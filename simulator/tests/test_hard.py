"""Hard level (decision 0035): coverage, format variants and the four new traps.

Each trap test reads the visible artifacts the way a naive analyzer would, and
checks that this reading contradicts the ground truth as spec section 7.3
says. The artifacts are read with plain text rules that handle both
configuration formats (set and hierarchical), never with the analyzer.
"""

import csv
import hashlib
import io
import json
import re
from functools import cache
from pathlib import Path

import pytest

from palimp_sim.generate import generate
from palimp_sim.voice import code

# Same rule as test_leakage.py.
STOP_WORDS = {"a", "an", "the", "to", "of", "for", "from", "and", "with", "its", "on", "in", "by"}
MAX_SHARED = 0.6


def shared_ratio(visible: str, summary: str, app_id: str) -> float:
    def tokens(text: str) -> set[str]:
        return set(re.findall(r"[a-z0-9]+", text.lower())) - STOP_WORDS

    words = tokens(visible) - {code(app_id).lower()}
    return len(words & tokens(summary)) / len(words) if words else 0.0


FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "junos_docs"
NEW_TRAPS = ["TRAP-RENAME-CHAIN", "TRAP-IP-REUSE", "TRAP-SCANNER-HITS", "TRAP-STALE-NAME"]
V1_TRAPS = [
    "TRAP-LIVE-NOLOG",
    "TRAP-RARE-JOB",
    "TRAP-EMERGENCY-LOADBEARING",
    "TRAP-MISLEADING-COMMENT",
    "TRAP-BATCH-COMMIT",
    "TRAP-HISTORY-HORIZON",
    "TRAP-DEACTIVATED",
]
TIMELINE_TRAPS = ["TRAP-HISTORY-HORIZON", "TRAP-DEACTIVATED"]
DRAWN_TRAPS = [t for t in V1_TRAPS + NEW_TRAPS if t not in TIMELINE_TRAPS]
# Seeds 0 to 15 measured in session 22: together these hold every trap, and
# each new trap is absent from at least one of them; both formats, with and
# without global policies.
SEEDS = [0, 2, 3, 4, 11]
# SHA-256 of manifest.json (which holds the hash of every other file), session
# 22. Easy and Medium hashes did not change when Hard was added (decision 0035).
GOLDEN_HARD = {0: "22d16e525fe814feef855f3e2ee5e4ca5afd03701c7e47e82db72e2ec4847583"}
SCOPE = r"(from-zone (\S+) to-zone (\S+)|global) policy (\S+)"
SET_POLICY = re.compile(rf"^set security policies {SCOPE} (.*)$")
DEACTIVATE = re.compile(rf"^deactivate security policies {SCOPE}$")
COMMIT = re.compile(r"^(\d+)\s+(\d{4}-\d\d-\d\d) ")


@cache
def files_of(seed: int, overrides: tuple = ()) -> dict[str, str]:
    files = generate("hard", seed, dict(overrides))
    return {path: data.decode("utf-8") for path, data in files.items()}


