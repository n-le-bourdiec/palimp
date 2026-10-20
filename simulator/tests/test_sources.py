"""Naming sources and the confidence they justify (spec 6.1, decision 0045)."""

import json

import pytest

from palimp_sim.generate import generate
from palimp_sim.sources import confidence, copies_object, counted, names, rule_sources


def sources(app="crm", objects=(), name="rule-47", services=("junos-https",), texts=(), **kw):
    return rule_sources(
        app,
        list(objects),
        name,
        list(services),
        list(texts),
        kw.get("comment"),
        list(kw.get("tickets", ())),
    )


def test_names_by_id_code_and_trailing_number() -> None:
    assert names("crm-web-01", "crm") == "full"
    assert names("EG-CRM-SQL01", "crm") == "full"
    assert names("ESHOP01", "webshop") == "full"  # the application code
    assert names("erp-de-app-01", "erp-de") == "full"
    assert names("erp-app-01", "erp-de") is None  # another instance
    assert names("EG-SQL01", "crm") is None
    assert names("CI-Builds", "ci") == "short"
    assert names("Allow-MX", "mail") == "short"


def test_one_source_is_low() -> None:
    assert confidence(sources(objects=["crm-web-01"]), traffic=True) == "LOW"


def test_both_sides_and_a_shared_prefix_are_one_source() -> None:
    found = sources(objects=["crm-web-01", "crm-app-01"])
    assert [s.kind for s in found] == ["objects"]
    assert confidence(found, traffic=True) == "LOW"


def test_policy_name_copied_from_an_object_is_not_independent() -> None:
    assert copies_object("users-to-crm-web", ["crm-web-01"])
    assert copies_object("Allow-EG-CRM-SQL01", ["EG-CRM-SQL01"])
    assert not copies_object("CRM-HTTPS", ["crm-web-01"])
    assert confidence(sources(objects=["crm-web-01"], name="users-to-crm-web"), True) == "LOW"
    assert confidence(sources(objects=["crm-web-01"], name="CRM-HTTPS"), True) == "MEDIUM"


def test_two_letter_names_need_a_source_that_is_not_a_name() -> None:
    found = sources(app="ci", objects=["ci-app-01"], name="CI-access")
    assert counted(found) == []
    assert confidence(found, traffic=True) == "LOW"
    found = sources(app="ci", objects=["ci-app-01"], texts=["CI - 443 from LAN"])
    assert confidence(found, traffic=False) == "MEDIUM"


def test_a_service_port_is_a_second_source_only() -> None:
    assert confidence(sources(app="vault", services=["tcp-8200"]), True) == "LOW"
    found = sources(app="vault", objects=["vault-app-01"], services=["tcp-8200"])
    assert confidence(found, traffic=True) == "MEDIUM"  # no direct statement


def test_high_needs_traffic_and_a_direct_statement() -> None:
    found = sources(objects=["EG-SQL01"], texts=["CRM - 443 from LAN"], comment="CRM go-live")
    assert confidence(found, traffic=False) == "MEDIUM"
    assert confidence(found, traffic=True) == "HIGH"
    found = sources(objects=["crm-web-01"], name="CHG0012345", tickets=["crm"])
    assert confidence(found, traffic=True) == "HIGH"
    found = sources(objects=["crm-web-01"], name="CRM-HTTPS")
    assert confidence(found, traffic=True) == "MEDIUM"


@pytest.mark.parametrize("level", ["medium", "hard"])
def test_ground_truth_spreads_over_every_confidence_level(level: str) -> None:
    truth = json.loads(generate(level, 0)["ground_truth.json"])
    seen = {r["expected"]["max_justified_confidence"] for r in truth["rules"]}
    assert seen == {"LOW", "MEDIUM", "HIGH"}
