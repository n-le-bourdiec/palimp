"""Hierarchical (curly-brace) configuration reader (decision 0032).

Fixture tests read samples copied from Juniper documentation pages
(tests/fixtures/junos_docs/hier_*.txt, decision 0013). The documentation
shows no security policy with a description, an annotation or `inactive:`,
so the inline samples below put those constructs, as the documentation
shows them on other statements, on a policy. They say so.
"""

from pathlib import Path

from palimp.formats.junos_config import detect_format, parse_config
from palimp.formats.junos_hier import parse_hierarchical, statements
from palimp.formats.junos_set import parse_set

FIXTURES = Path(__file__).parent / "fixtures" / "junos_docs"


def body(name: str) -> str:
    lines = (FIXTURES / name).read_text(encoding="utf-8").splitlines()
    return "\n".join(lines[lines.index("# ---") + 1 :]) + "\n"


def keys(config) -> list[str]:
    return [str(p.key) for p in config.policies]


# Documentation fixtures


def test_every_fixture_detected_as_hierarchical() -> None:
    for path in sorted(FIXTURES.glob("hier_*.txt")):
        assert detect_format(body(path.name)) == "hierarchical", path.name


def test_show_security_policies_relative_to_edit_level() -> None:
    config = parse_config(body("hier_show_security_policies.txt"))
    assert config.stats.format == "hierarchical"
    assert config.stats.unknown == 0
    assert keys(config) == ["trust/untrust/permit-all", "untrust/trust/deny-all"]
    permit, deny = config.policies
    assert (permit.sources, permit.destinations, permit.applications) == (["any"], ["any"], ["any"])
    assert (permit.action, deny.action) == ("permit", "deny")


def test_show_policies_of_one_zone_pair_and_one_zone() -> None:
    config = parse_config(body("hier_zone_relative_show.txt"))
    assert config.stats.unknown == 0
    assert keys(config) == ["trust/DMZ/permit-mail-trust-DMZ", "DMZ/DMZ/permit-http-in-DMZ"]
    assert config.policies[0].destinations == ["Server-SMTP"]
    assert config.policies[0].applications == ["junos-smtp"]
    book = config.addresses
    assert book["Server-SMTP"].value == "192.168.2.4/24" and book["Server-SMTP"].book == "DMZ"
    assert book["DMZ-address-set-http"].members == ["Server-HTTP-1", "Server-HTTP-2"]


def test_named_address_books_with_attach() -> None:
    config = parse_config(body("hier_address_book_attach.txt"))
    assert config.stats.unknown == 0
    assert config.policies[0].sources == ["mail-trust"]
    assert config.addresses["mail-untrust"].value == "203.0.113.14/24"
    assert config.addresses["mail-trust"].book == "book2"


def test_address_sets_and_container_form_address() -> None:
    config = parse_config(body("hier_address_book_sets_dns.txt"))
    assert config.stats.unknown == 0
    assert config.addresses["sw-eng"].members == ["a1", "a2"]
    assert config.addresses["Intranet"].value == "dns-name www-int.device1.example.com"
    assert config.addresses["g1"].book == "global"


def test_log_and_prompt_without_space() -> None:
    config = parse_config(body("hier_policy_log_prompt_nospace.txt"))
    assert config.stats.unknown == 0
    (policy,) = config.policies
    assert str(policy.key) == "tap-zone/tap-zone/tap-policy"
    assert policy.action == "permit" and policy.log_init and policy.log_close


def test_applications() -> None:
    config = parse_config(body("hier_applications.txt"))
    assert config.stats.unknown == 0
    app = config.applications["src_2123"]
    assert (app.protocol, app.destination_port) == ("udp", "0-0")


