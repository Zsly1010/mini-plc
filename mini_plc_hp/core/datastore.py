import dataclasses, json, logging, random, socket
from typing import Any, Dict, Optional, Tuple


from pymodbus.datastore import ModbusSequentialDataBlock
from ..utils.time import utc_ts


@dataclasses.dataclass
class UdpSink:
    addr: Optional[Tuple[str, int]] = None
    def emit(self, record: Dict[str, Any]) -> None:
        if not self.addr:
            return
        try:
            data = (json.dumps(record) + "\n").encode("utf-8")
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.sendto(data, self.addr)
            sock.close()
        except Exception:
            pass


class LoggedBlock(ModbusSequentialDataBlock):
    def __init__(self, kind: str, address: int, values: list[int], logger: logging.Logger, udp: UdpSink):
        super().__init__(address, values)
        self.kind = kind
        self.logger = logger
        self.udp = udp
    def getValues(self, address: int, count: int = 1) -> list[int]:
        vals = super().getValues(address, count)
        event = {"ts": utc_ts(), "event": "mb_read", "type": self.kind, "address": address, "count": count, "values": vals}
        self.logger.info("READ %-8s addr=%d count=%d -> %s", self.kind, address, count, vals)
        self.udp.emit(event)
        return vals
    def setValues(self, address: int, values: list[int]) -> None:
        super().setValues(address, values)
        event = {"ts": utc_ts(), "event": "mb_write", "type": self.kind, "address": address, "count": len(values), "values": values}
        self.logger.info("WRITE %-8s addr=%d count=%d <- %s", self.kind, address, len(values), values)
        self.udp.emit(event)


@dataclasses.dataclass
class PlcModel:
    coils: int = 64
    discretes: int = 64
    holdings: int = 64
    inputs: int = 64
    def bootstrap_values(self) -> Dict[str, list[int]]:
        rnd = random.Random(0xC0FFEE)
        return {
            "coils": [0] * self.coils,
            "discrete": [rnd.randint(0, 1) for _ in range(self.discretes)],
            "holding": [rnd.randint(100, 300) for _ in range(self.holdings)],
            "input": [rnd.randint(20, 80) for _ in range(self.inputs)],
        }   
