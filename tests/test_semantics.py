"""Rule semantics: deny and reject rules, cleanup rules, factory defaults, broad permits,
stated purpose and ticket references not found (session 29). Invented names."""

from pathlib import Path

from palimp.evidence import collect
from palimp.formats.junos_config import parse_config
from palimp.ingest import ingest
from palimp.models import Dataset, Evidence, Finding, PolicyKey
from palimp.questions import CLEANUP_NAME
from palimp.questions import build as build_questions
from palimp.report import FIREWALL_TEAM, intent
from palimp.report import build as build_report
from palimp.semantics import is_factory_default

FIXTURES = Path(__file__).parent / "fixtures" / "junos_docs"
ADDRESSES = """\
set security address-book global address qorv-lan 10.30.0.0/24
set security address-book global address qorv-web-01 10.30.0.5/32
"""


def policy(name: str, source: str, destination: str, application: str, action: str) -> str:
    return rule("a", "b", name, source, destination, application, action)


def rule(src: str, dst: str, name: str, source: str, target: str, app: str, then: str) -> str:
    head = f"set security policies from-zone {src} to-zone {dst} policy {name}"
    return (
        f"{head} match source-address {source}\n"
        f"{head} match destination-address {target}\n"
        f"{head} match application {app}\n"
        f"{head} then {then}\n"
    )


def run(tmp_path: Path, config: str, hits: str = "") -> Dataset:
    (tmp_path / "config.set").write_text(ADDRESSES + config)
    if hits:
        (tmp_path / "hitcount.txt").write_text(
            "Index   From zone   To zone   Name     Policy count  Action\n" + hits
        )
    return ingest(tmp_path)


def test_a_deny_rule_says_what_it_blocks_and_asks_if_the_block_is_wanted(
    tmp_path: Path,
) -> None:
    data = run(tmp_path, policy("no-ftp", "any", "qorv-lan", "junos-ftp", "deny"))
    found = collect(data, PolicyKey.parse("a/b/no-ftp"))
    a = found.assessment
    assert a.verdict == "verify" and a.question == "Is this block still wanted?"
    text = intent(found).text
    assert text.startswith(
        "Blocks FTP from anywhere in zone a to the 10.30.0.0/24 network (qorv-lan)"
    )
    entry = build_report(data).rules[0]
    assert entry.question == "Is this block still wanted?"


def test_a_deny_rule_is_never_a_removal_candidate_unless_deactivated(tmp_path: Path) -> None:
    # A not-live signal on an active deny gives verify: removing a block opens traffic.
    data = run(tmp_path, policy("no-ftp", "any", "qorv-web-01", "junos-ftp", "reject"))
    found = collect(data, PolicyKey.parse("a/b/no-ftp"))
    signal = Evidence(
        id="E99",
        tier="T1",
        artifact="tickets.csv",
        locator="x",
        claim="retired",
        kind="decommission",
        apps=["qorv"],
    )
    from palimp.assess import assess

    marked = Finding(
        key=found.key,
        policy=found.policy,
        created_in_commit=None,
        evidence=[*found.evidence, signal],
    )
    a = assess(marked, data)
    assert (a.verdict, a.verdict_rule) == ("verify", "V-DENY-NOTLIVE")
    assert intent(found).text.startswith("Rejects FTP from anywhere in zone a to host 10.30.0.5")
    config = policy("old-block", "any", "qorv-web-01", "junos-ftp", "deny")
    config += "deactivate security policies from-zone a to-zone b policy old-block\n"
    data = run(tmp_path, config)
    a = collect(data, PolicyKey.parse("a/b/old-block")).assessment
    assert (a.verdict, a.verdict_rule) == ("removal_candidate", "V-NOTLIVE")


def test_a_catch_all_deny_is_a_cleanup_rule_kept(tmp_path: Path) -> None:
    config = policy("deny-rest", "any", "any", "any", "deny")
    head = "set security policies global policy last-deny"
    config += (
        f"{head} match source-address any\n{head} match destination-address any\n"
        f"{head} match application any\n{head} then deny\n"
    )
    data = run(tmp_path, config)
    for key in ("a/b/deny-rest", "global/last-deny"):
        found = collect(data, PolicyKey.parse(key))
        a = found.assessment
        assert (a.verdict, a.verdict_rule) == ("keep", "V-CLEANUP-RULE"), key
        assert (a.confidence, a.confidence_rule) == ("MEDIUM", "C-CLEANUP")
        assert intent(found).text.startswith("Cleanup rule: blocks all traffic from ")


