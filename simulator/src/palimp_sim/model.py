"""Company and history records. Days are integers counted from the start date."""

from dataclasses import dataclass, field

from palimp_sim.catalog import AppTemplate, FlowTemplate
from palimp_sim.junos import Config


@dataclass
class Person:
    person_id: str
    name: str
    team: str


@dataclass
class Admin:
    admin_id: str
    login: str
    name: str
    persona: str
    joined: int
    left: int | None = None

    def active(self, day: int) -> bool:
        return self.joined <= day and (self.left is None or day < self.left)


@dataclass
class Server:
    server_id: str
    hostname: str
    ip: str
    zone_role: str
    app_id: str
    tier: str
    active_from: int
    active_to: int | None = None


@dataclass
class App:
    app_id: str
    name: str
    owner_id: str
    shared: bool
    template: AppTemplate
    index: int
    tiers: dict[str, list[str]] = field(default_factory=dict)  # tier -> server ids
    go_live: int | None = None
    retired: int | None = None
    generation: int = 0


@dataclass
class Endpoint:
    zone_role: str
    address: str
    prefixes: list[str]
    label: str


@dataclass
class Flow:
    flow_id: str
    app_id: str
    template: FlowTemplate
    src: Endpoint
    dst: Endpoint
    start: int
    end: int | None = None

    def active(self, day: int) -> bool:
        return self.start <= day and (self.end is None or day < self.end)


@dataclass
class Commit:
    seq: int
    day: int
    second: int
    login: str
    admin_id: str
    client: str
    comment: str
    event_id: str
    config: Config
    created: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)


@dataclass
class Ticket:
    ticket_id: str
    opened: int
    closed: int
    status: str
    requester: str
    assignee: str
    summary: str
    category: str
    related_ci: str
    exported: bool


@dataclass
class Event:
    event_id: str
    kind: str
    day: int
    admin_id: str
    app_id: str | None = None
    ticket_id: str | None = None
    commits: list[int] = field(default_factory=list)
    note: str = ""


@dataclass
class PolicyMeta:
    uid: str
    app_id: str
    flow_ids: list[str]
    event_id: str
    commit_seq: int
    admin_id: str
    ticket_id: str | None
