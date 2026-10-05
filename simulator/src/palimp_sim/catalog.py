"""Static catalog: application templates, shared services, people, zones.

Endpoint tokens used in flow templates:
- "users": every user site subnet (address set users-all)
- "internet": any internet address
- "partner:<name>": one internet host (RFC 5737 range)
- "servers-net": the whole server range
- "<tier>": the servers of this application's tier
- "shared:<app>:<tier>": the servers of a shared service tier
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TierTemplate:
    name: str
    count: int
    zone_role: str  # "servers" or "dmz"


@dataclass(frozen=True)
class FlowTemplate:
    src: str
    dst: str
    services: tuple[str, ...]
    schedule: str  # business, always, nightly
    base: int  # sessions per day on a normal day
    kind: str
    summary: str


@dataclass(frozen=True)
class AppTemplate:
    app_id: str
    name: str
    tiers: tuple[TierTemplate, ...]
    flows: tuple[FlowTemplate, ...]


def _t(name: str, count: int = 1, zone_role: str = "servers") -> TierTemplate:
    return TierTemplate(name, count, zone_role)


def _f(src, dst, services, schedule, base, kind, summary) -> FlowTemplate:
    return FlowTemplate(src, dst, tuple(services), schedule, base, kind, summary)


APPS = (
    AppTemplate(
        "crm",
        "Customer CRM",
        (_t("web", 2), _t("app"), _t("db")),
        (
            _f(
                "users",
                "web",
                ["junos-https"],
                "business",
                400,
                "app_access",
                "Office users reach the CRM web front end",
            ),
            _f(
                "web",
                "app",
                ["tcp-8080"],
                "business",
                900,
                "app_dependency",
                "CRM web servers call the CRM application server",
            ),
            _f(
                "app",
                "db",
                ["tcp-3306"],
                "business",
                1200,
                "app_dependency",
                "CRM application server queries its MySQL database",
            ),
        ),
    ),
    AppTemplate(
        "erp",
        "ERP",
        (_t("app", 2), _t("db")),
        (
            _f(
                "users",
                "app",
                ["junos-https"],
                "business",
                600,
                "app_access",
                "Office users reach the ERP application",
            ),
            _f(
                "app",
                "db",
                ["tcp-1521"],
                "always",
                1500,
                "app_dependency",
                "ERP application servers query the Oracle database",
            ),
        ),
    ),
    AppTemplate(
        "intranet",
        "Intranet portal",
        (_t("web"),),
        (
            _f(
                "users",
                "web",
                ["junos-http", "junos-https"],
                "business",
                800,
                "app_access",
                "Office users browse the intranet portal",
            ),
        ),
    ),
    AppTemplate(
        "hr",
        "HR portal",
        (_t("web"), _t("db")),
        (
            _f(
                "users",
                "web",
                ["junos-https"],
                "business",
                150,
                "app_access",
                "Office users reach the HR portal",
            ),
            _f(
                "web",
                "db",
                ["tcp-5432"],
                "business",
                300,
                "app_dependency",
                "HR portal queries its PostgreSQL database",
            ),
        ),
    ),
    AppTemplate(
        "files",
        "File server",
        (_t("file"),),
        (
            _f(
                "users",
                "file",
                ["tcp-445"],
                "business",
                1500,
                "app_access",
                "Office users map network drives on the file server",
            ),
        ),
    ),
    AppTemplate(
        "billing",
        "Billing",
        (_t("app"), _t("db")),
        (
            _f(
                "users",
                "app",
                ["junos-https"],
                "business",
                200,
                "app_access",
                "Finance users reach the billing application",
            ),
            _f(
                "app",
                "db",
                ["tcp-1433"],
                "business",
                500,
                "app_dependency",
                "Billing application queries its SQL Server database",
            ),
            _f(
                "app",
                "partner:bank-sftp",
                ["junos-ssh"],
                "nightly",
                1,
                "partner_access",
                "Billing uploads payment files to the bank SFTP server every night",
            ),
        ),
    ),
    AppTemplate(
        "webshop",
        "Public web shop",
        (_t("web", 2, "dmz"), _t("app")),
        (
            _f(
                "internet",
                "web",
                ["junos-https"],
                "always",
                2000,
                "app_access",
                "Internet customers reach the public web shop",
            ),
            _f(
                "web",
                "app",
                ["tcp-8443"],
                "always",
                1800,
                "app_dependency",
                "Web shop front ends call the order application server",
            ),
        ),
    ),
    AppTemplate(
        "mail",
        "Mail",
        (_t("relay", 1, "dmz"), _t("mbx")),
        (
            _f(
                "internet",
                "relay",
                ["junos-smtp"],
                "always",
                300,
                "app_access",
                "Inbound mail from the internet reaches the mail relay",
            ),
            _f(
                "relay",
                "mbx",
                ["junos-smtp"],
                "always",
                280,
                "app_dependency",
                "Mail relay forwards mail to the mailbox server",
            ),
            _f(
                "users",
                "mbx",
                ["tcp-993"],
                "business",
                700,
                "app_access",
                "Office users read mail over IMAPS",
            ),
        ),
    ),
    AppTemplate(
        "wiki",
        "Team wiki",
        (_t("web"),),
        (
            _f(
                "users",
                "web",
                ["junos-https"],
                "business",
                250,
                "app_access",
                "Office users edit the team wiki",
            ),
        ),
    ),
    AppTemplate(
        "servicedesk",
        "Service desk",
        (_t("web"), _t("db")),
        (
            _f(
                "users",
                "web",
                ["junos-https"],
                "business",
                300,
                "app_access",
                "Office users open service desk tickets",
            ),
            _f(
                "web",
                "db",
                ["tcp-3306"],
                "business",
                600,
                "app_dependency",
                "Service desk queries its MySQL database",
            ),
        ),
    ),
    AppTemplate(
        "payroll",
        "Payroll",
        (_t("app"),),
        (
            _f(
                "users",
                "app",
                ["junos-https"],
                "business",
                60,
                "app_access",
                "HR users reach the payroll application",
            ),
            _f(
                "app",
                "partner:payroll-provider",
                ["junos-https"],
                "business",
                40,
                "partner_access",
                "Payroll application exchanges data with the payroll provider",
            ),
        ),
    ),
    AppTemplate(
        "reporting",
        "Reporting",
        (_t("app"), _t("db")),
        (
            _f(
                "users",
                "app",
                ["junos-https"],
                "business",
                120,
                "app_access",
                "Managers open reports",
            ),
            _f(
                "app",
                "db",
                ["tcp-5432"],
                "business",
                400,
                "app_dependency",
                "Reporting application queries its PostgreSQL warehouse",
            ),
        ),
    ),
)

APPS = APPS + (
    AppTemplate(
        "lms",
        "Learning portal",
        (_t("web"),),
        (
            _f(
                "users",
                "web",
                ["junos-https"],
                "business",
                90,
                "app_access",
                "Employees follow mandatory training courses online",
            ),
        ),
    ),
    AppTemplate(
        "dms",
        "Document management",
        (_t("web"), _t("db")),
        (
            _f(
                "users",
                "web",
                ["junos-https"],
                "business",
                350,
                "app_access",
                "Staff store and search signed contracts",
            ),
            _f(
                "web",
                "db",
                ["tcp-1433"],
                "business",
                700,
                "app_dependency",
                "Contract archive keeps its index in SQL Server",
            ),
        ),
    ),
    AppTemplate(
        "pos",
        "Store point of sale backend",
        (_t("app"), _t("db")),
        (
            _f(
                "users",
                "app",
                ["tcp-8443"],
                "always",
                900,
                "app_access",
                "Shop tills send sales to the central backend",
            ),
            _f(
                "app",
                "db",
                ["tcp-5432"],
                "always",
                1100,
                "app_dependency",
                "Sales backend records transactions in PostgreSQL",
            ),
        ),
    ),
    AppTemplate(
        "wms",
        "Warehouse management",
        (_t("app", 2), _t("db")),
        (
            _f(
                "users",
                "app",
                ["junos-https"],
                "business",
                500,
                "app_access",
                "Warehouse staff scan pallets and pick orders",
            ),
            _f(
                "app",
                "db",
                ["tcp-1521"],
                "always",
                1300,
                "app_dependency",
                "Stock levels are kept in an Oracle schema",
            ),
        ),
    ),
    AppTemplate(
        "tms",
        "Transport management",
        (_t("app"),),
        (
            _f(
                "users",
                "app",
                ["junos-https"],
                "business",
                180,
                "app_access",
                "Dispatchers plan truck routes",
            ),
            _f(
                "app",
                "partner:carrier-api",
                ["junos-https"],
                "business",
                120,
                "partner_access",
                "Shipment bookings are pushed to the carrier API",
            ),
        ),
    ),
    AppTemplate(
        "gitlab",
        "Source control",
        (_t("web"),),
        (
            _f(
                "users",
                "web",
                ["junos-https", "junos-ssh"],
                "business",
                400,
                "app_access",
                "Developers push code and review merge requests",
            ),
        ),
    ),
    AppTemplate(
        "ci",
        "Build servers",
        (_t("app", 2),),
        (
            _f(
                "users",
                "app",
                ["junos-https"],
                "business",
                150,
                "app_access",
                "Developers trigger pipelines and read build results",
            ),
            _f(
                "app",
                "partner:package-mirror",
                ["junos-https"],
                "always",
                600,
                "internet_access",
                "Build agents download libraries from a package mirror",
            ),
        ),
    ),
    AppTemplate(
        "edi",
        "EDI gateway",
        (_t("gw", 1, "dmz"), _t("db")),
        (
            _f(
                "partner:edi-partner",
                "gw",
                ["junos-ssh"],
                "nightly",
                4,
                "partner_access",
                "A retail customer drops purchase orders every night",
            ),
            _f(
                "gw",
                "db",
                ["tcp-5432"],
                "always",
                200,
                "app_dependency",
                "Received orders are queued in a PostgreSQL table",
            ),
        ),
    ),
)

SHARED = (
    AppTemplate(
        "shared-dns",
        "Internal DNS",
        (_t("dns", 2),),
        (
            _f(
                "users",
                "dns",
                ["junos-dns-udp"],
                "business",
                3000,
                "shared_service",
                "Office users resolve names with the internal DNS servers",
            ),
            _f(
                "servers-net",
                "dns",
                ["junos-dns-udp"],
                "always",
                2000,
                "shared_service",
                "Servers resolve names with the internal DNS servers",
            ),
        ),
    ),
    AppTemplate(
        "shared-ntp",
        "Time synchronization",
        (),
        (
            _f(
                "servers-net",
                "partner:ntp-pool",
                ["junos-ntp"],
                "always",
                96,
                "shared_service",
                "Servers synchronize time with an external NTP server",
            ),
        ),
    ),
    AppTemplate(
        "shared-internet",
        "Web browsing",
        (),
        (
            _f(
                "users",
                "internet",
                ["junos-http", "junos-https"],
                "business",
                5000,
                "internet_access",
                "Office users browse the internet",
            ),
        ),
    ),
    AppTemplate(
        "shared-backup",
        "Backup",
        (_t("bkp"),),
        (
            _f(
                "bkp",
                "servers-net",
                ["tcp-10000"],
                "nightly",
                3,
                "backup",
                "Backup server pulls nightly backups from all servers",
            ),
        ),
    ),
    AppTemplate(
        "shared-monitoring",
        "Monitoring",
        (_t("mon"),),
        (
            _f(
                "mon",
                "servers-net",
                ["udp-161"],
                "always",
                288,
                "monitoring",
                "Monitoring server polls all servers over SNMP",
            ),
        ),
    ),
)

PREDEFINED_APPLICATIONS = {
    "junos-http": ("tcp", 80),
    "junos-https": ("tcp", 443),
    "junos-ssh": ("tcp", 22),
    "junos-smtp": ("tcp", 25),
    "junos-dns-udp": ("udp", 53),
    # Unverified (VSRX-12b): the junos-defaults sample does not list it and the
    # documentation gives NTP port 123 without the `junos-` name. Kept until a
    # capture settles it.
    "junos-ntp": ("udp", 123),
}


def service_port(name: str) -> tuple[str, int]:
    """Protocol and port of a predefined (junos-*) or custom (tcp-8080) application."""
    if name in PREDEFINED_APPLICATIONS:
        return PREDEFINED_APPLICATIONS[name]
    protocol, port = name.split("-")
    return protocol, int(port)


PARTNERS = {
    "bank-sftp": "203.0.113.25",
    "payroll-provider": "203.0.113.80",
    "ntp-pool": "198.51.100.123",
    "carrier-api": "203.0.113.140",
    "package-mirror": "198.51.100.200",
    "edi-partner": "203.0.113.60",
}

FIRST_NAMES = (
    "Alma",
    "Bruno",
    "Chiara",
    "Dmitri",
    "Elif",
    "Farid",
    "Greta",
    "Hugo",
    "Ines",
    "Jonas",
    "Kaori",
    "Lucas",
    "Mirela",
    "Nadia",
    "Oskar",
    "Priya",
    "Quentin",
    "Rosa",
)
LAST_NAMES = (
    "Albescu",
    "Brandt",
    "Carvalho",
    "Duval",
    "Eriksen",
    "Ferrante",
    "Gallo",
    "Haddad",
    "Ivanova",
    "Jansen",
    "Kowal",
    "Lindqvist",
    "Moreau",
    "Novak",
    "Ortega",
    "Petrov",
)
TEAMS = ("Sales IT", "Finance IT", "HR IT", "Digital", "Workplace", "Infrastructure")

ZONE_STYLES = (
    {"users": "trust", "internet": "untrust", "dmz": "dmz", "servers": "servers"},
    {"users": "users", "internet": "internet", "dmz": "dmz", "servers": "dc"},
)

INTERFACES = {
    "internet": ("ge-0/0/0", "192.0.2.1/24"),
    "users": ("ge-0/0/1", "10.10.0.1/16"),
    "dmz": ("ge-0/0/2", "172.16.10.1/24"),
    "servers": ("ge-0/0/3", "10.20.0.1/15"),
}

SITE_NAMES = ("hq", "branch1", "branch2", "branch3")

JUNOS_VERSIONS = ("20.4R3-S2", "21.4R3-S4")

# ---------------------------------------------------------------- Medium only
# Kept out of APPS, SHARED, ZONE_STYLES and INTERFACES' Easy roles so the Easy
# draws (sample of APPS, choice of zone style) do not change.

EXTRA_APPS = (
    AppTemplate(
        "bi",
        "Business intelligence",
        (_t("web"), _t("db")),
        (
            _f(
                "users",
                "web",
                ["junos-https"],
                "business",
                140,
                "app_access",
                "Office users open the BI dashboards",
            ),
            _f(
                "web",
                "db",
                ["tcp-5432"],
                "business",
                350,
                "app_dependency",
                "BI dashboards read the warehouse database",
            ),
        ),
    ),
    AppTemplate(
        "telephony",
        "IP telephony",
        (_t("app", 2),),
        (
            _f(
                "users",
                "app",
                ["udp-5060"],
                "business",
                900,
                "app_access",
                "Desk phones register with the call managers",
            ),
        ),
    ),
    AppTemplate(
        "badge",
        "Physical access control",
        (_t("app"), _t("db")),
        (
            _f(
                "users",
                "app",
                ["tcp-8443"],
                "business",
                40,
                "app_access",
                "Security staff manage badges in the access control console",
            ),
            _f(
                "app",
                "db",
                ["tcp-1433"],
                "always",
                300,
                "app_dependency",
                "Access control server stores badge events in SQL Server",
            ),
        ),
    ),
    AppTemplate(
        "print",
        "Print management",
        (_t("app"),),
        (
            _f(
                "users",
                "app",
                ["tcp-9100"],
                "business",
                600,
                "app_access",
                "Workstations send print jobs to the print server",
            ),
        ),
    ),
    AppTemplate(
        "vault",
        "Secrets vault",
        (_t("app", 2),),
        (
            _f(
                "servers-net",
                "app",
                ["tcp-8200"],
                "always",
                700,
                "shared_service",
                "Application servers fetch secrets from the vault cluster",
            ),
        ),
    ),
    AppTemplate(
        "apigw",
        "Partner API gateway",
        (_t("gw", 1, "dmz"), _t("app")),
        (
            _f(
                "internet",
                "gw",
                ["junos-https"],
                "always",
                900,
                "app_access",
                "Partners call the public API gateway",
            ),
            _f(
                "gw",
                "app",
                ["tcp-8080"],
                "always",
                850,
                "app_dependency",
                "API gateway forwards calls to the order service",
            ),
        ),
    ),
    AppTemplate(
        "archive",
        "Document archive",
        (_t("file"), _t("db")),
        (
            _f(
                "users",
                "file",
                ["tcp-445"],
                "business",
                220,
                "app_access",
                "Office users read archived documents from the archive share",
            ),
            _f(
                "file",
                "db",
                ["tcp-5432"],
                "business",
                160,
                "app_dependency",
                "Archive file server indexes documents in its database",
            ),
        ),
    ),
)

SHARED_MEDIUM = (
    AppTemplate(
        "shared-jump",
        "Admin jump hosts",
        (_t("jump", 2, "management"),),
        (
            _f(
                "users",
                "jump",
                ["junos-ssh"],
                "business",
                60,
                "management",
                "IT staff open sessions on the jump hosts",
            ),
            _f(
                "jump",
                "servers-net",
                ["junos-ssh"],
                "business",
                250,
                "management",
                "Administrators reach servers over SSH from the jump hosts",
            ),
        ),
    ),
)

# Shared services that live in the management zone at Medium (zone count 5).
MANAGEMENT_APPS = ("shared-monitoring", "shared-backup", "shared-jump")

MANAGEMENT_NAMES = ("mgmt", "admin")
INTERFACES = INTERFACES | {"management": ("ge-0/0/4", "10.30.0.1/24")}

# Scheduled jobs added to applications at Medium. `src` is filled with one of
# the application's server tiers; `dst` with a partner the application does
# not already reach with that service. The period and the day of the run are
# drawn per scenario (world.py).
JOB_KINDS = {
    "weekly": (
        "junos-ssh",
        2,
        "partner_access",
        "Weekly export file pushed to an external partner",
    ),
    "quarterly": (
        "junos-https",
        3,
        "partner_access",
        "Quarter-end figures uploaded to an external partner",
    ),
    "yearly": (
        "junos-ssh",
        1,
        "partner_access",
        "Year-end archive transferred to an external partner",
    ),
}
JOB_PERIODS = {"weekly": 7, "quarterly": 91, "yearly": 365}
JOB_PARTNERS = ("bank-sftp", "payroll-provider", "carrier-api", "edi-partner")
