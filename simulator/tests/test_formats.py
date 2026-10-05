"""Simulator output keeps the line shapes and field names of real Junos output.

Reference: the published samples in tests/fixtures/junos_docs/ (decisions 0013
and 0015, docs/format-assumptions.md). Each shape below is checked twice: every
fixture line it describes must match it (so the shape comes from real output,
not from the simulator), and every line the simulator writes must match it.
Field names are read from the fixtures themselves.
"""

import json
import re
from pathlib import Path

import pytest

from palimp_sim.generate import generate

FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "junos_docs"

# Knob combinations covering every format choice (levels.CHOICES, rescue_line),
# on Easy, and Medium with its per scenario draw (decision 0016).
VARIANTS = [
    ("easy", 2, {}),
    ("easy", 2, {"hitcount_layout": "legacy", "rescue_line": "true"}),
    ("easy", 2, {"log_release": "12.x", "log_collection": "syslog-server"}),
    ("easy", 2, {"log_release": "22.2", "log_collection": "syslog-server"}),
    ("medium", 0, {}),
    ("medium", 1, {"hitcount_layout": "legacy", "log_release": "12.x"}),
    ("medium", 2, {"log_collection": "syslog-server", "rescue_line": "false"}),
]


def body(name: str) -> list[str]:
    """Fixture lines after the `# ---` header, without terminal prompts or elisions."""
    lines = (FIXTURES / name).read_text(encoding="utf-8").splitlines()
    lines = lines[lines.index("# ---") + 1 :]
    return [
        line.rstrip()
        for line in lines
        if line.strip()
        and not re.match(r"^\S+@\S+[>#] ", line)
        and not line.startswith("[edit")
        and line.strip() != "..."
    ]


@pytest.fixture(scope="module", params=range(len(VARIANTS)))
def scenario(request) -> tuple[dict, dict[str, str]]:
    """Effective knobs (from the manifest, drawn or not) and the files."""
    level, seed, overrides = VARIANTS[request.param]
    files = {path: data.decode("utf-8") for path, data in generate(level, seed, overrides).items()}
    return json.loads(files["manifest.json"])["knobs"], files


def lines_of(text: str) -> list[str]:
    return text.splitlines()


# ---------------------------------------------------------------- config.set

SET_LINE = re.compile(r"^(set|deactivate) \S")


def test_set_shape_matches_fixtures() -> None:
    for name in ("display_set_deactivate.txt", "display_set_pipe.txt"):
        assert body(name)
        # display_set_pipe.txt also shows `display set relative` (lines
        # without the [edit] path); they are set lines all the same.
        assert all(SET_LINE.match(line) for line in body(name)), name


def test_config_and_rollbacks_are_set_lines(scenario) -> None:
    _, files = scenario
    for path, text in files.items():
        if path.endswith(".set"):
            bad = [line for line in lines_of(text) if not SET_LINE.match(line)]
            assert not bad, (path, bad[:3])


# ---------------------------------------------------------------- commits.txt

COMMIT_ENTRY = re.compile(
    r"^(?P<index>\d+) +\d{4}-\d\d-\d\d \d\d:\d\d:\d\d [A-Z]{2,5} by \S+ via (?P<method>\S+)"
    r"(?P<suffix> commit confirmed, rollback in \d+mins| commit activate| re0-\d+-\d+)?$"
)
COMMIT_COMMENT = re.compile(r"^ {4}\S.*$")
RESCUE = re.compile(r"^rescue +\d{4}-\d\d-\d\d \d\d:\d\d:\d\d [A-Z]{2,5} by \S+ via \S+$")
COMMIT_FIXTURES = [
    "show-system-commit-vmx-2023.txt",
    "show_system_commit.txt",
    "show_system_commit_rollback_pending.txt",
    "show_system_commit_rollback_pending_12.3.txt",
    "show_system_commit_include_revision.txt",
]
# `via netconf` is not shown in any sample (VSRX-4b); it stays allowed until a
# capture settles it, and simulator Easy does not use it.
UNVERIFIED_METHODS = {"netconf"}


def fixture_methods() -> set[str]:
    methods = set()
    for name in COMMIT_FIXTURES:
        for line in body(name):
            match = COMMIT_ENTRY.match(line)
            if match:
                methods.add(match.group("method"))
    return methods


def test_commit_shapes_match_fixtures() -> None:
    for name in COMMIT_FIXTURES:
        for line in body(name):
            assert COMMIT_ENTRY.match(line) or COMMIT_COMMENT.match(line) or RESCUE.match(line), (
                name,
                line,
            )
    # The practitioner capture shows comments on the next line, 4 spaces in.
    vmx = body("show-system-commit-vmx-2023.txt")
    assert any(COMMIT_COMMENT.match(line) for line in vmx)