def test_annotations_attach_to_the_next_statement() -> None:
    found = [s for s in statements(body("hier_annotations.txt")) if s.kind == "annotate"]
    shown = [(" ".join(s.path), s.text) for s in found]
    assert (
        "protocols ospf area 0.0.0.0",
        "Backbone area configuration added June 15, 1998",
    ) in shown
    assert (
        "protocols ospf area 0.0.0.0 interface so-0/0/0",
        "Interface from router sj1 to router sj2",
    ) in shown
    assert ("routing-options", "This comment goes with routing-options") in shown
    assert (
        "routing-options traceoptions traceflag task",
        "This comment goes with routing-options traceoptions traceflag task",
    ) in shown
    # The page says these are dropped: after a statement, or before a closing brace.
    assert not any("dropped" in text for _, text in shown)
    assert parse_config(body("hier_annotations.txt")).stats.unknown == 0


def test_inactive_prefix_is_deactivate() -> None:
    found = [s for s in statements(body("hier_inactive.txt")) if s.kind == "deactivate"]
    assert [s.path[-1] for s in found] == ["at-5/2/0"]
    assert parse_config(body("hier_inactive.txt")).stats.unknown == 0


# Inline samples (constructs from the documentation, put on a policy)

POLICY = """\
## Last commit: 2026-01-12 09:30:00 UTC by alice
version 21.4R3;
security {
    address-book {
        global {
            address web-01 192.0.2.10/32;
            address-set web-farm {
                address web-01;
            }
        }
    }
    policies {
        from-zone trust to-zone dmz {
            /* opened for the billing migration, ask Jane (CHG-20431) */
            policy allow-billing {
                description "Billing app; CHG-20431 {temp}";
                match {
                    source-address [ any-a any-b ];
                    destination-address web-farm;
                    application [ junos-https junos-http ];
                }
                then {
                    permit;
                    log {
                        session-close;
                    }
                }
            }
            inactive: policy old-ftp {
                match {
                    source-address any;
                    destination-address web-01;
                    application junos-ftp;
                }
                then {
                    permit;
                }
            }
            policy partial {
                match {
                    source-address any;
                    inactive: destination-address web-01;
                    application junos-ssh;
                }
                then {
                    deny;
                }
            }
        }
    }
}
applications {
    application tcp-8443 {
        protocol tcp;
        destination-port 8443;
    }
}
"""

SAME_AS_SET = """\
set security address-book global address web-01 192.0.2.10/32
set security address-book global address-set web-farm address web-01
set security policies from-zone trust to-zone dmz policy allow-billing description "Billing app; CHG-20431 {temp}"
set security policies from-zone trust to-zone dmz policy allow-billing match source-address any-a
set security policies from-zone trust to-zone dmz policy allow-billing match source-address any-b
set security policies from-zone trust to-zone dmz policy allow-billing match destination-address web-farm
set security policies from-zone trust to-zone dmz policy allow-billing match application junos-https
set security policies from-zone trust to-zone dmz policy allow-billing match application junos-http
set security policies from-zone trust to-zone dmz policy allow-billing then permit
set security policies from-zone trust to-zone dmz policy allow-billing then log session-close
set security policies from-zone trust to-zone dmz policy old-ftp match source-address any
set security policies from-zone trust to-zone dmz policy old-ftp match destination-address web-01
set security policies from-zone trust to-zone dmz policy old-ftp match application junos-ftp
set security policies from-zone trust to-zone dmz policy old-ftp then permit
deactivate security policies from-zone trust to-zone dmz policy old-ftp
set security policies from-zone trust to-zone dmz policy partial match source-address any
set security policies from-zone trust to-zone dmz policy partial match destination-address web-01
deactivate security policies from-zone trust to-zone dmz policy partial match destination-address web-01
set security policies from-zone trust to-zone dmz policy partial match application junos-ssh
set security policies from-zone trust to-zone dmz policy partial then deny
set applications application tcp-8443 protocol tcp
set applications application tcp-8443 destination-port 8443
"""  # noqa: E501


