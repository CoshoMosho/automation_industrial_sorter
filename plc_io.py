# ══════════════════════════════════════════════════════════════
# plc_io.py
# Layer snap7 condiviso — connessione, lettura, scrittura
# Usato da SensorWriter e HmiBridge tramite PlcConnection
# ══════════════════════════════════════════════════════════════

import struct
import threading
import logging
import snap7
from plc_config import PLC_IP, RACK, SLOT, DB_NUM, VAR_MAP

log = logging.getLogger("PlcIO")

# Dimensione massima del DB da leggere in un blocco unico
DB_READ_SIZE = 34


class PlcConnection:
    """
    Connessione snap7 thread-safe al PLC.
    Espone read_var() e write_var() che accedono al DB
    tramite un lock per evitare accessi concorrenti.
    """

    def __init__(self):
        self._client = snap7.client.Client()
        self._lock   = threading.Lock()
        self._connected = False

    # ── Connessione ───────────────────────────────────────────

    def connect(self):
        try:
            self._client.connect(PLC_IP, RACK, SLOT)
            self._connected = self._client.get_connected()
            if self._connected:
                log.info(f"Connesso al PLC {PLC_IP}")
            else:
                log.error("Connessione snap7 fallita (get_connected = False)")
        except Exception as e:
            self._connected = False
            log.error(f"Errore connessione PLC: {e}")
        return self._connected

    def disconnect(self):
        try:
            self._client.disconnect()
            log.info("Disconnesso dal PLC")
        except Exception:
            pass
        self._connected = False

    @property
    def connected(self):
        return self._connected

    # ── Lettura intera ────────────────────────────────────────

    def read_db(self) -> bytearray | None:
        """Legge l'intero DB in un unico blocco. Thread-safe."""
        if not self._connected:
            return None
        with self._lock:
            try:
                return bytearray(self._client.db_read(DB_NUM, 0, DB_READ_SIZE))
            except Exception as e:
                log.warning(f"Errore lettura DB: {e}")
                self._connected = False
                return None

    def write_db(self, db: bytearray):
        """Scrive l'intero DB. Thread-safe."""
        if not self._connected:
            return
        with self._lock:
            try:
                self._client.db_write(DB_NUM, 0, db)
            except Exception as e:
                log.warning(f"Errore scrittura DB: {e}")
                self._connected = False

    # ── Lettura singola variabile ─────────────────────────────

    def read_var(self, name: str, db: bytearray = None) -> object:
        """
        Legge una variabile per nome dalla VAR_MAP.
        Se db è fornito lo usa (più efficiente in un ciclo),
        altrimenti fa una lettura fresca dal PLC.
        """
        if name not in VAR_MAP:
            raise KeyError(f"Variabile '{name}' non in VAR_MAP")
        cfg = VAR_MAP[name]
        if db is None:
            db = self.read_db()
        if db is None:
            return None
        return _decode(db, cfg)

    # ── Scrittura singola variabile ───────────────────────────

    def write_var(self, name: str, value: object):
        """
        Scrive una variabile per nome.
        Legge il DB, modifica il byte/bit, riscrive.
        Thread-safe grazie al lock interno.
        """
        if name not in VAR_MAP:
            raise KeyError(f"Variabile '{name}' non in VAR_MAP")
        cfg = VAR_MAP[name]
        if cfg.get("mode") == "read":
            log.warning(f"Tentativo di scrivere variabile read-only: {name}")
            return
        with self._lock:
            try:
                db = bytearray(self._client.db_read(DB_NUM, 0, DB_READ_SIZE))
                _encode(db, cfg, value)
                self._client.db_write(DB_NUM, 0, db)
            except Exception as e:
                log.warning(f"Errore scrittura '{name}': {e}")
                self._connected = False

    # ── Scrittura multipla (un solo read-modify-write) ────────

    def write_vars(self, values: dict):
        """
        Scrive più variabili in un solo ciclo read-modify-write.
        values: {'nome_var': valore, ...}
        """
        with self._lock:
            try:
                db = bytearray(self._client.db_read(DB_NUM, 0, DB_READ_SIZE))
                for name, value in values.items():
                    if name not in VAR_MAP:
                        log.warning(f"Variabile sconosciuta: {name}")
                        continue
                    cfg = VAR_MAP[name]
                    if cfg.get("mode") == "read":
                        continue
                    _encode(db, cfg, value)
                self._client.db_write(DB_NUM, 0, db)
            except Exception as e:
                log.warning(f"Errore scrittura multipla: {e}")
                self._connected = False


# ── Helpers decode/encode ─────────────────────────────────────

def _decode(db: bytearray, cfg: dict) -> object:
    off = cfg["offset"]
    t   = cfg["type"]
    if t == "real":
        return round(struct.unpack_from(">f", db, off)[0], 4)
    elif t == "int":
        return struct.unpack_from(">h", db, off)[0]
    elif t == "dint":
        return struct.unpack_from(">i", db, off)[0]
    elif t == "bool":
        bit = cfg.get("bit", 0)
        return bool(db[off] & (1 << bit))
    else:
        raise ValueError(f"Tipo sconosciuto: {t}")


def _encode(db: bytearray, cfg: dict, value: object):
    off = cfg["offset"]
    t   = cfg["type"]
    if t == "real":
        struct.pack_into(">f", db, off, float(value))
    elif t == "int":
        struct.pack_into(">h", db, off, int(value))
    elif t == "dint":
        struct.pack_into(">i", db, off, int(value))
    elif t == "bool":
        bit = cfg.get("bit", 0)
        if value:
            db[off] |= (1 << bit)
        else:
            db[off] &= ~(1 << bit)
    else:
        raise ValueError(f"Tipo sconosciuto: {t}")
