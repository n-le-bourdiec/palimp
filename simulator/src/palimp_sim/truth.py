"""Ground truth (spec section 6), validated against schema/ground_truth.schema.json."""

import json
from functools import cache
from importlib.resources import files

from jsonschema import Draft202012Validator

from palimp_sim import __version__
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


def _rule(sim, policy, traffic: TrafficResult, live: dict, log_lines: dict) -> dict:
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
    ticket = next((t for t in sim.tickets if t.ticket_id == meta.ticket_id), None)

    evidence: list[dict] = []

    def add(tier: str, artifact: str, locator: str, supports: str) -> None:
        evidence.append(
            {
                "id": f"G{len(evidence) + 1}",
                "tier": tier,
                "artifact": artifact,
                "locator": locator,
                "supports": supports,
                "misleading": False,
            }
        )

    if policy.description:
        add("T1", "config.set", f"policy {policy.name} description", "intent")
    if retained and commit.comment:
        add("T1", "commits.txt", f"commit {index} comment", "intent")
    if ticket and ticket.exported:
        texts = [policy.description or "", commit.comment if retained else ""]
        if any(ticket.ticket_id in text for text in texts):
            add("T1", "tickets.csv", f"ticket {ticket.ticket_id}", "intent")
    add("T2", "hitcount.txt", f"policy {policy.name}", "live" if hits else "not_live")
    if policy.log_init or policy.log_close:
        add(
            "T2",
            "logs/rt_flow.log",
            f'policy-name="{policy.name}"',
            "live" if lines else "not_live",
        )
    named = [n for n in policy.sources + policy.destinations if n not in GENERIC_ADDRESSES]
    if named:
        add("T3", "config.set", "address objects " + ", ".join(named), "intent")
    if retained and len(commit.created) > 1:
        add("T3", "rollbacks", f"rules created together in commit {index}", "intent")
    add("T4", "config.set", "applications " + ", ".join(policy.applications), "intent")

    window = sim.total_days - (sim.hit_reset_day or 0)
    if is_live:
        verdict = best = "keep"
    else:
        verdict = "removal_candidate"
        removable = hits == 0 and window >= MIN_WINDOW_FOR_REMOVAL
        best = "removal_candidate" if removable else "verify"
    return {
        "rule_uid": policy.uid,
        "key": {"from_zone": policy.from_zone, "to_zone": policy.to_zone, "name": policy.name},
        "name_history": [policy.name],
        "deactivated": False,
        "created": {
            "event_id": meta.event_id,
            "date": _iso(sim, commit.day),
            "admin_id": meta.admin_id,
            "persona": next(a.persona for a in sim.admins if a.admin_id == meta.admin_id),
            "commit_index": index,
            "in_retained_history": retained,
        },
        "intent": {
            "kind": flows[0].template.kind,
            "app_id": app.app_id,
            "flows": meta.flow_ids,
            "summary": flows[0].template.summary,
        },
        "status": {
            "live": is_live,
            "still_needed": is_live,
            "carried_flows": live.get(policy.uid, []),
            "last_real_use": _iso(sim, stats.last_hit if stats else None),
            "hits_in_window": hits,
            "hits_total": stats.hits_total if stats else 0,
            "log_lines": lines,
            "hits_reason": "business" if hits else "none",
        },
        "expected": {
            "verdict": verdict,
            "best_achievable_verdict": best,
            "max_justified_confidence": _confidence(evidence),
            "owner_to_ask": app.owner_id,
        },
        "evidence": evidence,
        "traps": [],
    }


def ground_truth(sim, traffic: TrafficResult, live: dict, log_lines: dict) -> dict:
    config = sim.config
    snapshot = sim.date(sim.total_days)
    document = {
        "schema_version": 1,
        "simulator_version": __version__,
        "scenario_id": f"{sim.level.name}-{sim.seed:06d}",
        "level": sim.level.name,
        "snapshot": f"{snapshot.isoformat()}T09:00:00Z",
        "hit_count_reset": _iso(sim, sim.hit_reset_day),
        "log_window_start": _iso(sim, sim.total_days - sim.level.log_window_days),
        "rules": [_rule(sim, p, traffic, live, log_lines) for p in config.ordered_policies()],
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
