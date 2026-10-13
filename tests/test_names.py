"""Name filters, server roles and the corroboration rule (decision 0042). Invented names."""

from palimp.apps import (
    GENERIC_WORDS,
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
set security applications application kelvo-tcp protocol tcp
set security applications application kelvo-tcp destination-port 7400
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


def test_both_sides_or_an_application_name_corroborate() -> None:
    rules = policy("p1", "zorvex-app-01", "zorvex-db-01")
    rules += policy("p2", "any", "kelvo-01", "kelvo-tcp")
    assert confidence(rules, "p1")[:3] == ("MEDIUM", "C-T3", ["zorvex"])
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
