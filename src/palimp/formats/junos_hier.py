"""Reader for the hierarchical (curly-brace) Junos format, as printed by
`show configuration`, `show` in configuration mode and `show system rollback N`.

The text is walked into the statements `display set` would print (full path,
one per leaf, `deactivate` after an `inactive:` subtree) and fed to the model
builder of the set reader, so both formats give the same model.

Hierarchical specifics:
- `inactive: X` is read as `deactivate X`; `protect:` and `replace:` prefixes
  are dropped (they do not change what the statement is).
- `/* ... */` on the lines before a statement is an annotation of that
  statement (`annotate`); one on the same line after a statement is dropped,
  as Junos drops it. Annotations on a policy, or on a statement inside one,
  are kept on the policy (a T1 evidence source); others are not used.
- `#` starts a comment to the end of the line (`## Last commit: ...`,
  `## SECRET-DATA`), outside quoted strings.
- `[ a b ]` lists give one statement per value.
- `apply-groups` is reported, never expanded (statements inherited from
  configuration groups are missing from the model).
- Terminal captures: prompt, banner and elision lines are ignored. Output of
  `show X Y` in configuration mode, or of `show configuration X Y`, is
  relative to `X Y`; an `[edit X]` banner adds `X` in front.
"""

import re
from collections.abc import Iterator
from dataclasses import dataclass, field

from palimp.formats.junos_set import _Builder
from palimp.formats.terminal import edit_path, is_terminal_noise, shown_path
from palimp.models import Config

PREFIXES = ("inactive:", "protect:", "replace:")
WORD = re.compile(r'"((?:[^"\\]|\\.)*)"|([{};\[\]])|(/\*)|(#)|([^\s{};\[\]"]+)')


@dataclass
class Statement:
    """One statement as `display set` would print it, or an annotation."""

    kind: str  # "set", "deactivate", "annotate", "noise" or "unknown"
    path: list[str]
    line: int
    text: str = ""  # annotation text, or the raw text of an unknown statement


@dataclass
class _Frame:
    words: list[str]
    inactive: bool
    children: int = 0
    annotation: str | None = None


@dataclass
class _Walk:
    level: list[str] = field(default_factory=list)
    edit: list[str] = field(default_factory=list)
    stack: list[_Frame] = field(default_factory=list)
    words: list[str] = field(default_factory=list)
    start: int = 0
    note: str | None = None  # pending annotation
    note_parts: list[str] | None = None  # comment still open (multi-line)
    note_keep: bool = False  # the open comment annotates the next statement

    def path(self) -> list[str]:
        return self.level + [w for f in self.stack for w in f.words]


def _expand(words: list[str]) -> list[list[str]]:
    """`source-address [ a b ]` gives `source-address a` and `source-address b`."""
    if "[" not in words:
        return [words]
    i = words.index("[")
    j = words.index("]", i) if "]" in words[i:] else len(words)
    head, items, tail = words[:i], words[i + 1 : j], words[j + 1 :]
    return [head + [item] + tail for item in items] or [head + tail]


def _split_prefix(words: list[str]) -> tuple[bool, list[str]]:
    inactive = False
    while words and words[0] in PREFIXES:
        inactive = inactive or words[0] == "inactive:"
        words = words[1:]
    return inactive, words


def statements(text: str) -> Iterator[Statement]:
    """Walk hierarchical TEXT into statements, in configuration order."""
    w = _Walk()
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if w.note_parts is not None:
            end = line.find("*/")
            if end < 0:
                w.note_parts.append(line)
                continue
            w.note_parts.append(line[:end])
            if w.note_keep:
                w.note = " ".join(p for p in w.note_parts if p).strip()
            w.note_parts = None
            line = line[end + 2 :].strip()
        if not line:
            continue
        if not w.words and is_terminal_noise(line):
            yield Statement("noise", [], number, line)
            if not w.stack:
                banner = edit_path(line)
                if banner is not None:
                    w.edit = banner.split()
                    w.level = list(w.edit)
                shown = shown_path(line)
                if shown is not None:
                    mode, words = shown
                    w.level = (w.edit if mode == "edit" else []) + words
            continue
        yield from _line(w, line, number)
    if w.words:
        yield Statement("unknown", w.path() + w.words, w.start, " ".join(w.words))
    if w.stack:
        yield Statement("unknown", w.path(), len(text.splitlines()), f"{len(w.stack)} unclosed")


def _line(w: _Walk, line: str, number: int) -> Iterator[Statement]:
    for match in WORD.finditer(line):
        quoted, punct, comment, hash_, word = match.groups()
        if comment is not None:
            rest = line[match.end() :]
            end = rest.find("*/")
            # Only a note on its own line annotates the next statement.
            own_line = not w.words and not line[: match.start()].strip()
            if end < 0:
                w.note_parts, w.note_keep = [rest.strip()], own_line
                return
            if own_line:
                w.note = rest[:end].strip()
            yield from _line(w, rest[end + 2 :], number)
            return
        if hash_ is not None:
            return
        if quoted is not None or word is not None:
            if not w.words:
                w.start = number
            w.words.append(quoted if quoted is not None else word)
            continue
        if punct in "[]":
            w.words.append(punct)
            continue
        if punct == "{":
            inactive, words = _split_prefix(w.words)
            frame = _Frame(words, inactive, annotation=w.note)
            if w.stack:
                w.stack[-1].children += 1
            w.stack.append(frame)
            if w.note is not None:
                yield Statement("annotate", w.path(), number, w.note)
                w.note = None
            w.words = []
            continue
        if punct == ";":
            inactive, words = _split_prefix(w.words)
            w.words = []
            if not words:
                continue
            if w.stack:
                w.stack[-1].children += 1
            base = w.path()
            for one in _expand(words):
                if w.note is not None:
                    yield Statement("annotate", base + one, number, w.note)
                yield Statement("set", base + one, number)
                if inactive:
                    yield Statement("deactivate", base + one, number)
            w.note = None
            continue
        # "}"
        w.note = None
        if w.words:
            yield Statement("unknown", w.path() + w.words, w.start, " ".join(w.words))
            w.words = []
        if not w.stack:
            yield Statement("unknown", w.path(), number, "}")
            continue
        path = w.path()
        frame = w.stack.pop()
        if not frame.children:
            yield Statement("set", path, number)
        if frame.inactive:
            yield Statement("deactivate", path, number)


def parse_hierarchical(text: str, file: str = "config.set") -> Config:
    builder = _Builder(file)
    stats = builder.stats
    stats.format = "hierarchical"
    for statement in statements(text):
        stats.total += 1
        shown = " ".join(statement.path)
        if statement.kind == "noise":
            stats.ignored += 1
            continue
        if statement.kind == "unknown":
            builder.record("unknown", f"line {statement.line}: {statement.text or shown}")
            continue
        try:
            if statement.kind == "annotate":
                outcome = builder.annotate(statement.path, statement.text)
            else:
                outcome = builder.statement(statement.path, statement.kind == "deactivate")
        except (IndexError, ValueError):
            outcome = "unknown"
        builder.record(outcome, f"line {statement.line}: {statement.kind} {shown}")
    return builder.config()
