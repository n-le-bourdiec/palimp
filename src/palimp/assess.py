"""Deterministic verdict and confidence for one finding (decision 0020).

Every output names the rule that produced it and cites evidence IDs.

Verdict rules, first match wins:
- V-CLEANUP-RULE (keep): an active catch-all deny (any source, any destination,
  any application): the cleanup rule (decision 0044).
- V-SHARED-ADDRESS (verify): a destination address is also an object named after
  another application, and traffic is seen or a not-live signal exists: the
  address may have been reused (or the application renamed). Never keep, never
  removal_candidate (session 24).
- V-CONTRADICTION (verify): a positive not-live signal, but traffic is seen.
  When the only logged traffic is probe traffic (scanner or monitoring, see
  palimp.formats.rt_flow), hits on the counters do not count as traffic seen.
- V-DENY-NOTLIVE (verify): the same on an active deny or reject rule: removing a
  block opens traffic, so a deny is a removal candidate only when deactivated.
- V-NOTLIVE (removal_candidate): a positive not-live signal, no traffic seen.
- V-PROBE-ONLY (verify): the only logged traffic is probe traffic, no
  not-live signal: not in use as far as the artifacts show, not unused either.
- V-TEMPORARY-IN-USE (verify): traffic seen on a policy marked temporary that
  permits any application (the shape of an emergency opening). A narrow
  policy with a "temp" label is judged like any other. Policies it took over
  (removed or deactivated while it existed, covered by its match) are cited.
- V-TAKEOVER-IN-USE (verify): the same shape without the label: a policy that
  permits any application, carries traffic and took over removed or
  deactivated policies is load-bearing for flows it was not written for.
- V-TRAFFIC-NOT-RECENT (verify): hits on the counters, but a logging policy
  logged no session in the log window: the hits are older than the window.
  Never removal_candidate: old hits are still hits.
- V-TRAFFIC-STOPPED (verify): logged traffic was dense, then stopped well
  before the end of the log window.
- V-NAME-SERVICE (verify): traffic seen, but the policy name names a service
  the matched applications do not offer (`ALLOW-SNMP` on junos-https,
  decision 0043). Never keep; the question goes to the firewall team.
- V-FACTORY-DEFAULT, V-BROAD-PERMIT (verify): a Junos factory default policy, or
  any other permit of any source to any destination for any application
  (palimp.semantics): at most verify, asked of the firewall team (decision 0044).
- V-TRAFFIC (keep): traffic seen.
- V-NO-TRAFFIC-SEEN (verify): artifacts could show traffic and show none.
  Absence is never evidence of absence: this never gives removal_candidate.
- V-NO-VISIBILITY (verify): no artifact can show traffic for this policy.

Confidence rules (about the intent), first match wins:
- C-CLEANUP, C-FACTORY-DEFAULT (MEDIUM): a catch-all deny or a factory default
  policy, from its match alone (decision 0044).
- C-T1-T3-CONFLICT: a T1 item names applications that the address objects do
  not name. One level below what the agreeing evidence alone would give.
- C-T1-T3-AGREE (HIGH): T1 names an application the address objects name,
  and traffic is seen (T2 present).
- C-T1-T3-AGREE-NO-TRAFFIC (MEDIUM): the same without traffic seen: the
  documented intent may be stale (deactivated, rare or unlogged policy).
- C-T1-ONLY (MEDIUM): T1 names an application, the objects name none.
- C-T3 (MEDIUM): two independent names point to the same application
  (decisions 0042 and 0043): the address objects (both sides together count
  once: one naming convention), the policy name, a custom application or
  application-set name. Only the confirmed applications make the intent:
  names a single source gives are left out (decision 0044).
  A well-known port counts as a source for the product it stands for
  (`tcp/8834` and an object naming nessus), and a server role that offers the
  service of the port names that service with two sources when no name names
  an application (a `dns` object on udp/53 names dns), decision 0043.
- C-DYNAMIC-APP (MEDIUM): a dynamic application names the application: the
  rule's own match criterion, not a name chosen by a person (decision 0043).
  Never HIGH without traffic.
- C-T3-SINGLE (LOW): only one of those names points to an application. A name
  alone may be a place, a person or a generic word (`dan-pc`, `en-srv`), so it
  stays LOW until a second source names the same application. This only
  lowers confidence, it never changes a verdict.
- C-WEAK (LOW): nothing names an application (T1 without one, T4 only). When
  the object names state server roles (`sql`, `web`, palimp.apps), the intent
  describes the flow by them ("SMB file sharing between SQL servers") without
  naming an application.
T4 alone can never exceed LOW.
Then a cap: C-AMBIGUOUS-INSTANCE (MEDIUM at most): the application named
first is the bare name of regional instances (`payroll` with `payroll-uk` and
`payroll-pl`, palimp.apps); its candidates are listed after it. A bare name
and one of its instances are compatible: neither agreement nor conflict.
"""

