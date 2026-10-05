"""Same level and seed give byte-identical output, on any platform."""

import hashlib

import pytest

from palimp_sim import generate as generate_module
from palimp_sim import truth
from palimp_sim.generate import generate

# SHA-256 of manifest.json, which holds the SHA-256 of every other file.
# Computed on Windows; CI checks the same values on Linux. Update only with a
# simulator version bump.
# 0.2.0 (session 8): hitcount.txt follows the documentation layout and lists
# rows in random order; RT_FLOW CLOSE attributes follow the template order;
# four format knobs added to the manifest; simulator_version in ground truth.
# 0.3.0 (session 10): Medium trap counts drawn per scenario and the hit count
# clear placed independently of the jobs (decision 0018). Easy output did not
# change; its hashes change only because the version string is written in
# manifest.json and ground_truth.json (test_easy_changed_only_by_version below).
GOLDEN = {
    1: "fd55025b30669a3c9b49afcc2847db03dc23cceb4142e5bee7d3d2ff64d3ea2a",
    7: "c85ddc7f0b22dcf6d7188203ab3db48e23eb44b12062ae390dfeab1bf62df3d3",
}
# Easy hashes of 0.2.0: still produced when the version string is set back.
GOLDEN_0_2_0 = {
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


@pytest.mark.parametrize("seed", sorted(GOLDEN_0_2_0))
def test_easy_changed_only_by_version(seed: int, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(generate_module, "__version__", "0.2.0")
    monkeypatch.setattr(truth, "__version__", "0.2.0")
    manifest = generate("easy", seed)["manifest.json"]
    assert hashlib.sha256(manifest).hexdigest() == GOLDEN_0_2_0[seed]


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
# 0.3.0 (session 10): trap counts drawn per scenario (decision 0018).
GOLDEN_MEDIUM = {
    0: "8a34091e66a51d3ae42aca08b44359054dade79ea4a6e06d1133db3bb24df48e",
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
