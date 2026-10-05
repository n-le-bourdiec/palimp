"""Year of standard RT_FLOW lines, whose syslog timestamp has none."""

from datetime import datetime
from pathlib import Path

from typer.testing import CliRunner

from palimp.cli import app
from palimp.formats.rt_flow import parse_rt_flow
from palimp.ingest import ingest


def line(stamp: str, session: int, policy: str = "p1") -> str:
    return (
        f"{stamp} fw RT_FLOW: RT_FLOW_SESSION_CREATE: session created "
        f"10.0.0.1/40000->10.0.0.2/443 junos-https 10.0.0.1/40000->10.0.0.2/443 "
        f"None None 6 {policy} trust dc {session} N/A(N/A) ge-0/0/1.0"
    )


ROLLOVER = "\n".join(
    [
        line("Dec 30 23:10:00", 1),
        line("Dec 31 23:59:59", 2),
        line("Jan  1 00:00:05", 3),
        line("Jan  2 10:00:00", 4),
    ]
)


def test_rollover_with_forced_year() -> None:
    summaries, _, window = parse_rt_flow(ROLLOVER, year=2025)
    summary = summaries["trust/dc/p1"]
    assert summary.first_seen == datetime(2025, 12, 30, 23, 10)
    assert summary.last_seen == datetime(2026, 1, 2, 10, 0)
    assert window.year_source == "forced"
    assert (window.start, window.end) == (summary.first_seen, summary.last_seen)


def test_year_inferred_from_reference_before_rollover() -> None:
    # Newest commit in December, logs collected in early January.
    _, _, window = parse_rt_flow(ROLLOVER, reference=datetime(2025, 12, 20))
    assert window.year_source == "inferred"
    assert window.start == datetime(2025, 12, 30, 23, 10)
    assert window.end == datetime(2026, 1, 2, 10, 0)
    assert "2025 to 2026" in window.year_note and "--log-year" in window.year_note


def test_year_inferred_when_commits_are_old() -> None:
    # No commit for 11 months: the logs are still after the newest commit.
    text = line("Feb 10 08:00:00", 1)
    _, _, window = parse_rt_flow(text, reference=datetime(2025, 3, 15))
    assert window.end == datetime(2026, 2, 10, 8, 0)


def test_late_line_from_previous_year_does_not_move_the_clock() -> None:
    text = "\n".join(
        [line("Dec 31 23:59:58", 1), line("Jan  1 00:00:01", 2), line("Dec 31 23:59:59", 3)]
    )
    summaries, _, _ = parse_rt_flow(text, year=2025)
    assert summaries["trust/dc/p1"].last_seen == datetime(2026, 1, 1, 0, 0, 1)
    assert summaries["trust/dc/p1"].first_seen == datetime(2025, 12, 31, 23, 59, 58)


def test_no_year_source_leaves_times_unset() -> None:
    summaries, _, window = parse_rt_flow(ROLLOVER)
    assert summaries["trust/dc/p1"].first_seen is None
    assert window.year_source == "none" and window.undated_lines == 4


def test_iso_server_stamp_gives_the_year() -> None:
    text = "2026-01-01T00:00:02+00:00 collector " + line("Dec 31 23:59:59", 1)
    summaries, _, window = parse_rt_flow(text)
    assert summaries["trust/dc/p1"].first_seen == datetime(2025, 12, 31, 23, 59, 59)
    assert window.undated_lines == 0 and window.year_source == ""


def test_ingest_infers_year_and_warns(tmp_path: Path) -> None:
    (tmp_path / "logs").mkdir()
    (tmp_path / "config.set").write_text(
        "set security policies from-zone trust to-zone dc policy p1 then permit\n"
    )
    (tmp_path / "commits.txt").write_text("0   2025-12-20 10:00:00 UTC by ann via cli\n")
    (tmp_path / "logs" / "rt_flow.log").write_text(ROLLOVER + "\n")
    dataset = ingest(tmp_path)
    assert dataset.logs["trust/dc/p1"].last_seen == datetime(2026, 1, 2, 10, 0)
    assert any("inferred 2025 to 2026" in w for w in dataset.warnings)

    forced = ingest(tmp_path, log_year=2030)
    assert forced.logs["trust/dc/p1"].first_seen.year == 2030
    assert not any("inferred" in w for w in forced.warnings)

    out = tmp_path / "out.json"
    result = CliRunner().invoke(app, ["ingest", str(tmp_path), "-o", str(out)])
    assert result.exit_code == 0 and "inferred 2025 to 2026" in result.output
    result = CliRunner().invoke(
        app, ["ingest", str(tmp_path), "-o", str(out), "--log-year", "2025"]
    )
    assert result.exit_code == 0 and "inferred" not in result.output