import re

from palimp.models import Assessment, Conflict, Dataset, Evidence, Finding
from palimp.owners import find_owner
from palimp.semantics import is_deny
from palimp.services import ROLE_SERVICES, aliases

# Evidence kinds that say a policy is unused (decision 0020), not that nothing is known.
NOT_LIVE_KINDS = frozenset({"deactivated", "decommission", "migration_leftover"})
LEVELS = ("LOW", "MEDIUM", "HIGH")
# T1 kinds that state why a policy exists (a decommission states why it ended).
INTENT_KINDS = frozenset({"description", "annotation", "commit_comment", "ticket"})
# T3 and T4 items whose names may point to an application, each one independent source
# (decision 0042). Address objects count once, both sides together (decision 0043).
NAMING = {
    "policy_name": "the policy name",
    "services": "a custom application name",
    "dynamic_application": "a dynamic application",
}
# Sources that may confirm a two-letter name, with a port and a dynamic application
# (decision 0044): never the policy name.
SHORT_SOURCES = {
    "address_objects": "the address objects",
    "services": NAMING["services"],
    "description": "the description",
    "annotation": "an annotation",
}


def _ids(items: list[Evidence]) -> list[str]:
    return [e.id for e in items]


def _in_use(finding: Finding) -> list[Evidence]:
    """T2 items that show traffic. When the only logged traffic is probe traffic, hits on
    the counters are not business use (session 24)."""
    present = [e for e in finding.evidence if e.tier == "T2" and e.signal == "present"]
    if any(e.kind == "probe_only" for e in finding.evidence):
        present = [e for e in present if e.kind != "hit_count"]
    return present


