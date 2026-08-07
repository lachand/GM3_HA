"""Unit tests for plum_device.py (Family: wire protocol driver).

This is where the real bugs were (byte-offset error reading the value
after the status byte, no CRC/length/source validation, signed/unsigned
struct format mismatches -- see IMPROVEMENT_PLAN.md section 0). These
tests pin the fixed behavior against the worked examples from Plum's
"Standard Transmission Protocols ed.15" PDF so a regression here is
caught by CI instead of only by manually replaying capture logs against
the live boiler.

`_socket_transaction` opens a raw `socket.socket(...)` itself rather than
taking an injected transport, so tests that need to control what "arrives
on the wire" monkeypatch `plum_device.socket.socket` with `_FakeSocket`,
which scripts `recv()` to return pre-built frames chunk by chunk.
"""
from __future__ import annotations

import asyncio
import struct
import threading
import time

import pytest

from custom_components.plum_ecomax import plum_device as plum_device_module
from custom_components.plum_ecomax.plum_device import (
    CMD_READ_RESP,
    CMD_READ_VAL,
    CMD_WRITE_RESP,
    DEST_ID,
    SOURCE_ID,
    PlumDevice,
)


def _make_device(**overrides) -> PlumDevice:
    device = PlumDevice("192.0.2.1", **overrides)
    return device


# ---------------------------------------------------------------------------
# _extract_valid_frame: ground-truth bytes from spec 1.5.3.12 (p.25)
# ---------------------------------------------------------------------------

# Response to cmd 0x43, session=0x003B (59), one block of 1 param (pid=16,
# status=0x05, value=00 E0 2B 46) then one block of 3 params (pid=147..149).
SPEC_READ_RESPONSE = bytes.fromhex(
    "68"          # start
    "2000"        # l_val = 0x0020 = 32
    "0000"        # dest
    "0100"        # src = 1 (boiler)
    "C3"          # func = READ_RESP
    "3B00"        # session = 59
    "02"          # n_blocks = 2
    "01" "1000"   # block0: n_params=1, first_pid=16
    "05" "00E02B46"  # status=5, value (4 bytes)
    "03" "9300"   # block1: n_params=3, first_pid=147
    "10" "0F000000"  # status, value
    "10" "10000000"  # status, value
    "10" "0A00"      # status, value (2 bytes -- a different type)
    "F14F"        # CRC
    "16"          # stop
)

SPEC_WRITE_OK_RESPONSE = bytes.fromhex("680600000001 00A9E5FC1216".replace(" ", ""))


class TestExtractValidFrame:
    def test_parses_spec_worked_example(self):
        device = _make_device()
        func, payload = device._extract_valid_frame(bytearray(SPEC_READ_RESPONSE))

        assert func == CMD_READ_RESP
        session, n_blocks = struct.unpack("<HB", payload[0:3])
        assert session == 59
        assert n_blocks == 2
        # Block 0: pid 16, status 5, value 00 E0 2B 46 (value starts right
        # after the 1-byte status -- this is the offset that was wrong).
        resp_pid = struct.unpack("<H", payload[4:6])[0]
        assert resp_pid == 16
        assert payload[6] == 0x05  # status byte, must NOT be mistaken for value
        assert payload[7:11] == bytes.fromhex("00E02B46")

    def test_skips_noise_prefix_with_coincidental_start_byte(self):
        device = _make_device()
        noisy = bytearray(b"\xAB\xCD\x68\xFF") + bytearray(SPEC_READ_RESPONSE)
        result = device._extract_valid_frame(noisy)
        assert result == device._extract_valid_frame(bytearray(SPEC_READ_RESPONSE))

    def test_rejects_corrupted_crc(self):
        device = _make_device()
        corrupted = bytearray(SPEC_READ_RESPONSE)
        corrupted[-3] ^= 0xFF  # flip a CRC byte
        assert device._extract_valid_frame(corrupted) is None

    def test_rejects_wrong_stop_byte(self):
        device = _make_device()
        corrupted = bytearray(SPEC_READ_RESPONSE)
        corrupted[-1] = 0x00
        assert device._extract_valid_frame(corrupted) is None

    def test_incomplete_frame_returns_none_without_crashing(self):
        device = _make_device()
        truncated = bytearray(SPEC_READ_RESPONSE[:10])
        assert device._extract_valid_frame(truncated) is None

    def test_rejects_frame_from_wrong_source(self):
        device = _make_device()
        wrong_src = bytearray(SPEC_READ_RESPONSE)
        # src field is at offset 5:7; DEST_ID is 1, so use 2 instead.
        wrong_src[5:7] = struct.pack("<H", 2)
        # Recompute CRC so only the source-address check can reject it.
        body = bytes(wrong_src[1:1 + 2 + struct.unpack("<H", bytes(wrong_src[1:3]))[0]])
        new_crc = device._crc16(body)
        wrong_src[-3:-1] = struct.pack(">H", new_crc)
        assert device._extract_valid_frame(wrong_src) is None

    def test_write_ok_response_parses_as_single_result_byte(self):
        device = _make_device()
        func, payload = device._extract_valid_frame(bytearray(SPEC_WRITE_OK_RESPONSE))
        assert func == CMD_WRITE_RESP
        assert payload == b"\xE5"


