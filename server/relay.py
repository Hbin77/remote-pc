"""
RemoteGate WebSocket relay.

Manages two classes of WebSocket connections:
  - **Agent** connections  (WS /ws/agent)  – authenticated via AGENT_SECRET
  - **Client** connections (WS /ws/client) – authenticated via JWT

The relay forwards binary screen frames from agent -> client and JSON
input events from client -> agent.
"""

import hmac
import json
import logging
import time

from fastapi import WebSocket, WebSocketDisconnect

from auth import verify_token
from config import settings
from models import (
    create_session,
    end_session,
    register_agent,
    update_agent_status,
)

logger = logging.getLogger(__name__)


class SessionManager:
    """In-memory registry of connected agents and clients."""

    def __init__(self) -> None:
        # agent_id -> WebSocket
        self.agents: dict[str, WebSocket] = {}
        # agent_id -> WebSocket (one client per agent)
        self.clients: dict[str, WebSocket] = {}
        # agent_id -> metadata dict
        self.agent_info: dict[str, dict] = {}
        # agent_id -> latest raw binary frame (header + jpeg)
        self.latest_frames: dict[str, bytes] = {}
        # agent_id -> db session id for the current client session
        self._session_ids: dict[str, int] = {}

    # ------------------------------------------------------------------
    # Agent helpers
    # ------------------------------------------------------------------

    def register(self, agent_id: str, ws: WebSocket, info: dict) -> None:
        self.agents[agent_id] = ws
        self.agent_info[agent_id] = info
        logger.info("Agent registered: %s (%s)", agent_id, info.get("hostname"))

    def unregister_agent(self, agent_id: str) -> None:
        self.agents.pop(agent_id, None)
        self.agent_info.pop(agent_id, None)
        self.latest_frames.pop(agent_id, None)
        logger.info("Agent unregistered: %s", agent_id)

    # ------------------------------------------------------------------
    # Client helpers
    # ------------------------------------------------------------------

    async def link_client(
        self, agent_id: str, ws: WebSocket, client_addr: str
    ) -> int | None:
        """Associate a client WS with an agent and create a DB session."""
        if agent_id not in self.agents:
            await ws.send_json({"type": "error", "message": "Agent not connected"})
            return None

        # Kick previous client for this agent if any
        prev = self.clients.pop(agent_id, None)
        if prev is not None:
            try:
                await prev.send_json(
                    {"type": "error", "message": "Replaced by another client"}
                )
                await prev.close(code=1000)
            except Exception:
                pass

        self.clients[agent_id] = ws
        session_id = await create_session(settings.DB_PATH, agent_id, client_addr)
        self._session_ids[agent_id] = session_id
        logger.info(
            "Client linked to agent %s (session %s) from %s",
            agent_id,
            session_id,
            client_addr,
        )

        # Send the latest frame immediately so the client doesn't see a blank
        latest = self.latest_frames.get(agent_id)
        if latest:
            try:
                await ws.send_bytes(latest)
            except Exception:
                pass

        return session_id

    async def unlink_client(self, agent_id: str) -> None:
        """Remove a client from an agent and end the DB session."""
        self.clients.pop(agent_id, None)
        session_id = self._session_ids.pop(agent_id, None)
        if session_id is not None:
            await end_session(settings.DB_PATH, session_id)
        logger.info("Client unlinked from agent %s", agent_id)

    def get_agent_list(self) -> list[dict]:
        """Return a list of currently connected agent info dicts."""
        result = []
        for aid, info in self.agent_info.items():
            result.append({
                "agent_id": aid,
                "hostname": info.get("hostname", ""),
                "resolution": info.get("resolution", [0, 0]),
                "has_client": aid in self.clients,
            })
        return result


# Singleton shared across the app
manager = SessionManager()


# ---------------------------------------------------------------------------
# WS /ws/agent
# ---------------------------------------------------------------------------

async def ws_agent_endpoint(ws: WebSocket) -> None:
    """Handle an agent WebSocket connection lifecycle."""
    await ws.accept()
    agent_id: str | None = None

    try:
        # --- Step 1: auth ---
        raw = await ws.receive_text()
        msg = json.loads(raw)
        if msg.get("type") != "auth" or not hmac.compare_digest(msg.get("token", ""), settings.AGENT_SECRET):
            await ws.send_json({"type": "error", "message": "Authentication failed"})
            await ws.close(code=1008)
            return
        await ws.send_json({"type": "auth", "status": "ok"})

        # --- Step 2: register ---
        raw = await ws.receive_text()
        msg = json.loads(raw)
        if msg.get("type") != "register_agent":
            await ws.send_json({"type": "error", "message": "Expected register_agent"})
            await ws.close(code=1008)
            return

        agent_id = msg["agent_id"]
        hostname = msg.get("hostname", "")
        resolution = msg.get("resolution", [0, 0])

        manager.register(agent_id, ws, {
            "hostname": hostname,
            "resolution": resolution,
        })
        await register_agent(
            settings.DB_PATH,
            agent_id,
            hostname,
            int(resolution[0]),
            int(resolution[1]),
        )
        await ws.send_json({"type": "register_agent", "status": "ok"})

        # --- Step 3: main loop (frames + heartbeat) ---
        while True:
            data = await ws.receive()

            # Binary frame from agent
            if data.get("type") == "websocket.receive" and "bytes" in data and data["bytes"]:
                frame_bytes: bytes = data["bytes"]
                manager.latest_frames[agent_id] = frame_bytes

                # Forward to connected client
                client_ws = manager.clients.get(agent_id)
                if client_ws is not None:
                    try:
                        await client_ws.send_bytes(frame_bytes)
                    except Exception:
                        # Client disconnected; unlink
                        await manager.unlink_client(agent_id)

            # JSON control message (ping, config, etc.)
            elif data.get("type") == "websocket.receive" and "text" in data and data["text"]:
                msg = json.loads(data["text"])
                msg_type = msg.get("type")

                if msg_type == "ping":
                    await ws.send_json({"type": "pong", "ts": msg.get("ts", time.time())})
                    # Update last_seen
                    await update_agent_status(settings.DB_PATH, agent_id, "online")
                else:
                    logger.debug("Agent %s sent unhandled message type: %s", agent_id, msg_type)

    except WebSocketDisconnect:
        logger.info("Agent %s disconnected", agent_id or "unknown")
    except Exception:
        logger.exception("Error in agent WS handler (agent=%s)", agent_id or "unknown")
    finally:
        if agent_id:
            # End any active client session
            await manager.unlink_client(agent_id)
            manager.unregister_agent(agent_id)
            await update_agent_status(settings.DB_PATH, agent_id, "offline")


