"""Evidence recall of palimp against simulator ground truth, on dev seeds only.

Runs both tools as black boxes:
    palimp-sim generate --level LEVEL --seed N --out TMP
    palimp explain --all --json --no-llm -a TMP/scenario-*/artifacts
then compares, rule by rule, the evidence palimp found with the evidence the
ground truth says a perfect analyzer could find (ground_truth.json, see
simulator/src/palimp_sim/schema/ground_truth.schema.json).

An expected item counts as found when palimp reports an item for the same rule
with the same tier and the same artifact (one-to-one). Locators are free text
in both tools, so they are not compared.

Dev seeds only. This script never reads a held-out salt (decision 0007).

Usage:
    uv run python eval/evidence_recall.py --level easy --seeds 0-19
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

TIERS = ("T1", "T3")


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


def run_seed(level: str, seed: int, workdir: Path) -> tuple[dict, list[dict]]:
    subprocess.run(
        [
            tool("palimp-sim"),
            "generate",
            "--level",
            level,
            "--seed",
            str(seed),
            "--out",
            str(workdir),
            "--force",
        ],
        check=True,
        capture_output=True,
    )
    scenario = next(workdir.glob(f"scenario-{level}-{seed:06d}"))
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
    return truth, json.loads(result.stdout)


def key_of(item: dict) -> tuple[str, str, str]:
    return (item["from_zone"], item["to_zone"], item["name"])


def compare(truth: dict, findings: list[dict], totals: Counter) -> None:
    found_by_rule = {key_of(f["key"]): f["evidence"] for f in findings}
    for rule in truth["rules"]:
        found = [e for e in found_by_rule.get(key_of(rule["key"]), []) if e["tier"] in TIERS]
        pool = Counter((e["tier"], e["artifact"]) for e in found)
        expected = [e for e in rule["evidence"] if e["tier"] in TIERS]
        totals["rules"] += 1
        if any(e["tier"] == "T1" for e in found):
            totals["rules_with_t1_found"] += 1
        if any(e["tier"] == "T1" for e in expected):
            totals["rules_with_t1_expected"] += 1
        for item in expected:
            slot = (item["tier"], item["artifact"])
            totals[f"{item['tier']}_expected"] += 1
            totals[f"{item['tier']}_expected:{item['artifact']}"] += 1
            if pool[slot] > 0:
                pool[slot] -= 1
                totals[f"{item['tier']}_found"] += 1
                totals[f"{item['tier']}_found:{item['artifact']}"] += 1
        for (tier, artifact), extra in pool.items():
            totals[f"{tier}_extra"] += extra
            if extra:
                totals[f"{tier}_extra:{artifact}"] += extra
    totals["rules_missing_in_palimp"] += len(
        {key_of(r["key"]) for r in truth["rules"]} - set(found_by_rule)
    )


def ratio(found: int, expected: int) -> str:
    return f"{found / expected:.1%} ({found}/{expected})" if expected else "n/a"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--level", default="easy")
    parser.add_argument("--seeds", default="0-19", help="dev seeds, for example 0-19 or 1,4,7")
    parser.add_argument("--json", type=Path, help="also write the totals to this file")
    args = parser.parse_args()

    totals: Counter = Counter()
    with tempfile.TemporaryDirectory() as tmp:
        for seed in seed_range(args.seeds):
            truth, findings = run_seed(args.level, seed, Path(tmp))
            compare(truth, findings, totals)

    print(f"level {args.level}, dev seeds {args.seeds}, {totals['rules']} rules")
    for tier in TIERS:
        print(f"{tier} recall: {ratio(totals[f'{tier}_found'], totals[f'{tier}_expected'])}")
        artifacts = sorted(k.split(":", 1)[1] for k in totals if k.startswith(f"{tier}_expected:"))
        for artifact in artifacts:
            found = totals[f"{tier}_found:{artifact}"]
            expected = totals[f"{tier}_expected:{artifact}"]
            print(f"  {artifact}: {ratio(found, expected)}")
        extras = {
            k.split(":", 1)[1]: v for k, v in totals.items() if k.startswith(f"{tier}_extra:")
        }
        print(f"  found but not expected: {totals[f'{tier}_extra']} {extras or ''}".rstrip())
    print(
        "rules with at least one T1 item found: "
        f"{ratio(totals['rules_with_t1_found'], totals['rules'])}"
        f" (ground truth expects T1 on {totals['rules_with_t1_expected']} rules)"
    )
    print(f"ground truth rules missing from palimp output: {totals['rules_missing_in_palimp']}")
    if args.json:
        args.json.write_text(json.dumps(dict(sorted(totals.items())), indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
