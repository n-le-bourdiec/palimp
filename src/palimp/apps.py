"""Application names found in the artifacts, to tell which application a text or object names.

Plain rules, no scoring. Applications are learned from the input itself:
- the related CI column of tickets.csv (for example `webshop`);
- short names used in ticket summaries, mapped to the related CI of the same
  ticket (`Decom ESHOP` with related CI `webshop` gives `eshop` -> `webshop`).
  A short name seen with two different related CIs is ambiguous and dropped;
- the first segment of address object names (`crm-db-01` gives `crm`), unless
  it is a role word such as `pc`, `users` or `servers`. A segment that is
  already a ticket alias (`bkp-01` with tickets `BKP ...` for `backup`) names
  that application. A segment of at least 3 letters that is the start of
  exactly one related CI is an abbreviation of it (`mon-01` with related CI
  `shared-monitoring` gives `mon` -> `monitoring`). Shorter segments are never
  read as abbreviations (`bi` must not name `billing`).

A token names an application when it is one of the learned names or aliases.
Free text gets no prefix matching: `web` must not name `webshop`.

Regional instances (session 24). Related CIs such as `payroll-uk` and
`hr-de` end with a two-letter instance suffix; the suffixes seen this way are
learned. A name followed by a learned suffix (`payroll-pl-app-01`,
`fw-bi-nl`) names that instance, `payroll-pl`, even when no ticket names it:
an exact match. A bare name is never expanded to one of its instances
(`payroll` does not name `payroll-uk`). A bare name that is not itself a
related CI while instances of it exist is ambiguous: `candidates` lists the
instances it may stand for, and confidence is capped (palimp.assess).
"""

import re
from dataclasses import dataclass, field

from palimp.models import Dataset

# Words that say who or what kind of host or network, not which application.
ROLE_WORDS = frozenset(
    {
        "pc",
        "server",
        "servers",
        "srv",
        "mgmt",
        "lan",
        "subnet",
        "ws",
        "user",
        "users",
        "vendor",
        "partner",
        "host",
        "hosts",
        "net",
        "network",
        "any",
        "all",
        "grp",
        "group",
        "h",
        "n",
        "shared",
        "new",
        "old",
    }
)
TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9]*")
SHORT_NAME = re.compile(r"\b[A-Z][A-Z0-9]{1,9}\b")
TICKET_ID = re.compile(r"^(?:CHG|INC|RITM|REQ|CR|SR|TASK)\d*$")


@dataclass
class Vocabulary:
    names: set[str] = field(default_factory=set)
    aliases: dict[str, str] = field(default_factory=dict)
    # Related CIs of tickets.csv, and the instance suffixes they use (`uk`, `pl`).
    cis: set[str] = field(default_factory=set)
    regions: set[str] = field(default_factory=set)
    # Bare name -> its instances (`payroll` -> `payroll-pl`, `payroll-uk`).
    instances: dict[str, list[str]] = field(default_factory=dict)

    def lookup(self, token: str) -> str | None:
        token = token.lower()
        if token in ROLE_WORDS:
            return None
        if token in self.names:
            return token
        return self.aliases.get(token)

    def _apps(self, tokens: list[tuple[str, bool]]) -> list[str]:
        """Applications named by TOKENS, each with whether it is joined to the next one
        by `-` or `_` (`payroll` + `pl` gives the instance `payroll-pl`)."""
        found: list[str] = []
        i = 0
        while i < len(tokens):
            token, joined = tokens[i]
            token = token.lower()
            after = tokens[i + 1][0].lower() if joined and i + 1 < len(tokens) else ""
            app = self.lookup(token)
            if after and self.regions and f"{token}-{after}" in self.names | self.cis:
                app, i = f"{token}-{after}", i + 1
            elif app and after in self.regions:
                app, i = f"{self.base(app)}-{after}", i + 1
            if app and app not in found:
                found.append(app)
            i += 1
        return found

    def base(self, app: str) -> str:
        """`payroll-uk` gives `payroll`; a name with no instance suffix is its own base."""
        head, _, tail = app.rpartition("-")
        return head if head and tail in self.regions else app

    def candidates(self, app: str) -> list[str]:
        """Instances a bare name may stand for, when it is ambiguous; [] otherwise."""
        if app in self.cis:
            return []
        return [i for i in self.instances.get(app, []) if i != app]

    def in_text(self, text: str) -> list[str]:
        """Applications named in free text (comment, description, ticket summary)."""
        text = text or ""
        tokens: list[tuple[str, bool]] = []
        matches = [m for m in TOKEN.finditer(text) if not TICKET_ID.match(m.group().upper())]
        for m, nxt in zip(matches, [*matches[1:], None], strict=False):
            joined = nxt is not None and text[m.end() : nxt.start()] in ("-", "_")
            tokens.append((m.group(), joined))
        return self._apps(tokens)

    def in_object(self, name: str) -> list[str]:
        """Applications named by an address object name, for example `vendor-bi-52`."""
        tokens: list[tuple[str, bool]] = []
        for token in re.split(r"[-_.]", name):
            if not token.isalpha():
                if tokens:
                    tokens[-1] = (tokens[-1][0], False)
                continue
            tokens.append((token, True))
        return self._apps(tokens)


def _ci(value: str | None) -> str | None:
    """Related CI as an application name: `shared-dns` gives `dns`."""
    if not value:
        return None
    value = value.strip().lower()
    return value.removeprefix("shared-") or None


# Shortest object name segment read as an abbreviation of a related CI.
MIN_ABBREVIATION = 3


def vocabulary(dataset: Dataset, instances: bool = True) -> Vocabulary:
    """The applications of DATASET. Without `instances`, regional instances are not
    learned: the reading before session 24, kept for positive not-live signals
    (palimp.notlive, palimp.lineage) until the project lead approves the move."""
    vocab = Vocabulary()
    for ticket in dataset.tickets.values():
        if app := _ci(ticket.related_ci):
            vocab.names.add(app)
    vocab.cis = set(vocab.names)
    for ci in vocab.cis if instances else ():
        head, _, tail = ci.rpartition("-")
        if head and len(tail) == 2 and tail.isalpha() and tail not in ROLE_WORDS:
            vocab.regions.add(tail)
    cis = sorted(vocab.names)
    seen: dict[str, set[str]] = {}
    for ticket in dataset.tickets.values():
        app = _ci(ticket.related_ci)
        if not app:
            continue
        for short in SHORT_NAME.findall(ticket.summary or ""):
            if not TICKET_ID.match(short):
                seen.setdefault(short.lower(), set()).add(app)
    for short, apps in seen.items():
        if len(apps) == 1 and short not in vocab.names and short not in ROLE_WORDS:
            vocab.aliases[short] = next(iter(apps))
    for name in dataset.config.addresses:
        first = re.split(r"[-_.]", name.lower())[0]
        if not first.isalpha() or len(first) < 2 or first in ROLE_WORDS:
            continue
        if first in vocab.names or first in vocab.aliases:
            continue
        if any(vocab.base(ci) == first for ci in cis if ci != first):
            vocab.names.add(first)  # the bare name of regional instances, never one of them
            continue
        expanded = [ci for ci in cis if ci.startswith(first)]
        if len(first) >= MIN_ABBREVIATION and len(expanded) == 1:
            vocab.aliases[first] = expanded[0]
        else:
            vocab.names.add(first)
    found = set(vocab.cis)
    for name in dataset.config.addresses:
        found.update(vocab.in_object(name))
    for app in sorted(found):
        if (base := vocab.base(app)) != app:
            vocab.instances.setdefault(base, []).append(app)
    return vocab
