# ══════════════════════════════════════════════════════════════
# plc_config.py
# Configurazione centralizzata — modifica qui, vale per tutto
# ══════════════════════════════════════════════════════════════

# ── Connessione PLC ───────────────────────────────────────────
PLC_IP   = "192.168.0.44"
RACK     = 0
SLOT     = 1
DB_NUM   = 1          # numero del Data Block principale

# ── Timing ───────────────────────────────────────────────────
SENSOR_WRITE_INTERVAL = 10.0   # secondi tra una scrittura sensori e la prossima
HMI_TICK              = 0.05   # secondi ciclo HMI bridge (50 ms)
PLC_READ_INTERVAL     = 0.05   # secondi tra una lettura PLC e la prossima

# ── WebSocket ─────────────────────────────────────────────────
WS_HOST = "localhost"
WS_PORT = 8765

# ══════════════════════════════════════════════════════════════
# MAPPA VARIABILI PLC
# Per ogni variabile specificare:
#   offset : byte offset nel DB (intero)
#   type   : 'real' | 'int' | 'bool' | 'dint'
#   bit    : (solo per bool) numero del bit nel byte (0–7)
#   mode   : 'read' | 'write' | 'readwrite'
#
# ⚠️  COMPLETARE con i valori reali del tuo DB prima dell'uso
# ══════════════════════════════════════════════════════════════

VAR_MAP = {

    # ── Sensori in ingresso (scritti da Python → PLC) ─────────

    "peso": {
        "offset": 2,
        "type":   "real",
        "mode":   "write",
    },

    "val_induttivo": {
        "offset": 0,
        "type":   "bool",
        "bit":    2,
        "mode":   "write",
    },

    "val_capacitivo": {
        "offset": 0,
        "type":   "bool",
        "bit":    3,
        "mode":   "write",
    },

    # ── Comandi impianto (scritti da HmiBridge → PLC) ─────────
    # Il PLC gestisce internamente la logica start/stop/alarm.
    # Python scrive solo l'impulso, non legge stato.

    "Sistema_START": {
        "offset": 28,        # ← da verificare
        "type":   "bool",
        "bit":    0,        # ← da verificare
        "mode":   "write",
    },

    "Sistema_STOP": {
        "offset": 28,        # ← da verificare
        "type":   "bool",
        "bit":    1,        # ← da verificare
        "mode":   "write",
    },

    "Allarme_generale": {
        "offset": 34,        # ← da verificare
        "type":   "bool",
        "bit":    0,        # ← da verificare
        "mode":   "read",   # letto per sapere se c'è allarme attivo
    },

    "Sistema_ANNULLA_ALLARMI": {
        "offset": 28,        # ← da verificare
        "type":   "bool",
        "bit":    2,        # ← da verificare
        "mode":   "write",
    },

    # ── Posizioni (lette dal PLC → mandate alla GUI) ──────────

    "tipo_oggetto": {
        "offset": 8,
        "type":   "int",
        "mode":   "read",
    },

    "posizione_carrello": {
        "offset": 12,
        "type":   "int",
        "mode":   "read",
    },

    "posizione_oggetto_y": {
        "offset": 20,
        "type":   "real",
        "mode":   "read",
    },

    "posizione_oggetto_x": {
        "offset": 24,
        "type":   "real",
        "mode":   "read",
    },

    "Pusher_avanza": {
        "offset": 10,
        "type":   "bool",
        "bit":    1,
        "mode":   "read",
    },

    "Pusher_rientra": {
        "offset": 10,
        "type":   "bool",
        "bit":    2,
        "mode":   "read",
    },
}

# ── Mappa codice tipo PLC → stringa per la GUI ────────────────
TIPO_MAP = {
    0: None,
    1: "plastica",
    2: "metallo",
    3: "vetro",
    4: "scarto",
    5: "scarto",   # eventuali tipi extra vanno a scarto
}

# ── Profili sensori per la generazione simulata ───────────────
# Usati da SensorWriter per generare valori realistici per tipo
# (in un impianto reale verrebbero dai sensori fisici)
SENSOR_PROFILES = {
    "plastica": {"peso": (0.05, 0.30), "p_induttivo": 0.05, "p_capacitivo": 0.80},
    "metallo":  {"peso": (0.40, 2.50), "p_induttivo": 0.95, "p_capacitivo": 0.10},
    "vetro":    {"peso": (0.20, 0.90), "p_induttivo": 0.05, "p_capacitivo": 0.30},
    "scarto":   {"peso": (0.01, 3.00), "p_induttivo": 0.40, "p_capacitivo": 0.40},
}
