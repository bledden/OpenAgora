"""Escrow creation for job payments using x402 protocol."""

import uuid
from datetime import datetime
from typing import Optional
import structlog

from ..models import BazaarTransaction, TransactionType, TransactionStatus
from ..db import create_transaction, get_transaction, update_transaction
from ..config import get_settings
from .x402_client import escrow_job_payment

logger = structlog.get_logger()


async def create_escrow(
    job_id: str,
    payer_id: str,
    payer_wallet: str,
    amount_usd: float,
) -> BazaarTransaction:
    """Create an escrow transaction for a job using x402.

    Flow:
    1. Call x402 to receive payment from poster to marketplace
    2. Store escrow reference in MongoDB
    3. Funds held in marketplace wallet until quality verified

    Args:
        job_id: Job this escrow is for
        payer_id: ID of the job poster
        payer_wallet: Wallet address of payer
        amount_usd: Amount to escrow

    Returns:
        Created escrow transaction
    """
    settings = get_settings()
    txn_id = f"txn_{uuid.uuid4().hex[:8]}"

    logger.info(
        "creating_escrow",
        job_id=job_id,
        amount_usd=amount_usd,
        payer_wallet=payer_wallet[:10] + "...",
    )

    # Execute x402 payment from poster to marketplace
    x402_result = await escrow_job_payment(
        job_id=job_id,
        poster_wallet=payer_wallet,
        amount_usdc=amount_usd,
    )

    if not x402_result.success:
        raise ValueError(f"x402 escrow failed: {x402_result.error}")

    txn = BazaarTransaction(
        txn_id=txn_id,
        txn_type=TransactionType.ESCROW,
        job_id=job_id,
        payer_id=payer_id,
        payer_wallet=payer_wallet,
        amount_usd=amount_usd,
        amount_usdc=amount_usd,  # 1:1 for USDC
        x402_escrow_id=x402_result.txn_hash,  # Real x402 transaction hash
        status=TransactionStatus.ESCROWED,
        created_at=datetime.utcnow(),
        confirmed_at=datetime.utcnow(),
    )

    await create_transaction(txn.model_dump())

    logger.info(
        "escrow_created",
        txn_id=txn_id,
        x402_txn_hash=x402_result.txn_hash[:20] + "..." if x402_result.txn_hash else None,
        amount=amount_usd,
    )

    return txn


async def get_escrow_status(txn_id: str) -> Optional[dict]:
    """Get the current status of an escrow.

    Args:
        txn_id: Transaction ID

    Returns:
        Escrow status details
    """
    txn = await get_transaction(txn_id)
    if not txn:
        return None

    return {
        "txn_id": txn["txn_id"],
        "job_id": txn["job_id"],
        "status": txn["status"],
        "amount_usd": txn["amount_usd"],
        "x402_escrow_id": txn.get("x402_escrow_id"),
        "created_at": txn["created_at"],
        "payer_wallet": txn["payer_wallet"],
    }


async def cancel_escrow(txn_id: str) -> bool:
    """Cancel an escrow and return funds to payer.

    Only allowed if job was cancelled before assignment.
    """
    txn = await get_transaction(txn_id)
    if not txn:
        return False

    if txn["status"] != TransactionStatus.ESCROWED.value:
        logger.warning(
            "cannot_cancel_escrow",
            txn_id=txn_id,
            status=txn["status"],
        )
        return False

    # In production: Call x402 to return funds
    # For demo: Just update status

    await update_transaction(txn_id, {
        "status": TransactionStatus.REFUNDED.value,
        "released_at": datetime.utcnow(),
    })

    logger.info("escrow_cancelled", txn_id=txn_id)

    return True
