"""Bid acceptance and job assignment."""

from datetime import datetime
import structlog

from ..models import BidStatus, JobStatus, AgentStatus
from ..db import update_bid, update_job, update_agent, get_bid, get_job, get_bids_for_job

logger = structlog.get_logger()


async def accept_bid(
    job_id: str,
    bid_id: str,
    poster_id: str,
) -> dict:
    """Accept a bid and assign the job to the agent.

    Args:
        job_id: Job being assigned
        bid_id: Winning bid
        poster_id: Poster accepting (for verification)

    Returns:
        Assignment details
    """
    # Verify job
    job = await get_job(job_id)
    if not job:
        raise ValueError(f"Job {job_id} not found")

    if job["poster_id"] != poster_id:
        raise ValueError(f"Only the job poster can accept bids")

    if job["status"] not in [JobStatus.OPEN.value, JobStatus.BIDDING.value]:
        raise ValueError(f"Job {job_id} is not accepting bids (status: {job['status']})")

    # Verify bid
    bid = await get_bid(bid_id)
    if not bid:
        raise ValueError(f"Bid {bid_id} not found")

    if bid["job_id"] != job_id:
        raise ValueError(f"Bid {bid_id} is not for job {job_id}")

    if bid["status"] != BidStatus.PENDING.value:
        raise ValueError(f"Bid {bid_id} is not pending (status: {bid['status']})")

    agent_id = bid["agent_id"]
    now = datetime.utcnow()

    # Update winning bid
    await update_bid(bid_id, {
        "status": BidStatus.ACCEPTED.value,
        "accepted_at": now,
    })

    # Reject other bids
    all_bids = await get_bids_for_job(job_id)
    for other_bid in all_bids:
        if other_bid["bid_id"] != bid_id and other_bid["status"] == BidStatus.PENDING.value:
            await update_bid(other_bid["bid_id"], {
                "status": BidStatus.REJECTED.value,
            })

    # Update job
    await update_job(job_id, {
        "status": JobStatus.ASSIGNED.value,
        "winning_bid_id": bid_id,
        "assigned_agent_id": agent_id,
        "assigned_at": now,
    })

    # Update agent status
    await update_agent(agent_id, {
        "status": AgentStatus.BUSY.value,
        "last_active": now,
    })

    logger.info(
        "bid_accepted",
        job_id=job_id,
        bid_id=bid_id,
        agent_id=agent_id,
        price=bid["price_usd"],
    )

    return {
        "job_id": job_id,
        "bid_id": bid_id,
        "agent_id": agent_id,
        "price_usd": bid["price_usd"],
        "estimated_time_seconds": bid["estimated_time_seconds"],
        "assigned_at": now.isoformat(),
    }


async def auto_accept_bid(
    job_id: str,
    max_price: float,
    min_rating: float = 4.0,
    min_confidence: float = 0.8,
) -> dict | None:
    """Automatically accept the best bid meeting criteria.

    Args:
        job_id: Job to auto-accept for
        max_price: Maximum acceptable price
        min_rating: Minimum agent rating required
        min_confidence: Minimum bid confidence required

    Returns:
        Assignment details if a bid was accepted, None otherwise
    """
    from .rank import rank_bids

    job = await get_job(job_id)
    if not job:
        return None

    ranked_bids = await rank_bids(job_id)

    for bid in ranked_bids:
        if (
            bid["price_usd"] <= max_price
            and bid.get("agent_rating", 0) >= min_rating
            and bid["confidence"] >= min_confidence
        ):
            return await accept_bid(
                job_id=job_id,
                bid_id=bid["bid_id"],
                poster_id=job["poster_id"],
            )

    logger.info(
        "no_bid_meets_criteria",
        job_id=job_id,
        max_price=max_price,
        min_rating=min_rating,
    )

    return None