def test_same_model_as_set_format() -> None:
    hier = parse_config(POLICY)
    flat = parse_config(SAME_AS_SET)
    assert (hier.stats.format, flat.stats.format) == ("hierarchical", "set")
    assert hier.stats.unknown == 0 and flat.stats.unknown == 0
    without = [p.model_copy(update={"annotations": []}) for p in hier.policies]
    assert without == flat.policies
    assert hier.addresses == flat.addresses
    assert hier.applications == flat.applications


def test_quoted_description_keeps_punctuation() -> None:
    policy = parse_config(POLICY).policies[0]
    assert policy.description == "Billing app; CHG-20431 {temp}"


def test_annotation_on_policy() -> None:
    allow, old, partial = parse_config(POLICY).policies
    assert allow.annotations == ["opened for the billing migration, ask Jane (CHG-20431)"]
    assert old.annotations == [] and partial.annotations == []


def test_inactive_policy_and_inactive_statement() -> None:
    _, old, partial = parse_config(POLICY).policies
    assert old.deactivated and not old.deactivated_statements
    assert not partial.deactivated
    assert partial.deactivated_statements == ["match destination-address web-01"]


def test_annotation_inside_policy_and_multiline() -> None:
    text = """\
security {
    policies {
        from-zone a to-zone b {
            policy p {
                match {
                    /* first line
                       second line */
                    source-address any;
                }
            }
        }
        /* on the zone pair, not used */
        from-zone b to-zone a {
            policy q {
                then {
                    permit;    /* trailing, dropped */
                }
            }
        }
    }
}
"""
    p, q = parse_config(text).policies
    assert p.annotations == ["first line second line"]
    assert q.annotations == [] and q.action == "permit"


def test_apply_groups_reported_not_expanded() -> None:
    text = """\
groups {
    common-policies {
        security {
            policies {
                from-zone a to-zone b {
                    policy from-group {
                        then {
                            permit;
                        }
                    }
                }
            }
        }
    }
}
apply-groups common-policies;
security {
    policies {
        apply-groups [ g1 g2 ];
        from-zone a to-zone b {
            policy local {
                then {
                    deny;
                }
            }
        }
    }
}
"""
    config = parse_config(text)
    assert keys(config) == ["a/b/local"]
    assert config.stats.apply_groups == [
        "top level: apply-groups common-policies",
        "security policies: apply-groups g1",
        "security policies: apply-groups g2",
    ]
    flat = parse_set("set apply-groups common-policies\n")
    assert flat.stats.apply_groups == ["top level: apply-groups common-policies"]


def test_inactive_zone_pair_deactivates_its_policies() -> None:
    # No documentation sample shows `inactive:` on a zone pair (decision 0034):
    # inline sample, with `inactive:` placed as HIER-1b shows it on interfaces.
    text = """security {
    policies {
        inactive: from-zone a to-zone b {
            policy p {
                then {
                    permit;
                }
            }
        }
        from-zone a to-zone c {
            policy q {
                then {
                    permit;
                }
            }
        }
    }
}
"""
    config = parse_config(text)
    p, q = config.policies
    assert p.deactivated and not q.deactivated
    assert p.deactivated_statements == ["deactivated with security policies from-zone a to-zone b"]
    assert config.stats.notes == [
        "deactivate security policies from-zone a to-zone b: every policy under it is read "
        "as deactivated"
    ]
    assert config.stats.unknown == 0


def test_inactive_policies_or_security_deactivates_every_policy() -> None:
    for wrapper in ("inactive: security {\n    policies {", "security {\n    inactive: policies {"):
        text = (
            wrapper
            + """
        from-zone a to-zone b {
            policy p {
                then {
                    permit;
                }
            }
        }
        from-zone b to-zone a {
            policy q {
                then {
                    deny;
                }
            }
        }
    }
}
"""
        )
        config = parse_config(text)
        assert [p.deactivated for p in config.policies] == [True, True], wrapper


