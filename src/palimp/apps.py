"""Application names found in the artifacts, to tell which application a text or object names.

Plain rules, no scoring. Applications are learned from the input itself:
- the related CI column of tickets.csv (for example `webshop`);
- short names used in ticket summaries, mapped to the related CI of the same
  ticket (`Decom ESHOP` with related CI `webshop` gives `eshop` -> `webshop`).
  A short name seen with two different related CIs is ambiguous and dropped;
- the first segment of address object names (`crm-db-01` gives `crm`), unless
  it is a role word such as `pc`, `users` or `servers`. A segment that is
  already a ticket alias (`bkp-01` with tickets `BKP ...` for `backup`) names
  that application. A segment of at least 3 letters that is the start of
  exactly one related CI is an abbreviation of it (`mon-01` with related CI
  `shared-monitoring` gives `mon` -> `monitoring`). Shorter segments are never
  read as abbreviations (`bi` must not name `billing`).

A token names an application when it is one of the learned names or aliases.
Free text gets no prefix matching: `web` must not name `webshop`.

Name filters (session 27, decision 0042). Real object names often start with a
zone, a place, a person or a generic word (`addr-`, `dmz-`, `local-`), not
with an application. A name learned from object names alone is never shorter
than MIN_NAME letters, never one of GENERIC_WORDS and never a server role
(SERVER_ROLES: `sql`, `web`, `jump` say what a host does, not which application
it serves), nor a word of a zone name (`Security_52` names a zone). Names
tickets.csv backs (related CIs, their bare regional names,
ticket short names and abbreviations of a related CI) are kept whatever their
length or word: a ticket is an explicit source.

Products and application names (session 28). A product name (PRODUCTS: `redis`,
`nessus`, `oracle`, `sap`) names an application in any object, policy or
application name, zone names included; free text is read as before (a commit
comment that mentions `ansible` is about the tool, not the rule). The first
segment of custom application and application-set names is learned like that
of address object names (`REDIS` names redis, `CRM-PORTS` crm).

Regional instances (session 24). Related CIs such as `payroll-uk` and
`hr-de` end with a two-letter instance suffix; the suffixes seen this way are
learned. A name followed by a learned suffix (`payroll-pl-app-01`,
`fw-bi-nl`) names that instance, `payroll-pl`, even when no ticket names it:
an exact match. A bare name is never expanded to one of its instances
(`payroll` does not name `payroll-uk`). A bare name that is not itself a
related CI while instances of it exist is ambiguous: `candidates` lists the
instances it may stand for, and confidence is capped (palimp.assess).
"""

import re
from dataclasses import dataclass, field

from palimp.models import Dataset

