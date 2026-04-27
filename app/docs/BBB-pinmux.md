# Enabling UART4 on the BeagleBone Black

The container needs `/dev/ttyS4` (BBB UART4) to talk to the EnOcean
daughter-board. Pinmux is a host-side concern; the container only does
`devices: ["/dev/ttyS4:/dev/ttyS4"]` and joins the `dialout` group.

> **Naming note.** The legacy Java code (and BBB Debian images shipped before
> ~2020) called this node `/dev/ttyO4` — the kernel's old "OMAP UART"
> naming. Modern kernels expose the same hardware as `/dev/ttyS4` and no
> longer create the `ttyO*` symlinks. If your image still has `/dev/ttyO4`
> (rare, and `ls /dev/ttyO*` shows it), set
> `VDSENSOR_SERIAL_PORT=/dev/ttyO4` in `.env` and update the device
> passthrough in `docker-compose.yml` accordingly.

## What needs to happen

UART4 is exposed on the P9 expansion header:

| BBB pin | UART4 function | Mode |
|---|---|---|
| **P9.11** | RX | Mode 6 |
| **P9.13** | TX | Mode 6 |

These two pins must be muxed into UART4 mode at boot. Pick one of the
following — Option A is the most reliable on current Debian images.

### Option A — U-Boot overlay (recommended)

Add to `/boot/uEnv.txt`:

```
enable_uboot_overlays=1
uboot_overlay_addr0=/lib/firmware/BB-UART4-00A0.dtbo
```

Verify the file exists:

```bash
ls -l /lib/firmware/BB-UART4-00A0.dtbo
```

Reboot. After boot, UART4 is muxed in stone — `config-pin` is not needed
and would in fact fail with `P9_11 pinmux file not found!` because this
overlay does not expose runtime mux files (that's cape-universal's job —
see Option B). The `uart4-pinmux.service` systemd unit shipped with the
installer tolerates this: it tries `config-pin` with a leading `-` so a
failure here is a no-op.

### Option B — cape-universal + `config-pin` at runtime

Use this if you want `config-pin` to be functional for other pins as well:

```
enable_uboot_overlays=1
uboot_overlay_addr4=/lib/firmware/cape-universaln-00A0.dtbo
```

Reboot. After this, `config-pin` works:

```bash
sudo config-pin -q P9.11      # 'Current mode for P9.11 is: …'
sudo config-pin    P9.11 uart
sudo config-pin    P9.13 uart
```

The `uart4-pinmux.service` unit will succeed normally and the mux will be
re-applied on every boot.

### Verify either option worked

```bash
ls -l /dev/ttyS4                       # expect crw-rw---- root:dialout
dmesg | grep -i 'serial.*tty' | tail   # should mention ttyS4 around boot
```

## Verifying the chip is actually wired

Once `/dev/ttyS4` exists, prove the EnOcean module is reachable *before*
launching the container — much faster to debug at this layer.

```bash
# In the project venv, on the BBB itself:
python -m vdsensor.cli probe --port /dev/ttyS4
# Expected output:
#   app_version  = 2.x.y.z
#   api_version  = 1.x.y.z
#   chip_id      = 0xXXXXXXXX
#   description  = 'GATEWAYCTRLR' (or similar)
#   idbase       = 0xFFXXXXXX (N writes left)
```

If `probe` times out, the chip isn't responding — check pinmux, baud
(should be 57600 8N1), and the daughter-board's power/wiring.

## `dialout` GID

Most BBB Debian images use `gid=20` for the `dialout` group, which is
what `docker-compose.yml` adds via `group_add: ["20"]`. Confirm on your
target:

```bash
getent group dialout                # 'dialout:x:20:'  → 20 is right
```

If the GID differs, edit the compose file accordingly.
