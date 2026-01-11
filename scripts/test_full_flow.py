#!/usr/bin/env python3
"""Test full AgentBazaar flow: Post job -> Bid -> Accept -> Execute -> Review -> Payment."""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")


async def main():
    from bazaar.db import init_db, get_all_agents, get_job, get_agent, update_job, update_agent
    from bazaar.jobs import create_job
    from bazaar.bidding.submit import submit_bid, select_winning_bid
    from bazaar.execution.runner import execute_job
    from bazaar.models import JobStatus
    from bazaar.payments.release import release_payment

    print("=" * 60)
    print("  AgentBazaar Full Flow Test")
    print("=" * 60)

    # Initialize DB
    print("\n[1] Initializing database...")
    await init_db()
    print("    Database connected")

    # List available agents
    print("\n[2] Listing available agents...")
    agents = await get_all_agents()
    available_agents = [a for a in agents if a.get("status") == "available" and a.get("capabilities")]
    print(f"    Found {len(available_agents)} available agents")

    if not available_agents:
        print("    ERROR: No available agents. Run seed_data.py first.")
        return

    for agent in available_agents[:3]:
        caps = agent.get("capabilities", {})
        top_cap = max(caps.items(), key=lambda x: x[1]) if caps else ("none", 0)
        print(f"    - {agent['name']} ({agent['agent_id'][:15]}...) - top skill: {top_cap[0]}={top_cap[1]:.2f}")

    # Find an agent that can do summarization
    target_cap = "summarization"
    matching_agents = [a for a in available_agents
                       if a.get("capabilities", {}).get(target_cap, 0) >= 0.7]

    if not matching_agents:
        print(f"    WARNING: No agents with {target_cap} >= 0.7, using first available")
        matching_agents = available_agents[:1]

    test_agent = matching_agents[0]
    print(f"\n    Selected agent: {test_agent['name']}")

    # Post a job
    print("\n[3] Posting a new job...")
    job = await create_job(
        title="Summarize market trends",
        description="Analyze and summarize the key market trends from Q4 2024 earnings reports.",
        poster_id="test_user",
        poster_wallet="0xTestWallet0000000000000000000000000001",
        budget_usd=2.50,
        required_capabilities=["summarization"],
        min_capability_score=0.7,
    )
    print(f"    Job created: {job.job_id}")
    print(f"    Budget: ${job.budget_usd:.2f}")
    print(f"    Status: {job.status.value if hasattr(job.status, 'value') else job.status}")

    # Submit a bid
    print("\n[4] Submitting bid...")
    try:
        bid = await submit_bid(
            job_id=job.job_id,
            agent_id=test_agent['agent_id'],
            price_usd=2.00,
            confidence=0.90,
            estimated_time_seconds=60,
            approach="Will analyze earnings data and extract key trends using NLP",
        )
        print(f"    Bid submitted: {bid.bid_id}")
        print(f"    Price: ${bid.price_usd:.2f}")
        print(f"    Confidence: {bid.confidence:.0%}")
    except ValueError as e:
        print(f"    ERROR: Could not submit bid - {e}")
        # Try with lower requirements
        print("    Trying with lower capability requirement...")
        await update_job(job.job_id, {"min_capability_score": 0.3})
        bid = await submit_bid(
            job_id=job.job_id,
            agent_id=test_agent['agent_id'],
            price_usd=2.00,
            confidence=0.90,
            estimated_time_seconds=60,
            approach="Will analyze earnings data and extract key trends using NLP",
        )
        print(f"    Bid submitted: {bid.bid_id}")

    # Accept the bid
    print("\n[5] Accepting bid...")
    job_data = await select_winning_bid(job.job_id, bid.bid_id)
    print(f"    Bid accepted!")
    print(f"    Job status: {job_data.get('status')}")
    print(f"    Assigned agent: {job_data.get('assigned_agent_id')}")

    # Execute the job
    print("\n[6] Executing job...")
    print("    Agent is working...")
    exec_result = await execute_job(job.job_id)

    status = exec_result.get("status")
    print(f"    Execution complete!")
    print(f"    Status: {status}")

    if status == "pending_review":
        ai_suggestion = exec_result.get("ai_quality_suggestion", {})
        print(f"    AI Suggested Score: {ai_suggestion.get('suggested_overall', 0):.0%}")
        print(f"    AI Recommendation: {ai_suggestion.get('recommendation', 'N/A')}")

        # Show result summary
        result = exec_result.get("result", {})
        if result:
            summary = result.get("summary", str(result)[:200])
            print(f"    Result summary: {summary[:100]}...")
    elif status == "failed":
        print(f"    ERROR: {exec_result.get('error')}")
        return

    # Human review
    print("\n[7] Human review...")
    job_data = await get_job(job.job_id)
    ai_suggestion = job_data.get("ai_quality_suggestion", {})

    if ai_suggestion:
        print(f"    AI analysis:")
        print(f"      - Suggested overall: {ai_suggestion.get('suggested_overall', 0):.0%}")
        print(f"      - Recommendation: {ai_suggestion.get('recommendation', 'N/A')}")
        print(f"      - Strengths: {', '.join(ai_suggestion.get('strengths', []))[:80]}")
        if ai_suggestion.get('red_flags'):
            print(f"      - Red flags: {', '.join(ai_suggestion.get('red_flags', []))}")

    # Simulate human accepting
    human_decision = "accept"
    human_rating = 0.85
    print(f"\n    Human Decision: {human_decision.upper()}")
    print(f"    Human Rating: {human_rating:.0%}")

    # Update job with human review
    await update_job(job.job_id, {
        "status": JobStatus.COMPLETED.value,
        "quality_score": human_rating,
        "human_review_decision": human_decision,
        "human_review_rating": human_rating,
        "human_review_feedback": "Good analysis, clear summary.",
        "reviewed_by": "test_user",
        "reviewed_at": datetime.utcnow(),
        "completed_at": datetime.utcnow(),
    })

    # Process payment
    print("\n[8] Processing payment...")
    escrow_txn_id = job_data.get("escrow_txn_id")
    agent_id = job_data.get("assigned_agent_id")
    agent = await get_agent(agent_id) if agent_id else None
    agreed_price = job_data.get("final_price_usd") or job_data.get("budget_usd", 0)

    if escrow_txn_id and agent:
        try:
            txn = await release_payment(
                escrow_txn_id=escrow_txn_id,
                payee_id=agent_id,
                payee_wallet=agent.get("wallet_address", ""),
                amount_usd=agreed_price,
            )
            print(f"    Payment released: ${agreed_price:.2f}")
            print(f"    Transaction ID: {txn.txn_id}")

            # Update agent stats
            await update_agent(agent_id, {
                "jobs_completed": agent.get("jobs_completed", 0) + 1,
                "total_earned_usd": agent.get("total_earned_usd", 0) + agreed_price,
            })
            print(f"    Agent stats updated")
        except Exception as e:
            print(f"    Payment error: {e}")
    else:
        print(f"    No escrow found (simulated mode)")

    # Summary
    print("\n" + "=" * 60)
    print("  FLOW COMPLETE")
    print("=" * 60)
    print(f"  Job ID: {job.job_id}")
    print(f"  Agent: {test_agent['name']}")
    print(f"  Final Price: ${agreed_price:.2f}")
    print(f"  Human Decision: {human_decision.upper()}")
    print(f"  Human Rating: {human_rating:.0%}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
