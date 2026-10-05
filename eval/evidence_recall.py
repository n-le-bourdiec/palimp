"""Evidence recall of palimp against simulator ground truth, on dev seeds only.

Runs both tools as black boxes:
    palimp-sim generate --level LEVEL --seed N --out TMP
    palimp explain --all --json --no-llm -a TMP/scenario-*/artifacts
then compares, rule by rule, the evidence palimp found with the evidence the
ground truth says a perfect analyzer could find (ground_truth.json, see
simulator/src/palimp_sim/schema/ground_truth.schema.json).

An expected item counts as found when palimp reports an item for the same rule
with the same tier and the same artifact (one-to-one). Locators are free text
in both tools, so they are not compared. T2 items palimp marks "blind"
(decision 0019) state a gap, not evidence: they never match.

Recall is broken down:
- per tier and artifact;
- per trap, counted per rule (every expected item of every tagged rule) and per
  trap instance (rules tagged with the same trap and created by the same
  event form one instance; each instance weighs the same);
- per format variant, read from manifest.json (`format_draw`). Only this
  harness reads the manifest: palimp detects formats on its own.

T2 direction: a palimp "present" item should meet a ground truth item that
supports "live", and "absent" one that supports "not_live".
It also counts T2 items palimp marks "absent" on rules the ground truth says
are live: "no traffic" on a live rule is the path to the most severe error.

Dev seeds only. This script never reads a held-out salt (decision 0007).

Usage:
    uv run python eval/evidence_recall.py --level medium --seeds 0-9
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

TIERS = ("T1", "T2", "T3", "T4")
# Ground truth `supports` of a T2 item, and the palimp signal that matches it.
DIRECTION = {"live": "present", "not_live": "absent"}


def seed_range(text: str) -> list[int]:
    seeds: list[int] = []
    for part in text.split(","):
        low, _, high = part.partition("-")
        seeds.extend(range(int(low), int(high or low) + 1))
    return seeds


def tool(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        sys.exit(f"{name} not found on PATH; run with `uv run`")
    return path


def run_seed(
    level: str, seed: int, workdir: Path, holdout: bool = False
) -> tuple[dict, list[dict], dict]:
    """Generate one scenario and run palimp on it.

    With `holdout`, `seed` is a held-out index: the simulator reads the salt
    from HOLDOUT_SALT (decision 0021), and the scenario never carries the seed.
    """
    which, prefix = ("--holdout", "holdout-") if holdout else ("--seed", "")
    subprocess.run(
        [
            tool("palimp-sim"),
            "generate",
            "--level",
            level,
            which,
            str(seed),
            "--out",
            str(workdir),
            "--force",
        ],
        check=True,
        capture_output=True,
    )
    scenario = next(workdir.glob(f"scenario-{prefix}{level}-{seed:06d}"))
    result = subprocess.run(
        [
            tool("palimp"),
            "explain",
            "--all",
            "--json",
            "--no-llm",
            "-a",
            str(scenario / "artifacts"),
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    truth = json.loads((scenario / "ground_truth.json").read_text(encoding="utf-8"))
    manifest = json.loads((scenario / "manifest.json").read_text(encoding="utf-8"))
    return truth, json.loads(result.stdout), manifest


def key_of(item: dict) -> tuple[str, str, str]:
    return (item["from_zone"], item["to_zone"], item["name"])


def match_rule(rule: dict, found: list[dict]) -> tuple[Counter, Counter, Counter]:
    """Expected, found (matched) and extra item counts by (tier, artifact)."""
    usable = [e for e in found if e["tier"] in TIERS and e.get("signal") != "blind"]
    pool = Counter((e["tier"], e["artifact"]) for e in usable)
    expected: Counter = Counter()
    matched: Counter = Counter()
    for item in rule["evidence"]:
        slot = (item["tier"], item["artifact"])
        expected[slot] += 1
        if pool[slot] > 0:
            pool[slot] -= 1
            matched[slot] += 1
    return expected, matched, +pool


class Totals:
    """Expected and found counts per scope, tier and artifact."""

    def __init__(self) -> None:
        self.expected: dict[str, Counter] = defaultdict(Counter)
        self.found: dict[str, Counter] = defaultdict(Counter)
        self.extra: Counter = Counter()
        self.counts: Counter = Counter()
        # trap -> instance -> [expected, found]
        self.instances: dict[str, dict[tuple, list[int]]] = defaultdict(
            lambda: defaultdict(lambda: [0, 0])
        )

    def add(self, scope: str, expected: Counter, matched: Counter) -> None:
        self.expected[scope].update(expected)
        self.found[scope].update(matched)


def compare(truth: dict, findings: list[dict], manifest: dict, totals: Totals) -> None:
    found_by_rule = {key_of(f["key"]): f["evidence"] for f in findings}
    formats = [f"{k}={v}" for k, v in sorted(manifest.get("format_draw", {}).items())]
    scenario = truth["scenario_id"]
    for rule in truth["rules"]:
        found = found_by_rule.get(key_of(rule["key"]), [])
        expected, matched, extra = match_rule(rule, found)
        totals.counts["rules"] += 1
        totals.extra.update(extra)
        for scope in ["all", *(f"format {f}" for f in formats)]:
            totals.add(scope, expected, matched)
        for trap in rule["traps"]:
            totals.add(f"trap {trap}", expected, matched)
            totals.counts[f"rules {trap}"] += 1
            instance = (scenario, rule["created"]["event_id"])
            totals.instances[trap][instance][0] += sum(expected.values())
            totals.instances[trap][instance][1] += sum(matched.values())
        signals = {e["artifact"]: e.get("signal") for e in found if e["tier"] == "T2"}
        for item in rule["evidence"]:
            if item["tier"] != "T2" or item["supports"] not in DIRECTION:
                continue
            agree = signals.get(item["artifact"]) == DIRECTION[item["supports"]]
            totals.counts[f"T2 direction {'agrees' if agree else 'differs'}"] += 1
            if not agree:
                totals.counts[
                    f"T2 direction differs: {item['artifact']} expected {item['supports']}, "
                    f"palimp {signals.get(item['artifact'])}"
                ] += 1
        for item in found:
            if item["tier"] != "T2":
                continue
            totals.counts[f"T2 {item['signal']}"] += 1
            if item["signal"] == "absent" and rule["status"]["live"]:
                totals.counts[f"absent on live rule: {item['artifact']}"] += 1
                for trap in rule["traps"]:
                    totals.counts[f"absent on live rule: {item['artifact']} ({trap})"] += 1
    missing = {key_of(r["key"]) for r in truth["rules"]} - set(found_by_rule)
    totals.counts["rules missing in palimp"] += len(missing)


def ratio(found: int, expected: int) -> str:
    return f"{found / expected:.1%} ({found}/{expected})" if expected else "n/a"


def tier_line(totals: Totals, scope: str) -> str:
    cells = []
    for tier in TIERS:
        expected = sum(v for (t, _), v in totals.expected[scope].items() if t == tier)
        found = sum(v for (t, _), v in totals.found[scope].items() if t == tier)
        cells.append(f"{tier} {ratio(found, expected)}")
    return "; ".join(cells)


def report(totals: Totals, level: str, seeds: str) -> dict:
    print(f"level {level}, dev seeds {seeds}, {totals.counts['rules']} rules")
    print("\nPer tier and artifact (all rules)")
    for tier in TIERS:
        slots = sorted(s for s in totals.expected["all"] if s[0] == tier)
        expected = sum(totals.expected["all"][s] for s in slots)
        found = sum(totals.found["all"][s] for s in slots)
        print(f"  {tier}: {ratio(found, expected)}")
        for slot in slots:
            print(
                f"    {slot[1]}: {ratio(totals.found['all'][slot], totals.expected['all'][slot])}"
            )
        extras = {a: v for (t, a), v in totals.extra.items() if t == tier}
        if extras:
            print(f"    found but not expected: {extras}")

    print("\nPer trap, counted per rule")
    traps = sorted(s.removeprefix("trap ") for s in totals.expected if s.startswith("trap "))
    for trap in traps:
        print(f"  {trap} ({totals.counts[f'rules {trap}']} rules)")
        print(f"    {tier_line(totals, f'trap {trap}')}")

    print("\nPer trap, counted per instance (same trap, same creating event)")
    instance_scores = {}
    for trap in traps:
        instances = totals.instances[trap].values()
        scored = [found / expected for expected, found in instances if expected]
        complete = sum(1 for expected, found in instances if expected and found == expected)
        mean = sum(scored) / len(scored) if scored else 0.0
        instance_scores[trap] = {"instances": len(instances), "mean_recall": mean}
        print(
            f"  {trap}: {len(instances)} instances, mean recall {mean:.1%}, "
            f"fully recalled {complete}/{len(scored)}"
        )

    print("\nPer format variant (manifest format_draw, read by this harness only)")
    for scope in sorted(s for s in totals.expected if s.startswith("format ")):
        print(f"  {scope.removeprefix('format ')}: {tier_line(totals, scope)}")

    print("\nT2 signals reported by palimp")
    for signal in ("present", "absent", "blind"):
        print(f"  {signal}: {totals.counts[f'T2 {signal}']}")
    agree, differ = totals.counts["T2 direction agrees"], totals.counts["T2 direction differs"]
    print(
        f"  direction agrees with ground truth (live/present, not_live/absent): "
        f"{ratio(agree, agree + differ)}"
    )
    for key, value in sorted(totals.counts.items()):
        if key.startswith("T2 direction differs:"):
            print(f"    {key.removeprefix('T2 direction differs: ')}: {value}")
    dangerous = {k: v for k, v in totals.counts.items() if k.startswith("absent on live rule")}
    print(f"  'absent' on a rule the ground truth says is live: {dangerous or 0}")
    missing = totals.counts["rules missing in palimp"]
    print(f"\nground truth rules missing from palimp output: {missing}")
    return {
        "counts": dict(sorted(totals.counts.items())),
        "expected": {
            s: {f"{t}:{a}": v for (t, a), v in c.items()} for s, c in totals.expected.items()
        },
        "found": {s: {f"{t}:{a}": v for (t, a), v in c.items()} for s, c in totals.found.items()},
        "instances": instance_scores,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--level", default="easy")
    parser.add_argument("--seeds", default="0-19", help="dev seeds, for example 0-19 or 1,4,7")
    parser.add_argument("--json", type=Path, help="also write the totals to this file")
    args = parser.parse_args()

    totals = Totals()
    with tempfile.TemporaryDirectory() as tmp:
        for seed in seed_range(args.seeds):
            truth, findings, manifest = run_seed(args.level, seed, Path(tmp))
            if manifest.get("split") not in (None, "dev"):
                sys.exit(f"seed {seed} is not a dev scenario")
            compare(truth, findings, manifest, totals)

    summary = report(totals, args.level, args.seeds)
    if args.json:
        args.json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
