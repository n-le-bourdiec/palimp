"""List the rules tagged with a trap in dev scenarios, from the ground truth.

Harness side only: palimp never sees ground truth or manifest. Use it to pick
a rule, then run `palimp explain` on it like a user would.

Usage:
    uv run python eval/trap_rules.py --level medium --seeds 0-9 --trap TRAP-RARE-JOB --out DIR
"""

import argparse
import json
import subprocess
from pathlib import Path

from evidence_recall import seed_range, tool


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--level", default="medium")
    parser.add_argument("--seeds", default="0-9")
    parser.add_argument("--trap", required=True)
    parser.add_argument("--out", type=Path, required=True, help="where scenarios are generated")
    args = parser.parse_args()
    for seed in seed_range(args.seeds):
        scenario = args.out / f"scenario-{args.level}-{seed:06d}"
        if not (scenario / "ground_truth.json").is_file():
            subprocess.run(
                [tool("palimp-sim"), "generate", "--level", args.level, "--seed", str(seed)]
                + ["--out", str(args.out), "--force"],
                check=True,
                capture_output=True,
            )
        truth = json.loads((scenario / "ground_truth.json").read_text(encoding="utf-8"))
        if truth.get("level") != args.level:
            continue
        for rule in truth["rules"]:
            if args.trap in rule["traps"]:
                key = rule["key"]
                status = rule["status"]
                print(
                    f"{scenario / 'artifacts'}  {key['from_zone']}/{key['to_zone']}/{key['name']}"
                    f"  intent={rule['intent']['kind']} live={status['live']}"
                    f" hits_in_window={status['hits_in_window']} log_lines={status['log_lines']}"
                    f" verdict={rule['expected']['verdict']}"
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
