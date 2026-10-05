"""Readers against published Junos output (decisions 0013 and 0015).

Each test reads a fixture from tests/fixtures/junos_docs/ (header removed) and
checks one gap from docs/format-assumptions.md. Short inline samples are used
only where no published sample exists; they are built from the documented
templates and say so.
"""

from datetime import datetime
from pathlib import Path

from palimp.formats.commits import parse_commits
from palimp.formats.hitcount import parse_hitcount
from palimp.formats.junos_set import parse_set
from palimp.formats.rt_flow import parse_event, parse_rt_flow

FIXTURES = Path(__file__).parent / "fixtures" / "junos_docs"


def by_name(summaries: dict, name: str):
    """The only log summary of policy NAME (summaries are keyed by FROM/TO/NAME)."""
    (summary,) = [s for s in summaries.values() if s.policy_name == name]
    return summary


def body(name: str) -> str:
    lines = (FIXTURES / name).read_text(encoding="utf-8").splitlines()
    return "\n".join(lines[lines.index("# ---") + 1 :]) + "\n"


# G1: prompt, banner, completion and elision lines are ignored, not unknown.


def test_g1_prompt_lines_ignored() -> None:
    commits, stats = parse_commits(body("show_system_commit_rollback_pending.txt"))
    assert len(commits) == 1 and stats.unknown == 0 and stats.ignored == 1
    rows, stats = parse_hitcount(body("hitcount_logical_system.txt"))
    assert len(rows) == 1 and stats.unknown == 0
    config = parse_set(body("display_set_deactivate.txt"))
    assert config.stats.unknown == 0


# G2: `display set relative` lines get the `[edit ...]` level back.


def test_g2_display_set_relative() -> None:
    config = parse_set(body("display_set_pipe.txt"))
    assert config.stats.unknown == 0
    relative = (
        "[edit security policies]\n"
        "user@host# show | display set relative\n"
        "set from-zone users to-zone servers policy p1 match source-address any\n"
        "set from-zone users to-zone servers policy p1 then permit\n"
        "[edit]\n"
        "user@host# show | display set\n"
        "set security policies from-zone users to-zone servers policy p2 then deny\n"
    )
    config = parse_set(relative)
    assert config.stats.unknown == 0
    assert [p.name for p in config.policies] == ["p1", "p2"]


# G3: the trailing `rescue` entry and `...` are ignored.


def test_g3_rescue_and_elision() -> None:
    commits, stats = parse_commits(body("show_system_commit.txt"))
    assert [c.index for c in commits] == [0, 1, 2, 3, 4, 5]
    assert [c.client for c in commits[:4]] == ["other", "cli", "cli", "button"]
    assert stats.unknown == 0 and stats.ignored == 3


# G4: known suffixes after the method are split from free text.


def test_g4_commit_confirmed() -> None:
    (commit,), _ = parse_commits(body("show_system_commit_rollback_pending.txt"))
    assert (commit.commit_type, commit.rollback_minutes) == ("confirmed", 10)
    assert commit.extra == "" and commit.comment == ""
    (commit,), _ = parse_commits(body("show_system_commit_rollback_pending_12.3.txt"))
    assert (commit.commit_type, commit.rollback_minutes) == ("confirmed", 3)


def test_g4_revision_and_activate() -> None:
    commits, stats = parse_commits(body("show_system_commit_include_revision.txt"))
    assert commits[0].revision == "re0-1596309177-4" and commits[0].extra == ""
    assert stats.unknown == 0
    commits, _ = parse_commits(body("show_system_commit_activate.txt"))
    assert commits[0].commit_type == "activate" and commits[0].extra == ""


# VSRX-4d: comment on the next line, indented (practitioner capture, real vMX).


def test_vsrx4d_comment_on_next_line() -> None:
    commits, stats = parse_commits(body("show-system-commit-vmx-2023.txt"))
    assert stats.unknown == 0
    assert [c.index for c in commits] == list(range(11))
    assert commits[0].comment == "Commit 11 / Rollback 0"
    assert commits[10].comment == "Commit 1 / Rollback 10"
    assert commits[0].time_zone == "UTC" and commits[0].user == "lab"


# G5: right-aligned indexes start new entries instead of extending a comment.


def test_g5_right_aligned_indexes() -> None:
    commits, stats = parse_commits(body("rollback_completions_0_49.txt"))
    assert [c.index for c in commits] == list(range(50))
    assert all(c.comment == "" for c in commits)
    assert commits[10].user == "def" and commits[49].user == "vw"
    assert stats.unknown == 0


# G6: hit-count layouts; rows in any order, Index is only a line number.


def test_g6_hitcount_detail_layout() -> None:
    rows, stats = parse_hitcount(body("hitcount_detail.txt"))
    assert [(r.name, r.count, r.action) for r in rows] == [
        ("policy1", 5202, "Permit"),
        ("policy2", 5202, "Reject"),
    ]
    assert stats.unknown == 0


def test_g6_hitcount_legacy_layout() -> None:
    rows, stats = parse_hitcount(body("hitcount_legacy.txt"))
    assert [(r.from_zone, r.to_zone, r.name, r.count) for r in rows] == [
        ("untrust", "vrtrust", "policy1", 40),
        ("untrust", "trust", "policy2", 20),
        ("untrust", "trust", "policy3", 80),
    ]
    assert all(r.action == "" for r in rows)
    assert stats.unknown == 0 and stats.ignored == 3


