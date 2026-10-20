"""Best achievable intent, rule kinds, shadowed rules and `ANY` sets (decision 0047)."""

import ipaddress
import json
import re

import pytest

from palimp_sim.generate import generate

FIREWALL_KINDS = {"block", "cleanup_deny", "broad_permit", "factory_default"}
SCENARIOS = [("easy", 0), ("easy", 1), ("medium", 0), ("medium", 20), ("hard", 1)]
# Seeds measured in session 32 (set format): each holds a shadowed rule.
SHADOWED = [("medium", 0), ("medium", 5), ("hard", 1), ("hard", 12)]
# Seeds with an address set named like the `any` keyword (one per format).
ANY_SETS = [("medium", 20), ("hard", 0)]
ANY_SOURCE = re.compile(r"source-address (?:\[ )?(ANY|Any-Hosts)\b")


def files(level: str, seed: int) -> dict[str, str]:
    return {path: data.decode("utf-8") for path, data in generate(level, seed).items()}


def truth_of(level: str, seed: int) -> dict:
    return json.loads(files(level, seed)["ground_truth.json"])


@pytest.mark.parametrize(("level", "seed"), SCENARIOS)
def test_every_rule_has_a_kind_and_a_best_achievable_intent(level: str, seed: int) -> None:
    truth = truth_of(level, seed)
    for rule in truth["rules"]:
        expected = rule["expected"]
        kind, best = expected["rule_kind"], expected["best_achievable_intent"]
        if rule["intent"]["kind"] in FIREWALL_KINDS:
            # Read from the rule's structure: no application to name.
            assert kind == rule["intent"]["kind"], rule["key"]
            assert best is None, rule["key"]
            continue
        assert kind == "application", rule["key"]
        if best not in (None, rule["intent"]["app_id"]):
            # Only a stale name no artifact reveals names another application.
            assert level == "hard" and "TRAP-STALE-NAME" in rule["traps"], rule["key"]
    if level == "easy":
        # Every Easy object starts with its application's name.
        assert all(r["expected"]["best_achievable_intent"] for r in truth["rules"])


@pytest.mark.parametrize("level", ["medium", "hard"])
def test_some_application_rules_have_no_best_achievable_intent(level: str) -> None:
    rules = [r for r in truth_of(level, 0)["rules"] if r["expected"]["rule_kind"] == "application"]
    unknown = [r for r in rules if r["expected"]["best_achievable_intent"] is None]
    assert 0.1 < len(unknown) / len(rules) < 0.6


def set_lines(config: str, rule: dict) -> list[int]:
    key = rule["key"]
    prefix = (
        f"set security policies from-zone {key['from_zone']} to-zone {key['to_zone']} "
        f"policy {key['name']} "
    )
    return [i for i, line in enumerate(config.splitlines()) if line.startswith(prefix)]


@pytest.mark.parametrize(("level", "seed"), SHADOWED)
def test_shadowed_rule_comes_after_the_catch_all_deny(level: str, seed: int) -> None:
    scenario = files(level, seed)
    truth = json.loads(scenario["ground_truth.json"])
    config = scenario["artifacts/config.set"]
    shadowed = [r for r in truth["rules"] if "TRAP-SHADOWED-BY-DENY" in r["traps"]]
    assert shadowed
    for rule in shadowed:
        pair = (rule["key"]["from_zone"], rule["key"]["to_zone"])
        denies = [
            r
            for r in truth["rules"]
            if r["intent"]["kind"] == "cleanup_deny"
            and (r["key"]["from_zone"], r["key"]["to_zone"]) == pair
        ]
        assert len(denies) == 1, rule["key"]
        assert min(set_lines(config, rule)) > max(set_lines(config, denies[0]))
        expected, status = rule["expected"], rule["status"]
        assert expected["best_achievable_verdict"] == "verify"
        assert expected["owner_to_ask"] == "firewall_team"
        assert expected["rule_kind"] == "application"
        assert not status["live"] and status["hits_in_window"] == 0
        # Wanted while its flow still tries: never a removal then.
        wanted = "verify" if status["still_needed"] else "removal_candidate"
        assert expected["verdict"] == wanted
        assert any("after catch-all deny" in e["locator"] for e in rule["evidence"])


@pytest.mark.parametrize(("level", "seed"), ANY_SETS)
def test_any_set_holds_specific_addresses(level: str, seed: int) -> None:
    scenario = files(level, seed)
    truth = json.loads(scenario["ground_truth.json"])
    objects = {o["name"]: o for o in truth["objects"]}
    sets = [o for name, o in objects.items() if name in ("ANY", "Any-Hosts")]
    assert len(sets) == 1 and sets[0]["kind"] == "address_set"
    for member in sets[0]["value"].split():
        network = ipaddress.ip_network(objects[member]["value"])
        assert network.prefixlen >= 8  # a site subnet, never 0.0.0.0/0
    assert ANY_SOURCE.search(scenario["artifacts/config.set"])
