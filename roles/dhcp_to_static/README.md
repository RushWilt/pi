# rushwilt.pi.dhcp_to_static

Detects the interfaces whose configuration was issued by a DHCP server and
rewrites them as **static**, keeping the currently assigned IPv4 address and
prefix, the default gateway, and the DNS and NTP servers. Hosts that are not
DHCP-managed come back as a clean no-op; re-running on converted interfaces
is a no-op.

## Supported setups

| OS                      | Backends                     |
|-------------------------|------------------------------|
| Debian 12/13            | ifupdown, NetworkManager     |
| Ubuntu 24.04/26.04      | netplan, NetworkManager      |
| Raspberry Pi OS (Debian-based) | dhcpcd               |

Detection is per interface and based on live state, not on what the
configuration *claims*:

- leases from the kernel (`ip -j addr`, `ip -j route table main`),
- DNS servers and search domains from `/etc/resolv.conf`,
- NTP servers from the running `systemd-timesyncd` (bus property
  `LinkNTPServers`),
- backend ownership from the netplan documents (`/etc/netplan/*.y*ml`),
  `/etc/network/interfaces`, an enabled `dhcpcd` service plus
  `/etc/dhcpcd.conf`, and the active NetworkManager connections
  (`nmcli ... connection show --active`, per-connection `ipv4.method`).

An interface is converted only if a supported backend is the one handing it
to DHCP; a leased interface with no recognised backend is reported and left
alone.

## Requirements

- `ansible-core >= 2.20`
- Debian 12 or later / Ubuntu 24.04 or later / the current Debian-based
  Raspberry Pi OS (asserted at run time)
- `become: true`
- check mode (`--check`) is refused: the role rewrites the configuration and
  then verifies the live result, so it cannot be previewed.

## Role variables

| Variable                   | Default                                          | Purpose                                                                    |
|----------------------------|--------------------------------------------------|----------------------------------------------------------------------------|
| `dhcp_to_static_exclude`   | `^(lo\|docker\|veth\|virbr\|tap\|br-\|vcan\|dummy\|kube\|cni\|flannel)` | regex matched against interface names that must never be converted |
| `dhcp_to_static_min_debian`| `[12]`                                           | minimum supported Debian version                                           |
| `dhcp_to_static_min_ubuntu`| `[24, 4]`                                        | minimum supported Ubuntu version                                           |

## Usage

```yaml
- hosts: pi5
  become: true
  roles:
    - rushwilt.pi.dhcp_to_static
```

The play ends by reporting each converted interface, e.g.
`eth0 -> static 192.168.11.230/24, gateway 192.168.11.254 [ifupdown]`.

## What gets written

- **netplan** (Ubuntu): the target stanzas in the existing
  `/etc/netplan/*.y*ml` file(s) become static (`dhcp4: false`,
  `addresses`, `routes`, `nameservers`), then `netplan apply`.
- **ifupdown** (Debian): `iface <if> inet dhcp` stanzas in
  `/etc/network/interfaces` become `inet static` stanzas, then the
  `networking` service restarts.
- **dhcpcd** (Raspberry Pi OS): a static stanza for the interface is added
  to `/etc/dhcpcd.conf`, then `dhcpcd` restarts.
- **NetworkManager** (desktop): a static keyfile connection
  (`rushwilt-<iface>`) is written and activated with `nmcli`.
- **NTP**: the DHCP-provided NTP servers are pinned into the
  `systemd-timesyncd` drop-in `/etc/systemd/timesyncd.conf.d/rushwilt-dhcp-to-static.conf`
  (with `backup: true`) and the service restarted — NTP otherwise travels in
  the DHCP lease and would be lost when the interfaces go static.

After applying, the role re-reads the live kernel state and asserts that each
converted interface still has the same address, prefix and gateway and is no
longer dynamically configured.

## Notes

- The converted address is the one the DHCP server just handed out. Where the
  pool is managed, keep that address reserved for the host.
- `plugins/filters/dhcp_to_static.py` at the collection root (`lease_index`,
  `ifupdown_static`, `nm_keyfile`, ...) implements the backend rewrites. It is
  an internal helper; the tasks reference it by qualified name (`rushwilt.pi.lease_index`, ...).

## License

Apache-2.0 — see the file headers.
