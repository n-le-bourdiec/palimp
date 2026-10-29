"""Same level and seed give byte-identical output, on any platform."""

import hashlib
import json

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
# 0.4.0 (session 30): realistic names, the naming source confidence model and
# new rule kinds in Medium and Hard (decision 0045). Easy output did not change.
# 0.5.0 (session 32): `expected.rule_kind` and `expected.best_achievable_intent`
# in every rule, shadowed rules and `ANY` address sets in Medium and Hard
# (decision 0047). Easy artifacts did not change; its ground truth gains the
# two fields (test_easy_changed_only_by_version below).
# 0.5.1 (session 34): a direct statement alone justifies MEDIUM in Medium and
# Hard (decision 0049). Easy output did not change.
GOLDEN = {
    1: "df53a0ed1571a3c0fea68e0ca75b3b9c459601aa53001c4c4cd4eb45ac4bb34c",
    7: "92e68539e72ed246e706e7540d5b1b6a2da5f2ab4c180e61e5963bb60c28f9f5",
}
# Easy hashes of earlier versions: still produced when the version string is
# set back and the fields added since are left out of the ground truth.
GOLDEN_EARLIER = {
    ("0.3.0", 1): "fd55025b30669a3c9b49afcc2847db03dc23cceb4142e5bee7d3d2ff64d3ea2a",
    ("0.3.0", 7): "c85ddc7f0b22dcf6d7188203ab3db48e23eb44b12062ae390dfeab1bf62df3d3",
    ("0.4.0", 1): "3c8ee77e905fe22bf2e478a163ce58eedb53d2ef534bd0c89ff409e79bd26324",
    ("0.4.0", 7): "b616ad6db3bb8d63ec44e227f3c0888b2ae81c8d925f5c1e0034c91ca93cdf12",
    ("0.5.0", 1): "321be406b21aed1831d9b78d8608d0458cfb14f6aedbcb83462597d3a1c6ba11",
    ("0.5.0", 7): "ecafedb605325af3e23ca4cce0292f76d56ab3482a59fb4e7f3e43eaa89859b7",
}
# Ground truth fields added after each earlier version.
FIELDS_SINCE = {
    "0.3.0": ("rule_kind", "best_achievable_intent"),
    "0.4.0": ("rule_kind", "best_achievable_intent"),
    "0.5.0": (),
}


def test_same_seed_same_bytes() -> None:
    assert generate("easy", 3) == generate("easy", 3)


def test_different_seeds_differ() -> None:
    assert generate("easy", 1)["manifest.json"] != generate("easy", 2)["manifest.json"]


@pytest.mark.parametrize("seed", sorted(GOLDEN))
def test_golden_manifest(seed: int) -> None:
    manifest = generate("easy", seed)["manifest.json"]
    assert hashlib.sha256(manifest).hexdigest() == GOLDEN[seed]


@pytest.mark.parametrize(("version", "seed"), sorted(GOLDEN_EARLIER))
def test_easy_changed_only_by_version(
    version: str, seed: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(generate_module, "__version__", version)
    monkeypatch.setattr(truth, "__version__", version)
    files = generate("easy", seed)
    document = json.loads(files["ground_truth.json"])
    for rule in document["rules"]:
        for name in FIELDS_SINCE[version]:
            del rule["expected"][name]
    data = generate_module._json(document).encode("utf-8")
    manifest = json.loads(files["manifest.json"])
    manifest["files"]["ground_truth.json"] = hashlib.sha256(data).hexdigest()
    rebuilt = generate_module._json(manifest).encode("utf-8")
    assert hashlib.sha256(rebuilt).hexdigest() == GOLDEN_EARLIER[(version, seed)]


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
        generate("adversarial", 1)


# 0.2.0 (session 9): Medium added; Easy output unchanged.
# 0.3.0 (session 10): trap counts drawn per scenario (decision 0018).
# 0.4.0 (session 30): decision 0045.
# 0.5.0 (session 32): decision 0047.
# 0.5.1 (session 34): decision 0049.
GOLDEN_MEDIUM = {
    0: "83beb244763fc35e6684a79a1dd7f8036b7927fd8e75419868b8dbe1c5972a8c",
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
