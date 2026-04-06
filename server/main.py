"""
RemoteGate Relay Server – FastAPI entry point.

Starts the HTTP + WebSocket server that brokers connections between
Windows agents and browser clients.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

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


# ---------------------------------------------------------------------------
# Agent installer download
# ---------------------------------------------------------------------------

_INSTALLER_TEMPLATE = r'''@echo off
chcp 65001 >nul
echo ============================================
echo   RemoteGate Agent Installer
echo ============================================
echo.

set INSTALL_DIR=%USERPROFILE%\RemoteGateAgent
set PYTHON_DIR=%INSTALL_DIR%\python
set PYTHON=%PYTHON_DIR%\python.exe
set PIP=%PYTHON_DIR%\Scripts\pip.exe
set PYTHON_URL=https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe

:: Create install directory
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
cd /d "%INSTALL_DIR%"

:: Check if embedded Python already exists
if exist "%PYTHON%" goto :skip_python

:: Check if system Python exists
python --version >nul 2>&1
if %errorlevel% equ 0 (
    echo [INFO] System Python found.
    set PYTHON=python
    goto :setup_venv
)

:: Download and install Python silently
echo [1/5] Downloading Python 3.11 ...
curl -sL "%PYTHON_URL%" -o python_installer.exe
if not exist python_installer.exe (
    echo [ERROR] Failed to download Python. Check internet connection.
    pause
    exit /b 1
)

echo [2/5] Installing Python (this may take a minute) ...
python_installer.exe /quiet InstallAllUsers=0 TargetDir="%PYTHON_DIR%" PrependPath=0 Include_launcher=0 Include_test=0 Include_doc=0 Include_tcltk=0 CompileAll=0
if %errorlevel% neq 0 (
    echo [ERROR] Python installation failed.
    del python_installer.exe >nul 2>&1
    pause
    exit /b 1
)
del python_installer.exe >nul 2>&1
echo [OK] Python installed to %PYTHON_DIR%
set PIP=%PYTHON_DIR%\Scripts\pip.exe
goto :install_deps

:setup_venv
:: Use system Python with venv
if not exist "venv" (
    echo [2/5] Creating virtual environment...
    %PYTHON% -m venv venv
)
call venv\Scripts\activate.bat
set PYTHON=python
set PIP=pip
goto :install_deps

:skip_python
echo [INFO] Python already installed at %PYTHON_DIR%
set PIP=%PYTHON_DIR%\Scripts\pip.exe

:install_deps
echo [3/5] Installing dependencies...
"%PIP%" install --quiet mss==9.0.2 Pillow==10.4.0 pynput==1.7.7 websockets==13.0 python-dotenv==1.0.1

:: Write .env
echo [4/5] Writing configuration...
(
echo RELAY_URL=$$RELAY_URL$$
echo AGENT_SECRET=$$AGENT_SECRET$$
echo AGENT_ID=%COMPUTERNAME%
echo DEFAULT_FPS=24
echo DEFAULT_QUALITY=50
echo DEFAULT_SCALE=0.75
) > .env

:: Download agent source files
echo [5/5] Downloading agent files...
set BASE_URL=$$BASE_URL$$
curl -sL "%BASE_URL%/config.py" -o config.py
curl -sL "%BASE_URL%/capture.py" -o capture.py
curl -sL "%BASE_URL%/encoder.py" -o encoder.py
curl -sL "%BASE_URL%/input_handler.py" -o input_handler.py
curl -sL "%BASE_URL%/connection.py" -o connection.py
curl -sL "%BASE_URL%/main.py" -o main.py

:: Create start script
(
echo @echo off
echo cd /d "%INSTALL_DIR%"
echo if exist "%PYTHON_DIR%\python.exe" (
echo     "%PYTHON_DIR%\python.exe" main.py
echo ) else (
echo     call venv\Scripts\activate.bat
echo     python main.py
echo )
) > start_agent.bat

:: Create desktop shortcut
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut([System.IO.Path]::Combine([Environment]::GetFolderPath('Desktop'), 'RemoteGate Agent.lnk')); $s.TargetPath = '%INSTALL_DIR%\start_agent.bat'; $s.WorkingDirectory = '%INSTALL_DIR%'; $s.IconLocation = 'shell32.dll,21'; $s.Save()"

echo.
echo ============================================
echo   Installation complete!
echo ============================================
echo.
echo   Location: %INSTALL_DIR%
echo   Shortcut: Desktop\RemoteGate Agent
echo.
echo Starting agent...
echo.

if exist "%PYTHON_DIR%\python.exe" (
    "%PYTHON_DIR%\python.exe" main.py
) else (
    python main.py
)
'''


@app.get("/api/installer")
async def download_installer(request: Request):
    """Generate a Windows batch installer script with embedded config."""
    host = request.headers.get("host", "remote.hbinserver.cloud")
    scheme = request.headers.get("x-forwarded-proto", "https")
    relay_url = f"wss://{host}" if scheme == "https" else f"ws://{host}"
    base_url = f"{scheme}://{host}/api/agent-source"

    script = _INSTALLER_TEMPLATE
    script = script.replace("$$RELAY_URL$$", relay_url)
    script = script.replace("$$AGENT_SECRET$$", settings.AGENT_SECRET)
    script = script.replace("$$BASE_URL$$", base_url)

    return PlainTextResponse(
        content=script,
        media_type="application/octet-stream",
        headers={"Content-Disposition": "attachment; filename=install_remotegate.bat"},
    )


# ---------------------------------------------------------------------------
# Agent source file serving
# ---------------------------------------------------------------------------

AGENT_DIR = Path(__file__).parent.parent / "agent"
AGENT_DOCKER_DIR = Path("/app/agent_src")

_ALLOWED_AGENT_FILES = {"config.py", "capture.py", "encoder.py", "input_handler.py", "connection.py", "main.py"}


def _get_agent_dir() -> Path:
    if AGENT_DOCKER_DIR.is_dir():
        return AGENT_DOCKER_DIR
    return AGENT_DIR


@app.get("/api/agent-source/{filename}")
async def serve_agent_source(filename: str):
    """Serve individual agent Python source files."""
    if filename not in _ALLOWED_AGENT_FILES:
        raise HTTPException(status_code=404, detail="File not found")
    file_path = _get_agent_dir() / filename
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, media_type="text/plain")


# ---------------------------------------------------------------------------
# Static files (built React frontend)
# ---------------------------------------------------------------------------

STATIC_DIR = Path(__file__).parent / "static"

if STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str):
        """Serve the React SPA for all non-API/WS routes."""
        file_path = STATIC_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(STATIC_DIR / "index.html")
