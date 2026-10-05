"""Application names found in the artifacts, to tell which application a text or object names.

Plain rules, no scoring. Applications are learned from the input itself:
- the related CI column of tickets.csv (for example `webshop`);
- short names used in ticket summaries, mapped to the related CI of the same
  ticket (`Decom ESHOP` with related CI `webshop` gives `eshop` -> `webshop`).
  A short name seen with two different related CIs is ambiguous and dropped;
- the first segment of address object names (`crm-db-01` gives `crm`), unless
  it is a role word such as `pc`, `users` or `servers`. A segment that is
  already a ticket alias (`bkp-01` with tickets `BKP ...` for `backup`) names
  that application. A segment of at least 3 letters that is the start of
  exactly one related CI is an abbreviation of it (`mon-01` with related CI
  `shared-monitoring` gives `mon` -> `monitoring`). Shorter segments are never
  read as abbreviations (`bi` must not name `billing`).

A token names an application when it is one of the learned names or aliases.
Free text gets no prefix matching: `web` must not name `webshop`.
"""

import re
from dataclasses import dataclass, field

from palimp.models import Dataset

# Words that say who or what kind of host or network, not which application.
ROLE_WORDS = frozenset(
    {
        "pc",
        "server",
        "servers",
        "srv",
        "mgmt",
        "lan",
        "subnet",
        "ws",
        "user",
        "users",
        "vendor",
        "partner",
        "host",
        "hosts",
        "net",
        "network",
        "any",
        "all",
        "grp",
        "group",
        "h",
        "n",
        "shared",
        "new",
        "old",
    }
)
TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9]*")
SHORT_NAME = re.compile(r"\b[A-Z][A-Z0-9]{1,9}\b")
TICKET_ID = re.compile(r"^(?:CHG|INC|RITM|REQ|CR|SR|TASK)\d*$")


@dataclass
class Vocabulary:
    names: set[str] = field(default_factory=set)
    aliases: dict[str, str] = field(default_factory=dict)

    def lookup(self, token: str) -> str | None:
        token = token.lower()
        if token in ROLE_WORDS:
            return None
        if token in self.names:
            return token
        return self.aliases.get(token)

    def in_text(self, text: str) -> list[str]:
        """Applications named in free text (comment, description, ticket summary)."""
        found: list[str] = []
        for token in TOKEN.findall(text or ""):
            if TICKET_ID.match(token.upper()):
                continue
            app = self.lookup(token)
            if app and app not in found:
                found.append(app)
        return found

    def in_object(self, name: str) -> list[str]:
        """Applications named by an address object name, for example `vendor-bi-52`."""
        found: list[str] = []
        for token in re.split(r"[-_.]", name):
            if not token.isalpha():
                continue
            app = self.lookup(token)
            if app and app not in found:
                found.append(app)
        return found


def _ci(value: str | None) -> str | None:
    """Related CI as an application name: `shared-dns` gives `dns`."""
    if not value:
        return None
    value = value.strip().lower()
    return value.removeprefix("shared-") or None


# Shortest object name segment read as an abbreviation of a related CI.
MIN_ABBREVIATION = 3


def vocabulary(dataset: Dataset) -> Vocabulary:
    vocab = Vocabulary()
    for ticket in dataset.tickets.values():
        if app := _ci(ticket.related_ci):
            vocab.names.add(app)
    cis = sorted(vocab.names)
    seen: dict[str, set[str]] = {}
    for ticket in dataset.tickets.values():
        app = _ci(ticket.related_ci)
        if not app:
            continue
        for short in SHORT_NAME.findall(ticket.summary or ""):
            if not TICKET_ID.match(short):
                seen.setdefault(short.lower(), set()).add(app)
    for short, apps in seen.items():
        if len(apps) == 1 and short not in vocab.names and short not in ROLE_WORDS:
            vocab.aliases[short] = next(iter(apps))
    for name in dataset.config.addresses:
        first = re.split(r"[-_.]", name.lower())[0]
        if not first.isalpha() or len(first) < 2 or first in ROLE_WORDS:
            continue
        if first in vocab.names or first in vocab.aliases:
            continue
        expanded = [ci for ci in cis if ci.startswith(first)]
        if len(first) >= MIN_ABBREVIATION and len(expanded) == 1:
            vocab.aliases[first] = expanded[0]
        else:
            vocab.names.add(first)
    return vocab