def test_commit_lines_have_fixture_shapes(scenario) -> None:
    knobs, files = scenario
    lines = lines_of(files["artifacts/commits.txt"])
    methods = fixture_methods() | UNVERIFIED_METHODS
    previous = None
    for line in lines:
        entry = COMMIT_ENTRY.match(line)
        if entry:
            assert entry.group("method") in methods, line
            # Index padded to 4 columns as in current samples (`10  2023-...`).
            assert line[4] != " " and line[:4].rstrip() == entry.group("index"), line
            previous = "entry"
        elif COMMIT_COMMENT.match(line):
            assert previous == "entry", f"comment not right after an entry: {line}"
            previous = "comment"
        else:
            assert RESCUE.match(line), line
            assert line == lines[-1], "rescue must be the last line"
    assert any(RESCUE.match(line) for line in lines) == knobs["rescue_line"]


# ---------------------------------------------------------------- hitcount.txt


def columns(header: str) -> list[str]:
    return re.split(r"\s{2,}", header.strip())


HIT_ROW = re.compile(r"^ ?\d+ +\S+ +\S+ +\S+ +\d+( +(Permit|Deny|Reject))?$")


def test_hitcount_rows_match_fixtures() -> None:
    for name in ("hitcount_logical_system.txt", "hitcount_legacy.txt"):
        rows = [line for line in body(name)[1:] if line[:2].strip().isdigit()]
        assert rows and all(HIT_ROW.match(row) for row in rows), name


def test_hitcount_layout_matches_fixture(scenario) -> None:
    knobs, files = scenario
    lines = lines_of(files["artifacts/hitcount.txt"])
    if knobs["hitcount_layout"] == "legacy":
        reference = body("hitcount_legacy.txt")
        assert columns(lines[0]) == columns(reference[0])
        rows = lines[1:-2]
        assert lines[-2] == "" and re.match(r"^Number of policy: \d+$", lines[-1])
        assert re.match(r"^Number of policy: \d+$", reference[-1])
        assert int(lines[-1].split()[-1]) == len(rows)
    else:
        reference = body("hitcount_logical_system.txt")
        assert lines[0] == reference[0] == "Logical system: root-logical-system"
        assert columns(lines[1]) == columns(reference[1])
        # Columns start where the documentation header puts them.
        assert lines[1].index("From zone") == reference[1].index("From zone")
        assert lines[1].index("To zone") >= reference[1].index("To zone")
        rows = lines[2:]
    assert rows and all(HIT_ROW.match(row) for row in rows), rows[:3]
    # Index is a line number, not the evaluation order (VSRX-7b).
    assert [int(row.split()[0]) for row in rows] == list(range(1, len(rows) + 1))


# ---------------------------------------------------------------- rt_flow.log

STRUCTURED = re.compile(
    r"^(?P<prefix><14>1|[A-Z][a-z]{2} \d\d \d\d:\d\d:\d\d \d+\.\d+\.\d+\.\d+ 1) "
    r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d{3})?(Z|[+-]\d\d:\d\d)? \S+ RT_FLOW - "
    r"RT_FLOW_SESSION_(?P<kind>CREATE|CLOSE|DENY)(_LS)? "
    r"\[junos@2636(\.\d+)+ (?P<pairs>[^\]]*)\]$"
)
PAIR = re.compile(r'([a-z0-9-]+)="([^"]*)"')


def names(pairs: str) -> list[str]:
    assert PAIR.sub("", pairs).strip() == "", pairs
    return [name for name, _ in PAIR.findall(pairs)]


def template(kind: str, release: str = "22.2R1") -> list[str]:
    """Attribute list of a System Log Explorer template fixture."""
    lines = (FIXTURES / f"syslog_explorer_rt_flow_session_{kind.lower()}.txt").read_text(
        encoding="utf-8"
    )
    section = lines.split(f"## release {release}\n", 1)[1]
    attributes = section.split("## attributes:\n", 1)[1]
    return attributes.split("\n\n", 1)[0].split()


def sample_names_12x() -> dict[str, list[str]]:
    """First CREATE and CLOSE line of rt_flow_structured_12.1x47.txt."""
    found: dict[str, list[str]] = {}
    for line in body("rt_flow_structured_12.1x47.txt"):
        match = STRUCTURED.match(line)
        if match and "_LS" not in line:
            found.setdefault(match.group("kind"), names(match.group("pairs")))
    return found


def test_structured_shape_matches_fixtures() -> None:
    for name in ("rt_flow_structured_12.1x47.txt", "rt_flow_structured_12.3_remote.txt"):
        lines = body(name)
        assert lines and all(STRUCTURED.match(line) for line in lines), name
    remote = STRUCTURED.match(body("rt_flow_structured_12.3_remote.txt")[0])
    assert not remote.group("prefix").startswith("<")


def test_log_lines_have_fixture_shapes_and_names(scenario) -> None:
    knobs, files = scenario
    release = knobs["log_release"]
    server = knobs["log_collection"] == "syslog-server"
    expected = {}
    for kind in ("CREATE", "CLOSE"):
        if release == "12.x":
            expected[kind] = sample_names_12x()[kind]
        elif release == "22.2":
            expected[kind] = template(kind)
        else:
            full = template(kind)
            expected[kind] = full[: full.index("encrypted") + 1]
    lines = lines_of(files["artifacts/logs/rt_flow.log"])
    assert lines
    for line in lines:
        match = STRUCTURED.match(line)
        assert match, line
        assert match.group("prefix").startswith("<14>") != server, line
        assert names(match.group("pairs")) == expected[match.group("kind")], line
