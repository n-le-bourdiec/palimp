"""Medium level: trap coverage, format draw, clock skew, and the seven v1 traps.

Each trap test reads the visible artifacts the way a naive analyzer would, and
checks that this reading contradicts the ground truth as spec section 7.3
says: the trap is real, not only a tag.
"""

import json
import re
from datetime import datetime

import pytest

from palimp_sim.generate import draw_formats, generate
from palimp_sim.rng import Rng
from palimp_sim.voice import APP_CODES

V1_TRAPS = [
    "TRAP-LIVE-NOLOG",
    "TRAP-RARE-JOB",
    "TRAP-EMERGENCY-LOADBEARING",
    "TRAP-MISLEADING-COMMENT",
    "TRAP-BATCH-COMMIT",
    "TRAP-HISTORY-HORIZON",
    "TRAP-DEACTIVATED",
]
# Trap counts are drawn per scenario (decision 0018). Seeds 0 to 4 hold every
# v1 trap between them; 6 and 8 add scenarios without some of the drawn traps.
SEEDS = [0, 1, 2, 3, 4, 6, 8]
# Traps whose number of instances is drawn; the other two follow from the
# timeline and are in every scenario.
DRAWN_TRAPS = V1_TRAPS[:5]
TIMELINE_TRAPS = V1_TRAPS[5:]
COMMIT = re.compile(r"^(\d+)\s+(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) ")
ON_CALL_NAMES = ("temp-fix", "emergency-allow", "test", "tmp-allow")


class Scenario:
    """Visible artifacts parsed with plain text rules, plus the ground truth."""

    def __init__(self, seed: int, overrides: dict | None = None) -> None:
        files = generate("medium", seed, overrides)
        self.files = {path: data.decode("utf-8") for path, data in files.items()}
        self.truth = json.loads(self.files["ground_truth.json"])
        self.manifest = json.loads(self.files["manifest.json"])
        self.config = self.files["artifacts/config.set"]

    def rules(self, trap: str) -> list[dict]:
        return [r for r in self.truth["rules"] if trap in r["traps"]]

    def policy_lines(self, rule: dict, text: str | None = None) -> list[str]:
        key = rule["key"]
        prefix = (
            f"security policies from-zone {key['from_zone']} to-zone {key['to_zone']} "
            f"policy {key['name']} "
        )
        lines = (text or self.config).splitlines()
        return [line for line in lines if (line + " ").split(" ", 1)[1].startswith(prefix)]

    def hit_count(self, rule: dict) -> int | None:
        key = rule["key"]
        for line in self.files["artifacts/hitcount.txt"].splitlines():
            fields = line.split()
            if fields[:1] and fields[0].isdigit() and fields[1:4] == list(key.values()):
                return int(fields[4])
        return None

    def log_lines(self, rule: dict) -> int:
        name = rule["key"]["name"]
        return self.files["artifacts/logs/rt_flow.log"].count(f'policy-name="{name}"')

    def comments(self) -> dict[int, str]:
        found, current = {}, None
        for line in self.files["artifacts/commits.txt"].splitlines():
            match = COMMIT.match(line)
            if match:
                current = int(match.group(1))
            elif current is not None and line.startswith("    "):
                found[current] = line.strip()
        return found

    def rollback(self, index: int) -> str:
        if index == 0:
            return self.config
        return self.files[f"artifacts/rollbacks/rollback-{index:02d}.set"]

    def flow(self, flow_id: str) -> dict:
        return next(f for f in self.truth["flows"] if f["flow_id"] == flow_id)


@pytest.fixture(scope="module", params=SEEDS)
def medium(request) -> Scenario:
    return Scenario(request.param)


def misleading(rule: dict, artifact: str) -> list[dict]:
    return [e for e in rule["evidence"] if e["artifact"] == artifact and e["misleading"]]


# ------------------------------------------------------------------ coverage


def trap_counts(seed: int) -> dict[str, int]:
    truth = json.loads(generate("medium", seed)["ground_truth.json"])
    return {t: sum(1 for r in truth["rules"] if t in r["traps"]) for t in V1_TRAPS}


@pytest.mark.parametrize("seed", range(10))
def test_timeline_traps_in_every_medium_scenario(seed: int) -> None:
    counts = trap_counts(seed)
    assert all(counts[trap] for trap in TIMELINE_TRAPS), counts


def test_fixture_seeds_cover_every_trap_and_its_absence() -> None:
    counts = [trap_counts(seed) for seed in SEEDS]
    for trap in V1_TRAPS:
        assert any(c[trap] for c in counts), trap
    for trap in DRAWN_TRAPS:
        assert any(not c[trap] for c in counts), trap


@pytest.mark.full
def test_drawn_trap_distribution_over_seeds_0_to_99() -> None:
    """Each drawn trap is in 60 to 90% of scenarios, with varying counts."""
    counts = [trap_counts(seed) for seed in range(100)]
    for trap in DRAWN_TRAPS:
        values = [c[trap] for c in counts]
        share = sum(1 for v in values if v) / len(values)
        assert 0.6 <= share <= 0.9, (trap, share)
        assert len({v for v in values if v}) >= 2, (trap, sorted(set(values)))
    for trap in TIMELINE_TRAPS:
        assert all(c[trap] for c in counts), trap