def parse_config(text: str) -> dict:
    """Policies and address objects of either format.

    Returns {"policies": {key: {"stmts", "inactive", "annotation"}}, "addresses":
    {name: prefix}}; a key is (from zone, to zone, name), "global" twice for a
    global policy; statements are relative to the policy ("match
    source-address x", "then permit"), one value each.
    """
    policies: dict = {}
    addresses: dict = {}
    sets: dict = {}
    if text.startswith("set ") or "\nset " in text[:200]:
        for line in text.splitlines():
            match = SET_POLICY.match(line)
            if match:
                scope, fz, tz, name, rest = match.groups()
                key = (fz or "global", tz or "global", name)
                empty = {"stmts": [], "inactive": False, "annotation": None}
                entry = policies.setdefault(key, empty)
                entry["stmts"].append(rest)
            match = DEACTIVATE.match(line)
            if match:
                _, fz, tz, name = match.groups()
                policies[(fz or "global", tz or "global", name)]["inactive"] = True
            if line.startswith("set security address-book global address "):
                name, prefix = line.split()[5:7]
                addresses[name] = prefix
            if line.startswith("set security address-book global address-set "):
                name, member = line.split()[5], line.split()[7]
                sets.setdefault(name, []).append(member)
        return {"policies": policies, "addresses": addresses, "sets": sets}
    stack: list[str] = []
    note = None
    key = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("##"):
            continue
        if line.startswith("/*"):
            note = line[3:-3]
            continue
        if line.endswith("{"):
            head = line[:-1].strip()
            inactive = head.startswith("inactive: ")
            stack.append(head.removeprefix("inactive: "))
            if stack[:2] == ["security", "policies"] and len(stack) == 4:
                scope = stack[2].split()
                zones = ("global", "global") if scope == ["global"] else (scope[1], scope[3])
                key = (*zones, stack[3].split()[1])
                policies[key] = {"stmts": [], "inactive": inactive, "annotation": note}
            note = None
            continue
        if line == "}":
            stack.pop()
            continue
        statement = line.rstrip(";")
        if stack[:2] == ["security", "policies"] and len(stack) >= 4:
            words = statement.split(" ", 1)
            values = [statement]
            if len(words) == 2 and words[1].startswith("[ "):
                values = [f"{words[0]} {v}" for v in words[1][2:-2].split()]
            for value in values:
                policies[key]["stmts"].append(" ".join(stack[4:] + [value]))
        if stack == ["security", "address-book", "global"] and statement.startswith("address "):
            _, name, prefix = statement.split()
            addresses[name] = prefix
        if stack[:3] == ["security", "address-book", "global"] and len(stack) == 4:
            sets.setdefault(stack[3].split()[1], []).append(statement.split()[1])
    return {"policies": policies, "addresses": addresses, "sets": sets}


class Scenario:
    def __init__(self, seed: int, overrides: tuple = ()) -> None:
        self.files = files_of(seed, overrides)
        self.truth = json.loads(self.files["ground_truth.json"])
        self.manifest = json.loads(self.files["manifest.json"])
        self.config = parse_config(self.files["artifacts/config.set"])

    def rules(self, trap: str) -> list[dict]:
        return [r for r in self.truth["rules"] if trap in r["traps"]]

    def rollback(self, index: int) -> dict:
        if index == 0:
            return self.config
        return parse_config(self.files[f"artifacts/rollbacks/rollback-{index:02d}.set"])

    def oldest(self) -> int:
        return max(int(p[-6:-4]) for p in self.files if "rollback-" in p)

    def hit_count(self, key: tuple) -> int | None:
        for line in self.files["artifacts/hitcount.txt"].splitlines():
            fields = line.split()
            if fields[:1] and fields[0].isdigit() and tuple(fields[1:4]) == key:
                return int(fields[4])
        return None

    def log_lines(self, name: str) -> list[str]:
        needle = f'policy-name="{name}"'
        return [x for x in self.files["artifacts/logs/rt_flow.log"].splitlines() if needle in x]

    def app(self, app_id: str) -> dict:
        return next(a for a in self.truth["apps"] if a["app_id"] == app_id)

    def flow(self, flow_id: str) -> dict:
        return next(f for f in self.truth["flows"] if f["flow_id"] == flow_id)


def key_of(rule: dict) -> tuple:
    return tuple(rule["key"].values())


def misleading(rule: dict, artifact: str | None = None) -> list[dict]:
    return [
        e
        for e in rule["evidence"]
        if e["misleading"] and (artifact is None or e["artifact"] == artifact)
    ]


@pytest.fixture(scope="module", params=SEEDS)
def hard(request) -> Scenario:
    return Scenario(request.param)


# ------------------------------------------------------------------ determinism


