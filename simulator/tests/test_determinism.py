"""Same level and seed give byte-identical output, on any platform."""

import hashlib

import pytest

from palimp_sim.generate import generate

# SHA-256 of manifest.json, which holds the SHA-256 of every other file.
# Computed on Windows; CI checks the same values on Linux. Update only with a
# simulator version bump.
GOLDEN = {
    1: "b7e806c39d1c6f650b25c9f6402ae03f16153d0ad16f1d94725391d0e439216d",
    7: "2fefc20a557c70f88cedf8a4ef68c42346111f8a90f2b0ecdb19782fcce713e8",
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
