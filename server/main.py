"""
RemoteGate Relay Server – FastAPI entry point.

Starts the HTTP + WebSocket server that brokers connections between
Windows agents and browser clients.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from auth import router as auth_router
from config import settings
from models import get_agents, init_db
from relay import ws_agent_endpoint, ws_client_endpoint

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lifespan (startup / shutdown)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup — validate secrets before anything else
    settings.validate_secrets()

    data_dir = Path(settings.DB_PATH).parent
    data_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Data directory: %s", data_dir.resolve())

    await init_db(settings.DB_PATH)
    logger.info("RemoteGate Relay Server starting on %s:%s", settings.SERVER_HOST, settings.SERVER_PORT)

    yield

    # Shutdown
    logger.info("RemoteGate Relay Server shutting down")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="RemoteGate Relay Server",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://remote.hbinserver.cloud",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth REST endpoints
app.include_router(auth_router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health():
    agents = await get_agents(settings.DB_PATH)
    online = [a for a in agents if a["status"] == "online"]
    return {
        "status": "ok",
        "agents_total": len(agents),
        "agents_online": len(online),
    }


# ---------------------------------------------------------------------------
# WebSocket routes
# ---------------------------------------------------------------------------

@app.websocket("/ws/agent")
async def ws_agent(ws):
    await ws_agent_endpoint(ws)


@app.websocket("/ws/client")
async def ws_client(ws):
    await ws_client_endpoint(ws)