def _verdict(finding: Finding) -> tuple[str, str, str, list[str]]:
    evidence = finding.evidence
    not_live = [e for e in evidence if e.kind in NOT_LIVE_KINDS]
    present = _in_use(finding)
    policy = finding.policy
    catch_all = [e for e in evidence if e.kind == "catch_all_deny"]
    if catch_all and not policy.deactivated:
        return (
            "keep",
            "V-CLEANUP-RULE",
            "a catch-all deny: the cleanup rule that blocks whatever no rule above permits",
            _ids(catch_all + present),
        )
    probe = [e for e in evidence if e.kind == "probe_only"]
    absent = [e for e in evidence if e.tier == "T2" and e.signal == "absent"]
    temporary = [e for e in evidence if e.kind == "temporary_marker"]
    shared = [e for e in evidence if e.kind == "shared_address"]
    if shared and (present or not_live):
        return (
            "verify",
            "V-SHARED-ADDRESS",
            "a destination address is also an object of another application: the rule may "
            "carry traffic it was not written for, or serve an application under a new name",
            _ids(shared + not_live + present),
        )
    if not_live and present:
        return (
            "verify",
            "V-CONTRADICTION",
            "a not-live signal and traffic seen contradict each other",
            _ids(not_live + present),
        )
    if not_live and is_deny(policy) and not policy.deactivated:
        return (
            "verify",
            "V-DENY-NOTLIVE",
            "a not-live signal on a rule that blocks traffic: removing a block opens that "
            "traffic, so a deny rule is never a removal candidate unless it is deactivated",
            _ids(not_live + [e for e in evidence if e.tier == "T2"]),
        )
    if not_live:
        return (
            "removal_candidate",
            "V-NOTLIVE",
            "a positive not-live signal, and no traffic seen",
            _ids(not_live + absent),
        )
    if probe and not present:
        hits = [e for e in evidence if e.kind == "hit_count"]
        return (
            "verify",
            "V-PROBE-ONLY",
            "the only logged traffic comes from scanner or monitoring probes: the policy is not "
            "shown to be in use, and that is no proof it is unused",
            _ids(probe + absent + hits),
        )
    broad = [e for e in evidence if e.kind == "services" and "any" in finding.policy.applications]
    took = [e for e in evidence if e.kind == "takeover"]
    if present and temporary and broad:
        reason = (
            "a policy marked temporary that permits any application carries traffic: "
            "it may now be load-bearing"
        )
        if took:
            reason += ", and it took over the match of removed or deactivated policies"
        return "verify", "V-TEMPORARY-IN-USE", reason, _ids(temporary + broad + took + present)
    if present and took and broad:
        return (
            "verify",
            "V-TAKEOVER-IN-USE",
            "a policy that permits any application carries traffic and took over the match "
            "of removed or deactivated policies: it is load-bearing for flows it was not "
            "written for",
            _ids(took + broad + present),
        )
    hits = [e for e in present if e.kind == "hit_count"]
    quiet_log = [e for e in absent if e.kind == "session_log"]
    if hits and quiet_log and not [e for e in present if e.kind == "session_log"]:
        cleared = [e for e in evidence if e.kind == "counter_clear"]
        reason = (
            "hits on the counters, but no session logged in the log window although the "
            "policy logs: the hits are older than the window, the traffic may have stopped"
        )
        if cleared:
            reason = (
                "hits on the counters, no session logged in the log window although the "
                "policy logs, and counters of this zone pair were cleared inside the window: "
                "either this counter was not cleared and the hits are old, or logging misses "
                "this traffic"
            )
        return "verify", "V-TRAFFIC-NOT-RECENT", reason, _ids(hits + quiet_log + cleared)
    stop = [e for e in absent if e.kind == "log_stopped"]
    if stop:
        return (
            "verify",
            "V-TRAFFIC-STOPPED",
            "logged traffic stopped well before the end of the log window: the flow may have ended",
            _ids(stop),
        )
    mismatch = [e for e in evidence if e.kind == "name_service_mismatch"]
    if present and mismatch:
        return (
            "verify",
            "V-NAME-SERVICE",
            "traffic seen, but the policy name names a service the rule does not match: "
            "the rule may not do what its name says",
            _ids(mismatch + present),
        )
    t2 = [e for e in evidence if e.tier == "T2" and e.signal != "blind"] or [
        e for e in evidence if e.tier == "T2"
    ]
    factory = [e for e in evidence if e.kind == "factory_default"]
    if factory:
        return (
            "verify",
            "V-FACTORY-DEFAULT",
            "a Junos factory default policy: it permits everything between its zones and may "
            "have been kept from the initial setup, a question for the firewall team",
            _ids(factory + t2),
        )
    broad = [e for e in evidence if e.kind == "broad_permit"]
    if broad:
        return (
            "verify",
            "V-BROAD-PERMIT",
            "a broad permit (any source, any destination, any application): at most verify, "
            "a question for the firewall team",
            _ids(broad + t2),
        )
    if present:
        return "keep", "V-TRAFFIC", "traffic seen", _ids(present)
    if absent:
        return (
            "verify",
            "V-NO-TRAFFIC-SEEN",
            "no traffic seen, which does not prove the policy is unused "
            "(rare job, cleared counters)",
            _ids(absent),
        )
    blind = [e for e in evidence if e.tier == "T2"]
    return (
        "verify",
        "V-NO-VISIBILITY",
        "no artifact can show traffic for this policy",
        _ids(blind),
    )


