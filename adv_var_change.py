"""
PLCSIM Advanced → Python Data Writer
======================================
Scrive variabili Real, Int e Bool su un DB di PLCSIM Advanced via snap7.
Supporta campionamento probabilistico con distribuzione scelta per variabile.

Dipendenze:
    pip install python-snap7 numpy
    + snap7.dll nella stessa cartella (https://sourceforge.net/projects/snap7/)

Distribuzioni supportate:
    Real : normal | beta | gamma | lognormal | exponential
    Int  : uniform | poisson | binomial | weighted
    Bool : p_true (float tra 0 e 1)
"""

import snap7
import struct
import time
import random
import numpy as np


# ══════════════════════════════════════════════════════════════
#  CONFIGURAZIONE CONNESSIONE
# ══════════════════════════════════════════════════════════════

PLC_IP       = '192.168.0.1'
RACK         = 0
SLOT         = 1
DB_NUMBER    = 1
INTERVAL_SEC = 5.0


# ══════════════════════════════════════════════════════════════
#  CONFIGURAZIONE VARIABILI
#
#  Ogni variabile ha:
#    offset      : byte offset nel DB (dalla colonna Offset in TIA Portal)
#    type        : 'real' | 'int' | 'bool'
#    distribution: nome della distribuzione (vedi sotto)
#    params      : dizionario parametri specifici della distribuzione
#    low / high  : (solo per beta) range di scala del valore finale
#    bit         : (solo per bool) indice del bit nel byte
#
#  Distribuzioni Real:
#    'normal'      → params: { mean, std }
#    'beta'        → params: { a, b }         + low, high per scalare in [low, high]
#    'gamma'       → params: { shape, scale } → valori sempre > 0
#    'lognormal'   → params: { mean, sigma }  → valori sempre > 0
#    'exponential' → params: { scale }        → valori sempre > 0
#
#  Distribuzioni Int:
#    'uniform'  → params: { low, high }
#    'poisson'  → params: { lam }             → valori sempre >= 0
#    'binomial' → params: { n, p }            → valori in [0, n]
#    'weighted' → params: { values, weights } → controllo manuale totale
#
#  Bool:
#    params: { p_true }   es. 0.7 → True nel 70% dei casi
# ══════════════════════════════════════════════════════════════

VAR_CONFIG = {

    'peso': {
        'offset': 2,
        'type': 'real',
        'distribution': 'beta',
        'params': {'a': 1, 'b': 1},
        'low': 0.0,      # valore minimo dopo la scalatura
        'high': 100.0,   # valore massimo dopo la scalatura
    },

    'val_induttivo': {
        'offset': 6,
        'type': 'bool',
        'bit': 0,
        'params': {'p_true': 0.2},
    },

    'val_capacitivo': {
        'offset': 6,
        'type': 'bool',
        'bit': 1,
        'params': {'p_true': 0.4},
    },

    # ── Esempi aggiuntivi (decommentare per usare) ──────────────

    # 'temperatura': {
    #     'offset': 10,
    #     'type': 'real',
    #     'distribution': 'normal',
    #     'params': {'mean': 25.0, 'std': 3.0},
    # },

    # 'pressione': {
    #     'offset': 14,
    #     'type': 'real',
    #     'distribution': 'gamma',
    #     'params': {'shape': 2.0, 'scale': 5.0},   # sempre > 0
    # },

    # 'portata': {
    #     'offset': 18,
    #     'type': 'real',
    #     'distribution': 'lognormal',
    #     'params': {'mean': 3.0, 'sigma': 0.5},    # sempre > 0
    # },

    # 'contatore_pezzi': {
    #     'offset': 22,
    #     'type': 'int',
    #     'distribution': 'poisson',
    #     'params': {'lam': 8},                      # sempre >= 0
    # },

    # 'scarti': {
    #     'offset': 24,
    #     'type': 'int',
    #     'distribution': 'binomial',
    #     'params': {'n': 20, 'p': 0.1},             # valori in [0, 20]
    # },

    # 'categoria': {
    #     'offset': 26,
    #     'type': 'int',
    #     'distribution': 'weighted',
    #     'params': {'values': [1, 2, 3], 'weights': [10, 5, 1]},
    # },
}


# ══════════════════════════════════════════════════════════════
#  CAMPIONAMENTO
# ══════════════════════════════════════════════════════════════

