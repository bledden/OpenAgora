"""Job creation and management."""

import uuid
from datetime import datetime, timedelta
from typing import Optional
import structlog

from ..models import BazaarJob, JobStatus, PosterType, DataContext
from ..db import create_job as db_create_job, get_job, update_job
from ..llm import get_embedding
from ..payments.escrow import create_escrow
from ..config import get_settings

logger = structlog.get_logger()


async def create_job(
    poster_id: str,
    title: str,
    description: str,
    budget_usd: float,
    collection: Optional[str] = None,
    query: Optional[dict] = None,
    required_capabilities: Optional[list[str]] = None,
    task_type: str = "analysis",
    deadline_minutes: int = 10,
    min_capability_score: float = 0.7,
    poster_type: str = "human",
    poster_wallet: str = "",
) -> BazaarJob:
    """Create a new job posting with escrow.

    Args:
        poster_id: ID of the human/agent posting the job
        title: Short job title
        description: Detailed task description
        budget_usd: Maximum budget in USD
        collection: MongoDB collection for data context
        query: MongoDB query filter for data context
        required_capabilities: List of required capability names
        task_type: Type of task (analysis, summarization, etc.)
        deadline_minutes: Time limit for completion
        min_capability_score: Minimum capability score required
        poster_type: "human" or "agent"
        poster_wallet: Wallet address for payment

    Returns:
        Created BazaarJob
    """
    settings = get_settings()
    job_id = f"job_{uuid.uuid4().hex[:8]}"

    logger.info(
        "job_creation_started",
        job_id=job_id,
        poster_id=poster_id,
        budget=budget_usd,
    )

    # Infer required capabilities from description if not provided
    if not required_capabilities:
        required_capabilities = _infer_capabilities(description, task_type)

    # Build data context
    data_context = None
    if collection:
        data_context = DataContext(
            collection=collection,
            query=query or {},
            estimated_docs=None,  # Will be updated when agents query
        )

    # Generate job embedding for matching
    job_text = f"{title}: {description}. Required: {', '.join(required_capabilities)}"
    job_embedding = await get_embedding(job_text)

    # Create escrow for budget
    escrow_txn = await create_escrow(
        job_id=job_id,
        payer_id=poster_id,
        payer_wallet=poster_wallet or f"0x{uuid.uuid4().hex[:40]}",
        amount_usd=budget_usd,
    )

    # Calculate bid deadline
    bid_deadline = datetime.utcnow() + timedelta(minutes=settings.bid_window_minutes)

    # Create job record
    job = BazaarJob(
        job_id=job_id,
        poster_id=poster_id,
        poster_type=PosterType(poster_type),
        title=title,
        description=description,
        task_type=task_type,
        required_capabilities=required_capabilities,
        min_capability_score=min_capability_score,
        job_embedding=job_embedding,
        data_context=data_context,
        budget_usd=budget_usd,
        deadline_minutes=deadline_minutes,
        escrow_txn_id=escrow_txn.txn_id,
        status=JobStatus.OPEN,
        bid_deadline=bid_deadline,
        created_at=datetime.utcnow(),
    )

    await db_create_job(job.model_dump())

    logger.info(
        "job_created",
        job_id=job_id,
        escrow_txn=escrow_txn.txn_id,
        bid_deadline=bid_deadline.isoformat(),
    )

    return job


def _infer_capabilities(description: str, task_type: str) -> list[str]:
    """Infer required capabilities from job description."""
    desc_lower = description.lower()
    capabilities = []

    capability_keywords = {
        "summarization": ["summarize", "summary", "condense", "brief"],
        "sentiment_analysis": ["sentiment", "opinion", "feeling", "positive", "negative"],
        "data_extraction": ["extract", "parse", "find", "identify"],
        "pattern_recognition": ["pattern", "trend", "anomaly", "outlier"],
        "classification": ["classify", "categorize", "sort", "label"],
        "aggregation": ["aggregate", "count", "sum", "average", "group"],
    }

    for cap, keywords in capability_keywords.items():
        if any(kw in desc_lower for kw in keywords):
            capabilities.append(cap)

    # Add based on task type
    task_type_caps = {
        "analysis": ["pattern_recognition", "aggregation"],
        "summarization": ["summarization"],
        "classification": ["classification"],
        "extraction": ["data_extraction"],
    }

    for cap in task_type_caps.get(task_type, []):
        if cap not in capabilities:
            capabilities.append(cap)

    # Default to general analysis if nothing detected
    if not capabilities:
        capabilities = ["summarization", "data_extraction"]

    return capabilities


async def get_job_details(job_id: str) -> Optional[BazaarJob]:
    """Get job by ID."""
    data = await get_job(job_id)
    if data:
        return BazaarJob(**data)
    return None


async def update_job_status(job_id: str, status: JobStatus) -> bool:
    """Update job status."""
    return await update_job(job_id, {"status": status.value})
