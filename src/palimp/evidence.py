"""Deterministic evidence collectors. No scoring here.

T1 direct: policy description, annotations of the policy (`/* ... */`, an
admin's note, hierarchical format only), comment of the commit that created
the policy, ticket references found in the name, description, annotations or
that comment (matched against tickets.csv when present), a decommission the
policy was left behind by (palimp.notlive).
T2 behavioral: hit count row, RT_FLOW log summary. Each T2 item says whether
the artifact shows traffic ("present"), could show it and shows none
("absent"), or cannot show it for this policy ("blind": no logging,
deactivated, artifact missing), see decision 0019.
T3 structural: address object names, applications the policy name names
(with the same name filters, palimp.apps), application services attached to the
permit (`then permit application-services`), other permit options (`tunnel`,
`firewall-authentication`, `destination-address`), policies created in the same
commit, deactivation, a name, description or annotation that marks the policy as
temporary, dynamic applications matched (`junos:SLACK` names slack),
the requesters of the tickets for each application named above (palimp.owners),
history lineage from the rollbacks (palimp.lineage): removed or deactivated
policies whose traffic this one took over, and a migration that left this
policy pointing to a silent old host.
T2 also says when logged traffic stopped well before the end of the log
window, and when counters were cleared inside it (palimp.counters).
T4 contextual: plain service names of the applications the policy matches.

Each item has a stable `kind` and the applications it names (`apps`).
"""

import re
from typing import NamedTuple

from palimp.apps import Vocabulary, roles, vocabulary
from palimp.assess import assess
from palimp.behavior import recurrence, stopped, time_of_day
from palimp.counters import Clear, clears, log_summary, meaning
from palimp.lineage import Migration, leftover_items, migrations, takeover_claim, takeovers
from palimp.models import (
    Dataset,
    Evidence,
    Finding,
    LogSummary,
    Policy,
    PolicyKey,
    Side,
    Signal,
)
from palimp.notlive import Marker, decommission_items, markers
from palimp.owners import requester_items
from palimp.services import describe, service_names

TICKET_REF = re.compile(r"\b(?:CHG|INC|RITM|REQ|CR|SR|TASK)[-_]?\d{4,}\b", re.IGNORECASE)


def shown(values: list[str], sep: str = ", ") -> str:
    """VALUES joined, at most LIST_SHOWN of them, then "and N more"."""
    more = len(values) - LIST_SHOWN
    return sep.join(values[:LIST_SHOWN]) + (f"{sep}and {more} more" if more > 0 else "")


def _resolve(dataset: Dataset, name: str) -> str:
    obj = dataset.config.addresses.get(name)
    if obj is None:
        return name
    if obj.kind == "address_set":
        return f"{name} = {{{shown(obj.members)}}}"
    return f"{name} = {obj.value}"


class Item(NamedTuple):
    tier: str
    artifact: str
    locator: str
    claim: str
    signal: Signal | None = None
    kind: str = ""
    apps: list[str] = []
    sides: dict[str, Side] = {}
    services: list[str] = []
    address: str = ""
    objects: list[str] = []


LIST_SHOWN = 5
MAX_SET_DEPTH = 8
# Words that mark a policy as temporary: a label, not a sign that it is unused.
TEMPORARY_WORDS = frozenset(
    {"temp", "tmp", "temporary", "test", "testing", "urgent", "emergency", "incident", "hotfix"}
)


def _some(values: list[str], count: int) -> str:
    shown = ", ".join(values[:LIST_SHOWN])
    return f"{count} ({shown}{', ...' if count > LIST_SHOWN else ''})" if count else "0"