# Words that say who or what kind of host or network, not which application.
ROLE_WORDS = frozenset(
    {
        "pc",
        "server",
        "servers",
        "srv",
        "mgmt",
        "lan",
        "subnet",
        "ws",
        "user",
        "users",
        "vendor",
        "partner",
        "host",
        "hosts",
        "net",
        "network",
        "any",
        "all",
        "grp",
        "group",
        "h",
        "n",
        "shared",
        "new",
        "old",
    }
)
# Generic network words: where a host sits or what kind of object it is, never
# which application it serves (decision 0042). The one list used for object
# names, policy names and application names. ROLE_WORDS above stays filtered
# everywhere, even for a related CI; these words are filtered unless
# tickets.csv names them.
GENERIC_WORDS = frozenset(
    """
    addr address addresses obj object objects range ranges set sets list pool prefix
    ips hst ip ipv4 ipv6 nets subnets vlan vlans segment seg zone zones groups networks
    main dmz local remote inside outside internal external trust untrust trusted
    untrusted wan edge core public private priv pub site office branch hq campus corp
    corporate cloud internet inet guest guests wifi wireless home lab management oob
    transit
    prod production dev devel development test testing uat qa stage staging preprod pre
    sandbox demo dr
    client clients workstation workstations desktop desktops laptop laptops device
    devices node nodes vm vms member members partners vendors customer customers staff
    admin admins employee employees contractor contractors
    none other others misc default generic common temp tmp bad good allow allowed deny
    denied block blocked permit src source dst dest destination from to and the for
    primary secondary vip nat snat dnat static dynamic vpn tunnel ipsec ssl traffic
    access outbound inbound out in
    tcp udp icmp proto protocol port ports svc service services custom junos
    """.split()
)
# Product names (session 28): software that names what a host runs, not a role
# (`redis`, `nessus`, `oracle`, `sap`). A product name is an application in any
# object, policy or application name, even one that is also a zone name word
# (`REDIS-DMZ-PRIV` is the zone of the redis servers). Free text is not affected.
PRODUCTS = frozenset(
    """
    redis nessus tenable qualys rapid7 oracle sap hana mysql mssql postgres postgresql
    mongodb mongo mariadb sybase teradata elasticsearch elastic kibana logstash splunk
    graylog zabbix nagios prometheus grafana solarwinds prtg jenkins gitlab github
    bitbucket jira confluence sharepoint exchange citrix vmware vcenter esxi veeam
    commvault netbackup kafka rabbitmq vault tableau salesforce workday servicenow
    crowdstrike sccm wsus okta docker kubernetes ansible puppet saltstack nexus
    artifactory sonarqube tomcat nginx weblogic websphere jboss informatica cognos
    """.split()
)
# Server roles: what a host does, not which application it serves. With no
# application named, an intent may describe the flow by its roles ("SMB file
# sharing between SQL servers"). Each word maps to the label used in that text.
SERVER_ROLES: dict[str, str] = {
    "sql": "SQL",
    "db": "database",
    "dbs": "database",
    "database": "database",
    "web": "web",
    "www": "web",
    "http": "web",
    "app": "application",
    "apps": "application",
    "jump": "jump",
    "jumphost": "jump",
    "jumpbox": "jump",
    "bastion": "jump",
    "proxy": "proxy",
    "dns": "DNS",
    "ns": "DNS",
    "ntp": "NTP",
    "mail": "mail",
    "smtp": "mail",
    "mx": "mail",
    "backup": "backup",
    "bkp": "backup",
    "file": "file",
    "fs": "file",
    "nas": "file",
    "ftp": "FTP",
    "sftp": "FTP",
    "print": "print",
    "printer": "print",
    "ldap": "directory",
    "radius": "RADIUS",
    "syslog": "log",
    "log": "log",
    "nms": "monitoring",
    "snmp": "monitoring",
    "storage": "storage",
    "san": "storage",
    "lb": "load balancer",
    "router": "router",
    "fw": "firewall",
    "firewall": "firewall",
}
# Roles read only when the rule matches the service they offer (session 29): `ad`
# is Active Directory on LDAP or Kerberos, and may be anything else otherwise (a site,
# a team). Word -> (label, port names of the service).
CONDITIONAL_ROLES: dict[str, tuple[str, frozenset[str]]] = {
    "ad": ("directory", frozenset({"ldap", "kerberos"})),
}
# Hosting platforms (session 31): where an application runs, not which one it is
# (`GIT-AZURE-MS-SQL` is SQL hosted in Azure).
HOSTING = frozenset({"azure", "aws", "gcp", "oci"})
# Shortest name read as an application when no ticket backs it.
MIN_NAME = 3


def not_an_application(token: str) -> bool:
    """A word that never names an application unless tickets.csv backs it (decision 0042)."""
    token = token.lower()
    if token in PRODUCTS:
        return False
    return (
        len(token) < MIN_NAME
        or token in ROLE_WORDS
        or token in GENERIC_WORDS
        or token in SERVER_ROLES
        or token in HOSTING
    )


def roles(name: str, ports: frozenset[str] = frozenset()) -> list[str]:
    """Server roles a name states, as labels (`sql01-a` gives `SQL`). A plural or a
    trailing number is read as the word (`printers`, `web2`). A conditional role
    (`ad`) is read only when PORTS, the port names of the rule, hold its service."""
    found = []
    for token in re.split(r"[-_.]", name.lower()):
        word = re.sub(r"\d+$", "", token)
        label = SERVER_ROLES.get(word) or (
            SERVER_ROLES.get(word[:-1]) if word.endswith("s") else None
        )
        if word in CONDITIONAL_ROLES and CONDITIONAL_ROLES[word][1] & ports:
            label = CONDITIONAL_ROLES[word][0]
        if label and label not in found:
            found.append(label)
    return found


TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9]*")
SHORT_NAME = re.compile(r"\b[A-Z][A-Z0-9]{1,9}\b")
TICKET_ID = re.compile(r"^(?:CHG|INC|RITM|REQ|CR|SR|TASK)\d*$")


@dataclass
class Vocabulary:
    names: set[str] = field(default_factory=set)
    aliases: dict[str, str] = field(default_factory=dict)
    # Related CIs of tickets.csv, and the instance suffixes they use (`uk`, `pl`).
    cis: set[str] = field(default_factory=set)
    regions: set[str] = field(default_factory=set)
    # Bare name -> its instances (`payroll` -> `payroll-pl`, `payroll-uk`).
    instances: dict[str, list[str]] = field(default_factory=dict)
    # Names and aliases tickets.csv backs: kept through the name filters.
    backed: set[str] = field(default_factory=set)
    # Words of the zone names (`Security_52` gives `security`): a zone, not an application.
    zone_words: set[str] = field(default_factory=set)
    # Two-letter first segments (`bi`, `hr`): names only when a second source confirms
    # them, never alone (decision 0043).
    short: set[str] = field(default_factory=set)

    def short_in(self, name: str) -> list[str]:
        """Two-letter names of `short` in an object, policy or application name. A name
        the vocabulary already knows (a ticket names `hr`) is read by `in_object`."""
        tokens = [t.lower() for t in re.split(r"[-_.]", name)]
        return list(dict.fromkeys(t for t in tokens if t in self.short and t not in self.names))

    def short_in_text(self, text: str) -> list[str]:
        """Two-letter names of `short` in free text (a description, an annotation)."""
        tokens = re.findall(r"[a-z0-9]+", (text or "").lower())
        return list(dict.fromkeys(t for t in tokens if t in self.short and t not in self.names))

    def lookup(self, token: str, name: bool = False) -> str | None:
        """The application TOKEN names. With NAME (an object, policy or application
        name, not free text), a product name always names itself."""
        token = token.lower()
        if token in ROLE_WORDS:
            return None
        if name and token in PRODUCTS:
            return token
        if token not in self.backed and (not_an_application(token) or token in self.zone_words):
            return None
        if token in self.names:
            return token
        return self.aliases.get(token)

    def _apps(self, tokens: list[tuple[str, bool]], name: bool = False) -> list[str]:
        """Applications named by TOKENS, each with whether it is joined to the next one
        by `-` or `_` (`payroll` + `pl` gives the instance `payroll-pl`)."""
        found: list[str] = []
        i = 0
        while i < len(tokens):
            token, joined = tokens[i]
            token = token.lower()
            after = tokens[i + 1][0].lower() if joined and i + 1 < len(tokens) else ""
            app = self.lookup(token, name)
            if after and self.regions and f"{token}-{after}" in self.names | self.cis:
                app, i = f"{token}-{after}", i + 1
            elif app and after in self.regions:
                app, i = f"{self.base(app)}-{after}", i + 1
            if app and app not in found:
                found.append(app)
            i += 1
        return found

    def base(self, app: str) -> str:
        """`payroll-uk` gives `payroll`; a name with no instance suffix is its own base."""
        head, _, tail = app.rpartition("-")
        return head if head and tail in self.regions else app

    def candidates(self, app: str) -> list[str]:
        """Instances a bare name may stand for, when it is ambiguous; [] otherwise."""
        if app in self.cis:
            return []
        return [i for i in self.instances.get(app, []) if i != app]

    def in_text(self, text: str) -> list[str]:
        """Applications named in free text (comment, description, ticket summary)."""
        text = text or ""
        tokens: list[tuple[str, bool]] = []
        matches = [m for m in TOKEN.finditer(text) if not TICKET_ID.match(m.group().upper())]
        for m, nxt in zip(matches, [*matches[1:], None], strict=False):
            joined = nxt is not None and text[m.end() : nxt.start()] in ("-", "_")
            tokens.append((m.group(), joined))
        return self._apps(tokens)

    def in_application(self, name: str) -> list[str]:
        """Applications named by a custom application or application-set name. A product
        written in two words (`MS-SQL-PORT-GROUP` gives mssql) names it too (session 31)."""
        found = self.in_object(name)
        if found:
            return found
        tokens = [t.lower() for t in re.split(r"[-_.]", name) if t.isalpha()]
        joined = [a + b for a, b in zip(tokens, tokens[1:], strict=False)]
        return list(dict.fromkeys(j for j in joined if j in PRODUCTS))

    def in_object(self, name: str) -> list[str]:
        """Applications named by an address object name, for example `vendor-bi-52`."""
        tokens: list[tuple[str, bool]] = []
        for token in re.split(r"[-_.]", name):
            if not token.isalpha():
                if tokens:
                    tokens[-1] = (tokens[-1][0], False)
                continue
            tokens.append((token, True))
        return self._apps(tokens, name=True)