def test_hard_same_seed_same_bytes() -> None:
    assert generate("hard", 3) == generate("hard", 3)


def test_golden_manifest_hard() -> None:
    manifest = files_of(0)["manifest.json"].encode("utf-8")
    assert hashlib.sha256(manifest).hexdigest() == GOLDEN_HARD[0]


def test_no_carriage_returns(hard: Scenario) -> None:
    assert all("\r" not in text for text in hard.files.values())


# ------------------------------------------------------------------ coverage


def trap_counts(seed: int) -> dict[str, int]:
    truth = json.loads(files_of(seed)["ground_truth.json"])
    return {t: sum(1 for r in truth["rules"] if t in r["traps"]) for t in V1_TRAPS + NEW_TRAPS}


def test_timeline_traps_in_every_hard_scenario(hard: Scenario) -> None:
    for trap in TIMELINE_TRAPS:
        assert hard.rules(trap), trap


def test_fixture_seeds_cover_every_trap_and_its_absence() -> None:
    counts = [trap_counts(seed) for seed in SEEDS]
    for trap in V1_TRAPS + NEW_TRAPS:
        assert any(c[trap] for c in counts), trap
    for trap in NEW_TRAPS:
        assert any(not c[trap] for c in counts), trap


@pytest.mark.full
def test_hard_trap_distribution_over_seeds_0_to_49() -> None:
    """Every drawn trap is absent from some scenarios, with a count that varies."""
    counts = [trap_counts(seed) for seed in range(50)]
    for trap in DRAWN_TRAPS:
        values = [c[trap] for c in counts]
        share = sum(1 for v in values if v) / len(values)
        assert 0.5 <= share <= 0.95, (trap, share)
        assert len({v for v in values if v}) >= 2, (trap, sorted(set(values)))
    for trap in TIMELINE_TRAPS:
        assert all(c[trap] for c in counts), trap


# ------------------------------------------------------------------ formats


def test_format_variants_are_drawn_recorded_and_applied(hard: Scenario) -> None:
    draw = hard.manifest["format_draw"]
    assert {"config_format", "global_policies"} <= set(draw)
    text = hard.files["artifacts/config.set"]
    hierarchical = draw["config_format"] == "hierarchical"
    assert text.startswith("## Last commit: ") == hierarchical
    for path, content in hard.files.items():
        if path.endswith(".set"):
            assert content.startswith("set version ") != hierarchical, path
    keys = set(hard.config["policies"])
    assert any(k[0] == "global" for k in keys) == draw["global_policies"]


HIER_FIXTURES = (
    "hier_show_security_policies.txt",
    "hier_global_policies.txt",
    "hier_global_policy_zones.txt",
    "hier_policy_log_prompt_nospace.txt",
    "hier_inactive.txt",
    "hier_annotations.txt",
)
HIER_SHAPES = (
    re.compile(r"^(inactive: )?[\w\-./: \[\]]+ \{$"),  # container
    re.compile(r"^\}$"),
    re.compile(r"^/\* .+ \*/$"),  # annotation
    re.compile(r'^[\w\-./]+( [\w\-./:"\'\[\], ]+)?;$'),  # statement
)

# A quoted string (description, login message): no hierarchical sample shows
# one (HIER-1d, unverified), so this shape is not checked against a fixture.
QUOTED = re.compile(r'^(description|message) "[^"]*";$')


def body(name: str) -> list[str]:
    """Fixture lines after `# ---`, without prompts or elisions (as test_formats.py)."""
    lines = (FIXTURES / name).read_text(encoding="utf-8").splitlines()
    lines = lines[lines.index("# ---") + 1 :]
    return [
        line.rstrip()
        for line in lines
        if line.strip()
        and not re.match(r"^\S+@\S+[>#]", line.strip())
        and not line.strip().startswith("[edit")
        and line.strip() != "..."
    ]