# ---------------------------------------------------------------------------
# WS /ws/client
# ---------------------------------------------------------------------------

async def ws_client_endpoint(ws: WebSocket) -> None:
    """Handle a client (browser) WebSocket connection lifecycle."""
    await ws.accept()
    linked_agent: str | None = None

    try:
        # --- Step 1: auth via JWT ---
        raw = await ws.receive_text()
        msg = json.loads(raw)
        if msg.get("type") != "auth":
            await ws.send_json({"type": "error", "message": "Expected auth message"})
            await ws.close(code=1008)
            return

        token = msg.get("token", "")
        try:
            payload = verify_token(token)
        except Exception:
            await ws.send_json({"type": "error", "message": "Invalid or expired token"})
            await ws.close(code=1008)
            return

        if payload.get("type") != "access":
            await ws.send_json({"type": "error", "message": "Token is not an access token"})
            await ws.close(code=1008)
            return

        username = payload.get("sub", "unknown")
        client_addr = f"{ws.client.host}:{ws.client.port}" if ws.client else "unknown"
        await ws.send_json({"type": "auth", "status": "ok"})
        logger.info("Client authenticated: user=%s addr=%s", username, client_addr)

        # Send the list of available agents right away
        await ws.send_json({"type": "agent_list", "agents": manager.get_agent_list()})

        # --- Step 2: main loop ---
        while True:
            data = await ws.receive()

            # JSON control / input messages
            if data.get("type") == "websocket.receive" and "text" in data and data["text"]:
                msg = json.loads(data["text"])
                msg_type = msg.get("type")

                if msg_type == "session_start":
                    target_agent = msg.get("agent_id", "")
                    session_id = await manager.link_client(
                        target_agent, ws, client_addr
                    )
                    if session_id is not None:
                        linked_agent = target_agent
                        info = manager.agent_info.get(target_agent, {})
                        await ws.send_json({
                            "type": "session_start",
                            "status": "ok",
                            "agent_id": target_agent,
                            "hostname": info.get("hostname", ""),
                            "resolution": info.get("resolution", [0, 0]),
                        })

                elif msg_type == "session_end":
                    if linked_agent:
                        await manager.unlink_client(linked_agent)
                        await ws.send_json({"type": "session_end", "status": "ok"})
                        linked_agent = None

                elif msg_type in ("mouse", "key", "config"):
                    # Validate message structure before forwarding
                    if msg_type == "mouse":
                        if not isinstance(msg.get("x"), (int, float)) or not isinstance(msg.get("y"), (int, float)):
                            await ws.send_json({"type": "error", "message": "Invalid mouse message: x and y required"})
                            continue
                        if msg.get("action") not in ("move", "click", "double_click", "scroll", "drag", "button_down", "button_up"):
                            await ws.send_json({"type": "error", "message": "Invalid mouse action"})
                            continue
                    elif msg_type == "key":
                        if not isinstance(msg.get("key"), str) or not msg["key"]:
                            await ws.send_json({"type": "error", "message": "Invalid key message: key required"})
                            continue
                    # Forward input / config to the agent
                    if linked_agent:
                        agent_ws = manager.agents.get(linked_agent)
                        if agent_ws is not None:
                            try:
                                await agent_ws.send_text(json.dumps(msg))
                            except Exception:
                                await ws.send_json({
                                    "type": "error",
                                    "message": "Agent connection lost",
                                })
                                await manager.unlink_client(linked_agent)
                                linked_agent = None
                    else:
                        await ws.send_json({
                            "type": "error",
                            "message": "No active session",
                        })

                elif msg_type == "ping":
                    await ws.send_json({"type": "pong", "ts": msg.get("ts", time.time())})

                else:
                    logger.debug("Client sent unhandled message type: %s", msg_type)

            # Binary messages from clients are not expected but handle gracefully
            elif data.get("type") == "websocket.receive" and "bytes" in data and data["bytes"]:
                logger.debug("Ignoring unexpected binary message from client")

    except WebSocketDisconnect:
        logger.info("Client disconnected (agent=%s)", linked_agent or "none")
    except Exception:
        logger.exception("Error in client WS handler")
    finally:
        if linked_agent:
            await manager.unlink_client(linked_agent)
