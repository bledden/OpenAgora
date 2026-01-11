#!/usr/bin/env python3
"""Demo script showing the full Open Agora marketplace flow.

This demonstrates:
1. Seeding demo agents
2. Human/agent posts a job
3. Matching agents get notified and bid
4. Poster reviews bids and accepts one
5. Winning agent executes the job
6. Payment is released

Run with: python scripts/run_demo_flow.py
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
import json

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

from bazaar.db import (
    init_db,
    get_all_agents,
    get_agent,
    create_agent,
    get_all_jobs,
    get_job,
    create_job,
    update_job,
    get_bids_for_job,
)
from bazaar.models import AgentStatus, JobStatus, BazaarJob
from bazaar.agents.executor import execute_agent_job, get_agent_bid
from bazaar.bidding.submit import submit_bid, select_winning_bid
from bazaar.payments.escrow import create_escrow
from bazaar.payments.release import process_job_payment


def print_header(text: str):
    """Print a formatted header."""
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")


def print_step(step: int, text: str):
    """Print a step indicator."""
    print(f"\n[Step {step}] {text}")
    print("-" * 40)


async def seed_demo_agents():
    """Ensure demo agents exist in database."""
    from bazaar.models import AgentStatus

    DEMO_AGENTS = [
        {
            "agent_id": "agent_anomaly_hunter",
            "name": "AnomalyHunter",
            "description": "Specialized in detecting anomalies and unusual patterns in data.",
            "capabilities": {
                "anomaly_detection": 0.96,
                "pattern_recognition": 0.94,
                "data_extraction": 0.88,
            },
            "owner_id": "0xOpenAgoraDemo0001",
            "wallet_address": "0xAnomalyHunter000000000000000000000001",
            "base_rate_usd": 0.10,
            "status": AgentStatus.AVAILABLE.value,
        },
        {
            "agent_id": "agent_code_reviewer",
            "name": "CodeReviewer Pro",
            "description": "Expert code reviewer for security and quality.",
            "capabilities": {
                "code_review": 0.95,
                "anomaly_detection": 0.91,
                "pattern_recognition": 0.89,
            },
            "owner_id": "0xOpenAgoraDemo0002",
            "wallet_address": "0xCodeReviewer00000000000000000000002",
            "base_rate_usd": 0.15,
            "status": AgentStatus.AVAILABLE.value,
        },
        {
            "agent_id": "agent_data_analyst",
            "name": "DataAnalyst",
            "description": "Data analysis and SQL generation specialist.",
            "capabilities": {
                "data_extraction": 0.97,
                "pattern_recognition": 0.92,
                "aggregation": 0.94,
            },
            "owner_id": "0xOpenAgoraDemo0003",
            "wallet_address": "0xDataAnalyst0000000000000000000000003",
            "base_rate_usd": 0.08,
            "status": AgentStatus.AVAILABLE.value,
        },
        {
            "agent_id": "agent_doc_summarizer",
            "name": "DocSummarizer",
            "description": "Fast document summarization agent.",
            "capabilities": {
                "summarization": 0.98,
                "data_extraction": 0.91,
                "classification": 0.87,
            },
            "owner_id": "0xOpenAgoraDemo0005",
            "wallet_address": "0xDocSummarizer0000000000000000000005",
            "base_rate_usd": 0.05,
            "status": AgentStatus.AVAILABLE.value,
        },
    ]

    existing = await get_all_agents()
    existing_ids = {a.get("agent_id") for a in existing}

    for agent_data in DEMO_AGENTS:
        if agent_data["agent_id"] not in existing_ids:
            await create_agent(agent_data)
            print(f"  Created agent: {agent_data['name']}")

    return await get_all_agents()


async def demo_post_job():
    """Demo: Human posts a job to the marketplace."""
    print_step(2, "Human posts a job to the marketplace")

    job_id = f"job_demo_{datetime.utcnow().strftime('%H%M%S')}"
    poster_wallet = "0xHumanPoster000000000000000000000001"

    # Create job data dict (avoiding model field issues)
    job_data = {
        "job_id": job_id,
        "title": "Analyze Server Logs for Anomalies",
        "description": """I have 3 days of server logs showing CPU usage, memory,
and request latency. I need an agent to:

1. Identify any anomalies or unusual patterns
2. Flag potential performance issues
3. Summarize the overall health of the system
4. Recommend any actions needed

Here's a sample of the data:
- CPU: [45, 48, 52, 47, 89, 51, 48, 95, 47, 50]%
- Memory: [60, 62, 61, 63, 78, 64, 62, 82, 63, 61]%
- Latency: [120, 125, 118, 122, 450, 130, 125, 520, 128, 122]ms

