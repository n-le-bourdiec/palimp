"""Ground truth (spec section 6), validated against schema/ground_truth.schema.json."""

import json
from functools import cache
from importlib.resources import files

from jsonschema import Draft202012Validator

from palimp_sim import __version__, voice
from palimp_sim.artifacts import RETAINED, commit_index
from palimp_sim.junos import ANY
from palimp_sim.traffic import TrafficResult

GENERIC_ADDRESSES = {ANY, "users-all", "servers-net"}
MIN_WINDOW_FOR_REMOVAL = 90  # days of hit counts needed to call a zero-hit rule removable


@cache
def schema() -> dict:
    text = files("palimp_sim").joinpath("schema/ground_truth.schema.json").read_text("utf-8")
    return json.loads(text)


def validate(document: dict) -> None:
    Draft202012Validator(schema()).validate(document)


def _iso(sim, day: int | None) -> str | None:
    return None if day is None else sim.date(day).isoformat()


def _confidence(evidence: list[dict]) -> str:
    tiers = {e["tier"] for e in evidence if not e["misleading"]}
    if "T1" in tiers and "T2" in tiers:
        return "HIGH"
    if "T1" in tiers or "T3" in tiers:
        return "MEDIUM"
    return "LOW"


def _mentions(text: str | None, app_id: str) -> bool:
    """Whether a visible name or text still names an application (TRAP-STALE-NAME)."""
    if not text:
        return False
    lowered = text.lower()
    return app_id in lowered or voice.code(app_id).lower() in lowered


