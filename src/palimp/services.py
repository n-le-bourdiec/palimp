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
