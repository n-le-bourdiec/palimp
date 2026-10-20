"""Rules that serve no application flow (decision 0045, spec 4.11). Medium and Hard.

Real configurations (docs/real-configs-robustness.md, session 29) hold deny
and reject rules, catch-all deny rules at the end of a zone pair, broad
permits (any source, any destination, any application) and Junos factory
default policies. This mixin adds them to the Medium and Hard timelines with
their own sub-generator (`rule-kinds`), so the draws of the application
timeline and of the traps do not move.

Placement keeps every trap mechanism as it was:

- a specific deny goes on top of its zone pair and matches only services or
  sources no application flow uses (`telnet`, `ftp`, `rdp`, `tftp`, an
  outside range in 198.51.100.0/24 that no partner uses);
- catch-all deny rules, broad permits and factory defaults are `tail`
  policies: they stay last in their zone pair, so they carry only traffic no
  rule above them matches, and never in a zone pair a global policy covers
  (from the management zone, servers to internet);
- each rule carries its own `extra` flow (blocked attempts, or traffic only
  the broad permit lets through), counted from its own generator in
  traffic.py, from zone-wide prefixes that no application rule matches.

All these rules belong to the firewall team (`FIREWALL`, owner
`FIREWALL_OWNER`) and are protected from hit count cleanups (nobody removes
a deny or an any/any permit on hit counts alone). Some specific deny rules
are deactivated later.
"""

from palimp_sim import voice
from palimp_sim.catalog import FlowTemplate
from palimp_sim.junos import ANY, Policy
from palimp_sim.model import Endpoint, Flow, PolicyMeta

NEW_KINDS = ("block", "cleanup_deny", "broad_permit", "factory_default")
FIREWALL = "firewall"  # pseudo application of the firewall team's own rules
FIREWALL_OWNER = "firewall_team"
FIREWALL_APP = {"app_id": FIREWALL, "name": "Firewall team rules", "owner_id": FIREWALL_OWNER}

# Instances per scenario: weights of 0, 1, 2, ... (simulator choices).
KIND_COUNT_WEIGHTS = {
    "medium": {
        "denies": (0.3, 0.3, 0.25, 0.15),
        "host_blocks": (0.6, 0.3, 0.1),
        "cleanups": (0.4, 0.3, 0.2, 0.1),
        "broad": (0.55, 0.3, 0.15),
    },
    "hard": {
        "denies": (0.1, 0.2, 0.25, 0.2, 0.15, 0.1),
        "host_blocks": (0.4, 0.4, 0.2),
        "cleanups": (0.25, 0.3, 0.25, 0.2),
        "broad": (0.35, 0.35, 0.2, 0.1),
    },
}
FACTORY_RATE = 0.5  # scenarios whose zones are named trust and untrust
FACTORY_SAMPLE_RATE = 0.5  # `trust-to-untrust` only (FACTORY-1), else `default-permit` twice
DENY_DEACTIVATE_RATE = 0.2
REJECT_RATE = 0.2
UNDOCUMENTED_RATE = 0.6  # a broad permit or factory default still carries traffic
BROAD_LOG_RATE = 0.3

