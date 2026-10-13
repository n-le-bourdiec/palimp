"""Deterministic verdict and confidence for one finding (decision 0020).

Every output names the rule that produced it and cites evidence IDs.

Verdict rules, first match wins:
- V-SHARED-ADDRESS (verify): a destination address is also an object named after
  another application, and traffic is seen or a not-live signal exists: the
  address may have been reused (or the application renamed). Never keep, never
  removal_candidate (session 24).
- V-CONTRADICTION (verify): a positive not-live signal, but traffic is seen.
  When the only logged traffic is probe traffic (scanner or monitoring, see
  palimp.formats.rt_flow), hits on the counters do not count as traffic seen.
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
- V-TRAFFIC (keep): traffic seen.
- V-NO-TRAFFIC-SEEN (verify): artifacts could show traffic and show none.
  Absence is never evidence of absence: this never gives removal_candidate.
- V-NO-VISIBILITY (verify): no artifact can show traffic for this policy.

Confidence rules (about the intent), first match wins:
- C-T1-T3-CONFLICT: a T1 item names applications that the address objects do
  not name. One level below what the agreeing evidence alone would give.
- C-T1-T3-AGREE (HIGH): T1 names an application the address objects name,
  and traffic is seen (T2 present).
- C-T1-T3-AGREE-NO-TRAFFIC (MEDIUM): the same without traffic seen: the
  documented intent may be stale (deactivated, rare or unlogged policy).
- C-T1-ONLY (MEDIUM): T1 names an application, the objects name none.
- C-T3 (MEDIUM): two independent names point to the same application
  (decision 0042): the address objects on both sides of the rule, or an
  address object and the policy name, a custom application name or a
  dynamic application.
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

from palimp.models import Assessment, Conflict, Dataset, Evidence, Finding
from palimp.owners import find_owner

# Evidence kinds that say a policy is unused (decision 0020), not that nothing is known.
NOT_LIVE_KINDS = frozenset({"deactivated", "decommission", "migration_leftover"})
LEVELS = ("LOW", "MEDIUM", "HIGH")
# T1 kinds that state why a policy exists (a decommission states why it ended).
INTENT_KINDS = frozenset({"description", "annotation", "commit_comment", "ticket"})
# T3 and T4 items whose names may point to an application, each one independent source
# (decision 0042). Address objects count once per side of the rule.
NAMING = {
    "policy_name": "the policy name",
    "services": "a custom application name",
    "dynamic_application": "a dynamic application",
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
        if sure:
            apps = sure + [a for a in apps if a not in sure]
            said = " and ".join(sorted({w for a in sure for w, _ in named[a]}))
            reason = f"two independent names point to the application: {said}"
            cited = sorted({i for a in sure for _, i in named[a]}, key=_order)
            return "MEDIUM", "C-T3", reason, cited, apps, []
        said = " and ".join(sorted({w for a in apps for w, _ in named[a]}))
        reason = (
            f"only one name points to an application ({said}): a name alone may be a place, "
            "a person or a generic word, no second source confirms it"
        )
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
            sides = item.sides or {"": None}
            for side, names in sides.items():
                for app in names.apps if names else item.apps:
                    what = f"the {side} address objects" if side else "the address objects"
                    found.setdefault(app, set()).add((what, item.id))
        elif item.kind in NAMING:
            for app in item.apps:
                found.setdefault(app, set()).add((NAMING[item.kind], item.id))
    return found


def flow(finding: Finding) -> str | None:
    """The flow in words from server roles and services, when the object names state
    roles (decision 0042): "SMB file sharing between SQL servers"."""
    objects = next((e for e in finding.evidence if e.kind == "address_objects"), None)
    if objects is None:
        return None
    source = objects.sides.get("source")
    target = objects.sides.get("destination")
    src = source.roles if source else []
    dst = target.roles if target else []
    if not src and not dst:
        return None
    services = [s for e in finding.evidence if e.kind == "services" for s in e.services]
    what = " and ".join(services[:2]) if services else "traffic"
    if src and src == dst:
        return f"{what} between {' and '.join(src)} servers"
    if src and dst:
        return f"{what} from {' and '.join(src)} servers to {' and '.join(dst)} servers"
    if dst:
        return f"{what} to {' and '.join(dst)} servers"
    return f"{what} from {' and '.join(src)} servers"


def _capped(
    finding: Finding, found: tuple[str, str, str, list[str], list[str], list[Conflict]]
) -> tuple[str, str, str, list[str], list[str], list[Conflict]]:
    """C-AMBIGUOUS-INSTANCE: the application named first is the bare name of regional
    instances (palimp.apps). Its candidates follow it, and confidence is at most MEDIUM."""
    level, rule, reason, cited, apps, conflicts = found
    objects = next((e for e in finding.evidence if e.kind == "address_objects"), None)
    for shared in [e for e in finding.evidence if e.kind in ("shared_address", "shared_source")]:
        ids = [shared.id] + ([objects.id] if objects else [])
        conflicts = [*conflicts, Conflict(evidence=ids, text=f"{shared.id}: {shared.claim}")]
        apps = list(dict.fromkeys(apps + shared.apps))
        cited = sorted(set(cited) | set(ids), key=_order)
        if level == "HIGH":
            level, rule = "MEDIUM", "C-SHARED-ADDRESS"
            reason += "; but an address of the policy is also an object of another application"
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
    "V-TRAFFIC-STOPPED": "Traffic on this policy stopped some weeks ago. Has the flow ended "
    "(migration, retirement), or is it paused?",
    "V-TRAFFIC-NOT-RECENT": "Traffic matched this policy in the past but none was logged "
    "recently. Has the flow stopped, or does it run rarely (monthly, quarterly, yearly)?",
    "V-NO-TRAFFIC-SEEN": "No traffic was seen on this policy. Is it a rare or seasonal flow "
    "(backup, year-end job, disaster recovery), or is it no longer needed?",
    "V-NO-VISIBILITY": "Nothing shows whether this policy is used (no logging, no counters). "
    "Is the flow still needed?",
}


def assess(finding: Finding, dataset: Dataset) -> Assessment:
    verdict, v_rule, v_reason, v_evidence = _verdict(finding)
    level, c_rule, c_reason, c_evidence, apps, conflicts = _capped(finding, _confidence(finding))
    question = QUESTIONS[v_rule] if verdict != "keep" else None
    # A flow between two applications may belong to either side: every application
    # the objects name is an owner candidate, not only the one the intent names.
    objects = [a for e in finding.evidence if e.kind == "address_objects" for a in e.apps]
    owner = find_owner(finding, dataset, list(dict.fromkeys(apps + objects)), bool(conflicts))
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
        intent_flow=None if apps else flow(finding),
        conflicts=conflicts,
        question=question,
        ask=owner.text,
        owner=owner.owner,
        owner_candidates=owner.candidates,
    )
