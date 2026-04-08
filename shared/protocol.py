"""
RemoteGate shared protocol definitions.

Defines message types and binary frame encoding/decoding
used by both the relay server and the Windows agent.
"""

import struct

# ---------------------------------------------------------------------------
# JSON message types
# ---------------------------------------------------------------------------
MESSAGE_TYPES = {
    "auth",
    "register_agent",
    "mouse",
    "key",
    "session_start",
    "session_end",
    "config",
    "ping",
    "pong",
}

# ---------------------------------------------------------------------------
# Binary frame constants
# ---------------------------------------------------------------------------
FRAME_TYPE_SCREEN = 0x01

# Header layout: [1 byte type][4 bytes uint32 frame number]
_HEADER_FORMAT = ">BI"  # unsigned char + unsigned int (big-endian)
_HEADER_SIZE = struct.calcsize(_HEADER_FORMAT)  # 5 bytes


def build_frame_header(frame_num: int) -> bytes:
    """Build a 5-byte binary header for a screen frame.

    Layout:
        byte 0     – frame type (0x01 for screen)
        bytes 1-4  – frame number as uint32 big-endian

    Args:
        frame_num: Monotonically increasing frame counter.

    Returns:
        5-byte header ready to be prepended to the JPEG payload.
    """
    return struct.pack(_HEADER_FORMAT, FRAME_TYPE_SCREEN, frame_num)


def parse_frame_header(data: bytes) -> tuple[int, int, bytes]:
    """Parse a binary frame message into its components.

    Args:
        data: Raw binary message (header + payload).

    Returns:
        A tuple of (frame_type, frame_number, jpeg_payload).

    Raises:
        ValueError: If the data is shorter than the header size.
    """
    if len(data) < _HEADER_SIZE:
        raise ValueError(
            f"Frame data too short: expected at least {_HEADER_SIZE} bytes, "
            f"got {len(data)}"
        )

    frame_type, frame_num = struct.unpack(_HEADER_FORMAT, data[:_HEADER_SIZE])
    payload = data[_HEADER_SIZE:]
    return frame_type, frame_num, payload