# ---------------------------------------------------------------------------
# _encode / _decode: signed vs. unsigned per spec 1.4.2
# ---------------------------------------------------------------------------

class TestEncodeDecodeTypes:
    @pytest.mark.parametrize(
        "ptype,value,expected_hex",
        [
            ("BYTE", 255, "ff"),
            ("SHORT_INT", -5, "fb"),
            ("WORD", 40000, "409c"),         # > INT16 max, must not raise
            ("INT", -100, "9cff"),
            ("DWORD", 3_000_000_000, "005ed0b2"),  # > INT32 max, must not raise
            ("LONG_INT", -2000000000, "006cca88"),
            ("FLOAT", 20.5, None),  # checked separately (float roundtrip)
        ],
    )
    def test_encode_matches_wire_format(self, ptype, value, expected_hex):
        device = _make_device()
        raw = device._encode(value, {"type": ptype, "exponent": 0})
        if expected_hex is not None:
            assert raw.hex() == expected_hex

    def test_encode_float_roundtrips_through_decode(self):
        device = _make_device()
        raw = device._encode(20.5, {"type": "FLOAT", "exponent": 0})
        assert device._decode(raw, {"type": "FLOAT", "exponent": 0}) == 20.5

    def test_decode_short_int_is_signed(self):
        device = _make_device()
        # 0xFB = 251 unsigned, -5 signed -- must decode as -5.
        assert device._decode(b"\xFB", {"type": "SHORT_INT", "exponent": 0}) == -5

    def test_decode_word_is_unsigned(self):
        device = _make_device()
        raw = struct.pack("<H", 40000)
        assert device._decode(raw, {"type": "WORD", "exponent": 0}) == 40000

    def test_decode_dword_is_unsigned(self):
        device = _make_device()
        raw = struct.pack("<I", 3_000_000_000)
        assert device._decode(raw, {"type": "DWORD", "exponent": 0}) == 3_000_000_000

    def test_encode_decode_round_trip_with_exponent(self):
        device = _make_device()
        param_def = {"type": "SHORT_INT", "exponent": 1}
        raw = device._encode(20.5, param_def)  # 20.5 / 10**1 = 2 (rounded, int-truncated)
        assert device._decode(raw, param_def) == 20.0  # 2 * 10**1

    def test_encode_unknown_type_returns_none(self):
        device = _make_device()
        assert device._encode(1, {"type": "NOPE", "exponent": 0}) is None

    def test_decode_too_short_returns_none(self):
        device = _make_device()
        assert device._decode(b"", {"type": "FLOAT", "exponent": 0}) is None


class TestRawStringType:
    """RAW is the spec's STRING type (1.4.2): "a sequence of characters
    followed by byte 00". Confirmed against real hardware -- the 'uid'
    parameter's raw wire bytes decode to the boiler's actual serial number
    once this type is handled (previously _decode had no RAW branch at
    all, so every RAW-typed parameter silently decoded as None forever,
    indistinguishable from a genuinely absent parameter).
    """

    def test_decode_stops_at_null_terminator(self):
        device = _make_device()
        raw = b"1M86DIP6H1GQE1H6P3KGIH5\x00\x00\x00"  # trailing padding after the string
        assert device._decode(raw, {"type": "RAW", "exponent": 0}) == "1M86DIP6H1GQE1H6P3KGIH5"

    def test_decode_without_trailing_null_still_works(self):
        device = _make_device()
        assert device._decode(b"circuit1", {"type": "RAW", "exponent": 0}) == "circuit1"

    def test_encode_appends_null_terminator(self):
        device = _make_device()
        raw = device._encode("circuit1", {"type": "RAW", "exponent": 0})
        assert raw == b"circuit1\x00"

    def test_exponent_is_not_applied_to_strings(self):
        # The exponent-scaling step in _decode/_encode guards on
        # isinstance(val, (int, float)); a non-zero exponent on a RAW
        # param must not raise or corrupt the string.
        device = _make_device()
        assert device._decode(b"abc\x00", {"type": "RAW", "exponent": 2}) == "abc"


