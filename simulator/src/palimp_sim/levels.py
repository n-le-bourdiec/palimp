"""Difficulty levels and their knobs (spec section 7.1, decisions 0008 and 0012).

v1 implements Easy and Medium. Knobs added for Medium (session 9) have a
neutral default that Easy keeps, and are listed in the manifest only when they
differ from it, so Easy manifests keep their bytes.

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

With `draw_formats`, the four format knobs are drawn per scenario from the seed
(decision 0016), except those given as overrides. `log_release="22.2"` is
never drawn: its attributes after `encrypted` are written `N/A`, an
assumption, so it stays opt-in.
"""

from dataclasses import asdict, dataclass, field, fields, replace

# Medium-only knobs: omitted from the manifest while equal to their default.
NEW = {"medium": True}


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
    zones: int = field(default=4, metadata=NEW)
    persona_mix: bool = field(default=False, metadata=NEW)
    misleading_comment_rate: float = field(default=0.0, metadata=NEW)
    emergency_per_year: float = field(default=0.0, metadata=NEW)
    rare_jobs: int = field(default=0, metadata=NEW)
    cleanup_deactivate_rate: float = field(default=0.0, metadata=NEW)
    traps: bool = field(default=False, metadata=NEW)
    draw_formats: bool = field(default=False, metadata=NEW)
    clock_skew: bool = field(default=False, metadata=NEW)  # syslog server clock off by seconds

    def __post_init__(self) -> None:
        for name, allowed in CHOICES.items():
            if getattr(self, name) not in allowed:
                raise ValueError(f"{name} must be one of {allowed}, not {getattr(self, name)!r}")

    def knobs(self) -> dict:
        values = asdict(self)
        for item in fields(self):
            if item.metadata.get("medium") and values[item.name] == item.default:
                del values[item.name]
        return values

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

# Spec section 7.1, Medium column, v1 values (decisions 0008 and 0012): the
# knobs that only produce v2 traps (IP reuse, renames, cleanup mistakes,
# contractor periods) stay at zero. Decommissions and migrations per year are
# "not set yet" in the spec; 1.5 each is a simulator choice (session 9).
# comment_rate, description_rate and log_rate are weighted means: each persona
# applies its own factor (world.PERSONA_FACTORS). The format knobs below are
# the spec defaults; with draw_formats they are drawn per scenario.
MEDIUM = Level(
    name="medium",
    years=4,
    applications=25,
    user_sites=3,
    comment_rate=0.6,
    description_rate=0.4,
    log_rate=0.6,
    log_init_rate=0.2,
    log_window_days=60,
    days_since_hit_reset=180,
    ticket_rate=0.6,
    ticket_export_coverage=0.8,
    cleanup_rate=0.6,
    decommissions_per_year=1.5,
    migrations_per_year=1.5,
    commits_per_year=60,
    device_time_zone="UTC",
    log_samples_per_policy_day=1,
    hitcount_layout="standard",
    log_release="pre-22.2",
    log_collection="syslog-server",
    rescue_line=True,
    zones=5,
    persona_mix=True,
    misleading_comment_rate=0.03,
    emergency_per_year=1.0,
    rare_jobs=2,
    cleanup_deactivate_rate=0.3,
    traps=True,
    draw_formats=True,
    clock_skew=True,
)

# Weights of the per scenario format draw (decision 0016). 22.2 is opt-in only.
FORMAT_DRAWS = {
    "log_collection": (("syslog-server", 0.6), ("device", 0.4)),
    "log_release": (("pre-22.2", 0.7), ("12.x", 0.3)),
    "hitcount_layout": (("standard", 0.7), ("legacy", 0.3)),
    "rescue_line": ((True, 0.5), (False, 0.5)),
}

LEVELS = {"easy": EASY, "medium": MEDIUM}
