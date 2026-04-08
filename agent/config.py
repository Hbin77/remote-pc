"""
RemoteGate Agent configuration.
Loads settings from .env file and environment variables.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


@dataclass
class AgentConfig:
    relay_url: str = "ws://localhost:8900"
    agent_secret: str = ""
    agent_id: str = "default-agent"
    default_fps: int = 24
    default_quality: int = 50
    default_scale: float = 0.75


def load_config() -> AgentConfig:
    """Load configuration from .env file and environment variables."""
    # Look for .env in the agent directory and parent directory
    agent_dir = Path(__file__).parent
    for env_path in [agent_dir / ".env", agent_dir.parent / ".env"]:
        if env_path.exists():
            load_dotenv(env_path)
            break
    else:
        load_dotenv()  # Try default locations

    config = AgentConfig(
        relay_url=os.getenv("RELAY_URL", "ws://localhost:8900"),
        agent_secret=os.getenv("AGENT_SECRET", ""),
        agent_id=os.getenv("AGENT_ID", "default-agent"),
        default_fps=int(os.getenv("DEFAULT_FPS", "24")),
        default_quality=int(os.getenv("DEFAULT_QUALITY", "50")),
        default_scale=float(os.getenv("DEFAULT_SCALE", "0.75")),
    )

    if not config.agent_secret:
        raise ValueError("AGENT_SECRET must be set in environment or .env file")

    return config
