"""Generate one scenario: artifacts, ground truth and manifest (spec section 5)."""

import hashlib
import json
from pathlib import Path

from palimp_sim import __version__
from palimp_sim.artifacts import commits_txt, hitcount_txt, rollback_files, rt_flow_log, tickets_csv
from palimp_sim.junos import render_set
from palimp_sim.levels import LEVELS
from palimp_sim.rng import Rng
from palimp_sim.traffic import live_policies, simulate
from palimp_sim.truth import ground_truth
from palimp_sim.world import Simulation


def scenario_id(level: str, seed: int) -> str:
    return f"{level}-{seed:06d}"


def _json(document: dict) -> str:
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def generate(level: str, seed: int) -> dict[str, bytes]:
    """Return every file of the scenario as {relative path: content}."""
    if level not in LEVELS:
        raise ValueError(f"level {level!r} is not implemented (available: {sorted(LEVELS)})")
    if seed < 0:
        raise ValueError("seed must be zero or positive")
    sim = Simulation(LEVELS[level], seed).run()
    traffic = simulate(sim, Rng(f"palimp-sim:{level}:{seed}").derive("traffic"))
    log_text, log_lines = rt_flow_log(sim, traffic)
    texts = {
        "artifacts/config.set": render_set(sim.config),
        "artifacts/commits.txt": commits_txt(sim),
        "artifacts/hitcount.txt": hitcount_txt(sim, traffic),
        "artifacts/logs/rt_flow.log": log_text,
        "artifacts/tickets.csv": tickets_csv(sim),
    }
    texts.update({f"artifacts/{path}": text for path, text in rollback_files(sim).items()})
    texts["ground_truth.json"] = _json(ground_truth(sim, traffic, live_policies(sim), log_lines))
    files = {path: text.encode("utf-8") for path, text in sorted(texts.items())}
    manifest = {
        "simulator_version": __version__,
        "scenario_id": scenario_id(level, seed),
        "level": level,
        "seed": seed,
        "split": "dev",
        "snapshot": sim.date(sim.total_days).isoformat(),
        "knobs": sim.level.knobs(),
        "files": {path: hashlib.sha256(data).hexdigest() for path, data in files.items()},
    }
    files["manifest.json"] = _json(manifest).encode("utf-8")
    return files


def write_scenario(files: dict[str, bytes], directory: Path) -> None:
    for path, data in files.items():
        target = directory / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
