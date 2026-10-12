# SPDX-License-Identifier: Apache-2.0
"""Filters for rushwilt.pi.dhcp_to_static.

Pure-Python helpers that turn raw `ip` JSON, /etc/resolv.conf text, netplan
documents and ifupdown files into the static configurations this role writes.
"""

import copy
import ipaddress
import re

NETPLAN_SECTIONS = ('ethernets', 'wifis', 'bonds', 'bridges', 'vlans')
IFACE_DHCP_RE = re.compile(r'^\s*iface\s+(\S+)\s+inet\s+dhcp\s*$')


def lease_index(devices, routes):
    """Index the live IPv4 state by interface name.

    ``devices`` is the JSON list from ``ip -j -4 addr show`` and ``routes``
    the JSON list from ``ip -j route show table main``.  Returns
    ``{iface: {address, prefix, broadcast, gateway, dynamic}}`` for every
    interface with a usable lease; ``gateway`` is set only on the interface
    that owns the preferred default route and ``dynamic`` mirrors the kernel's
    DHCP flag (true while the address was issued by a DHCP server).
    """
    leases = {}
    for dev in devices or []:
        for info in dev.get('addr_info') or []:
            if info.get('family') not in ('inet', 2):
                continue
            prefix = int(info.get('prefixlen') or 0)
            address = info.get('local') or ''
            if not address or prefix in (0, 31, 32):
                continue
            try:
                network = ipaddress.ip_network('%s/%d' % (address, prefix),
                                               strict=False)
            except ValueError:
                continue
            leases[dev.get('ifname')] = {
                'address': address,
                'prefix': prefix,
                'broadcast': str(network.broadcast_address),
                'gateway': None,
                'dynamic': bool(info.get('dynamic')),
            }
            break

    for route in routes or []:
        if route.get('dst') not in ('default', 'any'):
            continue
        via = route.get('gateway') or route.get('via')
        dev = route.get('dev')
        if via and dev in leases:
            leases[dev]['gateway'] = via
            break

    return leases


def resolv_index(text):
    """Extract the servers and search domains from a resolv.conf body."""
    servers = []
    search = []
    for line in (text or '').splitlines():
        line = line.strip()
        if line.startswith('#'):
            continue
        if line.startswith('nameserver '):
            server = line.split()[1]
            if server not in servers:
                servers.append(server)
        elif line.startswith('search '):
            search = [d for d in line[7:].split() if d]
    return {'servers': servers, 'search': search}


def resolv_content(servers, search):
    """Render the complete static /etc/resolv.conf body."""
    lines = ['# Managed by rushwilt.pi.dhcp_to_static: DHCP no longer fills this file.']
    for server in servers or []:
        lines.append('nameserver %s' % server)
    if search:
        lines.append('search %s' % ' '.join(search))
    return '\n'.join(lines) + '\n'


def _netplan_ifaces(doc):
    """Yield ``(section, iface, conf)`` for every interface stanza of a netplan document."""
    if not isinstance(doc, dict):
        return
    network = doc.get('network')
    if not isinstance(network, dict):
        return
    for section in NETPLAN_SECTIONS:
        block = network.get(section)
        if not isinstance(block, dict):
            continue
        for iface, conf in block.items():
            if isinstance(conf, dict):
                yield section, iface, conf


def backend_of(iface, lease, netplan_docs, interfaces_content, dhcpcd_active,
               nm_dhcp=None):
    """Work out how ``iface`` gets its configuration today.

    Returns a record ``{backend, file, address, prefix, broadcast, gateway}``
    when the interface is handed to DHCP by a supported backend, else
    ``None`` (already static, or managed by something this role does not
    touch).
    """
    if not lease:
        return None
    record = {
        'backend': None,
        'file': None,
        'address': lease.get('address'),
        'prefix': lease.get('prefix'),
        'broadcast': lease.get('broadcast'),
        'gateway': lease.get('gateway'),
    }

    for filename, doc in (netplan_docs or {}).items():
        for _section, name, conf in _netplan_ifaces(doc):
            if name == iface and conf.get('dhcp4') is True:
                record['backend'] = 'netplan'
                record['file'] = filename
                return record

    for line in (interfaces_content or '').splitlines():
        match = IFACE_DHCP_RE.match(line)
        if match and match.group(1) == iface:
            record['backend'] = 'ifupdown'
            return record

    if nm_dhcp and iface in nm_dhcp and nm_dhcp.get(iface) == 'auto':
        record['backend'] = 'networkmanager'
        record['file'] = ('/etc/NetworkManager/system-connections/'
                          'rushwilt-%s.nmconnection' % iface)
        return record

    if dhcpcd_active:
        record['backend'] = 'dhcpcd'
        return record

    return None