# ---------------------------------------------------------------------------
# get_value / set_value via a fake socket (no real network)
# ---------------------------------------------------------------------------

class _FakeSocket:
    """Stands in for socket.socket: scripts one response per connection,
    delivered as pre-chunked bytes, and records what was sent.
    """

    def __init__(self, response: bytes | None, chunk_size: int = 4096):
        self._response = response
        self._chunk_size = chunk_size
        self._pos = 0
        self.sent: list[bytes] = []
        self.closed = False

    def settimeout(self, _timeout):
        pass

    def connect(self, _addr):
        pass

    def send(self, data: bytes):
        self.sent.append(data)

    def recv(self, _bufsize: int) -> bytes:
        if self._response is None or self._pos >= len(self._response):
            return b""
        chunk = self._response[self._pos: self._pos + self._chunk_size]
        self._pos += len(chunk)
        return chunk

    def close(self):
        self.closed = True


def _patch_socket(monkeypatch, response: bytes | None, chunk_size: int = 4096):
    def _factory(*_args, **_kwargs):
        return _FakeSocket(response, chunk_size=chunk_size)

    monkeypatch.setattr(plum_device_module.socket, "socket", _factory)


class TestSyncGetValue:
    def test_successful_read(self, monkeypatch):
        device = _make_device()
        _patch_socket(monkeypatch, SPEC_READ_RESPONSE)
        val = device._sync_get_value(16, {"type": "DWORD", "exponent": 0})
        assert val == struct.unpack("<I", bytes.fromhex("00E02B46"))[0]

    def test_pid_mismatch_returns_none(self, monkeypatch):
        device = _make_device()
        _patch_socket(monkeypatch, SPEC_READ_RESPONSE)
        # Response answers pid 16, not 999.
        assert device._sync_get_value(999, {"type": "DWORD", "exponent": 0}) is None

    def test_no_response_returns_none(self, monkeypatch):
        device = _make_device()
        _patch_socket(monkeypatch, None)
        assert device._sync_get_value(16, {"type": "DWORD", "exponent": 0}) is None

    def test_response_split_across_multiple_recv_calls(self, monkeypatch):
        device = _make_device()
        _patch_socket(monkeypatch, SPEC_READ_RESPONSE, chunk_size=5)
        val = device._sync_get_value(16, {"type": "DWORD", "exponent": 0})
        assert val == struct.unpack("<I", bytes.fromhex("00E02B46"))[0]


class TestSyncSetValue:
    def test_confirmed_write_returns_true(self, monkeypatch):
        device = _make_device()
        _patch_socket(monkeypatch, SPEC_WRITE_OK_RESPONSE)
        assert device._sync_set_value(172, b"payload") is True

    def test_auth_error_returns_false(self, monkeypatch):
        device = _make_device()
        # 68 06 00 00 00 01 00 a9 7d <crc> 16, code=0x7D (auth error)
        frame = bytearray(SPEC_WRITE_OK_RESPONSE)
        frame[8] = 0x7D
        body = bytes(frame[1:1 + 2 + struct.unpack("<H", bytes(frame[1:3]))[0]])
        new_crc = device._crc16(body)
        frame[-3:-1] = struct.pack(">H", new_crc)
        _patch_socket(monkeypatch, bytes(frame))
        assert device._sync_set_value(172, b"payload") is False

    def test_no_response_returns_false(self, monkeypatch):
        device = _make_device()
        _patch_socket(monkeypatch, None)
        assert device._sync_set_value(172, b"payload") is False

    def test_empty_payload_ack_counts_as_success(self, monkeypatch):
        """Confirmed against real hardware (2026-08-07, IMPROVEMENT_PLAN.md):
        this firmware ACKs a successful write with func=CMD_WRITE_RESP and
        an *empty* data field (l_val=5, no result code byte at all) instead
        of the explicit 0xE5 the spec's worked example shows. The write
        still has to be treated as confirmed, or every write against this
        hardware is reported as failed even though it actually took effect
        (verified by reading the value back after the write).
        """
        device = _make_device()
        header = struct.pack("<HHHB", 5, SOURCE_ID, DEST_ID, CMD_WRITE_RESP)
        body = header  # no payload at all
        crc = device._crc16(body)
        frame = b"\x68" + body + struct.pack(">H", crc) + b"\x16"
        _patch_socket(monkeypatch, frame)
        assert device._sync_set_value(172, b"payload") is True


