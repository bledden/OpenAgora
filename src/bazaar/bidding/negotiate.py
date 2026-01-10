"""Agentic negotiation flow with counter-bids and human approval.

This module enables:
1. Counter-offers between poster and agent
2. Automatic negotiation by AI agents
3. Human-in-the-loop approval for high-value transactions
4. Escalation when negotiation reaches impasse
"""

import uuid
from datetime import datetime
from typing import Optional
import structlog

from ..models import (
    BazaarBid,
    BidStatus,
    JobStatus,
    CounterOffer,
)
from ..db import (
    get_bid,
    update_bid,
    get_job,
    update_job,
    get_agent,
)
from ..llm import call_llm
from ..config import get_settings

logger = structlog.get_logger()

# Thresholds for human approval
HUMAN_APPROVAL_THRESHOLD_USD = 10.0  # Jobs over $10 need approval
MAX_COUNTER_OFFERS = 5  # Max negotiation rounds before escalation


async def make_counter_offer(
    bid_id: str,
    new_price: float,
    message: str,
    by: str,  # "poster" or "agent"
) -> BazaarBid:
    """Make a counter-offer on an existing bid.

    Args:
        bid_id: The bid to counter
        new_price: Proposed new price
        message: Explanation for the counter
        by: Who is making the counter ("poster" or "agent")

    Returns:
        Updated bid with counter-offer
    """
    bid = await get_bid(bid_id)
    if not bid:
        raise ValueError(f"Bid {bid_id} not found")

    # Check if negotiation is still open
    if bid["status"] not in [
        BidStatus.PENDING.value,
        BidStatus.COUNTER_OFFERED.value,
        BidStatus.COUNTER_ACCEPTED.value,
    ]:
        raise ValueError(f"Bid {bid_id} is not open for negotiation")

    # Check counter limit
    counter_offers = bid.get("counter_offers", [])
    if len(counter_offers) >= MAX_COUNTER_OFFERS:
        raise ValueError("Maximum negotiation rounds reached")

    # Create counter-offer
    counter = CounterOffer(
        price_usd=new_price,
        message=message,
        by=by,
        created_at=datetime.utcnow(),
    )

    counter_offers.append(counter.model_dump())

    # Update bid status
    new_status = BidStatus.COUNTER_OFFERED.value

    # Check if this needs human approval
    requires_approval = new_price >= HUMAN_APPROVAL_THRESHOLD_USD
    approval_reason = None
    if requires_approval:
        approval_reason = f"Transaction exceeds ${HUMAN_APPROVAL_THRESHOLD_USD} threshold"
        new_status = BidStatus.AWAITING_APPROVAL.value

    await update_bid(bid_id, {
        "counter_offers": counter_offers,
        "status": new_status,
        "requires_approval": requires_approval,
        "approval_reason": approval_reason,
    })

    # Update job status
    job = await get_job(bid["job_id"])
    if job:
        job_status = JobStatus.AWAITING_APPROVAL.value if requires_approval else JobStatus.NEGOTIATING.value
        await update_job(bid["job_id"], {"status": job_status})

    logger.info(
        "counter_offer_made",
        bid_id=bid_id,
        by=by,
        new_price=new_price,
        requires_approval=requires_approval,
    )

    # Return updated bid
    return await get_bid(bid_id)


async def accept_counter_offer(bid_id: str, by: str) -> BazaarBid:
    """Accept the latest counter-offer.

    Args:
        bid_id: The bid with counter-offer to accept
        by: Who is accepting ("poster" or "agent")

    Returns:
        Updated bid
    """
    bid = await get_bid(bid_id)
    if not bid:
        raise ValueError(f"Bid {bid_id} not found")

    counter_offers = bid.get("counter_offers", [])
    if not counter_offers:
        raise ValueError("No counter-offer to accept")

    # Get the final negotiated price
    final_price = counter_offers[-1]["price_usd"]

    # Check if approval is needed
    if bid.get("requires_approval") and not bid.get("approved_by"):
        await update_bid(bid_id, {
            "status": BidStatus.AWAITING_APPROVAL.value,
            "final_price_usd": final_price,
        })
        logger.info(
            "counter_offer_accepted_pending_approval",
            bid_id=bid_id,
            final_price=final_price,
        )
        return await get_bid(bid_id)

    # Accept without approval needed
    await update_bid(bid_id, {
        "status": BidStatus.COUNTER_ACCEPTED.value,
        "final_price_usd": final_price,
        "accepted_at": datetime.utcnow(),
    })

    logger.info(
        "counter_offer_accepted",
        bid_id=bid_id,
        by=by,
        final_price=final_price,
    )

    return await get_bid(bid_id)


