"""Name filters, server roles and the corroboration rule (decision 0042). Invented names."""

from palimp.apps import (
    GENERIC_WORDS,
    PRODUCTS,
    ROLE_WORDS,
    SERVER_ROLES,
    not_an_application,
    roles,
    vocabulary,
)
from palimp.evidence import collect
from palimp.formats.junos_set import parse_set
from palimp.models import Dataset, PolicyKey, Ticket
from palimp.report import intent

ADDRESSES = """\
set security address-book global address addr-zorvex-01 10.1.0.1/32
set security address-book global address zorvex-app-01 10.1.0.2/32
set security address-book global address zorvex-db-01 10.1.0.3/32
set security address-book global address dmz-web-01 10.1.0.4/32
set security address-book global address local-net 10.1.0.0/24
set security address-book global address en-qplat-02 10.1.0.5/32
set security address-book global address dan-pc-07 10.1.0.6/32
set security address-book global address kelvo-01 10.1.0.7/32
set security address-book global address sql-node-1 10.1.0.8/32
set security address-book global address sql-node-2 10.1.0.9/32
set security address-book global address vpn-gw-01 10.1.0.10/32
set applications application kelvo-tcp protocol tcp
set applications application kelvo-tcp destination-port 7400
"""


def policy(name: str, source: str, destination: str, application: str = "any") -> str:
    head = f"set security policies from-zone a to-zone b policy {name}"
    return (
        f"{head} match source-address {source}\n"
        f"{head} match destination-address {destination}\n"
        f"{head} match application {application}\n"
        f"{head} then permit\n"
    )


def dataset(rules: str, tickets: dict | None = None) -> Dataset:
    return Dataset(source="t", config=parse_set(ADDRESSES + rules), tickets=tickets or {})


def test_generic_words_are_one_documented_list() -> None:
    asked = "addr net host main dmz local remote prod dev lan wan inside outside trust untrust"
    asked += " all any group range client vpn bad"
    assert all(not_an_application(w) for w in asked.split())
    assert all(w == w.lower() and w.isalnum() for w in GENERIC_WORDS)
    assert not GENERIC_WORDS & set(SERVER_ROLES), "a word is either generic or a role"
    assert not ROLE_WORDS & set(SERVER_ROLES)
    for word in ("sql", "db", "web", "jump", "proxy", "dns", "mail", "backup"):
        assert word in SERVER_ROLES and not_an_application(word)
    assert not_an_application("en") and not_an_application("ab")  # shorter than 3
    assert not not_an_application("zorvex")


def test_object_names_skip_generic_short_and_role_words() -> None:
    vocab = vocabulary(dataset(""))
    assert "zorvex" in vocab.names and "kelvo" in vocab.names
    for word in ("addr", "dmz", "local", "en", "sql", "vpn"):
        assert word not in vocab.names
    assert vocab.in_object("addr-zorvex-01") == ["zorvex"]
    assert vocab.in_object("en-qplat-02") == []
    assert vocab.in_text("open dmz access for zorvex") == ["zorvex"]


def test_a_ticket_keeps_a_short_or_generic_name() -> None:
    tickets = {"CHG1": Ticket(ticket_id="CHG1", summary="VPN change", related_ci="vpn")}
    vocab = vocabulary(dataset("", tickets))
    assert vocab.in_object("vpn-gw-01") == ["vpn"]


def confidence(rules: str, name: str) -> tuple[str, str, list[str], str]:
    found = collect(dataset(rules), PolicyKey.parse(f"a/b/{name}"))
    a = found.assessment
    return a.confidence, a.confidence_rule, a.intent_apps, a.verdict


def test_a_name_on_one_side_only_stays_low() -> None:
    rules = policy("p1", "any", "dan-pc-07") + policy("p2", "any", "zorvex-db-01")
    assert confidence(rules, "p1")[:3] == ("LOW", "C-T3-SINGLE", ["dan"])
    assert confidence(rules, "p2")[:3] == ("LOW", "C-T3-SINGLE", ["zorvex"])


