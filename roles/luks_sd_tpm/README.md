# rushwilt.pi.luks_sd_tpm

Provides the SD card as a **LUKS2 data volume that can only be unsealed on
this board**, mounted at `/data` and unlocked automatically at boot.

- The LUKS keyslot key is 64 random bytes from `/dev/urandom`; the key
  material only ever exists in `/run` (tmpfs) and is shredded as soon as the
  binding is in place.
- Its only copy is sealed to the board's TPM with a **clevis tpm2** binding
  under a PCR policy (`0,2,4`, sha256 bank) and registered as the LUKS token.
  No passphrase and no keyfile exist anywhere: take the card off the board
  and it cannot be opened.
- Boot unlock is a oneshot unit
  (`rushwilt-luks-sd-tpm.service`, target by PARTUUID) plus an fstab entry
  (by filesystem UUID, `noatime,nofail`).

## Decision flow

| Card state at run time                              | What the role does |
|-----------------------------------------------------|--------------------|
| LUKS volume with a tpm2 binding, open               | left alone; boot wiring ensured (no-op) |
| LUKS volume with a tpm2 binding, closed             | unsealed through the TPM, boot wiring ensured |
| LUKS volume the TPM can no longer unseal            | wiped and built fresh |
| No LUKS / no binding / other binding type           | wiped and built fresh |
| any of the above, with `rushwilt_luks_sd_format: true` | wiped and built fresh (new key, new seal) |

A rebuild: unmounts and closes the volume, wipes all signatures, writes one
GPT partition, creates the LUKS2 volume (aes-xts-plain64, 512-bit key),
seals the key to the TPM, verifies the binding is a tpm2 binding, opens the
volume, and creates the filesystem inside it.

## Requirements

- `ansible-core >= 2.20`
- the **`rushwilt.pi.tpm` role** (declared as a dependency) — a live TPM on
  `/dev/tpm0`; on a fresh OS the tpm role reboots the board in place
  (`rushwilt_tpm_auto_reboot`, default `true`) and this role continues in
  the same run
- an SD card on `/dev/mmcblk0` that does not host the system (checked
  before anything is wiped)
- `become: true`
- check mode is not meaningful: the rebuild path is destructive and the
  state checks assume a live system.

## Role variables

| Variable                      | Default          | Purpose                                                        |
|-------------------------------|------------------|----------------------------------------------------------------|
| `rushwilt_luks_sd_device`     | `/dev/mmcblk0`   | the SD card; its partition table is rewritten                  |
| `rushwilt_luks_sd_partition`  | `1`              | partition number of the LUKS volume                            |
| `rushwilt_luks_sd_mapper`     | `data`           | device-mapper name the volume is opened under                  |
| `rushwilt_luks_sd_mountpoint` | `/data`          | mountpoint of the volume                                       |
| `rushwilt_luks_sd_fs`         | `ext4`           | filesystem created inside the volume                           |
| `rushwilt_luks_sd_key_bytes`  | `64`             | length in bytes of the random LUKS key                         |
| `rushwilt_luks_sd_pcrs`       | `0,2,4`          | PCR policy (sha256 bank) of the tpm2 binding                   |
| `rushwilt_luks_sd_packages`   | see below        | userspace packages the role installs                           |
| `rushwilt_luks_sd_format`     | `false`          | force the wipe-and-rebuild path even on a healthy card         |

`rushwilt_luks_sd_packages`: `cryptsetup`, `clevis`, `clevis-luks`,
`clevis-tpm2`, `clevis-systemd`, `e2fsprogs`, `parted`, `tpm2-tools`.

## Usage

```yaml
- hosts: pi5
  become: true
  roles:
    - rushwilt.pi.luks_sd_tpm
```

Clean slate (destroys `/data`, new key, new seal):

```
ansible-playbook pi5.yml -e rushwilt_luks_sd_format=true --limit pi5
```

## Facts

After the role runs, the play scope carries `rushwilt_luks_sd_healthy`
(LUKS + tpm2 binding present), `rushwilt_luks_sd_open` (the mapper is up),
`rushwilt_luks_sd_mounted` (the mountpoint is in use) and
`rushwilt_luks_sd_rebuild` (set when an unseal attempt failed).

## Notes

- A re-image of the boot disk (NVMe) does not touch the SD card; the seal is
  bound to the board and its boot chain, so with the same image in place
  `/data` survives a re-blat and the role re-wires it on the next run.
- Verify the setup with:

  ```
  sudo blkid /dev/mmcblk0p1                 # TYPE="crypto_LUKS"
  sudo cryptsetup luksDump /dev/mmcblk0p1   # LUKS2, aes-xts-plain64
  sudo clevis luks list -d /dev/mmcblk0p1   # 0: tpm2 {... "pcr_ids":"0,2,4"}
  sudo cryptsetup status data               # open, backed by the card
  ```

## License

Apache-2.0 — see the file headers.