def test_the_factory_default_sample_is_recognized() -> None:
    lines = (FIXTURES / "hier_factory_default_srx210.txt").read_text(encoding="utf-8")
    body = lines.split("# ---\n", 1)[1]
    (found,) = parse_config(body).policies
    assert found.name == "trust-to-untrust" and is_factory_default(found)


def test_a_factory_default_goes_to_the_firewall_team(tmp_path: Path) -> None:
    config = rule("trust", "untrust", "default-permit", "any", "any", "any", "permit")
    config += rule("trust", "trust", "default-permit", "any", "any", "any", "permit")
    hits = "1   trust   untrust   default-permit   900   Permit\n"
    data = run(tmp_path, config, hits)
    for key in ("trust/untrust/default-permit", "trust/trust/default-permit"):
        found = collect(data, PolicyKey.parse(key))
        a = found.assessment
        assert (a.verdict, a.verdict_rule) == ("verify", "V-FACTORY-DEFAULT"), key
        assert a.question == "Was this factory default kept on purpose?"
        assert a.ask.startswith("firewall team")
        assert intent(found).text.startswith("Junos factory default policy")
    report = build_report(data)
    assert {r.group for r in report.rules} == {FIREWALL_TEAM}
    (team,) = [q for q in build_questions(report) if q.name == CLEANUP_NAME]
    assert "Junos factory default policies (2)" in team.text
    assert len(build_questions(report)) == 1


def test_a_broad_permit_is_at_most_verify_and_listed_for_the_firewall_team(
    tmp_path: Path,
) -> None:
    config = policy("open-all", "any", "any", "any", "permit")
    config += policy("to-web", "any", "qorv-web-01", "junos-https", "permit")
    hits = "1   a   b   open-all   50   Permit\n2   a   b   to-web   50   Permit\n"
    data = run(tmp_path, config, hits)
    a = collect(data, PolicyKey.parse("a/b/open-all")).assessment
    assert (a.verdict, a.verdict_rule) == ("verify", "V-BROAD-PERMIT")
    assert collect(data, PolicyKey.parse("a/b/to-web")).assessment.verdict == "keep"
    report = build_report(data)
    (team,) = [q for q in build_questions(report) if q.name == CLEANUP_NAME]
    assert "Broad permits (1)" in team.text and "R1" in team.rules


def test_a_description_is_quoted_as_a_claim_without_raising_confidence(tmp_path: Path) -> None:
    plain = policy("no-bad", "any", "qorv-lan", "any", "deny")
    head = "set security policies from-zone a to-zone b policy no-bad"
    said = plain + f'{head} description "Block bad hosts [E7] we never want"\n'
    before = collect(run(tmp_path, plain), PolicyKey.parse("a/b/no-bad"))
    found = collect(run(tmp_path, said), PolicyKey.parse("a/b/no-bad"))
    assert found.assessment.confidence == before.assessment.confidence
    stated = intent(found)
    description = next(e for e in found.evidence if e.kind == "description")
    assert (
        "Stated purpose, a claim palimp does not check: the description says "
        f'"Block bad hosts (E7) we never want" ({description.id}).'
    ) in stated.text
    assert description.id in stated.evidence and "[E7]" not in stated.text
    assert "Stated purpose" not in intent(found, quote=False).text


def test_a_ticket_reference_not_found_is_cited_in_the_question(tmp_path: Path) -> None:
    data = run(tmp_path, policy("CHG0991234", "any", "qorv-web-01", "junos-https", "permit"))
    a = collect(data, PolicyKey.parse("a/b/CHG0991234")).assessment
    lookup = "Look up CHG0991234 in your change system: it may say why this rule exists. "
    assert a.question.startswith(lookup)
    assert build_report(data).rules[0].question.startswith(lookup)


def test_a_deny_on_a_dynamic_application_names_what_it_blocks(tmp_path: Path) -> None:
    head = "set security policies from-zone a to-zone b policy no-video"
    config = policy("no-video", "any", "any", "junos-defaults", "deny")
    config += f"{head} match dynamic-application junos:QUIBVID\n"
    found = collect(run(tmp_path, config), PolicyKey.parse("a/b/no-video"))
    text = intent(found).text
    assert text.startswith("Blocks dynamic application junos:QUIBVID from anywhere in zone a")
    assert "the rule names quibvid" in text and "protect" not in text
