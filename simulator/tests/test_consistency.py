"""Internal consistency between artifacts and ground truth."""

import json
import re

import pytest

from palimp_sim.generate import generate

POLICY = re.compile(r"^set security policies from-zone (\S+) to-zone (\S+) policy (\S+) ")
SEEDS = [0, 1, 2, 3, 4, 5]


def config_policies(text: str) -> list[tuple[str, str, str]]:
    keys = []
    for line in text.splitlines():
        match = POLICY.match(line)
        if match and match.groups() not in keys:
            keys.append(match.groups())
    return keys


@pytest.fixture(scope="module", params=SEEDS)
def scenario(request) -> dict[str, str]:
    return {path: data.decode("utf-8") for path, data in generate("easy", request.param).items()}


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


def test_hitcount_lists_every_policy(scenario) -> None:
    rows = scenario["artifacts/hitcount.txt"].splitlines()[2:]
    names = [row.split()[3] for row in rows]
    assert names == [key[2] for key in config_policies(scenario["artifacts/config.set"])]


def test_commit_history_matches_rollbacks(scenario) -> None:
    entries = [x for x in scenario["artifacts/commits.txt"].splitlines() if x[:1] != " "]
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


def test_live_rules_are_kept_and_dead_rules_have_no_recent_hits(scenario) -> None:
    for rule in json.loads(scenario["ground_truth.json"])["rules"]:
        if rule["status"]["live"]:
            assert rule["expected"]["verdict"] == "keep"
        else:
            assert rule["expected"]["verdict"] == "removal_candidate"


def test_easy_has_no_traps(scenario) -> None:
    assert all(not r["traps"] for r in json.loads(scenario["ground_truth.json"])["rules"])


def test_manifest_hashes_match_files(scenario) -> None:
    import hashlib

    manifest = json.loads(scenario["manifest.json"])
    for path, digest in manifest["files"].items():
        assert hashlib.sha256(scenario[path].encode("utf-8")).hexdigest() == digest
    assert set(manifest["files"]) == set(scenario) - {"manifest.json"}