def _rule(
    sim, policy, traffic: TrafficResult, live: dict, log_lines: dict, log_names=frozenset()
) -> dict:
    meta = sim.policy_meta[policy.uid]
    commit = sim.commits[meta.commit_seq]
    index = commit_index(sim, commit.seq)
    retained = index < RETAINED
    flows = [sim.flows[f] for f in meta.flow_ids]
    app = sim.apps[meta.app_id]
    stats = traffic.policies.get(policy.uid)
    hits = stats.hits_since_reset if stats else 0
    lines = log_lines.get(policy.uid, 0)
    is_live = policy.uid in live
    logged = policy.log_init or policy.log_close
    ticket = next((t for t in sim.tickets if t.ticket_id == meta.ticket_id), None)
    facts = sim.traps
    traps: list[str] = []

    # Trap conditions, checked on the final state (medium.py builds them).
    emergency = policy.uid in facts.emergency
    load_bearing = (
        emergency
        and is_live
        and all(uid in facts.removed_by for uid in facts.emergency[policy.uid])
    )
    other_app = facts.misleading_comments.get(commit.seq)
    copied = other_app is not None and retained and other_app != meta.app_id
    batch = commit.seq in facts.batch_commits and retained
    batch_named = facts.batch_commits.get(commit.seq)
    hidden_live = is_live and hits == 0 and lines == 0 and not policy.inactive

    # Hard traps (hard.py). Every value below is empty or False in Medium.
    hierarchical = sim.level.config_format == "hierarchical"
    renames = facts.renames.get(policy.uid, [])
    reuse = facts.ip_reuse.get(policy.uid)
    stale = facts.stale.get(policy.uid)
    noise = stats.noise_since_reset if stats else 0
    if reuse:
        # The rule carries the new server's traffic, not a flow it was made for.
        is_live = any(f in meta.flow_ids for f in live.get(policy.uid, []))
    reused = bool(reuse) and not is_live and (hits > 0 or lines > 0)
    scanned = not is_live and not policy.inactive and hits > 0 and hits == noise
    old_app = stale["old"] if stale else None
    stale_texts = [policy.name, policy.description, policy.annotation]
    stale_texts += policy.sources + policy.destinations
    stale_named = bool(stale) and is_live and any(_mentions(t, old_app) for t in stale_texts)
    last_index = min(RETAINED, len(sim.commits)) - 1  # oldest rollback file
    shown_renames = [
        (commit_index(sim, seq), old)
        for seq, old in renames
        if commit_index(sim, seq) + 1 <= last_index or old in log_names
    ]
    object_renames = [
        (commit_index(sim, seq), old, new)
        for seq, old, new in facts.object_renames
        if new in policy.sources + policy.destinations and commit_index(sim, seq) + 1 <= last_index
    ]

    evidence: list[dict] = []

    def add(tier: str, artifact: str, locator: str, supports: str, misleading=False) -> None:
        evidence.append(
            {
                "id": f"G{len(evidence) + 1}",
                "tier": tier,
                "artifact": artifact,
                "locator": locator,
                "supports": supports,
                "misleading": misleading,
            }
        )

    if policy.description:
        wrong = stale_named and _mentions(policy.description, old_app)
        add("T1", "config.set", f"policy {policy.name} description", "intent", wrong)
    if hierarchical and policy.annotation:
        # `annotate` text shows in hierarchical output only (HIER-1c).
        wrong = stale_named and _mentions(policy.annotation, old_app)
        add("T1", "config.set", f"policy {policy.name} annotation", "intent", wrong)
    if retained and commit.comment:
        # A copied comment, or a batch comment naming another application,
        # describes another change (TRAP-MISLEADING-COMMENT, TRAP-BATCH-COMMIT).
        # The go-live comment of a replaced application names the old one.
        wrong = copied or (batch and batch_named != meta.app_id) or stale_named
        add("T1", "commits.txt", f"commit {index} comment", "intent", wrong)
    if ticket and ticket.exported:
        texts = [policy.description or "", commit.comment if retained else ""]
        if any(ticket.ticket_id in text for text in texts):
            add("T1", "tickets.csv", f"ticket {ticket.ticket_id}", "intent")
    if copied:
        for other in sim.tickets:
            shown = other.exported and other.ticket_id in commit.comment
            if shown and other.related_ci == other_app:
                add("T1", "tickets.csv", f"ticket {other.ticket_id}", "intent", True)
    if policy.inactive:
        # Not installed, so not in hitcount.txt and never in the logs.
        if hierarchical:
            where = f"inactive: policy {policy.name}"
        elif policy.is_global:
            where = f"deactivate security policies global policy {policy.name}"
        else:
            where = (
                f"deactivate security policies from-zone {policy.from_zone} "
                f"to-zone {policy.to_zone} policy {policy.name}"
            )
        add("T3", "config.set", where, "not_live")
        add("T3", "config.set", f"policy {policy.name} then permit", "live", True)
    else:
        # Hits of a reused address or of a scanner are not business use.
        wrong = hidden_live or reused or scanned
        support = "live" if hits else "not_live"
        add("T2", "hitcount.txt", f"policy {policy.name}", support, wrong)
        if logged:
            support = "live" if lines else "not_live"
            add("T2", "logs/rt_flow.log", f'policy-name="{policy.name}"', support, wrong)
    named = [
        n
        for n in policy.sources + policy.destinations
        if n not in GENERIC_ADDRESSES and not (sim.level.traps and n.startswith("users-"))
    ]
    if named:
        wrong = stale_named and any(_mentions(n, old_app) for n in named)
        add("T3", "config.set", "address objects " + ", ".join(named), "intent", wrong)
    if stale_named and _mentions(policy.name, old_app):
        add("T3", "config.set", f"policy {policy.name} name", "intent", True)
    if reused:
        # The address of the retired server is also the new server's object.
        config = sim.config
        own = {m for n in policy.destinations for m in config.address_sets.get(n, [n])}
        prefixes = {str(n) for n in config.resolve_address_list(policy.destinations)}
        twins = [
            name
            for name, prefix in config.addresses.items()
            if name not in own and prefix in prefixes
        ]
        if twins:
            add("T3", "config.set", "same address as " + ", ".join(twins), "intent")
    if stale:
        repoint = commit_index(sim, stale["seq"])
        if repoint + 1 <= last_index:
            add("T3", "rollbacks", f"address values changed in commit {repoint}", "intent")
        if repoint < RETAINED and sim.commits[stale["seq"]].comment:
            add("T1", "commits.txt", f"commit {repoint} comment", "intent")
    for where, old in shown_renames:
        if where + 1 <= last_index:
            text = f"policy {old} in rollback {where + 1}, {policy.name} from commit {where}"
            add("T3", "rollbacks", text, "intent")
            if sim.commits[len(sim.commits) - 1 - where].comment:
                # The rename commit looks like the creation of a new rule.
                add("T1", "commits.txt", f"commit {where} comment", "intent", True)
        if old in log_names:
            add("T2", "logs/rt_flow.log", f'policy-name="{old}"', "live")
    for where, old, new in object_renames:
        text = f"address {old} in rollback {where + 1}, {new} from commit {where}"
        add("T3", "rollbacks", text, "intent")
    if retained and len(commit.created) > 1:
        # In a batch commit the rules belong to unrelated applications.
        add("T3", "rollbacks", f"rules created together in commit {index}", "intent", batch)
    if emergency:
        # Name, comment and description say temporary; the rule is now needed.
        add("T3", "config.set", f"policy {policy.name} marked temporary", "not_live", True)
        for uid in facts.emergency[policy.uid]:
            seq = facts.removed_by.get(uid)
            if seq is not None and commit_index(sim, seq) < RETAINED:
                where = f"rule {_name_of(sim, uid)} removed in commit {commit_index(sim, seq)}"
                add("T3", "rollbacks", where, "live")
    add("T4", "config.set", "applications " + ", ".join(policy.applications), "intent")

    if sim.level.traps:
        has_t1 = any(e["tier"] == "T1" for e in evidence)
        if hidden_live and not logged and policy.uid in facts.nolog_jobs:
            traps.append("TRAP-LIVE-NOLOG")
        if hidden_live and policy.uid in facts.rare_jobs:
            traps.append("TRAP-RARE-JOB")
        if load_bearing:
            traps.append("TRAP-EMERGENCY-LOADBEARING")
        if copied:
            traps.append("TRAP-MISLEADING-COMMENT")
        if batch:
            traps.append("TRAP-BATCH-COMMIT")
        if not retained and not has_t1:
            traps.append("TRAP-HISTORY-HORIZON")
        if policy.inactive:
            traps.append("TRAP-DEACTIVATED")
        if shown_renames or object_renames:
            traps.append("TRAP-RENAME-CHAIN")
        if reused:
            traps.append("TRAP-IP-REUSE")
        if scanned:
            traps.append("TRAP-SCANNER-HITS")
        if stale_named:
            traps.append("TRAP-STALE-NAME")

    pair_reset = sim.pair_resets.get((policy.from_zone, policy.to_zone), 0)
    window = sim.total_days - max(sim.hit_reset_day or 0, pair_reset)
    if policy.inactive:
        # Deactivated by a cleanup because it carried nothing: removable.
        verdict = best = "removal_candidate"
    elif load_bearing or reused:
        # Needed: verify with the owner and replace it with a proper rule.
        # A reused address: the intent is dead, but another application's
        # traffic now goes through the rule.
        verdict = best = "verify"
    elif is_live:
        verdict = "keep"
        best = "verify" if hidden_live else "keep"
    else:
        verdict = "removal_candidate"
        removable = hits == 0 and window >= MIN_WINDOW_FOR_REMOVAL
        best = "removal_candidate" if removable else "verify"
    return {
        "rule_uid": policy.uid,
        "key": {"from_zone": policy.from_zone, "to_zone": policy.to_zone, "name": policy.name},
        "name_history": [old for _, old in renames] + [policy.name],
        "deactivated": policy.inactive,
        "created": {
            "event_id": meta.event_id,
            "date": _iso(sim, commit.day),
            "admin_id": meta.admin_id,
            "persona": next(a.persona for a in sim.admins if a.admin_id == meta.admin_id),
            "commit_index": index,
            "in_retained_history": retained,
        },
        "intent": {
            "kind": meta.intent_kind or flows[0].template.kind,
            "app_id": app.app_id,
            "flows": meta.flow_ids,
            "summary": meta.summary or flows[0].template.summary,
        },
        "status": {
            "live": is_live,
            "still_needed": is_live or reused,
            "carried_flows": live.get(policy.uid, []),
            "last_real_use": _iso(sim, stats.last_hit if stats else None),
            "hits_in_window": hits,
            "hits_total": stats.hits_total if stats else 0,
            "log_lines": lines,
            "hits_reason": _hits_reason(
                hits, reused, scanned, facts.scanner_targets.get(policy.uid)
            ),
        },
        "expected": {
            "verdict": verdict,
            "best_achievable_verdict": best,
            "max_justified_confidence": _confidence(evidence),
            "owner_to_ask": sim.apps[reuse["app"]].owner_id if reused else app.owner_id,
        },
        "evidence": evidence,
        "traps": traps,
    }