def _confidence(finding: Finding) -> tuple[str, str, str, list[str], list[str], list[Conflict]]:
    evidence = finding.evidence
    # The match and action alone say what these rules are for (session 29).
    for kind, rule, reason in (
        ("catch_all_deny", "C-CLEANUP", "a catch-all deny is a cleanup rule by its match"),
        (
            "factory_default",
            "C-FACTORY-DEFAULT",
            "the zones, name and match are those of a Junos factory default policy",
        ),
    ):
        if found := [e for e in evidence if e.kind == kind]:
            return "MEDIUM", rule, reason, _ids(found), [], []
    direct = [e for e in evidence if e.tier == "T1" and e.apps and e.kind in INTENT_KINDS]
    objects = next((e for e in evidence if e.kind == "address_objects" and e.apps), None)
    object_apps = set(objects.apps) if objects else set()
    agree = [e for e in direct if object_apps & set(e.apps)]
    # A bare name of regional instances (`ci`) is compatible with one of its
    # instances (`ci-it`): no conflict, but no agreement either.
    instances = {e.apps[0]: set(e.apps) for e in evidence if e.kind == "ambiguous_app"}
    conflicts = []
    if objects:
        for item in direct:
            compatible = all(object_apps & instances.get(a, set()) for a in item.apps)
            if not object_apps & set(item.apps) and not compatible:
                conflicts.append(
                    Conflict(
                        evidence=[item.id, objects.id],
                        text=(
                            f"{item.id} names {', '.join(item.apps)}, "
                            f"while the address objects in {objects.id} name "
                            f"{', '.join(objects.apps)}"
                        ),
                    )
                )
    apps = list(dict.fromkeys([a for e in agree for a in e.apps if a in object_apps]))
    if not apps:
        apps = list(objects.apps) if objects else []
    if not apps and direct and not conflicts:
        apps = list(dict.fromkeys(a for e in direct for a in e.apps))

    if conflicts:
        in_use = bool(_in_use(finding))
        base = "HIGH" if agree and in_use else "MEDIUM"
        level = LEVELS[LEVELS.index(base) - 1]
        cited = sorted({i for c in conflicts for i in c.evidence} | set(_ids(agree)), key=_order)
        reason = "tiers contradict each other on the application, confidence lowered"
        return level, "C-T1-T3-CONFLICT", reason, cited, apps, conflicts
    present = _in_use(finding)
    if agree and present:
        reason = "direct evidence names the same application as the address objects, in use"
        cited = _ids(agree) + [objects.id] + _ids(present)
        return "HIGH", "C-T1-T3-AGREE", reason, cited, apps, []
    if agree:
        reason = (
            "direct evidence names the same application as the address objects, "
            "but no traffic is seen to confirm it is current"
        )
        cited = _ids(agree) + [objects.id]
        return "MEDIUM", "C-T1-T3-AGREE-NO-TRAFFIC", reason, cited, apps, []
    if direct:
        reason = "direct evidence names an application, the address objects do not confirm it"
        return "MEDIUM", "C-T1-ONLY", reason, _ids(direct), apps, []
    named = _named(evidence)
    if named:
        apps = list(named)
        sure = [a for a in apps if len(named[a]) >= 2]
        dynamic = [a for a in apps if NAMING["dynamic_application"] in {w for w, _ in named[a]}]
        if dynamic and not sure:
            apps = dynamic + [a for a in apps if a not in dynamic]
            reason = (
                "a dynamic application names the application: the rule's own match "
                "criterion, not a name chosen by a person (" + _sources(dynamic, named) + ")"
            )
            cited = sorted({i for a in dynamic for _, i in named[a]}, key=_order)
            return "MEDIUM", "C-DYNAMIC-APP", reason, cited, apps, []
        if sure:
            # Names only one source gives leave the intent once one name is confirmed
            # (session 29): `mb` confirmed, the person names of the sources do not follow.
            apps = sure
            reason = "two independent names point to the application: " + _sources(sure, named)
            cited = sorted({i for a in sure for _, i in named[a]}, key=_order)
            return "MEDIUM", "C-T3", reason, cited, apps, []
        reason = f"only one source names each application ({_sources(apps, named)}), "
        reason += "no second source confirms it"
        if any(w != NAMING["dynamic_application"] for a in apps for w, _ in named[a]):
            reason += "; a name alone may be a place, a person or a generic word"
        cited = sorted({i for a in apps for _, i in named[a]}, key=_order)
        return "LOW", "C-T3-SINGLE", reason, cited, apps, []
    weak = [e for e in evidence if e.tier in ("T1", "T3", "T4") and e.kind != "deactivated"]
    reason = "nothing names an application; ports and labels alone"
    return "LOW", "C-WEAK", reason, _ids(weak), [], []


