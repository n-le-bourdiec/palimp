"""Naming sources of a rule and the confidence they justify (spec 6.1).

Medium and Hard only; Easy keeps the tier rule of truth._confidence. The
model is the project lead's, stated in decisions 0042 to 0044 and restated
in spec 6.1 as simulator rules (the analyzer code is never read):

- a source names the rule's application when its text holds the
  application id or code as a token (`crm-web-01`, `EG-CRM-SQL01`, `CRM go
  live`);
- the address objects of both sides of the rule are one source, whatever
  they share (a site prefix on both sides is one naming convention);
- the policy name is a second source only when it does not repeat an
  address object name of the rule (separators and trailing numbers aside);
- a service whose port stands for the application (`SERVICE_SOURCES`) is a
  source that is not a name, as are the description or annotation, the
  retained creation commit comment and an exported ticket that one of them
  (or the policy name) cites;
- a source that names the application only by a two-letter name (`ci`,
  `bi`, `hr`, `kb`, `s4`) counts only next to a source that is not a name;
- one source gives at most LOW, two independent sources MEDIUM, and HIGH
  needs two sources, one of them a direct statement (description,
  annotation, comment, ticket), and traffic seen.
"""

import re
from dataclasses import dataclass

from palimp_sim import catalog, voice

# Services whose port stands for the application itself (a product or a
# shared service): simulator choices, documented in spec 6.1. A port alone
# never names a rule's application; next to a name it is a second source.
SERVICE_SOURCES = {
    "vault": ("tcp-8200",),  # HashiCorp Vault API port
    "mail": ("junos-smtp", "tcp-993"),
    "print": ("tcp-9100",),  # raw printing (JetDirect)
    "telephony": ("udp-5060",),  # SIP
    "shared-dns": ("junos-dns-udp",),
    "shared-ntp": ("junos-ntp",),
    "shared-monitoring": ("udp-161",),  # SNMP polling
    "shared-backup": ("tcp-10000",),  # NDMP
}
NAME_KINDS = ("objects", "policy_name")
DIRECT_KINDS = ("text", "comment", "ticket")


@dataclass(frozen=True)
class Source:
    kind: str  # objects, policy_name, service, text, comment, ticket
    short: bool  # names the application only by a two-letter name

    @property
    def name(self) -> bool:
        return self.kind in NAME_KINDS

    @property
    def direct(self) -> bool:
        return self.kind in DIRECT_KINDS


def tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _stem(token: str) -> str:
    """`sql01` is `sql`; a token of digits only stays as it is."""
    stem = token.rstrip("0123456789")
    return stem or token


def _base(app_id: str) -> str:
    """Template id of a regional instance (`erp-de` is `erp`)."""
    head, _, region = app_id.rpartition("-")
    return head if head and region in catalog.REGIONS else app_id


def forms(app_id: str) -> list[tuple[str, ...]]:
    """Token sequences that name an application: its id and its code."""
    found = [tuple(tokens(app_id.removeprefix("shared-"))), (voice.code(app_id).lower(),)]
    return list(dict.fromkeys(found))


def names(text: str | None, app_id: str) -> str | None:
    """None, "short" (only by a two-letter name) or "full"."""
    if not text:
        return None
    words = tokens(text)
    stems = [_stem(w) for w in words]
    matched = []
    for form in forms(app_id):
        size = len(form)
        for i in range(len(words) - size + 1):
            window = range(i, i + size)
            if all(form[k] in (words[j], stems[j]) for k, j in enumerate(window)):
                matched.append(form)
                break
    if not matched:
        return None
    short = all(len(form) == 1 and len(form[0]) == 2 for form in matched)
    return "short" if short else "full"


def _core(name: str) -> list[str]:
    """Stemmed tokens of a name without its trailing number tokens."""
    words = tokens(name)
    while words and words[-1].isdigit():
        words.pop()
    return [_stem(w) for w in words if not w.isdigit()]


def copies_object(policy_name: str, objects: list[str]) -> bool:
    """Whether a policy name repeats an address object name of its rule."""
    name = _core(policy_name)
    for obj in objects:
        core = _core(obj)
        size = len(core)
        if size and any(name[i : i + size] == core for i in range(len(name) - size + 1)):
            return True
    return False


def rule_sources(
    app_id: str,
    objects: list[str],
    policy_name: str,
    services: list[str],
    texts: list[str],
    comment: str | None,
    tickets: list[str],
) -> list[Source]:
    """Independent sources that name `app_id`.

    `objects`: the rule's address objects that may name an application
    (generic ones left out, address sets with their members); `texts`: the
    description, and the annotation where the output shows it; `comment`: the
    retained creation commit comment; `tickets`: related CIs of the exported
    tickets the rule cites.
    """
    found: list[Source] = []
    marks = [names(o, app_id) for o in objects]
    if any(marks):
        found.append(Source("objects", "full" not in marks))
    mark = names(policy_name, app_id)
    if mark and not copies_object(policy_name, objects):
        found.append(Source("policy_name", mark == "short"))
    key = app_id if app_id in SERVICE_SOURCES else _base(app_id)
    if set(SERVICE_SOURCES.get(key, ())) & set(services):
        found.append(Source("service", False))
    marks = [names(t, app_id) for t in texts]
    if any(marks):
        found.append(Source("text", "full" not in marks))
    mark = names(comment, app_id)
    if mark:
        found.append(Source("comment", mark == "short"))
    if app_id in tickets:
        found.append(Source("ticket", False))
    return found


def counted(found: list[Source]) -> list[Source]:
    """Sources that count: a two-letter name needs a source that is not a name."""
    backed = any(not s.name for s in found)
    return [s for s in found if not (s.name and s.short and not backed)]


def confidence(found: list[Source], traffic: bool) -> str:
    sources = counted(found)
    if len(sources) < 2:
        return "LOW"
    if traffic and any(s.direct for s in sources):
        return "HIGH"
    return "MEDIUM"
