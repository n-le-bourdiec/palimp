"""Difficulty levels and their knobs (spec section 7.1, decision 0008).

Milestone 1 implements Easy only. Medium is declared in the spec but not
generated yet; its format knobs are fixed in spec section 7.1 (for example
`log_collection="syslog-server"`) and must be used when it is added.

Format knobs (session 8) choose between layouts confirmed in
tests/fixtures/junos_docs/ (docs/format-assumptions.md):
- `hitcount_layout`: "standard" (Logical system line, Action column) or
  "legacy" (lowercase header, no Action column, `Number of policy:` footer).
- `log_release`: RT_FLOW attribute list. "12.x" (`session-id-32`, no
  connection tag or NAT rule types), "pre-22.2" (22.2R1 list up to
  `encrypted`) or "22.2" (full 22.2R1 list).
- `log_collection`: "device" (`<14>1 ...` as in `show security log file`) or
  "syslog-server" (server timestamp and host prefix, no `<PRI>`).
- `rescue_line`: a `rescue ... by root via other` line ends commits.txt.
"""

from dataclasses import asdict, dataclass, fields, replace


@dataclass(frozen=True)
class Level:
    name: str
    years: int
    applications: int
    user_sites: int
    comment_rate: float
    description_rate: float
    log_rate: float
    log_init_rate: float
    log_window_days: int
    days_since_hit_reset: int
    ticket_rate: float
    ticket_export_coverage: float
    cleanup_rate: float
    decommissions_per_year: float
    migrations_per_year: float
    commits_per_year: int
    device_time_zone: str
    log_samples_per_policy_day: int
    hitcount_layout: str = "standard"
    log_release: str = "pre-22.2"
    log_collection: str = "device"
    rescue_line: bool = False

    def __post_init__(self) -> None:
        for name, allowed in CHOICES.items():
            if getattr(self, name) not in allowed:
                raise ValueError(f"{name} must be one of {allowed}, not {getattr(self, name)!r}")

    def knobs(self) -> dict:
        return asdict(self)

    def with_overrides(self, overrides: dict[str, str]) -> "Level":
        """Copy with knobs replaced; string values are converted to the knob's type."""
        types = {f.name: type(getattr(self, f.name)) for f in fields(self)}
        values = {}
        for name, value in overrides.items():
            if name not in types or name == "name":
                raise ValueError(f"unknown knob {name!r}")
            kind = types[name]
            if kind is bool and isinstance(value, str):
                if value.lower() not in ("true", "false"):
                    raise ValueError(f"{name} must be true or false, not {value!r}")
                value = value.lower() == "true"
            values[name] = kind(value)
        return replace(self, **values)


CHOICES = {
    "hitcount_layout": ("standard", "legacy"),
    "log_release": ("12.x", "pre-22.2", "22.2"),
    "log_collection": ("device", "syslog-server"),
}


EASY = Level(
    name="easy",
    years=2,
    applications=18,
    user_sites=2,
    comment_rate=0.9,
    description_rate=0.8,
    log_rate=0.9,
    log_init_rate=0.2,
    log_window_days=90,
    days_since_hit_reset=365,
    ticket_rate=0.9,
    ticket_export_coverage=1.0,
    cleanup_rate=0.35,
    decommissions_per_year=2.0,
    migrations_per_year=1.0,
    commits_per_year=20,
    device_time_zone="UTC",
    log_samples_per_policy_day=1,
)

LEVELS = {"easy": EASY}
