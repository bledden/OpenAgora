"""Configuration for AgentBazaar MCP server."""

import os
from dataclasses import dataclass
from typing import Literal


@dataclass
class BazaarMCPConfig:
    """Configuration for the MCP server."""

    mode: Literal["http", "direct"]
    api_url: str
    api_key: str | None
    mongodb_uri: str
    database: str

    @classmethod
    def from_env(cls) -> "BazaarMCPConfig":
        """Load configuration from environment variables."""
        mode = os.getenv("BAZAAR_MODE", "http")
        if mode not in ("http", "direct"):
            mode = "http"

        return cls(
            mode=mode,  # type: ignore
            api_url=os.getenv(
                "BAZAAR_API_URL", "https://agent-bazaar-i4rnccez5-bledden.vercel.app"
            ),
            api_key=os.getenv("BAZAAR_API_KEY"),
            mongodb_uri=os.getenv("MONGODB_URI", "mongodb://localhost:27017"),
            database=os.getenv("BAZAAR_DATABASE", "agentbazaar"),
        )


def get_config() -> BazaarMCPConfig:
    """Get the current configuration."""
    return BazaarMCPConfig.from_env()
