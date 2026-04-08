"""
WasteSorter — Server Python WebSocket
======================================
Avvio:  pip install websockets
        python wastesorter_server.py

La GUI si connette a ws://localhost:8765
Protocollo messaggi (JSON):

  GUI → Python:
    {"cmd": "start"}
    {"cmd": "stop"}
    {"cmd": "alarm"}
    {"cmd": "reset_alarm"}

  Python → GUI  (broadcast ogni ~50ms):
    {
      "obj": {
        "active": true/false,
        "x": -850.0,        # -1000..0  (nastro 1)
        "y": 0.0,           # 0..1000   (nastro 2, verso contenitore)
        "tipo": "plastica", # plastica|metallo|vetro|scarto|null
        "peso": 1.23,       # kg
        "induttanza": 0.45, # mH
        "capacitività": 12.3 # pF
      },
      "carrello": {
        "y": 0.0,           # posizione carrello su nastro 2
        "pusher": 0.0       # 0..1  (0=retratto, 1=completamente esteso)
      },
      "stato": "idle",      # idle|nastro1|scansione|nastro1b|nastro2|attesa|spinta|ritorno
      "alarm": false,
      "alarm_msg": ""
    }
"""

import asyncio
import json
import random
import time
import websockets
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("WasteSorter")

# ── Configurazione impianto ───────────────────────────────────
CFG = {
    "vel_nastro":   200.0,   # unità/s su asse X  (1000 unità = lunghezza nastro)
    "vel_carrello": 200.0,   # unità/s su asse Y
    "vel_pusher":   5.0,     # unità/s estensione (0→1)
    "x_start":     -1000.0, # posizione ingresso oggetto
    "x_scanner":   -500.0,  # dove si ferma per la scansione
    "x_fine":       0.0,     # fine nastro 1 / inizio nastro 2
    "t_scansione":  1.0,     # secondi di analisi
    "y_contenitori": {       # posizione Y di ogni contenitore su nastro 2
        "plastica": 250.0,
        "metallo":  500.0,
        "vetro":    750.0,
        "scarto":  1000.0,
    },
    "tick_s": 0.05,          # intervallo ciclo (50ms)
}

# ── Soglie sensori per classificazione ───────────────────────
#   In un impianto reale queste verrebbero dal PLC.
#   Qui usiamo range simulati per tipo.
PROFILI = {
    "plastica": {"peso": (0.05, 0.30), "induttanza": (0.01, 0.10), "capacitività": (15.0, 40.0)},
    "metallo":  {"peso": (0.40, 2.50), "induttanza": (5.0,  50.0), "capacitività": (1.0,  8.0)},
    "vetro":    {"peso": (0.20, 0.90), "induttanza": (0.01, 0.05), "capacitività": (5.0,  14.0)},
    "scarto":   {"peso": (0.01, 3.00), "induttanza": (0.01, 2.00), "capacitività": (1.0,  50.0)},
}

def genera_oggetto():
    """Crea un nuovo oggetto con proprietà fisiche casuali e lo classifica."""
    tipo = random.choices(
        ["plastica", "metallo", "vetro", "scarto"],
        weights=[40, 30, 20, 10]
    )[0]
    p = PROFILI[tipo]
    peso        = round(random.uniform(*p["peso"]),        3)
    induttanza  = round(random.uniform(*p["induttanza"]),  3)
    capacitività = round(random.uniform(*p["capacitività"]), 2)
    return {
        "tipo":        tipo,
        "peso":        peso,
        "induttanza":  induttanza,
        "capacitività": capacitività,
    }

