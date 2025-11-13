import asyncio, json
from typing import Tuple, Optional
from ..utils.logging_setup import make_logger


class UdpJsonLogServerProtocol(asyncio.DatagramProtocol):
    def __init__(self, logger):
        self.logger = logger
    def datagram_received(self, data: bytes, addr: Tuple[str, int]):
        try:
            line = data.decode("utf-8", errors="replace").strip()
            if line.startswith("{"):
                obj = json.loads(line)
                self.logger.info("REMOTE %s:%d %s", addr[0], addr[1], json.dumps(obj, ensure_ascii=False))
            else:
                self.logger.info("REMOTE %s:%d %s", addr[0], addr[1], line)
        except Exception as e:
            self.logger.warning("Malformed UDP log from %s:%d: %r (%s)", addr[0], addr[1], data[:200], e)


async def run_udp_log_server(host: str, port: int, logfile: Optional[str]):
    logger = make_logger("udp-log-server", log_file=logfile)
    loop = asyncio.get_running_loop()
    transport, _ = await loop.create_datagram_endpoint(lambda: UdpJsonLogServerProtocol(logger), local_addr=(host, port))
    logger.info("UDP log server listening on %s:%d", host, port)
    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        transport.close()
