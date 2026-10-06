"""A shareable copy of an artifact directory (decision 0031).

Every original value gets the same replacement in every file, computed from
a secret key with HMAC-SHA256, so the copy keeps what palimp needs:

- IP addresses: prefix-preserving (two addresses of one subnet stay in one
  subnet) and class-preserving (an address inside a private or reserved range
  stays inside the same range, a public one stays public). Bit i of an
  address is flipped by a keyed bit of its first i bits, except where the
  subtree below holds a reserved range, which must stay where it is.
- Names (policies, objects, applications, zones, people, logins, hosts,
  ticket IDs, related CIs): each run of letters and each run of digits is
  replaced character by character, each character by a keyed permutation
  that depends on the characters before it in the run. Runs keep their
  length, case and shared prefixes (`mon` stays the start of `monitoring`,
  so palimp still learns abbreviations), and separators stay. Words palimp
  reads as signals (role words such as `users`, temporary words, ticket
  prefixes such as `CHG`, decommission words) and one-letter runs are kept.
- Free text (descriptions, commit comments, ticket summaries): known names,
  IP addresses, ticket IDs, e-mail addresses, initials after "req" and
  upper-case short names are replaced, other words are kept. `strip_text`
  removes free text instead.
- Dates are kept, or shifted by one secret number of whole weeks
  (`shift_dates`), which keeps weekdays and times of day.

A replacement word never equals a kept signal word or a word left in free
text: if one does, the whole mapping is drawn again with the next salt.
"""

import csv
import hashlib
import hmac
import io
import ipaddress
import json
import re
import secrets
import unicodedata
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from palimp import __version__
from palimp.addresses import NON_PUBLIC
from palimp.apps import ROLE_WORDS, vocabulary
from palimp.evidence import TEMPORARY_WORDS
from palimp.formats.commits import ACTIVATE, CONFIRMED, ENTRY, RESCUE, REVISION
from palimp.formats.rollbacks import NAME as ROLLBACK_NAME
from palimp.formats.rollbacks import read_rollbacks
from palimp.formats.terminal import PROMPT
from palimp.ingest import ingest, resolve_directory
from palimp.models import Config, Dataset
from palimp.notlive import DECOMMISSION

KEY_BYTES = 32
MAX_SALT = 50
LETTERS = "abcdefghijklmnopqrstuvwxyz"
DIGITS = "0123456789"
TICKET_PREFIXES = {"chg", "inc", "ritm", "req", "cr", "sr", "task"}
# Words of free text that palimp's rules read: kept in names too.
SIGNAL_WORDS = {
    "any",
    "all",
    "junos",
    "requested",
    "by",
    "shut",
    "down",
    "shutdown",
    "end",
    "of",
    "life",
}
KNOWN_FILES = ("config.set", "commits.txt", "hitcount.txt", "tickets.csv", "logs/rt_flow.log")
KEPT_NAMES = {"any", "any-ipv4", "any-ipv6", "global", "root-logical-system"}
LOG_CONSTANTS = {"N/A", "UNKNOWN", "None", "none", ""}
# Log fields whose value is a name; every other field keeps its value.
LOG_NAME_KEYS = {
    "policy-name",
    "source-zone-name",
    "destination-zone-name",
    "username",
    "roles",
    "service-name",
    "application",
    "nested-application",
    "src-nat-rule-name",
    "dst-nat-rule-name",
    "logical-system-name",
    "rule-name",
    "rulebase-name",
    "hostname",
}
COMMIT_CLIENTS = {"cli", "junoscript", "netconf", "other", "j-web", "jweb", "gnmi", "grpc", "rest"}
TICKET_KEPT_COLUMNS = {"status", "category"}
TICKET_NAME_COLUMNS = {"ticket_id", "requester", "assignee", "related_ci"}
TICKET_DATE_COLUMNS = {"opened", "closed"}
# Junos words kept in configuration lines palimp does not read (system, snmp, ...).
JUNOS_WORDS = set(
    """set deactivate delete activate version system host-name domain-name time-zone login
    message user class super-user read-only operator authentication encrypted-password
    services ssh netconf web-management http https syslog host file messages any all notice
    info warning error critical emergency alert interactive-commands security log mode stream
    format sd-syslog structured-syslog central source-address category interfaces unit family
    inet inet6 address routing-options static route next-hop snmp community authorization
    read-write location contact clients ntp server boot-server name-server zones
    security-zone host-inbound-traffic system-services protocols ping traceroute ike
    dhcp ospf bgp policies from-zone to-zone policy match destination-address application
    then permit deny reject count session-init session-close default-policy deny-all
    permit-all screen ids-option flow tcp-session nat applications application-set
    protocol destination-port source-port inactivity-timeout tcp udp icmp utc root
    root-authentication retry-options max-configurations-on-flash
    max-configuration-rollbacks archival configuration transfer-on-commit archive-sites
    commit synchronize description vlan vlans vlan-id description apply-groups groups
    node0 node1 chassis cluster redundancy-group reth-count priority
    gigether-options redundant-parent redundant-ether-options""".split()
)

