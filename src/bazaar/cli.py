"""AgentBazaar CLI for demo and testing."""

import asyncio
from datetime import datetime
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import print as rprint

app = typer.Typer(name="bazaar", help="AgentBazaar - AI Agent Marketplace")
console = Console()


def run_async(coro):
    """Run async function in sync context."""
    return asyncio.get_event_loop().run_until_complete(coro)


# ============================================================
# Setup Commands
# ============================================================

@app.command()
def setup():
    """Initialize database indexes and verify connections."""
    from .db import setup_indexes, get_db

    async def _setup():
        console.print("[bold blue]Setting up AgentBazaar...[/]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Connecting to MongoDB...", total=None)
            db = await get_db()
            progress.update(task, description="Connected to MongoDB!")

            progress.add_task("Creating indexes...", total=None)
            await setup_indexes()

        console.print("[bold green]Setup complete![/]")

    run_async(_setup())


# ============================================================
# Agent Commands
# ============================================================

@app.command()
def register_agent(
    name: str = typer.Option(..., help="Agent name"),
    description: str = typer.Option(..., help="Agent description"),
    owner: str = typer.Option("demo_user", help="Owner ID"),
    skip_benchmark: bool = typer.Option(False, help="Skip benchmarking"),
):
    """Register a new AI agent with capability benchmarking."""
    from .registry import register_agent as reg_agent

    async def _register():
        console.print(f"[bold blue]Registering agent: {name}[/]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            if not skip_benchmark:
                progress.add_task("Running benchmark suite (this may take a minute)...", total=None)

            agent = await reg_agent(
                name=name,
                description=description,
                owner_id=owner,
                skip_benchmark=skip_benchmark,
            )

        # Display agent card
        cap_str = "\n".join(
            f"  {k}: {v:.2f}" for k, v in agent.capabilities.model_dump().items() if v > 0
        )

        panel = Panel(
            f"""[bold]Agent ID:[/] {agent.agent_id}
[bold]Name:[/] {agent.name}
[bold]Status:[/] {agent.status.value}
[bold]Provider:[/] {agent.provider.value}

[bold]Capabilities:[/]
{cap_str}

[bold]Wallet:[/] {agent.wallet_address[:20]}...""",
            title="[green]Agent Registered[/]",
        )
        console.print(panel)

    run_async(_register())


@app.command()
def list_agents():
    """List all registered agents."""
    from .db import get_collection

    async def _list():
        collection = await get_collection("bazaar_agents")
        agents = []
        async for doc in collection.find().sort("rating_avg", -1).limit(20):
            agents.append(doc)

        if not agents:
            console.print("[yellow]No agents registered yet.[/]")
            return

        table = Table(title="Registered Agents")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Status")
        table.add_column("Rating", justify="right")
        table.add_column("Jobs", justify="right")
        table.add_column("Earned", justify="right")

        for a in agents:
            status_color = "green" if a.get("status") == "available" else "yellow"
            table.add_row(
                a.get("agent_id", "?"),
                a.get("name", "?"),
                f"[{status_color}]{a.get('status', '?')}[/]",
                f"{a.get('rating_avg', 0):.1f}",
                str(a.get("jobs_completed", 0)),
                f"${a.get('total_earned_usd', 0):.2f}",
            )

        console.print(table)

    run_async(_list())


# ============================================================
# Job Commands
# ============================================================

@app.command()
def post_job(
    title: str = typer.Option(..., help="Job title"),
    description: str = typer.Option(..., help="Job description"),
    budget: float = typer.Option(0.50, help="Budget in USD"),
    collection: Optional[str] = typer.Option(None, help="MongoDB collection for data context"),
    deadline: int = typer.Option(10, help="Deadline in minutes"),
    poster: str = typer.Option("demo_user", help="Poster ID"),
):
    """Post a new job to the marketplace."""
    from .jobs import create_job
    from .jobs.match import find_matching_agents, notify_matching_agents

    async def _post():
        console.print(f"[bold blue]Posting job: {title}[/]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task("Creating job and escrow...", total=None)

            job = await create_job(
                poster_id=poster,
                title=title,
                description=description,
                budget_usd=budget,
                collection=collection,
                deadline_minutes=deadline,
            )

        # Display job card
        panel = Panel(
            f"""[bold]Job ID:[/] {job.job_id}
[bold]Title:[/] {job.title}
[bold]Status:[/] {job.status.value}
[bold]Budget:[/] ${job.budget_usd:.2f} (escrowed)
[bold]Deadline:[/] {job.deadline_minutes} minutes
[bold]Required Capabilities:[/] {', '.join(job.required_capabilities)}
[bold]Escrow Txn:[/] {job.escrow_txn_id}""",
            title="[green]Job Posted[/]",
        )
        console.print(panel)

        # Find matching agents
        console.print("\n[bold]Finding matching agents...[/]")
        agents = await find_matching_agents(job.job_id)

        if agents:
            table = Table(title="Matching Agents")
            table.add_column("Agent", style="cyan")
            table.add_column("Rating", justify="right")
            table.add_column("Match Score", justify="right")
            table.add_column("Base Rate", justify="right")

            for a in agents[:5]:
                table.add_row(
                    a.get("name", a.get("agent_id")),
                    f"{a.get('rating_avg', 0):.1f}",
                    f"{a.get('match_score', 0):.2f}",
                    f"${a.get('base_rate_usd', 0):.3f}",
                )

            console.print(table)
            await notify_matching_agents(job.job_id, agents)
            console.print(f"[green]Notified {len(agents)} agents[/]")
        else:
            console.print("[yellow]No matching agents found[/]")

    run_async(_post())


@app.command()
def list_jobs():
    """List open jobs."""
    from .db import find_open_jobs

    async def _list():
        jobs = await find_open_jobs()

        if not jobs:
            console.print("[yellow]No open jobs.[/]")
            return

        table = Table(title="Open Jobs")
        table.add_column("ID", style="cyan")
        table.add_column("Title", style="green")
        table.add_column("Budget", justify="right")
        table.add_column("Bids", justify="right")
        table.add_column("Status")

        for j in jobs:
            table.add_row(
                j.get("job_id", "?"),
                j.get("title", "?")[:30],
                f"${j.get('budget_usd', 0):.2f}",
                str(j.get("bid_count", 0)),
                j.get("status", "?"),
            )

        console.print(table)

    run_async(_list())


# ============================================================
# Bid Commands
# ============================================================

@app.command()
def submit_bid(
    job_id: str = typer.Option(..., help="Job ID to bid on"),
    agent_id: str = typer.Option(..., help="Agent submitting bid"),
    price: float = typer.Option(..., help="Bid price in USD"),
    time_estimate: int = typer.Option(120, help="Estimated seconds to complete"),
    confidence: float = typer.Option(0.85, help="Confidence level 0-1"),
    approach: str = typer.Option("Standard analysis approach", help="Brief approach description"),
):
    """Submit a bid on a job."""
    from .bidding import submit_bid as do_submit

    async def _submit():
        console.print(f"[bold blue]Submitting bid on {job_id}...[/]")

        bid = await do_submit(
            job_id=job_id,
            agent_id=agent_id,
            price_usd=price,
            estimated_time_seconds=time_estimate,
            confidence=confidence,
            approach=approach,
        )

        panel = Panel(
            f"""[bold]Bid ID:[/] {bid.bid_id}
[bold]Job:[/] {bid.job_id}
[bold]Agent:[/] {bid.agent_id}
[bold]Price:[/] ${bid.price_usd:.2f}
[bold]Confidence:[/] {bid.confidence:.0%}
[bold]Est. Time:[/] {bid.estimated_time_seconds}s""",
            title="[green]Bid Submitted[/]",
        )
        console.print(panel)

    run_async(_submit())


@app.command()
def view_bids(job_id: str = typer.Option(..., help="Job ID")):
    """View and rank bids for a job."""
    from .bidding import rank_bids

    async def _view():
        ranked = await rank_bids(job_id)

        if not ranked:
            console.print(f"[yellow]No bids for job {job_id}[/]")
            return

        table = Table(title=f"Bids for {job_id}")
        table.add_column("Rank", justify="right")
        table.add_column("Agent", style="cyan")
        table.add_column("Price", justify="right")
        table.add_column("Confidence", justify="right")
        table.add_column("Score", justify="right", style="green")

        for bid in ranked:
            table.add_row(
                str(bid.get("rank", "?")),
                bid.get("agent_name", bid.get("agent_id", "?")),
                f"${bid.get('price_usd', 0):.2f}",
                f"{bid.get('confidence', 0):.0%}",
                f"{bid.get('rank_score', 0):.3f}",
            )

        console.print(table)

    run_async(_view())


@app.command()
def accept_bid(
    job_id: str = typer.Option(..., help="Job ID"),
    bid_id: str = typer.Option(..., help="Bid ID to accept"),
    poster: str = typer.Option("demo_user", help="Poster ID for verification"),
):
    """Accept a bid and assign the job."""
    from .bidding import accept_bid as do_accept

    async def _accept():
        console.print(f"[bold blue]Accepting bid {bid_id}...[/]")

        result = await do_accept(
            job_id=job_id,
            bid_id=bid_id,
            poster_id=poster,
        )

        panel = Panel(
            f"""[bold]Job:[/] {result['job_id']}
[bold]Assigned to:[/] {result['agent_id']}
[bold]Price:[/] ${result['price_usd']:.2f}
[bold]Est. Time:[/] {result['estimated_time_seconds']}s""",
            title="[green]Bid Accepted - Job Assigned[/]",
        )
        console.print(panel)

    run_async(_accept())


# ============================================================
# Execution Commands
# ============================================================

@app.command()
def execute_job(job_id: str = typer.Option(..., help="Job ID to execute")):
    """Execute an assigned job."""
    from .execution import execute_job as do_execute

    async def _execute():
        console.print(f"[bold blue]Executing job {job_id}...[/]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task("Agent is working...", total=None)
            result = await do_execute(job_id)

        status = result.get("status")
        if status in ("pending_review", "completed"):
            ai_suggestion = result.get("ai_quality_suggestion", {})
            suggested_score = ai_suggestion.get("suggested_overall", 0) if ai_suggestion else 0
            recommendation = ai_suggestion.get("recommendation", "N/A") if ai_suggestion else "N/A"

            panel = Panel(
                f"""[bold]Job:[/] {result['job_id']}
[bold]Agent:[/] {result['agent_id']}
[bold]Status:[/] [cyan]PENDING HUMAN REVIEW[/]
[bold]Execution Time:[/] {result['execution_time_ms']:.0f}ms

[bold cyan]AI Quality Suggestion:[/]
  Suggested Score: {suggested_score:.0%}
  Recommendation: {recommendation}

[bold]Result Summary:[/]
{result.get('result', {}).get('summary', 'No summary')}

[yellow]Run 'list-reviews' to see pending reviews
Run 'review-job --job-id {job_id}' to review this job[/]""",
                title="[cyan]Work Complete - Awaiting Review[/]",
            )
        else:
            panel = Panel(
                f"""[bold]Job:[/] {result['job_id']}
[bold]Error:[/] {result.get('error', 'Unknown error')}""",
                title="[red]Job Failed[/]",
            )

        console.print(panel)

    run_async(_execute())


@app.command()
def process_payment(job_id: str = typer.Option(..., help="Job ID to process payment")):
    """Process payment for a completed job based on quality."""
    from .payments import process_job_payment

    async def _pay():
        console.print(f"[bold blue]Processing payment for {job_id}...[/]")

        result = await process_job_payment(job_id)

        status_color = {
            "released": "green",
            "partial": "yellow",
            "refunded": "red",
        }.get(result.get("payment_status"), "white")

        panel = Panel(
            f"""[bold]Job:[/] {result['job_id']}
[bold]Quality Score:[/] {result['quality_score']:.2f}
[bold]Payment Status:[/] [{status_color}]{result['payment_status']}[/]
[bold]Amount Paid:[/] ${result.get('amount_paid', 0):.2f}
[bold]Transaction:[/] {result.get('txn_id', 'N/A')}

[bold]Quality Decision:[/]
{result.get('quality_decision', {}).get('message', '')}""",
            title=f"[{status_color}]Payment Processed[/]",
        )
        console.print(panel)

    run_async(_pay())


# ============================================================
# Human Review Commands
# ============================================================

@app.command()
def list_reviews():
    """List jobs pending human quality review."""
    from .db import get_all_jobs
    from .models import JobStatus

    async def _list():
        jobs = await get_all_jobs()
        pending = [j for j in jobs if j.get("status") == JobStatus.PENDING_REVIEW.value]

        if not pending:
            console.print("[green]No jobs pending review.[/]")
            return

        table = Table(title="Pending Reviews")
        table.add_column("Job ID", style="cyan")
        table.add_column("Title", style="green")
        table.add_column("Agent")
        table.add_column("Budget", justify="right")
        table.add_column("AI Suggestion", justify="right")

        for j in pending:
            ai_suggestion = j.get("ai_quality_suggestion", {})
            suggested_score = ai_suggestion.get("suggested_overall", 0) if ai_suggestion else 0
            recommendation = ai_suggestion.get("recommendation", "?") if ai_suggestion else "?"

            table.add_row(
                j.get("job_id", "?"),
                j.get("title", "?")[:30],
                j.get("assigned_agent_id", "?")[:10] + "...",
                f"${j.get('budget_usd', 0):.2f}",
                f"{suggested_score:.0%} ({recommendation})",
            )

        console.print(table)
        console.print(f"\n[yellow]Use 'review-job --job-id <ID>' to review a job[/]")

    run_async(_list())


@app.command()
def review_job(
    job_id: str = typer.Option(..., help="Job ID to review"),
):
    """View job details and AI quality suggestion for human review."""
    from .db import get_job, get_agent
    from .models import JobStatus

    async def _review():
        job = await get_job(job_id)
        if not job:
            console.print(f"[red]Job {job_id} not found[/]")
            return

        if job.get("status") != JobStatus.PENDING_REVIEW.value:
            console.print(f"[yellow]Job is not pending review (status: {job.get('status')})[/]")
            return

        # Get agent info
        agent = await get_agent(job.get("assigned_agent_id")) if job.get("assigned_agent_id") else None
        agent_name = agent.get("name") if agent else job.get("assigned_agent_id", "Unknown")

        # AI Suggestion
        ai = job.get("ai_quality_suggestion", {})

        console.print(Panel(
            f"""[bold]Job ID:[/] {job_id}
[bold]Title:[/] {job.get('title')}
[bold]Description:[/] {job.get('description', '')[:200]}

[bold]Completed by:[/] {agent_name}
[bold]Budget:[/] ${job.get('budget_usd', 0):.2f}

[bold cyan]AI Quality Suggestion:[/]
  Overall Score: {ai.get('suggested_overall', 0):.0%}
  Recommendation: {ai.get('recommendation', 'N/A')}

  Scores:
    Relevance: {ai.get('scores', {}).get('relevance', 0):.0%}
    Accuracy: {ai.get('scores', {}).get('accuracy', 0):.0%}
    Completeness: {ai.get('scores', {}).get('completeness', 0):.0%}
    Clarity: {ai.get('scores', {}).get('clarity', 0):.0%}
    Actionability: {ai.get('scores', {}).get('actionability', 0):.0%}

  Feedback: {ai.get('feedback', 'N/A')}

[bold green]Strengths:[/] {', '.join(ai.get('strengths', [])) or 'None'}
[bold yellow]Improvements:[/] {', '.join(ai.get('improvements', [])) or 'None'}
[bold red]Red Flags:[/] {', '.join(ai.get('red_flags', [])) or 'None'}""",
            title="[cyan]Job Review[/]",
        ))

        # Result preview
        result = job.get("result", {})
        if result:
            summary = result.get("summary", str(result))[:300]
            console.print(Panel(
                summary,
                title="[blue]Agent's Result (preview)[/]",
            ))

        console.print("\n[yellow]Use 'submit-review --job-id <ID> --decision <accept|partial|reject>' to submit your decision[/]")

    run_async(_review())


@app.command()
def submit_review(
    job_id: str = typer.Option(..., help="Job ID to review"),
    decision: str = typer.Option(..., help="Decision: accept, partial, or reject"),
    rating: float = typer.Option(None, help="Quality rating 0.0-1.0 (defaults based on decision)"),
    feedback: str = typer.Option("", help="Feedback for the agent"),
    reviewer: str = typer.Option("demo_user", help="Reviewer ID"),
):
    """Submit human review decision for a completed job."""
    from .db import get_job, get_agent, update_job, update_agent as db_update_agent
    from .models import JobStatus
    from .payments.release import release_payment
    from .payments.refund import refund_payment
    from datetime import datetime

    async def _submit():
        if decision not in ["accept", "partial", "reject"]:
            console.print("[red]Decision must be 'accept', 'partial', or 'reject'[/]")
            return

        job = await get_job(job_id)
        if not job:
            console.print(f"[red]Job {job_id} not found[/]")
            return

        if job.get("status") != JobStatus.PENDING_REVIEW.value:
            console.print(f"[yellow]Job is not pending review (status: {job.get('status')})[/]")
            return

        # Default rating based on decision
        final_rating = rating
        if final_rating is None:
            final_rating = {"accept": 1.0, "partial": 0.5, "reject": 0.2}[decision]

        # Validate rating
        if not (0.0 <= final_rating <= 1.0):
            console.print("[red]Rating must be between 0.0 and 1.0[/]")
            return

        console.print(f"[bold blue]Submitting review for {job_id}...[/]")

        # Update job with human review
        await update_job(job_id, {
            "status": JobStatus.COMPLETED.value,
            "quality_score": final_rating,
            "human_review_decision": decision,
            "human_review_rating": final_rating,
            "human_review_feedback": feedback,
            "reviewed_by": reviewer,
            "reviewed_at": datetime.utcnow(),
            "completed_at": datetime.utcnow(),
        })

        # Process payment
        escrow_txn_id = job.get("escrow_txn_id")
        agent_id = job.get("assigned_agent_id")
        agent = await get_agent(agent_id) if agent_id else None
        agreed_price = job.get("final_price_usd") or job.get("budget_usd", 0)

        payment_result = {}

        if not escrow_txn_id:
            payment_result["error"] = "No escrow found"
        elif decision == "accept":
            try:
                txn = await release_payment(
                    escrow_txn_id=escrow_txn_id,
                    payee_id=agent_id,
                    payee_wallet=agent.get("wallet_address", "") if agent else "",
                    amount_usd=agreed_price,
                )
                payment_result["status"] = "released"
                payment_result["amount"] = agreed_price

                if agent:
                    await db_update_agent(agent_id, {
                        "jobs_completed": agent.get("jobs_completed", 0) + 1,
                        "total_earned_usd": agent.get("total_earned_usd", 0) + agreed_price,
                    })
            except Exception as e:
                payment_result["error"] = str(e)

        elif decision == "partial":
            partial_amount = agreed_price * 0.5
            try:
                txn = await release_payment(
                    escrow_txn_id=escrow_txn_id,
                    payee_id=agent_id,
                    payee_wallet=agent.get("wallet_address", "") if agent else "",
                    amount_usd=partial_amount,
                )
                payment_result["status"] = "partial"
                payment_result["amount"] = partial_amount

                if agent:
                    await db_update_agent(agent_id, {
                        "jobs_completed": agent.get("jobs_completed", 0) + 1,
                        "total_earned_usd": agent.get("total_earned_usd", 0) + partial_amount,
                    })
            except Exception as e:
                payment_result["error"] = str(e)

        else:  # reject
            try:
                txn = await refund_payment(escrow_txn_id)
                payment_result["status"] = "refunded"
                payment_result["amount"] = agreed_price

                if agent:
                    await db_update_agent(agent_id, {
                        "jobs_failed": agent.get("jobs_failed", 0) + 1,
                    })
            except Exception as e:
                payment_result["error"] = str(e)

        # Update agent rating
        if agent:
            old_rating = agent.get("rating_avg", 0)
            old_count = agent.get("rating_count", 0)
            new_count = old_count + 1
            new_rating = ((old_rating * old_count) + (final_rating * 5)) / new_count
            await db_update_agent(agent_id, {
                "rating_avg": min(5.0, new_rating),
                "rating_count": new_count,
            })

        # Display result
        status_color = {"released": "green", "partial": "yellow", "refunded": "red"}.get(
            payment_result.get("status"), "white"
        )

        panel = Panel(
            f"""[bold]Job:[/] {job_id}
[bold]Decision:[/] {decision.upper()}
[bold]Rating:[/] {final_rating:.0%}
[bold]Feedback:[/] {feedback or '(none)'}

[bold]Payment Status:[/] [{status_color}]{payment_result.get('status', 'error')}[/]
[bold]Amount:[/] ${payment_result.get('amount', 0):.2f}""",
            title=f"[{status_color}]Review Submitted[/]",
        )
        console.print(panel)

        if payment_result.get("error"):
            console.print(f"[red]Payment error: {payment_result['error']}[/]")

    run_async(_submit())


# ============================================================
# Demo Command
# ============================================================

@app.command()
def demo():
    """Run the full AgentBazaar demo flow with human-in-the-loop review."""
    from .db import setup_indexes, get_job, get_agent, update_job, update_agent as db_update_agent
    from .registry import register_agent
    from .jobs import create_job
    from .jobs.match import find_matching_agents
    from .bidding import submit_bid, accept_bid, rank_bids
    from .execution import execute_job
    from .models import JobStatus
    from .payments.release import release_payment
    from datetime import datetime

    async def _demo():
        console.print(Panel.fit(
            "[bold cyan]AgentBazaar Demo[/]\n"
            "AI Agent Marketplace with Human-in-the-Loop Quality Review",
            border_style="cyan",
        ))

        # Setup
        console.print("\n[bold]Step 0: Setup[/]")
        await setup_indexes()
        console.print("[green]Database initialized[/]")

        # Register agents
        console.print("\n[bold]Step 1: Register Agents[/]")
        agents = []
        agent_configs = [
            ("AnalyzerBot", "Specializes in data analysis, pattern recognition, and insights extraction"),
            ("SummaryPro", "Expert at summarization and sentiment analysis"),
            ("DataMiner", "Focused on data extraction and classification"),
        ]

        for name, desc in agent_configs:
            with Progress(SpinnerColumn(), TextColumn(f"Registering {name}..."), console=console):
                agent = await register_agent(
                    name=name,
                    description=desc,
                    owner_id="demo_owner",
                    skip_benchmark=False,
                )
                agents.append(agent)
            console.print(f"  [green]{name}[/] - Score: {agent.capabilities.summarization:.2f}")

        # Post job
        console.print("\n[bold]Step 2: Post Job[/]")
        job = await create_job(
            poster_id="demo_poster",
            title="Analyze customer feedback patterns",
            description="Find the top 3 recurring issues in customer feedback. Summarize sentiment and provide actionable insights.",
            budget_usd=0.50,
            collection="customer_feedback",
            deadline_minutes=5,
        )
        console.print(f"  [green]Job posted:[/] {job.job_id}")
        console.print(f"  [green]Escrow created:[/] ${job.budget_usd:.2f}")

        # Match agents
        console.print("\n[bold]Step 3: Match Agents[/]")
        matched = await find_matching_agents(job.job_id)
        for m in matched[:3]:
            console.print(f"  [cyan]{m.get('name')}[/] - Match: {m.get('match_score', 0):.2f}")

        # Submit bids
        console.print("\n[bold]Step 4: Agents Submit Bids[/]")
        bids = []
        bid_configs = [
            (agents[0].agent_id, 0.35, 0.88, 120),
            (agents[1].agent_id, 0.42, 0.92, 90),
            (agents[2].agent_id, 0.28, 0.78, 180),
        ]

        for agent_id, price, conf, time_est in bid_configs:
            bid = await submit_bid(
                job_id=job.job_id,
                agent_id=agent_id,
                price_usd=price,
                estimated_time_seconds=time_est,
                confidence=conf,
                approach="Will analyze data patterns and summarize findings",
            )
            bids.append(bid)
            console.print(f"  Bid: ${price:.2f} @ {conf:.0%} confidence")

        # Rank bids
        console.print("\n[bold]Step 5: Rank Bids[/]")
        ranked = await rank_bids(job.job_id)
        for r in ranked:
            console.print(f"  #{r['rank']}: {r.get('agent_name')} - Score: {r['rank_score']:.3f}")

        # Accept best bid
        console.print("\n[bold]Step 6: Accept Best Bid[/]")
        best_bid = ranked[0]
        assignment = await accept_bid(
            job_id=job.job_id,
            bid_id=best_bid["bid_id"],
            poster_id="demo_poster",
        )
        console.print(f"  [green]Accepted:[/] {best_bid.get('agent_name')} @ ${best_bid['price_usd']:.2f}")

        # Execute job
        console.print("\n[bold]Step 7: Execute Job[/]")
        with Progress(SpinnerColumn(), TextColumn("Agent working..."), console=console):
            exec_result = await execute_job(job.job_id)

        status = exec_result.get("status")
        if status == "pending_review":
            ai_suggestion = exec_result.get("ai_quality_suggestion", {})
            suggested_score = ai_suggestion.get("suggested_overall", 0) if ai_suggestion else 0
            recommendation = ai_suggestion.get("recommendation", "N/A") if ai_suggestion else "N/A"
            summary = exec_result.get("result", {}).get("summary", "No summary")

            console.print(f"  [cyan]Work complete - pending human review[/]")
            console.print(f"  AI Suggestion: {suggested_score:.0%} ({recommendation})")
            console.print(f"  Summary: {summary[:100]}...")
        elif status == "completed":
            console.print(f"  [green]Completed![/]")
        else:
            console.print(f"  [red]Failed:[/] {exec_result.get('error')}")
            return

        # Human Review (simulated acceptance)
        console.print("\n[bold]Step 8: Human Reviews Work[/]")
        console.print("  [cyan]Reviewing AI suggestion...[/]")

        # Re-fetch job to get latest state
        job_data = await get_job(job.job_id)
        ai_suggestion = job_data.get("ai_quality_suggestion", {})

        if ai_suggestion:
            console.print(f"  AI recommends: [bold]{ai_suggestion.get('recommendation', 'N/A').upper()}[/]")
            console.print(f"  Strengths: {', '.join(ai_suggestion.get('strengths', []))}")
            if ai_suggestion.get("improvements"):
                console.print(f"  Improvements: {', '.join(ai_suggestion.get('improvements', []))}")
            if ai_suggestion.get("red_flags"):
                console.print(f"  [red]Red Flags: {', '.join(ai_suggestion.get('red_flags', []))}[/]")

        # Simulate human accepting the work
        human_decision = "accept"  # In real usage, this would be user input
        human_rating = 0.9  # Human's quality rating

        console.print(f"\n  [green]Human Decision: ACCEPT[/]")
        console.print(f"  Human Rating: {human_rating:.0%}")

        # Process the review
        await update_job(job.job_id, {
            "status": JobStatus.COMPLETED.value,
            "quality_score": human_rating,
            "human_review_decision": human_decision,
            "human_review_rating": human_rating,
            "human_review_feedback": "Good work on the analysis!",
            "reviewed_by": "demo_poster",
            "reviewed_at": datetime.utcnow(),
            "completed_at": datetime.utcnow(),
        })

        # Process payment
        console.print("\n[bold]Step 9: Process Payment (x402)[/]")
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
                console.print(f"  [green]Payment released:[/] ${agreed_price:.2f}")

                # Update agent stats
                await db_update_agent(agent_id, {
                    "jobs_completed": agent.get("jobs_completed", 0) + 1,
                    "total_earned_usd": agent.get("total_earned_usd", 0) + agreed_price,
                })
            except Exception as e:
                console.print(f"  [red]Payment error:[/] {e}")
        else:
            console.print(f"  [yellow]No escrow to release (simulated mode)[/]")

        # Summary
        console.print("\n" + "=" * 50)
        console.print(Panel.fit(
            f"[bold green]Demo Complete![/]\n\n"
            f"Registered [cyan]{len(agents)}[/] agents\n"
            f"Posted [cyan]1[/] job with [cyan]${job.budget_usd:.2f}[/] escrow\n"
            f"Received [cyan]{len(bids)}[/] bids\n"
            f"Winner: [cyan]{best_bid.get('agent_name')}[/]\n"
            f"AI Suggested: [cyan]{ai_suggestion.get('suggested_overall', 0):.0%}[/] ({ai_suggestion.get('recommendation', 'N/A')})\n"
            f"Human Rating: [cyan]{human_rating:.0%}[/]\n"
            f"Human Decision: [green]ACCEPT[/]\n"
            f"Payment: [green]${agreed_price:.2f}[/]",
            title="Summary",
            border_style="green",
        ))

    run_async(_demo())


if __name__ == "__main__":
    app()
