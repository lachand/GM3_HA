"""Identifie le paramètre de marche forcée de la pompe ECS (HDW).

Protocole frame: 0x68 | l_val(2LE) | dest(2LE) | src(2LE) | cmd(1) | payload(l_val-5) | crc(2BE) | 0x16

Usage:
    python3 identify_dhw_force.py [IP]

Le script prend un snapshot AVANT, attend que tu actives/désactives la marche
forcée sur le panneau physique, puis prend un snapshot APRÈS et affiche le diff.
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

session_counter = [30]

# Bloc HDW complet (états, réglages, pompe, debug)
WATCH_IDS = list(range(100, 126))
# Paramètres debug/state des circuits (L/N/NN du panneau manuel)
WATCH_IDS += [
    235, 236,       # circuit1 pumpdebug, workstate
    285, 286,       # circuit2 pumpdebug, workstate
    335, 336,       # circuit3 pumpdebug, workstate
    462, 463, 464,  # heatsourcemainpump sett/state/ext
    466,            # heatsourcecontactstate
    943, 944,       # circuit4 pumpdebug, workstate
    994, 995,       # circuit5 pumpdebug, workstate
    752, 753,       # circuit6 pumpdebug, workstate
    802, 803,       # circuit7 pumpdebug, workstate
]
WATCH_IDS = sorted(set(WATCH_IDS))

# Noms connus pour l'affichage
NAMES = {
    101: "hdwsettings",
    102: "hdwstate",
    103: "hdwtsetpoint",
    104: "hdwtsetpointdownhist",
    105: "hdwminmalhisteresis",
    106: "hdwpumpstate",
    107: "hdwminsettemp",
    108: "hdwmaxsettemp",
    109: "hdwtempkeepwarm",
    110: "hdwmaxtemphist",
    113: "hdwloadtime",
    115: "hdwstartoneloading",
    116: "hdwdbstate",          # ← candidat principal L/N/NN pompe ECS
    117: "hdwsupplyhist",
    119: "hdwusermode",
    235: "circuit1pumpdebug",
    236: "circuit1workstate",
    285: "circuit2pumpdebug",
    286: "circuit2workstate",
    335: "circuit3pumpdebug",
    336: "circuit3workstate",
    462: "heatsourcemainpumpsett",
    463: "heatsourcemainpumpstate",
    464: "heatsourcemainpumpext",
    466: "heatsourcecontactstate",
    752: "circuit6pumpdebug",
    753: "circuit6workstate",
    802: "circuit7pumpdebug",
    803: "circuit7workstate",
    943: "circuit4pumpdebug",
    944: "circuit4workstate",
    994: "circuit5pumpdebug",
    995: "circuit5workstate",
}


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


def extract_frames(buf: bytes):
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


def find_pid_data(frames, pid: int):
    for frame in frames:
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
            return payload[6:]
    return None


def query_raw(pid: int) -> bytes | None:
    """Lit un paramètre et retourne ses bytes bruts (4 premiers octets)."""
    frame = build_frame(pid)
    buf = bytearray()
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3.0)
        sock.connect((IP, PORT))
        sock.send(frame)
        deadline = time.time() + 2.5
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

    time.sleep(0.1)
    frames = extract_frames(bytes(buf))
    data = find_pid_data(frames, pid)
    # Retourne les 4 premiers octets (suffisant pour tous les types utilisés)
    return data[:4] if data and len(data) >= 1 else data


def decode_all(raw: bytes) -> dict:
    """Décode un bloc de 4 bytes dans tous les formats utiles."""
    if raw is None:
        return {}
    result = {}
    if len(raw) >= 1:
        result["byte"] = raw[0]
    if len(raw) >= 2:
        result["int16"] = struct.unpack("<h", raw[:2])[0]
        result["uint16"] = struct.unpack("<H", raw[:2])[0]
    if len(raw) >= 4:
        result["int32"] = struct.unpack("<i", raw[:4])[0]
        try:
            f = struct.unpack("<f", raw[:4])[0]
            if -99999 < f < 99999:
                result["float"] = round(f, 2)
        except Exception:
            pass
    return result


def take_snapshot(label: str) -> dict:
    """Lit tous les paramètres surveillés et retourne {pid: raw_bytes}."""
    print(f"\n  Lecture snapshot '{label}' ({len(WATCH_IDS)} paramètres)...")
    snap = {}
    for pid in WATCH_IDS:
        raw = query_raw(pid)
        snap[pid] = raw
        name = NAMES.get(pid, "")
        status = raw.hex() if raw else "—"
        print(f"    id {pid:4d}  {name:36s}  {status}")
    return snap


def print_diff(before: dict, after: dict):
    print("\n" + "=" * 80)
    print("DIFFÉRENCES DÉTECTÉES (avant → après)")
    print("=" * 80)

    changed = []
    for pid in WATCH_IDS:
        b = before.get(pid)
        a = after.get(pid)
        if b != a:
            changed.append(pid)

    if not changed:
        print("  Aucun changement détecté.")
        print("  → Vérifie que la marche forcée a bien été activée pendant la fenêtre.")
        return

    for pid in changed:
        b = before.get(pid)
        a = after.get(pid)
        name = NAMES.get(pid, f"id_{pid}")
        b_hex = b.hex() if b else "—"
        a_hex = a.hex() if a else "—"
        b_dec = decode_all(b)
        a_dec = decode_all(a)
        print(f"\n  ★  id {pid:4d}  {name}")
        print(f"       avant : {b_hex:12s}  {b_dec}")
        print(f"       après : {a_hex:12s}  {a_dec}")

    print()
    print("  → Le(s) paramètre(s) ci-dessus contrôlent la marche forcée.")
    if len(changed) == 1:
        pid = changed[0]
        b_dec = decode_all(before.get(pid))
        a_dec = decode_all(after.get(pid))
        val_off = b_dec.get("byte", b_dec.get("int32", "?"))
        val_on  = a_dec.get("byte", a_dec.get("int32", "?"))
        name = NAMES.get(pid, f"id_{pid}")
        print(f"\n  CONCLUSION :")
        print(f"    Paramètre : {name} (id={pid})")
        print(f"    Valeur ARRÊT forcé  : {val_off}")
        print(f"    Valeur MARCHE forcée : {val_on}")


def main():
    print("=" * 80)
    print("  Identification trame marche forcée pompe ECS")
    print(f"  Boiler : {IP}:{PORT}")
    print("=" * 80)

    # ── Snapshot AVANT ──────────────────────────────────────────────────────
    snap_before = take_snapshot("AVANT")

    # ── Attente action utilisateur ──────────────────────────────────────────
    print()
    print("─" * 80)
    input("  ► Active maintenant la MARCHE FORCÉE sur le panneau physique,\n"
          "    puis appuie sur [Entrée] pour prendre le snapshot APRÈS...")
    print("─" * 80)

    # ── Snapshot APRÈS ──────────────────────────────────────────────────────
    snap_after = take_snapshot("APRÈS")

    # ── Diff ────────────────────────────────────────────────────────────────
    print_diff(snap_before, snap_after)

    # ── Deuxième round : vérification arrêt forcé ───────────────────────────
    print()
    again = input("  Veux-tu aussi capturer l'ARRÊT de la marche forcée ? [o/N] ").strip().lower()
    if again in ("o", "oui", "y", "yes"):
        snap_mid = snap_after.copy()
        print()
        input("  ► Désactive maintenant la marche forcée sur le panneau,\n"
              "    puis appuie sur [Entrée]...")
        snap_stop = take_snapshot("ARRÊT FORCÉ")

        print("\n" + "=" * 80)
        print("DIFFÉRENCES À L'ARRÊT (marche forcée → arrêt forcé)")
        print("=" * 80)
        print_diff(snap_mid, snap_stop)


if __name__ == "__main__":
    main()
