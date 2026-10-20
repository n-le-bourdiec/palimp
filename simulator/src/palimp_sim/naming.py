"""Object, policy and description names as real rule bases show them (spec 2.5).

Medium and Hard only. Easy keeps the application convention of session 3
(`crm-web-01`, `users-to-crm-web`). Tests on 32 real public SRX
configurations (docs/real-configs-robustness.md) showed object names that
start with a site code (`EG-`, `ASC-`), a server role (`SQL01`), a person's
name, or a generic word (`main`, `local`, `Hosted-Networks`), policy names
that are ticket numbers or copies of an object name, and descriptions that
hold a ticket number only. Every choice here is drawn from the scenario's
`naming` sub-generator, so no other draw of the timeline moves.

Only part of the applications keep objects named after them
(`app_share`, drawn per scenario): the others get site and role names, so the
ground truth confidence model (sources.py) sees rules with zero, one or
several naming sources.
"""

from palimp_sim import voice
from palimp_sim.rng import Rng

# Invented site codes. None equals an application code or id (voice.APP_CODES).
SITE_CODES = (
    "EG", "FM", "KR", "LV", "NT", "OB", "PD", "RZ", "TW", "VD",
    "ASC", "BRV", "CLM", "DNX", "FNM", "GRT", "HLB", "MRD", "OKV", "TSR",
)  # fmt: skip
# Server role words per tier. None equals an application code (no `MX`,
# `NMS`, `NAS`), except the shared services named after their role.
ROLE_WORDS = {
    "web": ("WEB", "WWW"),
    "app": ("APP", "AS"),
    "db": ("SQL", "DB"),
    "file": ("FS", "FILE"),
    "relay": ("SMTP",),
    "mbx": ("MBX", "EXCH"),
    "dns": ("DNS", "NS"),
    "bkp": ("BKP", "BACKUP"),
    "mon": ("MON",),
    "jump": ("JMP", "BASTION"),
    "gw": ("GW", "SFTP"),
}
USERS_ALL = ("All-Users", "internal", "Corp-LAN", "LAN-ALL", "local-nets")
SERVER_RANGES = ("Hosted-Networks", "DC-Range", "srv-nets", "local", "main")
SITE_STYLES = ("{code}-LAN", "{code}-Users", "LAN-{code}", "{lower}_clients")
HOST_STYLES = ("{site}-{role}{n:02d}", "{role}{n:02d}", "srv-{lower}-{n:02d}")
SET_STYLES = ("{site}-{role}-Farm", "{role}-Servers-{n}", "{site}_{role}_GRP")
WORKSTATION_STYLES = (
    "LT-{first}-{last}",
    "PC-{f}{last}",
    "WS-{LAST}-{f}",
    "{first_l}-{last_l}-pc",
)
COMPANIES = ("Brightwave", "Norland-IT", "Calder-Systems", "Ostrava-Tech", "Velmora", "Quillon")
FREE_TEXTS = (
    "requested by {owner}",
    "per change board",
    "do not remove without asking network team",
    "project {project}",
    "see ticket",
    "ok'd by security",
)
PROJECTS = ("Atlas", "Heron", "Juniper Move", "Phoenix", "Northstar", "Bluebird")
# Policy name styles per persona (spec 2.5): the persona's own name, an
# application name, a zone-to-zone name, a ticket number, or a name built
# from an object name. Weights add up to 1.
POLICY_STYLES = {
    "meticulous_senior": (("own", 0.25), ("app", 0.2), ("zones", 0.2), ("ticket", 0.15),
                          ("object", 0.2)),
    "hurried_operator": (("own", 0.6), ("ticket", 0.2), ("object", 0.2)),
}  # fmt: skip
DESCRIPTION_STYLES = (("own", 0.55), ("ticket", 0.25), ("free", 0.2))
MAX_NAME = 63


def _pick(rng: Rng, weighted) -> str:
    return weighted[rng.weighted([w for _, w in weighted])][0]


def _service_word(service: str) -> str:
    if service.startswith("junos-"):
        return service.removeprefix("junos-").upper()
    return service.split("-", 1)[1]


