"""Entry-point CLI.

    vdsensor sniff --port /dev/ttyO4         # print decoded ERP1 telegrams
    vdsensor probe --port /dev/ttyO4         # CO_RD_VERSION + CO_RD_IDBASE
    vdsensor reset --port /dev/ttyO4         # CO_WR_RESET
    vdsensor serve --port /dev/ttyO4         # FastAPI web UI
    vdsensor serve --fake                    # synthetic source, no hardware
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from .hardware import Color, build_leds
from .transport import Controller, FakeSerialLink


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="vdsensor")
    p.add_argument("--port", default="/dev/ttyO4", help="serial device (default /dev/ttyO4)")
    p.add_argument("--baud", type=int, default=57600, help="baudrate (default 57600)")
    p.add_argument("--fake", action="store_true",
                   help="use a synthetic ESP3 source instead of opening a real port")
    p.add_argument("-v", "--verbose", action="count", default=0)

    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("sniff", help="print decoded ERP1 telegrams to stdout")
    sub.add_parser("probe", help="read chip version and IDBASE, then exit")
    sub.add_parser("reset", help="send CO_WR_RESET, then exit")

    serve = sub.add_parser("serve", help="run the FastAPI web UI")
    serve.add_argument("--http-host", default="0.0.0.0")
    serve.add_argument("--http-port", type=int, default=8080)
    serve.add_argument("--db-url", default="sqlite+aiosqlite:///vdsensor.db")
    serve.add_argument("--mqtt-url", default=None,
                       help="e.g. mqtt://user:pass@host:1883; omit to disable MQTT")
    serve.add_argument("--mqtt-prefix", default="vdsensor")
    serve.add_argument("--ha-discovery-prefix", default="homeassistant")
    return p


def _make_controller(args: argparse.Namespace) -> Controller:
    # Default GPIO mapping matches the env-driven Settings; in --fake we skip
    # sysfs writes but still keep the Color → GPIO map so the dashboard /api/leds
    # endpoint can show what the hardware will look like.
    gpios = {Color.GREEN: 67, Color.ORANGE: 68, Color.RED: 66}
    leds = build_leds("none" if args.fake else "sysfs", gpios)
    if args.fake:
        return Controller(FakeSerialLink(), leds=leds)
    return Controller.from_serial(port=args.port, baudrate=args.baud, leds=leds)


async def _sniff(controller: Controller) -> None:
    print(f"# sniffing on {controller.link.port}; Ctrl-C to exit", file=sys.stderr)
    async with controller.subscribe() as q:
        while True:
            erp1 = await q.get()
            payload_hex = erp1.payload.hex()
            print(
                f"RORG=0x{erp1.rorg:02x} sender=0x{erp1.sender_id:08x} "
                f"status=0x{erp1.status:02x} dbm={erp1.dbm} payload={payload_hex}"
            )


async def _probe(controller: Controller) -> None:
    v = await controller.read_version()
    ib = await controller.read_idbase()
    print(f"app_version  = {'.'.join(str(x) for x in v.app_version)}")
    print(f"api_version  = {'.'.join(str(x) for x in v.api_version)}")
    print(f"chip_id      = 0x{v.chip_id:08x}")
    print(f"chip_version = 0x{v.chip_version:08x}")
    print(f"description  = {v.description!r}")
    print(f"idbase       = 0x{ib.base_id:08x} (remaining writes: {ib.remaining_writes})")


async def _reset(controller: Controller) -> None:
    resp = await controller.reset()
    print(f"CO_WR_RESET return code = 0x{resp.return_code:02x}")


async def _serve(controller: Controller, args: argparse.Namespace) -> None:
    import uvicorn

    from .web.app import build_app

    app = build_app(
        controller,
        db_url=args.db_url,
        mqtt_url=args.mqtt_url,
        mqtt_prefix=args.mqtt_prefix,
        ha_discovery_prefix=args.ha_discovery_prefix,
    )
    config = uvicorn.Config(
        app, host=args.http_host, port=args.http_port, log_level="info", lifespan="on"
    )
    await uvicorn.Server(config).serve()


async def _run(args: argparse.Namespace) -> int:
    if args.verbose >= 2:
        level = logging.DEBUG
    elif args.verbose == 1:
        level = logging.INFO
    else:
        level = logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    ctrl = _make_controller(args)

    if args.cmd == "serve":
        # web/app.py owns the controller lifespan; don't double-open it here.
        await _serve(ctrl, args)
        return 0

    async with ctrl.run():
        if args.cmd == "sniff":
            await _sniff(ctrl)
        elif args.cmd == "probe":
            await _probe(ctrl)
        elif args.cmd == "reset":
            await _reset(ctrl)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return asyncio.run(_run(args))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