# ------------------------------------------------------------------ format draw


def test_format_draw_is_recorded_and_applied(medium: Scenario) -> None:
    draw = medium.manifest["format_draw"]
    knobs = medium.manifest["knobs"]
    assert set(draw) == {"log_collection", "log_release", "hitcount_layout", "rescue_line"}
    assert all(knobs[name] == value for name, value in draw.items())
    log = medium.files["artifacts/logs/rt_flow.log"].splitlines()
    assert log[0].startswith("<14>1") == (draw["log_collection"] == "device")
    assert ("session-id-32=" in log[0]) == (draw["log_release"] == "12.x")
    hitcount = medium.files["artifacts/hitcount.txt"]
    assert hitcount.startswith("index ") == (draw["hitcount_layout"] == "legacy")
    last = medium.files["artifacts/commits.txt"].splitlines()[-1]
    assert last.startswith("rescue ") == draw["rescue_line"]


def test_format_draw_never_picks_22_2_and_covers_the_rest() -> None:
    seen: dict[str, set] = {}
    for seed in range(300):
        drawn = draw_formats(Rng(f"palimp-sim:medium:{seed}").derive("formats"), {})
        for name, value in drawn.items():
            seen.setdefault(name, set()).add(value)
    assert seen["log_release"] == {"12.x", "pre-22.2"}
    assert seen["log_collection"] == {"device", "syslog-server"}
    assert seen["hitcount_layout"] == {"standard", "legacy"}
    assert seen["rescue_line"] == {True, False}


def test_overrides_win_over_the_draw() -> None:
    overrides = {"log_release": "22.2", "log_collection": "device"}
    manifest = json.loads(generate("medium", 0, overrides)["manifest.json"])
    assert manifest["knobs"]["log_release"] == "22.2"
    assert manifest["knobs"]["log_collection"] == "device"
    assert "log_release" not in manifest["format_draw"]
    assert "syslog_clock_skew_seconds" not in manifest


def test_syslog_server_clock_is_skewed_by_a_few_seconds() -> None:
    scenario = Scenario(3, {"log_collection": "syslog-server"})
    skew = scenario.manifest["syslog_clock_skew_seconds"]
    assert 1 <= abs(skew) <= 6
    offsets = set()
    for line in scenario.files["artifacts/logs/rt_flow.log"].splitlines():
        server, device = line[:15], line.split(" 1 ", 1)[1].split(" ")[0]
        device_time = datetime.strptime(device[:19], "%Y-%m-%dT%H:%M:%S")
        server_time = datetime.strptime(f"{device_time.year} {server}", "%Y %b %d %H:%M:%S")
        offsets.add(round((server_time - device_time).total_seconds()))
    # Year boundaries aside, every line shows the same offset.
    assert offsets == {skew}


def test_easy_keeps_server_clock_equal_to_device_clock() -> None:
    manifest = json.loads(generate("easy", 1, {"log_collection": "syslog-server"})["manifest.json"])
    assert "syslog_clock_skew_seconds" not in manifest
    assert "format_draw" not in manifest


# ------------------------------------------------------------------ traps


def test_live_nolog_looks_dead_but_is_live(medium: Scenario) -> None:
    rules = medium.rules("TRAP-LIVE-NOLOG")
    clears = {(c["from_zone"], c["to_zone"]) for c in medium.manifest["hit_count_clears"]}
    for rule in rules:
        # Naive reading: no logging configured, no log line, zero hits: dead.
        assert not any(" then log " in line for line in medium.policy_lines(rule))
        assert medium.log_lines(rule) == 0
        assert medium.hit_count(rule) == 0
        # Truth: live; the counters of its zone pair were cleared recently.
        assert rule["status"]["live"] and rule["status"]["carried_flows"]
        assert (rule["key"]["from_zone"], rule["key"]["to_zone"]) in clears
        assert rule["expected"]["verdict"] == "keep"
        assert rule["expected"]["best_achievable_verdict"] == "verify"
        assert misleading(rule, "hitcount.txt")


def test_rare_job_has_no_hits_in_window_but_is_live(medium: Scenario) -> None:
    rules = medium.rules("TRAP-RARE-JOB")
    for rule in rules:
        assert medium.hit_count(rule) == 0
        assert medium.log_lines(rule) == 0
        schedules = {medium.flow(f)["schedule"] for f in rule["intent"]["flows"]}
        assert schedules <= {"quarterly", "yearly"}
        assert rule["status"]["live"]
        # Removing it would be the most severe error.
        assert rule["expected"]["verdict"] == "keep"
        assert rule["expected"]["best_achievable_verdict"] == "verify"
        assert misleading(rule, "hitcount.txt")