class TestSyncGetValuesBatch:
    def test_batch_decodes_both_blocks(self, monkeypatch):
        device = _make_device()
        # _sync_get_values_batch increments session_id before using it, and
        # SPEC_READ_RESPONSE echoes session=59, so pre-set to 58.
        device.session_id = 58
        _patch_socket(monkeypatch, SPEC_READ_RESPONSE)

        items = [
            (16, {"type": "DWORD", "exponent": 0}),
            (147, {"type": "DWORD", "exponent": 0}),
        ]
        values = device._sync_get_values_batch(items)

        assert values[16] == struct.unpack("<I", bytes.fromhex("00E02B46"))[0]
        # Block 1 in the spec example actually holds 3 params, but we only
        # requested 1 starting at pid 147 -- n_params=3 in the response
        # doesn't match our request (n_params=1), so that block must be
        # rejected rather than guessed at.
        assert 147 not in values

    def test_empty_items_returns_empty_without_network_call(self, monkeypatch):
        device = _make_device()
        _patch_socket(monkeypatch, None)
        assert device._sync_get_values_batch([]) == {}


class TestGetValuesRawRouting:
    """get_values() must keep RAW-type slugs out of the batched request
    and fall back to reading them one at a time (variable length, no size
    prefix on the wire -- see get_values()'s docstring).
    """

    @pytest.mark.asyncio
    async def test_raw_slugs_are_excluded_from_batching_and_read_individually(self, monkeypatch):
        device = _make_device()
        device.params_map = {
            "normal_slug": {"id": 16, "type": "DWORD", "exponent": 0},
            "raw_slug": {"id": 373, "type": "RAW", "exponent": 0},
        }

        batch_calls = []

        def fake_batch(items):
            batch_calls.append(items)
            return {16: 42}

        single_calls = []

        def fake_single(pid, param):
            single_calls.append((pid, param))
            return "1M86DIP6H1GQE1H6P3KGIH5"

        monkeypatch.setattr(device, "_sync_get_values_batch", fake_batch)
        monkeypatch.setattr(device, "_sync_get_value", fake_single)

        results = await device.get_values(["normal_slug", "raw_slug"])

        assert results == {"normal_slug": 42, "raw_slug": "1M86DIP6H1GQE1H6P3KGIH5"}
        assert len(batch_calls) == 1
        assert batch_calls[0] == [(16, device.params_map["normal_slug"])]
        assert single_calls == [(373, device.params_map["raw_slug"])]


# ---------------------------------------------------------------------------
# I/O serialization: a background write and a polling read must never open
# concurrent socket transactions (IMPROVEMENT_PLAN.md section A).
# ---------------------------------------------------------------------------

class _ConcurrencyTrackingSocket:
    """Fake socket that answers a read or a write appropriately (based on
    the func byte it was sent) and records the peak number of
    simultaneously-open transactions across real OS threads
    (asyncio.to_thread runs the sync workers in a thread pool, so the
    counters need a real threading.Lock, not an asyncio.Lock).
    """

    _lock = threading.Lock()
    active = 0
    max_concurrent = 0

    def __init__(self):
        self._sent_frame: bytes | None = None
        self._responded = False

    def settimeout(self, _timeout):
        pass

    def connect(self, _addr):
        pass

    def send(self, data: bytes):
        self._sent_frame = data
        with _ConcurrencyTrackingSocket._lock:
            _ConcurrencyTrackingSocket.active += 1
            _ConcurrencyTrackingSocket.max_concurrent = max(
                _ConcurrencyTrackingSocket.max_concurrent,
                _ConcurrencyTrackingSocket.active,
            )
        time.sleep(0.05)  # hold the "connection" open long enough to overlap if unlocked

    def recv(self, _bufsize):
        if self._responded:
            return b""
        self._responded = True
        func = self._sent_frame[7]
        return SPEC_READ_RESPONSE if func == CMD_READ_VAL else SPEC_WRITE_OK_RESPONSE

    def close(self):
        with _ConcurrencyTrackingSocket._lock:
            _ConcurrencyTrackingSocket.active -= 1


class TestIoSerialization:
    @pytest.mark.asyncio
    async def test_concurrent_get_and_set_never_overlap_on_the_wire(self, monkeypatch):
        _ConcurrencyTrackingSocket.active = 0
        _ConcurrencyTrackingSocket.max_concurrent = 0
        monkeypatch.setattr(
            plum_device_module.socket, "socket",
            lambda *a, **k: _ConcurrencyTrackingSocket(),
        )

        device = _make_device()
        device.params_map = {"pid16": {"id": 16, "type": "DWORD", "exponent": 0}}

        await asyncio.gather(
            device.get_value("pid16", retries=1),
            device.set_value("pid16", 5, password="0000", user="admin"),
            device.get_value("pid16", retries=1),
        )

        assert _ConcurrencyTrackingSocket.max_concurrent == 1
