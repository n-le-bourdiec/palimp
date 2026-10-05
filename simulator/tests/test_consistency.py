"""Internal consistency between artifacts and ground truth."""

import json
import re

import pytest

from palimp_sim.generate import generate

POLICY = re.compile(r"^set security policies from-zone (\S+) to-zone (\S+) policy (\S+) ")
DEACTIVATED = re.compile(
    r"^deactivate security policies from-zone (\S+) to-zone (\S+) policy (\S+)$"
)
SCENARIOS = [("easy", s) for s in range(6)] + [("medium", s) for s in range(4)]


def config_policies(text: str) -> list[tuple[str, str, str]]:
    keys = []
    for line in text.splitlines():
        match = POLICY.match(line)
        if match and match.groups() not in keys:
            keys.append(match.groups())
    return keys


def hitcount_rows(text: str) -> list[list[str]]:
    """Rows of either layout (standard or legacy), split on spaces."""
    return [line.split() for line in text.splitlines() if line[:2].strip().isdigit()]


@pytest.fixture(scope="module", params=SCENARIOS, ids=lambda p: f"{p[0]}-{p[1]}")
def scenario(request) -> dict[str, str]:
    level, seed = request.param
    return {path: data.decode("utf-8") for path, data in generate(level, seed).items()}


def test_every_policy_has_exactly_one_ground_truth_entry(scenario) -> None:
    truth = json.loads(scenario["ground_truth.json"])
    truth_keys = [
        (r["key"]["from_zone"], r["key"]["to_zone"], r["key"]["name"]) for r in truth["rules"]
    ]
    config_keys = config_policies(scenario["artifacts/config.set"])
    assert len(truth_keys) == len(set(truth_keys))
    assert sorted(truth_keys) == sorted(config_keys)


def test_policy_names_are_unique(scenario) -> None:
    names = [key[2] for key in config_policies(scenario["artifacts/config.set"])]
    assert len(names) == len(set(names))


def test_hitcount_lists_every_active_policy(scenario) -> None:
    rows = hitcount_rows(scenario["artifacts/hitcount.txt"])
    keys = [tuple(row[1:4]) for row in rows]
    config = scenario["artifacts/config.set"]
    inactive = {m.groups() for m in map(DEACTIVATED.match, config.splitlines()) if m}
    active = [key for key in config_policies(config) if key not in inactive]
    # Rows are in random order (VSRX-7b), so only the set of policies counts.
    # Deactivated policies are not installed, so not listed (VSRX-2b).
    assert sorted(keys) == sorted(active)
    assert [int(row[0]) for row in rows] == list(range(1, len(rows) + 1))


def test_commit_history_matches_rollbacks(scenario) -> None:
    entries = [x for x in scenario["artifacts/commits.txt"].splitlines() if x[:1].isdigit()]
    rollbacks = [p for p in scenario if p.startswith("artifacts/rollbacks/")]
    assert len(entries) == len(rollbacks) + 1
    assert len(entries) <= 50


def test_log_lines_name_known_policies(scenario) -> None:
    names = set(re.findall(r'policy-name="([^"]+)"', scenario["artifacts/logs/rt_flow.log"]))
    known = set()
    for path, text in scenario.items():
        if path.endswith(".set"):
            known |= {key[2] for key in config_policies(text)}
    assert names <= known


def test_verdicts_follow_live_status(scenario) -> None:
    for rule in json.loads(scenario["ground_truth.json"])["rules"]:
        expected = rule["expected"]
        if rule["status"]["live"]:
            # A load-bearing emergency rule is needed but must be replaced.
            emergency = "TRAP-EMERGENCY-LOADBEARING" in rule["traps"]
            assert expected["verdict"] == ("verify" if emergency else "keep"), rule["key"]
            assert expected["best_achievable_verdict"] != "removal_candidate", rule["key"]
        else:
            assert expected["verdict"] == "removal_candidate", rule["key"]


def test_easy_has_no_traps(scenario) -> None:
    truth = json.loads(scenario["ground_truth.json"])
    if truth["level"] == "easy":
        assert all(not r["traps"] for r in truth["rules"])


def test_manifest_hashes_match_files(scenario) -> None:
    import hashlib

    manifest = json.loads(scenario["manifest.json"])
    for path, digest in manifest["files"].items():
        assert hashlib.sha256(scenario[path].encode("utf-8")).hexdigest() == digest
    assert set(manifest["files"]) == set(scenario) - {"manifest.json"}
