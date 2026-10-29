"""Verdict and confidence evaluation of palimp against simulator ground truth.

Runs both tools as black boxes (see evidence_recall.py), then compares, rule
by rule, palimp's assessment with the ground truth `expected` block
(simulator/src/palimp_sim/schema/ground_truth.schema.json):

- verdict accuracy against `expected.verdict` and against
  `expected.best_achievable_verdict` (the fair one: what the artifacts allow);
- dangerous errors: removal_candidate on a rule whose `status.live` or
  `status.still_needed` is true (decision 0038: a rule whose original intent
  is dead but that now carries other needed traffic counts). Every one is
  listed. The old count (`status.live` only, used up to held-out run 1) is
  printed next to it;
- overconfidence: confidence above `expected.best_achievable_confidence`
  when present (Hard rules, decision 0040: what a perfect analyzer can justify
  from the artifacts alone), else `expected.max_justified_confidence`. The
  count against `max_justified_confidence` alone is printed next to it;
- intent against what the artifacts allow (decision 0047, session 33):
  application rules on `expected.best_achievable_intent` (palimp's first
  named application; when it is null, palimp is right when it names no
  application: "purpose unknown" or a flow without an application), firewall
  team rules on `expected.rule_kind` against palimp's own reading of the rule
  (cleanup, block, broad permit, factory default). The old number, palimp's
  first application against the true one (`intent.app_id`), is printed next
  to it as "vs true application";
- calibration: per confidence level, how often palimp's intent is right (vs
  best achievable and vs true application), and how often the verdict is the
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


def palimp_kind(finding: dict) -> str:
    """palimp's own reading of the rule, in the order the report's intent sentence uses."""
    kinds = {e.get("kind") for e in finding["evidence"]}
    for sign, kind in (
        ("catch_all_deny", "cleanup_deny"),
        ("factory_default", "factory_default"),
        ("broad_permit", "broad_permit"),
    ):
        if sign in kinds:
            return kind
    if (finding["policy"].get("action") or "").lower() in ("deny", "reject"):
        return "block"
    return "application"


def rule_kind(rule: dict) -> str:
    """`expected.rule_kind`; from the intent kind for a ground truth older than 0.5.0."""
    kind = rule["intent"]["kind"]
    return rule["expected"].get("rule_kind", kind if kind in FIREWALL_KINDS else "application")


def intent_best_ok(rule: dict, finding: dict) -> bool:
    """Intent right against what the artifacts allow (decision 0047): the rule kind for a
    firewall team rule, else `best_achievable_intent` (null: no application named)."""
    kind = rule_kind(rule)
    if kind != "application":
        return palimp_kind(finding) == kind
    if palimp_kind(finding) != "application":
        return False
    apps = finding["assessment"]["intent_apps"]
    best = rule["expected"].get("best_achievable_intent", rule["intent"]["app_id"])
    if best is None:
        return not apps
    return app_of(best) in [app_of(a) for a in apps[:1]]


def any_source(finding: dict) -> bool:
    """A source address object named like the `any` keyword (`ANY`, `Any-Hosts`)."""
    return any(
        s != "any" and s.lower() in ("any", "any-hosts") for s in finding["policy"]["sources"]
    )


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
            c[f"{who} dangerous"] += verdict == "removal_candidate" and row["needed"]
            c[f"{who} dangerous old"] += verdict == "removal_candidate" and row["live"]
            c[f"{who} removal"] += verdict == "removal_candidate"
        c["overconfident"] += LEVELS[row["confidence"]] > LEVELS[row["best_conf"]]
        c["overconfident max"] += LEVELS[row["confidence"]] > LEVELS[row["max_conf"]]
        c["underconfident"] += LEVELS[row["confidence"]] < LEVELS[row["best_conf"]]
        c["kind recognized"] += row["kind_recognized"]
        c["intent ok"] += row["intent_ok"]
        c["intent best ok"] += row["intent_best_ok"]
        c["owner named"] += row["owner_ok"]
        c["owner certain right"] += row["owner_certain"] == "right"
        c["owner certain wrong"] += row["owner_certain"] == "wrong"
        c["owner candidate right"] += row["owner_candidate_ok"]
        c["conflict"] += row["conflict"]
        c[f"verdict {row['palimp']}"] += 1


def pct(part: int, whole: int) -> str:
    return f"{part / whole:.1%}" if whole else "n/a"


# Firewall team rule kinds (decision 0045) -> palimp evidence kinds or verdict rules that
# show palimp read the rule as that kind. A deny rule is recognized by its action: any
# verdict rule of a deny (`V-CLEANUP-RULE`, `V-DENY-*`) or an action-based keep.
KIND_SIGNS = {
    "cleanup_deny": {"catch_all_deny"},
    "factory_default": {"factory_default"},
    "broad_permit": {"broad_permit", "factory_default"},
}
FIREWALL_KINDS = ("block", "cleanup_deny", "broad_permit", "factory_default")


def kind_recognized(kind: str, finding: dict) -> bool:
    if kind == "block":
        return finding["policy"].get("action") in ("deny", "reject")
    signs = KIND_SIGNS.get(kind)
    return bool(signs) and any(e.get("kind") in signs for e in finding["evidence"])


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
                "kind": rule["intent"]["kind"],
                "kind_recognized": kind_recognized(rule["intent"]["kind"], finding),
                "rule_kind": rule_kind(rule),
                "any_source": any_source(finding),
                "instance": (truth["scenario_id"], rule["created"]["event_id"]),
                "formats": formats,
                "live": rule["status"]["live"],
                "needed": rule["status"]["live"] or rule["status"]["still_needed"],
                "expected": expected["verdict"],
                "best": expected["best_achievable_verdict"],
                "max_conf": expected["max_justified_confidence"],
                "best_conf": expected.get(
                    "best_achievable_confidence", expected["max_justified_confidence"]
                ),
                "palimp": assessment["verdict"],
                "rule": assessment["verdict_rule"],
                "confidence": assessment["confidence"],
                "confidence_rule": assessment["confidence_rule"],
                "intent_ok": app_of(rule["intent"]["app_id"])
                in [app_of(a) for a in assessment["intent_apps"][:1]],
                "intent_best_ok": intent_best_ok(rule, finding),
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
        ("dangerous errors (removal_candidate on a live or still needed rule)", "dangerous"),
        ("dangerous errors, old definition (live rule only)", "dangerous old"),
    ):
        p, b = c[f"palimp {key}"], c[f"naive {key}"]
        if key in ("removal", "dangerous", "dangerous old"):
            print(f"| {label} | {p} | {b} |")
        else:
            print(f"| {label} | {pct(p, n)} ({p}) | {pct(b, n)} ({b}) |")
    print(
        "| overconfidence (above best_achievable_confidence, else max_justified) | "
        f"{pct(c['overconfident'], n)} ({c['overconfident']}) | n/a |"
    )
    print(
        f"| overconfidence (above max_justified_confidence) | {pct(c['overconfident max'], n)} "
        f"({c['overconfident max']}) | n/a |"
    )
    print(
        f"| underconfidence (below best_achievable_confidence, else max_justified) | "
        f"{pct(c['underconfident'], n)} ({c['underconfident']}) | n/a |"
    )
    print(
        "| intent right vs best achievable (best_achievable_intent, rule_kind) | "
        f"{pct(c['intent best ok'], n)} ({c['intent best ok']}) | n/a |"
    )
    print(
        "| intent application right vs true application (intent.app_id, first named app) | "
        f"{pct(c['intent ok'], n)} ({c['intent ok']}) | n/a |"
    )
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
        "dangerous palimp (old) | dangerous naive | overconfident (vs max justified) | "
        "per instance (best) |"
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
            f" | {pct(c['naive ok best'], n)}"
            f" | {c['palimp dangerous']} ({c['palimp dangerous old']}) | {c['naive dangerous']}"
            f" | {pct(c['overconfident'], n)} ({pct(c['overconfident max'], n)})"
            f" | {per_instance} |"
        )


def summary(scores: dict[str, Score]) -> None:
    """One table: all rules, per rule kind, shadowed rules and rules with an `ANY` source."""
    print("\nSummary")
    print(
        "| scope | rules | verdict vs best | intent vs best achievable | intent vs true "
        "application | overconfident | underconfident | dangerous palimp | dangerous naive |"
    )
    print("|---|---|---|---|---|---|---|---|---|")
    present = {s.removeprefix("rule kind ") for s in scores if s.startswith("rule kind ")}
    order = ["all"] + [f"rule kind {k}" for k in ("application", *FIREWALL_KINDS) if k in present]
    order += ["trap TRAP-SHADOWED-BY-DENY", "ANY source"]
    for scope in order:
        c = scores[scope].c if scope in scores else Counter()
        n = c["rules"]
        print(
            f"| {scope} | {n} | {pct(c['palimp ok best'], n)} | {pct(c['intent best ok'], n)}"
            f" | {pct(c['intent ok'], n)} | {pct(c['overconfident'], n)}"
            f" | {pct(c['underconfident'], n)} | {c['palimp dangerous']}"
            f" | {c['naive dangerous']} |"
        )


def kinds(scores: dict[str, Score]) -> None:
    """Per ground truth intent kind; firewall team kinds first (decision 0045)."""
    print("\nPer intent kind")
    print(
        "| kind | rules | palimp vs expected | palimp vs best | dangerous | intent vs best "
        "achievable | intent vs true application | kind recognized | overconfident "
        "| underconfident |"
    )
    print("|---|---|---|---|---|---|---|---|---|---|")
    present = sorted(s.removeprefix("kind ") for s in scores if s.startswith("kind "))
    order = [k for k in FIREWALL_KINDS if k in present] + [
        k for k in present if k not in FIREWALL_KINDS
    ]
    for kind in order:
        c = scores[f"kind {kind}"].c
        n = c["rules"]
        recognized = pct(c["kind recognized"], n) if kind in FIREWALL_KINDS else ""
        print(
            f"| {kind} | {n} | {pct(c['palimp ok expected'], n)} | {pct(c['palimp ok best'], n)}"
            f" | {c['palimp dangerous']} | {pct(c['intent best ok'], n)}"
            f" | {pct(c['intent ok'], n)} | {recognized}"
            f" | {pct(c['overconfident'], n)} | {pct(c['underconfident'], n)} |"
        )


def calibration(rows: list[dict]) -> None:
    print("\nCalibration (per palimp confidence level)")
    print(
        "| confidence | rules | intent vs best achievable | intent vs true application "
        "| verdict = best | at or below best achievable | at or below max justified |"
    )
    print("|---|---|---|---|---|---|---|")
    for level in ("HIGH", "MEDIUM", "LOW"):
        group = [r for r in rows if r["confidence"] == level]
        n = len(group)
        print(
            f"| {level} | {n} | {pct(sum(r['intent_best_ok'] for r in group), n)}"
            f" | {pct(sum(r['intent_ok'] for r in group), n)}"
            f" | {pct(sum(r['palimp'] == r['best'] for r in group), n)}"
            f" | {pct(sum(LEVELS[level] <= LEVELS[r['best_conf']] for r in group), n)}"
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
        scopes.append(f"kind {row['kind']}")
        scopes.append(f"rule kind {row['rule_kind']}")
        if row["any_source"]:
            scopes.append("ANY source")
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
    summary(scores)
    table("Per trap (verdict accuracy)", scores, "trap ", instances)
    table("Per format variant", scores, "format ", None)
    kinds(scores)
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

    dangerous = [r for r in rows if r["palimp"] == "removal_candidate" and r["needed"]]
    old = sum(r["live"] for r in dangerous)
    print(f"\nDangerous errors, palimp ({len(dangerous)}; old definition, live only: {old}):")
    for r in dangerous:
        cited = [e for e in r["evidence"] if e["kind"] in ("deactivated", "decommission")]
        why = "live" if r["live"] else "still needed, not live"
        print(f"  {r['scenario']} {r['key']} traps={r['traps']} rule={r['rule']} ({why})")
        for e in cited:
            print(f"    [{e['id']}] {e['kind']}: {e['locator']} :: {e['claim'][:160]}")
    naive = sum(r["naive"] == "removal_candidate" and r["needed"] for r in rows)
    naive_old = sum(r["naive"] == "removal_candidate" and r["live"] for r in rows)
    print(f"Dangerous errors, naive baseline: {naive} (old definition: {naive_old})")
    if args.json:
        for r in rows:
            r.pop("evidence")
        args.json.write_text(json.dumps(rows, indent=1, default=list) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
