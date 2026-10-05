"""T4 contextual evidence: plain service names for applications."""

from palimp.formats.junos_set import parse_set
from palimp.services import describe

CONFIG = """\
set applications application tcp-5432 protocol tcp
set applications application tcp-5432 destination-port 5432
set applications application tcp-7001 protocol tcp
set applications application tcp-7001 destination-port 7001
set applications application-set db-apps application tcp-5432
set applications application-set db-apps application junos-ms-sql
"""


def test_describe() -> None:
    apps = parse_set(CONFIG).applications
    assert describe("junos-ssh", apps) == ["junos-ssh: SSH (tcp/22, Junos predefined application)"]
    assert describe("tcp-5432", apps) == [
        "tcp-5432: PostgreSQL database (tcp/5432, custom application)"
    ]
    assert describe("tcp-7001", apps) == ["tcp-7001: tcp/7001, no well-known service on this port"]
    assert describe("any", apps)[0].startswith("any: any application")
    assert describe("db-apps", apps) == [
        "tcp-5432: PostgreSQL database (tcp/5432, custom application)",
        "junos-ms-sql: Microsoft SQL Server (tcp/1433, Junos predefined application)",
    ]
    assert describe("junos-unknown", apps) == [
        "junos-unknown: Junos predefined application, not in palimp's service table"
    ]
    assert describe("missing", apps) == ["missing: not defined in config.set"]
