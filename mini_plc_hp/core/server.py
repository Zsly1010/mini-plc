import asyncio, logging
from typing import Optional, Tuple


from pymodbus.datastore import ModbusServerContext, ModbusSlaveContext
from pymodbus.server import StartAsyncTcpServer
from pymodbus.datastore import ModbusSequentialDataBlock


from .datastore import LoggedBlock, PlcModel, UdpSink
from ..utils.logging_setup import make_logger
from ..utils.time import utc_ts


async def periodic_plc_task(ctx: ModbusServerContext, logger: logging.Logger, udp: UdpSink) -> None:
    unit_id = 1
    beat = 0
    while True:
        slave = ctx[unit_id]
        ir: ModbusSequentialDataBlock = slave.store['i'] # type: ignore
        # Update first few input registers (silent — no WRITE logs)
        for off in range(0, 3):
            from random import uniform
            val = int(40 + 5 * uniform(-1, 1))
            ModbusSequentialDataBlock.setValues(ir, off, [val]) # bypass logging
        beat += 1
        udp.emit({"ts": utc_ts(), "event": "heartbeat", "beat": beat})
        logger.debug("heartbeat %d", beat)
        await asyncio.sleep(3.0)


async def run_modbus_server(host: str, port: int, log_file: Optional[str], udp_addr: Optional[Tuple[str, int]]) -> None:
    logger = make_logger("plc", log_file=log_file)
    udp = UdpSink(addr=udp_addr)

    # Build datastore
    model = PlcModel()
    init = model.bootstrap_values()
    block_coils = LoggedBlock("coils", 0, init["coils"], logger, udp)
    block_discr = LoggedBlock("discrete", 0, init["discrete"], logger, udp)
    block_hold = LoggedBlock("holding", 0, init["holding"], logger, udp)
    block_input = LoggedBlock("input", 0, init["input"], logger, udp)


    store = ModbusSlaveContext(di=block_discr, co=block_coils, hr=block_hold, ir=block_input, zero_mode=True)
    context = ModbusServerContext(slaves={1: store}, single=False)


    logger.info("Starting Modbus/TCP honeypot on %s:%d (pymodbus 3.7.4)", host, port)
    if udp.addr:
        logger.info("Shipping JSON logs to udp://%s:%d", udp.addr[0], udp.addr[1])
    else:
        logger.info("UDP shipping disabled (no --log-udp specified)")


    periodic_task = asyncio.create_task(periodic_plc_task(context, logger, udp))
    try:
        await StartAsyncTcpServer(context=context, address=(host, port))
    finally:
        periodic_task.cancel()
        try:
            await periodic_task
        except Exception:
            pass
