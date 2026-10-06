"""Hard level timeline (spec section 7.1, decision 0035) and its four new traps.

Hard plays the Medium timeline (medium.py) at a larger scale: 7 years, 60
applications (regional instances of the templates), 150 commits a year, a
sixth zone (`pci` or `secure`), every persona (two contractor periods, a
cleaner, an on-call responder) and health check rules from the monitoring
server. The seven v1 traps are built as in Medium, with larger drawn counts
(levels.HARD_TRAP_COUNT_WEIGHTS). Four traps are added, each drawn per
scenario (zero instances possible):

- TRAP-RENAME-CHAIN: a cleaner renames policies or address objects to a new
  convention (Junos `rename`). Old rollbacks keep the old names, and so do the
  log lines written before the rename.
- TRAP-IP-REUSE: an application is retired and its users rule is left behind;
  a later application gets the freed address. The admin finds the flow
  already open and adds no rule: the dead rule now carries the new
  application's traffic.
- TRAP-SCANNER-HITS: an application is retired and one of its rules is left
  behind; the only traffic it still sees is a vulnerability scanner sweep
  (users zone) or a monitoring probe nobody removed.
- TRAP-STALE-NAME: an application is replaced by a new product that takes
  over its servers' address objects (repoint style migration, spec 4.2): the
  rules and objects keep the old application's names while they serve the new
  one.

truth.py checks each condition on the final state before tagging a rule.
"""

from dataclasses import replace

from palimp_sim import catalog, voice
from palimp_sim.catalog import AppTemplate, FlowTemplate
from palimp_sim.junos import GLOBAL, Zone
from palimp_sim.levels import HARD_TRAP_COUNT_WEIGHTS
from palimp_sim.medium import AUTOMATION, OPERATOR, MediumSimulation
from palimp_sim.model import Admin, App, Endpoint, Flow, Person
from palimp_sim.rng import Rng
from palimp_sim.world import SENIOR

CONTRACTOR = "contractor"
CLEANER = "cleaner"
ON_CALL = "on_call"
PERSONA_FACTORS = {SENIOR: 1.4, OPERATOR: 0.5, CONTRACTOR: 0.4, CLEANER: 1.0, ON_CALL: 0.3}
CONTRACTOR_SHARE = 0.5  # share of new applications a contractor deploys while active
HEALTH_CHECK_RATE = 0.5  # applications monitored by a service check
HEALTH_SERVICES = ("junos-https", "junos-http", "tcp-8080", "tcp-8443")
ANNOTATION_RATE = 0.25  # senior admins `annotate` some new policies (hierarchical only)
RENAME_ANNOTATION_RATE = 0.3  # the cleaner notes the old name in an annotation
RENAMES_PER_YEAR = 4  # rename events (spec 7.1), most before the retained history
POLICY_RENAME_SHARE = 0.65  # the rest rename an address object
HARD_ACCESS_PER_YEAR = 40
MONITOR = "app:shared-monitoring:mon"
# Shared services that may be written as global policies (GLOBAL-1), with the
# zone conditions of each: (app, from roles, to roles).
GLOBAL_SERVICES = (
    ("shared-monitoring", ("management",), ()),
    ("shared-backup", ("management",), ()),
    ("shared-ntp", ("servers",), ("internet",)),
)


def regional_templates() -> tuple:
    """Every application template, plus two regional instances of each."""
    base = catalog.APPS + catalog.EXTRA_APPS
    variants = []
    for index, template in enumerate(base):
        for step in (0, 3):
            region = catalog.REGIONS[(index + step) % len(catalog.REGIONS)]
            variants.append(
                replace(
                    template,
                    app_id=f"{template.app_id}-{region}",
                    name=f"{template.name} {region.upper()}",
                )
            )
    return base + tuple(variants)


def base_id(app_id: str) -> str:
    """Template id of a regional instance (`erp-de` is `erp`)."""
    head, _, region = app_id.rpartition("-")
    return head if head and region in catalog.REGIONS else app_id