def test_deactivate_zone_pair_in_set_format_any_line_order() -> None:
    lines = [
        "set security policies from-zone a to-zone b policy p then permit",
        "set security policies from-zone a to-zone b policy p2 then permit",
        "set security policies from-zone b to-zone a policy q then permit",
        "deactivate security policies from-zone a to-zone b",
    ]
    for text in ("\n".join(lines), "\n".join(lines[-1:] + lines[:-1])):
        config = parse_set(text + "\n")
        assert [p.deactivated for p in config.policies if p.from_zone == "a"] == [True, True]
        assert not next(p for p in config.policies if p.from_zone == "b").deactivated
        assert config.stats.unknown == 0
    everything = parse_set("\n".join(lines[:3]) + "\ndeactivate security policies\n")
    assert all(p.deactivated for p in everything.policies)
    whole = parse_set("\n".join(lines[:3]) + "\ndeactivate security\n")
    assert all(p.deactivated for p in whole.policies)


def test_operational_show_configuration_capture() -> None:
    text = """\
user@fw1> show configuration security policies | no-more
from-zone a to-zone b {
    policy p {
        then {
            permit;
        }
    }
}

{primary:node0}
user@fw1> show configuration applications
application x {
    protocol udp;
}
"""
    config = parse_config(text)
    assert keys(config) == ["a/b/p"]
    assert config.applications["x"].protocol == "udp"
    assert config.stats.unknown == 0


def test_unbalanced_braces_are_unknown_not_fatal() -> None:
    text = "security {\n    policies {\n        bogus;\n}\n}\n}\nsecurity {\n"
    config = parse_hierarchical(text)
    assert config.stats.unknown_samples == [
        "line 3: set security policies bogus",
        "line 6: }",
        "line 7: 1 unclosed",
    ]


def test_set_relative_reported() -> None:
    text = "[edit security policies]\nset from-zone a to-zone b policy p then permit\n"
    config = parse_config(text)
    assert config.stats.format == "set relative"
    assert keys(config) == ["a/b/p"]


# Global policies (decision 0034), fixtures from the Global Security Policies page


def test_global_policies_in_both_formats() -> None:
    for name in ("display_set_global_policies.txt", "hier_global_policies.txt"):
        config = parse_config(body(name))
        assert config.stats.unknown == 0, name
        assert keys(config) == ["global/gp1", "global/gp2"], name
        gp1, gp2 = config.policies
        assert gp1.is_global and (gp1.from_zone, gp1.to_zone) == ("global", "global")
        assert (gp1.sources, gp1.destinations, gp1.applications) == (
            ["server1"],
            ["server2"],
            ["any"],
        )
        assert (gp1.action, gp2.action) == ("permit", "deny")
        assert gp1.match_from_zones == [] and gp1.zones_text("from") == "any zone (global policy)"


def test_global_policy_zone_conditions_in_both_formats() -> None:
    for name in ("display_set_global_policy_zones.txt", "hier_global_policy_zones.txt"):
        config = parse_config(body(name))
        assert config.stats.unknown == 0, name
        (pa,) = config.policies
        assert str(pa.key) == "global/Pa"
        assert pa.match_from_zones == ["zone1", "zone2"]
        assert pa.match_to_zones == ["zone3", "zone4"]
        assert pa.zones_text("to") == "zones zone3, zone4 (global policy)"


def test_global_key_round_trip_and_deactivated_global_block() -> None:
    from palimp.models import PolicyKey

    key = PolicyKey.parse("global/gp1")
    assert (key.from_zone, key.to_zone, key.name) == ("global", "global", "gp1")
    assert str(key) == "global/gp1"
    text = body("display_set_global_policies.txt")
    zone = "set security policies from-zone a to-zone b policy p then permit\n"
    config = parse_set(zone + text + "deactivate security policies global\n")
    assert [p.deactivated for p in config.policies] == [False, True, True]
    one = parse_set(text + "deactivate security policies global policy gp2\n")
    assert [p.deactivated for p in one.policies] == [False, True]
