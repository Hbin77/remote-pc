"""
RemoteGate Relay Server configuration.

Reads all settings from environment variables / .env file
using pydantic-settings.
"""

import sys

from pydantic_settings import BaseSettings

_INSECURE_DEFAULTS = {
    "change-me-in-production",
    "change-me-jwt-secret",
    "change-me-agent-secret",
}


class Settings(BaseSettings):
    """Application settings populated from environment variables."""

    # Server
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8900
    SECRET_KEY: str = "change-me-in-production"

    # JWT
    JWT_SECRET: str = "change-me-jwt-secret"
    JWT_ACCESS_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_EXPIRE_DAYS: int = 7

    # Admin (single-user auth)
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD_HASH: str = ""  # bcrypt hash

    # Agent registration secret
    AGENT_SECRET: str = "change-me-agent-secret"

    # Streaming defaults
    DEFAULT_FPS: int = 24
    DEFAULT_QUALITY: int = 50
    DEFAULT_SCALE: float = 0.75

    # Database
    DB_PATH: str = "data/remotegate.db"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }

    def validate_secrets(self) -> None:
        """Refuse to start if secrets are still set to insecure defaults."""
        problems = []
        if self.SECRET_KEY in _INSECURE_DEFAULTS:
            problems.append("SECRET_KEY")
        if self.JWT_SECRET in _INSECURE_DEFAULTS:
            problems.append("JWT_SECRET")
        if self.AGENT_SECRET in _INSECURE_DEFAULTS:
            problems.append("AGENT_SECRET")
        if not self.ADMIN_PASSWORD_HASH:
            problems.append("ADMIN_PASSWORD_HASH (empty)")
        if problems:
            print(
                f"FATAL: Insecure default values detected for: {', '.join(problems)}. "
                "Set proper secrets in your .env file before starting the server.",
                file=sys.stderr,
            )
            sys.exit(1)


settings = Settings()