IPV4 = r"(?:\d{1,3}\.){3}\d{1,3}"
IPV6 = r"[0-9A-Fa-f]{0,4}(?::[0-9A-Fa-f]{0,4}){2,7}"
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
PIECES = [
    ("bsd", rf"\b(?:{'|'.join(MONTHS)})(?: {{1,2}})\d{{1,2}} \d{{2}}:\d{{2}}:\d{{2}}\b"),
    (
        "date",
        r"(?<!\d)\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)?",
    ),
    ("email", r"[\w.+-]+@(?=[\w.-]*[A-Za-z])[\w-]+(?:\.[\w-]+)+"),
    ("ip", rf"(?<![\w.@:]){IPV4}(?:/\d{{1,3}}(?![\d.]))?(?!\.?\d)(?![\w])"),
    ("ip6", rf"(?<![\w:.]){IPV6}(?:/\d{{1,3}}(?!\d))?(?![\w:])"),
    ("ticket", r"(?i:\b(?:CHG|INC|RITM|REQ|CR|SR|TASK)[-_]?\d{4,}\b)"),
    ("initials", r"\breq(?:uested by)?\.?\s*:?\s+[A-Z]{2,3}\b"),
    (
        "iface",
        r"\b(?:ge|xe|et|fe|ae|reth|lo|irb|fxp|em|st|vlan|lt|gr|ip|sp|me|vme|fab|swfab)"
        r"-?\d+(?:/\d+)*(?:\.\d+)?\b",
    ),
    ("word", r"[^\W_]+(?:[-_.][^\W_]+)*"),
]
TOKENS = re.compile("|".join(f"(?P<{name}>{pattern})" for name, pattern in PIECES))
RUN = re.compile(r"[^\W\d_]+|[0-9]+")
IP_INSIDE = re.compile(rf"(?<![\d.]){IPV4}(?!\.?\d)")
SET_TOKEN = re.compile(r'"((?:[^"\\]|\\.)*)"|(\S+)')
PAIR = re.compile(r'([\w-]+)="((?:[^"\\]|\\.)*)"')
USER_ROLES = re.compile(r"^([^\s()]+)\(([^\s()]*)\)$")


def is_signal(word: str) -> bool:
    """A word palimp's rules read, kept as it is (lower case)."""
    return (
        len(word) <= 1
        or word in ROLE_WORDS
        or word in TEMPORARY_WORDS
        or word in TICKET_PREFIXES
        or word in SIGNAL_WORDS
        or (len(word) == 4 and sorted(word) == list("empt"))
        or bool(DECOMMISSION.match(word))
    )


def _fold(char: str) -> str:
    """An ASCII lower-case letter for any letter (accents dropped)."""
    plain = unicodedata.normalize("NFKD", char).encode("ascii", "ignore").decode().lower()
    return plain[:1] if plain[:1] in LETTERS else "x"


def load_key(path: Path) -> tuple[bytes, bool]:
    """The secret key of KEYFILE, created (random, hex) when the file does not exist."""
    if path.exists():
        text = path.read_text(encoding="utf-8").strip()
        try:
            key = bytes.fromhex(text)
        except ValueError as error:
            raise ValueError(f"{path}: not a palimp key (hexadecimal expected)") from error
        if len(key) < 16:
            raise ValueError(f"{path}: key too short ({len(key)} bytes, 16 at least)")
        return key, False
    key = secrets.token_bytes(KEY_BYTES)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(key.hex() + "\n", encoding="utf-8")
    return key, True