def test_hierarchical_shapes_come_from_the_fixtures() -> None:
    """Every line shape the simulator writes is seen in a documentation sample."""
    for name in HIER_FIXTURES:
        lines = [x.strip() for x in body(name)]
        # hier_annotations.txt also shows a comment the device drops (same line).
        lines = [x for x in lines if "dropped" not in x and "#" not in x]
        assert lines, name
        bad = [x for x in lines if not any(shape.match(x) for shape in HIER_SHAPES)]
        assert not bad, (name, bad)
    used = set()
    for line in files_of(0)["artifacts/config.set"].splitlines()[1:]:
        if QUOTED.match(line.strip()):
            continue
        found = [i for i, shape in enumerate(HIER_SHAPES) if shape.match(line.strip())]
        assert found, line
        used.add(found[0])
    assert used == set(range(len(HIER_SHAPES)))


def test_hierarchical_shape_matches_the_fixtures() -> None:
    """Braces balance, statements end in `;`, `inactive:` and `/* */` as in hier_*.txt."""
    scenario = Scenario(0)
    assert scenario.manifest["format_draw"]["config_format"] == "hierarchical"
    text = scenario.files["artifacts/config.set"]
    depth = 0
    for line in text.splitlines()[1:]:
        stripped = line.strip()
        assert line == "    " * (depth - (stripped == "}")) + stripped, line
        if stripped.endswith("{"):
            depth += 1
            assert re.match(r"^(inactive: )?[\w\-./: \[\]]+ \{$", stripped), line
        elif stripped == "}":
            depth -= 1
        elif stripped.startswith("/*"):
            assert stripped.endswith(" */"), line
        else:
            assert stripped.endswith(";"), line
    assert depth == 0
    assert re.search(r"^ +inactive: policy \S+ \{$", text, re.M)
    assert re.search(r"^ +/\* .+ \*/\n +policy \S+ \{$", text, re.M)


def test_global_policies_follow_the_fixture_layout() -> None:
    scenario = Scenario(3, (("config_format", "set"),))
    lines = [
        x for x in scenario.files["artifacts/config.set"].splitlines() if " policies global " in x
    ]
    assert lines and all(SET_POLICY.match(x) for x in lines)
    assert any(" match from-zone " in x for x in lines)
    globals_ = [r for r in scenario.truth["rules"] if r["key"]["from_zone"] == "global"]
    for rule in globals_:
        # Hit counts list them under global/global (GLOBAL-1, an assumption);
        # logs name the real zones.
        assert scenario.hit_count(key_of(rule)) is not None
        for line in scenario.log_lines(rule["key"]["name"]):
            assert 'source-zone-name="global"' not in line


def test_annotations_only_in_hierarchical_output() -> None:
    hier = Scenario(0)
    flat = Scenario(0, (("config_format", "set"),))
    notes = [p["annotation"] for p in hier.config["policies"].values() if p["annotation"]]
    assert notes
    assert "/*" not in flat.files["artifacts/config.set"]
    rules = {key_of(r): r for r in hier.truth["rules"]}
    for key, policy in hier.config["policies"].items():
        located = any(e["locator"].endswith(" annotation") for e in rules[key]["evidence"])
        assert located == bool(policy["annotation"]), key
    for rule in flat.truth["rules"]:
        assert not any(e["locator"].endswith(" annotation") for e in rule["evidence"])


# ------------------------------------------------------------------ consistency


def test_every_policy_has_one_ground_truth_entry(hard: Scenario) -> None:
    keys = [key_of(r) for r in hard.truth["rules"]]
    assert len(keys) == len(set(keys))
    assert sorted(keys) == sorted(hard.config["policies"])
    names = [k[2] for k in keys]
    assert len(names) == len(set(names))


def test_hitcount_lists_every_active_policy(hard: Scenario) -> None:
    rows = [
        tuple(line.split()[1:4])
        for line in hard.files["artifacts/hitcount.txt"].splitlines()
        if line[:2].strip().isdigit()
    ]
    active = [k for k, p in hard.config["policies"].items() if not p["inactive"]]
    assert sorted(rows) == sorted(active)