# ── Stato macchina ────────────────────────────────────────────
class Impianto:
    def __init__(self):
        self.reset()

    def reset(self):
        self.stato       = "idle"      # idle|nastro1|scansione|nastro1b|nastro2|attesa|spinta|ritorno|rientro
        self.obj         = None        # dizionario oggetto corrente
        self.obj_x       = CFG["x_start"]
        self.obj_y       = 0.0
        self.scan_timer  = 0.0
        self.car_y       = 0.0        # posizione carrello
        self.pusher      = 0.0        # 0=retratto 1=esteso
        self.running     = False
        self.alarm       = False
        self.alarm_msg   = ""

    def start(self):
        if self.alarm:
            return
        self.running = True
        if self.stato == "idle":
            self._nuovo_oggetto()

    def stop(self):
        self.running = False
        self.stato   = "idle"
        self.obj     = None

    def set_alarm(self, msg="ALLARME"):
        self.alarm     = True
        self.alarm_msg = msg
        self.running   = False
        self.obj       = None
        self.stato     = "idle"
        log.warning(f"ALLARME: {msg}")

    def reset_alarm(self):
        self.alarm     = False
        self.alarm_msg = ""
        log.info("Allarme resettato")

    def _nuovo_oggetto(self):
        self.obj   = genera_oggetto()
        self.obj_x = CFG["x_start"]
        self.obj_y = 0.0
        self.stato = "nastro1"
        log.info(f"Nuovo oggetto: {self.obj}")

    def tick(self, dt: float):
        """Aggiorna lo stato dell'impianto di dt secondi."""
        if not self.running or self.alarm:
            return

        if self.stato == "nastro1":
            # Avanza verso lo scanner
            self.obj_x += CFG["vel_nastro"] * dt
            if self.obj_x >= CFG["x_scanner"]:
                self.obj_x   = CFG["x_scanner"]
                self.stato   = "scansione"
                self.scan_timer = CFG["t_scansione"]
                log.info(f"Scansione avviata ({self.obj['tipo']})")

        elif self.stato == "scansione":
            self.scan_timer -= dt
            if self.scan_timer <= 0:
                self.scan_timer = 0
                self.stato = "nastro1b"
                log.info("Scansione completata")

        elif self.stato == "nastro1b":
            # Avanza fino alla fine del nastro 1
            self.obj_x += CFG["vel_nastro"] * dt
            if self.obj_x >= CFG["x_fine"]:
                self.obj_x = CFG["x_fine"]
                self.stato = "nastro2"

        elif self.stato == "nastro2":
            # Scende sul nastro 2 verso il contenitore
            target_y = CFG["y_contenitori"][self.obj["tipo"]]
            self.obj_y += CFG["vel_nastro"] * dt
            if self.obj_y >= target_y:
                self.obj_y = target_y
                self.stato = "attesa"
                log.info(f"Oggetto in posizione Y={target_y}, attendo carrello")

        elif self.stato == "attesa":
            # Muovi il carrello verso l'oggetto
            target_y = CFG["y_contenitori"][self.obj["tipo"]]
            if self.car_y < target_y:
                self.car_y += CFG["vel_carrello"] * dt
                if self.car_y >= target_y:
                    self.car_y = target_y
                    self.stato = "spinta"
                    log.info("Carrello in posizione, avvio spinta")

        elif self.stato == "spinta":
            # Estendi il pusher
            self.pusher += CFG["vel_pusher"] * dt
            if self.pusher >= 1.0:
                self.pusher = 1.0
                self.stato  = "ritorno"
                self.obj    = None   # oggetto nel contenitore
                log.info("Oggetto smistato, ritiro pusher")

        elif self.stato == "ritorno":
            # Ritira il pusher
            self.pusher -= CFG["vel_pusher"] * dt
            if self.pusher <= 0.0:
                self.pusher = 0.0
                self.stato  = "rientro"
                log.info("Pusher rientrato, carrello torna a 0")

        elif self.stato == "rientro":
            # Carrello torna a posizione 0
            self.car_y -= CFG["vel_carrello"] * dt
            if self.car_y <= 0.0:
                self.car_y = 0.0
                self.stato = "idle"
                log.info("Carrello a 0 — pronto per prossimo oggetto")
                # Avvia subito il prossimo
                self._nuovo_oggetto()

    def stato_json(self) -> dict:
        """Serializza lo stato corrente da inviare alla GUI."""
        scan_progress = 0.0
        if self.stato == "scansione":
            scan_progress = round(1.0 - self.scan_timer / CFG["t_scansione"], 3)

        return {
            "obj": {
                "active":       self.obj is not None,
                "x":            round(self.obj_x, 1),
                "y":            round(self.obj_y, 1),
                "tipo":         self.obj["tipo"]         if self.obj else None,
                "peso":         self.obj["peso"]         if self.obj else None,
                "induttanza":   self.obj["induttanza"]   if self.obj else None,
                "capacitività": self.obj["capacitività"] if self.obj else None,
            },
            "carrello": {
                "y":      round(self.car_y, 1),
                "pusher": round(self.pusher, 3),
            },
            "stato":        self.stato,
            "scan_progress": scan_progress,
            "running":      self.running,
            "alarm":        self.alarm,
            "alarm_msg":    self.alarm_msg,
        }


# ── WebSocket server ──────────────────────────────────────────
impianto = Impianto()
clients: set = set()

async def handler(websocket):
    global clients
    clients.add(websocket)
    log.info(f"Client connesso: {websocket.remote_address}")
    try:
        async for raw in websocket:
            try:
                msg = json.loads(raw)
                cmd = msg.get("cmd", "")
                log.info(f"Comando ricevuto: {cmd}")

                if cmd == "start":
                    impianto.start()
                elif cmd == "stop":
                    impianto.stop()
                elif cmd == "alarm":
                    impianto.set_alarm(msg.get("msg", "ALLARME OPERATORE"))
                elif cmd == "reset_alarm":
                    impianto.reset_alarm()
                else:
                    log.warning(f"Comando sconosciuto: {cmd}")
            except json.JSONDecodeError:
                log.error(f"JSON non valido: {raw}")
    except websockets.exceptions.ConnectionClosedOK:
        pass
    except websockets.exceptions.ConnectionClosedError as e:
        log.warning(f"Connessione chiusa con errore: {e}")
    finally:
        clients.discard(websocket)
        log.info("Client disconnesso")

async def broadcast_loop():
    """Ciclo principale: tick impianto + broadcast stato a tutti i client."""
    global clients
    dt = CFG["tick_s"]
    while True:
        impianto.tick(dt)
        if clients:
            payload = json.dumps(impianto.stato_json())
            dead = set()
            for ws in clients:
                try:
                    await ws.send(payload)
                except websockets.exceptions.ConnectionClosed:
                    dead.add(ws)
            clients -= dead
        await asyncio.sleep(dt)

async def main():
    log.info("WasteSorter Server avviato su ws://localhost:8765")
    log.info("Apri wastesorter_gui.html nel browser, poi premi START")
    async with websockets.serve(handler, "localhost", 8765):
        await broadcast_loop()

if __name__ == "__main__":
    asyncio.run(main())
