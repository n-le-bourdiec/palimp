"""Medium level timeline (spec section 7.1) and the seven v1 traps (spec 7.3).

Medium adds, on top of the Easy timeline: a hurried operator and an automation
account next to the senior admins, a management zone, scheduled jobs, emergency
rules followed by hit-count based cleanups, a batch commit and copy-pasted
commit comments. The traps come out of these events; `TrapFacts` records what
was done on purpose, and truth.py checks each trap condition on the final
state.

Trap mechanisms (decision 0012 lists the seven v1 traps). The number of
instances of the first five is drawn per scenario (levels.TRAP_COUNT_WEIGHTS,
decision 0018), so a scenario can hold none or several of each:
- TRAP-LIVE-NOLOG: weekly job rules without logging, in the zone pair whose
  counters were cleared (`clear security policies hit-count from-zone A
  to-zone B`, VSRX-7c) a few days after their last run. The cleared pair is
  drawn on its own, among the pairs a weekly job can use.
- TRAP-RARE-JOB: yearly job rules that last ran before the hit count reset.
  Quarterly job rules (application to partner) still show hits, unless the
  clear happens to hit their zone pair after their last run.
- TRAP-EMERGENCY-LOADBEARING: an on-call admin inserts a broad rule at the top
  of users to servers; it shadows the proper rules, which then show no hits and
  are removed by the next cleanup. The temporary rule is left carrying the flow.
- TRAP-MISLEADING-COMMENT: commit comments copied from an earlier commit
  about another application.
- TRAP-BATCH-COMMIT: a hurried operator puts the go-live of two or three
  applications in one commit with a comment naming one of them.
- TRAP-HISTORY-HORIZON: 60 commits a year push most rule creations out of the
  50 retained commits (tagged in truth.py).
- TRAP-DEACTIVATED: cleanups deactivate some unused rules instead of deleting
  them.
"""

from palimp_sim import catalog, voice
from palimp_sim.artifacts import RETAINED
from palimp_sim.catalog import FlowTemplate, service_port
from palimp_sim.junos import ANY, Policy, Zone
from palimp_sim.levels import TRAP_COUNT_WEIGHTS
from palimp_sim.model import Admin, App, Endpoint, Event, Flow, Person, PolicyMeta
from palimp_sim.rng import Rng
from palimp_sim.traffic import Matcher
from palimp_sim.world import SENIOR, Simulation

OPERATOR = "hurried_operator"
AUTOMATION = "automation"
# Factor applied to comment_rate, description_rate and log_rate (weighted means
# in spec 7.1). The automation account always comments, describes and logs.
PERSONA_FACTORS = {SENIOR: 1.4, OPERATOR: 0.5}
OPERATOR_SPLIT_RATE = 0.7  # operator writes one rule per user site
AUTOMATION_SHARE = 0.6  # share of new applications deployed by automation
EMERGENCY_LOG_RATE = 0.2
EMERGENCY_DESCRIPTION_RATE = 0.3
JOB_SOURCE_TIERS = ("app", "db", "file", "mbx")
INTEGRATION_WEIGHTS = (0.2, 0.45, 0.35)  # an application calls 0, 1 or 2 others
ACCESS_PER_YEAR = 30  # ad hoc access requests
ACCESS_TEMPORARY_RATE = 0.5  # the access ends some day (project over, person left)
ACCESS_REMOVAL_RATE = 0.3  # its rule is removed when it ends
VENDOR_SHARE = 0.25
# Zone pairs (roles) a weekly job can run in; the hit count clear lands on one
# of them, drawn independently of every job (decision 0018).
CLEAR_PAIRS = (("servers", "internet"), ("servers", "management"), ("management", "servers"))
BACKUP = "app:shared-backup:bkp"


