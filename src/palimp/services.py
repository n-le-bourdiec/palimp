"""Plain service names for Junos predefined applications and well-known ports (T4).

T4 is contextual inference: a port says what a flow probably is, never why
the rule exists. These tables only name the service.

Predefined applications: the five in tests/fixtures/junos_docs/
junos_defaults_applications_13.2.txt are documented (VSRX-12); the others are
the usual junos-defaults definitions, to confirm on a real vSRX.
"""

from palimp.models import Application

PREDEFINED: dict[str, tuple[str, str]] = {
    "junos-ssh": ("SSH", "tcp/22"),
    "junos-telnet": ("Telnet", "tcp/23"),
    "junos-ftp": ("FTP", "tcp/21"),
    "junos-tftp": ("TFTP", "udp/69"),
    "junos-smtp": ("SMTP mail", "tcp/25"),
    "junos-pop3": ("POP3 mail", "tcp/110"),
    "junos-imap": ("IMAP mail", "tcp/143"),
    "junos-imaps": ("IMAP mail over TLS", "tcp/993"),
    "junos-http": ("HTTP", "tcp/80"),
    "junos-https": ("HTTPS", "tcp/443"),
    "junos-dns-udp": ("DNS", "udp/53"),
    "junos-dns-tcp": ("DNS", "tcp/53"),
    "junos-ntp": ("NTP time sync", "udp/123"),
    "junos-snmp-get": ("SNMP polling", "udp/161"),
    "junos-snmp-trap": ("SNMP traps", "udp/162"),
    "junos-syslog": ("syslog", "udp/514"),
    "junos-ldap": ("LDAP directory", "tcp/389"),
    "junos-radius": ("RADIUS authentication", "udp/1812"),
    "junos-bgp": ("BGP routing", "tcp/179"),
    "junos-ike": ("IPsec IKE", "udp/500"),
    "junos-ping": ("ICMP ping", "icmp"),
    "junos-icmp-all": ("ICMP", "icmp"),
    "junos-ms-sql": ("Microsoft SQL Server", "tcp/1433"),
    "junos-sqlnet-v2": ("Oracle database", "tcp/1521"),
    "junos-sip": ("SIP voice signaling", "udp/5060"),
    "junos-smb": ("SMB file sharing", "tcp/445"),
}

WELL_KNOWN: dict[str, str] = {
    "tcp/20": "FTP data",
    "tcp/21": "FTP",
    "tcp/22": "SSH",
    "tcp/23": "Telnet",
    "tcp/25": "SMTP mail",
    "udp/53": "DNS",
    "tcp/53": "DNS",
    "udp/67": "DHCP",
    "udp/69": "TFTP",
    "tcp/80": "HTTP",
    "tcp/88": "Kerberos",
    "udp/88": "Kerberos",
    "tcp/110": "POP3 mail",
    "udp/123": "NTP time sync",
    "tcp/135": "Microsoft RPC",
    "tcp/139": "NetBIOS session",
    "tcp/143": "IMAP mail",
    "udp/161": "SNMP polling",
    "udp/162": "SNMP traps",
    "tcp/179": "BGP routing",
    "tcp/389": "LDAP directory",
    "tcp/443": "HTTPS",
    "tcp/445": "SMB file sharing",
    "tcp/465": "SMTP mail over TLS",
    "udp/500": "IPsec IKE",
    "udp/514": "syslog",
    "tcp/514": "syslog",
    "tcp/587": "SMTP mail submission",
    "tcp/636": "LDAP over TLS",
    "tcp/873": "rsync",
    "tcp/990": "FTP over TLS",
    "tcp/993": "IMAP mail over TLS",
    "tcp/995": "POP3 mail over TLS",
    "tcp/1433": "Microsoft SQL Server",
    "tcp/1521": "Oracle database",
    "udp/1812": "RADIUS authentication",
    "tcp/2049": "NFS",
    "tcp/3268": "Active Directory global catalog",
    "tcp/3306": "MySQL database",
    "tcp/3389": "RDP remote desktop",
    "tcp/5060": "SIP voice signaling",
    "udp/5060": "SIP voice signaling",
    "tcp/5432": "PostgreSQL database",
    "tcp/5672": "AMQP message queue",
    "tcp/5900": "VNC remote desktop",
    "tcp/5985": "WinRM remote management",
    "tcp/5986": "WinRM remote management over TLS",
    "tcp/6379": "Redis",
    "tcp/8080": "HTTP alternate (proxy or application server)",
    "tcp/8200": "HashiCorp Vault",
    "tcp/8443": "HTTPS alternate (application server)",
    "tcp/9092": "Kafka",
    "tcp/9100": "raw printing (JetDirect) or Prometheus node exporter",
    "tcp/9200": "Elasticsearch",
    "tcp/10000": "NDMP backup",
    "tcp/10050": "Zabbix agent",
    "tcp/27017": "MongoDB",
}


def describe(name: str, applications: dict[str, Application], depth: int = 0) -> list[str]:
    """Plain description of one application (or set) referenced by a policy."""
    if name == "any":
        return ["any: any application, no service restriction (nothing to infer)"]
    if name in PREDEFINED:
        service, port = PREDEFINED[name]
        return [f"{name}: {service} ({port}, Junos predefined application)"]
    app = applications.get(name)
    if app is None:
        if name.startswith("junos-"):
            return [f"{name}: Junos predefined application, not in palimp's service table"]
        return [f"{name}: not defined in config.set"]
    if app.kind == "application_set":
        if depth > 3:
            return [f"{name}: application set (nesting too deep)"]
        return [
            line for member in app.members for line in describe(member, applications, depth + 1)
        ]
    port = f"{app.protocol or '?'}/{app.destination_port}" if app.destination_port else ""
    if not port:
        return [f"{name}: custom application, protocol {app.protocol or 'unknown'}"]
    service = WELL_KNOWN.get(port)
    if service is None:
        return [f"{name}: {port}, no well-known service on this port"]
    return [f"{name}: {service} ({port}, custom application)"]
