"""Payment refund for failed or disputed jobs."""

import uuid
from datetime import datetime
from typing import Optional
import structlog

from ..models import BazaarTransaction, TransactionType, TransactionStatus
from ..db import create_transaction, get_transaction, update_transaction
from ..config import get_settings
from .x402_client import refund_to_poster

logger = structlog.get_logger()


async def refund_payment(escrow_txn_id: str) -> Optional[BazaarTransaction]:
    """Refund escrowed payment to job poster via x402.

    Flow:
    1. Call x402 to transfer from marketplace back to poster wallet
    2. Record refund transaction in MongoDB

    Args:
        escrow_txn_id: Original escrow transaction to refund

    Returns:
        Refund transaction, or None if failed
    """
    escrow_txn = await get_transaction(escrow_txn_id)
    if not escrow_txn:
        logger.error("escrow_not_found", txn_id=escrow_txn_id)
        return None

    if escrow_txn["status"] != TransactionStatus.ESCROWED.value:
        logger.warning(
            "escrow_not_active",
            txn_id=escrow_txn_id,
            status=escrow_txn["status"],
        )
        return None

    txn_id = f"txn_{uuid.uuid4().hex[:8]}"

    logger.info(
        "processing_refund",
        escrow_txn_id=escrow_txn_id,
        amount=escrow_txn["amount_usd"],
    )

    # Execute x402 refund from marketplace to poster
    x402_result = await refund_to_poster(
        job_id=escrow_txn["job_id"],
        poster_wallet=escrow_txn["payer_wallet"],
        amount_usdc=escrow_txn["amount_usd"],
    )

    if not x402_result.success:
        logger.error("x402_refund_failed", error=x402_result.error)
        return None

    # Create refund transaction
    refund_txn = BazaarTransaction(
        txn_id=txn_id,
        txn_type=TransactionType.REFUND,
        job_id=escrow_txn["job_id"],
        payer_id=escrow_txn["payer_id"],  # Original payer receives refund
        payer_wallet=escrow_txn["payer_wallet"],
        payee_id=escrow_txn["payer_id"],  # Refund goes back to payer
        payee_wallet=escrow_txn["payer_wallet"],
        amount_usd=escrow_txn["amount_usd"],
        amount_usdc=escrow_txn["amount_usdc"],
        x402_payment_id=x402_result.txn_hash,  # Real x402 transaction hash
        x402_escrow_id=escrow_txn.get("x402_escrow_id"),
        status=TransactionStatus.REFUNDED,
        created_at=datetime.utcnow(),
        released_at=datetime.utcnow(),
    )

    await create_transaction(refund_txn.model_dump())

    # Update original escrow status
    await update_transaction(escrow_txn_id, {
        "status": TransactionStatus.REFUNDED.value,
        "released_at": datetime.utcnow(),
    })

    logger.info(
        "refund_completed",
        txn_id=txn_id,
        x402_txn_hash=x402_result.txn_hash[:20] + "..." if x402_result.txn_hash else None,
        amount=escrow_txn["amount_usd"],
    )

    return refund_txn


async def partial_refund(
    escrow_txn_id: str,
    refund_amount: float,
) -> Optional[BazaarTransaction]:
    """Issue a partial refund for a disputed job.

    Args:
        escrow_txn_id: Original escrow transaction
        refund_amount: Amount to refund to poster

    Returns:
        Refund transaction
    """
    escrow_txn = await get_transaction(escrow_txn_id)
    if not escrow_txn:
        return None

    if refund_amount > escrow_txn["amount_usd"]:
        refund_amount = escrow_txn["amount_usd"]

    txn_id = f"txn_{uuid.uuid4().hex[:8]}"

    refund_txn = BazaarTransaction(
        txn_id=txn_id,
        txn_type=TransactionType.REFUND,
        job_id=escrow_txn["job_id"],
        payer_id=escrow_txn["payer_id"],
        payer_wallet=escrow_txn["payer_wallet"],
        payee_id=escrow_txn["payer_id"],
        payee_wallet=escrow_txn["payer_wallet"],
        amount_usd=refund_amount,
        amount_usdc=refund_amount,
        x402_escrow_id=escrow_txn.get("x402_escrow_id"),
        status=TransactionStatus.REFUNDED,
        created_at=datetime.utcnow(),
        released_at=datetime.utcnow(),
    )

    await create_transaction(refund_txn.model_dump())

    logger.info(
        "partial_refund_completed",
        txn_id=txn_id,
        amount=refund_amount,
        total_escrowed=escrow_txn["amount_usd"],
    )

    return refund_txn
