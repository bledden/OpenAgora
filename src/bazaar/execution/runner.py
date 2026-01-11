"""Job execution by agents."""

import asyncio
import json
import time
from datetime import datetime
from typing import Optional
import structlog

from ..models import JobStatus, AgentStatus
from ..db import get_job, get_agent, update_job, update_agent, get_collection
from ..llm import call_fireworks_json
from ..config import get_settings
from .quality import get_quality_suggestion, get_payment_recommendation

logger = structlog.get_logger()


EXECUTOR_SYSTEM_PROMPT = """You are an AI agent executing a task in the AgentBazaar marketplace.

Your job is to analyze data and produce high-quality results that will be evaluated by Galileo.

## Execution Approach:
1. Understand the task requirements
2. Explore the provided data samples
3. Analyze patterns and insights
4. Produce a clear, structured result

## Output Format:
Return JSON with:
```json
{
  "summary": "Brief summary of findings",
  "key_findings": ["finding1", "finding2", "finding3"],
  "details": {
    // Task-specific structured data
  },
  "confidence": 0.85,
  "methodology": "Brief description of approach"
}
```

Be thorough but concise. Quality over quantity."""


async def execute_job(job_id: str) -> dict:
    """Execute an assigned job.

    Args:
        job_id: Job to execute

    Returns:
        Execution result with quality score
    """
    settings = get_settings()
    start_time = time.time()

    job = await get_job(job_id)
    if not job:
        raise ValueError(f"Job {job_id} not found")

    if job["status"] != JobStatus.ASSIGNED.value:
        raise ValueError(f"Job {job_id} is not assigned (status: {job['status']})")

    agent_id = job["assigned_agent_id"]
    agent = await get_agent(agent_id)
    if not agent:
        raise ValueError(f"Agent {agent_id} not found")

    logger.info(
        "job_execution_started",
        job_id=job_id,
        agent_id=agent_id,
    )

    # Update job status
    await update_job(job_id, {"status": JobStatus.IN_PROGRESS.value})

    try:
        # Get data context
        data_samples = []
        if job.get("data_context"):
            data_samples = await _get_data_samples(job["data_context"])

        # Build execution prompt
        prompt = _build_execution_prompt(job, data_samples)

        # Execute with timeout
        deadline_seconds = job.get("deadline_minutes", 10) * 60
        try:
            result = await asyncio.wait_for(
                call_fireworks_json(prompt, EXECUTOR_SYSTEM_PROMPT, temperature=0.4),
                timeout=deadline_seconds,
            )
        except asyncio.TimeoutError:
            raise Exception(f"Execution timed out after {deadline_seconds}s")

        execution_time_ms = (time.time() - start_time) * 1000

        # Get AI quality suggestion (human will make final decision)
        ai_suggestion = await get_quality_suggestion(
            task_type=job.get("task_type", "analysis"),
            task_description=job.get("description", ""),
            result=result,
        )

        # Get payment recommendation (also just a suggestion)
        payment_recommendation = get_payment_recommendation(ai_suggestion)

        # Update job to PENDING_REVIEW status (not COMPLETED yet)
        # Human must review and make final decision
        await update_job(job_id, {
            "status": JobStatus.PENDING_REVIEW.value,
            "result": result,
            "ai_quality_suggestion": ai_suggestion,
            # quality_score will be set by human reviewer
        })

        # Update agent status (back to available while awaiting review)
        await update_agent(agent_id, {
            "status": AgentStatus.AVAILABLE.value,
            "last_active": datetime.utcnow(),
        })

        logger.info(
            "job_pending_review",
            job_id=job_id,
            agent_id=agent_id,
            ai_suggested_score=ai_suggestion.get("suggested_overall"),
            ai_recommendation=ai_suggestion.get("recommendation"),
            execution_time_ms=execution_time_ms,
        )

        return {
            "job_id": job_id,
            "agent_id": agent_id,
            "result": result,
            "ai_quality_suggestion": ai_suggestion,
            "payment_recommendation": payment_recommendation,
            "execution_time_ms": execution_time_ms,
            "status": "pending_review",
            "message": "Work completed. Awaiting human review to finalize quality rating and payment.",
        }

    except Exception as e:
        logger.error(
            "job_execution_failed",
            job_id=job_id,
            agent_id=agent_id,
            error=str(e),
        )

        # Update job as failed
        await update_job(job_id, {
            "status": JobStatus.DISPUTED.value,
            "result": {"error": str(e)},
            "quality_score": 0.0,
        })

        # Update agent
        await update_agent(agent_id, {
            "status": AgentStatus.AVAILABLE.value,
            "jobs_failed": agent.get("jobs_failed", 0) + 1,
        })

        return {
            "job_id": job_id,
            "agent_id": agent_id,
            "error": str(e),
            "quality_score": 0.0,
            "status": "failed",
        }


async def _get_data_samples(data_context: dict, limit: int = 10) -> list[dict]:
    """Get sample documents from data context."""
    try:
        collection_name = data_context.get("collection")
        query = data_context.get("query", {})

        collection = await get_collection(collection_name)
        pipeline = [
            {"$match": query},
            {"$sample": {"size": limit}},
        ]

        samples = []
        async for doc in collection.aggregate(pipeline):
            # Convert ObjectId to string
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])
            samples.append(doc)

        return samples
    except Exception as e:
        logger.warning("data_sample_failed", error=str(e))
        return []


def _build_execution_prompt(job: dict, data_samples: list) -> str:
    """Build the execution prompt for the agent."""
    parts = [
        f"## Task: {job.get('title', 'Unknown Task')}",
        f"\n{job.get('description', 'No description provided.')}",
    ]

    if data_samples:
        parts.append("\n## Data Samples:")
        parts.append(f"Collection: {job.get('data_context', {}).get('collection', 'unknown')}")
        parts.append(f"Sample count: {len(data_samples)}")
        parts.append("\n```json")
        parts.append(json.dumps(data_samples[:5], indent=2, default=str))  # Show first 5
        parts.append("```")

        if len(data_samples) > 5:
            parts.append(f"\n(Showing 5 of {len(data_samples)} samples)")

    parts.append("\n## Requirements:")
    parts.append(f"- Task type: {job.get('task_type', 'analysis')}")
    parts.append(f"- Required capabilities: {', '.join(job.get('required_capabilities', []))}")

    parts.append("\nAnalyze the data and provide your findings in the required JSON format.")

    return "\n".join(parts)
