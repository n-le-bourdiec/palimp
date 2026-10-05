"""No removal candidate on a live rule, Medium dev seeds 0 to 9 (decision 0020).

Black box like the eval harness: the simulator writes a scenario, palimp reads
only its artifacts, and the test compares palimp's verdicts with the ground
truth `status.live` flag (the documented JSON Schema, not simulator code).
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from palimp.evidence import collect_all
from palimp.ingest import ingest


def generate(seed: int, out: Path) -> Path:
    command = [sys.executable, "-m", "palimp_sim.cli", "generate", "--level", "medium"]
    subprocess.run(
        command + ["--seed", str(seed), "--out", str(out)], check=True, capture_output=True
    )
    return out / f"scenario-medium-{seed:06d}"


@pytest.mark.slow
@pytest.mark.parametrize("seed", range(10))
def test_no_removal_candidate_on_a_live_rule(seed: int, tmp_path: Path) -> None:
    scenario = generate(seed, tmp_path)
    truth = json.loads((scenario / "ground_truth.json").read_text(encoding="utf-8"))
    live = {
        "/".join((r["key"]["from_zone"], r["key"]["to_zone"], r["key"]["name"]))
        for r in truth["rules"]
        if r["status"]["live"]
    }
    findings = collect_all(ingest(scenario / "artifacts"))
    removal = {str(f.key) for f in findings if f.assessment.verdict == "removal_candidate"}
    assert removal & live == set()
    assert all(f.assessment.verdict_rule and f.assessment.confidence_rule for f in findings)
