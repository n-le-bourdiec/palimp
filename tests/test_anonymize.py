"""`palimp anonymize` (decision 0031).

The key test: on Medium dev seeds 0 to 9, palimp gives the same verdicts,
confidence levels and owner certainty on the anonymized copy, and no original
IP address, name, person or ticket ID is left in it. Black box like the other
tests: the simulator writes a scenario, palimp reads only its artifacts.
"""

import ipaddress
import itertools
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import CliRunner

from palimp.addresses import NON_PUBLIC, is_public, special_range
from palimp.anonymize import RUN, Mapper, Options, anonymize, is_signal, write
from palimp.cli import app
from palimp.evidence import collect_all
from palimp.formats.terminal import PROMPT, is_terminal_noise
from palimp.ingest import ingest
from palimp.models import Dataset
from palimp.report import build

FIXTURES = Path(__file__).parent / "fixtures" / "junos_docs"
KEY = bytes(range(32))
OTHER_KEY = bytes(range(1, 33))
IP = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
TOKEN = re.compile(r"[\w@-]+(?:\.[\w@-]+)*")


def generate(seed: int, out: Path, level: str = "medium") -> Path:
    command = [sys.executable, "-m", "palimp_sim.cli", "generate", "--level", level]
    subprocess.run(
        command + ["--seed", str(seed), "--out", str(out)], check=True, capture_output=True
    )
    return out / f"scenario-{level}-{seed:06d}" / "artifacts"


