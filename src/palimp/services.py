"""Plain service names for Junos predefined applications and well-known ports (T4).

T4 is contextual inference: a port says what a flow probably is, never why
the rule exists. These tables only name the service.

Predefined applications (session 28, VSRX-12): the definitions of
tests/fixtures/junos_docs/junos_defaults_applications_full_13.2.txt (the
applications of `show groups junos-defaults`, Junos 13.2 documentation), the
names its application sets list with ports from
predefined_applications_table.txt (the predefined applications page), then a
few usual junos-defaults names the documentation does not show, to confirm
on a real vSRX.
"""

from palimp.models import Application

PREDEFINED: dict[str, tuple[str, str]] = {
    # Defined in junos_defaults_applications_full_13.2.txt.
    "junos-ftp": ("FTP", "tcp/21"),
    "junos-tftp": ("TFTP", "udp/69"),
    "junos-rpc-portmap-tcp": ("RPC port mapper", "tcp/111"),
    "junos-rpc-portmap-udp": ("RPC port mapper", "udp/111"),
    "junos-ip": ("any IP protocol", "ip"),
    "junos-rexec": ("remote exec", "tcp/512"),
    "junos-rlogin": ("remote login", "tcp/513"),
    "junos-rsh": ("remote shell", "tcp/514"),
    "junos-rtsp": ("RTSP streaming", "tcp/554"),
    "junos-sqlnet": ("Oracle database", "tcp/1521"),
    "junos-traceroute": ("traceroute", "udp/33435-33450"),
    "junos-traceroute-ttl-1": ("traceroute", "udp/33435-33450"),
    "junos-rpc-services-udp": ("Sun RPC services", "udp/rpc"),
    "junos-rpc-services-tcp": ("Sun RPC services", "tcp/rpc"),
    "junos-icmp-all": ("ICMP", "icmp"),
    "junos-icmp-ping": ("ICMP ping", "icmp"),
    "junos-netshow": ("Windows Media (NetShow)", "tcp/1755"),
    "junos-netbios-name-udp": ("NetBIOS name service", "udp/137"),
    "junos-netbios-name-tcp": ("NetBIOS name service", "tcp/137"),
    "junos-netbios-datagram": ("NetBIOS datagram", "udp/138"),
    "junos-netbios-session": ("NetBIOS session", "tcp/139"),
    "junos-dce-rpc-portmap": ("Microsoft RPC endpoint mapper", "tcp/135"),
    "junos-dcerpc-endpoint-mapper-service": ("Microsoft RPC endpoint mapper", "tcp/rpc"),
    "junos-ssh": ("SSH", "tcp/22"),
    "junos-telnet": ("Telnet", "tcp/23"),
    "junos-smtp": ("SMTP mail", "tcp/25"),
    "junos-dns-udp": ("DNS", "udp/53"),
    "junos-dns-tcp": ("DNS", "tcp/53"),
    "junos-tacacs": ("TACACS authentication", "tcp/49"),
    "junos-tacacs-ds": ("TACACS database service", "tcp/65"),
    "junos-dhcp-client": ("DHCP", "udp/68"),
    "junos-dhcp-server": ("DHCP", "udp/67"),
    "junos-bootpc": ("DHCP", "udp/68"),
    "junos-bootps": ("DHCP", "udp/67"),
    "junos-http": ("HTTP", "tcp/80"),
    "junos-https": ("HTTPS", "tcp/443"),
    # Listed in the application sets of that page; ports from the predefined
    # applications page (SNMP 161), else general knowledge.
    "junos-snmp-get": ("SNMP polling", "udp/161"),
    "junos-snmp-get-next": ("SNMP polling", "udp/161"),
    "junos-snmp-response": ("SNMP polling", "udp/161"),
    "junos-snmp-trap": ("SNMP traps", "udp/162"),
    "junos-xnm-ssl": ("Junos XML management over TLS", "tcp/3220"),
    "junos-xnm-clear-text": ("Junos XML management", "tcp/3221"),
    "junos-dcerpc-msexchange-directory-rfr": ("Microsoft Exchange", "tcp/rpc"),
    "junos-dcerpc-msexchange-information-store": ("Microsoft Exchange", "tcp/rpc"),
    "junos-dcerpc-msexchange-directory-nsp": ("Microsoft Exchange", "tcp/rpc"),
    # Usual junos-defaults names, not in the documentation samples (unverified).
    "junos-pop3": ("POP3 mail", "tcp/110"),
    "junos-imap": ("IMAP mail", "tcp/143"),
    "junos-imaps": ("IMAP mail over TLS", "tcp/993"),
    "junos-ntp": ("NTP time sync", "udp/123"),
    "junos-syslog": ("syslog", "udp/514"),
    "junos-ldap": ("LDAP directory", "tcp/389"),
    "junos-radius": ("RADIUS authentication", "udp/1812"),
    "junos-bgp": ("BGP routing", "tcp/179"),
    "junos-ike": ("IPsec IKE", "udp/500"),
    "junos-ping": ("ICMP ping", "icmp"),
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
    # Well-known product ports (session 28).
    "tcp/902": "VMware ESXi management",
    "tcp/1080": "SOCKS proxy",
    "tcp/3128": "HTTP proxy",
    "tcp/3200": "SAP dispatcher",
    "tcp/3300": "SAP gateway",
    "tcp/5601": "Kibana",
    "tcp/5666": "Nagios NRPE agent",
    "tcp/8089": "Splunk management",
    "tcp/8140": "Puppet server",
    "tcp/8834": "Nessus scanner",
    "tcp/9997": "Splunk forwarder",
    "tcp/10051": "Zabbix server",
    "tcp/15672": "RabbitMQ management",
    "tcp/26379": "Redis Sentinel",
}