def test_an_application_name_corroborates_both_sides_do_not() -> None:
    # Decision 0043: the same name on both sides is one naming convention, not two
    # independent sources.
    rules = policy("p1", "zorvex-app-01", "zorvex-db-01")
    rules += policy("p2", "any", "kelvo-01", "kelvo-tcp")
    assert confidence(rules, "p1")[:3] == ("LOW", "C-T3-SINGLE", ["zorvex"])
    assert confidence(rules, "p2")[:3] == ("MEDIUM", "C-T3", ["kelvo"])


def test_corroboration_never_changes_the_verdict() -> None:
    rules = policy("p1", "any", "dan-pc-07") + policy("p2", "zorvex-app-01", "zorvex-db-01")
    assert confidence(rules, "p1")[3] == confidence(rules, "p2")[3] == "verify"


def test_server_roles_describe_the_flow_without_an_application() -> None:
    assert roles("sql01-a") == ["SQL"]
    assert roles("web-printers-02") == ["web", "print"]
    found = collect(
        dataset(policy("p1", "sql-node-1", "sql-node-2", "junos-smb")), PolicyKey.parse("a/b/p1")
    )
    a = found.assessment
    assert a.intent_apps == [] and a.confidence == "LOW"
    assert a.intent_flow == "SMB file sharing between SQL servers"
    assert intent(found).text.startswith("Probably SMB file sharing between SQL servers")


def test_policy_name_is_t3_evidence_and_corroborates() -> None:
    rules = policy("allow-zorvex-dmz", "any", "zorvex-db-01")
    rules += policy("dmz-local-01", "any", "dan-pc-07")
    found = collect(dataset(rules), PolicyKey.parse("a/b/allow-zorvex-dmz"))
    item = next(e for e in found.evidence if e.kind == "policy_name")
    assert item.tier == "T3" and item.apps == ["zorvex"]
    assert (found.assessment.confidence, found.assessment.confidence_rule) == ("MEDIUM", "C-T3")
    assert "the policy name" in found.assessment.confidence_reason
    plain = collect(dataset(rules), PolicyKey.parse("a/b/dmz-local-01"))
    assert not [e for e in plain.evidence if e.kind == "policy_name"]  # generic words only


def test_policy_name_alone_stays_low() -> None:
    found = collect(dataset(policy("to-kelvo", "any", "any")), PolicyKey.parse("a/b/to-kelvo"))
    assert found.assessment.intent_apps == ["kelvo"]
    assert found.assessment.confidence_rule == "C-T3-SINGLE"


def test_dynamic_application_names_the_application() -> None:
    head = "set security policies from-zone a to-zone b policy"
    rules = (
        f"{head} chat match source-address any\n"
        f"{head} chat match destination-address any\n"
        f"{head} chat match application junos-defaults\n"
        f"{head} chat match dynamic-application [junos:QUIBBLE, junos:web:shopping]\n"
        f"{head} chat then permit\n"
    )
    found = collect(dataset(rules), PolicyKey.parse("a/b/chat"))
    item = next(e for e in found.evidence if e.kind == "dynamic_application")
    assert item.tier == "T3" and item.apps == ["quibble"]  # a group names no application
    assert "junos:QUIBBLE, junos:web:shopping" in item.claim
    assert found.assessment.intent_apps == ["quibble"]
    # Decision 0043: the rule's own match criterion gives MEDIUM alone, never HIGH.
    assert found.assessment.confidence == "MEDIUM"
    assert found.assessment.confidence_rule == "C-DYNAMIC-APP"
    services = next(e for e in found.evidence if e.kind == "services")
    assert "default ports of the dynamic applications" in services.claim


