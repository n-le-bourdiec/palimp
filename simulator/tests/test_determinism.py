"""Same level and seed give byte-identical output, on any platform."""

import hashlib

import pytest

from palimp_sim.generate import generate

# SHA-256 of manifest.json, which holds the SHA-256 of every other file.
# Computed on Windows; CI checks the same values on Linux. Update only with a
# simulator version bump.
GOLDEN = {
    1: "8da51ad7b79eca19815d777fc51e47a4697cf120d9769a27e35ee79ffb0c3c9e",
    7: "986c1062710f6b1d367e9d4eb8a056790ad446532cc73bc15da96f6100fdb807",
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
