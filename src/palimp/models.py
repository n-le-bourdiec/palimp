"""Normalized data model shared by the readers, the evidence collectors and the CLI."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

Tier = Literal["T1", "T2", "T3", "T4"]

# Zones of a global policy (`security policies global policy NAME`, decision 0034).
# Junos never allows `global` as a from-zone, so the pair cannot be a real zone pair.
GLOBAL = "global"


class PolicyKey(BaseModel, frozen=True):
    from_zone: str
    to_zone: str
    name: str

    def __str__(self) -> str:
        if self.from_zone == GLOBAL and self.to_zone == GLOBAL:
            return f"{GLOBAL}/{self.name}"
        return f"{self.from_zone}/{self.to_zone}/{self.name}"

    @classmethod
    def parse(cls, text: str) -> "PolicyKey":
        """FROM/TO/NAME for a zone policy, global/NAME for a global policy."""
        parts = text.split("/")
        if len(parts) == 2 and parts[0] == GLOBAL and parts[1]:
            return cls(from_zone=GLOBAL, to_zone=GLOBAL, name=parts[1])
        if len(parts) != 3 or not all(parts):
            raise ValueError(f"expected FROM/TO/NAME or global/NAME, got {text!r}")
        return cls(from_zone=parts[0], to_zone=parts[1], name=parts[2])


class Policy(BaseModel):
    from_zone: str
    to_zone: str
    name: str
    position: int = Field(description="order of first appearance in the configuration")
    description: str | None = None
    sources: list[str] = []
    destinations: list[str] = []
    applications: list[str] = []
    action: str | None = None
    log_init: bool = False
    log_close: bool = False
    deactivated: bool = False
    deactivated_statements: list[str] = []
    # `/* ... */` notes an admin attached to the policy or to a statement inside
    # it (`annotate`), shown only by the hierarchical format.
    annotations: list[str] = []
    # Global policies only: `match from-zone` and `match to-zone` conditions
    # (empty means any zone).
    match_from_zones: list[str] = []
    match_to_zones: list[str] = []

    @property
    def key(self) -> PolicyKey:
        return PolicyKey(from_zone=self.from_zone, to_zone=self.to_zone, name=self.name)

    @property
    def is_global(self) -> bool:
        return self.from_zone == GLOBAL and self.to_zone == GLOBAL

    def zones_text(self, side: str) -> str:
        """The zones a side of the rule applies to, in words ("zone X", "any zone")."""
        if not self.is_global:
            return f"zone {self.from_zone if side == 'from' else self.to_zone}"
        zones = self.match_from_zones if side == "from" else self.match_to_zones
        if not zones:
            return "any zone (global policy)"
        return ("zone " if len(zones) == 1 else "zones ") + ", ".join(zones) + " (global policy)"


class AddressObject(BaseModel):
    name: str
    kind: Literal["address", "address_set"]
    value: str | None = None
    members: list[str] = []
    book: str = "global"


class Application(BaseModel):
    name: str
    kind: Literal["application", "application_set"]
    protocol: str | None = None
    destination_port: str | None = None
    members: list[str] = []


class ParseStats(BaseModel):
    """Line accounting for one file. Unknown lines are reported, never fatal."""

    file: str
    total: int = 0
    parsed: int = 0
    ignored: int = 0
    unknown: int = 0
    unknown_samples: list[str] = []
    # Configuration files only: "set", "set relative" or "hierarchical".
    format: str = ""
    # Where `apply-groups` is used: statements inherited from configuration
    # groups are not expanded, so they are missing from the model.
    apply_groups: list[str] = []
    # Constructs read but not applied, each stated once.
    notes: list[str] = []

    def add_unknown(self, line: str) -> None:
        self.unknown += 1
        if len(self.unknown_samples) < 10:
            self.unknown_samples.append(line)


class Config(BaseModel):
    policies: list[Policy] = []
    addresses: dict[str, AddressObject] = {}
    applications: dict[str, Application] = {}
    stats: ParseStats

    def policy(self, key: PolicyKey) -> Policy | None:
        return next((p for p in self.policies if p.key == key), None)

    def keys(self) -> set[PolicyKey]:
        return {p.key for p in self.policies}


class Commit(BaseModel):
    index: int
    timestamp: datetime
    time_zone: str
    user: str
    client: str
    comment: str = ""
    # Known suffixes after the method (gap G4): "confirmed" or "activate".
    commit_type: str = ""
    rollback_minutes: int | None = None
    revision: str = ""
    # Any other text after the method, kept verbatim.
    extra: str = ""


class HitCount(BaseModel):
    from_zone: str
    to_zone: str
    name: str
    count: int
    # Empty in the legacy layout, which has no Action column.
    action: str = ""


class LogSummary(BaseModel):
    """What the RT_FLOW log says about one policy. Lists are capped, counts are not."""

    policy_name: str
    from_zone: str = ""
    to_zone: str = ""
    create: int = 0
    close: int = 0
    deny: int = 0
    sessions: int = Field(0, description="distinct sessions (by session id when logged)")
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    sources: list[str] = []
    source_count: int = 0
    destinations: list[str] = []
    destination_count: int = 0
    ports: list[str] = Field([], description="protocol/port, for example tcp/443")
    services: list[str] = Field([], description="service-name as logged, for example junos-ssh")
    hours: list[int] = Field([0] * 24, description="sessions per hour of day, as logged")
    weekdays: list[int] = Field([0] * 7, description="sessions per weekday, Monday first")
    days: list[date] = Field([], description="distinct days with at least one session")


class LogWindow(BaseModel):
    """Time span covered by the log file, and how the year was found."""

    start: datetime | None = None
    end: datetime | None = None
    undated_lines: int = Field(0, description="lines whose timestamp has no year")
    year_source: str = Field("", description="'forced', 'inferred', 'none' or '' (not needed)")
    year_note: str = ""
    addresses: list[str] = Field(
        [], description="every source and destination address seen in a log line"
    )


class Ticket(BaseModel):
    ticket_id: str
    opened: str | None = None
    closed: str | None = None
    status: str | None = None
    requester: str | None = None
    assignee: str | None = None
    summary: str | None = None
    category: str | None = None
    related_ci: str | None = None


class PolicyHistory(BaseModel):
    """Where a policy of the active configuration appears in the retained history."""

    created_in_commit: int | None = Field(
        None, description="commit index that added it; None if it predates the retained history"
    )
    oldest_retained_index: int


Signal = Literal["present", "absent", "blind"]


class Evidence(BaseModel):
    id: str
    tier: Tier
    artifact: str
    locator: str
    claim: str
    # T2 only (decision 0019): "present" when the artifact shows traffic,
    # "absent" when it could show traffic and shows none, "blind" when it cannot
    # show traffic for this policy (no logging, deactivated, artifact missing).
    # A blind item is a stated gap, never evidence of use or non-use.
    signal: Signal | None = None
    # Stable label of what the item is (for example "deactivated"), so that
    # scoring never parses claim text.
    kind: str = ""
    # Applications the item names (see palimp.apps), used to check agreement.
    apps: list[str] = []


Verdict = Literal["keep", "verify", "removal_candidate"]
Confidence = Literal["LOW", "MEDIUM", "HIGH"]


class Conflict(BaseModel):
    """Two evidence items that name different applications for the same policy."""

    evidence: list[str]
    text: str


class Assessment(BaseModel):
    """Deterministic verdict and confidence, each with the named rule that produced it."""

    verdict: Verdict
    verdict_rule: str
    verdict_reason: str
    verdict_evidence: list[str] = []
    confidence: Confidence
    confidence_rule: str
    confidence_reason: str
    confidence_evidence: list[str] = []
    intent_apps: list[str] = Field([], description="applications the intent evidence names")
    conflicts: list[Conflict] = []
    question: str | None = None
    ask: str | None = Field(None, description="who to ask about the policy, with the reasons")
    owner: str | None = Field(None, description="application owner, only when the artifacts agree")
    owner_candidates: list[str] = Field([], description="people who may own it, most likely first")


class Finding(BaseModel):
    key: PolicyKey
    policy: Policy
    created_in_commit: int | None
    evidence: list[Evidence] = []
    assessment: Assessment | None = None


class PastPolicy(BaseModel):
    """The match of a policy as one configuration of the history shows it."""

    key: str
    from_zone: str = ""
    to_zone: str = ""
    sources: list[str] = []
    destinations: list[str] = []
    applications: list[str] = []
    deactivated: bool = False

    @classmethod
    def of(cls, policy: Policy) -> "PastPolicy":
        return cls(
            key=str(policy.key),
            from_zone=policy.from_zone,
            to_zone=policy.to_zone,
            sources=policy.sources,
            destinations=policy.destinations,
            applications=policy.applications,
            deactivated=policy.deactivated,
        )


class Dataset(BaseModel):
    """Everything palimp read from one artifact directory, normalized."""

    source: str
    config: Config
    commits: list[Commit] = []
    commit_stats: ParseStats | None = None
    rollback_stats: list[ParseStats] = []
    history: dict[str, PolicyHistory] = {}
    created_by_commit: dict[int, list[str]] = Field(
        {}, description="policy keys added by each commit, found by diffing consecutive configs"
    )
    removed_by_commit: dict[int, list[PastPolicy]] = Field(
        {}, description="policies deleted by each commit, found by diffing consecutive configs"
    )
    added_by_commit: dict[int, list[PastPolicy]] = Field(
        {}, description="match of the policies added by each commit, as that commit left them"
    )
    deactivated_by_commit: dict[int, list[PastPolicy]] = Field(
        {}, description="policies each commit deactivated (active before, deactivated after)"
    )
    past_addresses: dict[str, AddressObject] = Field(
        {}, description="address objects of the retained history, newest definition first"
    )
    hit_counts: list[HitCount] = []
    hit_count_stats: ParseStats | None = None
    logs: dict[str, LogSummary] = Field(
        {}, description="keyed by FROM/TO/NAME, or by NAME when the log has no zones"
    )
    log_stats: ParseStats | None = None
    log_window: LogWindow = LogWindow()
    tickets: dict[str, Ticket] = {}
    ticket_stats: ParseStats | None = None
    warnings: list[str] = []