def _named(evidence: list[Evidence]) -> dict[str, set[tuple[str, str]]]:
    """Each application T3 and T4 names point to, with the independent sources naming it
    (what, evidence ID), in order of first mention."""
    found: dict[str, set[tuple[str, str]]] = {}
    for item in evidence:
        if item.kind == "address_objects" and item.apps:
            # Both sides together are one source: the same prefix on each side of a
            # rule is one naming convention (decision 0043).
            for app in item.apps:
                found.setdefault(app, set()).add(("the address objects", item.id))
        elif item.kind in NAMING:
            for app in item.apps:
                found.setdefault(app, set()).add((NAMING[item.kind], item.id))
    services = next((e for e in evidence if e.kind == "services"), None)
    ports = services.port_apps if services else []
    # Two-letter names (`bi`): only with two sources, never alone (decision 0043), and
    # never confirmed by the policy name, which follows the naming convention of the
    # objects (decision 0044): a port, a dynamic application, a custom application
    # name or a description confirms them.
    short: dict[str, set[tuple[str, str]]] = {}
    for item in evidence:
        what = SHORT_SOURCES.get(item.kind)
        for app in item.short_apps if what else []:
            short.setdefault(app, set()).add((what, item.id))
    for app, sources in short.items():
        if services and set(ports) & aliases(app):
            sources.add(("a well-known port", services.id))
        for item in evidence:
            if item.kind == "dynamic_application" and app in item.apps:
                sources.add((NAMING["dynamic_application"], item.id))
        if len(sources) >= 2:
            found.setdefault(app, set()).update(sources)
    if not services or not ports:
        return found
    port = ("a well-known port", services.id)
    # A port known for a product, with a name naming that product (decision 0043).
    for app in found:
        if set(ports) & aliases(app):
            found[app].add(port)
    # A server role offering the service of the port names that service, when no name
    # names an application: `billing-db-01` on tcp/1433 is for billing, not mssql.
    if found:
        return found
    objects = next((e for e in evidence if e.kind == "address_objects"), None)
    labels = {r for side in objects.sides.values() for r in side.roles} if objects else set()
    for app in ports:
        if any(app in ROLE_SERVICES.get(label, ()) for label in labels):
            assert objects is not None
            found.setdefault(app, set()).update({("the address objects", objects.id), port})
    return found


def _sources(apps: list[str], named: dict[str, set[tuple[str, str]]]) -> str:
    """`crm: the address objects and the policy name; ...`"""
    return "; ".join(f"{a}: {' and '.join(sorted({w for w, _ in named[a]}))}" for a in apps)


# Words of object names that say where a host sits (decision 0043), for a flow
# described without an application: "SNMP traps from the management range".
PLACES = {
    "mgmt": "management",
    "management": "management",
    "oob": "management",
    "dmz": "DMZ",
    "user": "user",
    "users": "user",
    "pc": "user",
    "client": "user",
    "clients": "user",
    "workstation": "user",
    "workstations": "user",
    "desktop": "user",
    "desktops": "user",
    "laptop": "user",
    "laptops": "user",
    "staff": "user",
    "guest": "guest",
    "guests": "guest",
    "wifi": "guest",
    "vpn": "VPN",
    "partner": "partner",
    "partners": "partner",
    "vendor": "vendor",
    "vendors": "vendor",
}


def _side(names: list[str], roles: list[str], zone: str) -> str:
    """One side of a flow in words: its server roles, else where its hosts sit, else
    its zone."""
    if roles:
        return f"{' and '.join(roles)} servers"
    if names and all(n == "any" for n in names):
        return f"anywhere in zone {zone}"
    places = list(
        dict.fromkeys(
            PLACES[w] for n in names for w in re.split(r"[-_.]", n.lower()) if w in PLACES
        )
    )
    if places:
        return f"the {' and '.join(places[:2])} range"
    return f"zone {zone}"


def flow(finding: Finding) -> str | None:
    """The flow in words when nothing names an application (decisions 0042 and 0043):
    the services matched, the server roles, where the hosts sit or the zones.
    "SMB file sharing between SQL servers", "SNMP traps from the management range to
    zone dc". None when neither a service nor a role is known."""
    objects = next((e for e in finding.evidence if e.kind == "address_objects"), None)
    source = objects.sides.get("source") if objects else None
    target = objects.sides.get("destination") if objects else None
    src = source.roles if source else []
    dst = target.roles if target else []
    services = [s for e in finding.evidence if e.kind == "services" for s in e.services]
    if not src and not dst and not services:
        return None
    what = " and ".join(services[:2]) if services else "traffic"
    if src and src == dst:
        return f"{what} between {' and '.join(src)} servers"
    policy = finding.policy
    origin = _side(policy.sources, src, policy.from_zone)
    goal = _side(policy.destinations, dst, policy.to_zone)
    return f"{what} from {origin} to {goal}"