ZONE_PREFIXES = {
    "users": "10.10.0.0/16",
    "servers": "10.20.0.0/15",
    "dmz": "172.16.10.0/24",
    "management": "10.30.0.0/24",
    "restricted": "10.40.0.0/24",
    "internet": "0.0.0.0/0",
}
ZONE_NET_NAMES = {
    "dmz": ("DMZ-Net", "{dc}-DMZ", "dmz-range"),
    "management": ("MGMT-Net", "{dc}-MGMT", "mgmt-range"),
    "restricted": ("Secure-Net", "{dc}-SECURE", "secure-range"),
}
# Specific deny rules on a service: (from role, to role, source, services).
SERVICE_BLOCKS = (
    ("users", "servers", "users", ("junos-telnet", "junos-ftp", "tcp-3389", "udp-69")),
    ("internet", "dmz", "any", ("junos-telnet", "junos-ftp", "tcp-3389")),
    ("users", "management", "users", ("junos-telnet", "tcp-3389")),
    ("dmz", "servers", "dmz", ("junos-telnet", "tcp-3389", "tcp-445")),
    ("users", "restricted", "users", ("junos-telnet", "tcp-3389", "tcp-445")),
    ("dmz", "restricted", "dmz", ("junos-telnet", "tcp-3389", "tcp-445")),
)
SERVICE_WORDS = {
    "junos-telnet": "telnet",
    "junos-ftp": "ftp",
    "tcp-3389": "rdp",
    "udp-69": "tftp",
    "tcp-445": "smb",
}
# Outside ranges that attack the company (RFC 5737, away from ntp-pool .123
# and package-mirror .200).
HOSTILE = ("198.51.100.64/27", "198.51.100.13/32", "198.51.100.37/32", "198.51.100.96/28")
HOSTILE_NAMES = ("blocked-hosts", "BLACKLIST", "bad-actors", "Block-{ip}")
HOST_BLOCK_PAIRS = (("internet", "dmz"), ("internet", "servers"))
CLEANUP_PAIRS = (
    ("internet", "dmz"),
    ("internet", "servers"),
    ("users", "servers"),
    ("dmz", "servers"),
    ("users", "management"),
    ("users", "dmz"),
    ("dmz", "internet"),
)
BROAD_PAIRS = (
    ("users", "internet"),
    ("users", "dmz"),
    ("dmz", "internet"),
    ("dmz", "servers"),
    ("users", "management"),
)
CLEANUP_SERVICES = ("tcp-5900", "tcp-6667", "udp-1900", "tcp-8888")
UNDOCUMENTED_SERVICES = ("junos-ssh", "tcp-8443", "udp-1194", "tcp-5000", "tcp-8081")
CLEANUP_NAMES = ("deny-all", "cleanup", "DENY-ANY", "default-deny", "explicit-deny", "drop-all")
BROAD_NAMES = ("allow-all", "any-any", "permit-all", "ALLOW_ANY", "TEMP-ANY", "test-any-any")
SUMMARIES = {
    "service": "Security policy refusing a legacy or risky protocol between two zones",
    "host": "Security policy refusing every session from an outside range known as hostile",
    "cleanup_deny": "Explicit last rule of the zone pair, refusing what the rules above it "
    "do not allow",
    "broad_permit": "Rule that permits any traffic between two zones; its purpose was never "
    "recorded",
    "factory_default": "Permit-all policy left from the Junos factory default configuration",
    "undocumented": "Traffic nobody documented, which only a permit-all rule lets through",
}


