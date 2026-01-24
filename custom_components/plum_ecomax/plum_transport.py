"""Asynchronous TCP Transport for Plum EcoMAX.

This module implements the low-level network transport layer using Python's
asyncio. It is responsible for:

* Establishing and managing the TCP connection.
* Buffering incoming bytes to handle TCP fragmentation.
* Parsing the binary stream to extract valid protocol frames (Start Byte, Length, CRC, Stop Byte).
"""
import asyncio
import struct
import logging
from typing import Optional, List
from .plum_utils import BoilerFrame, START_BYTE, STOP_BYTE, compute_crc16

logger = logging.getLogger(__name__)

class AsyncPlumTransport:
    """Manages the asynchronous TCP connection to the ecomax module.

    This class handles the raw byte stream, ensuring that fragmented packets
    are reassembled correctly and that invalid data (noise) is discarded.
    """

    def __init__(self, host: str, port: int):
        """Initializes the transport layer.

        Args:
            host: The IP address or hostname of the ecoNET module.
            port: The TCP port (usually 8899).
        """
        self.host = host
        self.port = port
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self._buffer = bytearray()

    async def connect(self):
        """Establishes the TCP connection.

        Raises:
            OSError: If the connection fails (timeout, refused, etc.).
        """
        logger.debug(f"Connecting to {self.host}:{self.port}")
        self.reader, self.writer = await asyncio.open_connection(self.host, self.port)

    async def close(self):
        """Closes the TCP connection and clears resources."""
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
        self.reader = None
        self.writer = None

    async def send_frame(self, frame: BoilerFrame):
        """Serializes and sends a frame over the network.

        Args:
            frame: The BoilerFrame object to send.

        Raises:
            ConnectionError: If the socket is not connected.
        """
        if not self.writer:
            raise ConnectionError("Not connected")

        packet = frame.to_bytes()
        # Flush input buffer before sending (Strategy from working script)
        self._buffer.clear()
        # Note: real socket flush is hard in asyncio without reading,
        # but clearing our parser buffer helps.

        self.writer.write(packet)
        await self.writer.drain()

    async def read_frame(self, timeout: float = 2.0) -> Optional[BoilerFrame]:
        """Reads the stream until a valid frame is found or timeout occurs.

        This method handles TCP stream processing:
        1.  It reads chunks of data into a persistent buffer.
        2.  It scans for the START_BYTE (0x68).
        3.  It parses the header to determine the expected frame length.
        4.  It verifies the CRC and STOP_BYTE.

        Args:
            timeout: Maximum time to wait for a complete frame in seconds.

        Returns:
            Optional[BoilerFrame]: A valid frame object, or None if timeout/error occurs.

        Raises:
            ConnectionError: If the socket is not connected.
        """
        if not self.reader:
            raise ConnectionError("Not connected")

        start_time = asyncio.get_running_loop().time()

        while (asyncio.get_running_loop().time() - start_time) < timeout:
            try:
                # Read in small chunks
                chunk = await asyncio.wait_for(self.reader.read(1024), timeout=0.5)
                if not chunk:
                    return None
                self._buffer.extend(chunk)

                # Parsing
                while True:
                    try:
                        start_idx = self._buffer.index(START_BYTE)
                    except ValueError:
                        self._buffer.clear()
                        break  # No start byte, waiting for more data

                    # Align the buffer
                    if start_idx > 0:
                        del self._buffer[:start_idx]

                    # Minimum header: 68 L L
                    if len(self._buffer) < 3:
                        break

                    l_val = struct.unpack("<H", self._buffer[1:3])[0]
                    total_len = (
                        l_val + 6
                    )  # 68 + L(2) + Content(L) + CRC(2) + 16

                    if len(self._buffer) < total_len:
                        break  # Incomplete frame, waiting

                    # Extraction
                    frame_bytes = self._buffer[:total_len]

                    # CRC Validation
                    # Body for CRC = L(2) + Content(L) => indices 1 to 1+2+L
                    body_end = 1 + 2 + l_val
                    body = frame_bytes[1:body_end]

                    received_crc = struct.unpack(
                        ">H", frame_bytes[body_end : body_end + 2]
                    )[0]

                    if (
                        compute_crc16(body) == received_crc
                        and frame_bytes[-1] == STOP_BYTE
                    ):
                        # Valid Frame!
                        # Extract internal content: Dest, Src, Func, Data
                        # Body contains: L(2) Dest(2) Src(2) Func(1) Payload...
                        # We pass body[2:] to from_bytes because from_bytes expects Dest...
                        valid_frame = BoilerFrame.from_bytes(body[2:])

                        del self._buffer[:total_len]  # Consume
                        return valid_frame
                    else:
                        # Invalid CRC, discard the StartByte and retry
                        del self._buffer[0]

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Transport error: {e}")
                return None

        return None