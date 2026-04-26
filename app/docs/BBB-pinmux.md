# Enabling UART4 on the BeagleBone Black

The container needs `/dev/ttyO4` (BBB UART4) to talk to the EnOcean
daughter-board. Pinmux is a host-side concern; the container only does
`devices: ["/dev/ttyO4:/dev/ttyO4"]` and joins the `dialout` group.

## What needs to happen

UART4 is exposed on the P9 expansion header:

| BBB pin | UART4 function | Mode |
|---|---|---|
| **P9.11** | RX | Mode 6 |
| **P9.13** | TX | Mode 6 |

These two pins must be muxed into UART4 mode at boot. Two equivalent ways
to make that happen:

### Option A — `config-pin` from a systemd unit (simplest)

```ini
# /etc/systemd/system/uart4-pinmux.service
[Unit]
Description=Mux P9.11/P9.13 to UART4 for vdsensor
Before=docker.service
After=multi-user.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/bin/config-pin P9.11 uart
ExecStart=/usr/bin/config-pin P9.13 uart

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now uart4-pinmux.service
ls -l /dev/ttyO4               # expect crw-rw---- root:dialout
```

### Option B — device-tree overlay (durable across kernel updates)

If the deployed BBB image uses U-Boot overlays, add `BB-UART4` (or the
equivalent for your distro) to `/boot/uEnv.txt`:

```
uboot_overlay_addr0=BB-UART4-00A0.dtbo
enable_uboot_overlays=1
```

Reboot. Verify the same way (`ls -l /dev/ttyO4`).

## Verifying the chip is actually wired

Once `/dev/ttyO4` exists, prove the EnOcean module is reachable *before*
launching the container — much faster to debug at this layer.

```bash
# In the project venv, on the BBB itself:
python -m vdsensor.cli probe --port /dev/ttyO4
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