def test_long_lists_show_five_and_a_count() -> None:
    members = "".join(
        f"set security address-book global address-set zorvex-farm address zorvex-db-0{i}\n"
        for i in range(1, 8)
    )
    apps = "".join(
        f"set applications application-set wide application svc-{i}\n"
        f"set applications application svc-{i} protocol tcp\n"
        f"set applications application svc-{i} destination-port {7000 + i}\n"
        for i in range(1, 9)
    )
    rules = members + apps + policy("p1", "zorvex-app-01", "zorvex-farm", "wide")
    found = collect(dataset(rules), PolicyKey.parse("a/b/p1"))
    objects = next(e for e in found.evidence if e.kind == "address_objects")
    assert "zorvex-db-05, and 2 more}" in objects.claim
    services = next(e for e in found.evidence if e.kind == "services")
    assert services.claim.count("svc-") == 5 and services.claim.endswith("; and 3 more")


def test_a_policy_name_repeating_an_object_name_is_not_independent() -> None:
    rules = policy("Zorvex-DB_to_any", "any", "zorvex-db-01")
    found = collect(dataset(rules), PolicyKey.parse("a/b/Zorvex-DB_to_any"))
    assert not [e for e in found.evidence if e.kind == "policy_name"]
    assert found.assessment.confidence_rule == "C-T3-SINGLE"


def test_zone_name_words_are_not_applications() -> None:
    head = "set security policies from-zone Quarry_7 to-zone b policy"
    rules = (
        "set security address-book global address Quarry_7_Clients 10.2.0.0/24\n"
        f"{head} q1 match source-address Quarry_7_Clients\n"
        f"{head} q1 match destination-address any\n"
        f"{head} q1 match application any\n"
        f"{head} q1 then permit\n"
    )
    found = collect(dataset(rules), PolicyKey.parse("Quarry_7/b/q1"))
    assert found.assessment.intent_apps == []
    assert "quarry" in vocabulary(dataset(rules)).zone_words


def test_a_product_name_is_an_application_even_in_a_zone_name() -> None:
    # Session 28 (review-2): the zone, the policy name and the application set all say
    # redis. A product is not a server role and not a zone word.
    head = "set security policies from-zone REDIS-QX-PRIV to-zone b policy QX-WITNESS-REDIS-PFS"
    rules = (
        "set security address-book global address en-qxa1red002 10.3.0.1/32\n"
        "set security address-book global address en-qxb1red001 10.3.0.2/32\n"
        "set applications application TCP-3333 protocol tcp\n"
        "set applications application TCP-3333 destination-port 3333\n"
        "set applications application-set REDIS application TCP-3333\n"
        f"{head} match source-address en-qxa1red002\n"
        f"{head} match destination-address en-qxb1red001\n"
        f"{head} match application REDIS\n"
        f"{head} then permit\n"
    )
    assert "redis" in PRODUCTS and "redis" not in SERVER_ROLES
    assert not not_an_application("redis")
    found = collect(dataset(rules), PolicyKey.parse("REDIS-QX-PRIV/b/QX-WITNESS-REDIS-PFS"))
    a = found.assessment
    assert a.intent_apps == ["redis"]
    assert (a.confidence, a.confidence_rule) == ("MEDIUM", "C-T3")
    assert "the policy name" in a.confidence_reason
    assert "a custom application name" in a.confidence_reason
    # tcp is a generic word: TCP-3333 names nothing.
    assert "tcp" not in vocabulary(dataset(rules)).names


def test_application_names_are_learned_like_object_names() -> None:
    rules = (
        "set applications application QUORLAN-PORTS protocol tcp\n"
        "set applications application QUORLAN-PORTS destination-port 7710\n"
        + policy("p1", "any", "any", "QUORLAN-PORTS")
    )
    vocab = vocabulary(dataset(rules))
    assert "quorlan" in vocab.names
    found = collect(dataset(rules), PolicyKey.parse("a/b/p1"))
    assert found.assessment.intent_apps == ["quorlan"]
    assert found.assessment.confidence_rule == "C-T3-SINGLE"


def test_a_product_in_free_text_is_read_as_before() -> None:
    vocab = vocabulary(dataset(""))
    assert vocab.in_text("pushed by ansible") == []
    assert vocab.in_object("ansible-ctl-01") == ["ansible"]


