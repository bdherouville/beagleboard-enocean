# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository actually contains

Read this first — it changes what tasks are sensible:

- **No source tree.** Only Java JARs + shell scripts under `VDSensor/`. There is no `pom.xml`, `build.gradle`, or `src/`. Nothing here builds.
- **No tests, no linter, no CI.** "Run the tests" / "build the project" are not applicable; do not look for a build system.
- **The artifacts target a BeagleBone Black** running an EnOcean daughter-board over UART. Code currently here cannot be exercised on the dev host beyond static inspection.
- **Stated user goal: reverse-engineer the protocol, then port to Python + Docker.** Maintaining the Java is *not* the job. Everything below is to support that reverse-engineering.

`config-pin` at the repo root is a symlink into `/opt/source/beaglebone-universal-io/` — that is a copy of cdsteinkuehler's BBB pinmux helper and is not part of this project's code. The two-byte `VDSensor/value` file is a stray artifact (a `LedsHandler` `echo 0 > value` that ran in the wrong cwd) — ignore it.

## How to inspect the JARs

There is no JDK toolchain installed (no `javap`, no decompiler, no internet). Use these patterns instead:

```bash
unzip -q VDSensor/VDSensorAgent.jar  -d /tmp/agent
UNZIP_DISABLE_ZIPBOMB_DETECTION=TRUE unzip -qo VDSensor/VDSensorClient.jar -d /tmp/client   # client jar trips zipbomb heuristic
strings -n 4 /tmp/client/main/ConsoleHandler.class      # class names, string literals, format strings
```

For numeric constants (baud rates, packet-type bytes), parse the constant pool directly with Python — the existing `/tmp/vdclient-extract/` extraction has been used to confirm the values cited below.

The `CLIENT_JAR/` and `AGENT_JAR/` subdirectories hold versioned snapshots of the same code (`VDMeeting-*.jar` is the predecessor product); the canonical artifacts are `VDSensorClient.jar` (v0.2, 2017‑01‑27) and `VDSensorAgent.jar` (v0.2, 2017‑01‑27) at the `VDSensor/` root.

## System architecture

Two cooperating Java processes on the BBB, both launched via cron and bash wrappers:

- **VDSensorAgent** (`Main` → `Agent`, supervisor). Polls `ps -fC java | grep VDSensorClient` on each heartbeat; if missing, runs `VDSensorClientLauncher.sh`. Also POSTs `ping_is_alive` to the server, fetches `VDSensorClient.json` / `VDSensorAgent.json` from a configured URL, and self-updates by downloading a new ZIP via `Updater` + `UnzipHelper`.
- **VDSensorClient** (`main.Main` → `main.ConsoleHandler`, sensor I/O). Opens the serial port to the EnOcean module, parses ESP3 frames, posts each radio telegram to the server, blinks BBB user LEDs, and optionally watches `/proc/net/dev` for an interface (`NetworkTrafficSpy`) to detect WAN loss. Buffers failed POSTs to disk via `OfflinePacketsHandler` and replays them.

Both share the same idiom: `helpers/RequestHelper` POSTs `application/x-www-form-urlencoded` to `<server>/php/Controller/client.php` with two fields, `functionName` and a JSON `parameters` string. Failed requests become `network/OfflinePacket` blobs (`.pkt` files via Java `ObjectOutputStream`) that the handler retries every 15 s.

Bootstrap chain (read these top-down to follow the runtime):

1. `VDSensorAgentSetup.sh` — installs zips into `/usr/local/bin/VDSensor/`.
2. `VDSensorAgentCron.sh` — installs a `* * * * *` crontab entry, then `nohup java -jar VDSensorAgent.jar …` if not already running. CLI flags consumed by `ArgsHandler`: `--location`, `--processToCheck`, `--heartbeat`, `--serverType`, `--agentName`, `--agentId`, `--server`, `--watchNetTraffic`.
3. `VDSensorClientLauncher.sh` — `java -jar VDSensorClient.jar --server https://viadirect-vds.serv.cdc.fr/sensors/ --connect /dev/ttyO4 --heartbeat 3 --disableOfflinePackets --watchNetTraffic eth0`. Client CLI: `--connect`, `--reconnectInterval`, `--disableOfflinePackets`, `--watchNetTraffic`, `--serverType`, `--heartbeat`, `--fakeData`, `--server`.

`ConsoleHandler` exposes an interactive REPL on stdin (`connect`, `close`, `reset`, `show`, `exit`) — useful for confirming behaviour against hardware once a port is reachable.

## Hardware: pins and serial path

Observed (extracted from class files):

- `usb/SerialPortHandler` constants: `BAUDRATE = 57600`, sync `0x55`, buffer 128 B.
- The handler branches on the device path: names matching `/dev/ttyAMA0` or `/dev/ttyO*` go through pi4j (`com.pi4j.io.serial.Serial`); anything else goes through RXTX (`gnu.io.SerialPort`). The launcher uses `/dev/ttyO4`, so the production path is **pi4j**. Note that pi4j is the Raspberry Pi library — the BBB still exposes the right `/dev/ttyO*` node, but the choice tells you the original author treated this as a "GPIO-backed serial" abstraction.
- `LedsHandler` writes via `/sys/class/gpio/gpio<N>/{export,direction,value}` and `cd /sys/class/gpio` shell sequences. LEDs used: `usr0`, `usr1`, plus the on-board Ethernet green/amber LEDs (these are referenced by name in `ConsoleHandler`, mapped to `LedsHandler` instances). The numeric GPIO IDs are passed in from `ConsoleHandler` constructor — confirm from the constant pool if you need them.

