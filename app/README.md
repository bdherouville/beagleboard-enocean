# vdsensor

Containerised replacement for the legacy Java `VDSensorClient`/`VDSensorAgent`.
Talks ESP3 over UART to an EnOcean daughter-board on a BeagleBone Black,
exposes a small web UI for pairing and management, and bridges decoded sensor
state to Home Assistant via MQTT discovery.

## Quickstart (dev host, no hardware)

```bash
make dev                                    # create .venv, install editable + dev deps
make test                                   # 50 unit tests
make lint                                   # ruff
make serve-fake                             # http://localhost:8080 with synthetic source
```

The fake source rotates through RPS / 1BS / 4BS / VLD telegrams once a second
so the live inspector and the pairing wizard have something to chew on.

## Quickstart (BeagleBone Black, real hardware)

1. **One-time on the BBB**: enable UART4. See `docs/BBB-pinmux.md`.
2. **Pull the image** from the registry that CI / your build host pushed to:

   ```bash
   echo "$GHCR_READ_PAT" | docker login ghcr.io -u <user> --password-stdin
   cp .env.example .env && $EDITOR .env
   docker compose pull
   docker compose up -d
   ```

3. Browse to `http://<bbb>:8080/`. Pair a device, label it, pick its EEP
   profile. If `VDSENSOR_MQTT_URL` is set, the device shows up in Home
   Assistant within a few seconds via MQTT discovery.

### Identifying the daughter-board LEDs

If the green / orange / red LEDs on the dashboard don't match the physical
ones, run `sudo bash app/scripts/leds-identify.sh` on the BBB. It walks
GPIOs 66/67/68/69 (the four the legacy Java exported) and lights each for
3 seconds, then prints the canonical BBB header-pin mapping. Whatever
colour you see when each GPIO is on tells you what to put in
`VDSENSOR_LED_{GREEN,ORANGE,RED}_GPIO`.

## Building the ARMv7 image

The dev host is x86_64; the BBB is ARMv7 (Cortex-A8). Two paths, both
documented in `docs/REGISTRY.md`:

- **GitHub Actions** (recommended): push to GitHub, `.github/workflows/build-and-push.yml`
  cross-builds with QEMU on a hosted runner and pushes to
  `ghcr.io/<owner>/vdsensor`. `GITHUB_TOKEN` handles GHCR auth automatically.
  No build infrastructure on your machine.
- **Local cross-build**: `make qemu-binfmt` once (needs sudo), then
  `make push IMAGE=ghcr.io/<user>/vdsensor` whenever. Auth via
  `gh auth login -p ssh` — no PAT stored on disk.

## Configuration

All runtime knobs are env vars (prefix `VDSENSOR_`). See `vdsensor.config.Settings`
and `.env.example`. Highlights:

| Variable | Default | Purpose |
|---|---|---|
| `VDSENSOR_SERIAL_PORT` | `/dev/ttyO4` | UART node attached to the EnOcean module |
| `VDSENSOR_DB_PATH` | `/data/vdsensor.db` | SQLite registry path (volume-mounted) |
| `VDSENSOR_HTTP_PORT` | `8080` | HTTP server port |
| `VDSENSOR_MQTT_URL` | unset | `mqtt://user:pass@host:1883` — enables the HA bridge |
| `VDSENSOR_MQTT_PREFIX` | `vdsensor` | Own topic namespace |
| `VDSENSOR_HA_DISCOVERY_PREFIX` | `homeassistant` | HA discovery topic prefix |
| `VDSENSOR_FAKE` | `false` | Use a synthetic source instead of opening UART |

## Project layout

```
app/
  src/vdsensor/
    esp3/         ESP3 framing + CRC + RADIO_ERP1 + RESPONSE/EVENT + 4 commands
    transport/    Serial link with reconnect; FakeSerialLink for dev iteration;
                  Controller (request/response correlation, learn windows)
    eep/          DecodedPoint + per-profile decoders (A5-02-05, A5-04-01, …)
    registry/     SQLAlchemy 2.0 async + aiosqlite; pairing state machine
    mqtt/         aiomqtt bridge with LWT + retained HA discovery
    web/          FastAPI + Jinja2 + HTMX; routes, templates, /ws/live, /ws/pair
    cli.py        sniff / probe / reset / serve subcommands
    main.py       container entry-point: settings-driven, no argparse
  tests/          50 unit tests, ESP3 fixtures from the v1.58 spec
  Dockerfile      multi-stage; cross-build target = linux/arm/v7
  docker-compose.yml  what runs on the BBB
  Makefile        dev / test / lint / build / push helpers
  docs/           BBB pinmux, registry setup
```

## Source of truth for the protocol

`/home/bdherouville/Lab/vdsensor/vdsensor/EnOceanSerialProtocol3-1.pdf` (ESP3
v1.58, 116 pp.). Numeric codes in `src/vdsensor/esp3/` carry inline `§x.y.z`
references so each constant is auditable.
