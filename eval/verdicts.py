"""Verdict and confidence evaluation of palimp against simulator ground truth.

Runs both tools as black boxes (see evidence_recall.py), then compares, rule
by rule, palimp's assessment with the ground truth `expected` block
(simulator/src/palimp_sim/schema/ground_truth.schema.json):

- verdict accuracy against `expected.verdict` and against
  `expected.best_achievable_verdict` (the fair one: what the artifacts allow);
- dangerous errors: removal_candidate on a rule whose `status.live` is true.
  Every one is listed;
- overconfidence: confidence above `expected.max_justified_confidence`;
- calibration: per confidence level, how often palimp's intent application
  is the ground truth one (`intent.app_id`), and how often the verdict is the
  best achievable one;
- the same per trap (per rule, and per instance: rules tagged with the same
  trap and created by the same event) and per format variant (manifest);
- a naive baseline next to palimp: zero hits gives removal_candidate,
  otherwise keep. It reads palimp's hit count signal (present means hits; an
  absent signal or no hit count row means zero hits).

Dev seeds by default. `--holdout N` scores held-out scenarios 0 to N-1
instead: the simulator reads the salt from HOLDOUT_SALT, which exists only in
the held-out GitHub Actions workflow (decisions 0007 and 0021). In that mode
the script prints aggregate tables only (headline, per trap, per format
variant, calibration), never a per-rule line, and hides failure details.

Usage:
    uv run python eval/verdicts.py --level medium --seeds 0-19
    uv run python eval/verdicts.py --level medium --holdout 50   (workflow only)
"""

import argparse
import json
import os
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

from evidence_recall import key_of, run_seed, seed_range

LEVELS = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}


def baseline(finding: dict) -> str:
    hits = [e for e in finding["evidence"] if e.get("kind") == "hit_count"]
    if any(e["signal"] == "present" for e in hits):
        return "keep"
    if any(e["locator"] == "hitcount.txt missing" for e in hits):
        return "keep"
    return "removal_candidate"


def app_of(value: str) -> str:
    return value.lower().removeprefix("shared-")


class Score:
    """Counters for one scope (all rules, a trap, a format variant)."""

    def __init__(self) -> None:
        self.c: Counter = Counter()

    def add(self, row: dict) -> None:
        c = self.c
        c["rules"] += 1
        for who in ("palimp", "naive"):
            verdict = row[who]
            c[f"{who} ok expected"] += verdict == row["expected"]
            c[f"{who} ok best"] += verdict == row["best"]
            c[f"{who} dangerous"] += verdict == "removal_candidate" and row["live"]
            c[f"{who} removal"] += verdict == "removal_candidate"
        c["overconfident"] += LEVELS[row["confidence"]] > LEVELS[row["max_conf"]]
        c["intent ok"] += row["intent_ok"]
        c["owner named"] += row["owner_ok"]
        c["owner certain right"] += row["owner_certain"] == "right"
        c["owner certain wrong"] += row["owner_certain"] == "wrong"
        c["owner candidate right"] += row["owner_candidate_ok"]
        c["conflict"] += row["conflict"]
        c[f"verdict {row['palimp']}"] += 1


def pct(part: int, whole: int) -> str:
    return f"{part / whole:.1%}" if whole else "n/a"


def owner_certain(assessment: dict, owner: str, names: set[str]) -> str:
    """'right' or 'wrong' when palimp states one owner as certain, '' otherwise.

    Without the `owner` field (palimp before session 14), any person named in
    `ask` counts as stated: right when it is the owner, wrong otherwise.
    """
    if "owner" in assessment:
        stated = assessment["owner"]
        if not stated:
            return ""
        return "right" if stated == owner else "wrong"
    ask = assessment["ask"] or ""
    if owner in ask:
        return "right"
    return "wrong" if any(n in ask for n in names) else ""


