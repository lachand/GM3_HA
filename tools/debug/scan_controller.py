"""Script de scan direct du contrôleur Plum EcoMAX.

Protocole frame: 0x68 | l_val(2LE) | dest(2LE) | src(2LE) | cmd(1) | payload(l_val-5) | crc(2BE) | 0x16
Taille totale frame = l_val + 6
"""
import socket
import struct
import time

IP = "192.168.1.38"
PORT = 8899
DEST_ID = 1        # boiler
SOURCE_ID = 100    # nous (0x64)
CMD_READ_VAL = 0x43

session_counter = [20]

KNOWN = {
    61:  ("tempcwu",                "FLOAT"),
    102: ("hdwstate",               "LONG_INT"),
    103: ("hdwtsetpoint",           "SHORT_INT"),
    109: ("hdwtempkeepwarm",        "SHORT_INT"),
    113: ("hdwloadtime",            "SHORT_INT"),
    119: ("hdwusermode",            "SHORT_INT"),
    183: ("buforsetpoint",          "SHORT_INT"),
    315: ("mixer2valveposition",    "FLOAT"),
    316: ("mixer2valveopeningtime", "INT"),
    318: ("mixer2valvesetposition", "SHORT_INT"),
}

SCAN_RANGES = [
    (100, 120, "HDW block — pompe ECS ?"),
    (265, 270, "Mixer 1 — hypothèse"),
    (768, 773, "Mixer 6 setposition — hypothèse"),
]


def crc16(data: bytes) -> int:
    crc, poly = 0x0000, 0x1021
    for b in data:
        crc ^= (b << 8)
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
    return b'\x68' + body + struct.pack(">H", crc16(body)) + b'\x16'


def extract_frames(buf: bytes):
    """
    Extrait tous les frames valides du buffer brut.
    Frame = 0x68 | l_val(2) | body(l_val) | crc(2) | 0x16
    Taille totale = l_val + 6
    """
    frames = []
    i = 0
    while i < len(buf):
        if buf[i] != 0x68:
            i += 1
            continue
        if i + 3 > len(buf):
            break
        l_val = struct.unpack("<H", buf[i + 1:i + 3])[0]
        if l_val < 5 or l_val > 4096:  # sanity check
            i += 1
            continue
        frame_len = l_val + 6          # CORRECT: 1(0x68) + 2(l_val field) + l_val(body) + 2(crc) + 1(0x16)
        if i + frame_len > len(buf):
            break
        frame = buf[i:i + frame_len]
        if frame[-1] == 0x16:
            frames.append(frame)
            i += frame_len
        else:
            i += 1
    return frames


def get_payload(frame: bytes):
    """Extrait le payload d'un frame (sans header ni CRC/fin)."""
    # frame[8:-3] = skip 0x68(1)+l_val(2)+dest(2)+src(2)+cmd(1) et enlève crc(2)+0x16(1)
    return frame[8:-3]


def find_pid_data(frames, pid: int):
    """Cherche dans les frames le payload correspondant au PID demandé."""
    for frame in frames:
        # Vérifie que src=1 (boiler) et cmd=0xC3 (réponse READ)
        if len(frame) < 8:
            continue
        src = struct.unpack("<H", frame[5:7])[0]
        cmd = frame[7]
        if src != DEST_ID or cmd != (CMD_READ_VAL | 0x80):
            continue
        payload = get_payload(frame)
        if len(payload) < 6:
            continue
        resp_pid = struct.unpack("<H", payload[4:6])[0]
        if resp_pid == pid:
            return payload[6:]   # bytes de la valeur
    return None


def decode_value(data: bytes, ptype: str):
    """Décode les bytes selon le type."""
    if not data:
        return None, {}
    extras = {}
    if len(data) >= 1:
        extras["byte"] = data[0]
    if len(data) >= 2:
        extras["int16"] = struct.unpack("<h", data[:2])[0]
        extras["uint16"] = struct.unpack("<H", data[:2])[0]
    if len(data) >= 4:
        extras["int32"] = struct.unpack("<i", data[:4])[0]
        try:
            f = struct.unpack("<f", data[:4])[0]
            if -99999 < f < 99999:
                extras["float"] = round(f, 2)
        except Exception:
            pass

    if ptype in ("SHORT_INT", "BYTE") and "byte" in extras:
        return extras["byte"], extras
    elif ptype == "INT" and "int16" in extras:
        return extras["int16"], extras
    elif ptype == "LONG_INT" and "int32" in extras:
        return extras["int32"], extras
    elif ptype == "FLOAT" and "float" in extras:
        return extras["float"], extras
    return extras.get("byte"), extras


def query(pid: int, ptype: str = "SHORT_INT", label: str = ""):
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
    except Exception as e:
        print(f"  id {pid:4d}  {label:44s}  ERREUR: {e}")
        return
    finally:
        try:
            sock.close()
        except Exception:
            pass

    time.sleep(0.15)

    frames = extract_frames(bytes(buf))
    value_bytes = find_pid_data(frames, pid)

    if value_bytes is None:
        # Fallback : cherche n'importe quelle réponse boiler→nous
        for frame in frames:
            if len(frame) < 8:
                continue
            src = struct.unpack("<H", frame[5:7])[0]
            cmd = frame[7]
            if src == DEST_ID and cmd == (CMD_READ_VAL | 0x80):
                p = get_payload(frame)
                if len(p) >= 6:
                    rp = struct.unpack("<H", p[4:6])[0]
                    value_bytes = p[6:]
                    print(f"  id {pid:4d}  {label:44s}  [fallback: resp_pid={rp}]  raw={value_bytes.hex()[:12]}")
                    return
        print(f"  id {pid:4d}  {label:44s}  PAS DE RÉPONSE  [{len(frames)} frames, {len(buf)} bytes]")
        return

    val, extras = decode_value(value_bytes, ptype)

    extra_str = "  ".join(f"{k}={v}" for k, v in extras.items())
    print(f"  id {pid:4d}  {label:44s}  {ptype:10s}  = {str(val):10s}  [{extra_str}]  raw={value_bytes.hex()[:12]}")


# ─── CALIBRAGE ─────────────────────────────────────────────────────────────
print("=" * 110)
print("Calibrage — paramètres connus")
print("=" * 110)
for pid, (name, ptype) in sorted(KNOWN.items()):
    query(pid, ptype, name)

# ─── SCAN ──────────────────────────────────────────────────────────────────
for start, end, label in SCAN_RANGES:
    print()
    print("=" * 110)
    print(f"Scan IDs {start}–{end-1}  —  {label}")
    print("=" * 110)
    for pid in range(start, end):
        known = KNOWN.get(pid)
        name, ptype = (known[0], known[1]) if known else ("", "SHORT_INT")
        query(pid, ptype, name)