def test_g6_hitcount_rows_in_any_order() -> None:
    lines = body("hitcount_legacy.txt").splitlines()
    header, rows, footer = lines[:2], lines[2:5], lines[5:]
    shuffled = "\n".join(header + [rows[2], rows[0], rows[1]] + footer)
    renumbered = shuffled.replace(" 3       untrust", " 9       untrust")
    expected = {r.name: r for r in parse_hitcount(body("hitcount_legacy.txt"))[0]}
    for text in (shuffled, renumbered):
        got, stats = parse_hitcount(text)
        assert {r.name: r for r in got} == expected and stats.unknown == 0


# G7: logical-system message types count as their base type.


def test_g7_logical_system_messages() -> None:
    summaries, stats, _ = parse_rt_flow(body("rt_flow_structured_12.1x47.txt"))
    lsys = by_name(summaries, "lsys1trust-to-lsys1trust")
    assert (lsys.create, lsys.close) == (1, 2)
    assert stats.unknown == 0
    first = next(
        line for line in body("rt_flow_structured_12.1x47.txt").splitlines() if "_LS" in line
    )
    event = parse_event(first)
    assert event.kind == "create" and event.logical_system == "LSYS1"


# Session ids: `session-id-32` (12.x) is read as the session id.


def test_session_id_32() -> None:
    line = body("rt_flow_structured_12.1x47.txt").splitlines()[0]
    event = parse_event(line)
    assert event.session_id == "60000442"
    assert (event.from_zone, event.to_zone) == ("client", "server")


# G8: structured lines stored by a syslog server (prefix, no <PRI>).


def test_g8_structured_from_syslog_server() -> None:
    summaries, stats, _ = parse_rt_flow(body("rt_flow_structured_12.3_remote.txt"))
    summary = by_name(summaries, "trust-untrust")
    assert (summary.create, summary.close) == (1, 2)
    # Device time, not the server's receive time.
    assert summary.first_seen == datetime(2010, 9, 6, 4, 24, 22, 94000)
    assert stats.unknown == 0


def test_g8_server_with_iso_prefix() -> None:
    line = body("rt_flow_structured_12.1x47.txt").splitlines()[0].removeprefix("<14>")
    event = parse_event("2011-08-28T21:14:44+02:00 collector-01 " + line)
    assert event.policy_name == "client-to-server"
    assert event.timestamp == datetime(2011, 8, 28, 21, 14, 43)


# G9: standard text after the closing `]` (page line wrapping undone).


def test_g9_text_after_bracket() -> None:
    text = body("rt_flow_structured_wrapped.txt")
    messages = ["<14>1" + part for part in text.split("<14>1") if part.strip()]
    joined = "\n".join(" ".join(m.split()) for m in messages)
    summaries, stats, _ = parse_rt_flow(joined)
    assert (by_name(summaries, "policy1").create, by_name(summaries, "policy1").close) == (1, 1)
    assert stats.unknown == 0


# G10: standard (unstructured) RT_FLOW, as stored by a syslog server.


def test_g10_standard_from_syslog_server() -> None:
    text = body("rt_flow_standard_12.3_remote.txt")
    summaries, stats, _ = parse_rt_flow(text)
    summary = by_name(summaries, "trust-untrust")
    assert (summary.create, summary.close) == (1, 1)
    # No year in BSD syslog timestamps: counted, times left unset.
    assert summary.first_seen is None
    # "last message repeated" is not an RT_FLOW message.
    assert stats.unknown == 0 and stats.ignored == 1

    summaries, _, _ = parse_rt_flow(text, year=2010)
    summary = by_name(summaries, "trust-untrust")
    assert summary.first_seen == datetime(2010, 9, 6, 2, 52, 30)
    assert summary.last_seen == datetime(2010, 9, 6, 2, 53, 49)


def test_g10_standard_fields() -> None:
    create, _, close = body("rt_flow_standard_12.3_remote.txt").splitlines()
    event = parse_event(create)
    assert (event.kind, event.policy_name, event.from_zone, event.to_zone, event.session_id) == (
        "create",
        "trust-untrust",
        "trust",
        "untrust",
        "192",
    )
    assert parse_event(close).kind == "close"
    # Same message as written in the device's own log file (no server prefix).
    device = "Sep  6 02:52:30 srx-01 " + create[create.index("RT_FLOW:") :]
    assert parse_event(device, year=2010).timestamp == datetime(2010, 9, 6, 2, 52, 30)


def test_g10_current_release_templates() -> None:
    # Built from the 22.2R1 templates in syslog_explorer_rt_flow_session_*.txt
    # (no published sample line): connection tags and NAT rule types included.
    create = (
        "RT_FLOW: RT_FLOW_SESSION_CREATE: session created 10.1.1.5/51000->10.2.2.9/443 0x0 "
        "junos-https 10.1.1.5/51000->10.2.2.9/443 0x0 N/A N/A N/A N/A 6 users-to-crm users "
        "servers 4242 N/A(N/A) ge-0/0/1.0 UNKNOWN UNKNOWN UNKNOWN No"
    )
    deny = (
        "RT_FLOW: RT_FLOW_SESSION_DENY: session denied 10.1.1.5/8->10.2.2.9/0 0x0 icmp 1(8) "
        "deny-all users servers UNKNOWN UNKNOWN N/A(N/A) ge-0/0/1.0 No policy deny 0"
    )
    event = parse_event(create)
    assert (event.policy_name, event.from_zone, event.to_zone, event.session_id) == (
        "users-to-crm",
        "users",
        "servers",
        "4242",
    )
    event = parse_event(deny)
    assert (event.kind, event.policy_name, event.to_zone) == ("deny", "deny-all", "servers")
