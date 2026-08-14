"""Moniteur en temps réel — affiche tout paramètre qui change pendant l'exécution.

Usage:
    python3 monitor_changes.py [IP]

Lance ce script, puis agis sur le panneau. Tout paramètre qui change s'affiche
immédiatement avec l'ancienne et la nouvelle valeur.

Ctrl+C pour arrêter.
"""

import socket
import struct
import sys
import time

IP = sys.argv[1] if len(sys.argv) > 1 else "192.168.1.38"
PORT = 8899
DEST_ID = 1
SOURCE_ID = 100
CMD_READ_VAL = 0x43

# Plage à surveiller — couvre tous les blocs connus (HDW, circuits, heatsource, buffor...)
# On exclut les IDs qui ne répondent pas pour garder la boucle rapide.
SCAN_START = 100
SCAN_END   = 530   # ~430 IDs — environ 90s pour un tour complet, 2s par ID déjà connu

# IDs connus pour aller plus vite (on skipe les IDs qui n'ont jamais répondu)
SKIP_IDS: set[int] = set()

# Noms connus pour l'affichage
NAMES: dict[int, str] = {
    101: "hdwsettings",
    102: "hdwstate",
    103: "hdwtsetpoint",
    106: "hdwpumpstate",
    115: "hdwstartoneloading",
    116: "hdwdbstate",
    119: "hdwusermode",
    182: "buforstate",
    232: "circuit1state",
    235: "circuit1pumpdebug",
    236: "circuit1workstate",
    282: "circuit2state",
    285: "circuit2pumpdebug",
    332: "circuit3state",
    335: "circuit3pumpdebug",
    432: "circulationstate",
    462: "heatsourcemainpumpsett",
    463: "heatsourcemainpumpstate",
    464: "heatsourcemainpumpext",
    466: "heatsourcecontactstate",
    492: "heaterpumpdecreasefordhw",
    522: "heaterpumpdecreaseforbuffer",
}

session_counter = [50]


def crc16(data: bytes) -> int:
    crc, poly = 0x0000, 0x1021
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ poly) if (crc & 0x8000) else (crc << 1)
            crc &= 0xFFFF
    return crc


def build_frame(pid: int) -> bytes:
    session_counter[0] = (session_counter[0] + 1) % 65000
    payload = struct.pack("<HB BH", session_counter[0], 1, 1, pid)
    l_val = 5 + len(payload)
    header = struct.pack("<HHHB", l_val, DEST_ID, SOURCE_ID, CMD_READ_VAL)
    body = header + payload
    return b"\x68" + body + struct.pack(">H", crc16(body)) + b"\x16"


def extract_frames(buf: bytes) -> list[bytes]:
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
            frames.append(frame)
            i += frame_len
        else:
            i += 1
    return frames


def query_raw(pid: int) -> bytes | None:
    frame = build_frame(pid)
    buf = bytearray()
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2.0)
        sock.connect((IP, PORT))
        sock.send(frame)
        deadline = time.time() + 1.5
        while time.time() < deadline:
            try:
                sock.settimeout(deadline - time.time())
                chunk = sock.recv(4096)
            except socket.timeout:
                break
            if not chunk:
                break
            buf.extend(chunk)
    except Exception:
        return None
    finally:
        try:
            sock.close()
        except Exception:
            pass

    for frame in extract_frames(bytes(buf)):
        if len(frame) < 8:
            continue
        src = struct.unpack("<H", frame[5:7])[0]
        cmd = frame[7]
        if src != DEST_ID or cmd != (CMD_READ_VAL | 0x80):
            continue
        payload = frame[8:-3]
        if len(payload) < 6:
            continue
        resp_pid = struct.unpack("<H", payload[4:6])[0]
        if resp_pid == pid:
            return payload[6:10]  # 4 bytes suffisent pour tous les types
    return None


def fmt(raw: bytes | None) -> str:
    if raw is None:
        return "—"
    h = raw.hex()
    extras = []
    if len(raw) >= 1:
        extras.append(f"b={raw[0]}")
    if len(raw) >= 2:
        extras.append(f"i16={struct.unpack('<h', raw[:2])[0]}")
    if len(raw) >= 4:
        extras.append(f"i32={struct.unpack('<i', raw[:4])[0]}")
        try:
            f = struct.unpack("<f", raw[:4])[0]
            if -9999 < f < 9999:
                extras.append(f"f={f:.2f}")
        except Exception:
            pass
    return f"{h}  ({', '.join(extras)})"


def main():
    print("=" * 80)
    print(f"  Moniteur temps réel  —  {IP}:{PORT}")
    print(f"  Plage scannée : IDs {SCAN_START}–{SCAN_END - 1}")
    print("  Agis sur le panneau, tout changement s'affiche ici.")
    print("  Ctrl+C pour arrêter.")
    print("=" * 80)

    # ── Phase 1 : baseline (première passe, silencieuse) ───────────────────
    print("\n  Initialisation baseline...", end="", flush=True)
    baseline: dict[int, bytes | None] = {}
    no_response: set[int] = set()

    for pid in range(SCAN_START, SCAN_END):
        raw = query_raw(pid)
        baseline[pid] = raw
        if raw is None:
            no_response.add(pid)

    responsive = len(baseline) - len(no_response)
    print(f" {responsive} paramètres actifs sur {SCAN_END - SCAN_START} scannés.\n")
    print("  En attente de changements...\n")

    # ── Phase 2 : boucle de surveillance ──────────────────────────────────
    round_num = 0
    try:
        while True:
            round_num += 1
            t_start = time.time()
            changed_this_round = []

            for pid in range(SCAN_START, SCAN_END):
                # Sauter les IDs qui n'ont jamais répondu pour aller plus vite
                if pid in no_response:
                    continue
                raw = query_raw(pid)
                prev = baseline.get(pid)
                if raw != prev:
                    changed_this_round.append((pid, prev, raw))
                    baseline[pid] = raw

            if changed_this_round:
                ts = time.strftime("%H:%M:%S")
                print(f"\n  [{ts}] ── {len(changed_this_round)} changement(s) détecté(s) ──")
                for pid, before, after in changed_this_round:
                    name = NAMES.get(pid, f"id_{pid}")
                    print(f"    ★  id {pid:4d}  {name:36s}")
                    print(f"         avant : {fmt(before)}")
                    print(f"         après : {fmt(after)}")
            else:
                elapsed = time.time() - t_start
                print(f"  Tour {round_num:3d} — {responsive} params — {elapsed:.1f}s — aucun changement", end="\r")

    except KeyboardInterrupt:
        print("\n\n  Arrêt.")


if __name__ == "__main__":
    main()