def test_log_lines_name_policies_of_some_configuration(hard: Scenario) -> None:
    names = set(re.findall(r'policy-name="([^"]+)"', hard.files["artifacts/logs/rt_flow.log"]))
    known = set()
    for path, text in hard.files.items():
        if path.endswith(".set"):
            known |= {k[2] for k in parse_config(text)["policies"]}
    assert names <= known


def test_no_ground_truth_text_in_visible_texts(hard: Scenario) -> None:
    """Descriptions, annotations, comments and tickets never echo intent.summary."""
    comments: dict[int, str] = {}
    current = None
    for line in hard.files["artifacts/commits.txt"].splitlines():
        match = COMMIT.match(line)
        if match:
            current = int(match.group(1))
        elif current is not None:
            comments[current] = line.strip()
    tickets = {
        row["ticket_id"]: row["summary"]
        for row in csv.DictReader(io.StringIO(hard.files["artifacts/tickets.csv"]))
    }
    events = {e["event_id"]: e for e in hard.truth["events"]}
    for rule in hard.truth["rules"]:
        policy = hard.config["policies"][key_of(rule)]
        texts = [s.split(" ", 1)[1] for s in policy["stmts"] if s.startswith("description ")]
        texts += [policy["annotation"] or "", comments.get(rule["created"]["commit_index"], "")]
        texts.append(tickets.get(events[rule["created"]["event_id"]]["ticket_id"], ""))
        summary = rule["intent"]["summary"]
        for text in filter(None, texts):
            assert summary.lower() not in text.lower(), (rule["key"], text)
            assert shared_ratio(text, summary, rule["intent"]["app_id"]) <= MAX_SHARED, (
                rule["key"],
                text,
                summary,
            )


# ------------------------------------------------------------------ new traps


def test_rename_chain_looks_like_two_rules_but_is_one(hard: Scenario) -> None:
    rules = hard.rules("TRAP-RENAME-CHAIN")
    for rule in rules:
        key = key_of(rule)
        final = hard.config["policies"][key]["stmts"]
        renamed = [
            e
            for e in rule["evidence"]
            if e["artifact"] == "rollbacks" and " from commit " in e["locator"]
        ]
        old_logs = [
            e
            for e in rule["evidence"]
            if e["artifact"] == "logs/rt_flow.log" and e["locator"] != f'policy-name="{key[2]}"'
        ]
        assert renamed or old_logs
        for evidence in renamed:
            words = evidence["locator"].split()
            old_name, before, kind = words[1], int(words[4].rstrip(",")), words[0]
            after = int(words[-1])
            old = hard.rollback(before)
            new = hard.rollback(after)
            if kind == "policy":
                # Naive reading of the rollback diff: one rule deleted, another added.
                old_key = (key[0], key[1], old_name)
                assert old_key in old["policies"] and old_key not in new["policies"]
                assert key in new["policies"] and key not in old["policies"]
                # Truth: the same rule (same match and action), created before.
                assert old["policies"][old_key]["stmts"] == new["policies"][key]["stmts"]
                assert old_name in rule["name_history"][:-1]
                assert rule["name_history"][-1] == key[2]
                created = rule["created"]["commit_index"]
                assert not rule["created"]["in_retained_history"] or created > after
            else:
                # An address object renamed: same address, new name in the rule.
                new_name = words[5].rstrip(",")
                assert old["addresses"][old_name] == new["addresses"][new_name]
                assert new_name not in old["addresses"] and old_name not in new["addresses"]
                assert f"match destination-address {new_name}" in final or (
                    f"match source-address {new_name}" in final
                )
        for name in rule["name_history"][:-1]:
            lines = hard.log_lines(name)
            if lines:
                # Old log lines still carry the old name.
                assert all(f'policy-name="{name}"' in x for x in lines)


