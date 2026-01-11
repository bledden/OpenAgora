"""Bid submission for agents."""

import uuid
from datetime import datetime
from typing import Optional
import structlog

from ..models import BazaarBid, BidStatus, JobStatus
from ..db import create_bid, get_bid, update_bid, get_job, get_agent

logger = structlog.get_logger()


async def submit_bid(
    job_id: str,
    agent_id: str,
    price_usd: float,
    estimated_time_seconds: int,
    confidence: float,
    approach: str,
) -> BazaarBid:
    """Submit a bid on a job.

    Args:
        job_id: Job to bid on
        agent_id: Agent submitting bid
        price_usd: Proposed price in USD
        estimated_time_seconds: Estimated completion time
        confidence: Agent's confidence level (0-1)
        approach: Brief description of approach

    Returns:
        Created BazaarBid
    """
    # Validate job exists and is open
    job = await get_job(job_id)
    if not job:
        raise ValueError(f"Job {job_id} not found")

    if job["status"] not in [JobStatus.OPEN.value, JobStatus.POSTED.value, JobStatus.BIDDING.value]:
        raise ValueError(f"Job {job_id} is not accepting bids (status: {job['status']})")

    # Check bid deadline
    if job.get("bid_deadline"):
        deadline = datetime.fromisoformat(job["bid_deadline"].replace("Z", "+00:00"))
        if datetime.utcnow() > deadline.replace(tzinfo=None):
            raise ValueError(f"Bid deadline has passed for job {job_id}")

    # Validate agent exists and is available
    agent = await get_agent(agent_id)
    if not agent:
        raise ValueError(f"Agent {agent_id} not found")

    if agent["status"] != "available":
        raise ValueError(f"Agent {agent_id} is not available (status: {agent['status']})")

    # Validate price is within budget
    if price_usd > job["budget_usd"]:
        raise ValueError(f"Bid price ${price_usd} exceeds job budget ${job['budget_usd']}")

    # Check agent has required capabilities
    required_caps = job.get("required_capabilities", [])
    min_score = job.get("min_capability_score", 0.7)
    agent_caps = agent.get("capabilities", {})

    for cap in required_caps:
        if agent_caps.get(cap, 0) < min_score:
            raise ValueError(
                f"Agent {agent_id} does not meet minimum {cap} score "
                f"(has {agent_caps.get(cap, 0)}, need {min_score})"
            )

    bid_id = f"bid_{uuid.uuid4().hex[:8]}"

    bid = BazaarBid(
        bid_id=bid_id,
        job_id=job_id,
        agent_id=agent_id,
        price_usd=price_usd,
        estimated_time_seconds=estimated_time_seconds,
        confidence=confidence,
        approach=approach,
        status=BidStatus.PENDING,
        created_at=datetime.utcnow(),
    )

    await create_bid(bid.model_dump())

    logger.info(
        "bid_submitted",
        bid_id=bid_id,
        job_id=job_id,
        agent_id=agent_id,
        price=price_usd,
    )

    return bid


async def withdraw_bid(bid_id: str, agent_id: str) -> bool:
    """Withdraw a pending bid.

    Args:
        bid_id: Bid to withdraw
        agent_id: Agent who submitted the bid (for verification)

    Returns:
        True if withdrawn successfully
    """
    bid = await get_bid(bid_id)
    if not bid:
        raise ValueError(f"Bid {bid_id} not found")

    if bid["agent_id"] != agent_id:
        raise ValueError(f"Bid {bid_id} does not belong to agent {agent_id}")

    if bid["status"] != BidStatus.PENDING.value:
        raise ValueError(f"Can only withdraw pending bids (status: {bid['status']})")

    await update_bid(bid_id, {"status": BidStatus.WITHDRAWN.value})

    logger.info("bid_withdrawn", bid_id=bid_id, agent_id=agent_id)

    return True


async def get_bid_details(bid_id: str) -> Optional[BazaarBid]:
    """Get bid by ID."""
    data = await get_bid(bid_id)
    if data:
        return BazaarBid(**data)
    return None


async def select_winning_bid(job_id: str, bid_id: str) -> dict:
    """Select a winning bid for a job.

    Args:
        job_id: Job to assign
        bid_id: Winning bid ID

    Returns:
        Updated job dict
    """
    from ..db import update_job

    job = await get_job(job_id)
    if not job:
        raise ValueError(f"Job {job_id} not found")

    bid = await get_bid(bid_id)
    if not bid:
        raise ValueError(f"Bid {bid_id} not found")

    if bid["job_id"] != job_id:
        raise ValueError(f"Bid {bid_id} is not for job {job_id}")

    # Update bid status
    final_price = bid.get("final_price_usd") or bid["price_usd"]
    await update_bid(bid_id, {
        "status": BidStatus.ACCEPTED.value,
        "final_price_usd": final_price,
        "accepted_at": datetime.utcnow(),
    })

    # Update job with winning bid
    await update_job(job_id, {
        "status": JobStatus.ASSIGNED.value,
        "winning_bid_id": bid_id,
        "assigned_agent_id": bid["agent_id"],
        "final_price_usd": final_price,
        "assigned_at": datetime.utcnow(),
    })

    logger.info(
        "winning_bid_selected",
        job_id=job_id,
        bid_id=bid_id,
        agent_id=bid["agent_id"],
        final_price=final_price,
    )

    return await get_job(job_id)
