"""
WebSocket connection manager for the RemoteGate Agent.
Handles connecting to the relay server, streaming frames, receiving input
commands, and maintaining heartbeat with automatic reconnection.
"""

import asyncio
import json
import logging
import socket
import time

import websockets

from capture import ScreenCapture
from config import AgentConfig
from encoder import encode_frame
from input_handler import InputHandler

logger = logging.getLogger(__name__)

# Reconnection backoff settings
BACKOFF_BASE = 1
BACKOFF_MAX = 30
BACKOFF_FACTOR = 2

# Heartbeat settings
HEARTBEAT_INTERVAL = 30  # seconds


class AgentConnection:
    """Manages the full lifecycle of the agent's connection to the relay server."""

    def __init__(self, config: AgentConfig):
        self._config = config
        self._capture = ScreenCapture()
        self._input_handler = InputHandler()

        # Streaming state
        self._fps = config.default_fps
        self._quality = config.default_quality
        self._scale = config.default_scale
        self._frame_num = 0

        # Heartbeat state
        self._last_pong = time.time()

        # Executor for running blocking input operations
        self._executor_loop: asyncio.AbstractEventLoop | None = None

        logger.info(
            "AgentConnection created: relay=%s, agent_id=%s, fps=%d, quality=%d, scale=%.2f",
            config.relay_url,
            config.agent_id,
            self._fps,
            self._quality,
            self._scale,
        )

    async def _connect(self) -> websockets.WebSocketClientProtocol:
        """Connect to the relay server and perform authentication and registration.

        Returns:
            The connected WebSocket instance.
        """
        url = f"{self._config.relay_url}/ws/agent"
        logger.info("Connecting to %s", url)

        ws = await websockets.connect(
            url,
            ping_interval=None,  # We handle our own heartbeat
            max_size=10 * 1024 * 1024,  # 10MB max message
            close_timeout=5,
        )
        logger.info("WebSocket connected")

        # Authenticate
        auth_msg = json.dumps({
            "type": "auth",
            "token": self._config.agent_secret,
        })
        await ws.send(auth_msg)
        auth_resp = json.loads(await ws.recv())
        if auth_resp.get("status") != "ok":
            raise ConnectionError(f"Auth failed: {auth_resp.get('message', 'unknown')}")
        logger.info("Auth succeeded")

        # Register agent
        width, height = self._capture.get_resolution()
        register_msg = json.dumps({
            "type": "register_agent",
            "agent_id": self._config.agent_id,
            "hostname": socket.gethostname(),
            "resolution": [width, height],
        })
        await ws.send(register_msg)
        reg_resp = json.loads(await ws.recv())
        if reg_resp.get("status") != "ok":
            raise ConnectionError(f"Registration failed: {reg_resp.get('message', 'unknown')}")
        logger.info("Agent registered: id=%s, hostname=%s, resolution=%dx%d",
                     self._config.agent_id, socket.gethostname(), width, height)

        return ws

    async def _stream_loop(self, ws: websockets.WebSocketClientProtocol):
        """Continuously capture, encode, and send screen frames.

        Maintains target FPS by measuring how long each capture+send cycle
        takes and adjusting sleep time. Skips frames if sending falls behind.
        """
        logger.info("Stream loop started (fps=%d, quality=%d, scale=%.2f)",
                     self._fps, self._quality, self._scale)

        while True:
            frame_start = time.monotonic()

            try:
                # Capture and encode
                image = self._capture.get_frame(scale=self._scale)
                frame_data = encode_frame(image, self._quality, self._frame_num)
                self._frame_num += 1

                # Send binary frame
                await ws.send(frame_data)

            except websockets.ConnectionClosed:
                logger.warning("Connection closed during frame send")
                raise
            except Exception:
                logger.exception("Error in stream loop (frame %d)", self._frame_num)

            # Calculate sleep to maintain target FPS
            elapsed = time.monotonic() - frame_start
            target_interval = 1.0 / max(self._fps, 1)
            sleep_time = target_interval - elapsed

            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            else:
                # We're behind schedule; skip sleep to catch up
                # Yield control briefly to allow other tasks to run
                await asyncio.sleep(0)
                if elapsed > target_interval * 2:
                    logger.debug(
                        "Frame %d took %.1fms (target %.1fms), skipping to catch up",
                        self._frame_num - 1,
                        elapsed * 1000,
                        target_interval * 1000,
                    )

    async def _receive_loop(self, ws: websockets.WebSocketClientProtocol):
        """Receive and process messages from the relay server.

        Handles input commands (mouse/keyboard), config updates, and pong messages.
        Input handling is dispatched to a thread executor since pynput operations
        are blocking.
        """
        logger.info("Receive loop started")
        loop = asyncio.get_running_loop()

        async for message in ws:
            try:
                if isinstance(message, bytes):
                    logger.debug("Received binary message (%d bytes), ignoring", len(message))
                    continue

                data = json.loads(message)
                msg_type = data.get("type")

                if msg_type in ("mouse", "key"):
                    # Run blocking pynput calls in thread executor
                    await loop.run_in_executor(
                        None, self._input_handler.handle_input, data
                    )

                elif msg_type == "config":
                    self._apply_config(data)

                elif msg_type == "pong":
                    self._last_pong = time.time()
                    logger.debug("Pong received (ts=%.0f)", data.get("ts", 0))

                elif msg_type == "error":
                    logger.error("Server error: %s", data.get("message", "unknown"))

                else:
                    logger.debug("Unhandled message type: %s", msg_type)

            except json.JSONDecodeError:
                logger.warning("Received non-JSON text message: %s", message[:100])
            except Exception:
                logger.exception("Error processing message")

        logger.info("Receive loop ended (connection closed)")

    def _apply_config(self, data: dict):
        """Apply dynamic configuration changes from the relay server.

        Args:
            data: Config dict that may contain "fps", "quality", "scale" keys.
        """
        if "fps" in data:
            self._fps = max(1, min(60, int(data["fps"])))
            logger.info("FPS updated to %d", self._fps)

        if "quality" in data:
            self._quality = max(1, min(100, int(data["quality"])))
            logger.info("Quality updated to %d", self._quality)

        if "scale" in data:
            self._scale = max(0.1, min(1.0, float(data["scale"])))
            logger.info("Scale updated to %.2f", self._scale)

    async def _heartbeat_loop(self, ws: websockets.WebSocketClientProtocol):
        """Send periodic ping messages to keep the connection alive.

        Sends a ping every HEARTBEAT_INTERVAL seconds.
        """
        logger.info("Heartbeat loop started (interval=%ds)", HEARTBEAT_INTERVAL)

        while True:
            try:
                ping_msg = json.dumps({
                    "type": "ping",
                    "ts": time.time(),
                })
                await ws.send(ping_msg)
                logger.debug("Ping sent")
            except websockets.ConnectionClosed:
                logger.warning("Connection closed during heartbeat")
                raise
            except Exception:
                logger.exception("Error sending heartbeat")

            await asyncio.sleep(HEARTBEAT_INTERVAL)

    async def run(self):
        """Main run loop with automatic reconnection and exponential backoff.

        Connects to the relay server and runs the stream, receive, and heartbeat
        loops concurrently. On disconnection or error, waits with exponential
        backoff before retrying.
        """
        backoff = BACKOFF_BASE

        while True:
            try:
                ws = await self._connect()
                # Reset backoff on successful connection
                backoff = BACKOFF_BASE
                self._last_pong = time.time()

                # Run all three loops concurrently; if any exits, we reconnect
                await asyncio.gather(
                    self._stream_loop(ws),
                    self._receive_loop(ws),
                    self._heartbeat_loop(ws),
                )

            except websockets.ConnectionClosed as e:
                logger.warning("Connection closed: code=%s reason=%s", e.code, e.reason)

            except ConnectionRefusedError:
                logger.warning("Connection refused by relay server")

            except OSError as e:
                logger.warning("Network error: %s", e)

            except Exception:
                logger.exception("Unexpected error in agent run loop")

            logger.info("Reconnecting in %d seconds...", backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * BACKOFF_FACTOR, BACKOFF_MAX)

    def close(self):
        """Clean up resources."""
        self._capture.close()
        logger.info("AgentConnection closed")