def evaluate(truth: dict, findings: list[dict], manifest: dict) -> list[dict]:
    by_key = {key_of(f["key"]): f for f in findings}
    people = {p["person_id"]: p["name"] for p in truth["people"]}
    names = set(people.values()) | {a["name"] for a in truth["admins"]}
    names |= {a["login"] for a in truth["admins"]}
    formats = [f"{k}={v}" for k, v in sorted(manifest.get("format_draw", {}).items())]
    rows = []
    for rule in truth["rules"]:
        finding = by_key.get(key_of(rule["key"]))
        if finding is None:
            sys.exit(f"{truth['scenario_id']}: rule {rule['key']} missing from palimp output")
        assessment = finding["assessment"]
        expected = rule["expected"]
        owner = people.get(expected["owner_to_ask"], expected["owner_to_ask"])
        rows.append(
            {
                "scenario": truth["scenario_id"],
                "key": "/".join(key_of(rule["key"])),
                "traps": rule["traps"],
                "instance": (truth["scenario_id"], rule["created"]["event_id"]),
                "formats": formats,
                "live": rule["status"]["live"],
                "expected": expected["verdict"],
                "best": expected["best_achievable_verdict"],
                "max_conf": expected["max_justified_confidence"],
                "palimp": assessment["verdict"],
                "rule": assessment["verdict_rule"],
                "confidence": assessment["confidence"],
                "confidence_rule": assessment["confidence_rule"],
                "intent_ok": app_of(rule["intent"]["app_id"])
                in [app_of(a) for a in assessment["intent_apps"][:1]],
                "owner_ok": bool(assessment["ask"]) and owner in assessment["ask"],
                "owner_certain": owner_certain(assessment, owner, names),
                "owner_candidate_ok": owner in assessment.get("owner_candidates", []),
                "conflict": bool(assessment["conflicts"]),
                "naive": baseline(finding),
                "evidence": finding["evidence"],
            }
        )
    return rows


def headline(scores: dict[str, Score]) -> None:
    c = scores["all"].c
    n = c["rules"]
    print(f"\nHeadline ({n} rules)")
    print("| metric | palimp | naive baseline |")
    print("|---|---|---|")
    for label, key in (
        ("verdict accuracy vs expected.verdict", "ok expected"),
        ("verdict accuracy vs best_achievable_verdict", "ok best"),
        ("removal_candidate verdicts", "removal"),
        ("dangerous errors (removal_candidate on a live rule)", "dangerous"),
    ):
        p, b = c[f"palimp {key}"], c[f"naive {key}"]
        if key == "removal" or key == "dangerous":
            print(f"| {label} | {p} | {b} |")
        else:
            print(f"| {label} | {pct(p, n)} ({p}) | {pct(b, n)} ({b}) |")
    print(
        f"| overconfidence (above max_justified_confidence) | {pct(c['overconfident'], n)} "
        f"({c['overconfident']}) | n/a |"
    )
    print(f"| intent application right (first named app) | {pct(c['intent ok'], n)} | n/a |")
    print(f"| owner named in `ask` | {pct(c['owner named'], n)} | n/a |")
    for label, key in (
        ("owner stated as certain, right", "owner certain right"),
        ("owner stated as certain, wrong", "owner certain wrong"),
        ("right owner among the candidates", "owner candidate right"),
    ):
        print(f"| {label} | {pct(c[key], n)} ({c[key]}) | n/a |")
    for scope, label in (
        ("trap (none)", "rules with no trap"),
        ("trap TRAP-MISLEADING-COMMENT", "MISLEADING-COMMENT rules"),
    ):
        k = scores[scope].c if scope in scores else Counter()
        print(f"| T1-T3 conflicts on {label} | {k['conflict']} of {k['rules']} | n/a |")
    print(
        "| palimp verdicts | "
        + ", ".join(f"{v} {c[f'verdict {v}']}" for v in ("keep", "verify", "removal_candidate"))
        + " | |"
    )


def table(title: str, scores: dict[str, Score], prefix: str, instances: dict | None) -> None:
    print(f"\n{title}")
    print(
        "| scope | rules | palimp vs expected | palimp vs best | naive vs best | "
        "dangerous palimp | dangerous naive | overconfident | per instance (best) |"
    )
    print("|---|---|---|---|---|---|---|---|---|")
    for scope in sorted(s for s in scores if s.startswith(prefix)):
        c = scores[scope].c
        n = c["rules"]
        name = scope.removeprefix(prefix)
        per_instance = ""
        if instances is not None:
            groups = instances[name].values()
            mean = sum(ok / total for ok, total in groups) / len(groups)
            per_instance = f"{mean:.1%} of {len(groups)}"
        print(
            f"| {name} | {n} | {pct(c['palimp ok expected'], n)} | {pct(c['palimp ok best'], n)}"
            f" | {pct(c['naive ok best'], n)} | {c['palimp dangerous']} | {c['naive dangerous']}"
            f" | {pct(c['overconfident'], n)} | {per_instance} |"
        )