def netplan_static(doc, leases, servers, search):
    """Return a copy of a netplan document with target DHCP stanzas made static.

    Every interface whose ``dhcp4`` is true and that holds a live lease gets
    ``dhcp4: false``, the live address/prefix, the default route when the
    interface owns one, and the current resolver configuration.  All other
    keys of the stanza (mtu, accept-ra, ...) are preserved.
    """
    out = copy.deepcopy(doc)
    for _section, iface, conf in _netplan_ifaces(out):
        if conf.get('dhcp4') is not True:
            continue
        lease = (leases or {}).get(iface)
        if not lease:
            continue
        conf['dhcp4'] = False
        conf['addresses'] = ['%s/%s' % (lease['address'], lease['prefix'])]
        if lease.get('gateway'):
            routes = conf.get('routes')
            if not isinstance(routes, list):
                routes = []
            routes = [r for r in routes
                      if not (isinstance(r, dict) and r.get('to') in ('default', 'any'))]
            routes.append({'to': 'default', 'via': lease['gateway']})
            conf['routes'] = routes
        if servers or search:
            nameservers = conf.get('nameservers')
            if not isinstance(nameservers, dict):
                nameservers = {}
            if servers:
                nameservers['addresses'] = list(servers)
            if search:
                nameservers['search'] = list(search)
            conf['nameservers'] = nameservers
    return out


def ifupdown_static(content, targets):
    """Rewrite ``iface <if> inet dhcp`` stanzas as static in an ifupdown file.

    ``targets`` maps interface name to its lease record.  The old option lines
    of a converted stanza (``dns-*``, ``hostname``, ...) are dropped and the
    new stanza carries address, broadcast and gateway; everything else in the
    file is preserved verbatim.
    """
    out = []
    skipping = False
    for line in (content or '').splitlines():
        match = IFACE_DHCP_RE.match(line)
        if match and match.group(1) in (targets or {}):
            t = targets[match.group(1)]
            out.append('iface %s inet static' % match.group(1))
            out.append('    address %s/%s' % (t['address'], t['prefix']))
            if t.get('broadcast'):
                out.append('    broadcast %s' % t['broadcast'])
            if t.get('gateway'):
                out.append('    gateway %s' % t['gateway'])
            skipping = True
        elif line.strip() == '' or not line[0].isspace():
            skipping = False
            out.append(line)
        elif skipping:
            pass  # drop the old DHCP option lines of the converted stanza
        else:
            out.append(line)
    return '\n'.join(out) + ('\n' if out else '')


def dict_from_items(items):
    """Rebuild a dict from ``dict2items`` output (a list of ``{key, value}`` pairs).

    Plain ``dict()`` would unpack each pair as a ``(key, value)`` tuple of its
    own keys, so the reconstruction needs this helper.
    """
    return {item['key']: item['value'] for item in items or []}


def nmcli_active(text):
    """Parse ``nmcli -t -f NAME,DEVICE connection show --active`` output.

    Returns ``[{name, device}, ...]``; each line is split on the last colon so
    a connection name may itself contain a colon.
    """
    out = []
    for line in (text or '').splitlines():
        line = line.strip()
        if not line or ':' not in line:
            continue
        name, _, device = line.rpartition(':')
        if not name or not device:
            continue
        out.append({'name': name, 'device': device})
    return out


def nm_keyfile(iface, lease, servers, search):
    """Render a static (manual) NetworkManager keyfile for ``iface``.

    Mirrors the on-disk format NetworkManager itself writes: a single ``[ipv4]``
    block with ``method=manual``, the live address, gateway and the resolver
    servers/search domains, plus ``[ipv6]`` left on auto.  No uuid is written;
    NetworkManager assigns one in memory and leaves the file untouched.
    """
    lines = [
        '[connection]',
        'id=rushwilt-%s' % iface,
        'type=ethernet',
        'interface-name=%s' % iface,
        'autoconnect=true',
        '',
        '[ipv4]',
        'method=manual',
        'address1=%s/%d' % (lease['address'], lease['prefix']),
    ]
    if lease.get('gateway'):
        lines.append('gateway=%s' % lease['gateway'])
    if servers:
        lines.append('dns=%s;' % ';'.join(servers))
    if search:
        lines.append('dns-search=%s;' % ';'.join(search))
    lines += ['', '[ipv6]', 'method=auto']
    return '\n'.join(lines) + '\n'


def timesync_ntp(text):
    """Parse busctl's ``as N "srv" "srv"`` property output into a list.

    ``as 0`` (no servers, or no timesyncd on the box) yields ``[]``.
    """
    text = (text or '').strip()
    match = re.match(r'^as\s+(\d+)(?:\s+(.*))?$', text, re.DOTALL)
    if not match:
        return []
    if int(match.group(1)) == 0:
        return []
    return re.findall(r'"((?:[^"\\]|\\.)*)"', match.group(2) or '')


def zip_dict(keys, values):
    """Pair two parallel lists into a ``{key: value}`` dict.

    Jinja's ``dict()`` takes a single iterable argument, so zipping two lists
    needs this helper.
    """
    keys = list(keys or [])
    values = list(values or [])
    return dict(zip(keys, values))


class FilterModule:
    """Filter plugins used by rushwilt.pi.dhcp_to_static."""

    def filters(self):
        return {
            'lease_index': lease_index,
            'resolv_index': resolv_index,
            'resolv_content': resolv_content,
            'backend_of': backend_of,
            'netplan_static': netplan_static,
            'ifupdown_static': ifupdown_static,
            'dict_from_items': dict_from_items,
            'nmcli_active': nmcli_active,
            'nm_keyfile': nm_keyfile,
            'timesync_ntp': timesync_ntp,
            'zip_dict': zip_dict,
        }
