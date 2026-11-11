"""Regression tests for the audit findings B1, B2 and M1 (session 36, decision 0051).

The core safety rule: a rule that is live or still needed must never become a
removal_candidate. Each scenario below is an ordinary history that broke it:

- B1: a decommission text that names an application word, a negated or
  conditional text, or a text about another environment, read as the
  retirement of every rule of that application;
- B2: a second node added next to an old one (the old one kept as a standby)
  read as a migration, and the old node's silence in a short log read as a
  removal signal;
- M1: one-way UDP (syslog) read as scanner probes, which then cancelled the
  hit counters.

All names and addresses are invented for these tests.
"""

from datetime import datetime, timedelta
from pathlib import Path

from palimp.evidence import collect_all
from palimp.ingest import ingest
from palimp.models import Finding

NOT_LIVE = {"deactivated", "decommission"}


def address(name: str, value: str) -> str:
    return f"set security address-book global address {name} {value}\n"


def policy(
    name: str,
    source: str,
    destination: str,
    app: str,
    log: bool = False,
    zones: tuple[str, str] = ("dc", "dc"),
) -> str:
    prefix = f"set security policies from-zone {zones[0]} to-zone {zones[1]} policy {name}"
    text = (
        f"{prefix} match source-address {source}\n"
        f"{prefix} match destination-address {destination}\n"
        f"{prefix} match application {app}\n"
        f"{prefix} then permit\n"
    )
    return text + (f"{prefix} then log session-close\n" if log else "")


def commits(comment: str) -> str:
    return (
        "0   2026-04-22 09:12:40 UTC by kim via cli\n    routine change\n"
        f"1   2026-04-10 15:03:11 UTC by lee via cli\n    {comment}\n"
        "2   2026-03-28 08:44:02 UTC by kim via cli\n    earlier work\n"
    )


def write(
    tmp_path: Path,
    now: str,
    before: str,
    comment: str,
    hits: list[tuple[str, str, str, int]] | None = None,
    log: list[str] | None = None,
    tickets: str | None = None,
) -> Path:
    """config.set and rollback-01 are the configuration after commit 1, rollback-02
    the one before it: commit 1 made the change between `before` and `now`."""
    (tmp_path / "rollbacks").mkdir()
    (tmp_path / "config.set").write_text(now, encoding="utf-8")
    (tmp_path / "rollbacks" / "rollback-01.set").write_text(now, encoding="utf-8")
    (tmp_path / "rollbacks" / "rollback-02.set").write_text(before, encoding="utf-8")
    (tmp_path / "commits.txt").write_text(commits(comment), encoding="utf-8")
    if hits is not None:
        rows = "".join(
            f"{i}   {fz}   {tz}   {name}   {count}   Permit\n"
            for i, (fz, tz, name, count) in enumerate(hits, start=1)
        )
        (tmp_path / "hitcount.txt").write_text(
            "Index   From zone   To zone   Name     Policy count  Action\n" + rows,
            encoding="utf-8",
        )
    if log is not None:
        (tmp_path / "logs").mkdir()
        (tmp_path / "logs" / "rt_flow.log").write_text("".join(log), encoding="utf-8")
    if tickets is not None:
        (tmp_path / "tickets.csv").write_text(tickets, encoding="utf-8")
    return tmp_path


def session(
    when: datetime,
    name: str,
    source: str,
    destination: str,
    port: int,
    number: int,
    zones: tuple[str, str] = ("dc", "dc"),
    protocol: int = 6,
    back: int = 8,
) -> str:
    reason = "TCP FIN" if protocol == 6 else "idle Timeout"
    return (
        f"<14>1 {when:%Y-%m-%dT%H:%M:%S}.000Z fw-lab RT_FLOW - RT_FLOW_SESSION_CLOSE "
        f'[junos@2636.1.1.1.2.129 reason="{reason}" source-address="{source}" '
        f'source-port="51515" destination-address="{destination}" '
        f'destination-port="{port}" service-name="x" protocol-id="{protocol}" '
        f'policy-name="{name}" source-zone-name="{zones[0]}" '
        f'destination-zone-name="{zones[1]}" session-id-32="{number}" '
        f'packets-from-client="3" packets-from-server="{back}"]\n'
    )


def findings(artifacts: Path) -> dict[str, Finding]:
    return {str(f.key): f for f in collect_all(ingest(artifacts))}


