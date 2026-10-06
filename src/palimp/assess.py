"""Deterministic verdict and confidence for one finding (decision 0020).

Every output names the rule that produced it and cites evidence IDs.

Verdict rules, first match wins:
- V-CONTRADICTION (verify): a positive not-live signal, but traffic is seen.
- V-NOTLIVE (removal_candidate): a positive not-live signal, no traffic seen.
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
- C-T3 (MEDIUM): the address objects name an application.
- C-WEAK (LOW): nothing names an application (T1 without one, T4 only).
T4 alone can never exceed LOW.
"""

from palimp.models import Assessment, Conflict, Dataset, Evidence, Finding
from palimp.owners import find_owner

# Evidence kinds that say a policy is unused (decision 0020), not that nothing is known.
NOT_LIVE_KINDS = frozenset({"deactivated", "decommission", "migration_leftover"})
LEVELS = ("LOW", "MEDIUM", "HIGH")
# T1 kinds that state why a policy exists (a decommission states why it ended).
INTENT_KINDS = frozenset({"description", "annotation", "commit_comment", "ticket"})


def _ids(items: list[Evidence]) -> list[str]:
    return [e.id for e in items]


def _verdict(finding: Finding) -> tuple[str, str, str, list[str]]:
    evidence = finding.evidence
    not_live = [e for e in evidence if e.kind in NOT_LIVE_KINDS]
    present = [e for e in evidence if e.tier == "T2" and e.signal == "present"]
    absent = [e for e in evidence if e.tier == "T2" and e.signal == "absent"]
    temporary = [e for e in evidence if e.kind == "temporary_marker"]
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
    conflicts = []
    if objects:
        for item in direct:
            if not object_apps & set(item.apps):
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
        in_use = any(e.tier == "T2" and e.signal == "present" for e in evidence)
        base = "HIGH" if agree and in_use else "MEDIUM"
        level = LEVELS[LEVELS.index(base) - 1]
        cited = sorted({i for c in conflicts for i in c.evidence} | set(_ids(agree)), key=_order)
        reason = "tiers contradict each other on the application, confidence lowered"
        return level, "C-T1-T3-CONFLICT", reason, cited, apps, conflicts
    present = [e for e in evidence if e.tier == "T2" and e.signal == "present"]
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
    if objects:
        reason = "only the address object names point to an application"
        return "MEDIUM", "C-T3", reason, [objects.id], apps, []
    weak = [e for e in evidence if e.tier in ("T1", "T3", "T4") and e.kind != "deactivated"]
    reason = "nothing names an application; ports and labels alone"
    return "LOW", "C-WEAK", reason, _ids(weak), [], []


def _order(evidence_id: str) -> int:
    return int(evidence_id.removeprefix("E"))


QUESTIONS = {
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
    level, c_rule, c_reason, c_evidence, apps, conflicts = _confidence(finding)
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
        conflicts=conflicts,
        question=question,
        ask=owner.text,
        owner=owner.owner,
        owner_candidates=owner.candidates,
    )
