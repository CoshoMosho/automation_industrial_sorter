# WasteSorter — Documentazione di Progetto

> 🇬🇧 **English version available at the bottom of this document** — [jump to English](#wastesorter--project-documentation)

---

https://github.com/user-attachments/assets/5289765f-fcd6-4f10-8f9d-9a3cef2a69e2



## Indice

1. [Panoramica del sistema](#1-panoramica-del-sistema)
2. [Architettura generale](#2-architettura-generale)
3. [Elenco file del progetto](#3-elenco-file-del-progetto)
4. [Descrizione del processo fisico](#4-descrizione-del-processo-fisico)
5. [Interfaccia HMI — GUI Web](#5-interfaccia-hmi--gui-web)
6. [Python — Simulazione con WebSocket](#6-python--simulazione-con-websocket)
7. [Python — Bridge PLC reale (snap7)](#7-python--bridge-plc-reale-snap7)
8. [PLC Siemens S7 / TIA Portal v17](#8-plc-siemens-s7--tia-portal-v17)
9. [Limitazione attuale: licenza TIA Portal scaduta](#9-limitazione-attuale-licenza-tia-portal-scaduta)
10. [Avvio rapido — modalità simulazione](#10-avvio-rapido--modalità-simulazione)
11. [Avvio completo — modalità PLC reale](#11-avvio-completo--modalità-plc-reale)
12. [Protocollo WebSocket](#12-protocollo-websocket)
13. [Sviluppi futuri](#13-sviluppi-futuri)

---

## 1. Panoramica del sistema

WasteSorter è un impianto di smistamento automatico che riceve oggetti misti su nastro trasportatore, li analizza tramite sensori (peso, induttanza, capacitività), ne determina la tipologia (plastica, metallo, vetro, scarto) e li invia al contenitore corretto tramite un sistema a carrello e pusher.

Il progetto è composto da tre livelli:

- **Livello campo**: PLC Siemens S7 con logica Ladder/SCL programmata in TIA Portal v17
- **Livello supervisione**: script Python che gestisce la logica di processo e comunica con la GUI; nella versione con PLC fisico legge e scrive le variabili tramite snap7
- **Livello HMI**: interfaccia grafica web in HTML/JS con aggiornamento in tempo reale via WebSocket

---

## 2. Architettura generale

```
┌─────────────────────────────────────────────────────────────┐
│                     IMPIANTO FISICO                         │
│  Nastro 1 ──► Scanner ──► Nastro 2 ──► Carrello/Pusher      │
│                                    ──► Contenitori (4)       │
└───────────────────────┬─────────────────────────────────────┘
                        │ I/O fisici
┌───────────────────────▼─────────────────────────────────────┐
│              PLC SIEMENS S7  —  TIA Portal v17              │
│              plc_industrial_sorter.zap17                     │
└───────────────────────┬─────────────────────────────────────┘
                        │ snap7 (lettura/scrittura DB)
                        │
              ┌─────────▼──────────┐
              │  plc_snap7_bridge  │  ← con PLC reale (non attivo)
              └─────────┬──────────┘
                        │   oppure, in sostituzione:
              ┌─────────▼──────────┐
              │ wastesorter_server │  ← simulazione standalone
              └─────────┬──────────┘
                        │ WebSocket  ws://localhost:8765
┌───────────────────────▼─────────────────────────────────────┐
│              wastesorter_gui.html                            │
│  Vista dall'alto: nastri, oggetto, carrello, contenitori     │
│  Comandi: AVVIA / STOP / EMERGENZA / AZZERA ALLARME          │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Elenco file del progetto

| File | Descrizione |
|------|-------------|
| `wastesorter_gui.html` | Interfaccia HMI web — client WebSocket, visualizzazione animata dell'impianto |
| `wastesorter_server.py` | Server WebSocket + simulazione completa del processo, senza PLC |
| `main.py` | Punto di ingresso per la modalità PLC reale — avvia tutto in un unico processo |
| `plc_config.py` | Configurazione centralizzata: IP PLC, offset variabili DB, timing |
| `plc_io.py` | Layer snap7 thread-safe — lettura e scrittura variabili PLC |
| `sensor_writer.py` | Thread che scrive periodicamente peso/induttanza/capacitività nel DB del PLC |
| `hmi_bridge.py` | WebSocket server — legge posizioni dal PLC e le manda alla GUI, riceve comandi dalla GUI e li scrive sul PLC |
| `plc_industrial_sorter.zap17` | Export del progetto PLC da TIA Portal v17 — vedi sezione 9 |

---

## 4. Descrizione del processo fisico

### Ciclo di lavorazione (un oggetto alla volta)

```
Ingresso           Scanner         Fine nastro 1
   │                  │                  │
X=-1000           X=-500             X=0
   │                  │                  │
   ▼   NASTRO 1   ▼   fermata 3s   ▼
   ●──────────────●─────────────────►
                  │ analisi sensori      │
                  │ peso / induttanza    │ trasferimento
                  │ capacitività         │
                  │ → tipo determinato   ▼
                                    NASTRO 2
                                       │ Y=0
                                       │
                                       ▼ Y=250  ┌──────────┐
                                       ├────────►│ Plastica │
                                       │         └──────────┘
                                       ▼ Y=500  ┌──────────┐
                                       ├────────►│ Metallo  │
                                       │         └──────────┘
                                       ▼ Y=750  ┌──────────┐
                                       ├────────►│ Vetro    │
                                       │         └──────────┘
                                       ▼ Y=1000 ┌──────────┐
                                       └────────►│ Scarto   │
                                                 └──────────┘
                     Carrello si sposta in Y fino all'oggetto,
                     pusher spinge l'oggetto nel contenitore,
                     pusher si ritrae, carrello torna a Y=0.
```

### Parametri di classificazione (usati dalla simulazione Python)

| Tipo | Peso (kg) | Induttanza (mH) | Capacitività (pF) | Contenitore Y |
|------|-----------|-----------------|-------------------|---------------|
| Plastica | 0.05 – 0.30 | 0.01 – 0.10 | 15 – 40 | 250 |
| Metallo | 0.40 – 2.50 | 5.0 – 50.0 | 1 – 8 | 500 |
| Vetro | 0.20 – 0.90 | 0.01 – 0.05 | 5 – 14 | 750 |
| Scarto | variabile | variabile | variabile | 1000 |

---

## 5. Interfaccia HMI — GUI Web

### File: `wastesorter_gui.html`

Aperta direttamente nel browser come file locale, senza server web. Si connette automaticamente al server Python su `ws://localhost:8765` e riprova ogni 2 secondi in caso di disconnessione.

Mostra una vista dall'alto dell'impianto con nastro 1 orizzontale, nastro 2 verticale, oggetto animato con colore per tipo, scanner a metà nastro 1 con barra di avanzamento, carrello con pusher sulla guida destra del nastro 2, e 4 contenitori a sinistra con contatori in tempo reale. Nel pannello laterale compaiono peso, induttanza e capacitività dell'oggetto in analisi.

I comandi disponibili sono AVVIA, STOP, ARRESTO DI EMERGENZA (sidebar) e AZZERA ALLARME (appare solo quando c'è un allarme attivo). La GUI invia questi comandi a Python via WebSocket e non esegue nessuna logica di processo autonomamente.

---

## 6. Python — Simulazione con WebSocket

### File: `wastesorter_server.py`

Simula l'intero processo senza alcun PLC. Gestisce la macchina a stati dell'impianto, genera oggetti con proprietà fisiche casuali, ne determina il tipo in base a soglie sui parametri simulati, e trasmette lo stato alla GUI ogni 50ms.

**Installazione:**
```bash
pip install websockets
```

**Avvio:**
```bash
python wastesorter_server.py
```

I parametri del processo (velocità nastro, velocità carrello, durata scansione, ecc.) sono raggruppati nel dizionario `CFG` in cima al file e possono essere modificati liberamente.

---

## 7. Python — Bridge PLC reale (snap7)

### File: `main.py` + `plc_config.py` + `plc_io.py` + `sensor_writer.py` + `hmi_bridge.py`

Quando il PLC fisico è disponibile, il vecchio file unico `plc_snap7_bridge.py` è stato sostituito da un'architettura modulare a processo unico:

- **`plc_config.py`** — unico file da modificare: IP del PLC, offset delle variabili nel Data Block, timing. Tutto il resto del codice non va toccato.
- **`plc_io.py`** — connessione snap7 thread-safe condivisa tra i moduli. Espone `read_var()` e `write_var()` che usano un lock per evitare accessi concorrenti.
- **`sensor_writer.py`** — thread che gira in background e scrive periodicamente nel DB del PLC i valori simulati di peso, segnale induttivo e segnale capacitivo. In un impianto reale leggerebbe i sensori fisici.
- **`hmi_bridge.py`** — WebSocket server asyncio che ogni 50ms legge le posizioni dal PLC e le manda alla GUI. Riceve i comandi dalla GUI (start, stop, allarme, reset allarme) e li traduce in impulsi sulle variabili del PLC (`Sistema_START`, `Sistema_STOP`, `Sistema_ANNULLA_ALLARMI`). Legge `Allarme_generale` dal PLC per rispecchiarlo nella GUI.
- **`main.py`** — avvia la connessione snap7, il `SensorWriter` (thread) e l'`HmiBridge` (asyncio) in un unico processo.

Quando il PLC tornerà disponibile, sarà sufficiente configurare gli offset corretti in `plc_config.py` e avviare `main.py` al posto di `wastesorter_server.py`. La GUI non richiede alcuna modifica.

**Installazione (per uso futuro):**
```bash
pip install websockets python-snap7
```
È inoltre necessario che la libreria nativa `snap7.dll` (Windows) o `libsnap7.so` (Linux) sia presente nel PATH di sistema, scaricabile da https://snap7.sourceforge.net/

---

## 8. PLC Siemens S7 / TIA Portal v17

### File: `plc_industrial_sorter.zap17`

Export del progetto PLC creato in TIA Portal v17. Contiene la configurazione hardware e tutta la logica di controllo dell'impianto programmata in Ladder e SCL.


Quando la licenza sarà disponibile: TIA Portal → *Open existing project* → seleziona `plc_industrial_sorter.zap17`.

---

## 9. Limitazione attuale: licenza TIA Portal scaduta

> ⚠️ **Nota importante sullo stato attuale del progetto**

La licenza di **TIA Portal v17** utilizzata durante lo sviluppo è scaduta. Di conseguenza, al momento non è possibile aprire il progetto PLC né far girare il bridge snap7 in modo completo. I due file (`plc_industrial_sorter.zap17` e `plc_snap7_bridge.py`) sono presenti e pronti, ma non possono essere utilizzati insieme fino al ripristino della licenza.

Il sistema funziona comunque nella sua interezza in **modalità simulazione** tramite `wastesorter_server.py` e `wastesorter_gui.html`.

| Componente | Stato attuale |
|------------|---------------|
| `wastesorter_gui.html` | ✅ Funzionante |
| `wastesorter_server.py` | ✅ Funzionante |
| `main.py` + moduli | ✅ Codice pronto — non testabile senza PLC attivo |
| `plc_industrial_sorter.zap17` | ⏸ Presente — non apribile senza licenza TIA Portal |

### Come ripristinare l'integrazione completa

1. Rinnovare la licenza TIA Portal v17, oppure attivare una licenza Trial dal portale Siemens Industry Online Support
2. Aprire `plc_industrial_sorter.zap17` in TIA Portal
3. Compilare e caricare su PLCSIM Advanced o su CPU S7 fisica
4. Configurare IP e offset variabili in `plc_config.py`
5. Avviare `python main.py` al posto di `wastesorter_server.py`
6. Aprire `wastesorter_gui.html` nel browser — nessuna altra modifica necessaria

---

## 10. Avvio rapido — modalità simulazione

```bash
# Installa le dipendenze
pip install websockets

# Avvia il server
python wastesorter_server.py

# Apri la GUI (doppio click sul file oppure trascinala nel browser)
# wastesorter_gui.html

# Premi AVVIA nell'interfaccia
```

Output atteso nel terminale:
```
[INFO] WasteSorter Server avviato su ws://localhost:8765
[INFO] Client connesso: ('127.0.0.1', ...)
[INFO] Comando ricevuto: start
[INFO] Nuovo oggetto: {'tipo': 'plastica', 'peso': 0.18, ...}
[INFO] Scansione avviata (plastica)
[INFO] Scansione completata
[INFO] Oggetto in posizione Y=250, attendo carrello
[INFO] Carrello in posizione, avvio spinta
[INFO] Oggetto smistato, ritiro pusher
[INFO] Carrello a 0 — pronto per prossimo oggetto
```

---

## 11. Avvio completo — modalità PLC reale

Da seguire quando la licenza TIA Portal è disponibile e il PLC è raggiungibile in rete.

```bash
# Aprire plc_industrial_sorter.zap17 in TIA Portal v17
# Compilare e caricare su PLCSIM Advanced o CPU fisica

# Installare dipendenze
pip install websockets python-snap7

# Configurare IP e offset variabili in plc_config.py:
#   PLC_IP = "192.168.0.1"
#   (verificare tutti gli offset nella VAR_MAP)

# Avviare il sistema
python main.py

# Aprire wastesorter_gui.html nel browser
```

---

## 12. Protocollo WebSocket

### GUI → Python

```json
{"cmd": "start"}
{"cmd": "stop"}
{"cmd": "alarm", "msg": "EMERGENZA OPERATORE"}
{"cmd": "reset_alarm"}
```

### Python → GUI (ogni 50ms)

```json
{
  "obj": {
    "active": true,
    "x": -650.0,
    "y": 0.0,
    "tipo": "plastica",
    "peso": 0.18,
    "induttanza": 0.07,
    "capacitività": 28.4
  },
  "carrello": {
    "y": 0.0,
    "pusher": 0.0
  },
  "stato": "nastro1",
  "scan_progress": 0.0,
  "running": true,
  "alarm": false,
  "alarm_msg": "",
  "counts": {
    "plastica": 12,
    "metallo": 7,
    "vetro": 4,
    "scarto": 1
  }
}
```

### Stati del ciclo

| Stato | Descrizione |
|-------|-------------|
| `idle` | Sistema fermo, attesa START |
| `nastro1` | Oggetto in movimento verso lo scanner (X: -1000 → -500) |
| `scansione` | Oggetto fermo a X=-500, analisi in corso |
| `nastro1b` | Oggetto riparte dallo scanner verso X=0 |
| `nastro2` | Oggetto scende sul nastro 2 verso il contenitore |
| `attesa` | Oggetto in posizione, carrello in avvicinamento |
| `spinta` | Pusher in estensione, oggetto spinto nel contenitore |
| `ritorno` | Pusher si ritrae |
| `rientro` | Carrello torna a Y=0 |

---

## 13. Sviluppi futuri

- **Machine Learning**: raccogliere i valori di peso, induttanza e capacitività di ogni ciclo per addestrare un classificatore (scikit-learn, poi PyTorch) che sostituisca le soglie fisse attuali
- **Ottimizzazione layout**: algoritmo che dopo N cicli suggerisce il riposizionamento dei contenitori in base alla frequenza di arrivo per tipo
- **Dashboard statistiche**: pannello Analytics con grafici di throughput, distribuzione per tipo ed efficienza nel tempo
- **Multi-oggetto**: gestione di più oggetti contemporanei sul nastro
- **OPC-UA nativo**: sostituzione di snap7 con client OPC-UA (`asyncua`) per accesso simbolico alle variabili PLC

---
---
---

# WasteSorter — Project Documentation

> 🇮🇹 **Versione italiana disponibile nella prima parte di questo documento** — [vai all'italiano](#wastesorter--documentazione-di-progetto)

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [General Architecture](#2-general-architecture)
3. [File List](#3-file-list)
4. [Physical Process Description](#4-physical-process-description)
5. [HMI Interface — Web GUI](#5-hmi-interface--web-gui)
6. [Python — Simulation with WebSocket](#6-python--simulation-with-websocket)
7. [Python — Real PLC Bridge (snap7)](#7-python--real-plc-bridge-snap7)
8. [PLC Siemens S7 / TIA Portal v17](#8-plc-siemens-s7--tia-portal-v17)
9. [Current Limitation: TIA Portal License Expired](#9-current-limitation-tia-portal-license-expired)
10. [Quick Start — Simulation Mode](#10-quick-start--simulation-mode)
11. [Full Start — Real PLC Mode](#11-full-start--real-plc-mode)
12. [WebSocket Protocol](#12-websocket-protocol)
13. [Future Development](#13-future-development)

---

## 1. System Overview

WasteSorter is an automated sorting plant that receives mixed objects on a conveyor belt, analyses them using sensors (weight, inductance, capacitance), determines their type (plastic, metal, glass, reject) and routes them to the correct container via a cart and pusher mechanism.

The project consists of three layers:

- **Field level**: Siemens S7 PLC with Ladder/SCL logic programmed in TIA Portal v17
- **Supervision level**: Python script that manages the process logic and communicates with the GUI; in the real-PLC version it reads and writes variables via snap7
- **HMI level**: web-based graphical interface in HTML/JS with real-time updates over WebSocket

---

## 2. General Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     PHYSICAL PLANT                          │
│  Belt 1 ──► Scanner ──► Belt 2 ──► Cart/Pusher              │
│                                ──► Containers (4)            │
└───────────────────────┬─────────────────────────────────────┘
                        │ Physical I/O
┌───────────────────────▼─────────────────────────────────────┐
│              SIEMENS S7 PLC  —  TIA Portal v17              │
│              plc_industrial_sorter.zap17                     │
└───────────────────────┬─────────────────────────────────────┘
                        │ snap7 (DB read/write)
                        │
              ┌─────────▼──────────┐
              │  plc_snap7_bridge  │  ← with real PLC (currently inactive)
              └─────────┬──────────┘
                        │   or, as a replacement:
              ┌─────────▼──────────┐
              │ wastesorter_server │  ← standalone simulation
              └─────────┬──────────┘
                        │ WebSocket  ws://localhost:8765
┌───────────────────────▼─────────────────────────────────────┐
│              wastesorter_gui.html                            │
│  Top-down view: belts, object, cart, containers              │
│  Controls: START / STOP / EMERGENCY / RESET ALARM            │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. File List

| File | Description |
|------|-------------|
| `wastesorter_gui.html` | Web HMI interface — WebSocket client, animated plant visualisation |
| `wastesorter_server.py` | WebSocket server + full process simulation, no PLC required |
| `main.py` | Entry point for real-PLC mode — starts everything in a single process |
| `plc_config.py` | Centralised configuration: PLC IP, DB variable offsets, timing |
| `plc_io.py` | Thread-safe snap7 layer — PLC variable read/write |
| `sensor_writer.py` | Thread that periodically writes weight/inductance/capacitance to the PLC DB |
| `hmi_bridge.py` | WebSocket server — reads positions from PLC and sends to GUI, receives commands from GUI and writes to PLC |
| `plc_industrial_sorter.zap17` | PLC project export from TIA Portal v17 — currently unopenable (see section 9) |

---

## 4. Physical Process Description

### Work cycle (one object at a time)

```
Entry              Scanner          End of belt 1
  │                  │                  │
X=-1000           X=-500             X=0
  │                  │                  │
  ▼    BELT 1    ▼   3s stop      ▼
  ●──────────────●─────────────────►
                 │ sensor analysis      │
                 │ weight/inductance    │ transfer
                 │ capacitance         │
                 │ → type determined   ▼
                                   BELT 2
                                      │ Y=0
                                      │
                                      ▼ Y=250  ┌──────────┐
                                      ├────────►│ Plastic  │
                                      │         └──────────┘
                                      ▼ Y=500  ┌──────────┐
                                      ├────────►│ Metal    │
                                      │         └──────────┘
                                      ▼ Y=750  ┌──────────┐
                                      ├────────►│ Glass    │
                                      │         └──────────┘
                                      ▼ Y=1000 ┌──────────┐
                                      └────────►│ Reject   │
                                                └──────────┘
                    Cart moves along Y to the object position,
                    pusher extends and pushes the object into
                    the container, retracts, cart returns to Y=0.
```

### Classification parameters (used by the Python simulation)

| Type | Weight (kg) | Inductance (mH) | Capacitance (pF) | Container Y |
|------|-------------|-----------------|------------------|-------------|
| Plastic | 0.05 – 0.30 | 0.01 – 0.10 | 15 – 40 | 250 |
| Metal | 0.40 – 2.50 | 5.0 – 50.0 | 1 – 8 | 500 |
| Glass | 0.20 – 0.90 | 0.01 – 0.05 | 5 – 14 | 750 |
| Reject | variable | variable | variable | 1000 |

---

## 5. HMI Interface — Web GUI

### File: `wastesorter_gui.html`

Opened directly in the browser as a local file, no web server required. Connects automatically to the Python server at `ws://localhost:8765` and retries every 2 seconds on disconnection.

Displays a top-down view of the plant with a horizontal belt 1, a vertical belt 2, a colour-coded animated object (blue=plastic, yellow=metal, green=glass, red=reject), a scanner at the midpoint of belt 1 with a progress bar, a cart with pusher on the right-hand rail of belt 2, and 4 containers on the left with live counters. The sidebar shows the weight, inductance and capacitance of the current object during analysis.

Available controls: START, STOP, EMERGENCY STOP (sidebar) and RESET ALARM (shown only when an alarm is active). The GUI sends these commands to Python via WebSocket and performs no process logic of its own.

---

## 6. Python — Simulation with WebSocket

### File: `wastesorter_server.py`

Simulates the entire process without any PLC. Manages the plant state machine, generates objects with random physical properties, determines their type based on threshold ranges, and broadcasts the state to the GUI every 50 ms.

**Installation:**
```bash
pip install websockets
```

**Run:**
```bash
python wastesorter_server.py
```

Process parameters (belt speed, cart speed, scan duration, etc.) are grouped in the `CFG` dictionary at the top of the file and can be freely adjusted.

---

## 7. Python — Real PLC Bridge (snap7)

### Files: `main.py` + `plc_config.py` + `plc_io.py` + `sensor_writer.py` + `hmi_bridge.py`

When the physical PLC is available, the original single-file `plc_snap7_bridge.py` has been replaced by a modular single-process architecture:

- **`plc_config.py`** — the only file that needs editing: PLC IP, DB variable offsets, timing. Nothing else needs to be touched.
- **`plc_io.py`** — thread-safe snap7 connection shared between modules, exposing `read_var()` and `write_var()` protected by a lock.
- **`sensor_writer.py`** — background thread that periodically writes simulated weight, inductive and capacitive sensor values to the PLC DB. In a real plant it would read from physical sensors.
- **`hmi_bridge.py`** — asyncio WebSocket server that reads PLC positions every 50 ms and pushes them to the GUI. Receives GUI commands (start, stop, alarm, reset) and translates them into PLC impulses (`Sistema_START`, `Sistema_STOP`, `Sistema_ANNULLA_ALLARMI`). Also reads `Allarme_generale` from the PLC and mirrors it in the GUI.
- **`main.py`** — starts the snap7 connection, the `SensorWriter` (thread) and the `HmiBridge` (asyncio) in a single process.

When the PLC becomes available again, update the offsets in `plc_config.py` and run `main.py` instead of `wastesorter_server.py`. No changes to the GUI are needed.

**Installation (for future use):**
```bash
pip install websockets python-snap7
```
The native library `snap7.dll` (Windows) or `libsnap7.so` (Linux) must also be present in the system PATH, available from https://snap7.sourceforge.net/

---

## 8. PLC Siemens S7 / TIA Portal v17

### File: `plc_industrial_sorter.zap17`

Export of the PLC project created in TIA Portal v17, containing the hardware configuration and the full control logic programmed in Ladder and SCL.

**Currently unopenable** — see section 9.

When the licence is available: TIA Portal → *Open existing project* → select `plc_industrial_sorter.zap17`.

---

## 9. Current Limitation: TIA Portal License Expired

> ⚠️ **Important note on the current state of the project**

The **TIA Portal v17** licence used during development has expired. As a result, it is currently not possible to open the PLC project or run the snap7 bridge in full. Both files (`plc_industrial_sorter.zap17` and `plc_snap7_bridge.py`) are present and ready, but cannot be used together until the licence is restored.

The system works fully in **simulation mode** via `wastesorter_server.py` and `wastesorter_gui.html`.

| Component | Current status |
|-----------|----------------|
| `wastesorter_gui.html` | ✅ Working |
| `wastesorter_server.py` | ✅ Working |
| `main.py` + modules | ✅ Code ready — cannot be tested without an active PLC |
| `plc_industrial_sorter.zap17` | ⏸ Present — cannot be opened without a TIA Portal licence |

### How to restore full integration

1. Renew the TIA Portal v17 licence, or activate a Trial licence from the Siemens Industry Online Support portal
2. Open `plc_industrial_sorter.zap17` in TIA Portal
3. Compile and download to PLCSIM Advanced or a physical S7 CPU
4. Configure IP and variable offsets in `plc_config.py`
5. Run `python main.py` instead of `wastesorter_server.py`
6. Open `wastesorter_gui.html` in the browser — no other changes needed

---

## 10. Quick Start — Simulation Mode

```bash
# Install dependencies
pip install websockets

# Start the server
python wastesorter_server.py

# Open the GUI (double-click the file or drag it into the browser)
# wastesorter_gui.html

# Press START in the interface
```

Expected terminal output:
```
[INFO] WasteSorter Server started on ws://localhost:8765
[INFO] Client connected: ('127.0.0.1', ...)
[INFO] Command received: start
[INFO] New object: {'tipo': 'plastica', 'peso': 0.18, ...}
[INFO] Scan started (plastica)
[INFO] Scan complete
[INFO] Object at position Y=250, waiting for cart
[INFO] Cart in position, starting push
[INFO] Object sorted, retracting pusher
[INFO] Cart at 0 — ready for next object
```

---

## 11. Full Start — Real PLC Mode

To be followed when the TIA Portal licence is available and the PLC is reachable on the network.

```bash
# Open plc_industrial_sorter.zap17 in TIA Portal v17
# Compile and download to PLCSIM Advanced or a physical CPU

# Install dependencies
pip install websockets python-snap7

# Configure IP and variable offsets in plc_config.py:
#   PLC_IP = "192.168.0.1"
#   (verify all offsets in VAR_MAP)

# Start the system
python main.py

# Open wastesorter_gui.html in the browser
```

---

## 12. WebSocket Protocol

### GUI → Python

```json
{"cmd": "start"}
{"cmd": "stop"}
{"cmd": "alarm", "msg": "OPERATOR EMERGENCY"}
{"cmd": "reset_alarm"}
```

### Python → GUI (every 50 ms)

```json
{
  "obj": {
    "active": true,
    "x": -650.0,
    "y": 0.0,
    "tipo": "plastica",
    "peso": 0.18,
    "induttanza": 0.07,
    "capacitività": 28.4
  },
  "carrello": {
    "y": 0.0,
    "pusher": 0.0
  },
  "stato": "nastro1",
  "scan_progress": 0.0,
  "running": true,
  "alarm": false,
  "alarm_msg": "",
  "counts": {
    "plastica": 12,
    "metallo": 7,
    "vetro": 4,
    "scarto": 1
  }
}
```

### Cycle states

| State | Description |
|-------|-------------|
| `idle` | System stopped, waiting for START |
| `nastro1` | Object moving towards scanner (X: -1000 → -500) |
| `scansione` | Object stopped at X=-500, analysis in progress |
| `nastro1b` | Object resuming from scanner towards X=0 |
| `nastro2` | Object descending belt 2 towards container |
| `attesa` | Object in position, cart approaching |
| `spinta` | Pusher extending, object pushed into container |
| `ritorno` | Pusher retracting |
| `rientro` | Cart returning to Y=0 |

---

## 13. Future Development

- **Machine Learning**: collect weight, inductance and capacitance readings from each cycle to train a classifier (scikit-learn, then PyTorch) replacing the current fixed thresholds
- **Layout optimisation**: algorithm that after N cycles suggests repositioning containers based on the arrival frequency of each type
- **Statistics dashboard**: Analytics panel with throughput charts, type distribution and efficiency over time
- **Multi-object**: support for multiple simultaneous objects on the belt
- **Native OPC-UA**: replace snap7 with an OPC-UA client (`asyncua`) for symbolic access to PLC variables

---

*WasteSorter Project — work in progress*
