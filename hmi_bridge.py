# ══════════════════════════════════════════════════════════════
# hmi_bridge.py
# WebSocket server: riceve comandi dalla GUI (start/stop/allarmi)
# e li scrive sul PLC. Legge posizioni dal PLC ogni HMI_TICK.
#
# Comandi GUI → PLC:
#   start          → impulso Sistema_START
#   stop           → impulso Sistema_STOP  (+ reset GUI)
#   alarm          → impulso Allarme_generale (GUI si resetta)
#   reset_alarm    → impulso Sistema_ANNULLA_ALLARMI
#
# PLC → GUI (ogni 50ms):
#   posizione_oggetto_x/y, posizione_carrello,
#   Pusher_avanza, Pusher_rientra, tipo_oggetto,
#   Allarme_generale
# ══════════════════════════════════════════════════════════════

import asyncio
import json
import logging
import websockets
from plc_config import WS_HOST, WS_PORT, HMI_TICK, TIPO_MAP, VAR_MAP
from plc_io import PlcConnection, _decode

log = logging.getLogger("HmiBridge")

clients: set = set()

# Quanto tempo (s) tenere un impulso bool alto prima di riabbassarlo
PULSE_DURATION = 0.2


class HmiBridge:

    def __init__(self, plc: PlcConnection, sensor_writer=None):
        self._plc   = plc
        self._sw    = sensor_writer
        self._alarm     = False
        self._alarm_msg = ""
        self._counts    = {"plastica": 0, "metallo": 0, "vetro": 0, "scarto": 0}
        self._obj_props = {"tipo": None, "peso": None, "induttanza": None, "capacitività": None}
        # Traccia se l'oggetto è attualmente sul nastro
        self._obj_on_belt    = False
        # Stato precedente pusher (per rilevare fronte di discesa)
        self._prev_pusher_av = False
        self._prev_pusher_ri = False
        self._prev_car_y     = 0.0

    # ── Entry point ───────────────────────────────────────────

    async def run(self):
        log.info(f"HMI WebSocket su ws://{WS_HOST}:{WS_PORT}")
        async with websockets.serve(self._handler, WS_HOST, WS_PORT):
            await self._broadcast_loop()

    # ── Handler connessioni ───────────────────────────────────

    async def _handler(self, websocket):
        global clients
        clients.add(websocket)
        log.info(f"GUI connessa: {websocket.remote_address}")
        try:
            async for raw in websocket:
                await self._handle_cmd(raw)
        except websockets.exceptions.ConnectionClosedOK:
            pass
        except websockets.exceptions.ConnectionClosedError as e:
            log.warning(f"GUI disconnessa con errore: {e}")
        finally:
            clients.discard(websocket)
            log.info("GUI disconnessa")

    # ── Comandi GUI ───────────────────────────────────────────

    async def _handle_cmd(self, raw: str):
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            log.error(f"JSON non valido: {raw}")
            return

        cmd = msg.get("cmd", "")
        log.info(f"Comando GUI: {cmd}")

        if cmd == "start":
            # Impulso Sistema_START
            await self._pulse("Sistema_START")
            self._alarm = False
            self._alarm_msg = ""

        elif cmd == "stop":
            await self._pulse("Sistema_STOP")
            self._alarm     = False
            self._alarm_msg = ""
            self._counts    = {"plastica": 0, "metallo": 0, "vetro": 0, "scarto": 0}
            self._obj_props = {"tipo": None, "peso": None, "induttanza": None, "capacitività": None}

        elif cmd == "alarm":
            self._alarm     = True
            self._alarm_msg = msg.get("msg", "ALLARME OPERATORE")
            await self._pulse("Sistema_STOP")
            self._counts    = {"plastica": 0, "metallo": 0, "vetro": 0, "scarto": 0}
            self._obj_props = {"tipo": None, "peso": None, "induttanza": None, "capacitività": None}
            log.warning(f"ALLARME: {self._alarm_msg}")

        elif cmd == "reset_alarm":
            # Impulso Sistema_ANNULLA_ALLARMI
            await self._pulse("Sistema_ANNULLA_ALLARMI")
            self._alarm     = False
            self._alarm_msg = ""
            log.info("Allarme annullato")

    async def _pulse(self, var_name: str):
        """Scrive TRUE, aspetta PULSE_DURATION, riscrive FALSE."""
        if not self._plc.connected:
            log.warning(f"PLC non connesso, impulso '{var_name}' ignorato")
            return
        self._plc.write_var(var_name, True)
        await asyncio.sleep(PULSE_DURATION)
        self._plc.write_var(var_name, False)

    # ── Ciclo broadcast ───────────────────────────────────────

    async def _broadcast_loop(self):
        global clients
        while True:
            if clients:
                payload = self._build_payload()
                dead = set()
                for ws in clients:
                    try:
                        await ws.send(payload)
                    except websockets.exceptions.ConnectionClosed:
                        dead.add(ws)
                clients -= dead
            await asyncio.sleep(HMI_TICK)

    # ── Costruzione payload ───────────────────────────────────

    def _build_payload(self) -> str:

        _ERR = lambda msg: json.dumps({
            "plc_connected": False, "alarm": True, "alarm_msg": msg,
            "obj": {"active": False, "x": -1000, "y": 0,
                    "tipo": None, "peso": None,
                    "induttanza": None, "capacitività": None},
            "carrello": {"y": 0, "pusher": 0},
            "stato": "idle", "scan_progress": 0,
            "running": False, "counts": dict(self._counts),
        })

        if not self._plc.connected:
            return _ERR("PLC NON CONNESSO")

        db = self._plc.read_db()
        if db is None:
            return _ERR("ERRORE LETTURA DB")

        def rd(name, default=None):
            if name not in VAR_MAP:
                return default
            try:
                return _decode(db, VAR_MAP[name])
            except Exception:
                return default

        # ── Leggi variabili PLC ───────────────────────────────
        obj_x        = float(rd("posizione_oggetto_x", -1000.0))
        obj_y        = float(rd("posizione_oggetto_y", 0.0))
        tipo_id      = int(rd("tipo_oggetto", 0))
        tipo         = TIPO_MAP.get(tipo_id)          # None se 0
        car_y        = float(rd("posizione_carrello", 0))
        push_avanza  = bool(rd("Pusher_avanza",  False))
        push_rientra = bool(rd("Pusher_rientra", False))
        allarme_plc  = bool(rd("Allarme_generale", False))

        alarm     = self._alarm or allarme_plc
        alarm_msg = self._alarm_msg if self._alarm else ("ALLARME PLC" if allarme_plc else "")

        # ── Pusher 0..1 per animazione ────────────────────────
        pusher = 0.6 if push_avanza else (0.3 if push_rientra else 0.0)

        # ── Oggetto attivo: visibile da x>-999 fino a pusher ritirato ──
        # L'oggetto è "in giro" quando x è tra -999 e 0 oppure y>0,
        # ma NON quando sia x=-1000 (fuori nastro) sia pusher=0 dopo spinta.
        # Usiamo una variabile di stato interna _obj_on_belt.
        x_in_belt = obj_x > -999.0                  # è sul nastro 1
        y_in_belt = obj_y > 5.0                     # è sul nastro 2
        pusher_active = push_avanza or push_rientra  # in fase spinta/ritiro

        if not self._obj_on_belt:
            # Inizia il ciclo quando l'oggetto entra sul nastro
            if x_in_belt:
                self._obj_on_belt = True
                # Congela le proprietà sensori al momento dell'ingresso
                sw = self._sw.last_values if self._sw else {}
                peso    = sw.get("peso")
                val_ind = sw.get("val_induttivo")
                val_cap = sw.get("val_capacitivo")
                self._obj_props = {
                    "tipo":          tipo,
                    "peso":          peso,
                    "induttanza":    round(float(val_ind)*45+0.5, 2) if val_ind is not None else None,
                    "capacitività":  round(float(val_cap)*28+2.0, 2) if val_cap is not None else None,
                }
                log.info(f"Oggetto entrato. Props: {self._obj_props}")
        else:
            # Aggiorna tipo quando disponibile (scanner lo determina)
            if tipo is not None and self._obj_props.get("tipo") is None:
                self._obj_props["tipo"] = tipo
                log.info(f"Tipo identificato: {tipo}")

            # Fine ciclo: pusher si è ritirato e carrello torna
            # → l'oggetto è nel contenitore
            if self._prev_pusher_ri and not push_rientra and not push_avanza:
                # Smistamento completato
                t   = self._obj_props.get("tipo") or "scarto"
                cat = t if t in self._counts else "scarto"
                self._counts[cat] += 1
                log.info(f"✓ Smistato → {cat}  totali={self._counts}")
                self._obj_on_belt = False
                self._obj_props   = {"tipo": None, "peso": None,
                                     "induttanza": None, "capacitività": None}

        self._prev_pusher_av = push_avanza
        self._prev_pusher_ri = push_rientra
        self._prev_car_y     = car_y

        obj_active = self._obj_on_belt and not alarm

        # ── Stato ciclo ───────────────────────────────────────
        stato = _derive_stato(obj_x, obj_y, car_y, push_avanza, push_rientra, alarm,
                              self._obj_on_belt)

        return json.dumps({
            "plc_connected": True,
            "obj": {
                "active":       obj_active,
                "x":            round(obj_x, 1),
                "y":            round(obj_y, 1),
                "tipo":         self._obj_props.get("tipo"),
                "peso":         self._obj_props.get("peso"),
                "induttanza":   self._obj_props.get("induttanza"),
                "capacitività": self._obj_props.get("capacitività"),
            },
            "carrello": {
                "y":      round(car_y, 1),
                "pusher": pusher,
            },
            "stato":         stato,
            "scan_progress": 0.0,
            "running":       not alarm,
            "alarm":         alarm,
            "alarm_msg":     alarm_msg,
            "counts":        dict(self._counts),
        })


def _derive_stato(obj_x, obj_y, car_y, push_av, push_ri, alarm, on_belt) -> str:
    if alarm:
        return "idle"
    if push_av:
        return "spinta"
    if push_ri:
        return "ritorno"
    if car_y > 30:
        # carrello in movimento o in posizione
        if obj_y > 5 and abs(car_y - obj_y) < 30:
            return "attesa"    # carrello arrivato vicino all'oggetto
        if obj_y < 5:
            return "rientro"   # oggetto già smistato, carrello rientra
        return "attesa"
    if obj_y > 5:
        return "nastro2"
    if not on_belt:
        return "idle"
    # su nastro 1
    if -510 <= obj_x <= -490:
        return "scansione"
    if obj_x > -490:
        return "nastro1b"
    return "nastro1"
