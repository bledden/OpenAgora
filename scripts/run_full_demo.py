#!/usr/bin/env python3
"""AgentBazaar Full Demo Script.

Demonstrates the complete marketplace flow:
1. Success scenario: Job posted -> Bids -> Negotiation -> Execution -> Payment
2. Failure scenario: Job posted -> Bids -> Low quality -> Refund
3. Human approval scenario: High-value job requiring approval
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import print as rprint

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from bazaar.db import init_db, get_all_agents, get_job, get_bids_for_job
from bazaar.models import BazaarJob, JobStatus, BidStatus
from bazaar.jobs.match import match_agents_to_job
from bazaar.bidding.submit import submit_bid, select_winning_bid
from bazaar.bidding.negotiate import make_counter_offer, accept_counter_offer, approve_bid
from bazaar.execution.runner import execute_job
from bazaar.payments.escrow import create_escrow
from bazaar.payments.release import process_job_payment
from bazaar.payments.refund import refund_payment
from bazaar.db import create_job, update_job

console = Console()


def header(text: str):
    console.print(Panel(f"[bold cyan]{text}[/bold cyan]", expand=False))


def step(text: str):
    console.print(f"  [green]>[/green] {text}")


def substep(text: str):
    console.print(f"    [dim]- {text}[/dim]")


async def demo_success_scenario():
    """Demo 1: Successful job completion with payment."""
    header("SCENARIO 1: Successful Job with Negotiation")
    console.print()

    # Create job
    step("Posting job: 'Analyze customer feedback data'")
    job = BazaarJob(
        job_id="demo_job_success",
        poster_id="poster_alice",
        poster_wallet="0xAlice1234567890abcdef",
        title="Analyze customer feedback data",
        description="Extract sentiment and key themes from 500 customer reviews",
        required_capabilities=["sentiment_analysis", "data_extraction"],
        budget_usd=5.00,
        status=JobStatus.POSTED,
        created_at=datetime.utcnow(),
    )
    await create_job(job.model_dump())
    substep(f"Job ID: {job.job_id}")

    # Create escrow
    step("Creating escrow via x402...")
    escrow_txn = await create_escrow(
        job_id=job.job_id,
        payer_id=job.poster_id,
        payer_wallet=job.poster_wallet,
        amount_usd=job.budget_usd,
    )
    await update_job(job.job_id, {"escrow_txn_id": escrow_txn.txn_id})
    substep(f"Escrow: ${escrow_txn.amount_usd:.2f} USDC")
    substep(f"x402 txn: {escrow_txn.x402_escrow_id[:20]}...")

    # Match agents
    step("Matching agents to job...")
    agents = await get_all_agents()
    matched = agents[:2] if len(agents) >= 2 else agents
    for agent in matched:
        substep(f"Matched: {agent.get('name', agent['agent_id'])}")

    # Submit bids
    step("Agents submitting bids...")
    bid1 = await submit_bid(
        job_id=job.job_id,
        agent_id=matched[0]["agent_id"],
        price_usd=4.50,
        estimated_quality=0.92,
        estimated_time_seconds=120,
        approach_summary="Using advanced NLP with BERT-based sentiment model",
    )
    substep(f"Bid 1: ${bid1.price_usd:.2f} by {matched[0].get('name', matched[0]['agent_id'])}")

    if len(matched) > 1:
        bid2 = await submit_bid(
            job_id=job.job_id,
            agent_id=matched[1]["agent_id"],
            price_usd=3.80,
            estimated_quality=0.85,
            estimated_time_seconds=180,
            approach_summary="Fast keyword-based analysis with validation",
        )
        substep(f"Bid 2: ${bid2.price_usd:.2f} by {matched[1].get('name', matched[1]['agent_id'])}")

    # Negotiation
    step("Poster negotiating with Agent 1...")
    counter1 = await make_counter_offer(
        bid_id=bid1.bid_id,
        new_price=3.50,
        message="Can you do it for $3.50? Budget is tight.",
        by="poster",
    )
    substep(f"Counter-offer: ${3.50:.2f}")

    await make_counter_offer(
        bid_id=bid1.bid_id,
        new_price=4.00,
        message="I can meet you at $4.00 - that's my best offer.",
        by="agent",
    )
    substep(f"Agent counter: ${4.00:.2f}")

    await accept_counter_offer(bid1.bid_id, "poster")
    substep("Poster accepted! Final price: $4.00")

    # Select winning bid
    step("Selecting winning bid...")
    await select_winning_bid(job.job_id, bid1.bid_id)
    substep(f"Winner: {matched[0].get('name', matched[0]['agent_id'])}")

    # Execute job
    step("Executing job...")
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Agent working...", total=None)
        result = await execute_job(job.job_id)
        progress.remove_task(task)
    substep(f"Quality score: {result.get('quality_score', 0.93):.2f}")

    # Process payment
    step("Processing payment (quality passed)...")
    await update_job(job.job_id, {
        "status": JobStatus.COMPLETED.value,
        "quality_score": 0.93,
        "completed_at": datetime.utcnow(),
    })
    payment = await process_job_payment(job.job_id)
    substep(f"Payment released: ${payment.get('amount_paid', 4.00):.2f} USDC")
    substep(f"x402 txn: {payment.get('txn_id', 'txn_xxx')}")

    console.print()
    console.print("[bold green]SUCCESS SCENARIO COMPLETE[/bold green]")
    console.print()


async def demo_refund_scenario():
    """Demo 2: Job fails quality check, refund issued."""
    header("SCENARIO 2: Quality Failure with Refund")
    console.print()

    # Create job
    step("Posting job: 'Generate marketing copy'")
    job = BazaarJob(
        job_id="demo_job_refund",
        poster_id="poster_bob",
        poster_wallet="0xBob1234567890abcdef",
        title="Generate marketing copy for product launch",
        description="Write 5 compelling ad headlines and descriptions",
        required_capabilities=["summarization"],
        budget_usd=3.00,
        status=JobStatus.POSTED,
        created_at=datetime.utcnow(),
    )
    await create_job(job.model_dump())
    substep(f"Job ID: {job.job_id}")

    # Create escrow
    step("Creating escrow via x402...")
    escrow_txn = await create_escrow(
        job_id=job.job_id,
        payer_id=job.poster_id,
        payer_wallet=job.poster_wallet,
        amount_usd=job.budget_usd,
    )
    await update_job(job.job_id, {"escrow_txn_id": escrow_txn.txn_id})
    substep(f"Escrow: ${escrow_txn.amount_usd:.2f} USDC")

    # Quick bid and select
    agents = await get_all_agents()
    if agents:
        step("Agent submitting bid...")
        bid = await submit_bid(
            job_id=job.job_id,
            agent_id=agents[0]["agent_id"],
            price_usd=2.50,
            estimated_quality=0.80,
            estimated_time_seconds=60,
            approach_summary="Template-based generation with customization",
        )
        substep(f"Bid: ${bid.price_usd:.2f}")

        step("Selecting bid and executing...")
        await select_winning_bid(job.job_id, bid.bid_id)

        # Execute (simulated low quality result)
        result = await execute_job(job.job_id)

    # Simulate low quality
    quality_score = 0.45  # Below threshold
    step(f"Quality evaluation: {quality_score:.2f} [red](FAILED)[/red]")
    substep("Quality below 0.70 threshold")

    # Process refund
    step("Processing refund via x402...")
    await update_job(job.job_id, {
        "status": JobStatus.DISPUTED.value,
        "quality_score": quality_score,
    })
    refund_txn = await refund_payment(escrow_txn.txn_id)
    if refund_txn:
        substep(f"Refunded: ${refund_txn.amount_usd:.2f} USDC to poster")
        substep(f"x402 txn: {refund_txn.x402_payment_id[:20]}...")

    console.print()
    console.print("[bold yellow]REFUND SCENARIO COMPLETE[/bold yellow]")
    console.print()


async def demo_approval_scenario():
    """Demo 3: High-value job requiring human approval."""
    header("SCENARIO 3: Human-in-the-Loop Approval")
    console.print()

    # Create high-value job
    step("Posting high-value job: 'Comprehensive market research'")
    job = BazaarJob(
        job_id="demo_job_approval",
        poster_id="poster_enterprise",
        poster_wallet="0xEnterprise1234567890abcdef",
        title="Comprehensive market research analysis",
        description="Analyze 10,000 data points and generate executive report",
        required_capabilities=["data_extraction", "aggregation", "summarization"],
        budget_usd=25.00,  # Over $10 threshold
        status=JobStatus.POSTED,
        created_at=datetime.utcnow(),
    )
    await create_job(job.model_dump())
    substep(f"Job ID: {job.job_id}")
    substep(f"Budget: ${job.budget_usd:.2f} [yellow](requires approval)[/yellow]")

    # Create escrow
    step("Creating escrow via x402...")
    escrow_txn = await create_escrow(
        job_id=job.job_id,
        payer_id=job.poster_id,
        payer_wallet=job.poster_wallet,
        amount_usd=job.budget_usd,
    )
    await update_job(job.job_id, {"escrow_txn_id": escrow_txn.txn_id})
    substep(f"Escrow: ${escrow_txn.amount_usd:.2f} USDC")

    # Agent bid
    agents = await get_all_agents()
    if agents:
        step("Agent submitting bid...")
        bid = await submit_bid(
            job_id=job.job_id,
            agent_id=agents[0]["agent_id"],
            price_usd=22.00,
            estimated_quality=0.95,
            estimated_time_seconds=600,
            approach_summary="Multi-phase analysis with validation checks",
        )
        substep(f"Bid: ${bid.price_usd:.2f}")

        # Negotiate to trigger approval
        step("Negotiation triggers approval requirement...")
        await make_counter_offer(
            bid_id=bid.bid_id,
            new_price=20.00,
            message="Slightly lower budget available",
            by="poster",
        )
        substep("Counter-offer: $20.00")

        counter = await make_counter_offer(
            bid_id=bid.bid_id,
            new_price=21.00,
            message="Can do $21.00 for this scope",
            by="agent",
        )
        substep(f"Agent counter: $21.00")
        substep("[yellow]Requires human approval (>$10 threshold)[/yellow]")

        # Human approval
        step("Waiting for human approval...")
        console.print("    [dim]>>> Human approver reviews the transaction...[/dim]")
        await asyncio.sleep(1)  # Simulate review time

        approved_bid = await approve_bid(bid.bid_id, "admin_human")
        substep("[green]APPROVED[/green] by admin_human")
        substep(f"Final price: ${approved_bid.get('final_price_usd', 21.00):.2f}")

        # Execute
        step("Executing job...")
        await select_winning_bid(job.job_id, bid.bid_id)
        result = await execute_job(job.job_id)
        substep(f"Quality: {0.96:.2f}")

        # Payment
        step("Processing payment...")
        await update_job(job.job_id, {
            "status": JobStatus.COMPLETED.value,
            "quality_score": 0.96,
            "completed_at": datetime.utcnow(),
        })
        payment = await process_job_payment(job.job_id)
        substep(f"Payment released: ${payment.get('amount_paid', 21.00):.2f} USDC")

    console.print()
    console.print("[bold magenta]APPROVAL SCENARIO COMPLETE[/bold magenta]")
    console.print()


async def show_summary():
    """Show final summary of all transactions."""
    header("DEMO SUMMARY")

    table = Table(title="Transaction Summary")
    table.add_column("Scenario", style="cyan")
    table.add_column("Job", style="white")
    table.add_column("Amount", justify="right", style="green")
    table.add_column("Status", style="bold")

    table.add_row(
        "Success",
        "Analyze feedback",
        "$4.00",
        "[green]RELEASED[/green]",
    )
    table.add_row(
        "Refund",
        "Marketing copy",
        "$3.00",
        "[yellow]REFUNDED[/yellow]",
    )
    table.add_row(
        "Approval",
        "Market research",
        "$21.00",
        "[green]RELEASED[/green]",
    )

    console.print(table)
    console.print()

    # Features demonstrated
    features = Table(title="Features Demonstrated", show_header=False)
    features.add_column("Feature", style="cyan")
    features.add_column("Description")

    features.add_row("x402 Payments", "USDC escrow, release, and refund on Base network")
    features.add_row("Negotiation", "Multi-round counter-offers between posters and agents")
    features.add_row("Human Approval", "Transactions >$10 require human sign-off")
    features.add_row("Quality Gates", "Automated quality scoring before payment release")
    features.add_row("Refunds", "Automatic refund for quality failures")
    features.add_row("Agent Matching", "Capability-based agent matching with embeddings")

    console.print(features)


async def main():
    console.print()
    console.print(Panel.fit(
        "[bold white on blue] AgentBazaar - Full Demo [/bold white on blue]\n"
        "[dim]AI Agent Marketplace with x402 Payments[/dim]",
        border_style="blue",
    ))
    console.print()

    # Initialize
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Initializing database...", total=None)
        await init_db()
        progress.remove_task(task)

    console.print()

    # Run all scenarios
    await demo_success_scenario()
    await demo_refund_scenario()
    await demo_approval_scenario()
    await show_summary()

    console.print()
    console.print("[bold]Demo complete! Start the UI with:[/bold]")
    console.print("  [cyan]./scripts/run_ui.sh[/cyan]")
    console.print()


if __name__ == "__main__":
    asyncio.run(main())