def assert_justified(finding: Finding) -> None:
    """A removal_candidate names the one positive signal it rests on (decision 0051)."""
    assessment = finding.assessment
    assert assessment.verdict == "removal_candidate"
    signal = next(e for e in finding.evidence if e.id == assessment.removal_signal)
    assert signal.kind in NOT_LIVE
    assert signal.id in assessment.verdict_evidence


# B1: decommission text

LEDGER = (
    address("ledger-app-03", "10.61.4.13/32")
    + address("ledger-app-04", "10.61.4.14/32")
    + address("ledger-db-01", "10.61.5.21/32")
    + address("vault-bkp-01", "10.61.9.40/32")
    + address("payfeed-01", "10.61.7.70/32")
)
GONE = policy("app03-to-ledger-db", "ledger-app-03", "ledger-db-01", "junos-ms-sql")
STILL_USED = (
    policy("app04-to-ledger-db", "ledger-app-04", "ledger-db-01", "junos-ms-sql")
    + policy("ledger-db-dump", "vault-bkp-01", "ledger-db-01", "junos-ssh")
    + policy("payfeed-to-ledger-db", "payfeed-01", "ledger-db-01", "junos-ms-sql")
)
# Left behind by the retirement of ledger-app-03 and naming it: the control.
LEFT = policy("app03-admin", "ledger-app-03", "ledger-db-01", "junos-ssh")
USED = ["dc/dc/app04-to-ledger-db", "dc/dc/ledger-db-dump", "dc/dc/payfeed-to-ledger-db"]


def ledger(tmp_path: Path, comment: str, **kwargs) -> dict[str, Finding]:
    now = LEDGER + STILL_USED + LEFT
    return findings(write(tmp_path, now, LEDGER + GONE + STILL_USED + LEFT, comment, **kwargs))


def test_retiring_one_server_does_not_retire_the_application(tmp_path: Path) -> None:
    found = ledger(tmp_path, "retire ledger-app-03, replaced by ledger-app-04")
    for key in USED:
        assert found[key].assessment.verdict == "verify", key
    # The rule that names the retired server itself is the positive signal.
    assert_justified(found["dc/dc/app03-admin"])


def test_zero_hit_counters_are_no_removal_signal(tmp_path: Path) -> None:
    hits = [("dc", "dc", name.split("/")[-1], 0) for name in USED + ["dc/dc/app03-admin"]]
    found = ledger(tmp_path, "retire ledger-app-03, replaced by ledger-app-04", hits=hits)
    for key in USED:
        assert found[key].assessment.verdict == "verify", key


def test_ticket_about_a_staging_environment(tmp_path: Path) -> None:
    tickets = (
        "ticket_id,closed,requester,summary,related_ci\n"
        "CHG0071234,2026-04-10,Robin Sample,Retire LEDGER staging environment,ledger\n"
    )
    found = ledger(tmp_path, "remove duplicate rule", tickets=tickets)
    for key in [*USED, "dc/dc/app03-admin"]:
        assert found[key].assessment.verdict != "removal_candidate", key


def test_negated_decommission_text(tmp_path: Path) -> None:
    found = ledger(tmp_path, "do not decommission ledger-app-03 yet, only drop the duplicate rule")
    for key in [*USED, "dc/dc/app03-admin"]:
        assert found[key].assessment.verdict != "removal_candidate", key
    item = next(e for e in found["dc/dc/app03-admin"].evidence if e.kind.startswith("decom"))
    assert item.kind != "decommission"  # a question, not a not-live signal


def test_conditional_decommission_text(tmp_path: Path) -> None:
    found = ledger(tmp_path, "retire ledger-app-03 once ledger-app-04 is validated")
    assert found["dc/dc/app03-admin"].assessment.verdict == "verify"


def test_decommission_text_of_another_environment(tmp_path: Path) -> None:
    found = ledger(tmp_path, "decommission ledger-app-03 test instance")
    assert found["dc/dc/app03-admin"].assessment.verdict == "verify"


# B2: second node read as a migration

STOCK = (
    address("stock-db-01", "10.62.1.11/32")
    + address("stock-db-02", "10.62.1.12/32")
    + address("stock-app-01", "10.62.2.10/32")
    + address("rpt-srv-01", "10.62.3.10/32")
    + address("misc-a", "10.62.8.1/32")
    + address("misc-b", "10.62.8.2/32")
)
OLD_NODE = policy("app-to-stockdb", "stock-app-01", "stock-db-01", "junos-ms-sql", log=True)
OLD_NODE += policy("rpt-to-stockdb", "rpt-srv-01", "stock-db-01", "junos-ms-sql", log=True)
NEW_NODE = policy("app-to-stockdb2", "stock-app-01", "stock-db-02", "junos-ms-sql", log=True)
NEW_NODE += policy("rpt-to-stockdb2", "rpt-srv-01", "stock-db-02", "junos-ms-sql", log=True)
MISC = policy("misc", "misc-a", "misc-b", "junos-https", log=True)
STANDBY = "add second stock db node (stock-db-01 stays as standby)"
START = datetime(2026, 4, 23, 7, 0, 0)


