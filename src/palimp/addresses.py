"""Address classes: which IP addresses are public (decision 0030).

Private or reserved means inside a special-purpose range of RFC 6890 and its
updates: RFC 1918 private networks, shared address space (RFC 6598),
loopback, link-local, multicast, "this network", benchmarking, IETF protocol
assignments, future use and broadcast; for IPv6 unique local, link-local,
multicast, loopback, unspecified, IPv4-mapped and discard-only addresses.

Documentation ranges (192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24,
2001:db8::/32) are counted as public: examples, documentation and synthetic
test data use them for internet hosts, never for internal networks.
"""

import ipaddress

Network = ipaddress.IPv4Network | ipaddress.IPv6Network

NON_PUBLIC: tuple[Network, ...] = tuple(
    ipaddress.ip_network(text)
    for text in (
        "0.0.0.0/8",
        "10.0.0.0/8",
        "100.64.0.0/10",
        "127.0.0.0/8",
        "169.254.0.0/16",
        "172.16.0.0/12",
        "192.0.0.0/24",
        "192.168.0.0/16",
        "198.18.0.0/15",
        "224.0.0.0/4",
        "240.0.0.0/4",
        "::/128",
        "::1/128",
        "::ffff:0:0/96",
        "100::/64",
        "fc00::/7",
        "fe80::/10",
        "ff00::/8",
    )
)


def special_range(network: Network) -> Network | None:
    """The private or reserved range that holds the whole network, if any."""
    for special in NON_PUBLIC:
        if special.version == network.version and network.subnet_of(special):  # type: ignore[arg-type]
            return special
    return None


def is_public(network: Network) -> bool:
    """True when the network is not inside a private or reserved range.

    A network larger than a reserved range that contains it (0.0.0.0/0) is
    public: it includes internet addresses.
    """
    return special_range(network) is None


def parse(value: str) -> Network | None:
    """An address object value (`10.1.2.0/24`, `192.0.2.7`) as a network, or None."""
    try:
        return ipaddress.ip_network(value.split()[0], strict=False)
    except (ValueError, IndexError):
        return None
