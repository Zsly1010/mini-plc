import asyncio, json
from typing import Optional, Tuple
from ..utils.logging_setup import make_logger
from ..ids.engine import IdsConfig, IdsEngine


class UdpJsonLogServerProtocol(asyncio.DatagramProtocol):
    def __init__(self, logger, ids_engine: Optional[IdsEngine], alert_logger):
        self.logger = logger
        self.ids_engine = ids_engine
        self.alert_logger = alert_logger
    def datagram_received(self, data: bytes, addr: Tuple[str, int]):
        try:
            line = data.decode("utf-8", errors="replace").strip()
            if line.startswith("{"):
                obj = json.loads(line)
                self.logger.info("REMOTE %s:%d %s", addr[0], addr[1], json.dumps(obj, ensure_ascii=False))
                if self.ids_engine:
                    alerts = self.ids_engine.process_event(obj, addr)
                    for alert in alerts:
                        self.alert_logger.warning(
                            "ALERT rule=%s src=%s %s",
                            alert.get("rule"),
                            alert.get("src"),
                            json.dumps(alert, ensure_ascii=False),
                        )
            else:
                self.logger.info("REMOTE %s:%d %s", addr[0], addr[1], line)
        except Exception as e:
            self.logger.warning("Malformed UDP log from %s:%d: %r (%s)", addr[0], addr[1], data[:200], e)


async def run_udp_log_server(
    host: str,
    port: int,
    logfile: Optional[str],
    ids_enabled: bool = False,
    ids_alert_file: Optional[str] = None,
):
    logger = make_logger("udp-log-server", log_file=logfile)
    ids_engine = IdsEngine(IdsConfig()) if ids_enabled else None
    alert_logger = make_logger("ids", log_file=ids_alert_file or "./logs/ids.log")
    loop = asyncio.get_running_loop()
    transport, _ = await loop.create_datagram_endpoint(
        lambda: UdpJsonLogServerProtocol(logger, ids_engine, alert_logger),
        local_addr=(host, port),
    )
    logger.info("UDP log server listening on %s:%d", host, port)
    if ids_engine:
        alert_logger.warning("IDS enabled: write_burst=%d/%ss bulk_write>=%d scan_read>=%d",
                             ids_engine.config.write_burst_threshold,
                             ids_engine.config.write_burst_window_s,
                             ids_engine.config.bulk_write_count,
                             ids_engine.config.scan_read_count)
    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        transport.close()