# Names a well-known port stands for (session 28, decision 0043): a product
# (`tcp/8834` is nessus) or a service a server role offers (`udp/53` is dns). A
# port alone never names the application of a rule (T4); with an object naming
# the same product, or a server role offering the same service, it is a second
# source. The first name is the one the intent uses.
PORT_NAMES: dict[str, tuple[str, ...]] = {
    "tcp/8834": ("nessus", "tenable"),
    "tcp/6379": ("redis",),
    "tcp/26379": ("redis",),
    "tcp/1521": ("oracle",),
    "tcp/3200": ("sap",),
    "tcp/3300": ("sap",),
    "tcp/9200": ("elasticsearch", "elastic"),
    "tcp/5601": ("kibana",),
    "tcp/27017": ("mongodb", "mongo"),
    "tcp/5432": ("postgresql", "postgres"),
    "tcp/3306": ("mysql", "mariadb"),
    "tcp/1433": ("mssql",),
    "tcp/9092": ("kafka",),
    "tcp/10050": ("zabbix",),
    "tcp/10051": ("zabbix",),
    "tcp/8200": ("vault",),
    "tcp/8089": ("splunk",),
    "tcp/9997": ("splunk",),
    "tcp/5666": ("nagios",),
    "tcp/902": ("vmware", "esxi"),
    "tcp/8140": ("puppet",),
    "tcp/5672": ("rabbitmq",),
    "tcp/15672": ("rabbitmq",),
    "udp/53": ("dns",),
    "tcp/53": ("dns",),
    "udp/123": ("ntp",),
    "tcp/3128": ("proxy",),
    "tcp/1080": ("proxy",),
    "tcp/25": ("smtp",),
    "tcp/465": ("smtp",),
    "tcp/587": ("smtp",),
    "tcp/389": ("ldap",),
    "tcp/636": ("ldap",),
    "tcp/3268": ("ldap",),
    "tcp/88": ("kerberos",),
    "udp/88": ("kerberos",),
    "udp/1812": ("radius",),
    "udp/514": ("syslog",),
    "tcp/514": ("syslog",),
    "udp/161": ("snmp",),
    "udp/162": ("snmp",),
    "tcp/21": ("ftp",),
    "tcp/990": ("ftp",),
    "tcp/445": ("smb",),
    "tcp/2049": ("nfs",),
    "tcp/10000": ("ndmp",),
}
# Server roles (palimp.apps labels) and the services they offer: a role that
# matches the port names that service as the application (`dns-01` on udp/53).
# Only services that are an application of their own. A database engine, a file,
# backup or mail transfer protocol is a part of some business application:
# `srv-db-01` on tcp/1433 says SQL Server, not which application uses it, so the
# intent describes the flow and names none (session 33, decision 0048).
ROLE_SERVICES: dict[str, frozenset[str]] = {
    "DNS": frozenset({"dns"}),
    "NTP": frozenset({"ntp"}),
    "proxy": frozenset({"proxy"}),
    "directory": frozenset({"ldap", "kerberos"}),
    "RADIUS": frozenset({"radius"}),
    "log": frozenset({"syslog", "splunk"}),
    "monitoring": frozenset({"snmp", "zabbix", "nagios"}),
    "FTP": frozenset({"ftp"}),
}


