"""Visible texts in the voice of whoever wrote them.

Policy descriptions, commit comments and ticket summaries are built from
structured facts (application code, tier, port, ticket, requester initials),
never from the ground truth summaries, so the ground truth does not leak into
the artifacts. Each persona has its own vocabulary and habits (spec section 3).
"""

from palimp_sim.catalog import service_port
from palimp_sim.rng import Rng

APP_CODES = {
    "crm": "CRM",
    "erp": "ERP",
    "intranet": "INTRA",
    "hr": "HRP",
    "files": "FILESRV",
    "billing": "BILL",
    "webshop": "ESHOP",
    "mail": "MX",
    "wiki": "WIKI",
    "servicedesk": "SDESK",
    "payroll": "PAYR",
    "reporting": "RPT",
    "lms": "LMS",
    "dms": "DMS",
    "pos": "POS",
    "wms": "WMS",
    "tms": "TMS",
    "gitlab": "GIT",
    "ci": "CI",
    "edi": "EDI",
    "shared-dns": "DNS",
    "shared-ntp": "NTP",
    "shared-internet": "INET",
    "shared-backup": "BKP",
    "shared-monitoring": "NMS",
}

TIER_WORDS = {
    "web": ("FE", "web fe", "frontend"),
    "app": ("AS", "app srv", "backend"),
    "db": ("DB", "dbsrv", "SQL"),
    "file": ("FS", "filer", "share"),
    "relay": ("MTA", "smtp gw", "edge mta"),
    "mbx": ("MBX", "mailstore", "imap srv"),
    "dns": ("NS", "resolvers", "ns cluster"),
    "bkp": ("bkp srv", "media agent", "BKP"),
    "mon": ("NMS", "poller", "mon srv"),
    "gw": ("GW", "b2b gw", "sftp gw"),
}

SOURCE_WORDS = {
    "users": ("LAN", "office LAN", "user VLANs", "all sites", "staff"),
    "internet": ("inet", "any ext", "ext clients"),
    "servers-net": ("srv range", "DC range", "all srv"),
}

PARTNER_WORDS = {
    "bank-sftp": ("ext bank", "bank gw", "BNK"),
    "payroll-provider": ("ext payprov", "provider", "PPV"),
    "ntp-pool": ("ext NTP", "pool.ntp", "time src"),
    "carrier-api": ("carrier", "ext api", "CARR"),
    "package-mirror": ("pkg mirror", "repo ext", "artifactory ext"),
    "edi-partner": ("EDI cust", "b2b peer", "PARTNER01"),
}

STOP_WORDS = {"a", "an", "the", "to", "of", "for", "from", "and", "with", "its", "on", "in", "by"}


def initials(name: str) -> str:
    return "".join(part[0] for part in name.split()).upper()


def code(app_id: str) -> str:
    return APP_CODES.get(app_id, app_id.upper())


def port_words(service: str) -> str:
    protocol, port = service_port(service)
    return f"{port}/udp" if protocol == "udp" else str(port)


def endpoint_words(token: str, app_id: str, rng: Rng) -> str:
    if token in SOURCE_WORDS:
        return rng.choice(SOURCE_WORDS[token])
    if token.startswith("partner:"):
        return rng.choice(PARTNER_WORDS[token.split(":", 1)[1]])
    tier = rng.choice(TIER_WORDS[token])
    return tier if app_id.startswith("shared-") else f"{code(app_id)} {tier}"


def typo(text: str, rng: Rng, rate: float) -> str:
    """Swap two adjacent letters in some words (hurried personas)."""
    words = []
    for word in text.split(" "):
        if len(word) > 3 and word.isalpha() and rng.chance(rate):
            i = rng.randint(0, len(word) - 2)
            word = word[:i] + word[i + 1] + word[i] + word[i + 2 :]
        words.append(word)
    return " ".join(words)


def description(persona: str, flow, ticket_id: str | None, requester: str, rng: Rng) -> str:
    """Policy description for one flow, in the admin's voice."""
    src = endpoint_words(flow.template.src, flow.app_id, rng)
    dst = endpoint_words(flow.template.dst, flow.app_id, rng)
    ports = "+".join(port_words(s) for s in flow.template.services)
    if persona == "meticulous_senior":
        text = rng.choice(
            (
                f"{src} > {dst} {ports}",
                f"{code(flow.app_id)} - {ports} from {src}",
                f"allow {src} to {dst} ({ports})",
            )
        )
        if ticket_id and rng.chance(0.5):
            text += f" [{ticket_id}]"
        if rng.chance(0.3):
            text += f" req {initials(requester)}"
        return text
    if persona == "hurried_operator":
        return typo(rng.choice((f"{code(flow.app_id)} acess", f"for {dst}", "temp")), rng, 0.4)
    if persona == "contractor":
        return f"{code(flow.app_id)} lot {rng.randint(1, 4)}"
    if persona == "automation":
        return f"managed: {flow.app_id}/{flow.template.dst}"
    return rng.choice(("urgent", "temp", "see INC"))


def commit_comment(
    persona: str, kind: str, app_id: str | None, ticket_id: str | None, rng: Rng, **facts
) -> str:
    """Commit comment for one event, in the admin's voice."""
    app = code(app_id) if app_id else ""
    if persona == "meticulous_senior":
        options = {
            "new_app": (
                f"{app} go-live, {facts.get('rules', 0)} rules",
                f"new {app} flows",
                f"{app}: initial rules",
            ),
            "shared": (f"{app} base rules", f"{app} flows"),
            "decommission": (f"{app} decom", f"retire {app}"),
            "migration": (f"{app} new hosts", f"{app} migration step 1"),
            "migration_cleanup": (f"{app} old hosts cleanup", f"{app} migration step 2"),
            "admin_join": (f"new admin acct {facts.get('login')}",),
            "admin_leave": (f"acct {facts.get('login')} removed",),
            "upgrade": (f"post upgrade {facts.get('version')}",),
            "snmp": ("snmp comm rotation",),
            "banner": ("banner update",),
            "syslog_add": ("syslog: add collector",),
            "syslog_remove": ("syslog: remove old collector",),
        }[kind]
        text = rng.choice(options)
        if facts.get("requester") and rng.chance(0.3):
            text += f" (req {initials(facts['requester'])})"
        return f"{ticket_id} {text}" if ticket_id else text
    if persona == "hurried_operator":
        return typo(
            rng.choice(("fix", "upd", "as requested", "add rule", f"{app} stuff")), rng, 0.4
        )
    if persona == "contractor":
        return f"MEP {app}".strip()
    if persona == "automation":
        return f"managed by ansible, run {rng.randint(100, 9999)}"
    if persona == "on_call":
        return rng.choice(("urgent", f"INC{rng.randint(10000, 99999):07d}", ""))
    return rng.choice(("cleanup", "remove unused"))


def ticket_summary(category: str, app_id: str, rng: Rng) -> str:
    """Ticket summary in the requester's voice (business user, vague)."""
    app = code(app_id)
    options = {
        "change": (
            f"FW request {app} go live",
            f"Need network access for {app}",
            f"{app} - open flows pls",
        ),
        "decommission": (f"Decom {app}", f"{app} retirement - remove access"),
        "migration": (f"{app} srv migration - FW part", f"Move {app} to new hosts"),
    }[category]
    return rng.choice(options)
