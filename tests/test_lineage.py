"""History lineage (palimp.lineage), counter clears (palimp.counters), stopped flows."""

from datetime import date, timedelta
from pathlib import Path

from palimp.assess import assess
from palimp.behavior import stopped
from palimp.evidence import collect
from palimp.formats.junos_set import parse_set
from palimp.ingest import ingest
from palimp.models import Dataset, Evidence, Finding, Policy, PolicyKey

ADDRESSES = """\
set security address-book global address users-all 10.10.0.0/16
set security address-book global address lms-net 10.20.10.0/24
set security address-book global address lms-web-01 10.20.10.5/32
set security address-book global address crm-web-01 10.20.30.5/32
set security address-book global address dms-db-01 10.20.40.5/32
set security address-book global address dms-db-02 10.20.41.5/32
set security address-book global address dms-web-01 10.20.42.5/32
set security address-book global address pc-aa-01 10.10.1.1/32
set security address-book global address pc-bb-02 10.10.1.2/32
set security address-book global address pc-cc-03 10.10.1.3/32
"""


def rule(
    name: str, source: str, destination: str, app: str = "junos-https", log: bool = False
) -> str:
    prefix = f"set security policies from-zone trust to-zone dc policy {name}"
    text = (
        f"{prefix} match source-address {source}\n"
        f"{prefix} match destination-address {destination}\n"
        f"{prefix} match application {app}\n"
        f"{prefix} then permit\n"
    )
    return text + (f"{prefix} then log session-close\n" if log else "")


def commits(*comments: str) -> str:
    lines = []
    for index, comment in enumerate(comments):
        lines.append(f"{index}   2026-03-{20 - index:02d} 10:00:00 UTC by bob via cli")
        if comment:
            lines.append(f"    {comment}")
    return "\n".join(lines) + "\n"


def write(tmp_path: Path, configs: list[str], comments: list[str], log: str = "") -> Path:
    (tmp_path / "rollbacks").mkdir()
    (tmp_path / "config.set").write_text(ADDRESSES + configs[0])
    for index, config in enumerate(configs[1:], start=1):
        (tmp_path / "rollbacks" / f"rollback-{index:02d}.set").write_text(ADDRESSES + config)
    (tmp_path / "commits.txt").write_text(commits(*comments))
    (tmp_path / "hitcount.txt").write_text(
        "Index   From zone   To zone   Name     Policy count  Action\n"
        + "".join(
            f"{i}   trust   dc   {name}   {count}   Permit\n"
            for i, (name, count) in enumerate(
                [("tmp-allow", 50), ("allow-all", 50), ("late", 50), ("dms-left", 0)], start=1
            )
        )
    )
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "rt_flow.log").write_text(log)
    return tmp_path


def logline(day: int, destination: str, name: str, session: int) -> str:
    return (
        f"<14>1 2026-03-{day:02d}T10:10:00.000Z fw RT_FLOW - RT_FLOW_SESSION_CLOSE "
        f'[junos@2636.1.1.1.2.129 reason="TCP FIN" source-address="10.10.1.9" '
        f'source-port="40000" destination-address="{destination}" destination-port="443" '
        f'service-name="junos-https" protocol-id="6" policy-name="{name}" '
        f'source-zone-name="trust" destination-zone-name="dc" session-id-32="{session}"]\n'
    )


TMP = rule("tmp-allow", "users-all", "lms-net", "any")
SPECIFIC = rule("users-to-lms-web", "users-all", "lms-web-01")
OTHER_ZONE = SPECIFIC.replace("trust to-zone dc", "trust to-zone dmz")


def kinds(finding: Finding) -> dict[str, Evidence]:
    return {e.kind: e for e in finding.evidence}


def test_policy_that_took_over_removed_rules_is_load_bearing(tmp_path: Path) -> None:
    # Commit 0 removed users-to-lms-web while tmp-allow existed and covers it.
    artifacts = write(tmp_path, [TMP, TMP + SPECIFIC + OTHER_ZONE], ["cleanup"])
    finding = collect(ingest(artifacts), PolicyKey.parse("trust/dc/tmp-allow"))
    item = kinds(finding)["takeover"]
    assert item.tier == "T3" and item.artifact == "rollbacks"
    assert "covers the whole match of 1 policy" in item.claim
    assert "trust/dc/users-to-lms-web (removed in commit 0" in item.claim
    assert "trust/dmz" not in item.claim  # another zone pair is never covered
    assessment = finding.assessment
    assert assessment.verdict_rule == "V-TEMPORARY-IN-USE"
    assert item.id in assessment.verdict_evidence


def test_takeover_without_a_temporary_label(tmp_path: Path) -> None:
    broad = rule("allow-all", "users-all", "lms-net", "any")
    artifacts = write(tmp_path, [broad, broad + SPECIFIC], ["cleanup"])
    finding = collect(ingest(artifacts), PolicyKey.parse("trust/dc/allow-all"))
    assert finding.assessment.verdict == "verify"
    assert finding.assessment.verdict_rule == "V-TAKEOVER-IN-USE"


def test_no_takeover_when_created_after_or_not_covering(tmp_path: Path) -> None:
    late = rule("late", "users-all", "lms-net", "any")
    narrow = rule("tmp-allow", "users-all", "lms-net", "junos-ssh")
    # late is created by commit 0, after commit 1 removed the specific rule.
    configs = [late + narrow, narrow, narrow + SPECIFIC]
    dataset = ingest(write(tmp_path, configs, ["add late", "cleanup"]))
    for name in ("late", "tmp-allow"):
        finding = collect(dataset, PolicyKey.parse(f"trust/dc/{name}"))
        assert "takeover" not in kinds(finding)


