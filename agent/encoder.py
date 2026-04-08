"""
Frame encoder module.
Encodes PIL Images to JPEG with a binary header for the streaming protocol.

Binary frame format:
  [1 byte: frame_type (0x01 = screen)] [4 bytes: frame_number (big-endian uint32)] [JPEG data]
"""

import struct
from io import BytesIO

from PIL import Image

# Frame type constants
FRAME_TYPE_SCREEN = 0x01


def encode_frame(image: Image.Image, quality: int, frame_num: int) -> bytes:
    """Encode a PIL Image as a JPEG frame with a 5-byte binary header.

    Args:
        image: The PIL Image to encode.
        quality: JPEG quality (1-100).
        frame_num: Monotonically increasing frame counter.

    Returns:
        Bytes containing the 5-byte header followed by JPEG data.
    """
    # Encode image to JPEG in memory
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=quality, optimize=False)
    jpeg_bytes = buffer.getvalue()

    # Build 5-byte header: 1 byte type + 4 bytes frame number (big-endian unsigned int)
    header = struct.pack(">BI", FRAME_TYPE_SCREEN, frame_num & 0xFFFFFFFF)

    return header + jpeg_bytes
