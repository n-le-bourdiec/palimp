"""Round trip set -> model -> hierarchical text -> model (decision 0032).

On Medium dev seeds 0 to 9, the test suite renders the model palimp parsed
from config.set and every rollback as hierarchical text (tests/conftest.py),
palimp reads it back, and everything it concludes is identical: the model
(except policy positions, since Junos groups policies by zone pair),
creation commits, verdicts, confidence levels and owners. Black box like the
other tests: the simulator writes a scenario, palimp reads only its artifacts.
"""

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from palimp.evidence import collect_all
from palimp.ingest import ingest
from palimp.models import Config, Dataset

SEEDS = range(10)


def generate(seed: int, out: Path) -> Path:
    command = [sys.executable, "-m", "palimp_sim.cli", "generate", "--level", "medium"]
    subprocess.run(
        command + ["--seed", str(seed), "--out", str(out)], check=True, capture_output=True
    )
    return out / f"scenario-medium-{seed:06d}" / "artifacts"


def model(config: Config) -> tuple:
    policies = sorted(
        (p.model_copy(update={"position": 0}) for p in config.policies), key=lambda p: str(p.key)
    )
    return policies, config.addresses, config.applications


def judgments(dataset: Dataset) -> dict[str, tuple]:
    found = {}
    for finding in collect_all(dataset):
        a = finding.assessment
        assert a is not None
        found[str(finding.key)] = (
            a.verdict,
            a.verdict_rule,
            a.confidence,
            a.confidence_rule,
            a.owner,
            a.owner_candidates,
        )
    return found


@pytest.mark.slow
@pytest.mark.parametrize("seed", SEEDS)
def test_hierarchical_round_trip(
    seed: int, tmp_path: Path, to_hierarchical: Callable[[Path, Path], Path]
) -> None:
    flat_dir = generate(seed, tmp_path / "set")
    hier_dir = to_hierarchical(flat_dir, tmp_path / "hier")
    assert (hier_dir / "config.set").read_text(encoding="utf-8").count("{") > 100
    flat, hier = ingest(flat_dir), ingest(hier_dir)

    assert hier.config.stats.format == "hierarchical" and hier.config.stats.unknown == 0
    assert {s.format for s in hier.rollback_stats} == {"hierarchical"}
    assert sum(s.unknown for s in hier.rollback_stats) == 0
    assert model(hier.config) == model(flat.config)
    assert hier.history == flat.history
    assert hier.created_by_commit == flat.created_by_commit
    assert hier.removed_by_commit == flat.removed_by_commit
    assert hier.deactivated_by_commit == flat.deactivated_by_commit
    assert judgments(hier) == judgments(flat)
