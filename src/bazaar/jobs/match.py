"""Agent matching for jobs using Voyage embeddings + MongoDB vector search."""

from typing import Optional
import structlog

from ..models import BazaarJob, BazaarAgent
from ..db import find_available_agents, vector_search_agents, get_job

logger = structlog.get_logger()


async def find_matching_agents(
    job_id: str,
    limit: int = 10,
    use_vector_search: bool = True,
) -> list[dict]:
    """Find agents matching a job's requirements.

    Args:
        job_id: Job to match agents for
        limit: Maximum agents to return
        use_vector_search: Use Voyage embedding similarity (recommended)

    Returns:
        List of matching agent profiles with match scores
    """
    job_data = await get_job(job_id)
    if not job_data:
        logger.error("job_not_found", job_id=job_id)
        return []

    job = BazaarJob(**job_data)

    logger.info(
        "matching_agents",
        job_id=job_id,
        required_capabilities=job.required_capabilities,
        min_score=job.min_capability_score,
    )

    # Try vector search first, fall back to capability filter
    agents = []
    if use_vector_search and job.job_embedding:
        try:
            agents = await vector_search_agents(
                job_embedding=job.job_embedding,
                required_capabilities=job.required_capabilities,
                min_score=job.min_capability_score,
                limit=limit,
            )
        except Exception as e:
            logger.warning("vector_search_failed", error=str(e))

    # Fallback to capability-based filtering if vector search failed or returned nothing
    if not agents:
        agents = await find_available_agents(
            required_capabilities=job.required_capabilities,
            min_score=job.min_capability_score,
            limit=limit,
        )

    # Calculate match scores
    matched_agents = []
    for agent_data in agents:
        match_score = _calculate_match_score(job, agent_data)
        matched_agents.append({
            **agent_data,
            "match_score": match_score,
        })

    # Sort by match score
    matched_agents.sort(key=lambda a: a["match_score"], reverse=True)

    logger.info(
        "agents_matched",
        job_id=job_id,
        matched_count=len(matched_agents),
    )

    return matched_agents


def _calculate_match_score(job: BazaarJob, agent_data: dict) -> float:
    """Calculate overall match score between job and agent.

    Scoring factors:
    - Capability match (40%): How well agent capabilities match requirements
    - Reputation (30%): Agent rating and completion rate
    - Price fit (20%): Agent's rate vs job budget
    - Search similarity (10%): Vector search score if available
    """
    capabilities = agent_data.get("capabilities", {})
    total_score = 0.0

    # 1. Capability match (40%)
    if job.required_capabilities:
        cap_scores = []
        for cap in job.required_capabilities:
            cap_score = capabilities.get(cap, 0.0)
            cap_scores.append(cap_score)
        avg_cap = sum(cap_scores) / len(cap_scores) if cap_scores else 0.0
        total_score += avg_cap * 0.4
    else:
        total_score += 0.4  # Full credit if no requirements specified

    # 2. Reputation (30%)
    rating = agent_data.get("rating_avg", 0.0)
    jobs_completed = agent_data.get("jobs_completed", 0)
    jobs_failed = agent_data.get("jobs_failed", 0)

    if jobs_completed + jobs_failed > 0:
        success_rate = jobs_completed / (jobs_completed + jobs_failed)
    else:
        success_rate = 0.5  # Neutral for new agents

    rep_score = (rating / 5.0) * 0.6 + success_rate * 0.4
    total_score += rep_score * 0.3

    # 3. Price fit (20%)
    base_rate = agent_data.get("base_rate_usd", 0.01)
    if base_rate <= job.budget_usd:
        price_score = 1.0 - (base_rate / job.budget_usd) * 0.3  # Slight preference for cheaper
    else:
        price_score = 0.0  # Over budget
    total_score += price_score * 0.2

    # 4. Vector search similarity (10%)
    search_score = agent_data.get("search_score", 0.5)
    total_score += search_score * 0.1

    return round(total_score, 3)


async def match_agents_to_job(job: "BazaarJob", limit: int = 10) -> list[dict]:
    """Alias for find_matching_agents that accepts a job object directly.

    Used by the API to match agents when a job is created.
    """
    from ..db import create_job, get_job

    # If job already exists in DB, use its ID
    job_data = await get_job(job.job_id)
    if job_data:
        return await find_matching_agents(job.job_id, limit=limit)

    # For new jobs, do capability-based matching directly
    agents = await find_available_agents(
        required_capabilities=job.required_capabilities,
        min_score=job.min_capability_score,
        limit=limit,
    )

    matched_agents = []
    for agent_data in agents:
        match_score = _calculate_match_score(job, agent_data)
        matched_agents.append({
            **agent_data,
            "match_score": match_score,
        })

    matched_agents.sort(key=lambda a: a["match_score"], reverse=True)
    return matched_agents


async def notify_matching_agents(job_id: str, agents: list[dict]) -> int:
    """Notify matching agents about a new job opportunity.

    In a real system, this would send notifications via webhooks/queues.
    For the demo, we just log the notifications.
    """
    notified = 0
    for agent in agents:
        logger.info(
            "agent_notified",
            job_id=job_id,
            agent_id=agent["agent_id"],
            match_score=agent.get("match_score", 0),
        )
        notified += 1

    return notified
