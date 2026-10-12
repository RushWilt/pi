# rushwilt.pi.tpm

Brings up a Raspberry Pi **SPI TPM 2.0** module (Infineon SLB 967x family,
driven by the kernel `tpm_tis_spi` driver) and verifies it answers on
`/dev/tpm0`.

The role works in two stages, because device-tree changes only take effect at
the next boot:

1. **First run** — writes the firmware settings into the boot configuration
   and installs the userspace tooling, then reports that a reboot is pending.
2. **After the reboot** — verifies the chip is live and reports its firmware
   revision.

Boards without a TPM module fitted come back as a clean no-op (or a
controlled failure, if you ask for one — see `rushwilt_tpm_fail_if_absent`).

## How it works

- Ensures `dtparam=spi=on` and `dtoverlay=tpm-slb9670` in the boot
  configuration. The overlay name is checked against the running kernel's
  device-tree overlay tree before anything is written.
- Installs `tpm2-tools`.
- After the reboot, probes `/dev/tpm0` and reports the firmware revision.
- If the configuration is in place but no chip answers, it dumps the last
  TPM/SPI kernel messages to help separate "no module wired" from "faulty SPI
  link".

## Requirements

- `ansible-core >= 2.20`
- Debian 12/13, Ubuntu 24.04/26.04, or the current Debian-based Raspberry Pi
  OS, with a kernel that ships the `tpm-slb9670` overlay and the
  `tpm_tis_spi` driver (all current Raspberry Pi kernels do)
- `become: true`

## Role variables

| Variable                      | Default         | Purpose                                                                     |
|-------------------------------|-----------------|-----------------------------------------------------------------------------|
| `rushwilt_tpm_dtparam`        | `spi=on`        | firmware parameter that enables the SPI controller on the Pi                |
| `rushwilt_tpm_dtoverlay`      | `tpm-slb9670`   | device-tree overlay that binds the SLB 967x SPI TPM to the kernel driver     |
| `rushwilt_tpm_packages`       | `[tpm2-tools]`  | userspace package providing the `tpm2_*` commands                          |
| `rushwilt_tpm_fail_if_absent` | `false`         | fail the play when this board is expected to carry a TPM but none answers; `false` reports the absence with the kernel messages instead |

## Facts

After the role runs, the play scope carries:

- `rushwilt_tpm_supported` — the running kernel can drive the module,
- `rushwilt_tpm_present` — `/dev/tpm0` answers,
- `rushwilt_tpm_reboot_pending` — configuration was just applied,
- `rushwilt_tpm_firmware` — the chip's firmware revision (when present).

## Usage

```yaml
- hosts: pi5
  become: true
  roles:
    - rushwilt.pi.tpm
```

Typical first-contact sequence:

```
ansible-playbook pi5.yml            # "reboot the board and re-run the play"
ansible pi5 -b -m reboot
ansible-playbook pi5.yml            # "TPM online on /dev/tpm0, firmware 0xF0019"
```

## License

Apache-2.0 — see the file headers.
