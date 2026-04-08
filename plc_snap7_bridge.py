import snap7
import struct
import time
import random
import numpy as np


# ══════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════

PLC_IP    = '192.168.0.1'
RACK      = 0
SLOT      = 1
DB_NUMBER = 1

READ_CYCLE   = 0.2   # lettura veloce (200 ms)
WRITE_CYCLE  = 10.0   # scrittura lenta (2 sec)

DB_SIZE = 20


# ══════════════════════════════════════════════════════════════
# VAR CONFIG
# ══════════════════════════════════════════════════════════════

VAR_CONFIG = {

    # ───── WRITE (SIMULAZIONE) ─────
    'peso': {
        'offset': 2,
        'type': 'real',
        'mode': 'write',
        'distribution': 'beta',
        'params': {'a': 1, 'b': 1},
        'low': 0.0,
        'high': 100.0,
    },

    'val_induttivo': {
        'offset': 0,
        'type': 'bool',
        'bit': 2,
        'mode': 'write',
        'params': {'p_true': 0.2},
    },

    'val_capacitivo': {
        'offset': 3,
        'type': 'bool',
        'bit': 3,
        'mode': 'write',
        'params': {'p_true': 0.4},
    },

    # ───── READ (PLC) ─────

    'val_capacitivo': {
        'offset': 3,
        'type': 'bool',
        'bit': 3,
        'mode': 'write',
        'params': {'p_true': 0.4},
    },

}


# ══════════════════════════════════════════════════════════════
# SAMPLING
# ══════════════════════════════════════════════════════════════

def sample_real(cfg):
    d = cfg['distribution']
    p = cfg['params']

    if d == 'beta':
        raw = np.random.beta(p['a'], p['b'])
        return cfg.get('low', 0) + raw * (cfg.get('high', 1) - cfg.get('low', 0))
    else:
        return float(np.random.random())


def sample_int(cfg):
    return int(np.random.randint(0, 100))


def sample_bool(cfg):
    return random.random() < cfg['params'].get('p_true', 0.5)


# ══════════════════════════════════════════════════════════════
# CONNECT
# ══════════════════════════════════════════════════════════════

def connect():
    client = snap7.client.Client()
    client.connect(PLC_IP, RACK, SLOT)

    if not client.get_connected():
        raise Exception("❌ Connessione fallita")

    print("✅ Connesso al PLC")
    return client


# ══════════════════════════════════════════════════════════════
# SCRITTURA
# ══════════════════════════════════════════════════════════════

def write_block(db):
    write_values = {}

    for name, cfg in VAR_CONFIG.items():

        if cfg.get('mode') != 'write':
            continue

        offset = cfg['offset']

        if cfg['type'] == 'real':
            val = sample_real(cfg)
            struct.pack_into('>f', db, offset, val)

        elif cfg['type'] == 'int':
            val = sample_int(cfg)
            struct.pack_into('>h', db, offset, val)

        elif cfg['type'] == 'bool':
            val = sample_bool(cfg)
            bit = cfg.get('bit', 0)

            if val:
                db[offset] |= (1 << bit)
            else:
                db[offset] &= ~(1 << bit)

        write_values[name] = val

    return write_values


# ══════════════════════════════════════════════════════════════
# LETTURA
# ══════════════════════════════════════════════════════════════

def read_block(db):
    read_values = {}

    for name, cfg in VAR_CONFIG.items():
        offset = cfg['offset']

        if cfg['type'] == 'real':
            val = struct.unpack_from('>f', db, offset)[0]

        elif cfg['type'] == 'int':
            val = struct.unpack_from('>h', db, offset)[0]

        elif cfg['type'] == 'bool':
            bit = cfg.get('bit', 0)
            val = bool(db[offset] & (1 << bit))

        read_values[name] = val

    return read_values


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

def main():
    client = connect()

    last_values = {}
    last_write_time = 0

    cycle = 0

    try:
        while True:
            cycle += 1
            now = time.time()

            # ─── READ ───
            db = bytearray(client.db_read(DB_NUMBER, 0, DB_SIZE))

            write_vals = {}

            # ─── WRITE SOLO OGNI N SECONDI ───
            if now - last_write_time >= WRITE_CYCLE:
                write_vals = write_block(db)
                client.db_write(DB_NUMBER, 0, db)
                last_write_time = now

            # ─── READ VALUES ───
            read_vals = read_block(db)

            # ─── STAMPA SOLO CAMBI ───
            for name, val in read_vals.items():

                if name not in last_values or last_values[name] != val:

                    source = "SIM" if name in write_vals else "PLC"

                    print(f"[{cycle:05d}] {name:20s} → {val}   [{source}]")

                    last_values[name] = val

            time.sleep(READ_CYCLE)

    except KeyboardInterrupt:
        print("\n⛔ Stop")

    finally:
        client.disconnect()
        print("🔌 Disconnesso")


if __name__ == "__main__":
    main()
