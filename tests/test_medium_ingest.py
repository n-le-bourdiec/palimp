"""Black-box ingest of Medium scenarios (seeds 0 to 9): every line is understood.

Unknown lines are not the only failure mode: a line read as "parsed" can still
be misread. So the test also checks that every log event got a timestamp and
that every hit count row names a policy of the configuration.
"""

import subprocess
import sys
from pathlib import Path

import pytest

from palimp.ingest import ingest


def generate(level: str, seed: int, out: Path) -> Path:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "palimp_sim.cli",
            "generate",
            "--level",
            level,
            "--seed",
            str(seed),
            "--out",
            str(out),
        ],
        check=True,
        capture_output=True,
    )
    return out / f"scenario-{level}-{seed:06d}"


@pytest.mark.slow
@pytest.mark.parametrize("seed", range(10))
def test_medium_ingest_has_no_unknown_lines(seed: int, tmp_path: Path) -> None:
    dataset = ingest(generate("medium", seed, tmp_path))
    all_stats = [
        dataset.config.stats,
        dataset.commit_stats,
        dataset.hit_count_stats,
        dataset.log_stats,
        dataset.ticket_stats,
        *dataset.rollback_stats,
    ]
    unknown = {s.file: s.unknown_samples for s in all_stats if s and s.unknown}
    assert unknown == {}
    assert dataset.logs and all(s.first_seen for s in dataset.logs.values())
    keys = {str(p.key) for p in dataset.config.policies}
    assert {f"{h.from_zone}/{h.to_zone}/{h.name}" for h in dataset.hit_counts} <= keys