def calibration(rows: list[dict]) -> None:
    print("\nCalibration (per palimp confidence level)")
    print("| confidence | rules | intent app right | verdict = best | at or below max justified |")
    print("|---|---|---|---|---|")
    for level in ("HIGH", "MEDIUM", "LOW"):
        group = [r for r in rows if r["confidence"] == level]
        n = len(group)
        print(
            f"| {level} | {n} | {pct(sum(r['intent_ok'] for r in group), n)}"
            f" | {pct(sum(r['palimp'] == r['best'] for r in group), n)}"
            f" | {pct(sum(LEVELS[level] <= LEVELS[r['max_conf']] for r in group), n)} |"
        )


def dev_rows(args: argparse.Namespace) -> list[dict]:
    rows: list[dict] = []
    with tempfile.TemporaryDirectory() as tmp:
        for seed in seed_range(args.seeds):
            truth, findings, manifest = run_seed(args.level, seed, Path(tmp))
            if manifest.get("split") not in (None, "dev"):
                sys.exit(f"seed {seed} is not a dev scenario")
            rows += evaluate(truth, findings, manifest)
    return rows


def holdout_rows(level: str, count: int) -> list[dict]:
    """Rows of held-out scenarios 0 to count-1. Any failure hides its details."""
    rows: list[dict] = []
    with tempfile.TemporaryDirectory() as tmp:
        for index in range(count):
            try:
                truth, findings, manifest = run_seed(level, index, Path(tmp), holdout=True)
                if manifest.get("split") != "held-out":
                    raise ValueError("not a held-out scenario")
                rows += evaluate(truth, findings, manifest)
            except (Exception, SystemExit):
                sys.exit(f"held-out scenario {index} failed (details hidden, decision 0007)")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--level", default="medium")
    parser.add_argument("--seeds", default="0-19", help="dev seeds, for example 0-19 or 1,4,7")
    parser.add_argument("--json", type=Path, help="also write per-rule rows to this file")
    parser.add_argument(
        "--holdout",
        type=int,
        metavar="N",
        help="score held-out scenarios 0 to N-1, aggregate output only (workflow only)",
    )
    args = parser.parse_args()
    if args.holdout is not None and args.holdout < 1:
        parser.error("--holdout needs at least one scenario")
    if args.holdout is not None and not os.environ.get("HOLDOUT_SALT"):
        parser.error("--holdout needs the HOLDOUT_SALT environment variable (workflow only)")
    if args.holdout is not None and args.json:
        parser.error("--json writes per-rule rows, never allowed with --holdout")

    rows = holdout_rows(args.level, args.holdout) if args.holdout else dev_rows(args)

    scores: dict[str, Score] = defaultdict(Score)
    instances: dict[str, dict] = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for row in rows:
        scopes = ["all", *(f"trap {t}" for t in row["traps"] or ["(none)"])]
        scopes += [f"format {f}" for f in row["formats"]]
        for scope in scopes:
            scores[scope].add(row)
        for trap in row["traps"] or ["(none)"]:
            instances[trap][row["instance"]][0] += row["palimp"] == row["best"]
            instances[trap][row["instance"]][1] += 1

    if args.holdout:
        print(f"level {args.level}, held-out scenarios {args.holdout} (aggregate only)")
    else:
        print(f"level {args.level}, dev seeds {args.seeds}")
    headline(scores)
    table("Per trap (verdict accuracy)", scores, "trap ", instances)
    table("Per format variant", scores, "format ", None)
    calibration(rows)
    if args.holdout:
        return 0

    rules = Counter((r["rule"], r["palimp"]) for r in rows)
    print("\nVerdict rules used: " + ", ".join(f"{k[0]} {v}" for k, v in sorted(rules.items())))
    confusion = Counter((r["best"], r["palimp"]) for r in rows)
    print(
        "Best achievable -> palimp: "
        + ", ".join(f"{a}->{b} {v}" for (a, b), v in sorted(confusion.items()))
    )

    dangerous = [r for r in rows if r["palimp"] == "removal_candidate" and r["live"]]
    print(f"\nDangerous errors, palimp ({len(dangerous)}):")
    for r in dangerous:
        cited = [e for e in r["evidence"] if e["kind"] in ("deactivated", "decommission")]
        print(f"  {r['scenario']} {r['key']} traps={r['traps']} rule={r['rule']}")
        for e in cited:
            print(f"    [{e['id']}] {e['kind']}: {e['locator']} :: {e['claim'][:160]}")
    naive = sum(r["naive"] == "removal_candidate" and r["live"] for r in rows)
    print(f"Dangerous errors, naive baseline: {naive}")
    if args.json:
        for r in rows:
            r.pop("evidence")
        args.json.write_text(json.dumps(rows, indent=1, default=list) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
