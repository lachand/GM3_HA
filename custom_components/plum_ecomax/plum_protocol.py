"""Utilities for the Plum EcoMAX protocol.

This module defines the data structures used to represent boiler parameters
and network frames. It also contains the CRC-16 algorithm used to verify
data integrity over the RS-485/TCP connection.
"""
import struct
from dataclasses import dataclass
from typing import ClassVar, Any

# --- CONSTANTES ---
START_BYTE = 0x68
STOP_BYTE = 0x16

# Mapping des types selon Spec 1.4.2
DATA_TYPES = {
    0x01: ("SHORT INT", 1), 0x02: ("INT", 2), 0x03: ("LONG INT", 4),
    0x04: ("BYTE", 1), 0x05: ("WORD", 2), 0x06: ("DWORD", 4),
    0x07: ("SHORT REAL", 4), 0x09: ("LONG REAL", 8), 0x0A: ("BOOLEAN", 1),
    0x0C: ("STRING", 0)
}

def compute_crc16(data: bytes) -> int:
    """Calculates the CRC-16/CCITT checksum.

    Used by the ecoNET protocol to verify frame integrity.
    Polynomial: 0x1021.

    Args:
        data: The raw bytes to calculate the checksum for.

    Returns:
        int: The calculated 16-bit checksum.
    """
    crc = 0x0000
    poly = 0x1021
    for b in data:
        crc ^= (b << 8)
        for _ in range(8):
            if crc & 0x8000: crc = (crc << 1) ^ poly
            else: crc <<= 1
            crc &= 0xFFFF
    return crc

@dataclass
class BoilerParameter:
    """Represents a specific parameter of the boiler.

    This data class holds metadata about a parameter (name, unit, type)
    and provides helper properties to decode the 'info_byte' which contains
    permissions and data type information.

    Attributes:
        index (int): The unique ID of the parameter.
        name (str): The human-readable name.
        unit (str): The unit of measurement (e.g., "°C", "%").
        exponent (int): Power of 10 to divide/multiply the raw value.
        info_byte (int): A bitmask byte containing type and permissions.
        value (Any): The current cached value (optional).
    """
    index: int
    name: str
    unit: str
    exponent: int
    info_byte: int
    value: Any = None  # Pour stocker la valeur courante plus tard

    @property
    def is_modifiable(self) -> bool:
        """Checks if the parameter can be modified (Bit 5).

        Returns:
            bool: True if writable.
        """
        return bool((self.info_byte >> 5) & 1)

    @property
    def is_readable(self) -> bool:
        """Checks if the parameter can be read (Bit 4).

        Returns:
            bool: True if readable.
        """
        return bool((self.info_byte >> 4) & 1)

    @property
    def data_type_code(self) -> int:
        """Extracts the data type code (Bits 0-3).

        Returns:
            int: The integer code representing the type (see DATA_TYPES).
        """
        return self.info_byte & 0x0F

    @property
    def type_name(self) -> str:
        """Returns the human-readable type name.

        Returns:
            str: The type name (e.g., "BYTE", "FLOAT").
        """
        return DATA_TYPES.get(self.data_type_code, ("UNK", 0))[0]

    def format_value(self, raw_value) -> float | int | str:
        """Formats the raw value according to the exponent.

        Args:
            raw_value: The raw numerical value received from the device.

        Returns:
            float | int | str: The processed value (e.g., 205 becomes 20.5 if exp is 1).
        """
        if isinstance(raw_value, (int, float)) and self.exponent != 0:
            # Code U2 pour l'exposant (gestion des négatifs)
            exp = self.exponent
            return raw_value * (10 ** exp)
        return raw_value

    def __str__(self):
        flags = ""
        if self.is_modifiable: flags += "W" # Write
        if self.is_readable: flags += "R"   # Read

        unit_str = f"[{self.unit}]" if self.unit else ""
        return f"ID {self.index:<4} | {flags:<2} | {self.type_name:<10} | {self.name} {unit_str}"

@dataclass
class BoilerFrame:
    """Represents a low-level network frame.

    Handles the encapsulation of the ecoNET protocol, including
    header construction and CRC appending.

    Attributes:
        dest (int): Destination address (usually 1 for boiler).
        src (int): Source address (usually 100 for HA).
        func (int): Function code (e.g., 0x43 for read).
        data (bytes): The payload of the message.
    """
    dest: int
    src: int
    func: int
    data: bytes

    def to_bytes(self) -> bytes:
        """Serializes the frame into bytes for transmission.

        Adds the header (Length, Dest, Src, Func), calculates the CRC,
        and adds Start/Stop bytes.

        Returns:
            bytes: The full binary frame ready to be sent over TCP.
        """
        # L = Dest(2) + Src(2) + Func(1) + Data(n)
        l_val = 2 + 2 + 1 + len(self.data)

        # Header (Little Endian)
        header = struct.pack("<HHHB", l_val, self.dest, self.src, self.func)
        body = header + self.data

        # CRC (Big Endian >H sur le réseau !)
        crc = compute_crc16(body)

        return struct.pack("B", START_BYTE) + body + struct.pack(">H", crc) + struct.pack("B", STOP_BYTE)

    @classmethod
    def from_bytes(cls, data: bytes) -> 'BoilerFrame':
        """Creates a BoilerFrame instance from the raw body.

        Args:
            data: The body of the frame (excluding Start, Stop, CRC, and Length).

        Returns:
            BoilerFrame: An initialized frame object.
        """
        # data doit être le body (sans start/stop/crc/len)
        # Structure Body reçue: Dest(2) Src(2) Func(1) Payload(n)
        dest = struct.unpack("<H", data[0:2])[0]
        src = struct.unpack("<H", data[2:4])[0]
        func = data[4]
        payload = data[5:]
        return cls(dest, src, func, payload)