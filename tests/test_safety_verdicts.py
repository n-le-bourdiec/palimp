"""No removal candidate on a rule that is live or still needed (decisions 0038 and 0051).

Black box like the eval harness: the simulator writes a scenario, palimp reads
only its artifacts, and the test compares palimp's verdicts with the ground
truth `status` block (the documented JSON Schema, not simulator code).

Dangerous means `removal_candidate` on a rule whose `status.live` or
`status.still_needed` is true (decision 0038). Every removal_candidate must
also name the one positive not-live signal it rests on (decision 0051): an
item of this rule, of a not-live kind, cited by the verdict.

Two tiers (audit M5, session 36):
- fast: Medium seeds 0 to 19 and Hard seeds 0 to 19, in CI (marker `slow`);
- slow: Medium seeds 20 to 99 and Hard seeds 20 to 49, with `--runslow` only
  (marker `full`). With `--runslow` both tiers run: Medium 0 to 99, Hard 0 to 49.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from palimp.assess import NOT_LIVE_KINDS
from palimp.evidence import collect_all
from palimp.ingest import ingest

FAST = [("medium", s) for s in range(20)] + [("hard", s) for s in range(20)]
SLOW = [("medium", s) for s in range(20, 100)] + [("hard", s) for s in range(20, 50)]


def generate(level: str, seed: int, out: Path) -> Path:
    command = [sys.executable, "-m", "palimp_sim.cli", "generate", "--level", level]
    subprocess.run(
        command + ["--seed", str(seed), "--out", str(out)], check=True, capture_output=True
    )
    return out / f"scenario-{level}-{seed:06d}"


def check(level: str, seed: int, tmp_path: Path) -> None:
    scenario = generate(level, seed, tmp_path)
    truth = json.loads((scenario / "ground_truth.json").read_text(encoding="utf-8"))
    needed = {
        "/".join((r["key"]["from_zone"], r["key"]["to_zone"], r["key"]["name"]))
        for r in truth["rules"]
        if r["status"]["live"] or r["status"]["still_needed"]
    }
    findings = collect_all(ingest(scenario / "artifacts"))
    removal = [f for f in findings if f.assessment.verdict == "removal_candidate"]
    assert {str(f.key) for f in removal} & needed == set()
    for finding in removal:
        assessment = finding.assessment
        signal = next((e for e in finding.evidence if e.id == assessment.removal_signal), None)
        assert signal is not None, f"{finding.key}: no named signal"
        assert signal.kind in NOT_LIVE_KINDS, f"{finding.key}: {signal.kind}"
        assert signal.id in assessment.verdict_evidence, str(finding.key)
    assert all(f.assessment.verdict_rule and f.assessment.confidence_rule for f in findings)


@pytest.mark.slow
@pytest.mark.parametrize(("level", "seed"), FAST)
def test_no_removal_candidate_on_a_needed_rule(level: str, seed: int, tmp_path: Path) -> None:
    check(level, seed, tmp_path)


@pytest.mark.full
@pytest.mark.parametrize(("level", "seed"), SLOW)
def test_no_removal_candidate_on_a_needed_rule_all_dev_seeds(
    level: str, seed: int, tmp_path: Path
) -> None:
    check(level, seed, tmp_path)
