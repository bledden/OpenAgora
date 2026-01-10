"""Agent registration flow."""

import uuid
from datetime import datetime
from typing import Optional
import structlog

from ..models import BazaarAgent, AgentStatus, Provider, AgentCapabilities
from ..db import create_agent, get_agent, update_agent
from ..llm import call_fireworks, get_embedding
from .benchmark import run_benchmark

logger = structlog.get_logger()


async def register_agent(
    name: str,
    description: str,
    owner_id: str,
    provider: str = "fireworks",
    model: Optional[str] = None,
    wallet_address: str = "",
    base_rate_usd: float = 0.01,
    rate_per_1k_tokens: float = 0.001,
    skip_benchmark: bool = False,
) -> BazaarAgent:
    """Register a new agent and run benchmarks.

    Args:
        name: Display name for the agent
        description: What this agent specializes in
        owner_id: Human owner's ID or wallet
        provider: LLM provider (fireworks, nvidia, openai)
        model: Model identifier (defaults based on provider)
        wallet_address: x402 payment address
        base_rate_usd: Minimum price per task
        rate_per_1k_tokens: Additional token-based pricing
        skip_benchmark: Skip benchmark for testing (not recommended)

    Returns:
        Registered BazaarAgent with verified capabilities
    """
    agent_id = f"agent_{uuid.uuid4().hex[:8]}"

    # Default models by provider
    default_models = {
        "fireworks": "accounts/fireworks/models/llama-v3p3-70b-instruct",
        "nvidia": "nvidia/llama-3.1-nemotron-ultra-253b-v1",
        "openai": "gpt-4-turbo-preview",
    }
    model = model or default_models.get(provider, default_models["fireworks"])

    logger.info(
        "agent_registration_started",
        agent_id=agent_id,
        name=name,
        provider=provider,
    )

    # Validate model access
    validation_ok = await _validate_model_access(provider, model)
    if not validation_ok:
        raise ValueError(f"Cannot access model {model} with provider {provider}")

    # Generate capability embedding from description
    capability_text = f"{name}: {description}"
    embedding = await get_embedding(capability_text)

    # Create agent record
    agent = BazaarAgent(
        agent_id=agent_id,
        name=name,
        description=description,
        owner_id=owner_id,
        provider=Provider(provider),
        model=model,
        capability_embedding=embedding,
        wallet_address=wallet_address or f"0x{uuid.uuid4().hex[:40]}",
        base_rate_usd=base_rate_usd,
        rate_per_1k_tokens=rate_per_1k_tokens,
        status=AgentStatus.AVAILABLE,
        created_at=datetime.utcnow(),
        last_active=datetime.utcnow(),
    )

    # Store agent (capabilities will be updated by benchmark)
    await create_agent(agent.model_dump())

    # Run benchmark suite
    if not skip_benchmark:
        benchmark = await run_benchmark(agent_id, model)
        logger.info(
            "agent_benchmark_completed",
            agent_id=agent_id,
            overall_score=benchmark.overall_score,
        )

        # Refresh agent with updated capabilities
        agent_data = await get_agent(agent_id)
        if agent_data:
            agent = BazaarAgent(**agent_data)
    else:
        logger.warning("agent_benchmark_skipped", agent_id=agent_id)

    logger.info(
        "agent_registration_completed",
        agent_id=agent_id,
        name=name,
        status=agent.status,
    )

    return agent


async def _validate_model_access(provider: str, model: str) -> bool:
    """Validate that we can call this model."""
    try:
        if provider == "fireworks":
            response = await call_fireworks(
                prompt="Say 'ok' if you can hear me.",
                temperature=0.0,
                max_tokens=10,
            )
            return "ok" in response.content.lower()
        else:
            # For other providers, assume valid for now
            return True
    except Exception as e:
        logger.error("model_validation_failed", provider=provider, model=model, error=str(e))
        return False


async def update_agent_status(agent_id: str, status: AgentStatus) -> bool:
    """Update agent availability status."""
    return await update_agent(agent_id, {
        "status": status.value,
        "last_active": datetime.utcnow(),
    })


async def get_agent_profile(agent_id: str) -> Optional[dict]:
    """Get full agent profile."""
    return await get_agent(agent_id)