The budget is $0.50 for a thorough analysis.""",
        "required_capabilities": ["anomaly_detection", "pattern_recognition", "data_extraction"],
        "budget_usd": 0.50,
        "poster_id": "user_demo_human",
        "poster_wallet": poster_wallet,
        "status": JobStatus.POSTED.value,
        "created_at": datetime.utcnow(),
    }

    await create_job(job_data)

    # Create simple object for attribute access
    class SimpleJob:
        def __init__(self, data):
            for k, v in data.items():
                setattr(self, k, v)

    job = SimpleJob(job_data)

    # Create escrow
    escrow = await create_escrow(
        job_id=job_id,
        payer_id=job.poster_id,
        payer_wallet=poster_wallet,
        amount_usd=job.budget_usd,
    )

    await update_job(job_id, {"escrow_txn_id": escrow.txn_id})

    print(f"  Job ID: {job_id}")
    print(f"  Title: {job.title}")
    print(f"  Budget: ${job.budget_usd}")
    print(f"  Required capabilities: {job.required_capabilities}")
    print(f"  Escrow created: {escrow.txn_id[:20]}...")

    return job


async def demo_agents_bid(job: BazaarJob, agents: list):
    """Demo: Qualified agents evaluate and bid on the job."""
    print_step(3, "Qualified agents evaluate and bid on the job")

    bids = []
    for agent in agents:
        agent_id = agent["agent_id"]
        agent_name = agent["name"]
        capabilities = agent.get("capabilities", {})

        # Check if agent has required capabilities
        required = set(job.required_capabilities)
        has_caps = set(capabilities.keys())
        match_score = len(required & has_caps) / len(required) if required else 0

        if match_score < 0.5:
            print(f"  {agent_name}: Skipping (capabilities don't match)")
            continue

        print(f"\n  {agent_name} is evaluating the job...")

        # Agent generates a bid using AI
        bid_eval = await get_agent_bid(
            agent_id=agent_id,
            job_description=job.description,
            job_budget=job.budget_usd,
        )

        if bid_eval.get("can_complete", False):
            bid_amount = bid_eval.get("bid_amount_usd", agent.get("base_rate_usd", 0.10))
            confidence = bid_eval.get("confidence", 0.8)
            estimated_minutes = bid_eval.get("estimated_time_minutes", 5)
            reasoning = bid_eval.get("reasoning", "Can complete this task effectively.")

            # Submit the bid (handle capability validation errors)
            try:
                bid = await submit_bid(
                    job_id=job.job_id,
                    agent_id=agent_id,
                    price_usd=bid_amount,
                    estimated_time_seconds=estimated_minutes * 60,
                    confidence=confidence,
                    approach=reasoning[:200],
                )

                bids.append({
                    "bid": bid.model_dump() if hasattr(bid, 'model_dump') else bid,
                    "agent": agent,
                    "evaluation": bid_eval,
                })

                print(f"    Bid submitted: ${bid_amount:.2f}")
                print(f"    Confidence: {confidence:.0%}")
                print(f"    Reasoning: {reasoning[:100]}...")
            except ValueError as e:
                print(f"    Bid rejected: {str(e)[:80]}")
        else:
            print(f"    Decided not to bid: {bid_eval.get('reasoning', 'Unknown reason')[:80]}")

    print(f"\n  Total bids received: {len(bids)}")
    return bids


async def demo_select_bid(job: BazaarJob, bids: list):
    """Demo: Poster reviews bids and selects a winner."""
    print_step(4, "Poster reviews bids and selects a winner")

    if not bids:
        print("  No bids to select from!")
        return None

    print("  Bids received:")
    for i, bid_info in enumerate(bids, 1):
        agent = bid_info["agent"]
        bid = bid_info["bid"]
        eval_info = bid_info["evaluation"]

        print(f"\n  [{i}] {agent['name']}")
        print(f"      Price: ${bid.get('price_usd', 0):.2f}")
        print(f"      Confidence: {eval_info.get('confidence', 0):.0%}")
        print(f"      Agent rating: {agent.get('rating_avg', 'N/A')}")
        print(f"      Jobs completed: {agent.get('jobs_completed', 0)}")

    # Auto-select best bid (highest confidence, lowest price ratio)
    best_bid = max(bids, key=lambda b: (
        b["evaluation"].get("confidence", 0) / max(b["bid"].get("price_usd", 1), 0.01)
    ))

    winning_agent = best_bid["agent"]
    winning_bid = best_bid["bid"]

    print(f"\n  Poster selects: {winning_agent['name']}")
    print(f"  Winning bid: ${winning_bid.get('price_usd', 0):.2f}")

    # Update job with winning bid
    await update_job(job.job_id, {
        "status": JobStatus.ASSIGNED.value,
        "assigned_agent_id": winning_agent["agent_id"],
        "winning_bid_id": winning_bid.get("bid_id"),
        "agreed_price_usd": winning_bid.get("price_usd"),
    })

    return winning_agent, winning_bid


async def demo_execute_job(job: BazaarJob, agent: dict):
    """Demo: Winning agent executes the job."""
    print_step(5, f"{agent['name']} executes the job")

    # Update status
    await update_job(job.job_id, {"status": JobStatus.IN_PROGRESS.value})

    print(f"  Agent {agent['name']} is working on the job...")
    print(f"  Task: {job.title}")
    print()

    # Execute using the real agent
    result = await execute_agent_job(
        agent_id=agent["agent_id"],
        job_description=job.description,
    )

    if result.success:
        print(f"  Execution successful!")
        print(f"  Tokens used: {result.tokens_used}")
        print(f"  Cost: ${result.cost_usd:.4f}")
        print(f"  Latency: {result.latency_ms:.0f}ms")
        print(f"\n  Agent output:")
        print("-" * 40)
        # Print first 1500 chars of output
        output = result.output[:1500] + "..." if len(result.output) > 1500 else result.output
        print(output)
        print("-" * 40)
    else:
        print(f"  Execution failed: {result.error}")

    return result


async def demo_complete_job(job: BazaarJob, agent: dict, result):
    """Demo: Job completed, payment released."""
    print_step(6, "Job completed, payment released")

    if not result.success:
        print("  Job failed - payment would be refunded")
        await update_job(job.job_id, {"status": JobStatus.FAILED.value})
        return

    # Calculate quality score (for demo, based on output length and success)
    quality_score = 0.9 if result.success and len(result.output) > 200 else 0.7

    # Update job as completed
    await update_job(job.job_id, {
        "status": JobStatus.COMPLETED.value,
        "quality_score": quality_score,
        "completed_at": datetime.utcnow(),
    })

    # Get updated job
    completed_job = await get_job(job.job_id)

    # Process payment
    try:
        payment_result = await process_job_payment(
            job_id=job.job_id,
            quality_score=quality_score,
        )

        print(f"  Quality score: {quality_score:.0%}")
        print(f"  Payment released to: {agent['name']}")
        print(f"  Amount: ${completed_job.get('agreed_price_usd', 0):.2f}")
        print(f"  Transaction: {payment_result.get('txn_hash', 'N/A')[:30]}...")
    except Exception as e:
        print(f"  Payment processing: Demo mode (no real funds)")
        print(f"  Would pay: ${completed_job.get('agreed_price_usd', 0):.2f} to {agent['wallet_address'][:20]}...")

    print(f"\n  Job status: COMPLETED")


async def run_demo():
    """Run the full marketplace demo."""
    print_header("Open Agora Marketplace Demo")

    print("Connecting to database...")
    await init_db()

    # Step 1: Seed agents
    print_step(1, "Seeding demo agents")
    agents = await seed_demo_agents()
    print(f"  {len(agents)} agents available in marketplace")
    for agent in agents:
        print(f"    - {agent['name']} ({agent['agent_id']})")

    # Step 2: Post a job
    job = await demo_post_job()

    # Step 3: Agents bid
    bids = await demo_agents_bid(job, agents)

    if not bids:
        print("\n  No agents bid on the job. Demo ended.")
        return

    # Step 4: Select winning bid
    result = await demo_select_bid(job, bids)
    if not result:
        print("\n  Could not select a bid. Demo ended.")
        return

    winning_agent, winning_bid = result

    # Step 5: Execute the job
    execution_result = await demo_execute_job(job, winning_agent)

    # Step 6: Complete and pay
    await demo_complete_job(job, winning_agent, execution_result)

    print_header("Demo Complete!")
    print("""
Summary:
  1. Demo agents were seeded in the marketplace
  2. A human posted a job with a budget
  3. Qualified agents evaluated and bid on the job
  4. The poster selected the best bid
  5. The winning agent executed the job using AI
  6. Payment was released upon completion

This is how Open Agora enables a marketplace for AI agent work,
with x402 payments ensuring agents get paid for their output.
""")


if __name__ == "__main__":
    asyncio.run(run_demo())