def test_ip_reuse_rule_looks_live_but_its_intent_is_dead(hard: Scenario) -> None:
    for rule in hard.rules("TRAP-IP-REUSE"):
        key = key_of(rule)
        # Naive reading: hits (or log lines) on the rule, so it is live: keep.
        assert (hard.hit_count(key) or 0) > 0 or hard.log_lines(key[2])
        # Truth: the application it was made for is retired; the traffic is
        # another application's, on the address its server got back.
        assert hard.app(rule["intent"]["app_id"])["retired"]
        assert not rule["status"]["live"] and rule["status"]["still_needed"]
        assert rule["status"]["hits_reason"] == "ip_reuse"
        carried = {hard.flow(f)["app_id"] for f in rule["status"]["carried_flows"]}
        assert carried and rule["intent"]["app_id"] not in carried
        assert rule["expected"]["verdict"] == "verify"
        assert rule["expected"]["best_achievable_verdict"] == "verify"
        assert misleading(rule, "hitcount.txt")
        addresses, sets = hard.config["addresses"], hard.config["sets"]
        stmts = hard.config["policies"][key]["stmts"]
        destinations = [s.split()[-1] for s in stmts if "destination-address" in s]
        destinations = [m for d in destinations for m in sets.get(d, [d])]
        twins = [e for e in rule["evidence"] if e["locator"].startswith("same address as ")]
        for evidence in twins:
            for twin in evidence["locator"].removeprefix("same address as ").split(", "):
                assert addresses[twin] in {addresses.get(d) for d in destinations}


def test_scanner_hits_rule_looks_live_but_is_dead(hard: Scenario) -> None:
    for rule in hard.rules("TRAP-SCANNER-HITS"):
        key = key_of(rule)
        # Naive reading: the rule has hits, so it is in use.
        assert (hard.hit_count(key) or 0) > 0
        # Truth: no flow it was made for remains; the hits are a scanner sweep
        # or a monitoring probe of a switched-off server.
        assert not rule["status"]["live"] and not rule["status"]["still_needed"]
        assert rule["status"]["hits_reason"] in ("scanner", "monitoring")
        assert rule["expected"]["verdict"] == "removal_candidate"
        # 45 days of counters: too short to call a rule unused (spec 7.4).
        assert rule["expected"]["best_achievable_verdict"] == "verify"
        assert misleading(rule, "hitcount.txt")
        sources = {
            re.search(r'source-address="([^"]+)"', x).group(1) for x in hard.log_lines(key[2])
        }
        monitors = {
            hard.config["addresses"][n]
            for n in hard.config["addresses"]
            if n.removeprefix("host_").startswith("mon-")
        }
        allowed = {"10.10.1.250"} | {m.split("/")[0] for m in monitors}
        assert sources <= allowed, sources


def test_stale_name_points_at_a_retired_application(hard: Scenario) -> None:
    for rule in hard.rules("TRAP-STALE-NAME"):
        key = key_of(rule)
        policy = hard.config["policies"][key]
        visible = [key[2], policy["annotation"] or ""] + policy["stmts"]
        old_ids = {a["app_id"] for a in hard.truth["apps"] if a["retired"]}
        named = {
            app_id
            for app_id in old_ids
            if any(app_id in v.lower() or code(app_id).lower() in v.lower() for v in visible)
        }
        # Naive reading: the rule or its objects name an application that the
        # tickets and the history show as retired: its intent is that one.
        assert named, visible
        # Truth: it serves the application that replaced it, and is live.
        assert rule["intent"]["app_id"] not in named
        assert not hard.app(rule["intent"]["app_id"])["retired"]
        assert rule["status"]["live"]
        assert rule["expected"]["verdict"] == "keep"
        assert rule["expected"]["best_achievable_verdict"] != "removal_candidate"
        assert misleading(rule)