def _block_side(names: list[str], zones: str, dataset: Dataset) -> str:
    """One side of a blocked flow: "the 192.168.1.0/24 network", "host 10.0.0.5", object
    names, or anywhere in its zones."""
    names = [n for n in names if n not in ("any", "any-ipv4", "any-ipv6")]
    if not names:
        return f"anywhere in {zones}"
    if len(names) == 1:
        obj = dataset.config.addresses.get(names[0])
        if obj is not None and obj.kind == "address" and obj.value:
            value = obj.value
            if value.endswith(("/32", "/128")) or "/" not in value:
                return f"host {value.split('/')[0]} ({names[0]})"
            if re.match(r"^[\d.:a-fA-F]+/\d+$", value):
                return f"the {value} network ({names[0]})"
    more = f" and {len(names) - 3} more" if len(names) > 3 else ""
    return f"{', '.join(names[:3])}{more} in {zones}"


def blocked(finding: Finding, dataset: Dataset) -> str:
    """What a deny or reject rule blocks, in words (session 29): "FTP from anywhere in zone
    untrust to the 192.168.1.0/24 network (addr-192-168-1-0-24)"."""
    policy = finding.policy
    services = [s for e in finding.evidence if e.kind == "services" for s in e.services]
    if policy.applications == ["any"] or not services:
        what = "all traffic"
    else:
        what = " and ".join(services[:2]) + (" and more" if len(services) > 2 else "")
    origin = _block_side(policy.sources, policy.zones_text("from"), dataset)
    goal = _block_side(policy.destinations, policy.zones_text("to"), dataset)
    return f"{what} from {origin} to {goal}"


def _capped(
    finding: Finding, found: tuple[str, str, str, list[str], list[str], list[Conflict]]
) -> tuple[str, str, str, list[str], list[str], list[Conflict]]:
    """Shared addresses: a conflict, and HIGH becomes MEDIUM (C-SHARED-ADDRESS); the
    applications of the other objects are never added to the intent.
    C-AMBIGUOUS-INSTANCE: the application named first is the bare name of regional
    instances (palimp.apps). Its candidates follow it, and confidence is at most MEDIUM."""
    level, rule, reason, cited, apps, conflicts = found
    objects = next((e for e in finding.evidence if e.kind == "address_objects"), None)
    for shared in [e for e in finding.evidence if e.kind in ("shared_address", "shared_source")]:
        ids = [shared.id] + ([objects.id] if objects else [])
        # A conflict never defines the application (session 28): the other objects
        # sharing the address are cited, not added to the intent.
        conflicts = [*conflicts, Conflict(evidence=ids, text=f"{shared.id}: {shared.claim}")]
        cited = sorted(set(cited) | set(ids), key=_order)
        if level == "HIGH":
            level, rule = "MEDIUM", "C-SHARED-ADDRESS"
            reason += "; but an address of the policy is also an object of another application"
    for item in [e for e in finding.evidence if e.kind == "name_service_mismatch"]:
        conflicts = [*conflicts, Conflict(evidence=[item.id], text=f"{item.id}: {item.claim}")]
        cited = sorted(set(cited) | {item.id}, key=_order)
        if level == "HIGH":
            level, rule = "MEDIUM", "C-NAME-SERVICE"
            reason += "; but the policy name names a service the rule does not match"
    found = level, rule, reason, cited, apps, conflicts
    ambiguous = next(
        (e for e in finding.evidence if e.kind == "ambiguous_app" and e.apps[0] in apps[:1]),
        None,
    )
    if ambiguous is None:
        return found
    apps = list(dict.fromkeys(apps + ambiguous.apps[1:]))
    cited = sorted(set(cited) | {ambiguous.id}, key=_order)
    if level == "HIGH":
        level, rule = "MEDIUM", "C-AMBIGUOUS-INSTANCE"
        reason += f"; but {ambiguous.apps[0]} may stand for several regional instances"
    return level, rule, reason, cited, apps, conflicts


def _order(evidence_id: str) -> int:
    return int(evidence_id.removeprefix("E"))


# Decision 0026: a deactivated rule not kept is asked of the firewall team, whatever
# its verdict rule. One question for `explain`, the report and the questionnaires.
CLEANUP_QUESTION = "Is this deactivated rule kept on purpose, as a rollback switch?"
CLEANUP_ASK = (
    "firewall team: the rule is deactivated, so the application owner's answer would not "
    "change the action (decision 0026)"
)