def hit_count_items(dataset: Dataset, policy: Policy, clear: Clear | None = None) -> list[Item]:
    artifact = "hitcount.txt"
    if dataset.hit_count_stats is None:
        claim = "no hit counts were provided: use of this policy is unknown from counters"
        return [Item("T2", artifact, "hitcount.txt missing", claim, "blind", "hit_count")]
    row = next(
        (
            h
            for h in dataset.hit_counts
            if (h.from_zone, h.to_zone, h.name) == (policy.from_zone, policy.to_zone, policy.name)
        ),
        None,
    )
    locator = f"policy {policy.name} ({policy.from_zone} -> {policy.to_zone})"
    if row is None:
        if policy.deactivated:
            claim = "no row: deactivated policies match no traffic and are not listed"
        elif policy.is_global:
            claim = (
                "no row under zones global global for this global policy: how hit counts list "
                "global policies is not documented, its use is unknown from counters"
            )
        else:
            claim = "no row for this policy: its use is unknown from counters"
        return [Item("T2", artifact, locator, claim, "blind", "hit_count")]
    since = "since the counters were last cleared (the clear date is not in hitcount.txt)"
    pair = (policy.from_zone, policy.to_zone)
    since += meaning(clear, policy.name, row.count, pair)
    signal: Signal = "present" if row.count else "absent"
    items = [Item("T2", artifact, locator, f"{row.count} hits {since}", signal, "hit_count")]
    if clear is not None and clear.after:
        name, when = clear.latest or ("", None)
        claim = (
            f"counters from {pair[0]} to {pair[1]} were cleared inside the log window, after "
            f"{when:%Y-%m-%d %H:%M} (policy {name} logged sessions until then and shows 0)"
        )
        locator = f"hitcount.txt and logs/rt_flow.log, zone pair {pair[0]} -> {pair[1]}"
        items.append(Item("T2", artifact, locator, claim, "blind", "counter_clear"))
    return items


def _span(dataset: Dataset) -> str:
    window = dataset.log_window
    if window.start is None or window.end is None:
        return "the log window (dates unknown)"
    days = (window.end.date() - window.start.date()).days + 1
    return f"the log window {window.start:%Y-%m-%d} to {window.end:%Y-%m-%d} ({days} days)"


def log_items(dataset: Dataset, policy: Policy) -> list[Item]:
    artifact = "logs/rt_flow.log"
    if dataset.log_stats is None:
        claim = "no session log was provided: traffic of this policy is unknown from logs"
        return [Item("T2", artifact, "logs/rt_flow.log missing", claim, "blind", "session_log")]
    summary = log_summary(dataset, policy)
    locator = f'policy-name="{policy.name}"'
    if summary is not None and summary.sessions and summary.probe_sessions >= summary.sessions:
        probes = [s for s in summary.sources if s in dataset.log_window.probe_sources]
        claim = (
            f"{_describe(dataset, summary)}; all {summary.sessions} sessions come from probe "
            f"sources ({', '.join(probes[:LIST_SHOWN]) or 'not listed'}) that reach many "
            "policies and destinations, and the server never answered them: scanner or "
            "monitoring probes, no business traffic logged"
        )
        return [
            Item("T2", artifact, locator, claim, "absent", "session_log"),
            Item(
                "T2",
                artifact,
                locator,
                "the only logged traffic is probe traffic: hits on the counters may be probes "
                "too, so they do not show that the policy is in use",
                "blind",
                "probe_only",
            ),
        ]
    if summary is not None and (summary.sessions or summary.deny):
        claim = _describe(dataset, summary)
        if summary.probe_sessions:
            claim += (
                f"; {summary.probe_sessions} of the sessions are unanswered probes from "
                "sources that reach many policies (scanner or monitoring), not business traffic"
            )
        items = [Item("T2", artifact, locator, claim, "present", "session_log")]
        end = dataset.log_window.end
        if end and (silence := stopped(summary.days, end.date())):
            claim = (
                f"logged sessions on {len(summary.days)} days up to {summary.days[-1]:%Y-%m-%d}, "
                f"then none in the last {silence} days of the log window although the policy "
                "still logs: the traffic seen is older than that, the flow may have stopped"
            )
            items.append(Item("T2", artifact, locator, claim, "absent", "log_stopped"))
        return items
    if policy.deactivated:
        claim = f"no session in {_span(dataset)}: the policy is deactivated, it matches no traffic"
        return [Item("T2", artifact, locator, claim, "blind", "session_log")]
    if not (policy.log_init or policy.log_close):
        claim = (
            "the policy has no `then log` statement, so the log cannot show its traffic: "
            "no log line here says nothing about use (not the same as no traffic)"
        )
        locator = f"policy {policy.name} has no logging"
        return [Item("T2", artifact, locator, claim, "blind", "session_log")]
    options = " and ".join(
        o
        for o, on in (("session-init", policy.log_init), ("session-close", policy.log_close))
        if on
    )
    claim = f"the policy logs {options}, and no session was logged in {_span(dataset)}"
    window = dataset.log_window
    if window.start and window.end:
        days = (window.end.date() - window.start.date()).days + 1
        claim += f"; a job that runs less often than every {days} days would not show in it"
    return [Item("T2", artifact, locator, claim, "absent", "session_log")]


