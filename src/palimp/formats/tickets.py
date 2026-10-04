"""Reader for a ticket export in CSV (optional input, any ticketing tool).

Required column: ticket_id. Recognized optional columns: opened, closed,
status, requester, assignee, summary, category, related_ci. Other columns are
ignored.
"""

import csv
import io

from palimp.models import ParseStats, Ticket

FIELDS = (
    "opened",
    "closed",
    "status",
    "requester",
    "assignee",
    "summary",
    "category",
    "related_ci",
)


def parse_tickets(text: str, file: str = "tickets.csv") -> tuple[dict[str, Ticket], ParseStats]:
    stats = ParseStats(file=file)
    tickets: dict[str, Ticket] = {}
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or "ticket_id" not in reader.fieldnames:
        stats.add_unknown("header without a ticket_id column")
        return tickets, stats
    for row in reader:
        stats.total += 1
        ticket_id = (row.get("ticket_id") or "").strip()
        if not ticket_id:
            stats.add_unknown(",".join(v or "" for v in row.values()))
            continue
        tickets[ticket_id] = Ticket(
            ticket_id=ticket_id, **{field: row.get(field) or None for field in FIELDS}
        )
        stats.parsed += 1
    return tickets, stats