@dataclass
class Options:
    strip_text: bool = False
    shift_dates: bool = False


@dataclass
class Mapper:
    """Keyed, consistent replacements. One instance per salt."""

    key: bytes
    salt: int = 0
    known: set[str] = field(default_factory=set)  # full names, exact
    segments: set[str] = field(default_factory=set)  # lower-case letter runs of known names
    shift: timedelta = timedelta(0)
    names: dict[str, str] = field(default_factory=dict)
    ips: dict[str, str] = field(default_factory=dict)
    runs: dict[str, str] = field(default_factory=dict)  # lower-case letter runs replaced
    kept_words: set[str] = field(default_factory=set)  # lower-case words left in free text
    _perms: dict[tuple[str, str], dict[str, str]] = field(default_factory=dict)
    _flips: dict[tuple[int, int, int], int] = field(default_factory=dict)

    def _prf(self, *parts: str) -> bytes:
        message = "\x1f".join([str(self.salt), *parts]).encode("utf-8")
        return hmac.new(self.key, message, hashlib.sha256).digest()

    def _perm(self, kind: str, context: str) -> dict[str, str]:
        found = self._perms.get((kind, context))
        if found is None:
            alphabet = LETTERS if kind == "a" else DIGITS
            order = sorted(alphabet, key=lambda c: self._prf(kind, context, c))
            found = self._perms[(kind, context)] = dict(zip(alphabet, order, strict=True))
        return found

    # Names

    def run(self, text: str) -> str:
        """One run of letters or of digits."""
        if text.isascii() and text.isdigit():
            perm = [self._perm("d", text[:i]) for i in range(len(text))]
            return "".join(p[c] for p, c in zip(perm, text, strict=True))
        lower = "".join(_fold(c) for c in text)
        if is_signal(lower):
            return text
        out = "".join(self._perm("a", lower[:i])[c] for i, c in enumerate(lower))
        self.runs[lower] = out
        return "".join(o.upper() if c.isupper() else o for o, c in zip(out, text, strict=True))

    def name(self, text: str) -> str:
        """A whole name: letter and digit runs replaced, IP addresses mapped, separators kept."""
        if text in KEPT_NAMES or text.lower().startswith("junos-") or not text:
            return text
        found = self.names.get(text)
        if found is None:
            parts, last = [], 0
            for match in IP_INSIDE.finditer(text):
                parts.append(RUN.sub(lambda m: self.run(m.group()), text[last : match.start()]))
                parts.append(self.ip(match.group()))
                last = match.end()
            parts.append(RUN.sub(lambda m: self.run(m.group()), text[last:]))
            found = self.names[text] = "".join(parts)
        return found

    # IP addresses

    def _flippable(self, version: int, bits: int, prefix: int, depth: int) -> bool:
        """No reserved range lies strictly below this node of the address tree."""
        for special in NON_PUBLIC:
            if special.version != version or special.prefixlen <= depth:
                continue
            if int(special.network_address) >> (bits - depth) == prefix:
                return False
        return True

    def _address(self, address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> str:
        value, bits, version = int(address), address.max_prefixlen, address.version
        out = 0
        for depth in range(bits):
            shift = bits - 1 - depth
            prefix = value >> (shift + 1)
            flip = self._flips.get((version, depth, prefix))
            if flip is None:
                flip = 0
                if self._flippable(version, bits, prefix, depth):
                    flip = self._prf("ip", str(version), str(depth), str(prefix))[0] & 1
                self._flips[(version, depth, prefix)] = flip
            out = (out << 1) | (((value >> shift) & 1) ^ flip)
        return str(ipaddress.ip_address(out) if version == 4 else ipaddress.IPv6Address(out))

    def ip(self, text: str) -> str:
        """An address (`10.1.2.3`) or a network (`10.1.2.0/24`); the text if it is neither."""
        found = self.ips.get(text)
        if found is not None:
            return found
        address, _, length = text.partition("/")
        try:
            parsed = ipaddress.ip_address(address)
        except ValueError:
            return text
        mapped = self._address(parsed)
        if length:
            if not length.isdigit() or int(length) > parsed.max_prefixlen:
                mapped = f"{mapped}/{length}"
            else:
                mapped = str(ipaddress.ip_network(f"{mapped}/{length}", strict=False))
        self.ips[text] = mapped
        return mapped

    # Dates

    def iso(self, text: str) -> str:
        if not self.shift:
            return text
        try:
            day = date.fromisoformat(text[:10])
        except ValueError:
            return text
        return (day - self.shift).isoformat() + text[10:]

    def bsd(self, text: str, year: int) -> str:
        """`Mar  4 10:00:00` shifted, in the year given (the year itself is not written)."""
        if not self.shift:
            return text
        month, rest = text[:3], text[3:]
        day_text, clock = rest.split()
        try:
            day = date(year, MONTHS.index(month) + 1, int(day_text)) - self.shift
        except ValueError:
            return text
        padded = rest.startswith("  ") or len(day_text) == 2
        day_out = f"{day.day:2d}" if padded else str(day.day)
        return f"{MONTHS[day.month - 1]} {day_out} {clock}"

    # Text

    def _word(self, word: str, mode: str) -> str:
        if word in self.known:
            return self.name(word)
        if mode == "generic":
            if word.lower() in JUNOS_WORDS or word.isdigit():
                return word
            return self.name(word)
        word = IP_INSIDE.sub(lambda m: self.ip(m.group()), word)
        if mode == "known":
            return word

        def free(match: re.Match[str]) -> str:
            run = match.group()
            lower = "".join(_fold(c) for c in run)
            if run.isdigit() or is_signal(lower):
                return run
            if lower in self.segments or (run.isupper() and len(run) >= 2):
                return self.run(run)
            self.kept_words.add(lower)
            return run

        return RUN.sub(free, word)

    def text(
        self, text: str, mode: str = "free", year: int | None = None, ports: bool = False
    ) -> str:
        """Rewrite TEXT. Modes: free (free text), known (only known names), generic (all).

        With `ports`, `/N` after an address is a port (log lines), not a prefix length.
        """

        def replace(match: re.Match[str]) -> str:
            kind, value = match.lastgroup, match.group()
            if kind == "bsd":
                return self.bsd(value, year) if year else value
            if kind == "date":
                return self.iso(value)
            if kind == "email":
                local, _, domain = value.partition("@")
                return f"{self.name(local)}@{self.name(domain)}"
            if kind in ("ip", "ip6"):
                if ports and "/" in value:
                    address, _, port = value.partition("/")
                    return f"{self.ip(address)}/{port}"
                return self.ip(value)
            if kind == "ticket":
                return self.name(value)
            if kind == "initials":
                if mode != "free":
                    return re.sub(r"[^\W_]+", lambda m: self._word(m.group(), mode), value)
                head, letters = value[: -len(value.split()[-1])], value.split()[-1]
                root = self._perm("a", "")
                return head + "".join(root[c.lower()].upper() for c in letters)
            if kind == "iface":
                return value
            return self._word(value, mode)

        return TOKENS.sub(replace, text)


def _letters(names: set[str]) -> set[str]:
    found = set()
    for name in names:
        for run in RUN.findall(name):
            lower = "".join(_fold(c) for c in run)
            if not run.isdigit() and len(lower) >= 2 and not is_signal(lower):
                found.add(lower)
    return found


def _config_names(config: Config) -> set[str]:
    found = set(config.addresses) | {a for a in config.applications if not a.startswith("junos-")}
    for policy in config.policies:
        found |= {policy.name, policy.from_zone, policy.to_zone}
        found |= set(policy.sources) | set(policy.destinations) | set(policy.applications)
    for obj in config.addresses.values():
        found |= set(obj.members) | {obj.book}
    return found


NAME_AFTER = ("security-zone", "from-zone", "to-zone", "host-name")


def _set_names(words: list[str]) -> set[str]:
    """Zone, address book, host and login names of one configuration line."""
    found = set()
    for i, (word, value) in enumerate(zip(words, words[1:], strict=False)):
        before = words[i - 1] if i else ""
        if (
            word in NAME_AFTER
            or (word == "address-book" and before == "security")
            or (word == "zone" and before == "attach")
            or (word == "user" and before == "login")
        ):
            found.add(value.strip('"'))
    return found


def known_names(directory: Path, dataset: Dataset) -> set[str]:
    """Every name the artifacts give a role to, from the files palimp reads."""
    found = _config_names(dataset.config)
    for config in read_rollbacks(directory / "rollbacks").values():
        found |= _config_names(config)
    for path in [directory / "config.set", *sorted((directory / "rollbacks").glob("*.set"))]:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            found |= _set_names(line.split())
    for commit in dataset.commits:
        found.add(commit.user)
        if commit.client not in COMMIT_CLIENTS:
            found.add(commit.client)
    for ticket in dataset.tickets.values():
        found |= {ticket.ticket_id, ticket.requester or "", ticket.assignee or ""}
        found.add(ticket.related_ci or "")
    for row in dataset.hit_counts:
        found |= {row.from_zone, row.to_zone, row.name}
    for summary in dataset.logs.values():
        found |= {summary.policy_name, summary.from_zone, summary.to_zone}
    log = directory / "logs" / "rt_flow.log"
    if log.is_file():
        for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
            for key, value in PAIR.findall(line):
                if key in LOG_NAME_KEYS and value not in LOG_CONSTANTS:
                    found.add(value)
    found |= set(vocabulary(dataset).aliases)
    found -= {""} | KEPT_NAMES | JUNOS_WORDS
    return {n for n in found if not n.lower().startswith("junos-")}


@dataclass
class Result:
    files: dict[str, str]  # relative path -> anonymized text
    mapper: Mapper
    skipped: list[str]
    salt: int


class _Rewriter:
    def __init__(self, mapper: Mapper, options: Options, log_year: int | None) -> None:
        self.m = mapper
        self.options = options
        self.log_year = log_year
        self._lines: dict[tuple[str, bool], str] = {}  # rollbacks repeat most lines

    # config.set and rollbacks

    def config(self, text: str) -> str:
        out = []
        for line in text.splitlines(keepends=True):
            body = line.rstrip("\r\n")
            ending = line[len(body) :]
            if PROMPT.match(body.strip()):
                out.append(self.m.text(body, "generic") + ending)
                continue
            if body.lstrip().startswith("#"):
                out.append(self.m.text(body, "free", self.log_year) + ending)
                continue
            words = body.split()
            if self.options.strip_text and "description" in words:
                continue
            security = words[1:3] in (
                ["security", "policies"],
                ["security", "address-book"],
                ["security", "zones"],
            ) or words[1:2] == ["applications"]
            out.append(self._set_line(body, security) + ending)
        return "".join(out)

    def _set_line(self, body: str, security: bool) -> str:
        found = self._lines.get((body, security))
        if found is None:
            found = self._lines[(body, security)] = self._rewrite_set_line(body, security)
        return found

    def _rewrite_set_line(self, body: str, security: bool) -> str:
        parts, last, previous = [], 0, ""
        for match in SET_TOKEN.finditer(body):
            parts.append(body[last : match.start()])
            last = match.end()
            quoted, word = match.group(1), match.group(2)
            if quoted is not None:
                if self.options.strip_text:
                    parts.append('""')
                elif security or previous in ("description", "message"):
                    parts.append(f'"{self.m.text(quoted, "free")}"')
                else:
                    parts.append(f'"{self.m.text(quoted, "generic")}"')
                previous = ""
                continue
            if previous in ("description", "message"):
                parts.append(self.m.text(word, "free"))
            elif previous in ("version", "time-zone"):
                parts.append(word)
            elif previous == "dns-name":
                parts.append(self.m.name(word))
            elif previous == "wildcard-address":
                address, _, mask = word.partition("/")
                parts.append(self.m.ip(address) + (f"/{mask}" if mask else ""))
            else:
                parts.append(self.m.text(word, "known" if security else "generic"))
            previous = word
        parts.append(body[last:])
        return "".join(parts)

    # commits.txt

    def commits(self, text: str) -> str:
        out = []
        for line in text.splitlines(keepends=True):
            body = line.rstrip("\r\n")
            ending = line[len(body) :]
            if not body.strip():
                out.append(line)
                continue
            if match := ENTRY.match(body):
                out.append(self._entry(body, match) + ending)
            elif RESCUE.match(body):
                out.append(self.m.text(body, "known") + ending)
            elif PROMPT.match(body.strip()):
                out.append(self.m.text(body, "generic") + ending)
            elif not self.options.strip_text:
                out.append(self.m.text(body, "free") + ending)
        return "".join(out)

    def _entry(self, body: str, match: re.Match[str]) -> str:
        index, stamp, zone, user, client, rest = match.groups()
        pieces = {
            2: self.m.iso(stamp),
            4: self.m.name(user),
            5: client if client in COMMIT_CLIENTS else self.m.name(client),
            6: self._commit_rest(rest),
        }
        parts, last = [], 0
        for group in sorted(pieces):
            parts.append(body[last : match.start(group)])
            parts.append(pieces[group])
            last = match.end(group)
        parts.append(body[last:])
        return "".join(parts)

    def _commit_rest(self, rest: str) -> str:
        """Text after the method: commit type and revision kept, the rest is free text."""
        kept = [m.span() for p in (CONFIRMED, ACTIVATE, REVISION) for m in p.finditer(rest)]
        parts, last = [], 0
        for start, end in sorted(kept):
            parts.append(self._free(rest[last:start]))
            parts.append(rest[start:end])
            last = end
        parts.append(self._free(rest[last:]))
        return "".join(parts)

    def _free(self, text: str) -> str:
        if self.options.strip_text:
            return " " if text.strip() else text
        return self.m.text(text, "free")

    # hitcount.txt

    def hitcount(self, text: str) -> str:
        return self.m.text(text, "known")

    # logs/rt_flow.log

    def log(self, text: str) -> str:
        out, year, previous_month = [], self.log_year, 0
        for line in text.splitlines(keepends=True):
            iso = re.search(r"(?<!\d)(\d{4})-\d{2}-\d{2}T", line)
            bsd = re.search(rf"\b({'|'.join(MONTHS)}) ", line)
            if iso:
                line_year: int | None = int(iso.group(1))
            else:
                if bsd and year:
                    month = MONTHS.index(bsd.group(1)) + 1
                    if month < previous_month:
                        year += 1
                    previous_month = month
                line_year = year
            out.append(self._log_line(line, line_year))
        return "".join(out)

    def _log_line(self, line: str, year: int | None) -> str:
        head, marker, body = line.partition("RT_FLOW")
        if not marker:
            return self.m.text(line, "generic", year)
        head = self.m.text(head, "generic", year)
        parts, last = [], 0
        for match in PAIR.finditer(body):
            parts.append(self.m.text(body[last : match.start()], "known", year))
            key, value = match.groups()
            if key in LOG_NAME_KEYS and value not in LOG_CONSTANTS:
                value = self.m.name(value)
            elif key != "reason":
                value = self.m.text(value, "known", year, ports=True)
            parts.append(f'{key}="{value}"')
            last = match.end()
        tail = body[last:]
        if parts:
            parts.append(self.m.text(tail, "known", year, ports=True))
        else:
            parts.append(" ".join(self._standard(token) for token in tail.split(" ")))
        return head + marker + "".join(parts)

    def _standard(self, token: str) -> str:
        """A token of a standard (not structured) RT_FLOW message."""
        if match := USER_ROLES.match(token):
            user, roles = match.groups()
            user = user if user in LOG_CONSTANTS else self.m.name(user)
            roles = roles if roles in LOG_CONSTANTS else self.m.name(roles)
            return f"{user}({roles})"
        return self.m.text(token, "known", ports=True)

    # tickets.csv

    def tickets(self, text: str) -> str:
        ending = "\r\n" if "\r\n" in text else "\n"
        rows = list(csv.reader(io.StringIO(text, newline="")))
        if not rows:
            return text
        header = rows[0]
        out = io.StringIO()
        writer = csv.writer(out, lineterminator=ending)
        writer.writerow(header)
        for row in rows[1:]:
            writer.writerow(
                [self._cell(header[i] if i < len(header) else "", v) for i, v in enumerate(row)]
            )
        return out.getvalue()

    def _cell(self, column: str, value: str) -> str:
        column = column.strip().lower()
        if not value or column in TICKET_KEPT_COLUMNS:
            return value
        if column in TICKET_DATE_COLUMNS:
            return self.m.iso(value)
        if column in TICKET_NAME_COLUMNS:
            return self.m.name(value)
        if column == "summary":
            return "" if self.options.strip_text else self.m.text(value, "free")
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}.*", value):
            return self.m.iso(value)
        return self.m.name(value)


