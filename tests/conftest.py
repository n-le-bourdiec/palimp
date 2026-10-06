"""Shared test helpers for the analyzer tests.

`to_hierarchical` renders the model palimp parsed from a set-format artifact
directory as hierarchical (curly-brace) text, the way `show configuration`
prints it, for the round-trip and anonymize tests (decision 0032). It writes
only what the model holds: statements palimp ignores (system, interfaces,
NAT) are not rendered.
"""

import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from palimp.formats.junos_config import parse_config
from palimp.models import Config, Policy

INDENT = "    "


def _block(name: str, body: list[str], prefix: str = "") -> list[str]:
    return [f"{prefix}{name} {{", *(INDENT + line for line in body), "}"]


def _values(keyword: str, values: list[str]) -> list[str]:
    if not values:
        return []
    if len(values) == 1:
        return [f"{keyword} {values[0]};"]
    return [f"{keyword} [ {' '.join(values)} ];"]


def _policy(policy: Policy) -> list[str]:
    body = []
    if policy.description is not None:
        body.append(f'description "{policy.description}";')
    match = (
        _values("source-address", policy.sources)
        + _values("destination-address", policy.destinations)
        + _values("application", policy.applications)
    )
    if match:
        body += _block("match", match)
    then = [f"{policy.action};"] if policy.action else []
    flags = (("session-init", policy.log_init), ("session-close", policy.log_close))
    log = [f"{name};" for name, on in flags if on]
    if log:
        then += _block("log", log)
    if then:
        body += _block("then", then)
    body += [f"inactive: {statement};" for statement in policy.deactivated_statements]
    lines = []
    for note in policy.annotations:
        lines.append(f"/* {note} */")
    prefix = "inactive: " if policy.deactivated else ""
    return lines + _block(f"policy {policy.name}", body, prefix)


def _book(config: Config, book: str) -> list[str]:
    body = []
    for obj in config.addresses.values():
        if obj.book != book:
            continue
        if obj.kind == "address":
            body.append(f"address {obj.name} {obj.value};")
        else:
            body += _block(f"address-set {obj.name}", [f"address {m};" for m in obj.members])
    return body


def render_hierarchical(config: Config) -> str:
    """Hierarchical text for CONFIG: policies grouped by zone pair, as Junos prints them."""
    books = list(dict.fromkeys(obj.book for obj in config.addresses.values()))
    security: list[str] = []
    if "global" in books:
        security += _block("address-book", _block("global", _book(config, "global")))
    zones = [b for b in books if b != "global"]
    if zones:
        body = []
        for zone in zones:
            body += _block(f"security-zone {zone}", _block("address-book", _book(config, zone)))
        security += _block("zones", body)
    pairs: dict[tuple[str, str], list[str]] = {}
    for policy in config.policies:
        pairs.setdefault((policy.from_zone, policy.to_zone), []).extend(_policy(policy))
    if pairs:
        body = []
        for (source, target), lines in pairs.items():
            body += _block(f"from-zone {source} to-zone {target}", lines)
        security += _block("policies", body)
    apps: list[str] = []
    for app in config.applications.values():
        if app.kind == "application":
            fields = [
                f"{k} {v};"
                for k, v in (("protocol", app.protocol), ("destination-port", app.destination_port))
                if v
            ]
            apps += _block(f"application {app.name}", fields or ['description "rendered";'])
        else:
            apps += _block(
                f"application-set {app.name}", [f"application {m};" for m in app.members]
            )
    lines = ["## Last commit: rendered by the palimp test suite", "version 21.4R3;"]
    if security:
        lines += _block("security", security)
    if apps:
        lines += _block("applications", apps)
    return "\n".join(lines) + "\n"


def hierarchical_copy(source: Path, target: Path) -> Path:
    """Copy the artifact directory SOURCE to TARGET with config.set and every rollback
    rendered as hierarchical text from the model palimp parsed."""
    shutil.copytree(source, target)
    configs = [target / "config.set", *sorted((target / "rollbacks").glob("rollback-*.set"))]
    for path in configs:
        config = parse_config(path.read_text(encoding="utf-8"))
        path.write_text(render_hierarchical(config), encoding="utf-8")
    return target


@pytest.fixture
def to_hierarchical() -> Callable[[Path, Path], Path]:
    return hierarchical_copy
