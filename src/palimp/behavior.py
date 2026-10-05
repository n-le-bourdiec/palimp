"""Behavioral patterns read from log summaries: time of day and recurrence.

Plain rules on counts, no scoring. Each function returns a short factual
phrase, or None when the data cannot support one.
"""

from datetime import date

WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
# A pattern needs this many sessions (time of day) or active days (recurrence).
MIN_SESSIONS = 3
MIN_OCCURRENCES = 3
# Activity starting or ending this many days inside the window is reported.
EDGE_DAYS = 7
NIGHT = range(0, 6)
BUSINESS = range(7, 19)
PERIODS = (
    # name, smallest gap, largest gap (days)
    ("weekly", 7, 7),
    ("monthly", 28, 31),
    ("quarterly", 89, 92),
)


def time_of_day(hours: list[int], weekdays: list[int]) -> str | None:
    total = sum(hours)
    if total < MIN_SESSIONS:
        return None
    night = sum(hours[h] for h in NIGHT)
    business = sum(hours[h] for h in BUSINESS)
    working_days = sum(weekdays[:5])
    if night / total >= 0.8:
        return f"nightly ({night / total:.0%} of sessions between 00:00 and 06:00)"
    if business / total >= 0.8 and working_days / total >= 0.9:
        return f"business hours ({business / total:.0%} between 07:00 and 19:00, on weekdays)"
    if business / total >= 0.8:
        return f"daytime ({business / total:.0%} between 07:00 and 19:00)"
    return "around the clock"


def recurrence(days: list[date], start: date | None, end: date | None) -> str | None:
    """Recurrence hint from the distinct active days within the log window."""
    if not days or start is None or end is None:
        return None
    window = (end - start).days + 1
    count = len(days)
    if count == 1:
        return (
            f"active on a single day ({days[0]:%Y-%m-%d}) of a {window}-day log window: "
            "a one-off, or a job that runs less often than the window shows"
        )
    edges = _edges(days, start, end)
    span = (days[-1] - days[0]).days + 1
    if span >= 7 and count >= 0.6 * span:
        if span >= window - 2 * EDGE_DAYS:
            return f"daily (active on {count} of {window} days)"
        return f"daily from {days[0]:%Y-%m-%d} to {days[-1]:%Y-%m-%d} ({count} active days)" + edges
    gaps = [(b - a).days for a, b in zip(days, days[1:], strict=False)]
    for name, low, high in PERIODS:
        if all(low <= gap <= high for gap in gaps):
            detail = {
                "weekly": f"every {WEEKDAYS[days[0].weekday()]}",
                "monthly": f"around day {days[0].day}",
                "quarterly": f"starting {days[0]:%Y-%m-%d}",
            }[name]
            if count >= MIN_OCCURRENCES:
                return f"{name} ({detail}, {count} occurrences)" + edges
            return f"possibly {name} (2 occurrences {gaps[0]} days apart)" + edges
    return f"irregular ({count} active days in a {window}-day window)" + edges


# A flow that stops: active on at least STOP_MIN_DAYS days, on half the days of its
# span or more, then silent for STOP_DAYS days or more until the window ends,
# a silence longer than twice any earlier gap.
STOP_MIN_DAYS = 5
STOP_DAYS = 14


def stopped(days: list[date], end: date) -> int | None:
    """Days of silence at the end of the window after dense activity, else None."""
    if len(days) < STOP_MIN_DAYS:
        return None
    span = (days[-1] - days[0]).days + 1
    silence = (end - days[-1]).days
    gaps = [(b - a).days for a, b in zip(days, days[1:], strict=False)]
    if len(days) >= 0.5 * span and silence >= STOP_DAYS and silence > 2 * max(gaps):
        return silence
    return None


def _edges(days: list[date], start: date, end: date) -> str:
    """Say when activity starts late or stops early in the window."""
    notes = []
    if (days[0] - start).days > EDGE_DAYS:
        notes.append(f"first session {(days[0] - start).days} days after the window opens")
    if (end - days[-1]).days > EDGE_DAYS:
        notes.append(f"no session in the last {(end - days[-1]).days} days of the window")
    return "; " + "; ".join(notes) if notes else ""