Inferred (BeagleBone Black convention, **not** observed in any setup script in this repo):

- `/dev/ttyO4` is BBB UART4 → header pins **P9.11 (RX, mode 6)** and **P9.13 (TX, mode 6)**. Pinmux is *not* configured by anything checked in here; the deployed BBB image must do it at boot (device-tree overlay or `config-pin P9.11 uart` / `config-pin P9.13 uart`). When porting, this is the first thing to verify on the target board.

## EnOcean ESP3 protocol shape

This is the bulk of the porting work. Observed from `helpers/PacketHelper` and `packets/`:

- ESP3 framing: sync `0x55`, then 4-byte header `[data_len_hi, data_len_lo, opt_len, packet_type]`, header CRC8, data, opt-data, data CRC8.
- Packet-type symbols present (numeric values follow ESP3 spec, not constant-pool order): `RESERVED`, `RADIO`, `RESPONSE`, `RADIO_SUB_TEL`, `EVENT`, `COMMON_COMMAND`, `SMART_ACK_COMMAND`, `REMOTE_MAN_COMMAND`. A `CO_WR_RESET` symbol also appears; treat it per the ESP3 spec (subcode of `COMMON_COMMAND`).
- Radio-telegram RORG bytes recognised: `0xA5` (4BS), `0xA6` (ADT), `0xD2` (VLD), `0xD4` (VLL), `0xF6` (RPS). Each branches to a separate `loadXxxPacket` parser in `PacketRadioEnOcean`.
- After parse, `PacketRadioEnOcean` exposes `getDataByte0..3` + 4-byte `getSenderID()` + `getStatus()`. The CRC8 table is in `helpers/Helper.checkCRC8` — the constant pool of `Helper.class` holds the 256-byte lookup table, useful to lift verbatim into Python.
- `RET_OK / RET_ERROR / RET_NOT_SUPPORTED / RET_WRONG_PARAM / RET_OPERATION_DENIED` come back inside `RESPONSE` packets.

## Server-facing wire format

`POST <server>/php/Controller/client.php` (`application/x-www-form-urlencoded`) with two URL-encoded fields:

- `functionName` — one of: `insert_event` (radio telegram), `ping_is_alive` (heartbeat / metadata), `get_vdsensorclient_json`, `get_vdsensoragent_json` (update manifests).
- `parameters` — JSON. For `insert_event`, the format string is literally:
  ```
  {"date": "%s", "data_1": "%s", "data_2": "%s", "data_3": "%s", "unique_name": "%08x"}
  ```
  `data_1..3` are EnOcean data bytes 1, 2, 3 (note: byte 0 is *not* sent), `unique_name` is the 32-bit sender ID hex-formatted, `date` is `yyyy-MM-dd HH:mm:ss'z'` UTC.

Servers seen referenced in the artifacts:
- Production: `https://viadirect-vds.serv.cdc.fr/sensors/` (in `VDSensorClientLauncher.sh`).
- Default-baked dev: `http://192.168.1.19/projects/VDSensorServer/` (in `helpers/RequestHelper`) and `http://192.168.1.19/projects/VDMeeting/` (in `ArgsHandler`). These are stale defaults overridden by `--server` at runtime.

Update flow: `Updater` downloads a ZIP to `temp/`, `UnzipHelper` extracts it, `JsonVDSensor{Client,Agent}` parses the metadata fields `file`, `version`, `update`, `sha1`, `md5`. Replicate this only if the Python port needs to keep self-update parity.

## Where to look for what

- ESP3 framing & RORG decoders → `packets/PacketEnOcean.class`, `packets/PacketRadioEnOcean.class`, `packets/PacketResponseEnOcean.class`, `packets/PacketFactory.class`.
- CRC8 table → constant pool of `helpers/Helper.class`.
- Serial I/O & port-type branching → `usb/SerialPortHandler.class`.
- Server protocol → `helpers/RequestHelper.class` and the `insert_event` site in `main/ConsoleHandler.class`.
- Supervisor / heartbeat / self-update → `Agent.class`, `Updater.class`, `helpers/UnzipHelper.class` (in agent JAR).
- Offline-packet replay queue → `network/OfflinePacketsHandler.class`, `network/OfflinePacket.class`.
- LED + interactive console behaviour → `main/LedsHandler.class`, `main/ConsoleHandler.class`.

When the Python port begins, the natural module split mirrors this: `esp3` (framing+CRC+RORG decoders), `transport` (serial), `uplink` (HTTP + offline queue), `supervisor` (agent role), `cli` (entry points). Containerise the client and agent separately — they have independent lifecycles in the original design.
