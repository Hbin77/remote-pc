"""
WebRTC peer connection handler for the RemoteGate Agent.
Creates a video track from screen captures and a DataChannel for input.
"""

import asyncio
import json
import logging
import time
from fractions import Fraction

import av
from aiortc import (
    RTCIceCandidate,
    RTCPeerConnection,
    RTCSessionDescription,
    MediaStreamTrack,
)
from aiortc.contrib.media import MediaStreamError

from capture import ScreenCapture
from input_handler import InputHandler

logger = logging.getLogger(__name__)


class ScreenVideoTrack(MediaStreamTrack):
    """A video track that captures the screen and delivers av.VideoFrames."""

    kind = "video"

    def __init__(self, capture: ScreenCapture, fps: int = 24, scale: float = 0.75):
        super().__init__()
        self._capture = capture
        self._fps = fps
        self._scale = scale
        self._pts = 0
        self._time_base = Fraction(1, fps)
        self._start_time: float | None = None

    async def recv(self) -> av.VideoFrame:
        """Capture a screen frame and return it as an av.VideoFrame.

        Maintains target FPS by sleeping the appropriate amount between frames.
        """
        if self._start_time is None:
            self._start_time = time.monotonic()

        # Calculate the target time for this frame and sleep until then
        target_time = self._start_time + (self._pts / self._fps)
        now = time.monotonic()
        sleep_duration = target_time - now
        if sleep_duration > 0:
            await asyncio.sleep(sleep_duration)

        try:
            image = self._capture.get_frame(scale=self._scale)
            frame = av.VideoFrame.from_image(image)
            frame.pts = self._pts
            frame.time_base = self._time_base
            self._pts += 1
            return frame
        except Exception:
            logger.exception("Error capturing screen frame")
            raise MediaStreamError()


class AgentPeerConnection:
    """Manages a WebRTC peer connection for P2P screen sharing and input."""

    def __init__(
        self,
        capture: ScreenCapture,
        input_handler: InputHandler,
        ice_servers: list[dict] | None = None,
    ):
        self._capture = capture
        self._input_handler = input_handler
        self._ice_servers = ice_servers
        self._pc: RTCPeerConnection | None = None
        self._video_track: ScreenVideoTrack | None = None
        self._ice_candidates: list[dict] = []
        self._ice_gather_complete = asyncio.Event()
        self._setup_pc()

    def _setup_pc(self):
        """Create and configure the RTCPeerConnection."""
        from aiortc import RTCConfiguration, RTCIceServer

        if self._ice_servers:
            ice_server_objs = []
            for server in self._ice_servers:
                ice_server_objs.append(RTCIceServer(
                    urls=server.get("urls", server.get("url", "")),
                    username=server.get("username"),
                    credential=server.get("credential"),
                ))
            config = RTCConfiguration(iceServers=ice_server_objs)
        else:
            config = RTCConfiguration(iceServers=[
                RTCIceServer(urls="stun:stun.l.google.com:19302"),
                RTCIceServer(urls="stun:stun1.l.google.com:19302"),
            ])

        self._pc = RTCPeerConnection(configuration=config)

        # Add video track
        self._video_track = ScreenVideoTrack(
            capture=self._capture,
            fps=24,
            scale=0.75,
        )
        self._pc.addTrack(self._video_track)

        # Handle DataChannel for input
        @self._pc.on("datachannel")
        def on_datachannel(channel):
            logger.info("DataChannel opened: label=%s", channel.label)
            if channel.label == "input":
                @channel.on("message")
                def on_message(message):
                    self._handle_datachannel_message(message)

        # Log ICE connection state changes
        @self._pc.on("iceconnectionstatechange")
        async def on_ice_state_change():
            state = self._pc.iceConnectionState
            logger.info("ICE connection state: %s", state)
            if state == "failed":
                logger.error("ICE connection failed")
            elif state == "closed":
                logger.info("ICE connection closed")

        # Collect ICE candidates
        @self._pc.on("icecandidate")
        def on_ice_candidate(candidate):
            if candidate is None:
                # Gathering complete
                self._ice_gather_complete.set()
            else:
                candidate_dict = {
                    "candidate": candidate.candidate,
                    "sdpMid": candidate.sdpMid,
                    "sdpMLineIndex": candidate.sdpMLineIndex,
                }
                self._ice_candidates.append(candidate_dict)

        logger.info("RTCPeerConnection configured")

    def _handle_datachannel_message(self, message: str):
        """Parse a DataChannel message and dispatch to the input handler.

        Runs the blocking pynput call in a thread executor.
        """
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            logger.warning("Invalid JSON from DataChannel: %s", message[:100])
            return

        try:
            loop = asyncio.get_running_loop()
            loop.run_in_executor(None, self._input_handler.handle_input, data)
        except RuntimeError:
            # No running event loop; run synchronously as fallback
            logger.warning("No event loop for executor, running input handler synchronously")
            self._input_handler.handle_input(data)
        except Exception:
            logger.exception("Error dispatching DataChannel input")

    async def handle_offer(self, sdp: str) -> str:
        """Process a WebRTC offer and return an answer SDP.

        Args:
            sdp: The SDP string from the remote offer.

        Returns:
            The SDP string of the local answer.
        """
        offer = RTCSessionDescription(sdp=sdp, type="offer")
        await self._pc.setRemoteDescription(offer)
        logger.info("Remote offer set")

        answer = await self._pc.createAnswer()
        await self._pc.setLocalDescription(answer)
        logger.info("Local answer created")

        return self._pc.localDescription.sdp

    async def add_ice_candidate(self, candidate_dict: dict):
        """Add a remote ICE candidate to the peer connection.

        Args:
            candidate_dict: Dict with "candidate", "sdpMid", "sdpMLineIndex" keys.
        """
        try:
            candidate_str = candidate_dict.get("candidate", "")
            if not candidate_str:
                logger.debug("Empty ICE candidate, ignoring")
                return

            # aiortc accepts candidate dicts or RTCIceCandidate objects
            try:
                candidate = RTCIceCandidate(
                    sdpMid=candidate_dict.get("sdpMid"),
                    sdpMLineIndex=candidate_dict.get("sdpMLineIndex"),
                    candidate=candidate_str,
                )
            except TypeError:
                # Fallback for aiortc versions with different constructor
                candidate = candidate_dict
            await self._pc.addIceCandidate(candidate)
            logger.debug("Added remote ICE candidate")
        except Exception:
            logger.exception("Error adding ICE candidate")

    @property
    def ice_candidates(self) -> list[dict]:
        """Return the list of collected local ICE candidates."""
        return list(self._ice_candidates)

    async def close(self):
        """Close the peer connection and stop the video track."""
        if self._video_track is not None:
            self._video_track.stop()
            self._video_track = None

        if self._pc is not None:
            await self._pc.close()
            self._pc = None

        logger.info("AgentPeerConnection closed")