def _ci(value: str | None) -> str | None:
    """Related CI as an application name: `shared-dns` gives `dns`."""
    if not value:
        return None
    value = value.strip().lower()
    return value.removeprefix("shared-") or None


# Shortest object name segment read as an abbreviation of a related CI.
MIN_ABBREVIATION = 3


def vocabulary(dataset: Dataset, instances: bool = True) -> Vocabulary:
    """The applications of DATASET. Without `instances`, regional instances are not
    learned: the reading before session 24, kept for positive not-live signals
    (palimp.notlive, palimp.lineage) until the project lead approves the move."""
    vocab = Vocabulary()
    for ticket in dataset.tickets.values():
        if app := _ci(ticket.related_ci):
            vocab.names.add(app)
    vocab.cis = set(vocab.names)
    for ci in vocab.cis if instances else ():
        head, _, tail = ci.rpartition("-")
        if head and len(tail) == 2 and tail.isalpha() and tail not in ROLE_WORDS:
            vocab.regions.add(tail)
    cis = sorted(vocab.names)
    seen: dict[str, set[str]] = {}
    for ticket in dataset.tickets.values():
        app = _ci(ticket.related_ci)
        if not app:
            continue
        for short in SHORT_NAME.findall(ticket.summary or ""):
            if not TICKET_ID.match(short):
                seen.setdefault(short.lower(), set()).add(app)
    for short, apps in seen.items():
        if len(apps) == 1 and short not in vocab.names and short not in ROLE_WORDS:
            vocab.aliases[short] = next(iter(apps))
    vocab.backed = set(vocab.names) | set(vocab.aliases)
    for policy in dataset.config.policies:
        zones = [policy.from_zone, policy.to_zone, *policy.match_from_zones]
        for zone in zones + policy.match_to_zones:
            vocab.zone_words.update(re.split(r"[-_.]", zone.lower()))
    # Address object names, then custom application and application-set names: both
    # are names a person chose for what the rule serves (session 28).
    custom = [n for n in dataset.config.applications if not n.lower().startswith("junos-")]
    for name in [*dataset.config.addresses, *custom]:
        first = re.split(r"[-_.]", name.lower())[0]
        if not first.isalpha() or len(first) < 2 or first in ROLE_WORDS:
            continue
        if (
            len(first) == 2
            and first not in GENERIC_WORDS
            and first not in SERVER_ROLES
            and first not in CONDITIONAL_ROLES
            and first not in vocab.zone_words
            and first not in vocab.backed
        ):
            vocab.short.add(first)
        if first in vocab.names or first in vocab.aliases:
            continue
        if any(vocab.base(ci) == first for ci in cis if ci != first):
            vocab.names.add(first)  # the bare name of regional instances, never one of them
            vocab.backed.add(first)
            continue
        expanded = [ci for ci in cis if ci.startswith(first)]
        if len(first) >= MIN_ABBREVIATION and len(expanded) == 1:
            vocab.aliases[first] = expanded[0]
            vocab.backed.add(first)
        elif not not_an_application(first) and (first not in vocab.zone_words or first in PRODUCTS):
            vocab.names.add(first)
    found = set(vocab.cis)
    for name in dataset.config.addresses:
        found.update(vocab.in_object(name))
    for app in sorted(found):
        if (base := vocab.base(app)) != app:
            vocab.instances.setdefault(base, []).append(app)
    return vocab
