"""Company model and timeline of events (spec sections 2 to 4).

The base timeline plays the Easy level: meticulous senior admins only, new
applications, shared services, decommissions, duplicate style migrations,
one upgrade (hit count reset), admin turnover and routine commits. No traps.
medium.py extends it for the Medium level through the hooks below.
"""

from datetime import date, timedelta

from palimp_sim import catalog, voice
from palimp_sim.catalog import FlowTemplate
from palimp_sim.junos import ANY, Config, Policy, Zone
from palimp_sim.levels import Level
from palimp_sim.model import (
    Admin,
    App,
    Commit,
    Endpoint,
    Event,
    Flow,
    Person,
    PolicyMeta,
    Server,
    Ticket,
    TrapFacts,
)
from palimp_sim.rng import Rng

BASE_DATE = date(2019, 1, 7)
SENIOR = "meticulous_senior"


class Simulation:
    def __init__(self, level: Level, seed: int) -> None:
        self.level = level
        self.seed = seed
        root = Rng(f"palimp-sim:{level.name}:{seed}")
        self.rng_calendar = root.derive("calendar")
        self.rng_company = root.derive("company")
        self.rng_events = root.derive("events")
        self.rng_admins = root.derive("admins")
        self.rng_text = root.derive("text")
        self.rng_times = root.derive("commit-times")
        self.rng_tickets = root.derive("tickets")

        self.total_days = level.years * 365
        self.start = BASE_DATE + timedelta(days=self.rng_calendar.randint(0, 1460))
        self.zone_names = self.rng_calendar.choice(catalog.ZONE_STYLES)
        self.host_name = f"fw-{self.rng_calendar.choice(('hq', 'dc1', 'core'))}-01"

        self.people: list[Person] = []
        self.admins: list[Admin] = []
        self.servers: dict[str, Server] = {}
        self.apps: dict[str, App] = {}
        self.flows: dict[str, Flow] = {}
        self.commits: list[Commit] = []
        self.events: list[Event] = []
        self.tickets: list[Ticket] = []
        self.policy_meta: dict[str, PolicyMeta] = {}
        self.hit_reset_day: int | None = None
        self.pair_resets: dict[tuple[str, str], int] = {}
        self.traps = TrapFacts()

        self._next_ticket = self.rng_tickets.randint(10000, 60000)
        self._counters: dict[str, int] = {}
        self._last_commit: tuple[int, int] = (-1, 0)
        self._banner_revision = 0
        self._pending_cleanup: dict[str, tuple[list[str], list[str], Ticket | None]] = {}
        roles = ("internet", "users", "dmz", "servers")
        self.config = Config(
            version=catalog.JUNOS_VERSIONS[0],
            host_name=self.host_name,
            time_zone=level.device_time_zone,
            zones=[Zone(self.zone_names[role], role, *catalog.INTERFACES[role]) for role in roles],
            syslog_hosts=["10.20.2.40"],
        )

    # ------------------------------------------------------------------ helpers

    def date(self, day: int) -> date:
        return self.start + timedelta(days=day)

    def next_id(self, prefix: str, width: int = 4) -> str:
        self._counters[prefix] = self._counters.get(prefix, 0) + 1
        return f"{prefix}-{self._counters[prefix]:0{width}d}"

    def workday(self, day: int) -> int:
        """Move a day to the next weekday, or back if past the end."""
        moved = day
        while self.date(moved).weekday() >= 5:
            moved += 1
        if moved >= self.total_days:
            moved = day
            while self.date(moved).weekday() >= 5 or moved >= self.total_days:
                moved -= 1
        return moved

    def active_admin(self, day: int) -> Admin:
        active = [a for a in self.admins if a.active(day)]
        return self.rng_admins.choice(active)

    def zone(self, role: str) -> str:
        return self.zone_names[role]

    def admin(self, admin_id: str) -> Admin:
        return next(a for a in self.admins if a.admin_id == admin_id)

    # Hooks that MediumSimulation overrides. Easy keeps these defaults, so its
    # random draws and output stay the same.

    def _rate(self, admin: Admin, base: float) -> float:
        return base

    def _tier_zone(self, app: App, tier) -> str:
        return tier.zone_role

    def _name_for(self, flow: Flow, suffix: str, admin: Admin) -> str:
        return self._policy_name(flow, suffix)

    def _policies_for_flow(self, flow: Flow, app: App, event: Event, ticket) -> list[str]:
        return [self._add_policy(flow, app, event, ticket)]

    def _commit_second(self, day: int, admin: Admin) -> int:
        return self.rng_times.randint(9 * 3600, 18 * 3600)

    # ------------------------------------------------------------------ setup

    def _make_people(self) -> None:
        rng = self.rng_company
        names = rng.sample(
            [f"{f} {last}" for f in catalog.FIRST_NAMES for last in catalog.LAST_NAMES], 14
        )
        for name in names[:10]:
            self.people.append(Person(self.next_id("P", 3), name, rng.choice(catalog.TEAMS)))
        first = Admin("ADM-1", "", names[10], SENIOR, joined=-rng.randint(200, 900))
        second_join = self.workday(
            rng.randint(self.total_days * 3 // 10, self.total_days * 6 // 10)
        )
        second = Admin("ADM-2", "", names[11], SENIOR, joined=second_join)
        first.left = self.workday(second_join + rng.randint(30, 90))
        for admin in (first, second):
            given, family = admin.name.split(" ")
            admin.login = (given[0] + family).lower()
        self.admins = [first, second]

    # ------------------------------------------------------------------ objects

    def _ensure_address(self, name: str, prefix: str) -> str:
        self.config.addresses.setdefault(name, prefix)
        return name

    def _ensure_application(self, name: str) -> None:
        if name in catalog.PREDEFINED_APPLICATIONS:
            return
        protocol, port = name.split("-")
        self.config.applications.setdefault(name, (protocol, int(port)))

    def _users_endpoint(self) -> Endpoint:
        sites = catalog.SITE_NAMES[: self.level.user_sites]
        members = []
        prefixes = []
        for index, site in enumerate(sites, start=1):
            prefix = f"10.10.{index}.0/24"
            members.append(self._ensure_address(f"users-{site}", prefix))
            prefixes.append(prefix)
        self.config.address_sets.setdefault("users-all", members)
        return Endpoint("users", "users-all", prefixes, "users")

    def _tier_endpoint(self, app: App, tier: str) -> Endpoint:
        servers = [self.servers[s] for s in app.tiers[tier]]
        label = app.app_id.removeprefix("shared-") if app.shared else f"{app.app_id}-{tier}"
        for server in servers:
            self._ensure_address(server.hostname, f"{server.ip}/32")
        if len(servers) == 1:
            address = servers[0].hostname
        else:
            base = app.app_id.removeprefix("shared-")
            address = f"{tier}-servers" if base == tier else f"{base}-{tier}-servers"
            if app.generation:
                address += "-new"
            self.config.address_sets[address] = [s.hostname for s in servers]
        return Endpoint(servers[0].zone_role, address, [f"{s.ip}/32" for s in servers], label)

    def _endpoint(self, token: str, app: App) -> Endpoint:
        if token == "users":
            return self._users_endpoint()
        if token == "internet":
            return Endpoint("internet", ANY, ["0.0.0.0/0"], "internet")
        if token == "servers-net":
            self._ensure_address("servers-net", "10.20.0.0/15")
            return Endpoint("servers", "servers-net", ["10.20.0.0/15"], "servers")
        if token.startswith("partner:"):
            name = token.split(":", 1)[1]
            prefix = f"{catalog.PARTNERS[name]}/32"
            return Endpoint("internet", self._ensure_address(name, prefix), [prefix], name)
        return self._tier_endpoint(app, token)

    def _create_servers(self, app: App, day: int) -> None:
        dmz_count = sum(1 for s in self.servers.values() if s.zone_role == "dmz")
        mgmt_count = sum(1 for s in self.servers.values() if s.zone_role == "management")
        app.tiers = {}
        host_offset = 11 + 10 * app.generation
        for tier_index, tier in enumerate(app.template.tiers):
            ids = []
            zone_role = self._tier_zone(app, tier)
            for i in range(tier.count):
                if zone_role == "management":
                    mgmt_count += 1
                    ip = f"10.30.0.{10 + mgmt_count}"
                elif tier.zone_role == "dmz":
                    dmz_count += 1
                    ip = f"172.16.10.{20 + dmz_count}"
                elif app.shared:
                    ip = f"10.20.1.{10 + 10 * app.index + 2 * tier_index + i}"
                else:
                    second = 20 if app.generation == 0 else 21
                    ip = f"10.{second}.{10 + app.index}.{host_offset + 5 * tier_index + i}"
                base = app.app_id.removeprefix("shared-") if app.shared else app.app_id
                number = i + 1 + tier.count * app.generation
                hostname = (
                    f"{base}-{tier.name}-{number:02d}"
                    if not app.shared
                    else (f"{tier.name}-{number:02d}")
                )
                server = Server(
                    self.next_id("S", 3), hostname, ip, zone_role, app.app_id, tier.name, day
                )
                self.servers[server.server_id] = server
                ids.append(server.server_id)
            app.tiers[tier.name] = ids

    # ------------------------------------------------------------------ commits

    def _commit(self, day: int, admin: Admin, comment: str, event: Event, **lists) -> Commit:
        second = lists.get("second")
        if second is None:
            second = self._commit_second(day, admin)
        if self._last_commit[0] == day:
            second = max(second, self._last_commit[1] + self.rng_times.randint(120, 900))
        self._last_commit = (day, second)
        commit = Commit(
            seq=len(self.commits),
            day=day,
            second=second,
            login=admin.login,
            admin_id=admin.admin_id,
            client="netconf" if admin.persona == "automation" else "cli",
            comment=comment,
            event_id=event.event_id,
            config=self.config.snapshot(),
            created=lists.get("created", []),
            removed=lists.get("removed", []),
        )
        self.commits.append(commit)
        event.commits.append(commit.seq)
        return commit

    def _owner_name(self, app: App) -> str:
        return next(p.name for p in self.people if p.person_id == app.owner_id)

    def _comment(
        self, admin: Admin, kind: str, app: App | None, ticket: Ticket | None, **facts
    ) -> str:
        if not self.rng_text.chance(self._rate(admin, self.level.comment_rate)):
            return ""
        if app is not None:
            facts["requester"] = self._owner_name(app)
        return voice.commit_comment(
            admin.persona,
            kind,
            app.app_id if app else None,
            ticket.ticket_id if ticket else None,
            self.rng_text,
            **facts,
        )

    def _ticket(
        self, day: int, admin: Admin, app: App, category: str, voice_kind: str
    ) -> Ticket | None:
        if not self.rng_tickets.chance(self.level.ticket_rate):
            return None
        self._next_ticket += self.rng_tickets.randint(3, 40)
        owner = next(p for p in self.people if p.person_id == app.owner_id)
        ticket = Ticket(
            ticket_id=f"CHG{self._next_ticket:07d}",
            opened=day - self.rng_tickets.randint(5, 20),
            closed=day + self.rng_tickets.randint(0, 3),
            status="closed",
            requester=owner.name,
            assignee=admin.login,
            summary=voice.ticket_summary(voice_kind, app.app_id, self.rng_tickets),
            category=category,
            related_ci=app.app_id,
            exported=self.rng_tickets.chance(self.level.ticket_export_coverage),
        )
        self.tickets.append(ticket)
        return ticket

    # ------------------------------------------------------------------ policies

    def _policy_name(self, flow: Flow, suffix: str = "") -> str:
        base = f"{flow.src.label}-to-{flow.dst.label}{suffix}"
        names = {p.name for p in self.config.policies}
        name, n = base, 2
        while name in names:
            name, n = f"{base}-{n}", n + 1
        return name

    def _add_policy(
        self,
        flow: Flow,
        app: App,
        event: Event,
        ticket,
        suffix: str = "",
        sources: list[str] | None = None,
        nolog: bool = False,
    ) -> str:
        rng = self.rng_text
        admin = self.admin(event.admin_id)
        for service in flow.template.services:
            self._ensure_application(service)
        description = None
        if rng.chance(self._rate(admin, self.level.description_rate)):
            ticket_id = ticket.ticket_id if ticket else None
            owner = self._owner_name(app)
            description = voice.description(admin.persona, flow, ticket_id, owner, rng)
        logged = rng.chance(self._rate(admin, self.level.log_rate)) and not nolog
        policy = Policy(
            uid=self.next_id("R"),
            name=self._name_for(flow, suffix, admin),
            from_zone=self.zone(flow.src.zone_role),
            to_zone=self.zone(flow.dst.zone_role),
            sources=sources or [flow.src.address],
            destinations=[flow.dst.address],
            applications=list(flow.template.services),
            log_init=logged and rng.chance(self.level.log_init_rate),
            log_close=logged,
            description=description,
        )
        self.config.policies.append(policy)
        self.policy_meta[policy.uid] = PolicyMeta(
            policy.uid,
            app.app_id,
            [flow.flow_id],
            event.event_id,
            -1,
            event.admin_id,
            ticket.ticket_id if ticket else None,
        )
        return policy.uid

    def _new_flow(self, app: App, template: FlowTemplate, start: int) -> Flow:
        flow = Flow(
            self.next_id("F"),
            app.app_id,
            template,
            self._endpoint(template.src, app),
            self._endpoint(template.dst, app),
            start,
        )
        self.flows[flow.flow_id] = flow
        return flow

    def _remove_policies(self, uids: list[str]) -> None:
        self.config.policies = [p for p in self.config.policies if p.uid not in uids]
        self.config.remove_unused_objects()

    def _app_policies(self, app_id: str) -> list[str]:
        return [p.uid for p in self.config.policies if self.policy_meta[p.uid].app_id == app_id]

    # ------------------------------------------------------------------ events

    def _event(
        self, kind: str, day: int, admin: Admin, app: App | None = None, note: str = ""
    ) -> Event:
        app_id = app.app_id if app else None
        event = Event(self.next_id("EV"), kind, day, admin.admin_id, app_id, note=note)
        self.events.append(event)
        return event

    def _bootstrap(self, day: int) -> None:
        admin = self.active_admin(day)
        self.config.logins = [a.login for a in self.admins if a.active(day)]
        event = self._event("bootstrap", day, admin)
        self._commit(day, admin, "Initial configuration", event)

    def _new_app(self, app: App, day: int) -> None:
        admin = self.active_admin(day)
        event = self._event("new_app", day, admin, app)
        ticket = self._ticket(day, admin, app, "change", "change")
        event.ticket_id = ticket.ticket_id if ticket else None
        self._create_servers(app, day)
        go_live = day if app.shared else day + self.rng_events.randint(0, 2)
        app.go_live = go_live
        created = []
        for template in list(app.template.flows) + app.extra_flows:
            flow = self._new_flow(app, template, go_live)
            created += self._policies_for_flow(flow, app, event, ticket)
        kind = "shared" if app.shared else "new_app"
        comment = self._comment(admin, kind, app, ticket, rules=len(created))
        commit = self._commit(day, admin, comment, event, created=created)
        for uid in created:
            self.policy_meta[uid].commit_seq = commit.seq

    def _decommission(self, app: App, day: int) -> None:
        admin = self.active_admin(day)
        event = self._event("decommission", day, admin, app)
        ticket = self._ticket(day, admin, app, "decommission", "decommission")
        event.ticket_id = ticket.ticket_id if ticket else None
        for flow in self.flows.values():
            if flow.app_id == app.app_id and flow.active(day):
                flow.end = day
        for server_ids in app.tiers.values():
            for server_id in server_ids:
                self.servers[server_id].active_to = day
        app.retired = day
        removed = [
            uid
            for uid in self._app_policies(app.app_id)
            if self.rng_events.chance(self.level.cleanup_rate)
        ]
        self._remove_policies(removed)
        comment = self._comment(admin, "decommission", app, ticket)
        self._commit(day, admin, comment, event, removed=removed)

    def _migrate(self, app: App, day: int) -> list[str]:
        """Duplicate style migration: new servers and rules, old rules kept for now."""
        admin = self.active_admin(day)
        event = self._event("migration", day, admin, app)
        ticket = self._ticket(day, admin, app, "change", "migration")
        event.ticket_id = ticket.ticket_id if ticket else None
        old_policies = self._app_policies(app.app_id)
        old_servers = [s for ids in app.tiers.values() for s in ids]
        app.generation += 1
        self._create_servers(app, day)
        created = []
        for flow in list(self.flows.values()):
            if flow.app_id == app.app_id and flow.active(day):
                flow.end = day
                new_flow = self._new_flow(app, flow.template, day)
                created.append(self._add_policy(new_flow, app, event, ticket, suffix="-new"))
        comment = self._comment(admin, "migration", app, ticket)
        commit = self._commit(day, admin, comment, event, created=created)
        for uid in created:
            self.policy_meta[uid].commit_seq = commit.seq
        self._pending_cleanup[app.app_id] = (old_policies, old_servers, ticket)
        return old_policies

    def _migration_cleanup(self, app: App, day: int) -> None:
        old_policies, old_servers, ticket = self._pending_cleanup.pop(app.app_id)
        admin = self.active_admin(day)
        event = self._event("migration_cleanup", day, admin, app)
        event.ticket_id = ticket.ticket_id if ticket else None
        for server_id in old_servers:
            self.servers[server_id].active_to = day
        removed = [uid for uid in old_policies if self.rng_events.chance(self.level.cleanup_rate)]
        self._remove_policies(removed)
        comment = self._comment(admin, "migration_cleanup", app, ticket)
        self._commit(day, admin, comment, event, removed=removed)

    def _upgrade(self, day: int) -> None:
        admin = self.active_admin(day)
        event = self._event("upgrade", day, admin, note="reboot clears hit counts")
        self.config.version = catalog.JUNOS_VERSIONS[1]
        self.hit_reset_day = day
        version = catalog.JUNOS_VERSIONS[1]
        self._commit(
            day, admin, self._comment(admin, "upgrade", None, None, version=version), event
        )

    def _admin_change(self, day: int, target: Admin, joining: bool) -> None:
        admin = next(a for a in self.admins if a.active(day) and a is not target)
        kind = "admin_join" if joining else "admin_leave"
        event = self._event(kind, day, admin, note=target.admin_id)
        if joining:
            self.config.logins.append(target.login)
        else:
            self.config.logins.remove(target.login)
        comment = self._comment(admin, kind, None, None, login=target.login)
        self._commit(day, admin, comment, event)

    def _routine(self, day: int) -> None:
        admin = self.active_admin(day)
        event = self._event("routine", day, admin)
        choice = self.rng_events.randint(0, 2)
        if choice == 0:
            number = int(self.config.snmp_community.rsplit("-", 1)[1]) + 1
            self.config.snmp_community = f"fm-ro-{number}"
            text = "snmp"
        elif choice == 1:
            self._banner_revision += 1
            self.config.banner = f"Authorized access only, rev {self._banner_revision}"
            text = "banner"
        else:
            if "10.20.2.41" in self.config.syslog_hosts:
                self.config.syslog_hosts.remove("10.20.2.41")
                text = "syslog_remove"
            else:
                self.config.syslog_hosts.append("10.20.2.41")
                text = "syslog_add"
        self._commit(day, admin, self._comment(admin, text, None, None), event)

    # ------------------------------------------------------------------ run

    def run(self) -> "Simulation":
        self._make_people()
        rng = self.rng_events
        total = self.total_days
        plan: list[tuple[int, int, str, object]] = [(0, 0, "bootstrap", None)]

        for index, template in enumerate(catalog.SHARED):
            owner = rng.choice(self.people).person_id
            app = App(template.app_id, template.name, owner, True, template, index)
            self.apps[app.app_id] = app
            plan.append((self.workday(1 + 3 * index), 1, "new_app", app))

        templates = rng.sample(catalog.APPS, self.level.applications)
        days = sorted(rng.randint(30, total - 120) for _ in templates)
        for index, (template, day) in enumerate(zip(templates, days, strict=True)):
            app = App(
                template.app_id,
                template.name,
                rng.choice(self.people).person_id,
                False,
                template,
                index,
            )
            self.apps[app.app_id] = app
            plan.append((self.workday(day), 1, "new_app", app))

        candidates = [p for p in plan if p[2] == "new_app" and not p[3].shared]
        decommissions = round(self.level.years * self.level.decommissions_per_year)
        migrations = round(self.level.years * self.level.migrations_per_year)
        eligible = [c for c in candidates if c[0] < total - 300]
        chosen = rng.sample(eligible, min(decommissions + migrations, len(eligible)))
        for _, _, _, app in chosen[:decommissions]:
            day = rng.randint(plan_day(plan, app) + 150, total - 30)
            plan.append((self.workday(day), 2, "decommission", app))
        for _, _, _, app in chosen[decommissions:]:
            day = self.workday(rng.randint(plan_day(plan, app) + 120, total - 90))
            plan.append((day, 2, "migration", app))
            plan.append((self.workday(day + rng.randint(7, 30)), 3, "migration_cleanup", app))

        upgrade_day = total - self.level.days_since_hit_reset
        if upgrade_day > 0:
            plan.append((self.workday(upgrade_day), 4, "upgrade", None))
        plan.append((self.admins[1].joined, 0, "admin_join", self.admins[1]))
        plan.append((self.admins[0].left, 5, "admin_leave", self.admins[0]))

        routine_count = max(0, self.level.commits_per_year * self.level.years - len(plan))
        for _ in range(routine_count):
            plan.append((self.workday(rng.randint(5, total - 1)), 6, "routine", None))

        handlers = {
            "bootstrap": lambda day, _: self._bootstrap(day),
            "new_app": lambda day, app: self._new_app(app, day),
            "decommission": lambda day, app: self._decommission(app, day),
            "migration": lambda day, app: self._migrate(app, day),
            "migration_cleanup": lambda day, app: self._migration_cleanup(app, day),
            "upgrade": lambda day, _: self._upgrade(day),
            "admin_join": lambda day, admin: self._admin_change(day, admin, True),
            "admin_leave": lambda day, admin: self._admin_change(day, admin, False),
            "routine": lambda day, _: self._routine(day),
        }
        for day, _, kind, subject in sorted(plan, key=lambda p: (p[0], p[1])):
            handlers[kind](day, subject)
        return self


def plan_day(plan: list, app: App) -> int:
    return next(p[0] for p in plan if p[2] == "new_app" and p[3] is app)
