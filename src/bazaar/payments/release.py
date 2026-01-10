"""Payment release after successful job completion."""

import uuid
from datetime import datetime
from typing import Optional
import structlog

from ..models import BazaarTransaction, TransactionType, TransactionStatus
from ..db import (
    create_transaction,
    get_transaction,
    update_transaction,
    get_job,
    get_bid,
    get_agent,
    update_agent,
)
from ..execution.quality import check_quality_threshold
from ..config import get_settings
from .x402_client import release_to_agent

logger = structlog.get_logger()


async def release_payment(
    escrow_txn_id: str,
    payee_id: str,
    payee_wallet: str,
    amount_usd: Optional[float] = None,
) -> BazaarTransaction:
    """Release escrowed payment to agent via x402.

    Flow:
    1. Call x402 to transfer from marketplace to agent wallet
    2. Record release transaction in MongoDB
    3. Update agent earnings

    Args:
        escrow_txn_id: Original escrow transaction
        payee_id: Agent receiving payment
        payee_wallet: Agent's wallet address
        amount_usd: Amount to release (defaults to full escrow)

    Returns:
        Release transaction
    """
    escrow_txn = await get_transaction(escrow_txn_id)
    if not escrow_txn:
        raise ValueError(f"Escrow transaction {escrow_txn_id} not found")

    if escrow_txn["status"] != TransactionStatus.ESCROWED.value:
        raise ValueError(f"Escrow is not active (status: {escrow_txn['status']})")

    release_amount = amount_usd or escrow_txn["amount_usd"]
    txn_id = f"txn_{uuid.uuid4().hex[:8]}"

    logger.info(
        "releasing_payment",
        escrow_txn_id=escrow_txn_id,
        payee_id=payee_id,
        amount=release_amount,
    )

    # Execute x402 payment from marketplace to agent
    x402_result = await release_to_agent(
        job_id=escrow_txn["job_id"],
        agent_wallet=payee_wallet,
        amount_usdc=release_amount,
    )

    if not x402_result.success:
        raise ValueError(f"x402 release failed: {x402_result.error}")

    # Create release transaction
    release_txn = BazaarTransaction(
        txn_id=txn_id,
        txn_type=TransactionType.RELEASE,
        job_id=escrow_txn["job_id"],
        bid_id=escrow_txn.get("bid_id"),
        payer_id=escrow_txn["payer_id"],
        payer_wallet=escrow_txn["payer_wallet"],
        payee_id=payee_id,
        payee_wallet=payee_wallet,
        amount_usd=release_amount,
        amount_usdc=release_amount,
        x402_payment_id=x402_result.txn_hash,  # Real x402 transaction hash
        x402_escrow_id=escrow_txn.get("x402_escrow_id"),
        status=TransactionStatus.RELEASED,
        created_at=datetime.utcnow(),
        released_at=datetime.utcnow(),
    )

    await create_transaction(release_txn.model_dump())

    # Update original escrow status
    await update_transaction(escrow_txn_id, {
        "status": TransactionStatus.RELEASED.value,
        "released_at": datetime.utcnow(),
    })

    # Update agent earnings
    agent = await get_agent(payee_id)
    if agent:
        await update_agent(payee_id, {
            "total_earned_usd": agent.get("total_earned_usd", 0) + release_amount,
        })

    logger.info(
        "payment_released",
        txn_id=txn_id,
        x402_txn_hash=x402_result.txn_hash[:20] + "..." if x402_result.txn_hash else None,
        amount=release_amount,
        payee_id=payee_id,
    )

    return release_txn


async def process_job_payment(job_id: str) -> dict:
    """Process payment for a completed job based on quality.

    This is the main payment flow after job completion:
    1. Check quality score
    2. Determine payment action (full, partial, refund)
    3. Execute appropriate payment

    Args:
        job_id: Completed job to process payment for

    Returns:
        Payment processing result
    """
    job = await get_job(job_id)
    if not job:
        raise ValueError(f"Job {job_id} not found")

    quality_score = job.get("quality_score", 0)
    quality_decision = await check_quality_threshold(quality_score)

    escrow_txn_id = job.get("escrow_txn_id")
    if not escrow_txn_id:
        raise ValueError(f"No escrow found for job {job_id}")

    agent_id = job.get("assigned_agent_id")
    agent = await get_agent(agent_id)
    if not agent:
        raise ValueError(f"Agent {agent_id} not found")

    # Get bid for the price
    bid_id = job.get("winning_bid_id")
    bid = await get_bid(bid_id) if bid_id else None
    agreed_price = bid.get("price_usd", job.get("budget_usd")) if bid else job.get("budget_usd")

    result = {
        "job_id": job_id,
        "quality_score": quality_score,
        "quality_decision": quality_decision,
        "agreed_price": agreed_price,
    }

    if quality_decision["action"] == "release_payment":
        # Full payment
        release_txn = await release_payment(
            escrow_txn_id=escrow_txn_id,
            payee_id=agent_id,
            payee_wallet=agent.get("wallet_address", ""),
            amount_usd=agreed_price,
        )
        result["payment_status"] = "released"
        result["amount_paid"] = agreed_price
        result["txn_id"] = release_txn.txn_id

    elif quality_decision["action"] == "partial_payment":
        # Partial payment
        partial_amount = agreed_price * quality_decision.get("payment_ratio", 0.5)
        release_txn = await release_payment(
            escrow_txn_id=escrow_txn_id,
            payee_id=agent_id,
            payee_wallet=agent.get("wallet_address", ""),
            amount_usd=partial_amount,
        )
        result["payment_status"] = "partial"
        result["amount_paid"] = partial_amount
        result["txn_id"] = release_txn.txn_id

    else:
        # Refund
        from .refund import refund_payment
        refund_txn = await refund_payment(escrow_txn_id)
        result["payment_status"] = "refunded"
        result["amount_paid"] = 0
        result["txn_id"] = refund_txn.txn_id if refund_txn else None

    logger.info(
        "job_payment_processed",
        job_id=job_id,
        payment_status=result["payment_status"],
        amount=result.get("amount_paid", 0),
    )

    return result
