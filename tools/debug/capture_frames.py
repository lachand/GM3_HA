"""Capture passive de trames TCP — port 8899 du module ecoNET.

Usage:
    python3 capture_frames.py [IP] [durée_secondes]

Exemple :
    python3 capture_frames.py 192.168.1.38 10

Pendant la fenêtre de capture, active la marche forcée sur le panneau.
Le script affiche et sauvegarde toutes les trames reçues pour analyse.
"""

import socket
import struct
import sys
import time
from datetime import datetime

IP       = sys.argv[1] if len(sys.argv) > 1 else "192.168.1.38"
DURATION = int(sys.argv[2]) if len(sys.argv) > 2 else 10
PORT     = 8899

NAMES: dict[int, str] = {
    61:  "tempcwu",
    101: "hdwsettings",
    102: "hdwstate",
    103: "hdwtsetpoint",
    106: "hdwpumpstate",
    115: "hdwstartoneloading",
    116: "hdwdbstate",
    119: "hdwusermode",
    182: "buforstate",
    235: "circuit1pumpdebug",
    285: "circuit2pumpdebug",
    335: "circuit3pumpdebug",
    432: "circulationstate",
    462: "heatsourcemainpumpsett",
    463: "heatsourcemainpumpstate",
}

CMD_NAMES = {
    0x01: "SCAN",
    0x43: "READ_REQ",
    0xC3: "READ_RESP",
    0x29: "WRITE_FORCE",
    0xA9: "WRITE_FORCE_RESP",
    0x44: "WRITE_OLD",
    0x45: "WRITE_V3",
}


def crc16(data: bytes) -> int:
    crc, poly = 0x0000, 0x1021
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ poly) if (crc & 0x8000) else (crc << 1)
            crc &= 0xFFFF
    return crc


def extract_frames(buf: bytes) -> list[tuple[int, bytes]]:
    """Retourne liste de (offset, frame_bytes)."""
    frames = []
    i = 0
    while i < len(buf):
        if buf[i] != 0x68:
            i += 1
            continue
        if i + 3 > len(buf):
            break
        l_val = struct.unpack("<H", buf[i + 1 : i + 3])[0]
        if l_val < 5 or l_val > 4096:
            i += 1
            continue
        frame_len = l_val + 6
        if i + frame_len > len(buf):
            break
        frame = buf[i : i + frame_len]
        if frame[-1] == 0x16:
            frames.append((i, frame))
            i += frame_len
        else:
            i += 1
    return frames


def decode_frame(frame: bytes) -> dict:
    """Décode les champs d'une trame."""
    if len(frame) < 8:
        return {"raw": frame.hex(), "error": "trop courte"}

    l_val  = struct.unpack("<H", frame[1:3])[0]
    dest   = struct.unpack("<H", frame[3:5])[0]
    src    = struct.unpack("<H", frame[5:7])[0]
    cmd    = frame[7]
    body   = frame[1 : 3 + l_val]          # champ soumis au CRC
    crc_rx = struct.unpack(">H", frame[-3:-1])[0]
    crc_ok = crc16(body) == crc_rx

    payload = frame[8 : -3]                 # données après cmd, avant CRC+0x16

    info: dict = {
        "l_val":   l_val,
        "dest":    dest,
        "src":     src,
        "cmd":     cmd,
        "cmd_name": CMD_NAMES.get(cmd, f"0x{cmd:02X}"),
        "crc_ok":  crc_ok,
        "payload": payload.hex(),
        "payload_bytes": payload,
    }

    # Décodage spécifique selon le type de trame
    if cmd == 0x43 and len(payload) >= 6:
        # READ_REQ : session(2) count(1) ? pid(2)
        pid = struct.unpack("<H", payload[4:6])[0]
        info["pid"] = pid
        info["param_name"] = NAMES.get(pid, "")

    elif cmd == 0xC3 and len(payload) >= 7:
        # READ_RESP : session(2) nblocks(1) nparams(1) pid(2) status(1) value(...)
        pid = struct.unpack("<H", payload[4:6])[0]
        val_bytes = payload[7:]
        info["pid"] = pid
        info["param_name"] = NAMES.get(pid, "")
        info["value_hex"] = val_bytes.hex()
        info["decoded"] = _decode_value(val_bytes)

    elif cmd == 0x29:
        # WRITE_FORCE : user\0 pass\0 0x01 pid(2) value(...)
        try:
            null1 = payload.index(0)
            null2 = payload.index(0, null1 + 1)
            user  = payload[:null1].decode("utf-8", errors="replace")
            pwd   = payload[null1 + 1 : null2].decode("utf-8", errors="replace")
            rest  = payload[null2 + 1:]
            if len(rest) >= 3:
                flag = rest[0]
                pid  = struct.unpack("<H", rest[1:3])[0]
                val  = rest[3:]
                info["user"]  = user
                info["pwd"]   = pwd
                info["flag"]  = flag
                info["pid"]   = pid
                info["param_name"] = NAMES.get(pid, "")
                info["value_hex"]  = val.hex()
                info["decoded"]    = _decode_value(val)
        except Exception as e:
            info["parse_error"] = str(e)

    return info


