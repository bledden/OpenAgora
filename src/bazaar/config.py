"""Configuration settings for AgentBazaar.

## Realistic Task Pricing Guide

LLM API costs (as of 2024-2025):
- Fireworks Llama 70B: ~$0.90/1M input tokens, ~$0.90/1M output tokens
- OpenAI GPT-4o: ~$5/1M input, ~$15/1M output
- Anthropic Claude: ~$3/1M input, ~$15/1M output

Typical task token usage:
- Simple summarization: ~500 input + ~200 output = 700 tokens
- Sentiment analysis: ~300 input + ~50 output = 350 tokens
- Data extraction: ~1000 input + ~500 output = 1500 tokens
- Complex analysis: ~2000 input + ~1000 output = 3000 tokens

Cost per task (Fireworks Llama 70B):
- Simple task (700 tokens): ~$0.0006 (< 1 cent)
- Medium task (1500 tokens): ~$0.0014
- Complex task (3000 tokens): ~$0.0027

Recommended pricing (with margin for agent owner):
- Minimum base rate: $0.01 (covers costs + small profit)
- Simple tasks: $0.01 - $0.05
- Medium tasks: $0.05 - $0.15
- Complex tasks: $0.15 - $0.50

Tasks over $10 require human approval (configurable threshold).
"""

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
    galileo_console_url: str = "https://app.galileo.ai"

    # Thesys (generative UI)
    thesys_api_key: str = ""

    # Bazaar settings
    quality_threshold: float = 0.7
    bid_window_minutes: int = 5
    max_execution_minutes: int = 10

    # Pricing defaults (realistic for LLM compute costs)
    default_base_rate_usd: float = 0.01  # $0.01 minimum per task
    default_rate_per_1k_tokens: float = 0.001  # $0.001 per 1000 tokens
    human_approval_threshold_usd: float = 10.0  # Require human approval above this

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
