#!/usr/bin/env python3
"""Run the full AgentBazaar demo.

This script demonstrates the complete flow:
1. Setup database
2. Seed demo data (agents + customer feedback)
3. Post a job with escrow
4. Agents bid on the job
5. Accept best bid
6. Execute the job
7. Evaluate quality
8. Process payment

Usage:
    python scripts/run_demo.py
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def print_header(text: str):
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)


def print_step(n: int, text: str):
    print(f"\n[Step {n}] {text}")
    print("-" * 40)


async def main():
    from bazaar.db import setup_indexes, get_db, get_collection
    from bazaar.jobs import create_job
    from bazaar.jobs.match import find_matching_agents
    from bazaar.bidding import submit_bid, accept_bid, rank_bids
    from bazaar.execution import execute_job
    from bazaar.payments import process_job_payment

    print_header("AgentBazaar Demo")
    print("AI Agent Marketplace with Verified Capabilities & x402 Payments")
    print(f"Started: {datetime.now().isoformat()}")

    # Step 0: Setup
    print_step(0, "Setup")
    await setup_indexes()
    print("Database indexes created")

    # Check if we have seed data
    db = await get_db()
    agent_count = await db.bazaar_agents.count_documents({})
    feedback_count = await db.customer_feedback.count_documents({})

    if agent_count == 0:
        print("\nNo agents found. Run: python scripts/seed_data.py first")
        return

    print(f"Found {agent_count} agents, {feedback_count} feedback documents")

    # Step 1: Show available agents
    print_step(1, "Available Agents")
    agents_collection = await get_collection("bazaar_agents")
    agents = []
    async for a in agents_collection.find({"status": "available"}).limit(5):
        agents.append(a)
        caps = a.get("capabilities", {})
        top_cap = max(caps.items(), key=lambda x: x[1]) if caps else ("none", 0)
        print(f"  {a['name']}: rating={a.get('rating_avg', 0):.1f}, "
              f"top_skill={top_cap[0]}({top_cap[1]:.2f}), "
              f"earned=${a.get('total_earned_usd', 0):.2f}")

    if not agents:
        print("No available agents!")
        return

    # Step 2: Post a job
    print_step(2, "Post Job")
    job = await create_job(
        poster_id="demo_user_001",
        title="Analyze Customer Feedback Patterns",
        description="Analyze the customer feedback to find the top 3 recurring issues. "
                    "Provide sentiment analysis and actionable recommendations.",
        budget_usd=0.50,
        collection="customer_feedback",
        deadline_minutes=5,
        required_capabilities=["sentiment_analysis", "summarization"],
        min_capability_score=0.7,
    )
    print(f"  Job ID: {job.job_id}")
    print(f"  Title: {job.title}")
    print(f"  Budget: ${job.budget_usd:.2f} (escrowed)")
    print(f"  Required: {', '.join(job.required_capabilities)}")
    print(f"  Escrow Txn: {job.escrow_txn_id}")

    # Step 3: Find matching agents
    print_step(3, "Match Agents")
    matched = await find_matching_agents(job.job_id)
    print(f"  Found {len(matched)} matching agents:")
    for m in matched[:5]:
        print(f"    {m['name']}: match_score={m.get('match_score', 0):.3f}")

    # Step 4: Agents submit bids
    print_step(4, "Submit Bids")
    bids = []

    if not matched:
        print("  No agents matched - cannot submit bids!")
        return

    # Build bid configs based on available agents
    bid_configs = []
    if len(matched) >= 1:
        bid_configs.append((matched[0]["agent_id"], 0.35, 0.88, 120, "Sentiment-first analysis with pattern extraction"))
    if len(matched) >= 2:
        bid_configs.append((matched[1]["agent_id"], 0.42, 0.92, 90, "Comprehensive multi-pass analysis"))
    if len(matched) >= 3:
        bid_configs.append((matched[2]["agent_id"], 0.28, 0.78, 180, "Cost-effective thorough analysis"))

    for agent_id, price, conf, time_est, approach in bid_configs:
        bid = await submit_bid(
            job_id=job.job_id,
            agent_id=agent_id,
            price_usd=price,
            estimated_time_seconds=time_est,
            confidence=conf,
            approach=approach,
        )
        bids.append(bid)
        print(f"  Bid {bid.bid_id}: ${price:.2f} @ {conf:.0%} confidence")

    # Step 5: Rank and view bids
    print_step(5, "Rank Bids")
    ranked = await rank_bids(job.job_id)
    for r in ranked:
        print(f"  #{r['rank']}: {r.get('agent_name', r['agent_id'])} - "
              f"${r['price_usd']:.2f}, score={r['rank_score']:.3f}")

    # Step 6: Accept best bid
    print_step(6, "Accept Best Bid")
    best_bid = ranked[0]
    assignment = await accept_bid(
        job_id=job.job_id,
        bid_id=best_bid["bid_id"],
        poster_id="demo_user_001",
    )
    print(f"  Accepted: {best_bid.get('agent_name', best_bid['agent_id'])}")
    print(f"  Price: ${best_bid['price_usd']:.2f}")
    print(f"  Est. Time: {best_bid['estimated_time_seconds']}s")

    # Step 7: Execute job
    print_step(7, "Execute Job")
    print("  Agent is working...")
    exec_result = await execute_job(job.job_id)

    if exec_result.get("status") == "completed":
        print(f"  Status: COMPLETED")
        print(f"  Quality Score: {exec_result['quality_score']:.2f}")
        print(f"  Execution Time: {exec_result['execution_time_ms']:.0f}ms")

        result = exec_result.get("result", {})
        print(f"\n  Summary: {result.get('summary', 'N/A')}")

        findings = result.get("key_findings", [])
        if findings:
            print("  Key Findings:")
            for f in findings[:3]:
                print(f"    - {f}")
    else:
        print(f"  Status: FAILED")
        print(f"  Error: {exec_result.get('error', 'Unknown')}")

    # Step 8: Process payment
    print_step(8, "Process Payment (x402)")
    payment = await process_job_payment(job.job_id)

    status = payment.get("payment_status")
    print(f"  Quality Score: {payment['quality_score']:.2f}")
    print(f"  Quality Decision: {payment['quality_decision']['action']}")
    print(f"  Payment Status: {status.upper()}")
    print(f"  Amount Paid: ${payment.get('amount_paid', 0):.2f}")
    print(f"  Transaction: {payment.get('txn_id', 'N/A')}")

    # Summary
    print_header("Demo Complete!")
    print(f"""
Summary:
  - Job: {job.title}
  - Winner: {best_bid.get('agent_name', best_bid['agent_id'])}
  - Price: ${best_bid['price_usd']:.2f}
  - Quality: {exec_result.get('quality_score', 0):.2f}
  - Payment: ${payment.get('amount_paid', 0):.2f} ({status})
  - Transaction ID: {payment.get('txn_id', 'N/A')}

AgentBazaar: Where AI agents compete on capability, not just price.
""")


if __name__ == "__main__":
    asyncio.run(main())
