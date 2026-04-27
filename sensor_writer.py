# ══════════════════════════════════════════════════════════════
# sensor_writer.py
# Genera e scrive le proprietà fisiche dell'oggetto sul PLC.
# Gira in un thread separato, ciclo lento (SENSOR_WRITE_INTERVAL).
#
# In un impianto reale questo modulo leggerebbe i valori
# dai sensori fisici (bilancia, bobina induttiva, sensore
# capacitivo) invece di simularli.
# ══════════════════════════════════════════════════════════════

import random
import threading
import time
import logging
from plc_config import SENSOR_WRITE_INTERVAL, SENSOR_PROFILES
from plc_io import PlcConnection

log = logging.getLogger("SensorWriter")


def _genera_valori(tipo: str | None = None) -> dict:
    """
    Genera peso, val_induttivo e val_capacitivo simulati.
    Se tipo è None sceglie un tipo casuale con pesi realistici.
    """
    if tipo is None:
        tipo = random.choices(
            ["plastica", "metallo", "vetro", "scarto"],
            weights=[40, 30, 20, 10]
        )[0]

    p = SENSOR_PROFILES[tipo]
    peso        = round(random.uniform(*p["peso"]), 3)
    val_ind     = random.random() < p["p_induttivo"]
    val_cap     = random.random() < p["p_capacitivo"]

    log.info(
        f"Sensori generati → tipo={tipo} "
        f"peso={peso:.3f} kg  ind={val_ind}  cap={val_cap}"
    )

    return {
        "peso":          peso,
        "val_induttivo": val_ind,
        "val_capacitivo": val_cap,
    }


class SensorWriter:
    """
    Thread che scrive periodicamente i valori sensori nel DB del PLC.
    Si ferma impostando _stop_event.
    """

    def __init__(self, plc: PlcConnection):
        self._plc        = plc
        self._stop_event = threading.Event()
        self._thread     = threading.Thread(
            target=self._loop,
            name="SensorWriter",
            daemon=True,
        )
        # Ultimo set di valori generati (leggibile dall'esterno)
        self.last_values: dict = {}

    def start(self):
        log.info("SensorWriter avviato")
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        self._thread.join(timeout=5)
        log.info("SensorWriter fermato")

    def _loop(self):
        while not self._stop_event.is_set():
            if self._plc.connected:
                values = _genera_valori()
                self._plc.write_vars(values)
                self.last_values = values
            else:
                log.warning("SensorWriter: PLC non connesso, skip")

            # Attende SENSOR_WRITE_INTERVAL ma reagisce allo stop
            self._stop_event.wait(timeout=SENSOR_WRITE_INTERVAL)
