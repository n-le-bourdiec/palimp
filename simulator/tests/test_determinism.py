"""Same level and seed give byte-identical output, on any platform."""

import hashlib

import pytest

from palimp_sim.generate import generate

# SHA-256 of manifest.json, which holds the SHA-256 of every other file.
# Computed on Windows; CI checks the same values on Linux. Update only with a
# simulator version bump.
# 0.2.0 (session 8): hitcount.txt follows the documentation layout and lists
# rows in random order; RT_FLOW CLOSE attributes follow the template order;
# four format knobs added to the manifest; simulator_version in ground truth.
GOLDEN = {
    1: "7b1b31876f097896ea3a7cd5f332d3a2d469cfb2a84b94a003e9da99152d5c9a",
    7: "e4e8c9fb36c9560fc3a153a460b760a7fb919230e35942e8e54c14f40a736872",
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


def test_overrides_are_deterministic_and_recorded() -> None:
    overrides = {"log_collection": "syslog-server", "rescue_line": "true"}
    first = generate("easy", 3, overrides)
    assert first == generate("easy", 3, overrides)
    assert b'"log_collection": "syslog-server"' in first["manifest.json"]


def test_unknown_knob_or_value_is_rejected() -> None:
    with pytest.raises(ValueError):
        generate("easy", 1, {"no_such_knob": "1"})
    with pytest.raises(ValueError):
        generate("easy", 1, {"log_collection": "carrier-pigeon"})


def test_unknown_level_is_rejected() -> None:
    with pytest.raises(ValueError):
        generate("hard", 1)


# 0.2.0 (session 9): Medium added; Easy output unchanged.
GOLDEN_MEDIUM = {
    0: "c6690e6c57b35c4e06abf14dd574efc9a7c9c5343070dbe5780dc4bcdbfecae9",
}


@pytest.mark.parametrize("seed", sorted(GOLDEN_MEDIUM))
def test_golden_manifest_medium(seed: int) -> None:
    manifest = generate("medium", seed)["manifest.json"]
    assert hashlib.sha256(manifest).hexdigest() == GOLDEN_MEDIUM[seed]


def test_medium_same_seed_same_bytes() -> None:
    assert generate("medium", 4) == generate("medium", 4)


def test_medium_has_no_carriage_returns() -> None:
    for path, data in generate("medium", 1).items():
        assert b"\r" not in data, path
