import dataclasses
import time
from collections import deque
from typing import Deque, Dict, List, Tuple


@dataclasses.dataclass(frozen=True)
class IdsConfig:
    write_burst_threshold: int = 5
    write_burst_window_s: float = 10.0
    bulk_write_count: int = 10
    scan_read_count: int = 32


Alert = Dict[str, object]


class IdsEngine:
    def __init__(self, config: IdsConfig):
        self.config = config
        self._write_history: Dict[str, Deque[float]] = {}

    def process_event(self, event: Dict[str, object], src: Tuple[str, int]) -> List[Alert]:
        alerts: List[Alert] = []
        event_type = str(event.get("event", ""))
        data_type = str(event.get("type", ""))
        count = int(event.get("count", 0) or 0)
        src_key = f"{src[0]}:{src[1]}"
        now = time.time()

        if event_type == "mb_write":
            alerts.extend(self._check_write_burst(src_key, now, event))
            if count >= self.config.bulk_write_count:
                alerts.append(self._make_alert("bulk_write", src_key, event, extra={"count": count}))
            if data_type in {"input", "discrete"}:
                alerts.append(self._make_alert("write_readonly_area", src_key, event, extra={"type": data_type}))

        if event_type == "mb_read":
            if count >= self.config.scan_read_count:
                alerts.append(self._make_alert("possible_scan", src_key, event, extra={"count": count}))

        return alerts

    def _check_write_burst(self, src_key: str, now: float, event: Dict[str, object]) -> List[Alert]:
        history = self._write_history.setdefault(src_key, deque())
        history.append(now)
        window = self.config.write_burst_window_s
        while history and now - history[0] > window:
            history.popleft()
        if len(history) >= self.config.write_burst_threshold:
            return [self._make_alert("write_burst", src_key, event, extra={"hits": len(history)})]
        return []

    def _make_alert(
        self,
        rule: str,
        src_key: str,
        event: Dict[str, object],
        extra: Dict[str, object],
    ) -> Alert:
        alert: Alert = {
            "ts": event.get("ts"),
            "rule": rule,
            "src": src_key,
            "event": event,
        }
        alert.update(extra)
        return alert