def _shift(key: bytes) -> timedelta:
    digest = hmac.new(key, b"palimp date shift", hashlib.sha256).digest()
    return timedelta(weeks=1 + int.from_bytes(digest[:4], "big") % 520)


def _violations(mapper: Mapper) -> list[str]:
    """Replacement words that equal a kept signal word or a word kept in free text."""
    return sorted(
        f"{original} -> {out}"
        for original, out in mapper.runs.items()
        if len(out) >= 2 and (is_signal(out) or out in mapper.kept_words) and out != original
    )


def anonymize(
    directory: Path, key: bytes, options: Options | None = None, log_year: int | None = None
) -> Result:
    """Anonymized text of every artifact palimp reads in DIRECTORY (nothing is written)."""
    options = options or Options()
    directory = resolve_directory(directory)
    dataset = ingest(directory, log_year=log_year)
    known = known_names(directory, dataset)
    year = log_year
    if year is None and dataset.log_window.start is not None:
        year = dataset.log_window.start.year
    sources: dict[str, str] = {}
    skipped: list[str] = []
    for path in sorted(p for p in directory.rglob("*") if p.is_file()):
        relative = path.relative_to(directory).as_posix()
        rollback = relative.startswith("rollbacks/") and ROLLBACK_NAME.match(path.name)
        if relative in KNOWN_FILES or rollback:
            with path.open(encoding="utf-8", errors="replace", newline="") as handle:
                sources[relative] = handle.read()
        else:
            skipped.append(relative)
    for salt in range(MAX_SALT):
        mapper = Mapper(key=key, salt=salt, known=known, segments=_letters(known))
        if options.shift_dates:
            mapper.shift = _shift(key)
        rewriter = _Rewriter(mapper, options, year)
        files = {}
        for relative, text in sources.items():
            if relative == "config.set" or relative.startswith("rollbacks/"):
                files[relative] = rewriter.config(text)
            elif relative == "commits.txt":
                files[relative] = rewriter.commits(text)
            elif relative == "hitcount.txt":
                files[relative] = rewriter.hitcount(text)
            elif relative == "tickets.csv":
                files[relative] = rewriter.tickets(text)
            else:
                files[relative] = rewriter.log(text)
        if not _violations(mapper):
            return Result(files=files, mapper=mapper, skipped=skipped, salt=salt)
    raise RuntimeError("no mapping without a collision with a kept word, try another key")