OLD = [
    rule(f"{pc}-to-dms", pc, "dms-db-01", "tcp-1433", log=True) for pc in ("pc-aa-01", "pc-bb-02")
]
NEW = [rule(f"{pc}-to-dms-new", pc, "dms-db-02", "tcp-1433") for pc in ("pc-aa-01", "pc-bb-02")]
LEFT = rule("dms-left", "pc-cc-03", "dms-db-01", "tcp-1433", log=True)


def migrated(tmp_path: Path, log: str, left: str = LEFT) -> Finding:
    # Commit 1 copies two policies to the new host, commit 0 removes the old ones.
    configs = ["".join(NEW) + left, "".join(OLD + NEW) + left, "".join(OLD) + left]
    artifacts = write(tmp_path, configs, ["DMS step 2", "DMS new hosts"], log)
    return collect(ingest(artifacts), PolicyKey.parse("trust/dc/dms-left"))


def test_leftover_of_a_migration_to_a_silent_host(tmp_path: Path) -> None:
    log = "".join(logline(day, "10.20.41.5", "pc-aa-01-to-dms-new", day) for day in range(1, 20))
    finding = migrated(tmp_path, log)
    item = kinds(finding)["migration_leftover"]
    assert "copied 2 policies from dms-db-01 to dms-db-02" in item.claim
    assert "no log line of any policy shows that address" in item.claim
    assert finding.assessment.verdict == "removal_candidate"
    assert finding.assessment.verdict_rule == "V-NOTLIVE"


def test_no_leftover_when_the_old_host_still_talks(tmp_path: Path) -> None:
    log = logline(3, "10.20.40.5", "some-other-policy", 1) + logline(4, "10.20.41.5", "x", 2)
    finding = migrated(tmp_path, log)
    assert "migration_leftover" not in kinds(finding)
    assert finding.assessment.verdict != "removal_candidate"


def test_no_leftover_without_logging_on_the_policy(tmp_path: Path) -> None:
    log = logline(4, "10.20.41.5", "x", 2)
    finding = migrated(tmp_path, log, LEFT.replace("then log session-close", "then permit"))
    assert "migration_leftover" not in kinds(finding)


def test_counter_cleared_after_logged_sessions(tmp_path: Path) -> None:
    config = rule("tmp-allow", "users-all", "lms-net", log=True) + rule(
        "dms-left", "pc-cc-03", "dms-db-01", log=True
    )
    log = logline(5, "10.20.40.5", "dms-left", 1)
    dataset = ingest(write(tmp_path, [config, config], [""], log))
    left = kinds(collect(dataset, PolicyKey.parse("trust/dc/dms-left")))
    assert "yet the log shows sessions up to 2026-03-05 10:10" in left["hit_count"].claim
    other = kinds(collect(dataset, PolicyKey.parse("trust/dc/tmp-allow")))
    assert "policy dms-left of the same zone pair" in other["hit_count"].claim
    assert other["counter_clear"].signal == "blind"
    # tmp-allow has hits and logs, but logged nothing: old hits, or logging misses it.
    finding = collect(dataset, PolicyKey.parse("trust/dc/tmp-allow"))
    assert finding.assessment.verdict_rule == "V-TRAFFIC-NOT-RECENT"
    assert "cleared inside the window" in finding.assessment.verdict_reason


def test_whole_zone_pair_at_zero() -> None:
    from palimp.counters import clears
    from palimp.models import HitCount, ParseStats

    names = ["a", "b", "c"]
    config = parse_set(
        "".join(rule(n, "users-all", "lms-net") for n in names)
        + rule("d", "users-all", "lms-net").replace("to-zone dc", "to-zone dmz")
    )
    rows = [HitCount(from_zone="trust", to_zone="dc", name=n, count=0) for n in names]
    rows.append(HitCount(from_zone="trust", to_zone="dmz", name="d", count=9))
    dataset = Dataset(
        source="t", config=config, hit_counts=rows, hit_count_stats=ParseStats(file="h")
    )
    assert clears(dataset)[("trust", "dc")].whole_pair == 3
    assert ("trust", "dmz") not in clears(dataset)


def test_stopped_flow() -> None:
    days = [date(2026, 1, 1) + timedelta(days=i) for i in range(20)]
    assert stopped(days, date(2026, 2, 20)) == 31
    assert stopped(days, date(2026, 1, 25)) is None  # 5 days of silence
    weekly = [date(2026, 1, 1) + timedelta(days=7 * i) for i in range(6)]
    assert stopped(weekly, date(2026, 3, 1)) is None  # sparse, not a daily flow
    policy = Policy(from_zone="trust", to_zone="dc", name="p", position=0)
    evidence = [
        Evidence(
            id="E1",
            tier="T2",
            artifact="x",
            locator="x",
            claim="c",
            signal="present",
            kind="session_log",
        ),
        Evidence(
            id="E2",
            tier="T2",
            artifact="x",
            locator="x",
            claim="c",
            signal="absent",
            kind="log_stopped",
        ),
    ]
    finding = Finding(key=policy.key, policy=policy, created_in_commit=None, evidence=evidence)
    result = assess(finding, Dataset(source="t", config=parse_set("")))
    assert (result.verdict, result.verdict_rule) == ("verify", "V-TRAFFIC-STOPPED")