@pytest.fixture(scope="module")
def easy(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return generate(0, tmp_path_factory.mktemp("easy"), "easy")


def judgments(dataset: Dataset) -> list[tuple[str, str, bool]]:
    """Verdict, confidence and owner certainty of every policy, in configuration order."""
    found = []
    for finding in collect_all(dataset):
        assessment = finding.assessment
        assert assessment is not None
        found.append((assessment.verdict, assessment.confidence, assessment.owner is not None))
    return found


def looks(dataset: Dataset) -> list[tuple[str, str]]:
    """The "Worth a look" list of the report: rule reference and risk, most risky first."""
    return [(e.ref, e.risk) for e in build(dataset).worth_a_look]


def originals(dataset: Dataset) -> tuple[set[str], set[str]]:
    """Names (policies, zones, objects, applications, people, logins, tickets) and words
    of people's names, from the original artifacts."""
    config = dataset.config
    names = set(config.addresses) | {a for a in config.applications if not a.startswith("junos")}
    for policy in config.policies:
        names |= {policy.name, policy.from_zone, policy.to_zone}
    names |= {c.user for c in dataset.commits}
    people = set()
    for ticket in dataset.tickets.values():
        names |= {ticket.ticket_id, ticket.related_ci or ""}
        people |= {ticket.requester or "", ticket.assignee or ""}
    words = {w for person in people for w in person.split()}
    return names - {"", "any", "global"}, words


def tokens(directory: Path) -> set[str]:
    found: set[str] = set()
    for path in directory.rglob("*"):
        if path.is_file():
            found |= set(TOKEN.findall(path.read_text(encoding="utf-8")))
    return found


def all_ips(directory: Path) -> set[str]:
    found: set[str] = set()
    for path in directory.rglob("*"):
        if path.is_file():
            found |= set(IP.findall(path.read_text(encoding="utf-8", errors="replace")))
    return {ip for ip in found if all(int(o) < 256 for o in ip.split("."))}


def check_copy(source: Path, out: Path, mapper: Mapper) -> None:
    original = ingest(source)
    copy = ingest(out)
    assert judgments(copy) == judgments(original)
    assert looks(copy) == looks(original)

    names, words = originals(original)
    image = set(mapper.names.values())
    image_words = {w for v in image for w in re.split(r"[\s@]", v)}
    found = tokens(out)
    assert not (names & found) - image, "original names left in the copy"
    assert not (words & found) - image_words, "words of people's names left in the copy"
    # Names made only of signal words (`servers-to-dns`, decision 0042) are kept.
    words_of = [(n, [r for r in RUN.findall(n.lower()) if not r.isdigit()]) for n in names]
    private = [n for n, runs in words_of if any(not is_signal(r) for r in runs)]
    changed = [n for n in private if mapper.name(n) != n]
    assert len(changed) >= 0.9 * len(private)

    ips = all_ips(source)
    mapped_ips = {str(ipaddress.ip_interface(v).ip) for v in mapper.ips.values()}
    assert not (ips & all_ips(out)) - mapped_ips, "original addresses left in the copy"
    assert len(ips) > 10


@pytest.mark.slow
@pytest.mark.parametrize("seed", range(10))
def test_medium_judgments_identical_and_nothing_left(seed: int, tmp_path: Path) -> None:
    source = generate(seed, tmp_path / "scenario")
    result = anonymize(source, KEY)
    write(result, tmp_path / "copy", Options())
    check_copy(source, tmp_path / "copy", result.mapper)


@pytest.mark.slow
def test_shifted_dates_keep_judgments(tmp_path: Path) -> None:
    source = generate(0, tmp_path / "scenario")
    options = Options(shift_dates=True)
    result = anonymize(source, KEY, options)
    write(result, tmp_path / "copy", options)
    assert judgments(ingest(tmp_path / "copy")) == judgments(ingest(source))
    original = (source / "commits.txt").read_text(encoding="utf-8")
    shifted = (tmp_path / "copy" / "commits.txt").read_text(encoding="utf-8")
    assert re.findall(r"\d{2}:\d{2}:\d{2}", shifted) == re.findall(r"\d{2}:\d{2}:\d{2}", original)
    assert re.findall(r"\d{4}-\d{2}-\d{2}", shifted) != re.findall(r"\d{4}-\d{2}-\d{2}", original)


def test_easy_copy(easy: Path, tmp_path: Path) -> None:
    result = anonymize(easy, KEY)
    write(result, tmp_path / "copy", Options())
    check_copy(easy, tmp_path / "copy", result.mapper)
    assert (tmp_path / "copy" / "ANONYMIZED.txt").is_file()


def test_same_key_same_bytes_other_key_other_mapping(easy: Path) -> None:
    first, again = anonymize(easy, KEY), anonymize(easy, KEY)
    assert first.files == again.files
    other = anonymize(easy, OTHER_KEY)
    assert other.files != first.files
    names = sorted(first.mapper.names)
    same = [n for n in names if first.mapper.names[n] == other.mapper.names.get(n)]
    assert len(same) < 0.2 * len(names)
    assert set(first.mapper.ips.values()) != set(other.mapper.ips.values())


def test_strip_text(easy: Path, tmp_path: Path) -> None:
    options = Options(strip_text=True)
    result = anonymize(easy, KEY, options)
    assert " description " not in result.files["config.set"]
    commits = ingest(easy).commits
    assert any(c.comment for c in commits)
    write(result, tmp_path / "copy", options)
    copy = ingest(tmp_path / "copy")
    assert not any(c.comment for c in copy.commits)
    assert len(copy.commits) == len(commits)
    assert not any(t.summary for t in copy.tickets.values())
    assert len(copy.config.policies) == len(ingest(easy).config.policies)


def test_addresses_keep_their_class_and_subnets() -> None:
    mapper = Mapper(key=KEY)
    samples = [str(n.network_address + 5) for n in NON_PUBLIC if n.num_addresses > 8]
    samples += ["8.8.8.8", "52.1.2.3", "198.51.100.7", "203.0.113.9", "2a00:1450::1"]
    for text in samples:
        address = ipaddress.ip_address(text)
        mapped = ipaddress.ip_address(mapper.ip(text))
        net = ipaddress.ip_network(address)
        mapped_net = ipaddress.ip_network(mapped)
        assert special_range(net) == special_range(mapped_net), text
        assert is_public(net) == is_public(mapped_net), text
    hosts = ["10.20.1.10", "10.20.1.11", "10.20.7.1", "10.99.0.1", "192.168.1.1", "8.8.8.8"]
    for a, b in itertools.combinations(hosts, 2):
        ma, mb = (int(ipaddress.ip_address(mapper.ip(x))) for x in (a, b))
        common = 32 - (int(ipaddress.ip_address(a)) ^ int(ipaddress.ip_address(b))).bit_length()
        assert 32 - (ma ^ mb).bit_length() == common, (a, b)
    network = mapper.ip("10.20.0.0/15")
    assert ipaddress.ip_address(mapper.ip("10.20.1.10")) in ipaddress.ip_network(network)


def test_host_with_prefix_length_keeps_host_bits() -> None:
    # Session 23 issue: `192.168.2.2/24` was mapped as its network, so three hosts
    # of one subnet collapsed into one address.
    mapper = Mapper(key=KEY)
    texts = ["192.168.2.0/24", *(f"192.168.2.{h}/24" for h in range(1, 255))]
    texts += ["10.20.0.0/15", "10.20.1.10/15", "10.21.0.0/15", "2a00:1450::/64", "2a00:1450::1/64"]
    mapped = [mapper.ip(t) for t in texts]
    assert len(set(mapped)) == len(texts)
    network = ipaddress.ip_network(mapper.ip("192.168.2.0/24"))
    for text, new in zip(texts, mapped, strict=True):
        before, after = ipaddress.ip_interface(text), ipaddress.ip_interface(new)
        assert after.network.prefixlen == before.network.prefixlen
        # A network stays a network, a host stays a host.
        assert (after.ip == after.network.network_address) == (
            before.ip == before.network.network_address
        ), text
    for host in range(1, 255):
        address = ipaddress.ip_interface(mapper.ip(f"192.168.2.{host}/24")).ip
        assert address in network
    # Most hosts match the same address written alone (log lines).
    alone = sum(
        mapper.ip(f"192.168.2.{h}/24").split("/")[0] == mapper.ip(f"192.168.2.{h}")
        for h in range(1, 255)
    )
    assert alone >= 253


def test_distinct_addresses_stay_distinct_in_the_copy(tmp_path: Path) -> None:
    source = tmp_path / "capture"
    source.mkdir()
    (source / "config.set").write_text(
        fixture_body("hier_zone_relative_show.txt"), encoding="utf-8"
    )
    result = anonymize(source, KEY)
    write(result, tmp_path / "copy", Options())
    original, anonymized = ingest(source), ingest(tmp_path / "copy")
    values = [o.value for o in original.config.addresses.values() if o.value]
    copied = [o.value for o in anonymized.config.addresses.values() if o.value]
    assert len(values) == len(copied) >= 3
    assert len(set(copied)) == len(set(values))
    assert {result.mapper.ip(v) for v in values} == set(copied)
    assert judgments(anonymized) == judgments(original)


def test_names_keep_structure_and_signal_words() -> None:
    mapper = Mapper(key=KEY)
    assert mapper.name("monitoring").startswith(mapper.name("mon"))
    assert mapper.name("crm-db-01").split("-")[0] == mapper.name("crm-web-02").split("-")[0]
    assert mapper.name("users-to-crm").startswith("users-")
    assert mapper.name("temp-vendor").startswith("temp-")
    assert mapper.name("untrust") == "untrust"
    assert mapper.name("CHG0045868").startswith("CHG")
    assert mapper.name("CHG0045868") != "CHG0045868"
    assert mapper.name("junos-ssh") == "junos-ssh"
    mapped = mapper.name("Elif Haddad")
    assert mapped[0].isupper() and len(mapped) == len("Elif Haddad") and " " in mapped
    assert mapper.name("h-10.20.1.5") == "h-" + mapper.ip("10.20.1.5")


def test_free_text_replaces_known_names_only() -> None:
    mapper = Mapper(key=KEY, known={"crm-db-01", "Elif Haddad"}, segments={"crm", "elif"})
    text = "temp access for crm-db-01, req EH, CHG0012345, 10.1.2.3 and ESHOP"
    out = mapper.text(text)
    assert out.startswith("temp access for ")
    assert mapper.name("crm-db-01") in out
    assert mapper.name("CHG0012345") in out
    assert mapper.ip("10.1.2.3") in out
    assert "ESHOP" not in out
    initials = "".join(word[0] for word in mapper.name("Elif Haddad").split())
    assert f"req {initials}" in out


def test_cli(easy: Path, tmp_path: Path) -> None:
    runner = CliRunner()
    out, key = tmp_path / "shared", tmp_path / "private" / "palimp.key"
    command = ["anonymize", "-a", str(easy), "-o", str(out), "--key", str(key), "--mapping"]
    result = runner.invoke(app, command)
    assert result.exit_code == 0, result.output
    assert key.is_file() and "new key written" in result.output
    mapping = tmp_path / "shared.PRIVATE-mapping.json"
    assert mapping.is_file()
    assert not list(out.rglob("*PRIVATE*")) and not list(out.rglob("*.key"))
    again = runner.invoke(app, command)
    assert again.exit_code == 2 and "already exists" in again.output
    inside = ["anonymize", "-a", str(easy), "-o", str(tmp_path / "o2"), "--key"]
    refused = runner.invoke(app, inside + [str(tmp_path / "o2" / "k")])
    assert refused.exit_code == 2 and "outside OUT" in refused.output
    report = runner.invoke(app, ["report", "-a", str(out), "-o", str(tmp_path / "r")])
    assert report.exit_code == 0, report.output


@pytest.mark.slow
@pytest.mark.parametrize("seed", range(10))
def test_hierarchical_judgments_identical_and_nothing_left(
    seed: int, tmp_path: Path, to_hierarchical: Callable[[Path, Path], Path]
) -> None:
    """The same check on a hierarchical rendering of the scenario (decision 0032)."""
    source = to_hierarchical(generate(seed, tmp_path / "scenario"), tmp_path / "hier")
    assert ingest(source).config.stats.format == "hierarchical"
    result = anonymize(source, KEY)
    write(result, tmp_path / "copy", Options())
    assert ingest(tmp_path / "copy").config.stats.format == "hierarchical"
    check_copy(source, tmp_path / "copy", result.mapper)


ANNOTATED = """\
## Last commit: 2026-03-02 10:00:00 UTC by bob
security {
    address-book {
        global {
            address crm-web 10.20.1.10/32;
        }
    }
    policies {
        from-zone trust to-zone dc {
            /* CRM front end for Alice Example, CHG0000777, server 10.20.1.10 */
            policy crm-web {
                description "CRM web CHG0000777";
                match {
                    source-address any;
                    destination-address crm-web;
                    application junos-https;
                }
                then {
                    permit;
                }
            }
            /* opened by bob
               for crm-web */
            inactive: policy crm-old {
                match {
                    source-address any;
                    destination-address crm-web;
                    application junos-http;
                }
                then {
                    permit;
                }
            }
        }
    }
}
"""


@pytest.fixture
def annotated(tmp_path: Path) -> Path:
    source = tmp_path / "annotated"
    source.mkdir()
    (source / "config.set").write_text(ANNOTATED, encoding="utf-8")
    (source / "commits.txt").write_text(
        "0   2026-03-02 10:00:00 UTC by bob via cli\n    CHG0000777 CRM\n", encoding="utf-8"
    )
    (source / "tickets.csv").write_text(
        "ticket_id,requester,status,summary\nCHG0000777,Alice Example,closed,CRM\n",
        encoding="utf-8",
    )
    return source


def test_annotations_anonymized_like_descriptions(annotated: Path, tmp_path: Path) -> None:
    result = anonymize(annotated, KEY)
    text = result.files["config.set"]
    for original in ("Alice", "Example", "CHG0000777", "10.20.1.10", "crm-web", "bob"):
        assert original not in text, original
    assert " front end for " in text and "opened by " in text
    write(result, tmp_path / "copy", Options())
    copy, original = ingest(tmp_path / "copy"), ingest(annotated)
    assert copy.config.stats.format == "hierarchical" and copy.config.stats.unknown == 0
    assert judgments(copy) == judgments(original)
    notes = [p.annotations for p in copy.config.policies]
    assert " front end for " in notes[0][0] and notes[1][0].startswith("opened by ")
    assert copy.config.policies[1].deactivated


def test_strip_text_removes_annotations(annotated: Path, tmp_path: Path) -> None:
    options = Options(strip_text=True)
    result = anonymize(annotated, KEY, options)
    assert (
        "/*" not in result.files["config.set"] and "description" not in result.files["config.set"]
    )
    write(result, tmp_path / "copy", options)
    copy = ingest(tmp_path / "copy")
    assert [p.annotations for p in copy.config.policies] == [[], []]
    assert copy.config.stats.unknown == 0 and len(copy.config.policies) == 2


# Saved terminal captures (session 21 issue): prompt, banner and elision lines
# are what the parsers ignore (palimp.formats.terminal); anonymize keeps their
# CLI words, so the copy keeps its relative paths and parses the same way.


def fixture_body(name: str) -> str:
    lines = (FIXTURES / name).read_text(encoding="utf-8").splitlines()
    return "\n".join(lines[lines.index("# ---") + 1 :]) + "\n"


@pytest.mark.parametrize(
    "name",
    [
        "hier_zone_relative_show.txt",
        "hier_policy_log_prompt_nospace.txt",
        "hier_permit_firewall_authentication.txt",
        "display_set_pipe.txt",
    ],
)
def test_terminal_capture_keeps_prompts_and_banners(name: str, tmp_path: Path) -> None:
    source = tmp_path / "capture"
    source.mkdir()
    text = fixture_body(name)
    (source / "config.set").write_text(text, encoding="utf-8")
    result = anonymize(source, KEY)
    copy = result.files["config.set"]
    known = result.mapper.known
    for before, after in zip(text.splitlines(), copy.splitlines(), strict=True):
        if not is_terminal_noise(before):
            continue
        assert is_terminal_noise(after), (before, after)
        prompt = PROMPT.match(before.strip())
        if prompt is None:
            # `[edit]`, `...`: unchanged unless they hold a name palimp knows.
            if not any(n in before for n in known):
                assert after == before
            continue
        login, host = before.strip()[: prompt.start(1)].split("@")
        # Login and host mapped like any name (a signal word such as `user` stays).
        mapped = f"{result.mapper.name(login)}@{result.mapper.name(host)}"
        assert after.strip().startswith(mapped)
        command = before.strip()[prompt.start(1) :].split()
        shown = PROMPT.match(after.strip())
        assert shown is not None
        rewritten = after.strip()[shown.start(1) :].split()
        assert len(rewritten) == len(command)
        for word, new in zip(command, rewritten, strict=True):
            assert new == word or word in known, (word, new)
    write(result, tmp_path / "copy", Options())
    original, anonymized = ingest(source), ingest(tmp_path / "copy")
    assert anonymized.config.stats.format == original.config.stats.format
    assert anonymized.config.stats.unknown == original.config.stats.unknown
    assert len(anonymized.config.policies) == len(original.config.policies)
    assert [result.mapper.name(p.name) for p in original.config.policies] == [
        p.name for p in anonymized.config.policies
    ]
    assert judgments(anonymized) == judgments(original)


# Invented names in the styles real networks use (session 31): site codes, people's
# workstations, ticket numbers in policy names, hostnames with a role and a site.
REALISTIC_ADDRESSES = {
    "web-par1-01": "10.10.1.10/32",
    "PC-SLINDQVIST": "10.20.5.33/32",
    "par1-sql-prd-01": "10.30.1.5/32",
    "LAN-LYO2": "10.40.0.0/16",
    "lyo2-web-02": "10.30.2.7/32",
}
# (from zone, to zone, name, source, destination, application, description)
REALISTIC_POLICIES = [
    (
        "untrust",
        "dmz",
        "CHG0451277",
        "any",
        "web-par1-01",
        "junos-https",
        "Webshop frontend for Sophie Lindqvist (INC0098123)",
    ),
    (
        "trust",
        "dc",
        "PC-SLINDQVIST-to-par1-sql-prd-01",
        "PC-SLINDQVIST",
        "par1-sql-prd-01",
        "junos-ms-sql",
        "",
    ),
    ("trust", "dc", "lyo2-web-02_access", "LAN-LYO2", "lyo2-web-02", "junos-http", "LYO2 req MF"),
]


def realistic_config() -> str:
    lines = [
        f"set security address-book global address {name} {value}"
        for name, value in REALISTIC_ADDRESSES.items()
    ]
    for from_zone, to_zone, name, source, destination, application, note in REALISTIC_POLICIES:
        head = f"set security policies from-zone {from_zone} to-zone {to_zone} policy {name}"
        if note:
            lines.append(f'{head} description "{note}"')
        lines += [
            f"{head} match source-address {source}",
            f"{head} match destination-address {destination}",
            f"{head} match application {application}",
            f"{head} then permit",
        ]
    return "\n".join(lines) + "\n"


REALISTIC_COMMITS = """\
0   2026-03-02 10:00:00 UTC by mferretti via cli
    INC0098123 webshop frontend for Sophie
1   2026-02-01 09:30:00 UTC by mferretti via cli
    CHG0451277 SQL access for PC-SLINDQVIST
"""
REALISTIC_TICKETS = """\
ticket_id,opened,closed,status,requester,assignee,summary,category,related_ci
CHG0451277,2026-01-20,2026-02-01,closed,Sophie Lindqvist,mferretti,PAR1 go live,change,webshop
INC0098123,2026-02-25,2026-03-02,closed,Sophie Lindqvist,Marco Ferretti,WEBSHOP,incident,webshop
"""
# Letter and digit runs that identify the company, its sites, people and tickets.
REALISTIC_SECRETS = {
    "par",
    "lyo",
    "sophie",
    "lindqvist",
    "slindqvist",
    "mferretti",
    "marco",
    "ferretti",
    "webshop",
    "0451277",
    "0098123",
}


def test_realistic_names_leave_nothing_and_keep_judgments(tmp_path: Path) -> None:
    source = tmp_path / "realistic"
    source.mkdir()
    (source / "config.set").write_text(realistic_config(), encoding="utf-8")
    (source / "commits.txt").write_text(REALISTIC_COMMITS, encoding="utf-8")
    (source / "tickets.csv").write_text(REALISTIC_TICKETS, encoding="utf-8")
    result = anonymize(source, KEY)
    write(result, tmp_path / "copy", Options())
    runs = {r.lower() for text in result.files.values() for r in RUN.findall(text)}
    assert not REALISTIC_SECRETS & runs, sorted(REALISTIC_SECRETS & runs)
    assert "MF" not in result.files["config.set"]
    original, copy = ingest(source), ingest(tmp_path / "copy")
    assert judgments(copy) == judgments(original)
    # `web-par1-01` reads as webshop (`web` abbreviates the related CI); the copy keeps
    # that reading under the replaced application name.
    before = [f.assessment.intent_apps for f in collect_all(original) if f.assessment]
    after = [f.assessment.intent_apps for f in collect_all(copy) if f.assessment]
    assert ["webshop"] in before
    assert after == [[result.mapper.name(a) for a in apps] for apps in before]
