"""Deterministic verdict and confidence for one finding (decision 0020).

Every output names the rule that produced it and cites evidence IDs.

Verdict rules, first match wins:
- V-CONTRADICTION (verify): a positive not-live signal, but traffic is seen.
- V-NOTLIVE (removal_candidate): a positive not-live signal, no traffic seen.
- V-TEMPORARY-IN-USE (verify): traffic seen on a policy marked temporary.
- V-TRAFFIC-NOT-RECENT (verify): hits on the counters, but a logging policy
  logged no session in the log window.
- V-TRAFFIC (keep): traffic seen.
- V-NO-TRAFFIC-SEEN (verify): artifacts could show traffic and show none.
  Absence is never evidence of absence: this never gives removal_candidate.
- V-NO-VISIBILITY (verify): no artifact can show traffic for this policy.

Confidence rules (about the intent), first match wins:
- C-T1-T3-CONFLICT: a T1 item names applications that the address objects do
  not name. One level below what the agreeing evidence alone would give.
- C-T1-T3-AGREE (HIGH): T1 names an application the address objects name.
- C-T1-ONLY (MEDIUM): T1 names an application, the objects name none.
- C-T3 (MEDIUM): the address objects name an application.
- C-WEAK (LOW): nothing names an application (T1 without one, T4 only).
T4 alone can never exceed LOW.
"""

from palimp.models import Assessment, Conflict, Dataset, Evidence, Finding

# Evidence kinds that say a policy is unused (decision 0020), not that nothing is known.
NOT_LIVE_KINDS = frozenset({"deactivated", "decommission", "cleanup_leftover"})
LEVELS = ("LOW", "MEDIUM", "HIGH")


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
    if present and temporary:
        return (
            "verify",
            "V-TEMPORARY-IN-USE",
            "a policy marked temporary carries traffic: it may now be load-bearing",
            _ids(temporary + present),
        )
    hits = [e for e in present if e.kind == "hit_count"]
    quiet_log = [e for e in absent if e.kind == "session_log"]
    if hits and quiet_log and not [e for e in present if e.kind == "session_log"]:
        return (
            "verify",
            "V-TRAFFIC-NOT-RECENT",
            "hits on the counters, but no session logged in the log window: "
            "the traffic may have stopped",
            _ids(hits + quiet_log),
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
    direct = [e for e in evidence if e.tier == "T1" and e.apps]
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
        base = "HIGH" if agree else "MEDIUM"
        level = LEVELS[LEVELS.index(base) - 1]
        cited = sorted({i for c in conflicts for i in c.evidence} | set(_ids(agree)), key=_order)
        reason = "tiers contradict each other on the application, confidence lowered"
        return level, "C-T1-T3-CONFLICT", reason, cited, apps, conflicts
    if agree:
        reason = "direct evidence names the same application as the address objects"
        return "HIGH", "C-T1-T3-AGREE", reason, _ids(agree) + [objects.id], apps, []
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


def _who(finding: Finding, dataset: Dataset, apps: list[str]) -> str:
    tickets = [e for e in finding.evidence if e.kind == "ticket"]
    for item in tickets:
        ticket_id = item.locator.split()[1]
        ticket = dataset.tickets.get(ticket_id)
        if ticket and ticket.requester:
            return f"{ticket.requester}, requester of {ticket_id} [{item.id}]"
    for app in apps:
        related = [
            t
            for t in dataset.tickets.values()
            if t.related_ci and t.related_ci.lower().removeprefix("shared-") == app and t.requester
        ]
        if related:
            latest = max(related, key=lambda t: t.opened or "")
            return (
                f"the owner of application {app}; latest requester for it in tickets.csv: "
                f"{latest.requester} ({latest.ticket_id})"
            )
    if apps:
        return f"the owner of application {', '.join(apps)} (no name in the artifacts)"
    commit = next((c for c in dataset.commits if c.index == finding.created_in_commit), None)
    if commit:
        return f"{commit.user}, who created the policy in commit {commit.index}"
    targets = ", ".join(finding.policy.destinations) or "the destination"
    return f"the team that runs {targets}"


QUESTIONS = {
    "V-CONTRADICTION": "The artifacts say this policy is unused, yet traffic matches it. "
    "Which systems still use it, and is that traffic expected?",
    "V-NOTLIVE": "Can this policy be removed? Confirm nothing still depends on it.",
    "V-TEMPORARY-IN-USE": "This policy was labeled temporary and still carries traffic. "
    "Is it still needed, and should it be replaced by a narrower permanent rule?",
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
    question = ask = None
    if verdict != "keep":
        question = QUESTIONS[v_rule]
        ask = _who(finding, dataset, apps)
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
        ask=ask,
    )