def describe(name: str, applications: dict[str, Application], depth: int = 0) -> list[str]:
    """Plain description of one application (or set) referenced by a policy."""
    if name == "any":
        return ["any: any application, no service restriction (nothing to infer)"]
    if name in PREDEFINED:
        service, port = PREDEFINED[name]
        return [f"{name}: {service} ({port}, Junos predefined application)"]
    if name == "junos-defaults":
        return [f"{name}: the default ports of the dynamic applications matched (DYNAPP-1)"]
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
    lines = []
    for number, (protocol, destination) in enumerate(app.ports()):
        label = f"{name} term {app.terms[number].name}" if app.terms else name
        port = f"{protocol or '?'}/{destination}" if destination else ""
        if not port:
            lines.append(f"{label}: custom application, protocol {protocol or 'unknown'}")
        elif (service := WELL_KNOWN.get(port)) is None:
            lines.append(f"{label}: {port}, no well-known service on this port")
        else:
            lines.append(f"{label}: {service} ({port}, custom application)")
    return lines


def service_names(name: str, applications: dict[str, Application], depth: int = 0) -> list[str]:
    """Plain names of the well-known services behind one application (or set): `SMB file
    sharing` for junos-smb. Empty for `any` and for ports with no well-known service."""
    if name in PREDEFINED:
        return [PREDEFINED[name][0]]
    app = applications.get(name)
    if app is None:
        return []
    if app.kind == "application_set":
        if depth > 3:
            return []
        found = [s for m in app.members for s in service_names(m, applications, depth + 1)]
        return list(dict.fromkeys(found))
    found = [WELL_KNOWN.get(f"{p or '?'}/{d}") for p, d in app.ports() if d]
    return list(dict.fromkeys(s for s in found if s))


def port_names(name: str, applications: dict[str, Application], depth: int = 0) -> list[str]:
    """PORT_NAMES of the ports behind one application (or set): `nessus` for a custom
    application on tcp/8834. Each entry is the first name of its port."""
    if name in PREDEFINED:
        names = PORT_NAMES.get(PREDEFINED[name][1])
        return [names[0]] if names else []
    app = applications.get(name)
    if app is None:
        return []
    if app.kind == "application_set":
        if depth > 3:
            return []
        found = [n for m in app.members for n in port_names(m, applications, depth + 1)]
        return list(dict.fromkeys(found))
    found = [PORT_NAMES.get(f"{p or '?'}/{d}") for p, d in app.ports() if d]
    return list(dict.fromkeys(n[0] for n in found if n))


