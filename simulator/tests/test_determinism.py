"""Same level and seed give byte-identical output, on any platform."""

import hashlib

import pytest

from palimp_sim.generate import generate

# SHA-256 of manifest.json, which holds the SHA-256 of every other file.
# Computed on Windows; CI checks the same values on Linux. Update only with a
# simulator version bump.
GOLDEN = {
    1: "7d3c6111a97a5415361ad00c4743fc2024988edfaad434fb4e04f7ff7eba2546",
    7: "bfdddeaa2fc395bf471f330ea77412132cac7686b528cf2c639d307c0eff0208",
}


def test_same_seed_same_bytes() -> None:
    assert generate("easy", 3) == generate("easy", 3)


def test_different_seeds_differ() -> None:
    assert generate("easy", 1)["manifest.json"] != generate("easy", 2)["manifest.json"]


@pytest.mark.parametrize("seed", sorted(GOLDEN))
def test_golden_manifest(seed: int) -> None:
    manifest = generate("easy", seed)["manifest.json"]
    assert hashlib.sha256(manifest).hexdigest() == GOLDEN[seed]


def test_no_carriage_returns() -> None:
    for path, data in generate("easy", 1).items():
        assert b"\r" not in data, path


def test_unknown_level_is_rejected() -> None:
    with pytest.raises(ValueError):
        generate("medium", 1)
