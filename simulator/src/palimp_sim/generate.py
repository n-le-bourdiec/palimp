"""Generate one scenario: artifacts, ground truth and manifest (spec section 5)."""

import hashlib
import json
from pathlib import Path

from palimp_sim import __version__
from palimp_sim.artifacts import commits_txt, hitcount_txt, rollback_files, rt_flow_log, tickets_csv
from palimp_sim.junos import render_set
from palimp_sim.levels import FORMAT_DRAWS, LEVELS
from palimp_sim.medium import MediumSimulation
from palimp_sim.rng import Rng
from palimp_sim.traffic import live_policies, simulate
from palimp_sim.truth import ground_truth
from palimp_sim.world import Simulation


def scenario_id(level: str, seed: int) -> str:
    return f"{level}-{seed:06d}"


def _json(document: dict) -> str:
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def draw_formats(rng: Rng, overrides: dict) -> dict:
    """Format knobs drawn per scenario (decision 0016); overrides win."""
    drawn = {}
    for name, options in FORMAT_DRAWS.items():
        point, value = rng.random(), options[-1][0]
        for option, weight in options:
            if point < weight:
                value = option
                break
            point -= weight
        if name not in overrides:
            drawn[name] = value
    return drawn


def clock_skew(rng: Rng) -> int:
    """Syslog server clock minus device clock, in seconds: 1 to 6, either sign."""
    return rng.randint(1, 6) * (1 if rng.chance(0.5) else -1)


def generate(level: str, seed: int, overrides: dict | None = None) -> dict[str, bytes]:
    """Return every file of the scenario as {relative path: content}.

    `overrides` replaces individual knobs of the level (spec section 7.1).
    """
    if level not in LEVELS:
        raise ValueError(f"level {level!r} is not implemented (available: {sorted(LEVELS)})")
    if seed < 0:
        raise ValueError("seed must be zero or positive")
    overrides = dict(overrides or {})
    rng = Rng(f"palimp-sim:{level}:{seed}")
    knobs = LEVELS[level].with_overrides(overrides)
    drawn = draw_formats(rng.derive("formats"), overrides) if knobs.draw_formats else {}
    knobs = knobs.with_overrides({name: str(value) for name, value in drawn.items()})
    simulation = MediumSimulation if knobs.traps else Simulation
    sim = simulation(knobs, seed).run()
    traffic = simulate(sim, rng.derive("traffic"))
    server = knobs.log_collection == "syslog-server"
    # Easy keeps the server clock equal to the device clock (session 8 output).
    skew = clock_skew(rng.derive("clock-skew")) if server and knobs.clock_skew else 0
    log_text, log_lines = rt_flow_log(sim, traffic, skew)
    texts = {
        "artifacts/config.set": render_set(sim.config),
        "artifacts/commits.txt": commits_txt(sim),
        "artifacts/hitcount.txt": hitcount_txt(sim, traffic, rng.derive("hitcount")),
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
    }
    if drawn:
        manifest["format_draw"] = {name: drawn[name] for name in sorted(drawn)}
    if server and knobs.clock_skew:
        manifest["syslog_clock_skew_seconds"] = skew
    if sim.pair_resets:
        manifest["hit_count_clears"] = [
            {"from_zone": pair[0], "to_zone": pair[1], "date": sim.date(day).isoformat()}
            for pair, day in sorted(sim.pair_resets.items())
        ]
    manifest |= {
        "files": {path: hashlib.sha256(data).hexdigest() for path, data in files.items()},
    }
    files["manifest.json"] = _json(manifest).encode("utf-8")
    return files


def write_scenario(files: dict[str, bytes], directory: Path) -> None:
    for path, data in files.items():
        target = directory / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
