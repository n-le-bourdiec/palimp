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


def test_rename_joins_the_history_across_names(tmp_path: Path) -> None:
    # Commit 2 created users-to-crm-web; commit 0 renamed it (same match) with a
    # misleading comment; old log lines carry the old name.
    old = rule("users-to-crm-web", "users-all", "crm-web-01", log=True)
    new = rule("users_dc_crm_01", "users-all", "crm-web-01", log=True)
    sibling = rule("users-to-lms-web", "users-all", "lms-web-01")
    log = logline(1, "10.20.30.5", "users-to-crm-web", 1) + logline(
        5, "10.20.30.5", "users_dc_crm_01", 2
    )
    artifacts = write(
        tmp_path,
        [new + sibling, old + sibling, old + sibling, ""],
        ["remove unused", "", "CRM web access for all users"],
        log,
    )
    dataset = ingest(artifacts)
    history = dataset.history["trust/dc/users_dc_crm_01"]
    assert history.created_in_commit == 2
    assert history.named_in_commit == 0
    assert [(r.commit, r.old_key) for r in history.renames] == [(0, "trust/dc/users-to-crm-web")]
    assert 0 not in dataset.created_by_commit  # a rename is not a creation
    assert 0 not in dataset.removed_by_commit  # nor a removal
    finding = collect(dataset, PolicyKey.parse("trust/dc/users_dc_crm_01"))
    found = kinds(finding)
    assert found["commit_comment"].claim == "CRM web access for all users"
    assert "renamed from trust/dc/users-to-crm-web" in found["renamed"].claim
    assert "remove unused" in found["renamed"].claim
    assert "users-to-crm-web" not in found["created_together"].claim
    assert "2 sessions logged" in found["session_log"].claim
    assert "takeover" not in found


def test_same_match_twice_is_not_a_rename(tmp_path: Path) -> None:
    one = rule("a1", "users-all", "crm-web-01")
    two = rule("a2", "users-all", "crm-web-01")
    artifacts = write(
        tmp_path,
        [rule("b1", "users-all", "crm-web-01") + rule("b2", "users-all", "crm-web-01"), one + two],
        ["", ""],
    )
    dataset = ingest(artifacts)
    assert dataset.history["trust/dc/b1"].renames == []
    assert dataset.history["trust/dc/b1"].created_in_commit == 0


SHARED = "set security address-book global address hr-web-01 10.20.30.5/32\n"


def test_reused_address_gives_verify_and_a_conflict(tmp_path: Path) -> None:
    # crm-web-01 and hr-web-01 share 10.20.30.5: the policy written for crm may now
    # carry hr traffic. "late" has 50 hits.
    artifacts = write(tmp_path, [SHARED + rule("late", "users-all", "crm-web-01")], [""])
    finding = collect(ingest(artifacts), PolicyKey.parse("trust/dc/late"))
    item = kinds(finding)["shared_address"]
    assert item.tier == "T3" and item.apps == ["hr"]
    assert "10.20.30.5/32 of crm-web-01 (crm) is also the address of hr-web-01 (hr)" in item.claim
    assessment = finding.assessment
    assert assessment.verdict == "verify"
    assert assessment.verdict_rule == "V-SHARED-ADDRESS"
    assert item.id in assessment.verdict_evidence
    assert assessment.confidence != "HIGH"
    assert assessment.intent_apps[:2] == ["crm", "hr"]
    assert any(item.id in c.evidence for c in assessment.conflicts)


def test_shared_address_is_asked_of_the_firewall_team_once_per_address(tmp_path: Path) -> None:
    # Decision 0041: two rules on 10.20.30.5 give one question to the firewall team,
    # none to the owners.
    from palimp.questions import CLEANUP_NAME
    from palimp.questions import build as build_questions
    from palimp.report import FIREWALL_TEAM, SHARED_QUESTION, shared_addresses
    from palimp.report import build as build_report

    config = (
        SHARED + rule("late", "users-all", "crm-web-01") + rule("allow-all", "lms-net", "hr-web-01")
    )
    artifacts = write(tmp_path, [config], [""])
    report = build_report(ingest(artifacts))
    shared = shared_addresses(report.rules)
    assert len(shared) == 1
    assert shared[0].address == "10.20.30.5/32"
    assert shared[0].objects == ["crm-web-01", "hr-web-01"]
    assert len(shared[0].rules) == 2
    for entry in report.rules:
        if entry.finding.assessment.verdict_rule == "V-SHARED-ADDRESS":  # type: ignore[union-attr]
            assert entry.group == FIREWALL_TEAM and entry.question == SHARED_QUESTION
    questionnaires = build_questions(report)
    team = [q for q in questionnaires if q.name == CLEANUP_NAME]
    assert len(team) == 1 and team[0].text.count(SHARED_QUESTION) == 1
    assert set(shared[0].rules) <= set(team[0].rules)
    for q in questionnaires:
        if q.group != FIREWALL_TEAM:
            assert not set(q.rules) & set(shared[0].rules)