def test_emergency_rule_looks_temporary_but_carries_the_flow(medium: Scenario) -> None:
    rules = medium.rules("TRAP-EMERGENCY-LOADBEARING")
    pair_policies: dict[tuple, list[str]] = {}
    for line in medium.config.splitlines():
        match = re.match(
            r"^set security policies from-zone (\S+) to-zone (\S+) policy (\S+) ", line
        )
        if match:
            names = pair_policies.setdefault(match.groups()[:2], [])
            if match.group(3) not in names:
                names.append(match.group(3))
    for rule in rules:
        key = rule["key"]
        lines = medium.policy_lines(rule)
        # Naive reading: a temporary, broad rule on top of the list: remove it.
        assert re.sub(r"-\d+$", "", key["name"]) in ON_CALL_NAMES
        assert any(line.endswith(" match application any") for line in lines)
        # On top of its zone pair: only other emergency rules come before it.
        order = pair_policies[(key["from_zone"], key["to_zone"])]
        above = order[: order.index(key["name"])]
        assert all(re.sub(r"-\d+$", "", name) in ON_CALL_NAMES for name in above), above
        # Truth: the proper rules for its flows are gone, it is the only rule
        # that carries them.
        assert rule["intent"]["kind"] == "emergency_temporary"
        assert rule["status"]["live"] and rule["status"]["carried_flows"]
        inactive = {
            line.rsplit(" ", 1)[1]
            for line in medium.config.splitlines()
            if line.startswith(f"deactivate security policies from-zone {key['from_zone']} ")
        }
        for flow_id in rule["intent"]["flows"]:
            destination = medium.flow(flow_id)["destination"]
            others = [
                line
                for line in medium.config.splitlines()
                if line.endswith(f" match destination-address {destination}")
                and f" from-zone {key['from_zone']} to-zone {key['to_zone']} " in line
                and line.split(" policy ", 1)[1].split(" ", 1)[0] not in inactive
            ]
            assert not others, others
        assert rule["expected"]["verdict"] == "verify"
        assert rule["expected"]["best_achievable_verdict"] == "verify"
        assert any(e["supports"] == "not_live" for e in misleading(rule, "config.set"))


def test_misleading_comment_names_another_application(medium: Scenario) -> None:
    rules = medium.rules("TRAP-MISLEADING-COMMENT")
    comments = medium.comments()
    codes = {code: app for app, code in APP_CODES.items()}
    for rule in rules:
        comment = comments[rule["created"]["commit_index"]]
        named = {codes[word] for word in re.findall(r"[A-Z]+", comment) if word in codes}
        # Naive reading: the comment gives the intent; it names another app.
        assert named and rule["intent"]["app_id"] not in named, (comment, rule["intent"])
        assert misleading(rule, "commits.txt")


def test_batch_commit_mixes_unrelated_applications(medium: Scenario) -> None:
    batches: dict[int, list[dict]] = {}
    for rule in medium.rules("TRAP-BATCH-COMMIT"):
        batches.setdefault(rule["created"]["commit_index"], []).append(rule)
    for index, rules in batches.items():
        # One commit adds all these policies (visible by diffing the rollbacks)...
        for rule in rules:
            assert medium.policy_lines(rule, medium.rollback(index))
            assert not medium.policy_lines(rule, medium.rollback(index + 1))
        # ...under one comment, but they serve unrelated applications.
        assert len({r["intent"]["app_id"] for r in rules}) >= 2
        assert all(misleading(rule, "rollbacks") for rule in rules)
        if index in medium.comments():
            assert any(misleading(rule, "commits.txt") for rule in rules)


def test_history_horizon_rules_have_no_direct_evidence(medium: Scenario) -> None:
    rules = medium.rules("TRAP-HISTORY-HORIZON")
    assert rules
    oldest = max(int(re.search(r"(\d+)", p).group(1)) for p in medium.files if "rollback-" in p)
    for rule in rules:
        # Naive reading: no commit adds it, no description: intent unknown.
        assert medium.policy_lines(rule, medium.rollback(oldest))
        assert not any(" description " in line for line in medium.policy_lines(rule))
        assert not rule["created"]["in_retained_history"]
        assert all(e["tier"] != "T1" for e in rule["evidence"])
        # Truth: the intent is known, from T2, T3 and T4 only, so capped.
        assert rule["intent"]["kind"] != "unknown_origin"
        assert rule["expected"]["max_justified_confidence"] in ("LOW", "MEDIUM")


def test_deactivated_policy_still_reads_as_a_permit_rule(medium: Scenario) -> None:
    rules = medium.rules("TRAP-DEACTIVATED")
    assert rules
    for rule in rules:
        lines = medium.policy_lines(rule)
        # Naive reading (set lines only): an active permit rule.
        assert any(line.endswith(" then permit") for line in lines)
        assert lines[-1].startswith("deactivate security policies ")
        # Truth: inactive, carries nothing, not installed so no hit count row.
        assert medium.hit_count(rule) is None
        assert rule["deactivated"] and not rule["status"]["live"]
        assert rule["expected"]["verdict"] == "removal_candidate"
        assert misleading(rule, "config.set")