def successor(template: AppTemplate) -> AppTemplate:
    new_id, name = catalog.SUCCESSORS[base_id(template.app_id)]
    flows = tuple(replace(f, summary=_successor_summary(f, name)) for f in template.flows)
    return replace(template, app_id=new_id, name=name, flows=flows)


def _successor_summary(flow: FlowTemplate, name: str) -> str:
    if flow.kind == "app_access":
        return f"Staff use {name}, which took over the servers of the application it replaced"
    if flow.kind == "partner_access":
        return f"{name} exchanges files with an outside company"
    return f"Components of {name} talk to each other"


class HardSimulation(MediumSimulation):
    def __init__(self, level, seed: int) -> None:
        super().__init__(level, seed)
        root = Rng(f"palimp-sim:{level.name}:{seed}")
        self.rng_hard = root.derive("hard")
        self.rng_rename = root.derive("renames")
        self.rng_annotate = root.derive("annotations")
        self.count_weights = HARD_TRAP_COUNT_WEIGHTS
        self.access_per_year = HARD_ACCESS_PER_YEAR
        self.zone_names["restricted"] = self.rng_hard.choice(catalog.RESTRICTED_NAMES)
        self.config.zones.append(
            Zone(self.zone_names["restricted"], "restricted", *catalog.INTERFACES["restricted"])
        )
        self._contractor_rules = 0
        self._restricted_hosts = 0
        self._alias: dict[str, str] = {}  # renamed address objects, old -> new
        self._forced: set[str] = set()  # rules a decommission must leave (trap subjects)
        self._reuse: dict[str, dict] = {}  # new app -> reuse plan (TRAP-IP-REUSE)
        self._leftover: dict[str, dict] = {}  # retired app -> rule left (IP reuse, scanner)
        self._stale: dict[str, int] = {}  # replaced app -> day (TRAP-STALE-NAME)
        self._health_forced: set[str] = set()
        self._zone_like: dict[str, str] = {}  # successor -> replaced app (tier zones)
        self._scanner_day: int | None = None
        self._global_apps: dict[str, tuple] = {}
        if level.global_policies:
            count = self.rng_hard.randint(1, len(GLOBAL_SERVICES))
            for app_id, froms, tos in self.rng_hard.sample(GLOBAL_SERVICES, count):
                self._global_apps[app_id] = (froms, tos)

    # ------------------------------------------------------------------ hooks

    def _rate(self, admin: Admin, base: float) -> float:
        if admin.persona == AUTOMATION:
            return 1.0
        return min(1.0, base * PERSONA_FACTORS[admin.persona])

    def _tier_zone(self, app: App, tier) -> str:
        app_id = self._zone_like.get(app.app_id, app.app_id)
        if app_id in catalog.MANAGEMENT_APPS:
            return "management"
        if base_id(app_id) in catalog.RESTRICTED_APPS and tier.name == "db":
            return "restricted"
        return tier.zone_role

    def _pc_address(self, site: int, pcs: int) -> str:
        # More requests than Medium: numbers wrap below the scanner (.250).
        return f"10.10.{site}.{20 + pcs % 220}"

    def _app_templates(self) -> tuple:
        return regional_templates()

    def active_admin(self, day: int) -> Admin:
        everyday = (SENIOR, OPERATOR, CONTRACTOR)
        active = [a for a in self.admins if a.active(day) and a.persona in everyday]
        return self.rng_admins.choice(active)

    def _persona_admin(self, day: int, persona: str) -> Admin | None:
        return next((a for a in self.admins if a.active(day) and a.persona == persona), None)

    def _app_admin(self, day: int) -> Admin:
        contractor = self._persona_admin(day, CONTRACTOR)
        if contractor and self.rng_hard.chance(CONTRACTOR_SHARE):
            return contractor
        return super()._app_admin(day)

    def _emergency_admin(self, day: int) -> Admin:
        return self._persona_admin(day, ON_CALL) or self.active_admin(day)

    def _cleanup_admin(self, day: int) -> Admin:
        return self._persona_admin(day, CLEANER) or self.active_admin(day)

    def _name_for(self, flow: Flow, suffix: str, admin: Admin) -> str:
        if admin.persona == CONTRACTOR:
            self._contractor_rules += 1
            return f"CTR_P{self._contractor_rules:03d}"
        return super()._name_for(flow, suffix, admin)

    def _ensure_address(self, name: str, prefix: str) -> str:
        return super()._ensure_address(self._alias.get(name, name), prefix)

    def _tier_endpoint(self, app: App, tier: str) -> Endpoint:
        endpoint = super()._tier_endpoint(app, tier)
        for set_name, members in self.config.address_sets.items():
            self.config.address_sets[set_name] = [self._alias.get(m, m) for m in members]
        endpoint.address = self._alias.get(endpoint.address, endpoint.address)
        return endpoint

    def _create_servers(self, app: App, day: int) -> None:
        super()._create_servers(app, day)
        reuse = self._reuse.get(app.app_id)
        for tier_name, server_ids in app.tiers.items():
            tier = next(t for t in app.template.tiers if t.name == tier_name)
            for index, server_id in enumerate(server_ids):
                server = self.servers[server_id]
                if self._tier_zone(app, tier) == "restricted":
                    self._restricted_hosts += 1
                    server.ip = f"10.40.0.{10 + self._restricted_hosts}"
                elif reuse and app.generation == 0 and tier_name == reuse["tier"]:
                    # The new server gets the address freed by the retired one.
                    server.ip = reuse["ips"][index]

    def _integrations(self, app: App, day: int) -> list[FlowTemplate]:
        flows = super()._integrations(app, day)
        if app.app_id in self._health_forced or self.rng_hard.chance(HEALTH_CHECK_RATE):
            check = self._health_check(app)
            if check:
                flows.append(check)
        return flows

    def _health_check(self, app: App) -> FlowTemplate | None:
        """Service check from the monitoring server to the users' entry tier."""
        zones = {t.name: self._tier_zone(app, t) for t in app.template.tiers}
        for flow in app.template.flows:
            service = flow.services[-1]
            if (
                flow.src == "users"
                and zones.get(flow.dst) in ("servers", "dmz")
                and service in HEALTH_SERVICES
            ):
                return FlowTemplate(
                    MONITOR,
                    flow.dst,
                    (service,),
                    "always",
                    288,
                    "monitoring",
                    "The monitoring server checks that the service answers",
                )
        return None

    def _add_policy(self, flow, app, event, ticket, suffix="", sources=None, nolog=False) -> str:
        uid = super()._add_policy(flow, app, event, ticket, suffix, sources, nolog)
        policy = self.config.policy(uid)
        admin = self.admin(event.admin_id)
        if admin.persona == SENIOR and self.rng_annotate.chance(ANNOTATION_RATE):
            ticket_id = ticket.ticket_id if ticket else None
            policy.annotation = voice.annotation(
                flow, ticket_id, self._owner_name(app), self.rng_annotate
            )
        shared = self._global_apps.get(app.app_id)
        if shared and flow.template in app.template.flows:
            # Written once as a global policy with zone conditions (GLOBAL-1).
            froms, tos = shared
            policy.from_zone = policy.to_zone = GLOBAL
            policy.from_zones = [self.zone(role) for role in froms]
            policy.to_zones = [self.zone(role) for role in tos]
            policy.name = self._unique(f"gp-{app.app_id.removeprefix('shared-')}")
        return uid

    def _policies_for_flow(self, flow: Flow, app: App, event, ticket) -> list[str]:
        reuse = self._reuse.get(app.app_id)
        leftover = self._leftover[reuse["source"]] if reuse else None
        if leftover and leftover["uids"] and flow.template == reuse["template"]:
            # The admin tests the flow before writing a rule: it already
            # works, through the rule left by the retired application.
            for uid in leftover["uids"]:
                self.traps.ip_reuse[uid] = {"app": app.app_id, "flow": flow.flow_id}
            return []
        return super()._policies_for_flow(flow, app, event, ticket)

    def _remove_policies(self, uids: list[str]) -> None:
        super()._remove_policies([uid for uid in uids if uid not in self._forced])

    # ------------------------------------------------------------------ setup

    def _make_people(self) -> None:
        rng = self.rng_company
        total = self.total_days
        names = rng.sample(
            [f"{f} {last}" for f in catalog.FIRST_NAMES for last in catalog.LAST_NAMES], 22
        )
        for name in names[:14]:
            self.people.append(Person(self.next_id("P", 3), name, rng.choice(catalog.TEAMS)))
        first = Admin("ADM-1", "", names[14], SENIOR, joined=-rng.randint(200, 900))
        operator = Admin("ADM-2", "", names[15], OPERATOR, joined=-rng.randint(30, 400))
        second_join = self.workday(rng.randint(total * 35 // 100, total * 55 // 100))
        second = Admin("ADM-3", "", names[16], SENIOR, joined=second_join)
        first.left = self.workday(second_join + rng.randint(30, 90))
        robot_join = self.workday(rng.randint(total * 50 // 100, total * 65 // 100))
        robot = Admin("ADM-4", "svc-ansible", "Ansible automation", AUTOMATION, joined=robot_join)
        admins = [first, operator, second, robot]
        # Two contractor periods of 3 to 12 months (spec 4.7).
        for number, (low, high) in enumerate(((15, 30), (60, 75)), start=5):
            joined = self.workday(rng.randint(total * low // 100, total * high // 100))
            left = self.workday(min(joined + rng.randint(90, 365), total - 10))
            admins.append(Admin(f"ADM-{number}", "", names[12 + number], CONTRACTOR, joined, left))
        cleaner_join = self.workday(rng.randint(total * 40 // 100, total * 60 // 100))
        admins.append(Admin("ADM-7", "", names[20], CLEANER, joined=cleaner_join))
        admins.append(Admin("ADM-8", "", names[21], ON_CALL, joined=self.workday(5)))
        for admin in admins:
            if admin.persona == AUTOMATION:
                continue
            given, family = admin.name.split(" ")
            login = (given[0] + family).lower()
            admin.login = f"ext-{login}" if admin.persona == CONTRACTOR else login
        self.admins = admins

    # ------------------------------------------------------------------ plan

    def _reserve(self, apps: list[App], go_lives: dict[str, int], protected: set[str]) -> set:
        """Applications for the new traps, kept out of every other draw."""
        rng = self.rng_hard
        total = self.total_days
        counts = self.counts
        free = [a for a in apps if a.app_id not in protected]
        taken: set[str] = set()

        def users_flows(app: App) -> list[FlowTemplate]:
            zones = {t.name: self._tier_zone(app, t) for t in app.template.tiers}
            return [f for f in app.template.flows if f.src == "users" and zones[f.dst] == "servers"]

        def tier_count(app: App, tier: str) -> int:
            return next(t.count for t in app.template.tiers if t.name == tier)

        for _ in range(counts["ip_reuse"]):
            pairs = []
            for old in free:
                if old.app_id in taken or go_lives[old.app_id] > total - 700:
                    continue
                for new in free:
                    if new.app_id in taken or new is old:
                        continue
                    if go_lives[new.app_id] < go_lives[old.app_id] + 250:
                        continue
                    for theirs in users_flows(new):
                        others = [f for f in new.template.flows if f is not theirs]
                        if not any(theirs.dst in (f.src, f.dst) for f in others):
                            continue  # the new server would leave no object behind
                        for ours in users_flows(old):
                            same = ours.services == theirs.services
                            if same and tier_count(new, theirs.dst) <= tier_count(old, ours.dst):
                                pairs.append((old, new, ours, theirs))
            if not pairs:
                break
            old, new, ours, theirs = rng.choice(pairs)
            taken |= {old.app_id, new.app_id}
            day = rng.randint(go_lives[old.app_id] + 150, go_lives[new.app_id] - 30)
            self._leftover[old.app_id] = {"template": ours, "day": self.workday(day), "uids": []}
            self._reuse[new.app_id] = {
                "source": old.app_id,
                "tier": theirs.dst,
                "old_tier": ours.dst,
                "template": theirs,
                "ips": [],
            }

        for _ in range(counts["scanner_hits"]):
            kind = "scanner" if rng.chance(0.5) else "monitoring"
            choices = []
            for app in free:
                if app.app_id in taken or go_lives[app.app_id] > total - 400:
                    continue
                if kind == "scanner":
                    template = next(iter(users_flows(app)), None)
                else:
                    template = self._health_check(app)
                if template:
                    choices.append((app, template))
            if not choices:
                continue
            app, template = rng.choice(choices)
            taken.add(app.app_id)
            if kind == "monitoring":
                self._health_forced.add(app.app_id)
            day = self.workday(rng.randint(go_lives[app.app_id] + 150, total - 60))
            self._leftover[app.app_id] = {
                "template": template,
                "day": day,
                "uids": [],
                "noise": kind,
            }
            if kind == "scanner":
                start = max(day + 7, total - 300)
                self._scanner_day = max(self._scanner_day or 0, start)

        for _ in range(counts["stale_names"]):
            choices = [
                a
                for a in free
                if a.app_id not in taken
                and base_id(a.app_id) in catalog.SUCCESSORS
                and go_lives[a.app_id] <= total - 400
                and users_flows(a)
            ]
            used = {catalog.SUCCESSORS[base_id(a)][0] for a in self._stale}
            choices = [a for a in choices if catalog.SUCCESSORS[base_id(a.app_id)][0] not in used]
            if not choices:
                break
            app = rng.choice(choices)
            taken.add(app.app_id)
            self._stale[app.app_id] = self.workday(
                rng.randint(go_lives[app.app_id] + 200, total - 60)
            )
        return taken

    def _plan_more(self, plan: list, apps: list[App], go_lives: dict[str, int]) -> None:
        by_id = {a.app_id: a for a in apps}
        for app_id, leftover in self._leftover.items():
            plan.append((leftover["day"], 2, "decommission", by_id[app_id]))
        for app_id, day in self._stale.items():
            plan.append((day, 2, "replace", by_id[app_id]))
        if self._scanner_day is not None:
            plan.append((self.workday(self._scanner_day), 2, "scanner", None))
        for admin in self.admins:
            if admin.persona == CONTRACTOR:
                plan.append((admin.left, 5, "admin_leave", admin))
        # Renames: the drawn ones inside the retained history (about the last
        # four months), the others spread over the earlier years.
        total = self.total_days
        visible = self.counts["renames"]
        for _ in range(visible):
            day = self.workday(total - self.rng_rename.randint(5, 100))
            plan.append((day, 3, "rename", None))
        for _ in range(max(0, round(self.level.years * RENAMES_PER_YEAR) - visible)):
            day = self.workday(self.rng_rename.randint(200, total - 150))
            plan.append((day, 3, "rename", None))

    def _more_handlers(self) -> dict:
        return {
            "replace": lambda day, app: self._replace(app, day),
            "scanner": lambda day, _: self._scanner(day),
            "rename": lambda day, _: self._rename(day),
        }

    # ------------------------------------------------------------------ events

    def _decommission(self, app: App, day: int) -> None:
        leftover = self._leftover.get(app.app_id)
        if leftover:
            # The rule left behind (its owners never asked for its removal).
            uids = [
                p.uid
                for p in self.config.policies
                if self.policy_meta[p.uid].app_id == app.app_id
                and any(
                    self.flows[f].template == leftover["template"]
                    for f in self.policy_meta[p.uid].flow_ids
                )
            ]
            leftover["uids"] = uids
            self._forced |= set(uids)
            self._protected |= set(uids)
            for reuse in self._reuse.values():
                if reuse["source"] == app.app_id:
                    tier = app.tiers[reuse["old_tier"]]
                    reuse["ips"] = [self.servers[s].ip for s in tier]
        super()._decommission(app, day)
        if leftover and leftover.get("noise") == "monitoring":
            # The monitoring tool still checks the retired server.
            template = leftover["template"]
            servers = [self.servers[s] for s in app.tiers[template.dst]]
            source = self._tier_endpoint(self.apps["shared-monitoring"], "mon")
            target = Endpoint(
                servers[0].zone_role,
                self._alias.get(servers[0].hostname, servers[0].hostname),
                [f"{s.ip}/32" for s in servers],
                f"{app.app_id}-{template.dst}",
            )
            probe = replace(
                template,
                summary="The monitoring tool still checks a server that was switched off",
            )
            flow = Flow(self.next_id("F"), "shared-monitoring", probe, source, target, day)
            flow.noise = "monitoring"
            self.flows[flow.flow_id] = flow
        for uid in leftover["uids"] if leftover else []:
            if leftover.get("noise"):
                self.traps.scanner_targets[uid] = leftover["noise"]

    def _scanner(self, day: int) -> None:
        """The security team starts a weekly sweep from a user LAN (no rule needed)."""
        rng = self.rng_hard
        targets = []
        for app_id, leftover in self._leftover.items():
            if leftover.get("noise") == "scanner":
                app = self.apps[app_id]
                tier = leftover["template"].dst
                targets += [self.servers[s].ip for s in app.tiers[tier]]
        live = sorted(
            {
                s.ip
                for s in self.servers.values()
                if s.zone_role == "servers" and s.active_to is None
            }
        )
        targets += rng.sample(live, min(12, len(live)))
        services = list(catalog.SCANNER_SERVICES)
        for leftover in self._leftover.values():
            for service in leftover["template"].services:
                if leftover.get("noise") == "scanner" and service not in services:
                    services.append(service)
        dst = [f"{ip}/32" for ip in dict.fromkeys(targets)]
        template = FlowTemplate(
            "scanner",
            "servers-net",
            tuple(services),
            "weekly",
            len(dst) * len(services),
            "monitoring",
            "Vulnerability scanner sweeps server ports every week",
        )
        source = Endpoint("users", "scanner", [f"{catalog.SCANNER_ADDRESS}/32"], "scanner")
        target = Endpoint("servers", "servers-net", dst, "servers")
        flow = Flow(self.next_id("F"), "shared-monitoring", template, source, target, day)
        flow.period, flow.phase, flow.noise = 7, day, "scanner"
        self.flows[flow.flow_id] = flow

    def _replace(self, old: App, day: int) -> None:
        """A new product takes over the servers' objects of an old one (repoint)."""
        rng = self.rng_hard
        admin = self.active_admin(day)
        template = successor(old.template)
        new = App(
            template.app_id,
            template.name,
            rng.choice(self.people).person_id,
            False,
            template,
            len(self.apps),
        )
        self.apps[new.app_id] = new
        self._zone_like[new.app_id] = old.app_id
        event = self._event("migration", day, admin, new, note=f"replaces {old.app_id}")
        ticket = self._ticket(day, admin, new, "change", "change")
        event.ticket_id = ticket.ticket_id if ticket else None
        if rng.chance(0.6):
            self._ticket(day, admin, old, "decommission", "decommission")
        self._create_servers(new, day)
        new.go_live = day
        old.retired = day
        ip_map = {}
        for tier, server_ids in old.tiers.items():
            for old_id, new_id in zip(server_ids, new.tiers[tier], strict=True):
                old_server, new_server = self.servers[old_id], self.servers[new_id]
                old_server.active_to = day
                ip_map[f"{old_server.ip}/32"] = f"{new_server.ip}/32"
                name = self._alias.get(old_server.hostname, old_server.hostname)
                if name in self.config.addresses:
                    self.config.addresses[name] = f"{new_server.ip}/32"
        own = dict(zip(old.template.flows, template.flows, strict=True))
        flow_map = {}
        for flow in list(self.flows.values()):
            if not flow.active(day) or not (
                flow.app_id == old.app_id or self._targets(flow, old.app_id)
            ):
                continue
            flow.end = day
            mine = flow.app_id == old.app_id
            moved = Flow(
                self.next_id("F"),
                new.app_id if mine else flow.app_id,
                own.get(flow.template, flow.template) if mine else flow.template,
                _remap(flow.src, ip_map),
                _remap(flow.dst, ip_map),
                day,
                period=flow.period,
                phase=flow.phase,
            )
            self.flows[moved.flow_id] = moved
            flow_map[flow.flow_id] = moved.flow_id
        stale = []
        for policy in self.config.policies:
            meta = self.policy_meta[policy.uid]
            if any(f in flow_map for f in meta.flow_ids):
                meta.flow_ids = [flow_map.get(f, f) for f in meta.flow_ids]
                if meta.app_id == old.app_id:
                    meta.app_id = new.app_id
                    stale.append(policy.uid)
        comment = self._comment(admin, "replace", old, ticket, new=voice.code(new.app_id))
        commit = self._commit(day, admin, comment, event)
        for uid in stale:
            self.traps.stale[uid] = {"old": old.app_id, "new": new.app_id, "seq": commit.seq}

    def _rename(self, day: int) -> None:
        """Policies or address objects renamed to a new convention (spec 4.6)."""
        rng = self.rng_rename
        facts = self.traps
        involved = (
            set(facts.emergency)
            | set(facts.nolog_jobs)
            | set(facts.rare_jobs)
            | set(facts.ip_reuse)
            | set(facts.stale)
            | self._forced
        )
        candidates = [
            p
            for p in self.config.policies
            if not p.inactive
            and not p.is_global
            and p.uid not in involved
            and p.uid not in facts.renames
            and self.commits[self.policy_meta[p.uid].commit_seq].day <= day - 60
        ]
        renamed_policies, renamed_objects = [], []
        if rng.chance(POLICY_RENAME_SHARE) and candidates:
            for policy in rng.sample(candidates, min(rng.randint(1, 2), len(candidates))):
                code = voice.code(self.policy_meta[policy.uid].app_id).lower()
                base = f"{policy.from_zone}_{policy.to_zone}_{code}"
                n = 1
                names = {p.name for p in self.config.policies}
                while f"{base}_{n:02d}" in names:
                    n += 1
                renamed_policies.append((policy, policy.name))
                policy.name = f"{base}_{n:02d}"
                if rng.chance(RENAME_ANNOTATION_RATE):
                    policy.annotation = f"renamed from {renamed_policies[-1][1]}"
        else:
            avoid = {
                name
                for p in self.config.policies
                if p.uid in involved
                for name in p.sources + p.destinations
            }
            used = {n for p in candidates for n in p.sources + p.destinations}
            # Server objects only: other names (servers-net, partners,
            # workstations) are reused by later rules under their old name.
            hostnames = {s.hostname for s in self.servers.values()}
            objects = [
                name
                for name in self.config.addresses
                if name in used and name not in avoid and name in hostnames
            ]
            for name in rng.sample(objects, min(rng.randint(1, 2), len(objects))):
                renamed_objects.append((name, f"host_{name}"))
        for old, new in renamed_objects:
            self._rename_object(old, new)
        if not renamed_policies and not renamed_objects:
            return
        admin = self._cleanup_admin(day)
        event = self._event("object_rename", day, admin, note="renames to a naming convention")
        comment = self._comment(admin, "rename", None, None)
        commit = self._commit(day, admin, comment, event)
        for policy, old in renamed_policies:
            facts.renames.setdefault(policy.uid, []).append((commit.seq, old))
        for old, new in renamed_objects:
            facts.object_renames.append((commit.seq, old, new))

    def _rename_object(self, old: str, new: str) -> None:
        config = self.config
        config.addresses = {(new if k == old else k): v for k, v in config.addresses.items()}
        for set_name, members in config.address_sets.items():
            config.address_sets[set_name] = [new if m == old else m for m in members]
        for policy in config.policies:
            policy.sources = [new if n == old else n for n in policy.sources]
            policy.destinations = [new if n == old else n for n in policy.destinations]
        for flow in self.flows.values():
            for endpoint in (flow.src, flow.dst):
                if endpoint.address == old:
                    endpoint.address = new
        self._alias = {k: (new if v == old else v) for k, v in self._alias.items()}
        self._alias[old] = new


def _remap(endpoint: Endpoint, ip_map: dict[str, str]) -> Endpoint:
    if not any(prefix in ip_map for prefix in endpoint.prefixes):
        return endpoint
    prefixes = [ip_map.get(prefix, prefix) for prefix in endpoint.prefixes]
    return Endpoint(endpoint.zone_role, endpoint.address, prefixes, endpoint.label)
