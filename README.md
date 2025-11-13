# Mini-PLC-Honeypot

> **Scope (implemented):** Modbus/TCP only · no Web UI · no S7Comm · one UDP JSON log collector · rotating local file logs · **silent heartbeat** (internal updates).  
> **Code layout:** structured multi-file project with a thin `main.py` entry and a `mini_plc_hp/` package.

---

## 1) Prerequisites

- **OS:** Ubuntu 20.04 / 22.04 / 24.04 (NAT).
- **Python:** 3.8.x or 3.12.x.
- **Pinned library:** `pymodbus==3.7.4`.

---

## 2) Project Layout

```
mini-plc/
├─ requirements.txt        
├─ main.py                 # thin entry → mini_plc_hp/cli.py
└─ mini_plc_hp/
   ├─ __init__.py
   ├─ cli.py               # CLI: logger / server
   ├─ utils/
   │  ├─ __init__.py
   │  ├─ logging_setup.py  # rotating file logger + console
   │  └─ time.py           # UTC RFC3339 timestamps (...Z)
   ├─ logging/
   │  ├─ __init__.py
   │  └─ udp_server.py     # lightweight UDP JSON log collector
   └─ core/
      ├─ __init__.py
      ├─ datastore.py      # logged data blocks (mb_read / mb_write)
      └─ server.py         # Modbus server + silent heartbeat
```


---

## 3) Installation

From the project root:

```bash
# 1) Create & activate venv
python3 -m venv .venv
. .venv/bin/activate

# 2) Install pinned dependency
pip install -U pip
pip install -r requirements.txt   

# 3) Verify
python -c "import pymodbus; print('pymodbus', pymodbus.__version__)"
```

---

## 4) Run **separately** in two terminals

### Terminal A — UDP JSON log server
```bash
python main.py logger --host 0.0.0.0 --port 9000
```
- Aggregates incoming JSON to `./logs/central.log`.
- Prints lines like:
  ```
  REMOTE 127.0.0.1:54321 {"ts":"…Z","event":"mb_write","type":"holding","address":0,"count":1,"values":[123]}
  ```

### Terminal B — Modbus/TCP honeypot
```bash
python main.py server \
  --host 0.0.0.0 --port 5020 \
  --log-udp 127.0.0.1:9000 \
  --log-file ./logs/plc.log
```
- Listens at `0.0.0.0:5020/TCP`.
- Sends JSON events to the UDP collector (`127.0.0.1:9000`).
- Writes rotating local logs to `./logs/plc.log` (5 MB × 3 backups).

> If using `ufw`:  
> `sudo ufw allow 5020/tcp` and `sudo ufw allow 9000/udp`.

---

## 5) Data Model & Addressing

- Four areas, **64** elements each: `coils`, `discrete`, `holding`, `input`.
- **Unit ID:** `1` (fixed).
- **Address base:** **0-based** (`zero_mode=True`).
- **Writable:** Coils (FC5/FC15), Holding Registers (FC6/FC16).  
  **Read-only:** Discrete Inputs (FC2), Input Registers (FC4).

> Many clients default to “1-based” (e.g., 40001). Use a 0-based switch or subtract 1.

---

## 6) Heartbeat (silent)

- A background task updates the first three **Input Registers** ~every 3 s (to look “alive”).
- Updates are **silent** (call the base data-block method), thus **no** `WRITE input …` lines are produced.
- A `heartbeat` JSON is emitted via UDP (not in INFO-level file logs):
```json
{"ts":"2025-11-13T02:02:18.001Z","event":"heartbeat","beat":42}
```

---

## 7) Telemetry

### 7.1 Local rotating log (`--log-file`)
- Logs **client-triggered** Modbus ops at INFO level:
```
2025-11-13 10:02:15,123 [INFO] READ  holding  addr=0 count=3 -> [155, 201, 142]
2025-11-13 10:02:15,234 [INFO] WRITE coils    addr=0 count=1 <- [1]
```

### 7.2 UDP JSON events (`--log-udp` + `logger`)
- One JSON per line. Fields:
  - `ts`: UTC RFC3339 timestamp (…Z)
  - `event`: `mb_read` | `mb_write` | `heartbeat`
  - `type`: `coils` | `discrete` | `holding` | `input`
  - `address`, `count`, `values` (Modbus ops)
  - `beat` (heartbeat)
- Examples:
```json
{"ts":"2025-11-13T02:02:15.456Z","event":"mb_write","type":"holding","address":0,"count":1,"values":[123]}
{"ts":"2025-11-13T02:02:15.789Z","event":"mb_read","type":"coils","address":0,"count":8,"values":[1,0,0,0,0,0,0,0]}
{"ts":"2025-11-13T02:02:18.001Z","event":"heartbeat","beat":7}
```

---

## 8) Cross-VM Sanity Test (attacker side)

On another VM reachable to the honeypot:

```bash
python3 -m pip install "pymodbus==3.7.4"
python3 - <<'PY'
from pymodbus.client import ModbusTcpClient
IP, PORT = "<HONEYPOT_IP>", 5020
c = ModbusTcpClient(IP, port=PORT)
print("connect:", c.connect())

print("holding:", c.read_holding_registers(0, count=3, slave=1).registers)
c.write_coil(0, True, slave=1)
print("coils:", list(c.read_coils(0, count=8, slave=1).bits))

c.close()
PY
```

Expected:
- Server terminal shows `READ/WRITE …` lines.
- UDP logger prints the corresponding JSON events and writes `./logs/central.log`.
```