NOTE = """This directory was anonymized by palimp {version} (palimp anonymize).

Names, IP addresses, people, logins, host names and ticket IDs were replaced
with keyed tokens. The same original value has the same replacement in every
file. Private addresses stay private, public addresses stay public, and two
addresses of one subnet stay in one subnet.
Free text: {text}.
Dates: {dates}.
The key and the mapping stay with the person who ran the command; neither is
needed to analyze this copy.
"""


def write(result: Result, out: Path, options: Options) -> None:
    for relative, text in result.files.items():
        path = out / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            handle.write(text)
    note = NOTE.format(
        version=__version__,
        text="removed"
        if options.strip_text
        else "kept, with known names, addresses and IDs replaced",
        dates="shifted by a secret number of whole weeks" if options.shift_dates else "kept",
    )
    with (out / "ANONYMIZED.txt").open("w", encoding="utf-8", newline="") as handle:
        handle.write(note)


def mapping_json(result: Result) -> str:
    mapper = result.mapper
    data = {
        "warning": "PRIVATE: this file links the anonymized copy back to the originals. "
        "Never share it.",
        "date_shift_days": -mapper.shift.days,
        "names": dict(sorted(mapper.names.items())),
        "ip_addresses": dict(sorted(mapper.ips.items())),
    }
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"
