"""Bid ranking algorithm."""

from typing import Optional
import structlog

from ..db import get_bids_for_job, get_agent, get_job

logger = structlog.get_logger()


async def rank_bids(job_id: str) -> list[dict]:
    """Rank all bids for a job.

    Ranking factors:
    - Price (30%): Lower is better (normalized to budget)
    - Confidence (25%): Agent's stated confidence
    - Agent rating (20%): Historical performance
    - Speed (15%): Faster estimated time
    - Capability match (10%): How well capabilities match requirements

    Returns:
        List of bids with ranking scores, sorted best first
    """
    job = await get_job(job_id)
    if not job:
        logger.error("job_not_found", job_id=job_id)
        return []

    bids = await get_bids_for_job(job_id)
    if not bids:
        return []

    # Filter to pending bids only
    pending_bids = [b for b in bids if b.get("status") == "pending"]

    if not pending_bids:
        return []

    # Get agent details for each bid
    ranked_bids = []
    for bid in pending_bids:
        agent = await get_agent(bid["agent_id"])
        if not agent:
            continue

        score = _calculate_bid_score(bid, agent, job)
        ranked_bids.append({
            **bid,
            "agent_name": agent.get("name", "Unknown"),
            "agent_rating": agent.get("rating_avg", 0),
            "agent_jobs_completed": agent.get("jobs_completed", 0),
            "rank_score": score,
        })

    # Sort by rank score descending
    ranked_bids.sort(key=lambda b: b["rank_score"], reverse=True)

    # Add rank position
    for i, bid in enumerate(ranked_bids):
        bid["rank"] = i + 1

    logger.info(
        "bids_ranked",
        job_id=job_id,
        bid_count=len(ranked_bids),
        top_bid=ranked_bids[0]["bid_id"] if ranked_bids else None,
    )

    return ranked_bids


def _calculate_bid_score(bid: dict, agent: dict, job: dict) -> float:
    """Calculate ranking score for a bid."""
    score = 0.0
    budget = job.get("budget_usd", 1.0)

    # 1. Price score (30%) - lower is better
    price = bid.get("price_usd", budget)
    price_ratio = price / budget
    price_score = max(0, 1 - price_ratio)  # 0 at budget, 1 at free
    score += price_score * 0.30

    # 2. Confidence score (25%)
    confidence = bid.get("confidence", 0.5)
    score += confidence * 0.25

    # 3. Agent rating (20%)
    rating = agent.get("rating_avg", 0)
    rating_score = rating / 5.0
    score += rating_score * 0.20

    # 4. Speed score (15%) - faster is better
    estimated_time = bid.get("estimated_time_seconds", 600)
    deadline_seconds = job.get("deadline_minutes", 10) * 60
    time_ratio = estimated_time / deadline_seconds
    speed_score = max(0, 1 - time_ratio)
    score += speed_score * 0.15

    # 5. Capability match (10%)
    required_caps = job.get("required_capabilities", [])
    agent_caps = agent.get("capabilities", {})
    if required_caps:
        cap_scores = [agent_caps.get(cap, 0) for cap in required_caps]
        avg_cap = sum(cap_scores) / len(cap_scores)
    else:
        avg_cap = 0.8
    score += avg_cap * 0.10

    return round(score, 3)


async def get_top_bid(job_id: str) -> Optional[dict]:
    """Get the highest-ranked bid for a job."""
    ranked = await rank_bids(job_id)
    return ranked[0] if ranked else None
