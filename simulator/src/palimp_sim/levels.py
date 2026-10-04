"""Difficulty levels and their knobs (spec section 7.1, decision 0008).

Milestone 1 implements Easy only. Medium is declared in the spec but not
generated yet.
"""

from dataclasses import asdict, dataclass


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

    def knobs(self) -> dict:
        return asdict(self)


EASY = Level(
    name="easy",
    years=2,
    applications=8,
    user_sites=2,
    comment_rate=0.9,
    description_rate=0.8,
    log_rate=0.9,
    log_init_rate=0.2,
    log_window_days=90,
    days_since_hit_reset=365,
    ticket_rate=0.9,
    ticket_export_coverage=1.0,
    cleanup_rate=0.9,
    decommissions_per_year=1.0,
    migrations_per_year=0.5,
    commits_per_year=20,
    device_time_zone="UTC",
    log_samples_per_policy_day=1,
)

LEVELS = {"easy": EASY}
