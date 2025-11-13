import argparse
import asyncio
from typing import Optional, Tuple

from .logging.udp_server import run_udp_log_server
from .core.server import run_modbus_server

def _parse_udp(addr: Optional[str]) -> Optional[Tuple[str, int]]:
    if not addr:
        return None
    host, port = addr.split(":", 1)
    return host, int(port)

def build_cli() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Minimal Modbus/TCP PLC honeypot + UDP log server")
    sub = p.add_subparsers(dest="cmd", required=True)


    p_log = sub.add_parser("logger", help="start UDP JSON log server")
    p_log.add_argument("--host", default="127.0.0.1")
    p_log.add_argument("--port", type=int, default=9000)
    p_log.add_argument("--log-file", default="./logs/central.log")


    p_srv = sub.add_parser("server", help="start Modbus/TCP honeypot server")
    p_srv.add_argument("--host", default="127.0.0.1")
    p_srv.add_argument("--port", type=int, default=5020)
    p_srv.add_argument("--log-udp", default=None, help="send JSON logs to UDP host:port (optional)")
    p_srv.add_argument("--log-file", default="./logs/plc.log")


    p_both = sub.add_parser("both", help="run both UDP logger and honeypot in one process")
    p_both.add_argument("--plc-host", default="127.0.0.1")
    p_both.add_argument("--plc-port", type=int, default=5020)
    p_both.add_argument("--log-host", default="127.0.0.1")
    p_both.add_argument("--log-port", type=int, default=9000)
    p_both.add_argument("--log-file", default="./logs/plc.log")


    return p

async def _main_async(argv: list[str]) -> int:
    parser = build_cli()
    args = parser.parse_args(argv)


    if args.cmd == "logger":
        await run_udp_log_server(args.host, args.port, args.log_file)
        return 0


    if args.cmd == "server":
        udp = _parse_udp(getattr(args, "log_udp", None))
        await run_modbus_server(args.host, args.port, args.log_file, udp)
        return 0


    if args.cmd == "both":
        # start logger then server; cancel logger when server exits
        logger_task = asyncio.create_task(run_udp_log_server(args.log_host, args.log_port, "./logs/central.log"))
        await asyncio.sleep(0.1)
        try:
            await run_modbus_server(args.plc_host, args.plc_port, args.log_file, (args.log_host, args.log_port))
        finally:
            logger_task.cancel()
            with contextlib.suppress(Exception):
                await logger_task
        return 0

    return 1

def main(argv: Optional[list[str]] = None) -> int:
    import sys, contextlib
    try:
        return asyncio.run(_main_async(sys.argv[1:] if argv is None else argv))
    except KeyboardInterrupt:
        return 0