class MediumSimulation(Simulation):
    def __init__(self, level, seed: int) -> None:
        super().__init__(level, seed)
        root = Rng(f"palimp-sim:{level.name}:{seed}")
        self.rng_medium = root.derive("medium")
        self.rng_traps = root.derive("traps")
        self.rng_counts = root.derive("trap_counts")
        self.rng_clear = root.derive("hit_count_clear")
        self._copied_count = 0
        self.zone_names = dict(self.zone_names)
        self.zone_names["management"] = self.rng_medium.choice(catalog.MANAGEMENT_NAMES)
        self.config.zones.append(
            Zone(
                self.zone_names["management"],
                "management",
                *catalog.INTERFACES["management"],
            )
        )
        self._rule_number = self.rng_medium.randint(20, 60)
        self._jobs: dict[tuple[str, FlowTemplate], tuple[int, int, bool]] = {}
        self._protected: set[str] = set()  # job rules: their owners object to removal
        self._hosts: dict[str, Endpoint] = {}  # workstations and vendors of access requests
        self._emergency_apps: set[str] = set()

    # ------------------------------------------------------------------ hooks

    def _rate(self, admin: Admin, base: float) -> float:
        if admin.persona == AUTOMATION:
            return 1.0
        return min(1.0, base * PERSONA_FACTORS[admin.persona])

    def _tier_zone(self, app: App, tier) -> str:
        return "management" if app.app_id in catalog.MANAGEMENT_APPS else tier.zone_role

    def _unique(self, base: str) -> str:
        names = {p.name for p in self.config.policies}
        name, n = base, 2
        while name in names:
            name, n = f"{base}-{n}", n + 1
        return name

    def _name_for(self, flow: Flow, suffix: str, admin: Admin) -> str:
        if admin.persona == OPERATOR:
            self._rule_number += self.rng_medium.randint(1, 3)
            name = voice.operator_name(flow.app_id, self._rule_number, self.rng_medium)
            return self._unique(name)
        if admin.persona == AUTOMATION:
            target = flow.template.dst.split(":")[-1]
            names = {p.name for p in self.config.policies}
            n = 1
            while f"app-{flow.app_id}-{target}-{n:02d}" in names:
                n += 1
            return f"app-{flow.app_id}-{target}-{n:02d}"
        return self._policy_name(flow, suffix)

    def _commit_second(self, day: int, admin: Admin) -> int:
        if admin.persona == AUTOMATION:
            # Pipeline run after office hours, at a fixed time.
            return 19 * 3600 + 1800 + self.rng_times.randint(0, 300)
        return super()._commit_second(day, admin)

    def active_admin(self, day: int) -> Admin:
        active = [a for a in self.admins if a.active(day) and a.persona != AUTOMATION]
        return self.rng_admins.choice(active)

    def _app_admin(self, day: int) -> Admin:
        robots = [a for a in self.admins if a.active(day) and a.persona == AUTOMATION]
        if robots and self.rng_admins.chance(AUTOMATION_SHARE):
            return robots[0]
        return self.active_admin(day)

    def _new_flow(self, app: App, template: FlowTemplate, start: int) -> Flow:
        flow = super()._new_flow(app, template, start)
        job = self._jobs.get((app.app_id, template))
        if job:
            flow.period, flow.phase = job[0], job[1]
        return flow

    def _policies_for_flow(self, flow: Flow, app: App, event: Event, ticket) -> list[str]:
        job = self._jobs.get((app.app_id, flow.template))
        if job:
            uid = self._add_policy(flow, app, event, ticket, nolog=job[2])
            (self.traps.nolog_jobs if job[2] else self.traps.rare_jobs).append(uid)
            self._protected.add(uid)
            return [uid]
        admin = self.admin(event.admin_id)
        if (
            admin.persona == OPERATOR
            and flow.template.src == "users"
            and self.rng_medium.chance(OPERATOR_SPLIT_RATE)
        ):
            sites = self.config.address_sets["users-all"]
            return [self._add_policy(flow, app, event, ticket, sources=[site]) for site in sites]
        return [self._add_policy(flow, app, event, ticket)]

    # ------------------------------------------------------------------ setup

    def _make_people(self) -> None:
        rng = self.rng_company
        total = self.total_days
        names = rng.sample(
            [f"{f} {last}" for f in catalog.FIRST_NAMES for last in catalog.LAST_NAMES], 14
        )
        for name in names[:10]:
            self.people.append(Person(self.next_id("P", 3), name, rng.choice(catalog.TEAMS)))
        first = Admin("ADM-1", "", names[10], SENIOR, joined=-rng.randint(200, 900))
        operator = Admin("ADM-2", "", names[11], OPERATOR, joined=-rng.randint(30, 400))
        second_join = self.workday(rng.randint(total * 35 // 100, total * 55 // 100))
        second = Admin("ADM-3", "", names[12], SENIOR, joined=second_join)
        first.left = self.workday(second_join + rng.randint(30, 90))
        robot_join = self.workday(rng.randint(total * 50 // 100, total * 65 // 100))
        robot = Admin("ADM-4", "svc-ansible", "Ansible automation", AUTOMATION, joined=robot_join)
        for admin in (first, operator, second):
            given, family = admin.name.split(" ")
            admin.login = (given[0] + family).lower()
        self.admins = [first, operator, second, robot]

    # ------------------------------------------------------------------ events

    def _app_admin_new_app(self, app: App, day: int, admin: Admin, event: Event, ticket) -> list:
        self._create_servers(app, day)
        app.go_live = day if app.shared else day + self.rng_events.randint(0, 2)
        if not app.shared:
            app.extra_flows += self._integrations(app, day)
        created = []
        for template in list(app.template.flows) + app.extra_flows:
            flow = self._new_flow(app, template, app.go_live)
            created += self._policies_for_flow(flow, app, event, ticket)
        return created

    def _inbound(self, app: App) -> list[tuple[str, str]]:
        """(tier, service) pairs other servers may call: servers zone, not web."""
        zones = {t.name: self._tier_zone(app, t) for t in app.template.tiers}
        # A tier every server already reaches (vault) needs no extra rule.
        wide = {(f.dst, f.services[0]) for f in app.template.flows if f.src == "servers-net"}
        found = []
        for flow in app.template.flows:
            if (flow.dst, flow.services[0]) in wide:
                continue
            if zones.get(flow.dst) == "servers" and flow.dst != "web":
                pair = (flow.dst, flow.services[0])
                if pair not in found:
                    found.append(pair)
        return found

    def _integrations(self, app: App, day: int) -> list[FlowTemplate]:
        """Calls from this application to other live applications (spec 2.3)."""
        rng = self.rng_medium
        draw = rng.random()
        count = (
            0 if draw < INTEGRATION_WEIGHTS[0] else 1 if draw < sum(INTEGRATION_WEIGHTS[:2]) else 2
        )
        tiers = [t.name for t in app.template.tiers if self._tier_zone(app, t) == "servers"]
        source = next((t for t in JOB_SOURCE_TIERS if t in tiers), tiers[0] if tiers else None)
        targets = [
            a
            for a in self.apps.values()
            if not a.shared
            and a is not app
            and a.go_live is not None
            and a.go_live <= day
            and a.retired is None
            and self._inbound(a)
        ]
        if source is None or not targets:
            return []
        flows = []
        for other in rng.sample(targets, min(count, len(targets))):
            tier, service = rng.choice(self._inbound(other))
            flows.append(
                FlowTemplate(
                    source,
                    f"app:{other.app_id}:{tier}",
                    (service,),
                    rng.choice(("business", "always")),
                    rng.randint(50, 400),
                    "app_dependency",
                    f"{app.name} exchanges data with another application",
                )
            )
        return flows

    def _endpoint(self, token: str, app: App):
        if token.startswith("app:"):
            _, other, tier = token.split(":")
            return self._tier_endpoint(self.apps[other], tier)
        if token in self._hosts:
            endpoint = self._hosts[token]
            self._ensure_address(endpoint.address, endpoint.prefixes[0])
            return endpoint
        return super()._endpoint(token, app)

    def _targets(self, flow: Flow, app_id: str) -> bool:
        return flow.template.dst.startswith(f"app:{app_id}:")

    def _decommission(self, app: App, day: int) -> None:
        # Calls from other applications stop too; their rules stay behind.
        for flow in self.flows.values():
            if self._targets(flow, app.app_id) and flow.active(day):
                flow.end = day
        super()._decommission(app, day)

    def _migrate(self, app: App, day: int) -> list[str]:
        """Duplicate style migration (world.py), including calls from other apps."""
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
            moved = flow.app_id == app.app_id or self._targets(flow, app.app_id)
            if moved and flow.active(day):
                flow.end = day
                owner = self.apps[flow.app_id]
                new_flow = self._new_flow(owner, flow.template, day)
                new_flow.period, new_flow.phase = flow.period, flow.phase
                created.append(self._add_policy(new_flow, owner, event, ticket, suffix="-new"))
        comment = self._comment(admin, "migration", app, ticket)
        commit = self._commit(day, admin, comment, event, created=created)
        for uid in created:
            self.policy_meta[uid].commit_seq = commit.seq
        self._pending_cleanup[app.app_id] = (old_policies, old_servers, ticket)
        return old_policies

    def _access(self, day: int, request: dict) -> None:
        """Ad hoc access for one workstation or one vendor (spec 2.3, S3)."""
        rng = self.rng_medium
        targets = [
            a
            for a in self.apps.values()
            if not a.shared
            and a.go_live is not None
            and a.go_live <= day
            and a.retired is None
            and self._inbound(a)
        ]
        if not targets:
            return
        app = rng.choice(targets)
        tier, service = rng.choice(self._inbound(app))
        number = len(self._hosts) + 1
        # A workstation rule for something users-all already reaches, or
        # behind an emergency rule, would be shadowed (TRAP-SHADOWED-DUPLICATE,
        # v2): those requests become vendor access.
        open_to_users = {
            (f.dst, s) for f in app.template.flows if f.src == "users" for s in f.services
        }
        if (tier, service) in open_to_users:
            tier, service = tier, "junos-ssh"
        shadowed = (tier, service) in open_to_users or app.app_id in self._emergency_apps
        if rng.chance(VENDOR_SHARE) or shadowed:
            token = f"vendor:vendor-{voice.code(app.app_id).lower()}-{number:02d}"
            vendors = sum(1 for t in self._hosts if t.startswith("vendor:"))
            name, ip = token.split(":")[1], f"203.0.113.{150 + vendors}"  # .150 to .254
            endpoint = Endpoint("internet", name, [f"{ip}/32"], name)
            kind = "partner_access"
            summary = "An outside support company maintains these servers remotely"
            service = "junos-ssh"
        else:
            person = rng.choice(self.people)
            site = rng.randint(1, self.level.user_sites)
            name = f"pc-{voice.initials(person.name).lower()}-{number:02d}"
            token = f"pc:{name}"
            pcs = sum(1 for t in self._hosts if t.startswith("pc:"))
            ip = f"10.10.{site}.{20 + pcs}"  # .20 to .254, distinct across sites too
            endpoint = Endpoint("users", name, [f"{ip}/32"], name)
            kind = "app_access"
            summary = "A named person's workstation reaches a back-end server directly"
        self._ensure_address(name, f"{ip}/32")
        self._hosts[token] = endpoint
        template = FlowTemplate(
            token, tier, (service,), "business", rng.randint(5, 40), kind, summary
        )
        operators = [a for a in self.admins if a.active(day) and a.persona == OPERATOR]
        if operators and rng.chance(0.7):
            admin = operators[0]
        else:
            admin = self.active_admin(day)
        event = self._event("access_request", day, admin, app)
        ticket = self._ticket(day, admin, app, "access", "access")
        event.ticket_id = ticket.ticket_id if ticket else None
        flow = self._new_flow(app, template, day + 1)
        created = [self._add_policy(flow, app, event, ticket)]
        comment = self._comment(admin, "access", app, ticket)
        commit = self._commit(day, admin, comment, event, created=created)
        self.policy_meta[created[0]].commit_seq = commit.seq
        request["flow"] = flow.flow_id

    def _access_end(self, day: int, request: dict) -> None:
        """Temporary access ends; the rule is removed only sometimes."""
        flow = self.flows.get(request.get("flow", ""))
        if flow is None or not flow.active(day):
            return
        flow.end = day
        if not self.rng_medium.chance(ACCESS_REMOVAL_RATE):
            return
        uids = [
            p.uid
            for p in self.config.policies
            if self.policy_meta[p.uid].flow_ids == [flow.flow_id]
        ]
        if not uids:
            return
        admin = self.active_admin(day)
        app = self.apps[flow.app_id]
        event = self._event("access_request", day, admin, app, note="access removed")
        self._remove_policies(uids)
        comment = self._comment(admin, "access_end", app, None)
        commit = self._commit(day, admin, comment, event, removed=uids)
        for uid in uids:
            self.traps.removed_by[uid] = commit.seq

    def _batch(self, apps: list[App], day: int) -> None:
        """One commit for the go-live of several applications (TRAP-BATCH-COMMIT)."""
        operators = [a for a in self.admins if a.active(day) and a.persona == OPERATOR]
        admin = self.rng_admins.choice(operators) if operators else self.active_admin(day)
        events, created = [], []
        for app in apps:
            event = self._event("new_app", day, admin, app, note="batch commit")
            ticket = self._ticket(day, admin, app, "change", "change")
            event.ticket_id = ticket.ticket_id if ticket else None
            created += self._app_admin_new_app(app, day, admin, event, ticket)
            events.append(event)
        comment = voice.batch_comment(apps[0].app_id, self.rng_traps)
        commit = self._commit(day, admin, comment, events[0], created=created)
        for event in events[1:]:
            event.commits.append(commit.seq)
        for uid in created:
            self.policy_meta[uid].commit_seq = commit.seq
        self.traps.batch_commits[commit.seq] = apps[0].app_id

    def _emergency(self, app: App, day: int) -> None:
        """Broad rule on top of users to servers during an incident (spec 4.4)."""
        rng = self.rng_traps
        admin = self.active_admin(day)
        event = self._event("emergency_rule", day, admin, app, note="incident, on-call change")
        users, servers = self.zone("users"), self.zone("servers")
        flows = [
            f
            for f in self.flows.values()
            if f.app_id == app.app_id
            and f.active(day)
            and f.src.zone_role == "users"
            and f.dst.zone_role == "servers"
        ]
        # The rule was for the application's own user flows; it also covers
        # workstation access rules to the same servers, which it shadows too.
        intended = [f for f in flows if f.template.src == "users"]
        matcher = Matcher(self.config, dict(self.zone_names))
        shadowed = []
        for flow in flows:
            for src, dst, service in _parts(flow):
                uid = matcher.match(flow, src, dst, service_port(service))
                if uid and uid not in shadowed:
                    shadowed.append(uid)
        net = self._ensure_address(f"{app.app_id}-net", f"10.20.{10 + app.index}.0/24")
        description = None
        if rng.chance(EMERGENCY_DESCRIPTION_RATE):
            description = voice.description("on_call", intended[0], None, "", rng)
        policy = Policy(
            uid=self.next_id("R"),
            name=self._unique(voice.on_call_name(rng)),
            from_zone=users,
            to_zone=servers,
            sources=["users-all"],
            destinations=[net],
            applications=[ANY],
            log_close=rng.chance(EMERGENCY_LOG_RATE),
            description=description,
        )
        top = next(
            i
            for i, p in enumerate(self.config.policies)
            if (p.from_zone, p.to_zone) == (users, servers)
        )
        self.config.policies.insert(top, policy)
        self.policy_meta[policy.uid] = PolicyMeta(
            policy.uid,
            app.app_id,
            [f.flow_id for f in intended],
            event.event_id,
            -1,
            admin.admin_id,
            None,
            intent_kind="emergency_temporary",
            summary=f"Temporary broad access opened during an incident on {app.name}",
        )
        if self.date(day).weekday() >= 5:
            second = rng.randint(10 * 3600, 20 * 3600)
        else:
            second = rng.randint(21 * 3600, 23 * 3600 + 3000)
        comment = voice.commit_comment("on_call", "emergency", app.app_id, None, rng)
        commit = self._commit(day, admin, comment, event, created=[policy.uid], second=second)
        self.policy_meta[policy.uid].commit_seq = commit.seq
        self.traps.emergency[policy.uid] = shadowed
        self._emergency_apps.add(app.app_id)

    def _partial_cleanup(self, day: int) -> None:
        """Rules that carry no traffic are removed or deactivated (spec 4.5).

        The rules shadowed by an emergency rule carry nothing, so they go first.
        Job rules are kept: their owners object (S2: some rules are needed
        although used less often than the review window).
        """
        rng = self.rng_traps
        admin = self.active_admin(day)
        event = self._event("partial_cleanup", day, admin, note="rules without hits")
        matcher = Matcher(self.config, dict(self.zone_names))
        carried = set()
        for flow in self.flows.values():
            # Flows that have not started yet count: their rules are new.
            if flow.end is None or day < flow.end:
                for src, dst, service in _parts(flow):
                    carried.add(matcher.match(flow, src, dst, service_port(service)))
        shadowed = {uid for uids in self.traps.emergency.values() for uid in uids}
        unused = [
            p.uid
            for p in self.config.policies
            if not p.inactive and p.uid not in carried and p.uid not in self._protected
        ]
        removed, deactivated, kept = [], [], []
        for uid in unused:
            draw = rng.random()
            if uid in shadowed or draw < self.level.cleanup_rate:
                removed.append(uid)
            elif draw < self.level.cleanup_rate + self.level.cleanup_deactivate_rate:
                deactivated.append(uid)
            else:
                kept.append(uid)
        if kept and not deactivated:
            deactivated.append(kept.pop(0))
        for policy in self.config.policies:
            if policy.uid in deactivated:
                policy.inactive = True
        self._remove_policies(removed)
        comment = self._comment(admin, "cleanup", None, None)
        commit = self._commit(day, admin, comment, event, removed=removed)
        for uid in removed:
            self.traps.removed_by[uid] = commit.seq

    def _admin_change(self, day: int, target: Admin, joining: bool) -> None:
        admin = self.active_admin(day)
        kind = "admin_join" if joining else "admin_leave"
        event = self._event(kind, day, admin, note=target.admin_id)
        if joining:
            self.config.logins.append(target.login)
        else:
            self.config.logins.remove(target.login)
        comment = self._comment(admin, kind, None, None, login=target.login)
        self._commit(day, admin, comment, event)

    def _new_app(self, app: App, day: int) -> None:
        admin = self._app_admin(day) if not app.shared else self.active_admin(day)
        event = self._event("new_app", day, admin, app)
        ticket = self._ticket(day, admin, app, "change", "change")
        event.ticket_id = ticket.ticket_id if ticket else None
        created = self._app_admin_new_app(app, day, admin, event, ticket)
        kind = "shared" if app.shared else "new_app"
        comment = self._comment(admin, kind, app, ticket, rules=len(created))
        commit = self._commit(day, admin, comment, event, created=created)
        for uid in created:
            self.policy_meta[uid].commit_seq = commit.seq

    # ------------------------------------------------------------------ plan

    def _add_job(
        self, app: App, kind: str, phase: int, pair: tuple[str, str] = CLEAR_PAIRS[0]
    ) -> None:
        service, base, intent, summary = catalog.JOB_KINDS[kind]
        tiers = [t.name for t in app.template.tiers if self._tier_zone(app, t) == "servers"]
        own = next((t for t in JOB_SOURCE_TIERS if t in tiers), tiers[0])
        if pair == ("servers", "management"):
            source, target, intent = own, BACKUP, "backup"
            summary = "Weekly database dump copied to the backup server"
        elif pair == ("management", "servers"):
            source, target, intent = BACKUP, own, "backup"
            summary = "Backup server collects a weekly full export from the application"
        else:
            flows = app.template.flows
            used = {f.dst.split(":", 1)[1] for f in flows if f.dst.startswith("partner:")}
            partner = self.rng_traps.choice([p for p in catalog.JOB_PARTNERS if p not in used])
            source, target = own, f"partner:{partner}"
        template = FlowTemplate(source, target, (service,), kind, base, intent, summary)
        app.extra_flows.append(template)
        self._jobs[(app.app_id, template)] = (catalog.JOB_PERIODS[kind], phase, kind == "weekly")

    def run(self) -> "MediumSimulation":
        self._make_people()
        rng = self.rng_events
        traps = self.rng_traps
        level = self.level
        total = self.total_days
        plan: list[tuple[int, int, str, object]] = [(0, 0, "bootstrap", None)]

        for index, template in enumerate(catalog.SHARED + catalog.SHARED_MEDIUM):
            owner = rng.choice(self.people).person_id
            app = App(template.app_id, template.name, owner, True, template, index)
            self.apps[app.app_id] = app
            plan.append((self.workday(1 + 3 * index), 1, "new_app", app))

        templates = rng.sample(catalog.APPS + catalog.EXTRA_APPS, level.applications)
        days = sorted(rng.randint(30, total - 120) for _ in templates)
        go_lives: dict[str, int] = {}
        apps: list[App] = []
        for index, (template, day) in enumerate(zip(templates, days, strict=True)):
            owner = rng.choice(self.people).person_id
            app = App(template.app_id, template.name, owner, False, template, index)
            self.apps[app.app_id] = app
            apps.append(app)
            go_lives[app.app_id] = self.workday(day)

        # Trap subjects, drawn from their own generator.
        early = [a for a in apps if go_lives[a.app_id] <= total - 400]

        def servers_users_flow(app: App) -> bool:
            zones = {t.name: t.zone_role for t in app.template.tiers}
            return any(
                f.src == "users" and zones.get(f.dst) == "servers" and f.kind == "app_access"
                for f in app.template.flows
            )

        counts = {
            name: self.rng_counts.weighted(weights) for name, weights in TRAP_COUNT_WEIGHTS.items()
        }
        self._copied_count = counts["copied_comments"]
        candidates = [a for a in early if servers_users_flow(a)]
        emergency_apps = traps.sample(candidates, min(counts["emergencies"], len(candidates)))
        job_candidates = [
            a
            for a in early
            if a not in emergency_apps
            and any(self._tier_zone(a, t) == "servers" for t in a.template.tiers)
        ]
        kinds = (
            ["weekly"] * counts["nolog_jobs"]
            + ["yearly"] * counts["yearly_jobs"]
            + ["quarterly"] * counts["quarterly_jobs"]
        )
        job_apps = traps.sample(job_candidates, min(len(kinds), len(job_candidates)))
        # One zone pair is cleared a few days before the snapshot, whatever the
        # jobs are. Weekly jobs without logging are put in that pair and last
        # ran in the days before the clear (and less than a week before the
        # snapshot, so they did not run again).
        clear_roles = self.rng_clear.choice(CLEAR_PAIRS)
        clear_day = total - self.rng_clear.randint(2, 5)
        self.pair_resets[(self.zone(clear_roles[0]), self.zone(clear_roles[1]))] = clear_day
        for kind, app in zip(kinds, job_apps, strict=False):
            if kind == "weekly":
                last_run = traps.randint(total - 6, clear_day - 1)
                self._add_job(app, kind, last_run, clear_roles)
            elif kind == "yearly":
                self._add_job(app, kind, total - traps.randint(200, 350))
            else:
                self._add_job(app, kind, total - traps.randint(1, 91))
        protected = {a.app_id for a in emergency_apps + job_apps}
        others = [a for a in apps if a.app_id not in protected]
        batches = []
        for _ in range(counts["batch_commits"]):
            batch = traps.sample(others, 3 if traps.chance(0.3) else 2)
            others = [a for a in others if a not in batch]
            batches.append((self.workday(traps.randint(total - 110, total - 40)), batch))
        batched = {a.app_id for _, batch in batches for a in batch}

        for app in apps:
            if app.app_id not in batched:
                plan.append((go_lives[app.app_id], 1, "new_app", app))
        for day, batch in batches:
            plan.append((day, 1, "batch", sorted(batch, key=lambda a: a.index)))

        eligible = [
            (go_lives[a.app_id], a)
            for a in apps
            if a.app_id not in protected
            and a.app_id not in batched
            and go_lives[a.app_id] < total - 300
        ]
        decommissions = round(level.years * level.decommissions_per_year)
        migrations = round(level.years * level.migrations_per_year)
        chosen = rng.sample(eligible, min(decommissions + migrations, len(eligible)))
        for go_live, app in chosen[:decommissions]:
            day = rng.randint(go_live + 150, total - 30)
            plan.append((self.workday(day), 2, "decommission", app))
        for go_live, app in chosen[decommissions:]:
            day = self.workday(rng.randint(go_live + 120, total - 90))
            plan.append((day, 2, "migration", app))
            plan.append((self.workday(day + rng.randint(7, 30)), 3, "migration_cleanup", app))

        # Hit count based cleanups, one a year whatever the incidents; each
        # emergency happens 90 to 150 days before one of them.
        cleanups = sorted(self.workday(traps.randint(180, total - 50)) for _ in range(level.years))
        for day in cleanups:
            plan.append((day, 3, "cleanup", None))
        for app in emergency_apps:
            first = go_lives[app.app_id] + 60
            fitting = [day for day in cleanups if day - 90 >= first]
            if fitting:
                cleanup = traps.choice(fitting)
                day = traps.randint(max(first, cleanup - 150), cleanup - 90)
            else:
                day = traps.randint(first, total - 200)
                plan.append((self.workday(day + traps.randint(90, 150)), 3, "cleanup", None))
            plan.append((day, 2, "emergency", app))

        for _ in range(round(level.years * ACCESS_PER_YEAR)):
            request: dict = {}
            day = self.workday(rng.randint(60, total - 30))
            plan.append((day, 2, "access", request))
            if rng.chance(ACCESS_TEMPORARY_RATE):
                end = day + rng.randint(30, 400)
                if end < total:
                    plan.append((self.workday(end), 3, "access_end", request))

        upgrade_day = total - level.days_since_hit_reset
        if upgrade_day > 0:
            plan.append((self.workday(upgrade_day), 4, "upgrade", None))
        for admin in self.admins[2:]:
            plan.append((admin.joined, 0, "admin_join", admin))
        plan.append((self.admins[0].left, 5, "admin_leave", self.admins[0]))

        # Most access ends make no commit: count the expected ones only.
        ends = sum(1 for entry in plan if entry[2] == "access_end")
        expected = len(plan) - ends + round(ends * ACCESS_REMOVAL_RATE)
        routine_count = max(0, level.commits_per_year * level.years - expected)
        for _ in range(routine_count):
            plan.append((self.workday(rng.randint(5, total - 1)), 6, "routine", None))

        handlers = {
            "bootstrap": lambda day, _: self._bootstrap(day),
            "new_app": lambda day, app: self._new_app(app, day),
            "batch": lambda day, group: self._batch(group, day),
            "decommission": lambda day, app: self._decommission(app, day),
            "migration": lambda day, app: self._migrate(app, day),
            "migration_cleanup": lambda day, app: self._migration_cleanup(app, day),
            "emergency": lambda day, app: self._emergency(app, day),
            "access": lambda day, request: self._access(day, request),
            "access_end": lambda day, request: self._access_end(day, request),
            "cleanup": lambda day, _: self._partial_cleanup(day),
            "upgrade": lambda day, _: self._upgrade(day),
            "admin_join": lambda day, admin: self._admin_change(day, admin, True),
            "admin_leave": lambda day, admin: self._admin_change(day, admin, False),
            "routine": lambda day, _: self._routine(day),
        }
        for day, _, kind, subject in sorted(plan, key=lambda p: (p[0], p[1])):
            handlers[kind](day, subject)
        self._copy_pasted_comments()
        return self

    def _copy_pasted_comments(self) -> None:
        """Comments copied from an earlier commit about another application.

        The number of copied comments is drawn per scenario; each goes to a
        retained commit whose rules survive to the snapshot. Older commits are
        not shown, so changing them would make no trap.
        """
        rng = self.rng_traps
        events = {e.event_id: e for e in self.events}
        first_retained = max(0, len(self.commits) - RETAINED)

        def app_of(commit) -> str | None:
            event = events[commit.event_id]
            kinds = ("new_app", "migration", "access_request")
            return event.app_id if event.kind in kinds else None

        creating = [c for c in self.commits if c.created and app_of(c)]
        final = {p.uid for p in self.config.policies}

        def source_of(commit):
            # The copied comment names an application none of its rules serve.
            served = {self.policy_meta[uid].app_id for uid in commit.created}
            earlier = [c for c in creating if c.seq < commit.seq and app_of(c) not in served]
            return earlier[-1] if earlier else None

        # People copy comments; the automation account writes its own template.
        candidates = [
            c
            for c in creating
            if c.seq >= first_retained
            and c.seq not in self.traps.batch_commits
            and self.admin(c.admin_id).persona != AUTOMATION
            and source_of(c) is not None
        ]
        # Each must leave a rule in the final config to carry the tag.
        visible = [c for c in candidates if any(uid in final for uid in c.created)]
        chosen = rng.sample(visible, min(self._copied_count, len(visible)))
        for commit in sorted(chosen, key=lambda c: c.seq):
            source = source_of(commit)
            other = app_of(source)
            if source.comment and voice.code(other) in source.comment:
                text = source.comment
            else:
                ticket = events[source.event_id].ticket_id
                text = voice.commit_comment(SENIOR, "new_app", other, ticket, rng, rules=2)
            commit.comment = text
            self.traps.misleading_comments[commit.seq] = other


def _parts(flow: Flow):
    for src in flow.src.prefixes:
        for dst in flow.dst.prefixes:
            for service in flow.template.services:
                yield src, dst, service