def sample_real(distribution: str, params: dict, low=None, high=None) -> float:
    """
    Campiona un valore float dalla distribuzione scelta.

    Beta: il campione grezzo è in [0,1], poi viene scalato in [low, high].
    Gamma, lognormal, exponential: producono valori sempre > 0.
    """
    if distribution == 'normal':
        return float(np.random.normal(params['mean'], params['std']))

    elif distribution == 'beta':
        raw = np.random.beta(params['a'], params['b'])   # in [0, 1]
        lo  = low  if low  is not None else 0.0
        hi  = high if high is not None else 1.0
        return float(lo + raw * (hi - lo))

    elif distribution == 'gamma':
        return float(np.random.gamma(params['shape'], params['scale']))

    elif distribution == 'lognormal':
        return float(np.random.lognormal(params['mean'], params['sigma']))

    elif distribution == 'exponential':
        return float(np.random.exponential(params['scale']))

    else:
        raise ValueError(
            f"Distribuzione Real sconosciuta: '{distribution}'\n"
            f"  Disponibili: normal | beta | gamma | lognormal | exponential"
        )


def sample_int(distribution: str, params: dict) -> int:
    """
    Campiona un valore intero dalla distribuzione scelta.

    poisson  → sempre >= 0
    binomial → sempre in [0, n]
    weighted → valori esattamente quelli in params['values']
    """
    if distribution == 'uniform':
        return int(np.random.randint(params['low'], params['high'] + 1))

    elif distribution == 'poisson':
        return int(np.random.poisson(params['lam']))

    elif distribution == 'binomial':
        return int(np.random.binomial(params['n'], params['p']))

    elif distribution == 'weighted':
        return int(random.choices(params['values'], weights=params['weights'])[0])

    else:
        raise ValueError(
            f"Distribuzione Int sconosciuta: '{distribution}'\n"
            f"  Disponibili: uniform | poisson | binomial | weighted"
        )


def sample_bool(params: dict) -> bool:
    """
    Campiona un Bool.
    p_true = 0.7  →  True nel 70% dei casi, False nel 30%.
    """
    return random.random() < params.get('p_true', 0.5)


# ══════════════════════════════════════════════════════════════
#  SCRITTURA SUL DB
# ══════════════════════════════════════════════════════════════

def write_real(client, db: int, byte_offset: int, value: float):
    data = bytearray(4)
    struct.pack_into('>f', data, 0, value)
    client.db_write(db, byte_offset, data)


def write_int(client, db: int, byte_offset: int, value: int):
    data = bytearray(2)
    struct.pack_into('>h', data, 0, value)
    client.db_write(db, byte_offset, data)


def write_bool(client, db: int, byte_offset: int, bit_offset: int, value: bool):
    data = client.db_read(db, byte_offset, 1)
    if value:
        data[0] |= (1 << bit_offset)
    else:
        data[0] &= ~(1 << bit_offset)
    client.db_write(db, byte_offset, data)


# ══════════════════════════════════════════════════════════════
#  SCRITTURA COMPLETA DI TUTTE LE VARIABILI
# ══════════════════════════════════════════════════════════════

def write_all(client, db: int, config: dict):
    for name, cfg in config.items():
        t      = cfg['type']
        offset = cfg['offset']
        params = cfg.get('params', {})

        if t == 'real':
            value = sample_real(
                cfg['distribution'], params,
                low=cfg.get('low'),
                high=cfg.get('high'),
            )
            write_real(client, db, offset, value)
            print(f"  {name:25s} [Real]  = {value:.4f}")

        elif t == 'int':
            value = sample_int(cfg['distribution'], params)
            write_int(client, db, offset, value)
            print(f"  {name:25s} [Int]   = {value}")

        elif t == 'bool':
            value = sample_bool(params)
            write_bool(client, db, offset, cfg.get('bit', 0), value)
            print(f"  {name:25s} [Bool]  = {value}")

        else:
            print(f"  ⚠️  Tipo sconosciuto per '{name}': {t}")


# ══════════════════════════════════════════════════════════════
#  CONNESSIONE
# ══════════════════════════════════════════════════════════════

def connect(ip: str, rack: int, slot: int) -> snap7.client.Client:
    client = snap7.client.Client()
    client.connect(ip, rack, slot)
    if client.get_connected():
        print(f"✅ Connesso a {ip}  (rack={rack}, slot={slot})")
    else:
        raise ConnectionError(f"❌ Impossibile connettersi a {ip}")
    return client


# ══════════════════════════════════════════════════════════════
#  LOOP PRINCIPALE
# ══════════════════════════════════════════════════════════════

def main():
    client = connect(PLC_IP, RACK, SLOT)
    iteration = 0

    print(f"\n🚀 Avvio loop — invio ogni {INTERVAL_SEC}s  (Ctrl+C per fermare)\n")

    try:
        while True:
            iteration += 1
            print(f"── Iterazione {iteration} " + "─" * 35)
            write_all(client, DB_NUMBER, VAR_CONFIG)
            print(f"  ↳ prossimo invio tra {INTERVAL_SEC}s\n")
            time.sleep(INTERVAL_SEC)

    except KeyboardInterrupt:
        print("\n⛔ Loop fermato dall'utente.")
    finally:
        client.disconnect()
        print("🔌 Disconnesso dal PLC.")


if __name__ == '__main__':
    main()