def _hits_reason(hits: int, reused: bool, scanned: bool, noise_kind: str | None) -> str:
    if not hits:
        return "none"
    if reused:
        return "ip_reuse"
    if scanned:
        # A forgotten monitoring probe, or the scanner sweep.
        return "monitoring" if noise_kind == "monitoring" else "scanner"
    return "business"


def _name_of(sim, uid: str) -> str:
    """Last name a policy had in the history (it may be gone from the final config)."""
    for commit in reversed(sim.commits):
        for policy in commit.config.policies:
            if policy.uid == uid:
                return policy.name
    raise KeyError(uid)


def ground_truth(
    sim, traffic: TrafficResult, live: dict, log_lines: dict, scenario_id: str | None = None
) -> dict:
    """`scenario_id` defaults to level and seed; held-out scenarios pass their index instead."""
    config = sim.config
    snapshot = sim.date(sim.total_days)
    log_names = frozenset(s.policy_name for s in traffic.sessions)
    document = {
        "schema_version": 1,
        "simulator_version": __version__,
        "scenario_id": scenario_id or f"{sim.level.name}-{sim.seed:06d}",
        "level": sim.level.name,
        "snapshot": f"{snapshot.isoformat()}T09:00:00Z",
        "hit_count_reset": _iso(sim, sim.hit_reset_day),
        "log_window_start": _iso(sim, sim.total_days - sim.level.log_window_days),
        "rules": [
            _rule(sim, p, traffic, live, log_lines, log_names) for p in config.ordered_policies()
        ],
        "objects": [
            {"name": name, "kind": "address", "value": prefix}
            for name, prefix in config.addresses.items()
        ]
        + [
            {"name": name, "kind": "address_set", "value": " ".join(members)}
            for name, members in config.address_sets.items()
        ],
        "apps": [
            {
                "app_id": app.app_id,
                "name": app.name,
                "owner_id": app.owner_id,
                "shared": app.shared,
                "go_live": _iso(sim, app.go_live),
                "retired": _iso(sim, app.retired),
            }
            for app in sim.apps.values()
        ],
        "flows": [
            {
                "flow_id": flow.flow_id,
                "app_id": flow.app_id,
                "kind": flow.template.kind,
                "summary": flow.template.summary,
                "source": flow.src.address,
                "destination": flow.dst.address,
                "services": list(flow.template.services),
                "schedule": flow.template.schedule,
                "start": _iso(sim, flow.start),
                "end": _iso(sim, flow.end),
            }
            for flow in sim.flows.values()
        ],
        "people": [{"person_id": p.person_id, "name": p.name, "team": p.team} for p in sim.people],
        "admins": [
            {
                "admin_id": a.admin_id,
                "login": a.login,
                "name": a.name,
                "persona": a.persona,
                "joined": sim.date(a.joined).isoformat(),
                "left": _iso(sim, a.left),
            }
            for a in sim.admins
        ],
        "events": [
            {
                "event_id": e.event_id,
                "kind": e.kind,
                "date": _iso(sim, e.day),
                "admin_id": e.admin_id,
                "app_id": e.app_id,
                "ticket_id": e.ticket_id,
                "commit_indexes": [commit_index(sim, seq) for seq in e.commits],
                "note": e.note,
            }
            for e in sim.events
        ],
    }
    validate(document)
    return document