def stock(tmp_path: Path, hours: int, **kwargs) -> dict[str, Finding]:
    log = [
        session(START + timedelta(hours=h), "app-to-stockdb2", "10.62.2.10", "10.62.1.12", 1433, h)
        for h in range(hours)
    ]
    log += [
        session(START + timedelta(hours=h), "misc", "10.62.8.1", "10.62.8.2", 443, 500 + h)
        for h in range(hours)
    ]
    now = STOCK + OLD_NODE + NEW_NODE + MISC
    return findings(write(tmp_path, now, STOCK + OLD_NODE + MISC, STANDBY, log=log, **kwargs))


def test_standby_node_is_not_a_removal_candidate(tmp_path: Path) -> None:
    found = stock(tmp_path, 48)
    for key in ("dc/dc/app-to-stockdb", "dc/dc/rpt-to-stockdb"):
        assessment = found[key].assessment
        assert assessment.verdict == "verify", key
        assert assessment.question == "Is the old node still kept as a standby?"


def test_short_log_and_zero_counters_are_no_removal_signal(tmp_path: Path) -> None:
    hits = [
        ("dc", "dc", "app-to-stockdb", 0),
        ("dc", "dc", "rpt-to-stockdb", 0),
        ("dc", "dc", "app-to-stockdb2", 5),
        ("dc", "dc", "misc", 5),
    ]
    found = stock(tmp_path, 1, hits=hits)
    for key in ("dc/dc/app-to-stockdb", "dc/dc/rpt-to-stockdb"):
        assert found[key].assessment.verdict == "verify", key


# M1: one-way UDP read as probes

LOGS = (
    address("stock-app-01", "10.62.2.10/32")
    + address("stock-log-01", "10.63.0.1/32")
    + address("stock-log-02", "10.63.0.2/32")
    + address("stock-log-03", "10.63.0.3/32")
)
SINKS = [("to-sink-1", "stock-log-01", "10.63.0.1")]
SINKS += [("to-sink-2", "stock-log-02", "10.63.0.2"), ("to-sink-3", "stock-log-03", "10.63.0.3")]
MGMT = ("dc", "mgmt")
SYSLOG = "".join(policy(n, "stock-app-01", o, "junos-syslog", True, MGMT) for n, o, _ in SINKS)
# Deleted by commit 1, it shares stock-app-01 with the syslog rules.
OLD_SYSLOG = policy("app-ntp", "stock-app-01", "stock-log-01", "junos-ntp", True, MGMT)
SYSLOG_HITS = [("dc", "mgmt", name, 48000 + i) for i, (name, _, _) in enumerate(SINKS)]


def syslog_log() -> list[str]:
    lines = []
    for day in range(30):
        for name, _, ip in SINKS:
            for k in range(4):
                when = datetime(2026, 4, 1) + timedelta(days=day, hours=6 * k)
                number = len(lines) + 1
                lines.append(
                    session(when, name, "10.62.2.10", ip, 514, number, MGMT, protocol=17, back=0)
                )
    return lines


def test_one_way_syslog_is_not_scanner_traffic(tmp_path: Path) -> None:
    now = LOGS + SYSLOG
    artifacts = write(tmp_path, now, now, "routine", hits=SYSLOG_HITS, log=syslog_log())
    dataset = ingest(artifacts)
    assert dataset.log_window.probe_sources == []
    for finding in collect_all(dataset):
        assert not [e for e in finding.evidence if e.kind == "probe_only"], str(finding.key)
        assert finding.assessment.verdict == "keep", str(finding.key)


def test_probe_reading_never_cancels_hits_against_a_not_live_signal(tmp_path: Path) -> None:
    artifacts = write(
        tmp_path,
        LOGS + SYSLOG,
        LOGS + SYSLOG + OLD_SYSLOG,
        "retire stock-app-01",
        hits=SYSLOG_HITS,
        log=syslog_log(),
    )
    for key, finding in findings(artifacts).items():
        assert finding.assessment.verdict != "removal_candidate", key