QUESTIONS = {
    "V-PROBE-ONLY": "Only scanner or monitoring probes were seen on this policy. Does any "
    "business flow still need it?",
    "V-SHARED-ADDRESS": "A destination address of this policy is also an object of another "
    "application. Does that application now use this policy? Ask its owner which flows still "
    "need it before changing anything.",
    "V-CONTRADICTION": "The artifacts say this policy is unused, yet traffic matches it. "
    "Which systems still use it, and is that traffic expected?",
    "V-NOTLIVE": "Can this policy be removed? Confirm nothing still depends on it.",
    "V-TEMPORARY-IN-USE": "This policy was labeled temporary and still carries traffic. "
    "Is it still needed, and should it be replaced by a narrower permanent rule?",
    "V-TAKEOVER-IN-USE": "This policy permits any application and now carries the traffic of "
    "policies that were removed or deactivated. Which flows does it serve, and should they get "
    "narrower rules?",
    "V-NAME-SERVICE": "The name of this policy names a service it does not match. Is the "
    "name stale, or does the policy match the wrong application?",
    "V-TRAFFIC-STOPPED": "Traffic on this policy stopped some weeks ago. Has the flow ended "
    "(migration, retirement), or is it paused?",
    "V-TRAFFIC-NOT-RECENT": "Traffic matched this policy in the past but none was logged "
    "recently. Has the flow stopped, or does it run rarely (monthly, quarterly, yearly)?",
    "V-NO-TRAFFIC-SEEN": "No traffic was seen on this policy. Is it a rare or seasonal flow "
    "(backup, year-end job, disaster recovery), or is it no longer needed?",
    "V-NO-VISIBILITY": "Nothing shows whether this policy is used (no logging, no counters). "
    "Is the flow still needed?",
    "V-DENY-NOTLIVE": "This rule blocks traffic, and a record says what it protects is gone. "
    "Is this block still wanted?",
    "V-FACTORY-DEFAULT": "Was this factory default kept on purpose?",
    "V-BROAD-PERMIT": "This rule permits any source to any destination for any application. "
    "Is it wanted as it is, or should it be narrowed?",
}
# Deny and reject rules (session 29): the question is about the block itself.
DENY_QUESTION = "Is this block still wanted?"
TEAM_ASK = {
    "V-FACTORY-DEFAULT": "firewall team: a Junos factory default policy, a question about the "
    "setup of the firewall itself",
    "V-BROAD-PERMIT": "firewall team: a broad permit (any source, any destination, any "
    "application), a question about the rule itself",
}


def ticket_lookup(finding: Finding) -> str:
    """The "Look up CHG0142136 in your change system" prefix for ticket references not found in
    tickets.csv, the policy name included (session 29). Empty when there are none."""
    refs = [
        e.locator.split()[2]
        for e in finding.evidence
        if e.kind == "ticket_reference" and e.locator.startswith("ticket reference ")
    ]
    if not refs:
        return ""
    listed = ", ".join(dict.fromkeys(refs))
    return f"Look up {listed} in your change system: it may say why this rule exists. "


def assess(finding: Finding, dataset: Dataset) -> Assessment:
    verdict, v_rule, v_reason, v_evidence = _verdict(finding)
    level, c_rule, c_reason, c_evidence, apps, conflicts = _capped(finding, _confidence(finding))
    question = QUESTIONS[v_rule] if verdict != "keep" else None
    # A flow between two applications may belong to either side: every application
    # the objects name is an owner candidate, not only the one the intent names.
    objects = [a for e in finding.evidence if e.kind == "address_objects" for a in e.apps]
    # Only applications two sources confirm are named as owners (session 29).
    confirmed = apps if level != "LOW" else []
    owner = find_owner(
        finding, dataset, list(dict.fromkeys(apps + objects)), bool(conflicts), confirmed
    )
    ask = owner.text
    if v_rule in TEAM_ASK:
        ask = TEAM_ASK[v_rule]
    elif is_deny(finding.policy) and verdict == "verify":
        question = DENY_QUESTION
    if finding.policy.deactivated and verdict != "keep":
        question, ask = CLEANUP_QUESTION, CLEANUP_ASK
    if question:
        question = ticket_lookup(finding) + question
    return Assessment(
        verdict=verdict,
        verdict_rule=v_rule,
        verdict_reason=v_reason,
        verdict_evidence=v_evidence,
        confidence=level,
        confidence_rule=c_rule,
        confidence_reason=c_reason,
        confidence_evidence=c_evidence,
        intent_apps=apps,
        intent_flow=blocked(finding, dataset)
        if is_deny(finding.policy)
        else None
        if apps
        else flow(finding),
        conflicts=conflicts,
        question=question,
        ask=ask,
        owner=owner.owner,
        owner_candidates=owner.candidates,
    )
