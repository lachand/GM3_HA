"""Test de la marche forcée pompe ECS → ballon solaire.

Usage:
    python3 test_dhw_pump_force.py [IP]
"""

import socket
import struct
import sys
import time

IP       = sys.argv[1] if len(sys.argv) > 1 else "192.168.1.38"
PORT     = 8899
DEST_ID  = 1
SRC_ID   = 100
CMD_READ  = 0x43
CMD_WRITE = 0x29
USER     = "admin"
PASSWD   = "0000"

PID      = 172
ON_VAL   = 512   # 0x00000200
OFF_VAL  = 0

session = [70]


def crc16(data: bytes) -> int:
    crc, poly = 0x0000, 0x1021
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ poly) if (crc & 0x8000) else (crc << 1)
            crc &= 0xFFFF
    return crc


def build_read(pid: int) -> bytes:
    session[0] = (session[0] + 1) % 65000
    payload = struct.pack("<HB BH", session[0], 1, 1, pid)
    l_val = 5 + len(payload)
    header = struct.pack("<HHHB", l_val, DEST_ID, SRC_ID, CMD_READ)
    body = header + payload
    return b"\x68" + body + struct.pack(">H", crc16(body)) + b"\x16"


def build_write(pid: int, value: int) -> bytes:
    session[0] = (session[0] + 1) % 65000
    user_b = USER.encode() + b"\x00"
    pass_b = PASSWD.encode() + b"\x00"
    val_b  = struct.pack("<i", value)   # LONG_INT little-endian
    payload = user_b + pass_b + b"\x01" + struct.pack("<H", pid) + val_b
    l_val = 5 + len(payload)
    header = struct.pack("<HHHB", l_val, DEST_ID, SRC_ID, CMD_WRITE)
    body = header + payload
    return b"\x68" + body + struct.pack(">H", crc16(body)) + b"\x16"


def transact(frame: bytes, timeout: float = 2.5) -> bytes | None:
    buf = bytearray()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((IP, PORT))
        s.send(frame)
        deadline = time.time() + timeout
        while time.time() < deadline:
            s.settimeout(deadline - time.time())
            try:
                chunk = s.recv(4096)
            except socket.timeout:
                break
            if not chunk:
                break
            buf.extend(chunk)
    except Exception as e:
        print(f"    Erreur socket : {e}")
        return None
    finally:
        try:
            s.close()
        except Exception:
            pass
    return bytes(buf) if buf else None


def read_value(pid: int, debug: bool = False) -> int | None:
    raw = transact(build_read(pid))
    if not raw:
        print("    [debug] aucune réponse reçue")
        return None

    if debug:
        print(f"    [debug] {len(raw)} bytes reçus : {raw.hex()}")

    i = 0
    while i < len(raw):
        if raw[i] != 0x68 or i + 3 > len(raw):
            i += 1
            continue
        l_val = struct.unpack("<H", raw[i+1:i+3])[0]
        if l_val < 5 or i + l_val + 6 > len(raw):
            i += 1
            continue
        frame = raw[i : i + l_val + 6]
        if frame[-1] != 0x16:
            i += 1
            continue
        cmd = frame[7]
        payload = frame[8:-3]
        if debug:
            src = struct.unpack("<H", frame[5:7])[0]
            print(f"    [debug] frame cmd=0x{cmd:02X} src={src} payload={payload.hex()}")
        if cmd != 0xC3:
            i += l_val + 6
            continue
        if len(payload) >= 6:
            resp_pid = struct.unpack("<H", payload[4:6])[0]
            if debug:
                print(f"    [debug] resp_pid={resp_pid}  val_bytes={payload[6:].hex()}")
            if resp_pid == pid and len(payload) >= 10:
                return struct.unpack("<i", payload[6:10])[0]
        i += l_val + 6
    return None


def write_value(pid: int, value: int) -> bool:
    raw = transact(build_write(pid, value))
    return raw is not None


def main():
    print("=" * 60)
    print(f"  Test marche forcée pompe ECS  —  {IP}:{PORT}")
    print(f"  Param ID={PID}  ON={ON_VAL} (0x{ON_VAL:04X})  OFF={OFF_VAL}")
    print("=" * 60)

    # ── Lecture état initial ──────────────────────────────────────────────
    val = read_value(PID, debug=True)
    print(f"\n  État actuel : {val}")

    # ── Activation ───────────────────────────────────────────────────────
    input("\n  Appuie sur [Entrée] pour activer la marche forcée...")
    ok = write_value(PID, ON_VAL)
    print(f"  Écriture {ON_VAL} → {'OK' if ok else 'ÉCHEC'}")
    time.sleep(1)
    val = read_value(PID, debug=True)
    print(f"  Lecture après activation : {val}  {'✓' if val == ON_VAL else '✗ valeur inattendue'}")

    # ── Désactivation ─────────────────────────────────────────────────────
    input("\n  Appuie sur [Entrée] pour désactiver...")
    ok = write_value(PID, OFF_VAL)
    print(f"  Écriture {OFF_VAL} → {'OK' if ok else 'ÉCHEC'}")
    time.sleep(1)
    val = read_value(PID, debug=True)
    print(f"  Lecture après désactivation : {val}  {'✓' if val == OFF_VAL else '✗ valeur inattendue'}")

    print("\n  Terminé.")


if __name__ == "__main__":
    main()
