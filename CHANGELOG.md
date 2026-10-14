# Changelog

All notable changes to the `rushwilt.pi` collection.

## 1.2.0 — 2026-10-14

### Added

- **luks_sd_tpm** — the volume is now mounted at a configurable
  mountpoint instead of the hardcoded `/data`: new default variable
  `rushwilt_luks_sd_mountpoint` (default `/data`). The fstab entry,
  the systemd boot-unlock ordering (`Before=<mountpoint>.mount`) and
  the "mount now" task all follow the configured mountpoint.

## 1.1.0 — 2026-10-12

### Added

- **tpm** — in-place auto-reboot: when the firmware configuration was just
  applied, the role reboots the board itself, waits for it to come back on
  its address, and continues the play with the verification, instead of
  stopping with "reboot the board and re-run the play". New default variable
  `rushwilt_tpm_auto_reboot` (default `true`) and new fact
  `rushwilt_tpm_reboot_now`. When the option is disabled — or when a
  dynamically leased interface with a gateway would lose its address across
  the reboot — the role falls back to reporting the pending reboot instead.
- **tpm** — check mode (`--check`) is now refused with an explanatory
  message, since the role rewrites the boot configuration and may reboot
  the host.

### Changed

- First contact with a freshly imaged Pi is now a single run of the play:
  the DHCP stage applies, the TPM stage reboots the board in place, and the
  LUKS stage seals the SD card and mounts `/data` in the same run.
- Root and role READMEs updated to match.
- **luks_sd_tpm** — the `format_sdcard` variable is now
  `rushwilt_luks_sd_format`, matching the `rushwilt_luks_sd_*` prefix of
  the role's other variables.

## 1.0.0 — 2026-10-12

Initial release:

- **dhcp_to_static** — convert DHCP-managed interfaces to static
  configuration.
- **tpm** — bring up the on-board SPI TPM 2.0 module (Infineon SLB 967x)
  and verify it answers on `/dev/tpm0`.
- **luks_sd_tpm** — provide the SD card as a LUKS data volume that only
  the board's own TPM can unseal.
