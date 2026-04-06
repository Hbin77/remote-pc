"""
RemoteGate Windows Agent entry point.
Starts the agent connection loop that streams screen frames and receives
remote input commands from the relay server.
"""

import asyncio
import logging

from config import load_config
from connection import AgentConnection

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


def main():
    config = load_config()
    agent = AgentConnection(config)
    try:
        asyncio.run(agent.run())
    except KeyboardInterrupt:
        logging.info("Agent shutting down...")
    finally:
        agent.close()


if __name__ == "__main__":
    main()
