# ══════════════════════════════════════════════════════════════
# main.py
# Punto di ingresso — avvia connessione PLC, SensorWriter
# e HmiBridge in un unico processo.
#
# Avvio:
#   pip install snap7 websockets
#   python main.py
#
# Struttura:
#   PlcConnection (snap7, thread-safe)
#       │
#       ├── SensorWriter  — thread, scrive sensori ogni N sec
#       └── HmiBridge     — asyncio, WebSocket + ciclo lettura PLC
# ══════════════════════════════════════════════════════════════

import asyncio
import logging
import signal
import sys

from plc_io      import PlcConnection
from sensor_writer import SensorWriter
from hmi_bridge  import HmiBridge

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger("Main")


async def main():
    # ── 1. Connessione PLC ────────────────────────────────────
    plc = PlcConnection()
    connected = plc.connect()

    if not connected:
        log.warning(
            "⚠️  PLC non raggiungibile all'avvio. "
            "Il sistema parte comunque: la GUI mostrerà "
            "'PLC NON CONNESSO' finché il collegamento non si stabilisce."
        )

    # ── 2. SensorWriter (thread) ──────────────────────────────
    sensor_writer = SensorWriter(plc)
    sensor_writer.start()

    # ── 3. HmiBridge (asyncio) ────────────────────────────────
    bridge = HmiBridge(plc, sensor_writer)

    # ── 4. Gestione Ctrl+C ────────────────────────────────────
    loop = asyncio.get_running_loop()

    def shutdown(sig, frame):
        log.info(f"Segnale {sig.name} ricevuto — chiusura in corso...")
        sensor_writer.stop()
        plc.disconnect()
        loop.stop()

    # Su Windows signal.SIGTERM non è sempre disponibile
    for s in (signal.SIGINT,):
        try:
            loop.add_signal_handler(s, lambda s=s: shutdown(s, None))
        except NotImplementedError:
            signal.signal(s, shutdown)

    log.info("Sistema avviato. Apri wastesorter_gui.html nel browser.")
    log.info("Ctrl+C per fermare.")

    try:
        await bridge.run()
    except KeyboardInterrupt:
        pass
    finally:
        sensor_writer.stop()
        plc.disconnect()
        log.info("Sistema fermato.")


if __name__ == "__main__":
    asyncio.run(main())
