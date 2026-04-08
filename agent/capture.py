"""
Screen capture module using mss.
Grabs the primary monitor and returns PIL Image frames.
"""

import logging

import mss
from PIL import Image

logger = logging.getLogger(__name__)


class ScreenCapture:
    """Captures the primary monitor screen using mss."""

    def __init__(self):
        self._sct = mss.mss()
        # Primary monitor is index 1 (index 0 is the virtual "all monitors" screen)
        self._monitor = self._sct.monitors[1]
        logger.info(
            "ScreenCapture initialized: %dx%d",
            self._monitor["width"],
            self._monitor["height"],
        )

    def get_frame(self, scale: float = 1.0) -> Image.Image:
        """Capture the primary monitor and return as a PIL Image.

        Args:
            scale: Resize factor (0.0-1.0). 1.0 means native resolution.

        Returns:
            PIL Image of the captured screen.
        """
        raw = self._sct.grab(self._monitor)
        # mss returns BGRA, convert to RGB via PIL
        image = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")

        if scale != 1.0 and 0.0 < scale < 1.0:
            new_width = int(image.width * scale)
            new_height = int(image.height * scale)
            image = image.resize((new_width, new_height), Image.LANCZOS)

        return image

    def get_resolution(self) -> tuple[int, int]:
        """Return the native resolution of the primary monitor.

        Returns:
            Tuple of (width, height).
        """
        return self._monitor["width"], self._monitor["height"]

    def close(self):
        """Release mss resources."""
        try:
            self._sct.close()
            logger.info("ScreenCapture closed")
        except Exception as e:
            logger.warning("Error closing ScreenCapture: %s", e)
