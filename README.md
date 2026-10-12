# rushwilt.pi — Raspberry Pi provisioning roles

Ansible collection of roles for a fleet of FreshPi-managed Raspberry Pis
(current Debian 12/13, Ubuntu 24.04/26.04 and Raspberry Pi OS):

| Role                                | Purpose                                                                 |
|-------------------------------------|-------------------------------------------------------------------------|
| `rushwilt.pi.dhcp_to_static`        | rewrite DHCP-issued network settings as static, keeping IP/gateway/DNS/NTP |
| `rushwilt.pi.tpm`                   | bring up the SPI TPM 2.0 module (device-tree overlay + `tpm2-tools`)    |
| `rushwilt.pi.luks_sd_tpm`           | SD card as a LUKS data volume only the board's TPM can unseal, at `/data` |

Each role is documented in its own directory — see
[`roles/dhcp_to_static/README.md`](roles/dhcp_to_static/README.md),
[`roles/tpm/README.md`](roles/tpm/README.md) and
[`roles/luks_sd_tpm/README.md`](roles/luks_sd_tpm/README.md) for
requirements, role variables and notes.

## Installation

From this repository (no Galaxy account needed):

```
ansible-galaxy collection install git+https://github.com/rushwilt/pi.git
```

From a local checkout:

```
ansible-galaxy collection install /path/to/rushwilt/pi
```

Or in a `requirements.yml`:

```yaml
collections:
  - name: rushwilt.pi
    source: git+https://github.com/rushwilt/pi.git
```

## Usage

```yaml
- hosts: pi5
  become: true
  roles:
    - rushwilt.pi.dhcp_to_static
    - rushwilt.pi.tpm
    - rushwilt.pi.luks_sd_tpm
```

Typical first contact with a freshly imaged Pi: run the play (the DHCP and
TPM stages apply; the LUKS stage stops with *"reboot the board and re-run
the play"*), reboot, re-run — then the play is idle (`changed=0`).

## Requirements

- `ansible-core >= 2.20`
- targets: the current Debian / Ubuntu / Raspberry Pi OS releases,
  root-capable (`become: true`); the roles install their own apt dependencies

## License

Apache-2.0 — see [LICENSE](LICENSE).
