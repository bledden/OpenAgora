"""Webhook notifications for Open Agora.

Notifies agents when jobs are posted that match their capabilities.
"""

import asyncio
from typing import List, Dict, Any, Optional
import httpx
import structlog

from .db import get_all_agents

logger = structlog.get_logger()

# Webhook timeout
WEBHOOK_TIMEOUT = 10.0


async def notify_agents_of_job(
    job: Dict[str, Any],
    matched_agent_ids: Optional[List[str]] = None,
) -> Dict[str, bool]:
    """Notify agents about a new job via their webhooks.

    Args:
        job: The job that was created
        matched_agent_ids: Optional list of agent IDs to notify.
                          If None, notifies all agents with webhooks.

    Returns:
        Dict mapping agent_id to success status
    """
    results = {}

    try:
        agents = await get_all_agents()
    except Exception as e:
        logger.warning("webhook_agent_fetch_failed", error=str(e))
        return results

    # Filter to agents with webhooks
    agents_to_notify = [
        a for a in agents
        if a.get("webhook_url")
        and (matched_agent_ids is None or a.get("agent_id") in matched_agent_ids)
    ]

    if not agents_to_notify:
        return results

    # Prepare notification payload
    payload = {
        "event": "job.posted",
        "job": {
            "job_id": job.get("job_id"),
            "title": job.get("title"),
            "description": job.get("description"),
            "budget_usd": job.get("budget_usd"),
            "required_capabilities": job.get("required_capabilities", []),
            "poster_id": job.get("poster_id"),
            "status": job.get("status"),
            "created_at": str(job.get("created_at", "")),
        },
    }

    # Send notifications concurrently
    async with httpx.AsyncClient(timeout=WEBHOOK_TIMEOUT) as client:
        tasks = []
        for agent in agents_to_notify:
            task = _send_webhook(
                client,
                agent.get("agent_id"),
                agent.get("webhook_url"),
                payload,
            )
            tasks.append(task)

        if tasks:
            webhook_results = await asyncio.gather(*tasks, return_exceptions=True)
            for agent, result in zip(agents_to_notify, webhook_results):
                agent_id = agent.get("agent_id")
                if isinstance(result, Exception):
                    results[agent_id] = False
                    logger.warning(
                        "webhook_failed",
                        agent_id=agent_id,
                        error=str(result),
                    )
                else:
                    results[agent_id] = result

    success_count = sum(1 for v in results.values() if v)
    logger.info(
        "webhooks_sent",
        total=len(results),
        success=success_count,
        job_id=job.get("job_id"),
    )

    return results


async def _send_webhook(
    client: httpx.AsyncClient,
    agent_id: str,
    webhook_url: str,
    payload: Dict[str, Any],
) -> bool:
    """Send a webhook notification to an agent.

    Args:
        client: HTTP client
        agent_id: Agent being notified
        webhook_url: URL to POST to
        payload: Notification payload

    Returns:
        True if successful
    """
    try:
        resp = await client.post(
            webhook_url,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "X-OpenAgora-Event": "job.posted",
                "X-OpenAgora-Agent-Id": agent_id,
            },
        )

        if resp.status_code < 300:
            logger.debug(
                "webhook_success",
                agent_id=agent_id,
                status=resp.status_code,
            )
            return True
        else:
            logger.warning(
                "webhook_non_success",
                agent_id=agent_id,
                status=resp.status_code,
            )
            return False

    except Exception as e:
        logger.warning(
            "webhook_error",
            agent_id=agent_id,
            url=webhook_url[:50] + "...",
            error=str(e),
        )
        return False


async def notify_job_assigned(job: Dict[str, Any], agent_id: str) -> bool:
    """Notify an agent that they've been assigned a job.

    Args:
        job: The job details
        agent_id: The assigned agent

    Returns:
        True if notification was successful
    """
    try:
        agents = await get_all_agents()
        agent = next((a for a in agents if a.get("agent_id") == agent_id), None)

        if not agent or not agent.get("webhook_url"):
            return False

        payload = {
            "event": "job.assigned",
            "job": {
                "job_id": job.get("job_id"),
                "title": job.get("title"),
                "description": job.get("description"),
                "budget_usd": job.get("budget_usd"),
                "required_capabilities": job.get("required_capabilities", []),
                "poster_id": job.get("poster_id"),
                "status": "assigned",
            },
        }

        async with httpx.AsyncClient(timeout=WEBHOOK_TIMEOUT) as client:
            return await _send_webhook(
                client,
                agent_id,
                agent.get("webhook_url"),
                payload,
            )

    except Exception as e:
        logger.warning("job_assigned_webhook_failed", agent_id=agent_id, error=str(e))
        return False


async def notify_bid_selected(job: Dict[str, Any], agent_id: str, bid: Dict[str, Any]) -> bool:
    """Notify an agent that their bid was selected.

    Args:
        job: The job details
        agent_id: The winning agent
        bid: The winning bid details

    Returns:
        True if notification was successful
    """
    try:
        agents = await get_all_agents()
        agent = next((a for a in agents if a.get("agent_id") == agent_id), None)

        if not agent or not agent.get("webhook_url"):
            return False

        payload = {
            "event": "bid.selected",
            "job": {
                "job_id": job.get("job_id"),
                "title": job.get("title"),
                "description": job.get("description"),
            },
            "bid": {
                "bid_id": bid.get("bid_id"),
                "amount_usd": bid.get("price_usd") or bid.get("amount_usd"),
            },
        }

        async with httpx.AsyncClient(timeout=WEBHOOK_TIMEOUT) as client:
            return await _send_webhook(
                client,
                agent_id,
                agent.get("webhook_url"),
                payload,
            )

    except Exception as e:
        logger.warning("bid_selected_webhook_failed", agent_id=agent_id, error=str(e))
        return False
