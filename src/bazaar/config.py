"""Configuration settings for AgentBazaar."""

from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """AgentBazaar settings from environment."""

    # MongoDB
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_database: str = "agentmesh"

    # Voyage AI (embeddings)
    voyage_api_key: str = ""

    # Fireworks AI (fast inference)
    fireworks_api_key: str = ""
    fireworks_model: str = "accounts/fireworks/models/llama-v3p3-70b-instruct"

    # NVIDIA (complex reasoning)
    nvidia_api_key: str = ""
    nemotron_model: str = "nvidia/llama-3.1-nemotron-ultra-253b-v1"

    # Galileo (quality evaluation)
    galileo_api_key: str = ""
    galileo_project: str = "agentbazaar"

    # Thesys (generative UI)
    thesys_api_key: str = ""

    # Bazaar settings
    quality_threshold: float = 0.7
    bid_window_minutes: int = 5
    max_execution_minutes: int = 10

    # x402 (simulated for demo)
    x402_enabled: bool = True
    x402_escrow_wallet: str = "0xBazaarEscrow"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