async def approve_bid(
    bid_id: str,
    approver_id: str,
) -> BazaarBid:
    """Human approval for a bid that exceeds thresholds.

    Args:
        bid_id: The bid awaiting approval
        approver_id: ID of the human approver

    Returns:
        Approved bid
    """
    bid = await get_bid(bid_id)
    if not bid:
        raise ValueError(f"Bid {bid_id} not found")

    if bid["status"] != BidStatus.AWAITING_APPROVAL.value:
        raise ValueError(f"Bid {bid_id} is not awaiting approval")

    final_price = bid.get("final_price_usd") or bid["price_usd"]

    await update_bid(bid_id, {
        "status": BidStatus.ACCEPTED.value,
        "approved_by": approver_id,
        "approved_at": datetime.utcnow(),
        "accepted_at": datetime.utcnow(),
        "final_price_usd": final_price,
    })

    # Update job status
    await update_job(bid["job_id"], {
        "status": JobStatus.ASSIGNED.value,
        "winning_bid_id": bid_id,
        "assigned_agent_id": bid["agent_id"],
        "assigned_at": datetime.utcnow(),
    })

    logger.info(
        "bid_approved",
        bid_id=bid_id,
        approver=approver_id,
        final_price=final_price,
    )

    return await get_bid(bid_id)


async def reject_bid(
    bid_id: str,
    rejector_id: str,
    reason: str = "",
) -> BazaarBid:
    """Reject a bid.

    Args:
        bid_id: The bid to reject
        rejector_id: ID of who is rejecting
        reason: Optional rejection reason

    Returns:
        Rejected bid
    """
    bid = await get_bid(bid_id)
    if not bid:
        raise ValueError(f"Bid {bid_id} not found")

    await update_bid(bid_id, {
        "status": BidStatus.REJECTED.value,
    })

    logger.info(
        "bid_rejected",
        bid_id=bid_id,
        rejector=rejector_id,
        reason=reason,
    )

    return await get_bid(bid_id)


async def auto_negotiate(
    bid_id: str,
    max_budget: float,
    negotiator_role: str = "poster",
) -> Optional[BazaarBid]:
    """Use LLM to automatically negotiate on behalf of poster/agent.

    Args:
        bid_id: The bid to negotiate
        max_budget: Maximum the negotiator is willing to pay/accept
        negotiator_role: "poster" or "agent"

    Returns:
        Updated bid after negotiation attempt
    """
    bid = await get_bid(bid_id)
    if not bid:
        raise ValueError(f"Bid {bid_id} not found")

    job = await get_job(bid["job_id"])
    if not job:
        raise ValueError(f"Job {bid['job_id']} not found")

    agent = await get_agent(bid["agent_id"])
    agent_name = agent.get("name", bid["agent_id"]) if agent else bid["agent_id"]

    # Build negotiation context
    counter_offers = bid.get("counter_offers", [])
    history = "\n".join([
        f"- {c['by'].title()}: ${c['price_usd']:.2f} - {c['message']}"
        for c in counter_offers
    ])

    current_price = counter_offers[-1]["price_usd"] if counter_offers else bid["price_usd"]

    prompt = f"""You are negotiating on behalf of the {negotiator_role} in an AI agent marketplace.

Job: {job['title']}
Description: {job['description']}
Original budget: ${job['budget_usd']:.2f}
Agent: {agent_name}
Agent's original bid: ${bid['price_usd']:.2f}
Current price: ${current_price:.2f}
Your max {"budget" if negotiator_role == "poster" else "minimum"}: ${max_budget:.2f}

Negotiation history:
{history or "No previous negotiations"}

Decide your next action:
1. If the current price is acceptable, respond with: ACCEPT
2. If you want to counter, respond with: COUNTER $X.XX | Your message
3. If the negotiation is impossible, respond with: REJECT | Your reason

Respond with only one of these formats, nothing else."""

    response = await call_llm(prompt, max_tokens=100)
    response = response.strip()

    logger.info(
        "auto_negotiate_response",
        bid_id=bid_id,
        negotiator=negotiator_role,
        response=response,
    )

    if response.startswith("ACCEPT"):
        return await accept_counter_offer(bid_id, negotiator_role)

    elif response.startswith("COUNTER"):
        try:
            # Parse counter: "COUNTER $X.XX | message"
            parts = response.replace("COUNTER ", "").split(" | ", 1)
            new_price = float(parts[0].replace("$", ""))
            message = parts[1] if len(parts) > 1 else "Counter-offer"
            return await make_counter_offer(bid_id, new_price, message, negotiator_role)
        except (ValueError, IndexError) as e:
            logger.warning("auto_negotiate_parse_error", error=str(e))
            return None

    elif response.startswith("REJECT"):
        reason = response.replace("REJECT", "").replace("|", "").strip()
        return await reject_bid(bid_id, f"auto_{negotiator_role}", reason)

    return None


async def get_pending_approvals() -> list[dict]:
    """Get all bids awaiting human approval.

    Returns:
        List of bids needing approval
    """
    from ..db import get_db

    db = await get_db()
    cursor = db.bazaar_bids.find({
        "status": BidStatus.AWAITING_APPROVAL.value,
    })

    bids = []
    async for bid in cursor:
        # Enrich with job and agent info
        job = await get_job(bid["job_id"])
        agent = await get_agent(bid["agent_id"])

        bids.append({
            **bid,
            "job": job,
            "agent": agent,
        })

    return bids