def _describe(dataset: Dataset, summary: LogSummary) -> str:
    parts = []
    if summary.sessions:
        when = ""
        if summary.first_seen and summary.last_seen:
            when = (
                f", first {summary.first_seen:%Y-%m-%d %H:%M}"
                f", last {summary.last_seen:%Y-%m-%d %H:%M}"
            )
        parts.append(f"{summary.sessions} sessions logged in {_span(dataset)}{when}")
        parts.append(f"sources {_some(summary.sources, summary.source_count)}")
        parts.append(f"destinations {_some(summary.destinations, summary.destination_count)}")
        if summary.ports:
            parts.append("ports " + ", ".join(summary.ports))
        if pattern := time_of_day(summary.hours, summary.weekdays):
            parts.append(f"time of day: {pattern}")
        window = dataset.log_window
        if hint := recurrence(
            summary.days,
            window.start.date() if window.start else None,
            window.end.date() if window.end else None,
        ):
            parts.append(f"recurrence: {hint}")
    if summary.deny:
        parts.append(f"{summary.deny} denied sessions")
    return "; ".join(parts)


def _hosts(dataset: Dataset, names: list[str], depth: int = 0) -> list[str]:
    """Address objects behind NAMES, address sets expanded."""
    found: list[str] = []
    for name in names:
        obj = dataset.config.addresses.get(name)
        if obj is None:
            continue
        if obj.kind == "address_set" and depth < MAX_SET_DEPTH:
            found += _hosts(dataset, obj.members, depth + 1)
        elif obj.kind == "address" and obj.value:
            found.append(name)
    return list(dict.fromkeys(found))


def shared_address_items(dataset: Dataset, policy: Policy, vocab: Vocabulary) -> list[Item]:
    """One T3 item per destination object whose address is also an object named after
    another application (session 24): the address may have been reused, so the policy
    may carry traffic it was not written for. Which side is current is not known.
    A source object with such an address gives a `shared_source` item: the name may be
    stale (the application renamed), which lowers confidence but not the verdict.
    A deactivated policy carries no traffic: no item."""
    if policy.deactivated:
        return []
    by_value: dict[str, list[str]] = {}
    for name, obj in dataset.config.addresses.items():
        if obj.kind == "address" and obj.value:
            by_value.setdefault(obj.value, []).append(name)
    items = []
    sides = [(n, "shared_address") for n in _hosts(dataset, policy.destinations)]
    sides += [(n, "shared_source") for n in _hosts(dataset, policy.sources)]
    for name, kind in sides:
        value = dataset.config.addresses[name].value or ""
        mine = vocab.in_object(name)
        others = [
            (other, theirs)
            for other in by_value.get(value, [])
            if other != name
            and (theirs := vocab.in_object(other))
            and mine
            and not set(theirs) & set(mine)
        ]
        if not others:
            continue
        apps = list(dict.fromkeys(a for _, theirs in others for a in theirs))
        named = ", ".join(f"{o} ({', '.join(t)})" for o, t in others)
        claim = f"address {value} of {name} ({', '.join(mine)}) is also the address of {named}: "
        if kind == "shared_address":
            claim += (
                "the address may have been reused by another application, or the application "
                "renamed, so this policy may carry traffic it was not written for"
            )
        else:
            claim += (
                "this source may now be the other application, or the application renamed: "
                "the name may be stale"
            )
        locator = f"address-book objects {name}, {', '.join(o for o, _ in others)}"
        objects = [name] + [o for o, _ in others]
        items.append(
            Item("T3", "config.set", locator, claim, None, kind, apps, {}, [], value, objects)
        )
    return items