def aliases(name: str) -> frozenset[str]:
    """Every name a port name goes by (`postgresql` and `postgres`)."""
    for names in PORT_NAMES.values():
        if name in names:
            return frozenset(names)
    return frozenset({name})


# Service families (session 28, decision 0043): what a policy name may say about the
# service it is for, and the ports of each family. A name naming a family that no
# matched application belongs to contradicts the match ("ALLOW-SNMP" on junos-https).
FAMILY_PORTS: dict[str, frozenset[str]] = {
    "SNMP": frozenset({"udp/161", "udp/162", "tcp/161", "tcp/162"}),
    "SSH": frozenset({"tcp/22"}),
    "Telnet": frozenset({"tcp/23"}),
    "RDP": frozenset({"tcp/3389", "udp/3389"}),
    "web": frozenset({"tcp/80", "tcp/443", "tcp/8080", "tcp/8443", "udp/443"}),
    "DNS": frozenset({"udp/53", "tcp/53"}),
    "NTP": frozenset({"udp/123"}),
    "mail": frozenset({"tcp/25", "tcp/465", "tcp/587", "tcp/110", "tcp/143", "tcp/993", "tcp/995"}),
    "LDAP": frozenset({"tcp/389", "tcp/636", "tcp/3268", "udp/389"}),
    "syslog": frozenset({"udp/514", "tcp/514", "tcp/6514"}),
    "ICMP": frozenset({"icmp"}),
    "FTP": frozenset({"tcp/20", "tcp/21", "tcp/990", "tcp/22"}),
    "TFTP": frozenset({"udp/69"}),
    "SMB": frozenset({"tcp/445", "tcp/139", "udp/137", "udp/138", "tcp/137"}),
    "RADIUS": frozenset({"udp/1812", "udp/1813", "udp/1645", "udp/1646"}),
    "NFS": frozenset({"tcp/2049", "udp/2049", "tcp/111", "udp/111"}),
    "Kerberos": frozenset({"tcp/88", "udp/88"}),
    "BGP": frozenset({"tcp/179"}),
    "VNC": frozenset({"tcp/5900", "tcp/5800"}),
}
# Words of a policy name that name a family. `web` and `mail` are server roles,
# not service names, and are left out.
NAME_FAMILIES: dict[str, str] = {
    "snmp": "SNMP",
    "ssh": "SSH",
    "sftp": "FTP",
    "scp": "SSH",
    "telnet": "Telnet",
    "rdp": "RDP",
    "http": "web",
    "https": "web",
    "dns": "DNS",
    "ntp": "NTP",
    "smtp": "mail",
    "imap": "mail",
    "pop3": "mail",
    "ldap": "LDAP",
    "ldaps": "LDAP",
    "syslog": "syslog",
    "icmp": "ICMP",
    "ping": "ICMP",
    "ftp": "FTP",
    "tftp": "TFTP",
    "smb": "SMB",
    "cifs": "SMB",
    "radius": "RADIUS",
    "nfs": "NFS",
    "kerberos": "Kerberos",
    "bgp": "BGP",
    "vnc": "VNC",
}


def families(name: str, applications: dict[str, Application], depth: int = 0) -> set[str] | None:
    """Service families of one application (or set). None when one port is not known
    (`any`, a custom port in no family, an undefined name): nothing can be compared."""
    if name in PREDEFINED:
        ports = [PREDEFINED[name][1]]
    else:
        app = applications.get(name)
        if app is None:
            return None
        if app.kind == "application_set":
            if depth > 3:
                return None
            found: set[str] = set()
            for member in app.members:
                part = families(member, applications, depth + 1)
                if part is None:
                    return None
                found |= part
            return found
        ports = [f"{p or '?'}/{d}" if d else (p or "?") for p, d in app.ports()]
    found = set()
    for port in ports:
        part = {f for f, known in FAMILY_PORTS.items() if port in known}
        if not part:
            return None
        found |= part
    return found
