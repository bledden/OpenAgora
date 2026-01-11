"""Hybrid semantic matching for jobs using Voyage embeddings + LLM validation.

This implements a two-stage matching approach:
1. Fast pre-filter using Voyage voyage-3-large embeddings (semantic similarity)
2. LLM validation for top candidates (ensures real capability match)

This hybrid approach balances speed, cost, and accuracy.
"""

from typing import Optional, Any
import asyncio
import structlog

from ..models import BazaarJob, BazaarAgent
from ..db import find_available_agents, vector_search_agents, get_job, get_all_agents
from ..llm import get_embedding, get_embeddings_batch, cosine_similarity, call_fireworks_json

logger = structlog.get_logger()

# Semantic similarity threshold for pre-filtering (voyage-3-large)
SEMANTIC_THRESHOLD = 0.65

# Number of candidates to pass to LLM validation
LLM_VALIDATION_CANDIDATES = 5

# Minimum LLM confidence to consider a match valid
LLM_CONFIDENCE_THRESHOLD = 0.6


async def find_matching_agents(
    job_id: str,
    limit: int = 10,
    use_hybrid_matching: bool = True,
) -> list[dict]:
    """Find agents matching a job's requirements using hybrid semantic matching.

    Args:
        job_id: Job to match agents for
        limit: Maximum agents to return
        use_hybrid_matching: Use Voyage embeddings + LLM validation (recommended)

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
        hybrid=use_hybrid_matching,
    )

    if use_hybrid_matching:
        # Hybrid: embeddings pre-filter + LLM validation
        matched_agents = await _hybrid_match(job, limit)
    else:
        # Fallback to simple capability-based matching
        matched_agents = await _simple_match(job, limit)

    logger.info(
        "agents_matched",
        job_id=job_id,
        matched_count=len(matched_agents),
    )

    return matched_agents


async def _hybrid_match(job: BazaarJob, limit: int) -> list[dict]:
    """Two-stage hybrid matching: embeddings pre-filter + LLM validation.

    Stage 1: Use voyage-3-large embeddings to find semantically similar agents
    Stage 2: Use LLM to validate capability match for top candidates
    """
    # Build job description for embedding
    job_text = _build_job_text(job)

    # Get all available agents
    all_agents = await get_all_agents(limit=100)
    available_agents = [a for a in all_agents if a.get("status") == "available"]

    if not available_agents:
        logger.warning("no_available_agents")
        return []

    # Stage 1: Semantic pre-filtering with Voyage embeddings
    logger.info("hybrid_stage1_embedding", agent_count=len(available_agents))

    try:
        # Get job embedding
        job_embedding = await get_embedding(job_text)

        # Build agent descriptions for embedding
        agent_texts = [_build_agent_text(agent) for agent in available_agents]

        # Get agent embeddings (batch for efficiency)
        agent_embeddings = await get_embeddings_batch(agent_texts)

        # Calculate similarity scores
        candidates = []
        for agent, agent_emb in zip(available_agents, agent_embeddings):
            similarity = cosine_similarity(job_embedding, agent_emb)
            if similarity >= SEMANTIC_THRESHOLD:
                candidates.append({
                    **agent,
                    "semantic_score": similarity,
                })

        # Sort by semantic similarity
        candidates.sort(key=lambda a: a["semantic_score"], reverse=True)

        logger.info(
            "hybrid_stage1_complete",
            candidates_found=len(candidates),
            threshold=SEMANTIC_THRESHOLD,
        )

    except Exception as e:
        logger.warning("embedding_failed", error=str(e))
        # Fallback to all available agents if embeddings fail
        candidates = [{**a, "semantic_score": 0.5} for a in available_agents]

    # Stage 2: LLM validation for top candidates
    top_candidates = candidates[:LLM_VALIDATION_CANDIDATES]

    if top_candidates:
        logger.info("hybrid_stage2_llm", candidates=len(top_candidates))
        validated = await _llm_validate_matches(job, top_candidates)
    else:
        validated = []

    # Combine semantic and LLM scores into final match score
    matched_agents = []
    for agent in validated:
        final_score = _calculate_hybrid_score(job, agent)
        matched_agents.append({
            **agent,
            "match_score": final_score,
        })

    # Sort by final match score
    matched_agents.sort(key=lambda a: a["match_score"], reverse=True)

    return matched_agents[:limit]


async def _llm_validate_matches(
    job: BazaarJob,
    candidates: list[dict],
) -> list[dict]:
    """Use LLM to validate capability matches for candidate agents.

    The LLM evaluates whether each agent can actually complete the job
    based on their description and stated capabilities.
    """
    validated = []

    for agent in candidates:
        try:
            validation = await _validate_single_agent(job, agent)

            if validation.get("can_complete", False):
                confidence = validation.get("confidence", 0.5)
                if confidence >= LLM_CONFIDENCE_THRESHOLD:
                    validated.append({
                        **agent,
                        "llm_validation": validation,
                        "llm_confidence": confidence,
                    })
                    logger.info(
                        "agent_validated",
                        agent_id=agent["agent_id"],
                        confidence=confidence,
                    )
                else:
                    logger.debug(
                        "agent_low_confidence",
                        agent_id=agent["agent_id"],
                        confidence=confidence,
                    )
            else:
                logger.debug(
                    "agent_cannot_complete",
                    agent_id=agent["agent_id"],
                    reason=validation.get("reasoning", "unknown"),
                )

        except Exception as e:
            logger.warning(
                "validation_error",
                agent_id=agent["agent_id"],
                error=str(e),
            )
            # Include with lower confidence on error
            validated.append({
                **agent,
                "llm_validation": {"error": str(e)},
                "llm_confidence": 0.5,
            })

    return validated


async def _validate_single_agent(job: BazaarJob, agent: dict) -> dict:
    """Have LLM evaluate if an agent can complete a specific job."""

    system_prompt = """You are an expert at matching AI agents to jobs.
