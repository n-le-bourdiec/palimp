"""T2 behavioral evidence: hit counts, log summaries, time patterns, recurrence."""

from datetime import date, timedelta
from pathlib import Path

import pytest

from palimp.behavior import recurrence, time_of_day
from palimp.evidence import collect
from palimp.ingest import ingest
from palimp.models import PolicyKey


def test_time_of_day() -> None:
    nightly = [0] * 24
    nightly[2] = 9
    nightly[14] = 1
    assert time_of_day(nightly, [2] * 5 + [0, 0]).startswith("nightly (90%")
    office = [0] * 24
    office[9] = office[15] = 10
    assert time_of_day(office, [4] * 5 + [0, 0]).startswith("business hours")
    assert time_of_day(office, [3] * 7).startswith("daytime")
    assert time_of_day([1] * 24, [3] * 7) == "around the clock"
    assert time_of_day([1, 1] + [0] * 22, [2] + [0] * 6) is None


def days_every(first: date, step: int, count: int) -> list[date]:
    return [first + timedelta(days=step * i) for i in range(count)]


START, END = date(2026, 1, 1), date(2026, 12, 31)


@pytest.mark.parametrize(
    ("days", "expected"),
    [
        (days_every(date(2026, 1, 5), 7, 50), "weekly (every Monday, 50 occurrences)"),
        ([date(2026, m, 3) for m in range(1, 13)], "monthly (around day 3, 12 occurrences)"),
        (days_every(date(2026, 1, 15), 91, 4), "quarterly (starting 2026-01-15, 4 occurrences)"),
        (days_every(START, 1, 365), "daily (active on 365 of 365 days)"),
        ([date(2026, 1, 3), date(2026, 1, 10)], "possibly weekly (2 occurrences 7 days apart"),
        ([date(2026, 6, 1)], "active on a single day (2026-06-01) of a 365-day log window"),
    ],
)
def test_recurrence(days: list[date], expected: str) -> None:
    assert recurrence(days, START, END).startswith(expected)


def test_daily_flow_that_stopped() -> None:
    hint = recurrence(days_every(START, 1, 30), START, date(2026, 3, 1))
    assert hint == (
        "daily from 2026-01-01 to 2026-01-30 (30 active days); "
        "no session in the last 30 days of the window"
    )


POLICY = "set security policies from-zone trust to-zone dc policy {name} {rest}\n"


def structured(day: int, hour: int, name: str, session: int) -> str:
    return (
        f"<14>1 2026-03-{day:02d}T{hour:02d}:10:00.000Z fw RT_FLOW - RT_FLOW_SESSION_CLOSE "
        f'[junos@2636.1.1.1.2.129 reason="TCP FIN" source-address="10.0.0.{session % 3}" '
        f'source-port="40000" destination-address="10.1.0.1" destination-port="5432" '
        f'service-name="tcp-5432" protocol-id="6" policy-name="{name}" '
        f'source-zone-name="trust" destination-zone-name="dc" session-id-32="{session}"]'
    )


@pytest.fixture
def artifacts(tmp_path: Path) -> Path:
    config = ""
    for name, rest in [
        ("logged", "then log session-close"),
        ("quiet", "then log session-close"),
        ("nolog", "then permit"),
        ("off", "then log session-close"),
    ]:
        config += POLICY.format(name=name, rest="then permit")
        config += POLICY.format(name=name, rest=rest)
    config += "deactivate security policies from-zone trust to-zone dc policy off\n"
    (tmp_path / "config.set").write_text(config)
    (tmp_path / "hitcount.txt").write_text(
        "Logical system: root-logical-system\n"
        "Index   From zone   To zone   Name     Policy count  Action\n"
        "1       trust       dc        nolog    120           Permit\n"
        "2       trust       dc        quiet    0             Permit\n"
        "3       trust       dc        logged   40            Permit\n"
    )
    (tmp_path / "logs").mkdir()
    lines = [structured(day, 2, "logged", day) for day in range(1, 31)]
    (tmp_path / "logs" / "rt_flow.log").write_text("\n".join(lines) + "\n")
    return tmp_path


def t2(artifacts: Path, name: str) -> dict[str, tuple[str, str]]:
    finding = collect(ingest(artifacts), PolicyKey.parse(f"trust/dc/{name}"))
    return {e.artifact: (e.signal, e.claim) for e in finding.evidence if e.tier == "T2"}


def test_present(artifacts: Path) -> None:
    items = t2(artifacts, "logged")
    assert items["hitcount.txt"] == (
        "present",
        "40 hits since the counters were last cleared (the clear date is not in hitcount.txt)",
    )
    signal, claim = items["logs/rt_flow.log"]
    assert signal == "present"
    assert claim.startswith("30 sessions logged in the log window 2026-03-01 to 2026-03-30")
    assert "sources 3 (10.0.0.0, 10.0.0.1, 10.0.0.2)" in claim
    assert "ports tcp/5432" in claim and "nightly (100%" in claim
    assert "recurrence: daily (active on 30 of 30 days)" in claim


def test_no_traffic_is_not_no_logging(artifacts: Path) -> None:
    quiet = t2(artifacts, "quiet")
    assert quiet["hitcount.txt"][0] == "absent"
    assert quiet["logs/rt_flow.log"][0] == "absent"
    assert "logs session-close, and no session was logged" in quiet["logs/rt_flow.log"][1]
    nolog = t2(artifacts, "nolog")
    assert nolog["hitcount.txt"][0] == "present"
    assert nolog["logs/rt_flow.log"][0] == "blind"
    assert "no `then log`" in nolog["logs/rt_flow.log"][1]


def test_deactivated_is_blind(artifacts: Path) -> None:
    off = t2(artifacts, "off")
    assert off["hitcount.txt"][0] == "blind" and "deactivated" in off["hitcount.txt"][1]
    assert off["logs/rt_flow.log"][0] == "blind"


def test_missing_artifacts_are_blind(artifacts: Path) -> None:
    (artifacts / "hitcount.txt").unlink()
    (artifacts / "logs" / "rt_flow.log").unlink()
    items = t2(artifacts, "logged")
    assert {signal for signal, _ in items.values()} == {"blind"}