def test_no_shared_address_item_on_a_deactivated_policy(tmp_path: Path) -> None:
    deactivated = (
        rule("late", "users-all", "crm-web-01")
        + "deactivate security policies from-zone trust to-zone dc policy late\n"
    )
    artifacts = write(tmp_path, [SHARED + deactivated], [""])
    finding = collect(ingest(artifacts), PolicyKey.parse("trust/dc/late"))
    assert "shared_address" not in kinds(finding)


def probe(day: int, source: str, destination: str, name: str, session: int, back: int) -> str:
    return (
        logline(day, destination, name, session)
        .replace('source-address="10.10.1.9"', f'source-address="{source}"')
        .replace("]\n", f' packets-from-client="1" packets-from-server="{back}"]\n')
    )


def test_probe_only_traffic_is_not_in_use(tmp_path: Path) -> None:
    # 10.10.9.9 reaches three policies and three servers, never answered: a probe.
    # "late" (50 hits) sees only that probe; "allow-all" also sees an answered session.
    config = (
        rule("late", "users-all", "crm-web-01", log=True)
        + rule("allow-all", "users-all", "lms-web-01", log=True)
        + rule("dms-left", "users-all", "dms-web-01", log=True)
    )
    log = (
        probe(1, "10.10.9.9", "10.20.30.5", "late", 1, 0)
        + probe(1, "10.10.9.9", "10.20.10.5", "allow-all", 2, 0)
        + probe(1, "10.10.9.9", "10.20.42.5", "dms-left", 3, 0)
        + probe(2, "10.10.1.7", "10.20.10.5", "allow-all", 4, 12)
    )
    dataset = ingest(write(tmp_path, [config], [""], log))
    assert dataset.log_window.probe_sources == ["10.10.9.9"]
    late = collect(dataset, PolicyKey.parse("trust/dc/late"))
    assert kinds(late)["session_log"].signal == "absent"
    assert "probe" in kinds(late)["session_log"].claim
    assert late.assessment.verdict == "verify"
    assert late.assessment.verdict_rule == "V-PROBE-ONLY"
    mixed = collect(dataset, PolicyKey.parse("trust/dc/allow-all"))
    assert kinds(mixed)["session_log"].signal == "present"
    assert "1 of the sessions are unanswered probes" in kinds(mixed)["session_log"].claim
    assert "probe_only" not in kinds(mixed)


def test_unanswered_sessions_from_one_policy_are_not_probes(tmp_path: Path) -> None:
    # A dead server: unanswered, but the source reaches one policy only.
    config = rule("late", "users-all", "crm-web-01", log=True)
    log = probe(1, "10.10.1.7", "10.20.30.5", "late", 1, 0) + probe(
        2, "10.10.1.7", "10.20.30.5", "late", 2, 0
    )
    dataset = ingest(write(tmp_path, [config], [""], log))
    assert dataset.log_window.probe_sources == []
    finding = collect(dataset, PolicyKey.parse("trust/dc/late"))
    assert finding.assessment.verdict_rule == "V-TRAFFIC"


def test_shared_source_address_lowers_confidence_not_the_verdict(tmp_path: Path) -> None:
    # crm-web-01 (source) shares 10.20.30.5 with hr-web-01: the name may be stale.
    artifacts = write(tmp_path, [SHARED + rule("late", "crm-web-01", "lms-web-01")], [""])
    finding = collect(ingest(artifacts), PolicyKey.parse("trust/dc/late"))
    item = kinds(finding)["shared_source"]
    assert item.apps == ["hr"] and "the name may be stale" in item.claim
    assert "shared_address" not in kinds(finding)
    assessment = finding.assessment
    assert assessment.verdict == "keep"
    assert assessment.confidence != "HIGH"
    assert any(item.id in c.evidence for c in assessment.conflicts)