class RuleKindsMixin:
    """Deny, catch-all deny, broad permit and factory default rules."""

    # ------------------------------------------------------------------ helpers

    def _kind_admin(self, day: int):
        everyday = ("meticulous_senior", "hurried_operator")
        active = [a for a in self.admins if a.active(day) and a.persona in everyday]
        return self.rng_kinds.choice(active)

    def _zone_object(self, role: str) -> str:
        """Address object of a whole zone (generic: it names no application)."""
        if role == "users":
            return self._users_endpoint().address
        if role == "servers":
            return self._endpoint("servers-net", None).address
        if role == "internet":
            return ANY
        key = ("zone-net", role)
        if key not in self.namer._memo:
            style = self.rng_kinds.choice(ZONE_NET_NAMES[role])
            name = self.namer._unique(style.format(dc=self.namer.dc))
            self.namer._memo[key] = name
        name = self._ensure_address(self.namer._memo[key], ZONE_PREFIXES[role])
        self.generic_names.add(name)
        return name

    def _extra_flow(self, src_role, src_prefix, dst_role, dst_prefix, service, kind, start, key):
        """Traffic of a rule kind (blocked attempts or undocumented use)."""
        rng = self.rng_kinds
        summary = SUMMARIES[key]
        template = FlowTemplate(
            f"zone:{src_role}",
            f"zone:{dst_role}",
            (service,),
            rng.choice(("business", "always")),
            rng.randint(1, 8) if kind != "unknown_origin" else rng.randint(5, 60),
            kind,
            summary,
        )
        src = Endpoint(src_role, ANY, [src_prefix], src_role)
        dst = Endpoint(dst_role, ANY, [dst_prefix], dst_role)
        flow = Flow(self.next_id("F"), FIREWALL, template, src, dst, start)
        flow.extra = True
        self.flows[flow.flow_id] = flow
        return flow

    def _end_some(self, flow, rate: float) -> None:
        """The traffic stops some day (attempts end, the hidden use goes away)."""
        rng = self.rng_kinds
        if not rng.chance(rate):
            low, high = flow.start + 30, self.total_days - 100
            if low < high:
                flow.end = rng.randint(low, high)

    def _kind_policy(self, kind, name, pair, sources, destinations, applications, **options):
        policy = Policy(
            uid=self.next_id("R"),
            name=name,
            from_zone=self.zone(pair[0]),
            to_zone=self.zone(pair[1]),
            sources=sources,
            destinations=destinations,
            applications=applications,
            action=options.get("action", "permit"),
            tail=options.get("tail", False),
            log_close=options.get("log", False),
            description=options.get("description"),
        )
        for application in applications:
            if application != ANY:
                self._ensure_application(application)
        if policy.tail:
            self.config.policies.append(policy)
        else:
            # A specific deny goes on top of its zone pair, below the
            # emergency rules (the on-call responder puts those first).
            top = next(
                (
                    i
                    for i, p in enumerate(self.config.policies)
                    if (p.from_zone, p.to_zone) == (policy.from_zone, policy.to_zone)
                    and self.policy_meta[p.uid].intent_kind != "emergency_temporary"
                ),
                len(self.config.policies),
            )
            self.config.policies.insert(top, policy)
        return policy

    def _register(self, policy, kind, flow, event, admin) -> None:
        summary = flow.template.summary if kind == "block" else SUMMARIES[kind]
        self.policy_meta[policy.uid] = PolicyMeta(
            policy.uid,
            FIREWALL,
            [flow.flow_id],
            event.event_id,
            -1,
            admin.admin_id,
            None,
            intent_kind=kind,
            summary=summary,
        )
        self._protected.add(policy.uid)

    def _kind_commit(self, day, admin, event, kind, created, **facts) -> None:
        rng = self.rng_kinds
        comment = ""
        if rng.chance(self._rate(admin, self.level.comment_rate)):
            comment = voice.security_comment(admin.persona, kind, rng, **facts)
        second = rng.randint(9 * 3600, 18 * 3600)
        commit = self._commit(day, admin, comment, event, created=created, second=second)
        for uid in created:
            self.policy_meta[uid].commit_seq = commit.seq

    def _kind_description(self, options) -> str | None:
        rng = self.rng_kinds
        if not rng.chance(0.5):
            return None
        if rng.chance(0.25):
            return f"RITM{rng.randint(10000, 999999):07d}"
        return rng.choice(options)

    # ------------------------------------------------------------------ plan

    def _plan_kinds(self, plan: list) -> None:
        """Plan entries for the rule kinds (counts drawn per scenario)."""
        rng = self.rng_kinds
        total = self.total_days
        weights = KIND_COUNT_WEIGHTS[self.level.name]
        counts = {name: rng.weighted(w) for name, w in weights.items()}
        self.kind_counts = counts
        roles = set(self.zone_names)
        names = self.zone_names
        self._factory = None
        if names["users"] == "trust" and names["internet"] == "untrust":
            if rng.chance(FACTORY_RATE):
                self._factory = "sample" if rng.chance(FACTORY_SAMPLE_RATE) else "default-permit"
        services = [b for b in SERVICE_BLOCKS if b[0] in roles and b[1] in roles]
        specs = [{"block": rng.choice(services)} for _ in range(counts["denies"])]
        for prefix in rng.sample(HOSTILE, counts["host_blocks"]):
            specs.append({"host": prefix, "pair": rng.choice(HOST_BLOCK_PAIRS)})
        for spec in specs:
            day = self.workday(rng.randint(60, total - 30))
            plan.append((day, 2, "deny", spec))
            if rng.chance(DENY_DEACTIVATE_RATE):
                off = day + rng.randint(60, 900)
                if off < total - 20:
                    plan.append((self.workday(off), 3, "deny_off", spec))
        broad_pairs = [p for p in BROAD_PAIRS if p[0] in roles and p[1] in roles]
        if self._factory:
            broad_pairs.remove(("users", "internet"))
        broad = rng.sample(broad_pairs, min(counts["broad"], len(broad_pairs)))
        for pair in broad:
            day = self.workday(rng.randint(30, total - 60))
            plan.append((day, 2, "broad", {"pair": pair}))
        cleanup_pairs = [p for p in CLEANUP_PAIRS if p not in broad]
        cleanup_pairs = [p for p in cleanup_pairs if p[0] in roles and p[1] in roles]
        pairs = rng.sample(cleanup_pairs, min(counts["cleanups"], len(cleanup_pairs)))
        same_name = rng.choice(CLEANUP_NAMES) if rng.chance(0.5) else None
        for pair in pairs:
            day = self.workday(rng.randint(5, total - 150))
            plan.append((day, 2, "cleanup_rule", {"pair": pair, "name": same_name}))

    def _kind_handlers(self) -> dict:
        return {
            "deny": lambda day, spec: self._deny(day, spec),
            "deny_off": lambda day, spec: self._deny_off(day, spec),
            "broad": lambda day, spec: self._broad(day, spec),
            "cleanup_rule": lambda day, spec: self._cleanup_rule(day, spec),
        }

    # ------------------------------------------------------------------ events

    def _factory_defaults(self, event, admin) -> list[str]:
        """Junos factory default policies kept from the initial configuration.

        FACTORY-1: `trust-to-untrust` from trust to untrust (SRX210 sample).
        FACTORY-2 and FACTORY-3: `default-permit` from trust to trust and from
        trust to untrust (practitioner name, unverified).
        """
        if not getattr(self, "_factory", None):
            return []
        if self._factory == "sample":
            policies = [("trust-to-untrust", ("users", "internet"))]
        else:
            policies = [("default-permit", ("users", "users"))]
            policies.append(("default-permit", ("users", "internet")))
        created = []
        for name, pair in policies:
            policy = self._kind_policy(
                "factory_default", name, pair, [ANY], [ANY], [ANY], tail=True
            )
            service = self.rng_kinds.choice(("tcp-445", "tcp-3389", "junos-ssh"))
            if pair[1] == "internet":
                service = self.rng_kinds.choice(UNDOCUMENTED_SERVICES)
            flow = self._extra_flow(
                pair[0],
                ZONE_PREFIXES[pair[0]],
                pair[1],
                ZONE_PREFIXES[pair[1]],
                service,
                "unknown_origin",
                self.rng_kinds.randint(1, 60),
                "undocumented",
            )
            self._end_some(flow, UNDOCUMENTED_RATE)
            self._register(policy, "factory_default", flow, event, admin)
            created.append(policy.uid)
        return created

    def _deny(self, day: int, spec: dict) -> None:
        rng = self.rng_kinds
        admin = self._kind_admin(day)
        event = self._event("security_rule", day, admin, note="deny rule")
        action = "reject" if rng.chance(REJECT_RATE) else "deny"
        if "block" in spec:
            src_role, dst_role, source, services = spec["block"]
            pair = (src_role, dst_role)
            service = rng.choice(services)
            word = SERVICE_WORDS[service]
            name = rng.choice((f"deny-{word}", f"block-{word}", f"DENY_{word.upper()}"))
            src = self._zone_object(src_role) if source != "any" else ANY
            dst = self._zone_object(dst_role)
            options = (f"no {word}", f"deny {word}", f"block {word} - security")
            applications = [service]
            src_prefix = "10.10.1.0/24" if source == "users" else ZONE_PREFIXES[src_role]
            flow_parts = (src_role, src_prefix, dst_role, ZONE_PREFIXES[dst_role], service)
            facts = {"what": word, "where": self.zone(dst_role)}
            kind = "deny"
        else:
            pair = spec["pair"]
            prefix = spec["host"]
            style = rng.choice(HOSTILE_NAMES)
            obj = self.namer._unique(style.format(ip=prefix.split("/")[0]))
            src = self._ensure_address(obj, prefix)
            self.generic_names.add(src)
            dst = ANY
            name = rng.choice(("block-bad-actors", "deny-ext-range", "block-hostile"))
            options = ("blocked range", "attackers - see SOC", "blacklist")
            applications = [ANY]
            service = rng.choice(("junos-https", "junos-ssh"))
            flow_parts = (pair[0], prefix, pair[1], ZONE_PREFIXES[pair[1]], service)
            facts = {"what": prefix, "where": self.zone(pair[1])}
            kind = "host_block"
        name = self._unique(name)
        description = self._kind_description(options)
        policy = self._kind_policy(
            "block", name, pair, [src], [dst], applications, action=action, description=description
        )
        key = "service" if kind == "deny" else "host"
        flow = self._extra_flow(*flow_parts, "block", day + 1, key)
        self._end_some(flow, 0.6)
        self._register(policy, "block", flow, event, admin)
        self._kind_commit(day, admin, event, kind, [policy.uid], **facts)
        spec["uid"] = policy.uid

    def _deny_off(self, day: int, spec: dict) -> None:
        """A deny rule no longer wanted is deactivated, not deleted (VSRX-2)."""
        admin = self._kind_admin(day)
        event = self._event("security_rule", day, admin, note="deny rule deactivated")
        for policy in self.config.policies:
            if policy.uid == spec["uid"]:
                policy.inactive = True
        self._kind_commit(day, admin, event, "deactivate", [])

    def _broad(self, day: int, spec: dict) -> None:
        rng = self.rng_kinds
        admin = self._kind_admin(day)
        event = self._event("security_rule", day, admin, note="broad permit")
        pair = spec["pair"]
        style = rng.choice(BROAD_NAMES + ("{a}-to-{b}-any",))
        name = self._unique(style.format(a=self.zone(pair[0]), b=self.zone(pair[1])))
        options = ("temp", "allow everything", "troubleshooting", "TEST - remove later")
        policy = self._kind_policy(
            "broad_permit",
            name,
            pair,
            [ANY],
            [ANY],
            [ANY],
            tail=True,
            log=rng.chance(BROAD_LOG_RATE),
            description=self._kind_description(options),
        )
        flow = self._extra_flow(
            pair[0],
            ZONE_PREFIXES[pair[0]],
            pair[1],
            ZONE_PREFIXES[pair[1]],
            rng.choice(UNDOCUMENTED_SERVICES),
            "unknown_origin",
            day + 1,
            "undocumented",
        )
        self._end_some(flow, UNDOCUMENTED_RATE)
        self._register(policy, "broad_permit", flow, event, admin)
        where = f"{self.zone(pair[0])}->{self.zone(pair[1])}"
        self._kind_commit(day, admin, event, "broad", [policy.uid], where=where)

    def _cleanup_rule(self, day: int, spec: dict) -> None:
        rng = self.rng_kinds
        admin = self._kind_admin(day)
        event = self._event("security_rule", day, admin, note="catch-all deny")
        pair = spec["pair"]
        if spec["name"]:
            name = spec["name"]  # the same name in every zone pair
        else:
            style = rng.choice(CLEANUP_NAMES + ("cleanup-{a}-{b}",))
            name = self._unique(style.format(a=self.zone(pair[0]), b=self.zone(pair[1])))
        options = ("log and drop", "catch all", "default deny")
        policy = self._kind_policy(
            "cleanup_deny",
            name,
            pair,
            [ANY],
            [ANY],
            [ANY],
            action="deny",
            tail=True,
            description=self._kind_description(options),
        )
        flow = self._extra_flow(
            pair[0],
            ZONE_PREFIXES[pair[0]],
            pair[1],
            ZONE_PREFIXES[pair[1]],
            rng.choice(CLEANUP_SERVICES),
            "cleanup_deny",
            day + 1,
            "cleanup_deny",
        )
        self._register(policy, "cleanup_deny", flow, event, admin)
        where = f"{self.zone(pair[0])}->{self.zone(pair[1])}"
        self._kind_commit(day, admin, event, "cleanup", [policy.uid], where=where)
