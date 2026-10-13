from palimp.formats.junos_set import parse_set, tokenize

CONFIG = """\
set version 21.4R3-S4
set system host-name fw-test
set security policies from-zone trust to-zone dc policy web-in description "CRM front end, req AB"
set security policies from-zone trust to-zone dc policy web-in match source-address lan
set security policies from-zone trust to-zone dc policy web-in match destination-address crm-web
set security policies from-zone trust to-zone dc policy web-in match application junos-https
set security policies from-zone trust to-zone dc policy web-in then permit
set security policies from-zone trust to-zone dc policy web-in then log session-close
set security policies from-zone trust to-zone dc policy old-ftp match source-address any
set security policies from-zone trust to-zone dc policy old-ftp match destination-address any
set security policies from-zone trust to-zone dc policy old-ftp match application tcp-21
set security policies from-zone trust to-zone dc policy old-ftp then permit
deactivate security policies from-zone trust to-zone dc policy old-ftp
set security policies default-policy deny-all
set security address-book global address crm-web 10.20.1.10/32
set security address-book global address lan-a 10.10.1.0/24
set security address-book global address-set lan address lan-a
set security zones security-zone dc address-book address zone-host 10.20.9.9/32
set security zones security-zone dc interfaces ge-0/0/3.0
set applications application tcp-21 protocol tcp
set applications application tcp-21 destination-port 21
this is not junos
set security policies from-zone trust to-zone dc policy web-in frobnicate
set security unknown-thing x
"""


def test_tokenize_keeps_quoted_strings() -> None:
    assert tokenize('set a description "x y z" b') == ["set", "a", "description", "x y z", "b"]


def test_policies_parsed_in_order() -> None:
    config = parse_set(CONFIG)
    assert [p.name for p in config.policies] == ["web-in", "old-ftp"]
    web = config.policies[0]
    assert web.description == "CRM front end, req AB"
    assert web.sources == ["lan"] and web.destinations == ["crm-web"]
    assert web.applications == ["junos-https"]
    assert web.action == "permit" and web.log_close and not web.log_init


def test_deactivate_marks_policy() -> None:
    config = parse_set(CONFIG)
    assert config.policies[1].deactivated
    assert not config.policies[0].deactivated


def test_address_book_and_applications() -> None:
    config = parse_set(CONFIG)
    assert config.addresses["crm-web"].value == "10.20.1.10/32"
    assert config.addresses["lan"].members == ["lan-a"]
    assert config.addresses["zone-host"].book == "dc"
    assert config.applications["tcp-21"].destination_port == "21"


def test_unknown_lines_are_counted_not_fatal() -> None:
    stats = parse_set(CONFIG).stats
    assert stats.unknown == 3
    assert "this is not junos" in stats.unknown_samples
    assert stats.total == stats.parsed + stats.ignored + stats.unknown


def test_application_set_inside_an_application_set() -> None:
    # Junos lets an application-set list other application-sets.
    config = parse_set(
        "set applications application-set web-ports application junos-http\n"
        "set applications application-set web-ports application junos-https\n"
        "set applications application-set all-ports application-set web-ports\n"
        "set applications application-set all-ports application junos-ssh\n"
    )
    assert config.stats.unknown == 0
    assert config.applications["all-ports"].members == ["web-ports", "junos-ssh"]


def test_tenant_and_logical_system_policies_are_stated_not_read() -> None:
    # Out of v1 scope: their policies are not modeled, and the reader says so.
    config = parse_set(
        "set tenants t1 security policies from-zone a to-zone b policy p match application any\n"
        "set tenants t1 interfaces ge-0/0/1 unit 0\n"
        "set logical-systems ls2 security policies from-zone a to-zone b policy q then permit\n"
        "set security policies from-zone a to-zone b policy r then permit\n"
    )
    assert config.stats.unknown == 0
    assert config.stats.not_read == ["tenants t1", "logical-systems ls2"]
    assert [p.name for p in config.policies] == ["r"]