def _flat(name: str) -> str:
    return re.sub(r"[-_.\s]+", "-", name.lower()).strip("-")


def _echoes(policy_name: str, object_name: str) -> bool:
    """The policy name contains the object name (separators and a trailing number aside):
    `Hosted-Networks_to_CCTV` repeats `Hosted-Networks`, `TO-SHARE_X` repeats `SHARE-X-2`."""
    obj = re.sub(r"-\d+$", "", _flat(object_name))
    return len(obj) >= 3 and obj in _flat(policy_name)


def dynamic_app(name: str) -> str | None:
    """The application a dynamic application names: `junos:SLACK` gives `slack`. A group
    (`junos:web:shopping`), `any` and `none` name no application."""
    parts = name.lower().split(":")
    if len(parts) != 2 or parts[1] in ("any", "none", ""):
        return None
    return parts[1]


def _temporary_words(policy: Policy) -> list[str]:
    """Words of the name, description or annotations that mark the policy as temporary
    (typos included)."""
    text = " ".join([policy.name, policy.description or "", *policy.annotations])
    words = re.findall(r"[a-z]+", text.lower())
    return sorted(
        {w for w in words if w in TEMPORARY_WORDS or (len(w) == 4 and sorted(w) == list("empt"))}
    )


def collect(
    dataset: Dataset,
    key: PolicyKey,
    vocab: Vocabulary | None = None,
    found: list[Marker] | None = None,
    moves: list[Migration] | None = None,
    cleared: dict[tuple[str, str], Clear] | None = None,
    legacy: Vocabulary | None = None,
) -> Finding:
    policy = dataset.config.policy(key)
    if policy is None:
        raise KeyError(f"policy {key} not found in config.set")
    vocab = vocab or vocabulary(dataset)
    # Not-live signals keep the reading without regional instances (palimp.apps).
    legacy = legacy or vocabulary(dataset, instances=False)
    found = markers(dataset, legacy) if found is None else found
    moves = migrations(dataset, legacy) if moves is None else moves
    cleared = clears(dataset) if cleared is None else cleared
    history = dataset.history.get(str(key))
    created = history.created_in_commit if history else None
    # Not-live signals date the policy from its current name (a rename is a deliberate
    # touch): the same reading as before renames were joined (session 24).
    named = history.named_in_commit if history else None
    renames = history.renames if history else []
    own_keys = {str(key)} | {r.old_key for r in renames}
    commit = next((c for c in dataset.commits if c.index == created), None)
    items: list[Item] = []

    if policy.description:
        locator = f"policy {policy.name} description"
        apps = vocab.in_text(policy.description)
        items.append(
            Item("T1", "config.set", locator, policy.description, None, "description", apps)
        )
    for number, note in enumerate(policy.annotations, start=1):
        locator = f"policy {policy.name} annotation" + (
            f" {number}" if len(policy.annotations) > 1 else ""
        )
        apps = vocab.in_text(note)
        items.append(Item("T1", "config.set", locator, note, None, "annotation", apps))
    if commit and commit.comment:
        when = f"{commit.timestamp:%Y-%m-%d %H:%M:%S} {commit.time_zone} by {commit.user}"
        locator = f"commit {commit.index} ({when})"
        apps = vocab.in_text(commit.comment)
        items.append(
            Item("T1", "commits.txt", locator, commit.comment, None, "commit_comment", apps)
        )

    places = [("name", policy.name), ("description", policy.description or "")]
    places += [("annotation", note) for note in policy.annotations]
    if commit:
        places.append((f"commit {commit.index} comment", commit.comment))
    seen: set[str] = set()
    for place, text in places:
        for ref in TICKET_REF.findall(text):
            ref = ref.upper()
            if ref in seen:
                continue
            seen.add(ref)
            ticket = dataset.tickets.get(ref)
            if ticket:
                details = ", ".join(
                    f"{label} {value}"
                    for label, value in (
                        ("requester", ticket.requester),
                        ("status", ticket.status),
                        ("opened", ticket.opened),
                        ("related CI", ticket.related_ci),
                    )
                    if value
                )
                claim = f"{ticket.summary or ''} ({details})".strip()
                apps = vocab.in_text(ticket.summary or "")
                if ticket.related_ci and (
                    ci := vocab.lookup(ticket.related_ci.removeprefix("shared-"))
                ):
                    apps = [ci] + [a for a in apps if a != ci]
                locator = f"ticket {ref} (referenced in {place})"
                items.append(Item("T1", "tickets.csv", locator, claim, None, "ticket", apps))
            else:
                artifact = "commits.txt" if place.startswith("commit") else "config.set"
                locator = f"ticket reference {ref} in {place}"
                items.append(
                    Item("T1", artifact, locator, "not in tickets.csv", None, "ticket_reference")
                )

    for artifact, locator, claim, apps in decommission_items(dataset, policy, named, found, legacy):
        items.append(Item("T1", artifact, locator, claim, None, "decommission", apps))

    for locator, claim, objects in leftover_items(dataset, policy, named, moves):
        apps = list(dict.fromkeys(a for o in objects for a in vocab.in_object(o)))
        items.append(Item("T3", "rollbacks", locator, claim, None, "migration_leftover", apps))

    named = [n for n in policy.sources + policy.destinations if n != "any"]
    if named:
        claim = shown([_resolve(dataset, n) for n in named], "; ")
        apps = [a for n in named for a in vocab.in_object(n)]
        apps = list(dict.fromkeys(apps))
        sides = {}
        for side, names in (("source", policy.sources), ("destination", policy.destinations)):
            names = [n for n in names if n != "any"]
            sides[side] = Side(
                apps=list(dict.fromkeys(a for n in names for a in vocab.in_object(n))),
                roles=list(dict.fromkeys(r for n in names for r in roles(n))),
            )
        locator = "address objects " + shown(named)
        items.append(Item("T3", "config.set", locator, claim, None, "address_objects", apps, sides))
    # A policy name that repeats an address object name of the rule is not an
    # independent source for what that object names (decision 0042).
    echoed = {a for n in named if _echoes(policy.name, n) for a in vocab.in_object(n)}
    if name_apps := [a for a in vocab.in_object(policy.name) if a not in echoed]:
        claim = (
            f"the policy name names {', '.join(name_apps)}: a name chosen for the rule, "
            "not a statement of why it exists"
        )
        locator = f"policy {policy.name} name"
        items.append(Item("T3", "config.set", locator, claim, None, "policy_name", name_apps))
    items += shared_address_items(dataset, policy, vocab)
    if policy.dynamic_applications:
        claim = (
            "the policy matches the dynamic application"
            + ("s " if len(policy.dynamic_applications) > 1 else " ")
            + ", ".join(policy.dynamic_applications)
            + " (application identification: the rule names the application it is for)"
        )
        locator = f"policy {policy.name} match dynamic-application"
        apps = [a for n in policy.dynamic_applications if (a := dynamic_app(n))]
        items.append(Item("T3", "config.set", locator, claim, None, "dynamic_application", apps))
    if policy.application_services:
        claim = (
            "the permit attaches application services: "
            + "; ".join(policy.application_services)
            + " (structure chosen for this rule, it names no application)"
        )
        locator = f"policy {policy.name} then permit application-services"
        items.append(Item("T3", "config.set", locator, claim, None, "application_services"))
    if policy.permit_options:
        claim = (
            "the permit carries options: "
            + "; ".join(policy.permit_options)
            + " (how this rule lets traffic through, it names no application)"
        )
        locator = f"policy {policy.name} then permit options"
        items.append(Item("T3", "config.set", locator, claim, None, "permit_options"))
    if policy.deactivated:
        statements = "; ".join(policy.deactivated_statements) or "deactivate statement"
        claim = (
            "the policy is deactivated: it is kept in the configuration but matches no traffic"
            f" ({statements})"
        )
        locator = f"policy {policy.name} deactivated"
        items.append(Item("T3", "config.set", locator, claim, None, "deactivated"))
    if words := _temporary_words(policy):
        where = "name, description or annotation" if policy.annotations else "name or description"
        claim = (
            f"the {where} marks the policy as temporary ({', '.join(words)}): "
            "a label, not a sign that the policy is unused"
        )
        locator = f"policy {policy.name} name and description"
        if policy.annotations:
            locator += " and annotations"
        items.append(Item("T3", "config.set", locator, claim, None, "temporary_marker"))
    if created is not None:
        siblings = [k for k in dataset.created_by_commit.get(created, []) if k not in own_keys]
        if siblings:
            locator = f"commit {created}: rollback-{created + 1:02d} vs " + (
                "config.set" if created == 0 else f"rollback-{created:02d}"
            )
            claim = "created together with " + ", ".join(siblings)
            items.append(Item("T3", "rollbacks", locator, claim, None, "created_together"))

    for rename in renames:
        changed = next((c for c in dataset.commits if c.index == rename.commit), None)
        said = f', "{changed.comment}"' if changed and changed.comment else ""
        locator = f"commit {rename.commit}: rollback-{rename.commit + 1:02d} vs " + (
            "config.set" if rename.commit == 0 else f"rollback-{rename.commit:02d}"
        )
        claim = (
            f"renamed from {rename.old_key} to {rename.new_key} in commit {rename.commit}{said}: "
            "deleted and re-added with the same match, the same rule under a new name"
        )
        items.append(Item("T3", "rollbacks", locator, claim, None, "renamed"))
    took = [t for t in takeovers(dataset, policy, created) if t.key not in own_keys]
    if took:
        commits = sorted({t.commit for t in took})
        locator = ("commit " if len(commits) == 1 else "commits ") + ", ".join(
            str(i) for i in commits
        )
        locator += " (rollbacks)"
        items.append(
            Item("T3", "rollbacks", locator, takeover_claim(dataset, took), None, "takeover")
        )

    named_apps = list(dict.fromkeys(a for item in items for a in item.apps))
    for app in named_apps:
        if candidates := vocab.candidates(app):
            claim = (
                f"{app} is the bare name of regional instances ({', '.join(candidates)}) and is "
                "not itself a related CI in tickets.csv: it may stand for any of them"
            )
            locator = f"tickets.csv related CIs and address object names starting with {app}"
            items.append(
                Item("T3", "tickets.csv", locator, claim, None, "ambiguous_app", [app, *candidates])
            )
    for locator, claim, apps in requester_items(dataset, named_apps):
        items.append(Item("T3", "tickets.csv", locator, claim, None, "app_requesters", apps))

    clear = cleared.get((policy.from_zone, policy.to_zone))
    items += hit_count_items(dataset, policy, clear) + log_items(dataset, policy)
    if policy.applications:
        services = [
            line
            for name in policy.applications
            for line in describe(name, dataset.config.applications)
        ]
        locator = "applications " + shown(policy.applications)
        # A custom application named after a known application names it too.
        custom = [n for n in policy.applications if n != "any" and not n.startswith("junos-")]
        apps = list(dict.fromkeys(a for n in custom for a in vocab.in_object(n)))
        plain = [
            s for n in policy.applications for s in service_names(n, dataset.config.applications)
        ]
        items.append(
            Item(
                "T4",
                "config.set",
                locator,
                shown(services, "; "),
                None,
                "services",
                apps,
                services=list(dict.fromkeys(plain)),
            )
        )

    evidence = [
        Evidence(
            id=f"E{i}",
            tier=item.tier,
            artifact=item.artifact,
            locator=item.locator,
            claim=item.claim,
            signal=item.signal,
            kind=item.kind,
            apps=item.apps,
            sides=item.sides,
            services=item.services,
            address=item.address,
            objects=item.objects,
        )
        for i, item in enumerate(items, start=1)
    ]
    finding = Finding(key=key, policy=policy, created_in_commit=created, evidence=evidence)
    finding.assessment = assess(finding, dataset)
    return finding


def collect_all(dataset: Dataset) -> list[Finding]:
    vocab = vocabulary(dataset)
    legacy = vocabulary(dataset, instances=False)
    found = markers(dataset, legacy)
    moves = migrations(dataset, legacy)
    cleared = clears(dataset)
    return [
        collect(dataset, p.key, vocab, found, moves, cleared, legacy)
        for p in dataset.config.policies
    ]