def _decode_value(data: bytes) -> dict:
    result = {}
    if len(data) >= 1:
        result["byte"] = data[0]
    if len(data) >= 2:
        result["int16"]  = struct.unpack("<h", data[:2])[0]
        result["uint16"] = struct.unpack("<H", data[:2])[0]
    if len(data) >= 4:
        result["int32"] = struct.unpack("<i", data[:4])[0]
        try:
            f = struct.unpack("<f", data[:4])[0]
            if -99999 < f < 99999:
                result["float"] = round(f, 2)
        except Exception:
            pass
    return result


def print_frame(ts: float, frame: bytes):
    info = decode_frame(frame)
    t = datetime.fromtimestamp(ts).strftime("%H:%M:%S.%f")[:-3]

    src_label  = "BOILER" if info.get("src")  == 1 else f"src={info.get('src')}"
    dest_label = "BOILER" if info.get("dest") == 1 else f"dst={info.get('dest')}"
    cmd_label  = info.get("cmd_name", "?")
    crc_label  = "OK" if info.get("crc_ok") else "ERR"

    header = (f"  [{t}]  {src_label:8s} → {dest_label:8s}"
              f"  cmd={cmd_label:20s}  CRC={crc_label}")
    print(header)

    if "pid" in info:
        name = f"  ({info['param_name']})" if info.get("param_name") else ""
        print(f"           param id={info['pid']}{name}")
    if "value_hex" in info:
        print(f"           valeur hex={info['value_hex']}  {info.get('decoded', '')}")
    if "user" in info:
        print(f"           user={info['user']}  pwd={info['pwd']}  flag=0x{info['flag']:02X}")
    if "error" in info:
        print(f"           !! {info['error']}")

    print(f"           raw: {frame.hex()}")


def main():
    log_file = f"capture_{datetime.now().strftime('%H%M%S')}.txt"

    print("=" * 70)
    print(f"  Capture passive — {IP}:{PORT}")
    print(f"  Durée : {DURATION}s   Log : {log_file}")
    print("=" * 70)
    print()
    print(f"  ► Active la marche forcée sur le panneau dans les {DURATION} secondes.")
    print()

    raw_buf = bytearray()
    timestamps: list[float] = []   # timestamp pour chaque byte reçu (approx)
    all_frames: list[tuple[float, bytes]] = []

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1.0)
    try:
        sock.connect((IP, PORT))
        print(f"  Connecté. Écoute pendant {DURATION}s...\n")
        t_end = time.time() + DURATION

        while time.time() < t_end:
            remaining = t_end - time.time()
            sock.settimeout(min(remaining, 1.0))
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                t_chunk = time.time()
                raw_buf.extend(chunk)
                # Associe le timestamp au milieu du chunk (approximation)
                timestamps.extend([t_chunk] * len(chunk))
            except socket.timeout:
                continue

    except Exception as e:
        print(f"  Erreur connexion : {e}")
        return
    finally:
        sock.close()

    print(f"\n  Capture terminée — {len(raw_buf)} bytes reçus.")

    # ── Extraction des trames ──────────────────────────────────────────────
    frame_list = extract_frames(bytes(raw_buf))
    print(f"  {len(frame_list)} trame(s) extraite(s).\n")

    if not frame_list:
        print("  Aucune trame détectée.")
        print("  → Le module ecoNET n'envoie peut-être rien en écoute passive.")
        print("  → Essaie avec monitor_changes.py qui envoie des requêtes actives.")
        return

    # Associe un timestamp à chaque trame via son offset dans le buffer
    for offset, frame in frame_list:
        ts = timestamps[offset] if offset < len(timestamps) else time.time()
        all_frames.append((ts, frame))
        print_frame(ts, frame)

    # ── Sauvegarde log ────────────────────────────────────────────────────
    with open(log_file, "w") as f:
        f.write(f"Capture {IP}:{PORT}  durée={DURATION}s\n")
        f.write(f"Raw hex:\n{raw_buf.hex()}\n\n")
        f.write(f"{len(all_frames)} trames:\n")
        for offset, frame in frame_list:
            info = decode_frame(frame)
            f.write(f"  offset={offset:5d}  {frame.hex()}\n")
            f.write(f"           {info}\n")

    print(f"\n  Log sauvegardé : {log_file}")

    # ── Résumé des WRITE détectés ─────────────────────────────────────────
    writes = [(ts, f) for ts, f in all_frames if f[7] == 0x29]
    if writes:
        print(f"\n  ══ {len(writes)} WRITE_FORCE détecté(s) ══")
        for ts, frame in writes:
            info = decode_frame(frame)
            t = datetime.fromtimestamp(ts).strftime("%H:%M:%S.%f")[:-3]
            print(f"  [{t}]  param={info.get('pid')} {info.get('param_name','')}  "
                  f"valeur={info.get('value_hex','')}  {info.get('decoded','')}")
    else:
        print("\n  Aucun WRITE_FORCE dans la capture.")
        print("  → Le panneau physique commande peut-être les relais en direct")
        print("     sans passer par le bus ecoNET (contrôle hardware local).")


if __name__ == "__main__":
    main()