class Namer:
    def __init__(self, rng: Rng, user_sites: int) -> None:
        self.rng = rng
        codes = rng.sample(SITE_CODES, 1 + user_sites)
        self.dc = codes[0]  # data center code: servers
        self.sites = codes[1:]  # one per user site
        self.app_share = rng.uniform(0.25, 0.6)
        self.host_styles = rng.sample(HOST_STYLES, 2)
        self.set_style = rng.choice(SET_STYLES)
        self.site_style = rng.choice(SITE_STYLES)
        self.workstation_styles = rng.sample(WORKSTATION_STYLES, 2)
        self.users_all = rng.choice(USERS_ALL)
        ranges = [r for r in SERVER_RANGES if r != self.users_all]
        self.servers_net = rng.choice(ranges)
        self.generic_hq = rng.chance(0.3)  # the first site is just `main` or `local`
        self._app_named: dict[str, bool] = {}
        self._app_style: dict[str, int] = {}
        self._memo: dict[tuple, str] = {}
        self._used: set[str] = {self.users_all, self.servers_net}
        self._counters: dict[str, int] = {}

    # ------------------------------------------------------------------ helpers

    def app_named(self, app_id: str) -> bool:
        """Whether the objects of this application are named after it (drawn once)."""
        if app_id not in self._app_named:
            self._app_named[app_id] = self.rng.chance(self.app_share)
            self._app_style[app_id] = self.rng.randint(0, 1)
        return self._app_named[app_id]

    def _unique(self, name: str) -> str:
        base, n = name[:MAX_NAME], 2
        while name in self._used:
            name = f"{base[: MAX_NAME - 3]}-{n}"
            n += 1
        self._used.add(name)
        return name

    def _number(self, key: str) -> int:
        self._counters[key] = self._counters.get(key, 0) + 1
        return self._counters[key]

    # ------------------------------------------------------------------ objects

    def hostname(self, app_id: str, shared: bool, tier: str, default: str) -> str:
        """Server address object (hostname). `default` is the Easy name."""
        if self.app_named(app_id):
            if self._app_style[app_id] == 0 or shared:
                return self._unique(default)
            code = voice.code(app_id)
            number = self._number(f"{code}-{tier}")
            role = ROLE_WORDS[tier][0]
            return self._unique(f"{self.dc}-{code}-{role}{number:02d}")
        role = self.rng.choice(ROLE_WORDS[tier])
        style = self.rng.choice(self.host_styles)
        while True:
            number = self._number(f"{style}{role}")
            name = style.format(site=self.dc, role=role, lower=role.lower(), n=number)
            if name not in self._used:
                self._used.add(name)
                return name

    def tier_set(self, app_id: str, tier: str, generation: int, default: str) -> str:
        """Address set of a tier with several servers (memoized: one per tier)."""
        key = ("set", app_id, tier, generation)
        if key not in self._memo:
            if self.app_named(app_id):
                name = default
            else:
                role = ROLE_WORDS[tier][0]
                number = self._number(f"set-{role}")
                name = self.set_style.format(site=self.dc, role=role, n=number)
            self._memo[key] = self._unique(name)
        return self._memo[key]

    def site(self, index: int) -> str:
        """User site subnet object (index from 1)."""
        key = ("site", index)
        if key not in self._memo:
            if index == 1 and self.generic_hq:
                name = "main" if "main" not in self._used else "local"
            else:
                code = self.sites[index - 1]
                name = self.site_style.format(code=code, lower=code.lower())
            self._memo[key] = self._unique(name)
        return self._memo[key]

    def workstation(self, person: str) -> str:
        """A named person's workstation (access requests)."""
        first, last = person.split(" ")
        style = self.rng.choice(self.workstation_styles)
        name = style.format(
            first=first,
            last=last,
            f=first[0],
            LAST=last.upper(),
            first_l=first.lower(),
            last_l=last.lower(),
        )
        return self._unique(name)

    def vendor(self, app_id: str, number: int, default: str) -> str:
        if self.app_named(app_id):
            return self._unique(default)
        company = self.rng.choice(COMPANIES)
        return self._unique(f"{company}-{self.rng.choice(('support', 'remote', 'VPN'))}")

    def app_net(self, app_id: str, index: int, default: str) -> str:
        """Subnet object an emergency rule opens."""
        if self.app_named(app_id):
            return self._unique(default)
        return self._unique(f"{self.dc}-VLAN{110 + index}")

    # ------------------------------------------------------------------ policies

    def policy_name(
        self, own: str, persona: str, app_id: str, flow, ticket_id: str | None, zones
    ) -> str:
        """Policy name in one of the styles real rule bases show (spec 2.5).

        `own` is the persona's name (kept for the automation account and the
        styles not drawn here). The caller makes it unique.
        """
        styles = POLICY_STYLES.get(persona)
        if styles is None:
            return own
        rng = self.rng
        style = _pick(rng, styles)
        if style == "app":
            code = voice.code(app_id)
            service = _service_word(flow.template.services[0])
            base = app_id.removeprefix("shared-")
            options = (code, f"{code}-{service}", f"{base}_access", f"Allow-{code}")
            return rng.choice(options)
        if style == "zones":
            source, target = zones
            return rng.choice((f"{source}-to-{target}", f"{source.upper()}_TO_{target.upper()}"))
        if style == "ticket":
            if ticket_id and rng.chance(0.7):
                return ticket_id
            return f"RITM{rng.randint(10000, 999999):07d}"
        if style == "object":
            source, target = flow.src.address, flow.dst.address
            if target == "any":
                target = source
            options = (f"Allow-{target}", target, f"{source}_to_{target}", f"to-{target}")
            name = rng.choice(options)
            return name if len(name) <= MAX_NAME else f"Allow-{target}"[:MAX_NAME]
        return own

    def description(self, own: str, ticket_id: str | None, owner: str) -> str:
        """A description as written, a ticket number alone, or free text."""
        rng = self.rng
        style = _pick(rng, DESCRIPTION_STYLES)
        if style == "ticket":
            if ticket_id:
                return ticket_id
            return f"RITM{rng.randint(10000, 999999):07d}"
        if style == "free":
            text = rng.choice(FREE_TEXTS)
            return text.format(owner=owner, project=rng.choice(PROJECTS))
        return own
