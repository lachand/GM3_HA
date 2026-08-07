"""Unit tests for plum_protocol.py (CRC16, BoilerFrame, BoilerParameter).

The CRC vectors and frame layout come straight from Plum's "Standard
Transmission Protocols ed.15" PDF (sections 1.2 and 1.5.1.1/1.5.2.1):
worked examples of real request/response bytes, used here as ground truth
instead of re-deriving the algorithm from scratch.
"""
from __future__ import annotations

from custom_components.plum_ecomax.plum_protocol import (
    BoilerFrame,
    BoilerParameter,
    compute_crc16,
)


class TestCrc16Vectors:
    """CRC-CCITT (poly 0x1021, init 0x0000), covering L+Dest+Src+Func+Data
    (never the start/stop bytes) -- per spec section 1.2.
    """

    def test_readout_device_id_request(self):
        # 68 05 00 06 00 00 00 00 b4 22 16 (spec 1.5.1.1)
        body = bytes.fromhex("05000600000000")
        assert compute_crc16(body) == 0xB422

    def test_readout_device_id_v2_request(self):
        # 68 05 00 06 00 00 00 09 25 0b 16 (spec 1.5.2.1)
        body = bytes.fromhex("05000600000009")
        assert compute_crc16(body) == 0x250B

    def test_empty_input_is_zero(self):
        assert compute_crc16(b"") == 0x0000


class TestBoilerFrameRoundTrip:
    def test_to_bytes_matches_spec_example(self):
        # Request from spec 1.5.1.1, direct addressing mode:
        # 68 05 00 06 00 00 00 00 b4 22 16
        frame = BoilerFrame(dest=6, src=0, func=0x00, data=b"")
        assert frame.to_bytes() == bytes.fromhex("6805000600000000b42216")

    def test_to_bytes_includes_start_and_stop_bytes(self):
        frame = BoilerFrame(dest=1, src=100, func=0x43, data=b"\x01\x02")
        raw = frame.to_bytes()
        assert raw[0] == 0x68
        assert raw[-1] == 0x16

    def test_round_trip_preserves_fields(self):
        original = BoilerFrame(dest=1, src=100, func=0x43, data=b"\x2A\x00\x01\x01\x10\x00")
        raw = original.to_bytes()

        # from_bytes expects the body without start/stop/CRC/length, i.e.
        # Dest(2) Src(2) Func(1) Payload(n) -- see BoilerFrame.from_bytes docstring.
        l_val = int.from_bytes(raw[1:3], "little")
        body_without_length = raw[3:3 + l_val]

        restored = BoilerFrame.from_bytes(body_without_length)
        assert restored.dest == original.dest
        assert restored.src == original.src
        assert restored.func == original.func
        assert restored.data == original.data

    def test_crc_verifies_against_compute_crc16(self):
        frame = BoilerFrame(dest=1, src=100, func=0x43, data=b"\x01\x02\x03")
        raw = frame.to_bytes()
        l_val = int.from_bytes(raw[1:3], "little")
        body = raw[1:3 + l_val]  # L + Dest + Src + Func + Data
        received_crc = int.from_bytes(raw[-3:-1], "big")
        assert compute_crc16(body) == received_crc


class TestBoilerParameter:
    def test_flags_and_type_from_info_byte(self):
        # b7 unused, b6=record, b5=modifiable, b4=readable, b3-b0=type code
        # 0b00110001 = modifiable + readable + SHORT_INT (0x1)
        param = BoilerParameter(index=172, name="HDWPumpForce", unit="", exponent=0, info_byte=0b00110001)
        assert param.is_modifiable is True
        assert param.is_readable is True
        assert param.data_type_code == 0x1
        assert param.type_name == "SHORT INT"

    def test_read_only_flag(self):
        # readable only (b4=1), not modifiable (b5=0)
        param = BoilerParameter(index=1, name="ReadOnly", unit="", exponent=0, info_byte=0b00010111)
        assert param.is_readable is True
        assert param.is_modifiable is False

    def test_unknown_type_code_falls_back(self):
        param = BoilerParameter(index=1, name="X", unit="", exponent=0, info_byte=0b1111)
        assert param.type_name == "UNK"

    def test_format_value_applies_exponent(self):
        # exponent=1 means raw value is in tenths (spec 1.4.2 <exponent> example)
        param = BoilerParameter(index=1, name="Pressure", unit="kPa", exponent=1, info_byte=0)
        assert param.format_value(205) == 2050  # 205 * 10**1, matches the class's own convention

    def test_format_value_passthrough_for_non_numeric(self):
        param = BoilerParameter(index=1, name="Text", unit="", exponent=0, info_byte=0)
        assert param.format_value("hello") == "hello"