def test_a_product_port_and_a_product_name_are_two_sources() -> None:
    # Decision 0043: tcp/8834 is known for nessus; an object naming nessus is a second
    # source. The port alone names nothing.
    rules = (
        "set security address-book global address scan-nessus-01 10.4.0.1/32\n"
        "set applications application quill-8834 protocol tcp\n"
        "set applications application quill-8834 destination-port 8834\n"
        + policy("p1", "any", "scan-nessus-01", "quill-8834")
        + policy("p2", "any", "any", "quill-8834")
    )
    found = collect(dataset(rules), PolicyKey.parse("a/b/p1"))
    services = next(e for e in found.evidence if e.kind == "services")
    assert services.port_apps == ["nessus"]
    a = found.assessment
    assert a.intent_apps[0] == "nessus"
    assert (a.confidence, a.confidence_rule) == ("MEDIUM", "C-T3")
    assert "a well-known port" in a.confidence_reason
    alone = collect(dataset(rules), PolicyKey.parse("a/b/p2")).assessment
    assert "nessus" not in alone.intent_apps


def test_a_server_role_matching_the_service_names_it() -> None:
    # A dns object on udp/53 and an ntp object on udp/123: two sources each.
    rules = (
        "set security address-book global address dns-01 10.4.0.2/32\n"
        "set security address-book global address ntp-02 10.4.0.3/32\n"
        + policy("p1", "any", "dns-01", "junos-dns-udp")
        + policy("p2", "any", "ntp-02", "junos-ntp")
        + policy("p3", "any", "ntp-02", "junos-dns-udp")
    )
    for name, app in (("p1", "dns"), ("p2", "ntp")):
        a = collect(dataset(rules), PolicyKey.parse(f"a/b/{name}")).assessment
        assert a.intent_apps == [app]
        assert (a.confidence, a.confidence_rule) == ("MEDIUM", "C-T3")
    # A role that does not offer the service names nothing.
    a = collect(dataset(rules), PolicyKey.parse("a/b/p3")).assessment
    assert a.intent_apps == [] and a.confidence == "LOW"


def test_a_two_letter_name_needs_a_second_source() -> None:
    # Decision 0043: `qx` alone names nothing; the object and the policy name together
    # name it (MEDIUM). Both sides of the rule are one source.
    rules = (
        "set security address-book global address qx-web-01 10.5.0.1/32\n"
        "set security address-book global address qx-db-01 10.5.0.2/32\n"
        + policy("p1", "any", "qx-web-01")
        + policy("p2", "qx-web-01", "qx-db-01")
        + policy("allow-qx-reports", "any", "qx-web-01")
    )
    assert "qx" in vocabulary(dataset(rules)).short
    for name in ("p1", "p2"):
        a = collect(dataset(rules), PolicyKey.parse(f"a/b/{name}")).assessment
        assert "qx" not in a.intent_apps and a.confidence == "LOW"
    a = collect(dataset(rules), PolicyKey.parse("a/b/allow-qx-reports")).assessment
    assert a.intent_apps == ["qx"]
    assert (a.confidence, a.confidence_rule) == ("MEDIUM", "C-T3")


def test_a_flow_is_described_when_nothing_names_an_application() -> None:
    # Decision 0043: "SNMP traps from the management range" rather than "Purpose
    # unknown", still LOW.
    rules = (
        "set security address-book global address mgmt-range-7 10.6.0.0/24\n"
        + policy("p1", "mgmt-range-7", "any", "junos-snmp-trap")
        + policy("p2", "any", "any", "any")
    )
    found = collect(dataset(rules), PolicyKey.parse("a/b/p1"))
    a = found.assessment
    assert a.intent_apps == [] and a.confidence == "LOW"
    assert a.intent_flow == "SNMP traps from the management range to anywhere in zone b"
    assert intent(found).text.startswith("Probably SNMP traps from the management range")
    # Nothing to describe: no service, no role.
    assert collect(dataset(rules), PolicyKey.parse("a/b/p2")).assessment.intent_flow is None