Evaluate whether an agent can successfully complete a given job.
Consider the agent's stated capabilities and the job requirements.
Be realistic - don't assume capabilities the agent doesn't claim."""

    prompt = f"""## Job to Complete
Title: {job.title}
Description: {job.description}
Required Capabilities: {', '.join(job.required_capabilities)}
Budget: ${job.budget_usd}

## Agent Profile
Name: {agent.get('name', 'Unknown')}
Description: {agent.get('description', 'No description')}
Capabilities: {agent.get('capabilities', {})}
Base Rate: ${agent.get('base_rate_usd', 0.10)}
Jobs Completed: {agent.get('jobs_completed', 0)}
Rating: {agent.get('rating_avg', 'N/A')}

## Evaluation Task
Can this agent successfully complete this job?

Respond with JSON:
{{
    "can_complete": true/false,
    "confidence": 0.0-1.0,
    "capability_match": 0.0-1.0,
    "reasoning": "<brief explanation>"
}}"""

    result = await call_fireworks_json(prompt, system_prompt, temperature=0.2)
    return result


def _calculate_hybrid_score(job: BazaarJob, agent: dict) -> float:
    """Calculate final match score combining all factors.

    Scoring breakdown:
    - Semantic similarity (35%): Voyage embedding match
    - LLM capability validation (30%): Assessed ability to complete
    - Reputation (20%): Rating and success rate
    - Price fit (15%): Agent rate vs job budget
    """
    total_score = 0.0

    # 1. Semantic similarity (35%)
    semantic_score = agent.get("semantic_score", 0.5)
    total_score += semantic_score * 0.35

    # 2. LLM capability validation (30%)
    llm_confidence = agent.get("llm_confidence", 0.5)
    validation = agent.get("llm_validation", {})
    cap_match = validation.get("capability_match", llm_confidence)
    total_score += ((llm_confidence + cap_match) / 2) * 0.30

    # 3. Reputation (20%)
    rating = agent.get("rating_avg", 0.0) or 0.0
    jobs_completed = agent.get("jobs_completed", 0)
    jobs_failed = agent.get("jobs_failed", 0)

    if jobs_completed + jobs_failed > 0:
        success_rate = jobs_completed / (jobs_completed + jobs_failed)
    else:
        success_rate = 0.5  # Neutral for new agents

    rep_score = (rating / 5.0) * 0.6 + success_rate * 0.4 if rating else success_rate
    total_score += rep_score * 0.20

    # 4. Price fit (15%)
    base_rate = agent.get("base_rate_usd", 0.01)
    if base_rate <= job.budget_usd:
        # Prefer agents who are within budget but not too cheap
        price_ratio = base_rate / job.budget_usd
        price_score = 0.7 + (price_ratio * 0.3)  # Range: 0.7-1.0
    else:
        price_score = max(0, 1 - (base_rate - job.budget_usd) / job.budget_usd)
    total_score += price_score * 0.15

    return round(total_score, 3)


def _build_job_text(job: BazaarJob) -> str:
    """Build text representation of job for embedding."""
    parts = [
        f"Job: {job.title}",
        f"Description: {job.description}",
        f"Required capabilities: {', '.join(job.required_capabilities)}",
    ]
    return "\n".join(parts)


def _build_agent_text(agent: dict) -> str:
    """Build text representation of agent for embedding."""
    caps = agent.get("capabilities", {})
    cap_str = ", ".join([f"{k}: {v:.2f}" for k, v in caps.items()])

    parts = [
        f"Agent: {agent.get('name', 'Unknown')}",
        f"Description: {agent.get('description', 'No description')}",
        f"Capabilities: {cap_str}",
    ]
    return "\n".join(parts)


async def _simple_match(job: BazaarJob, limit: int) -> list[dict]:
    """Simple capability-based matching (fallback)."""
    agents = await find_available_agents(
        required_capabilities=job.required_capabilities,
        min_score=job.min_capability_score,
        limit=limit * 2,
    )

    matched_agents = []
    for agent_data in agents:
        match_score = _calculate_simple_score(job, agent_data)
        matched_agents.append({
            **agent_data,
            "match_score": match_score,
        })

    matched_agents.sort(key=lambda a: a["match_score"], reverse=True)
    return matched_agents[:limit]


def _calculate_simple_score(job: BazaarJob, agent_data: dict) -> float:
    """Calculate match score using only keyword-based capability matching."""
    capabilities = agent_data.get("capabilities", {})
    total_score = 0.0

    # Capability match (50%)
    if job.required_capabilities:
        cap_scores = []
        for cap in job.required_capabilities:
            cap_score = capabilities.get(cap, 0.0)
            cap_scores.append(cap_score)
        avg_cap = sum(cap_scores) / len(cap_scores) if cap_scores else 0.0
        total_score += avg_cap * 0.5
    else:
        total_score += 0.5

    # Reputation (30%)
    rating = agent_data.get("rating_avg", 0.0) or 0.0
    jobs_completed = agent_data.get("jobs_completed", 0)
    jobs_failed = agent_data.get("jobs_failed", 0)

    if jobs_completed + jobs_failed > 0:
        success_rate = jobs_completed / (jobs_completed + jobs_failed)
    else:
        success_rate = 0.5

    rep_score = (rating / 5.0) * 0.6 + success_rate * 0.4 if rating else success_rate
    total_score += rep_score * 0.3

    # Price fit (20%)
    base_rate = agent_data.get("base_rate_usd", 0.01)
    if base_rate <= job.budget_usd:
        price_score = 1.0 - (base_rate / job.budget_usd) * 0.3
    else:
        price_score = 0.0
    total_score += price_score * 0.2

    return round(total_score, 3)


async def match_agents_to_job(job: "BazaarJob", limit: int = 10) -> list[dict]:
    """Match agents to a job object directly.

    Used by the API to match agents when a job is created.
    """
    from ..db import get_job

    # If job already exists in DB, use the full hybrid matching
    job_data = await get_job(job.job_id)
    if job_data:
        return await find_matching_agents(job.job_id, limit=limit)

    # For new jobs not yet in DB, use hybrid matching directly
    return await _hybrid_match(job, limit)


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
            semantic_score=agent.get("semantic_score", 0),
        )
        notified += 1

    return notified
