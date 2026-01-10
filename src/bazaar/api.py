"""AgentBazaar API with Thesys Generative UI integration.

This combines the marketplace backend with Thesys C1 for dynamic UI generation.
"""

import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import structlog

from openai import OpenAI
from thesys_genui_sdk.fast_api import with_c1_response
from thesys_genui_sdk.context import get_assistant_message, write_content
from dotenv import load_dotenv

from .db import (
    init_db,
    get_all_agents,
    get_agent,
    get_all_jobs,
    get_job,
    get_bids_for_job,
    get_transaction,
    create_job as db_create_job,
    update_job,
)
from .models import BazaarJob, JobStatus, TransactionStatus
from .jobs.match import match_agents_to_job
from .bidding.submit import submit_bid, select_winning_bid
from .bidding.negotiate import (
    make_counter_offer,
    accept_counter_offer,
    approve_bid,
    reject_bid,
    auto_negotiate,
    get_pending_approvals,
)
from .execution.runner import execute_job
from .payments.escrow import create_escrow
from .payments.release import process_job_payment
from .payments.refund import refund_payment

load_dotenv()
logger = structlog.get_logger()

# Mock data for development when MongoDB is unavailable
MOCK_AGENTS = [
    {
        "agent_id": "agent_alpha_001",
        "name": "DataAnalyzer Pro",
        "description": "Specialized in data extraction, sentiment analysis, and pattern recognition. High accuracy with structured data processing.",
        "capabilities": {"data_extraction": 0.95, "sentiment_analysis": 0.88, "pattern_recognition": 0.92, "summarization": 0.85},
        "rating_avg": 4.8,
        "rating_count": 127,
        "jobs_completed": 156,
        "jobs_failed": 3,
        "base_rate_usd": 2.50,
        "status": "available",
        "total_earned_usd": 1250.00,
    },
    {
        "agent_id": "agent_beta_002",
        "name": "CodeReview Assistant",
        "description": "Expert code reviewer with deep understanding of security vulnerabilities and best practices across multiple languages.",
        "capabilities": {"code_review": 0.94, "pattern_recognition": 0.89, "classification": 0.86, "anomaly_detection": 0.91},
        "rating_avg": 4.6,
        "rating_count": 89,
        "jobs_completed": 98,
        "jobs_failed": 5,
        "base_rate_usd": 3.00,
        "status": "available",
        "total_earned_usd": 890.00,
    },
    {
        "agent_id": "agent_gamma_003",
        "name": "ContentSummarizer",
        "description": "Fast and accurate document summarization with support for multiple languages and content types.",
        "capabilities": {"summarization": 0.96, "aggregation": 0.90, "classification": 0.84, "data_extraction": 0.82},
        "rating_avg": 4.9,
        "rating_count": 203,
        "jobs_completed": 245,
        "jobs_failed": 2,
        "base_rate_usd": 1.75,
        "status": "busy",
        "total_earned_usd": 2100.00,
    },
]

MOCK_JOBS = [
    {
        "job_id": "job_abc123",
        "title": "Analyze Q4 Sales Report",
        "description": "Extract key metrics, trends, and insights from the quarterly sales data. Identify top performing products and regions.",
        "budget_usd": 15.00,
        "status": "posted",
        "required_capabilities": ["data_extraction", "pattern_recognition", "summarization"],
        "poster_id": "user_demo",
        "created_at": "2026-01-10T10:00:00Z",
    },
    {
        "job_id": "job_def456",
        "title": "Security Code Review for Auth Module",
        "description": "Review the authentication module for potential security vulnerabilities and suggest improvements.",
        "budget_usd": 25.00,
        "status": "bidding",
        "required_capabilities": ["code_review", "anomaly_detection"],
        "poster_id": "user_enterprise",
        "created_at": "2026-01-10T09:30:00Z",
    },
    {
        "job_id": "job_ghi789",
        "title": "Summarize Research Papers",
        "description": "Summarize 10 academic papers on machine learning optimization techniques. Need concise abstracts and key findings.",
        "budget_usd": 8.00,
        "status": "in_progress",
        "required_capabilities": ["summarization", "aggregation"],
        "poster_id": "user_researcher",
        "assigned_agent_id": "agent_gamma_003",
        "created_at": "2026-01-10T08:00:00Z",
    },
]

USE_MOCK_DATA = False  # Will be set True if MongoDB connection fails

app = FastAPI(
    title="Open Agora",
    description="AI Agent Marketplace with x402 Payments and Generative UI",
    version="0.1.0",
)

# Serve static UI files (built React app)
UI_DIST_PATH = Path(__file__).parent.parent.parent / "ui" / "dist"
if UI_DIST_PATH.exists():
    app.mount("/assets", StaticFiles(directory=UI_DIST_PATH / "assets"), name="assets")

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Thesys C1 client
thesys_client = OpenAI(
    api_key=os.getenv("THESYS_API_KEY"),
    base_url="https://api.thesys.dev/v1/embed",
)

# Thread storage for conversation history
thread_store: Dict[str, List[Dict]] = {}


# ============================================================
# Request/Response Models
# ============================================================

class Prompt(BaseModel):
    role: str
    content: str
    id: str


class ChatRequest(BaseModel):
    prompt: Prompt
    threadId: str
    responseId: str

    class Config:
        extra = "allow"


class JobCreateRequest(BaseModel):
    title: str
    description: str
    required_capabilities: List[str]
    budget_usd: float
    poster_id: str
    poster_wallet: str


# ============================================================
# Marketplace REST Endpoints
# ============================================================

@app.on_event("startup")
async def startup():
    global USE_MOCK_DATA
    try:
        await init_db()
        # Test the connection by trying to list agents
        await get_all_agents()
        logger.info("agentbazaar_api_started", mode="database")
    except Exception as e:
        logger.warning("mongodb_unavailable", error=str(e)[:100], mode="mock_data")
        USE_MOCK_DATA = True
        logger.info("agentbazaar_api_started", mode="mock_data")


@app.get("/")
def root():
    """Serve the React UI or API info."""
    index_path = UI_DIST_PATH / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {
        "name": "Open Agora",
        "version": "0.1.0",
        "status": "operational",
        "features": ["x402_payments", "generative_ui", "agent_matching"],
    }


@app.get("/api/agents")
async def list_agents():
    """Get all registered agents."""
    if USE_MOCK_DATA:
        return {"agents": MOCK_AGENTS, "count": len(MOCK_AGENTS)}
    agents = await get_all_agents()
    return {"agents": agents, "count": len(agents)}


@app.get("/api/agents/{agent_id}")
async def get_agent_details(agent_id: str):
    """Get details for a specific agent."""
    if USE_MOCK_DATA:
        agent = next((a for a in MOCK_AGENTS if a["agent_id"] == agent_id), None)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        return agent
    agent = await get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@app.get("/api/jobs")
async def list_jobs(status: Optional[str] = None):
    """Get all jobs, optionally filtered by status."""
    if USE_MOCK_DATA:
        jobs = MOCK_JOBS
        if status:
            jobs = [j for j in jobs if j.get("status") == status]
        return {"jobs": jobs, "count": len(jobs)}
    jobs = await get_all_jobs()
    if status:
        jobs = [j for j in jobs if j.get("status") == status]
    return {"jobs": jobs, "count": len(jobs)}


@app.get("/api/jobs/{job_id}")
async def get_job_details(job_id: str):
    """Get details for a specific job."""
    if USE_MOCK_DATA:
        job = next((j for j in MOCK_JOBS if j["job_id"] == job_id), None)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        job["bids"] = []
        return job
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Include bids
    bids = await get_bids_for_job(job_id)
    job["bids"] = bids

    return job


@app.post("/api/jobs")
async def create_job(request: JobCreateRequest):
    """Create a new job and escrow payment."""
    job_id = f"job_{uuid.uuid4().hex[:8]}"

    if USE_MOCK_DATA:
        # In mock mode, just add to the in-memory list
        new_job = {
            "job_id": job_id,
            "title": request.title,
            "description": request.description,
            "budget_usd": request.budget_usd,
            "status": "posted",
            "required_capabilities": request.required_capabilities,
            "poster_id": request.poster_id,
            "created_at": datetime.utcnow().isoformat() + "Z",
        }
        MOCK_JOBS.insert(0, new_job)
        logger.info("job_created", job_id=job_id, mode="mock_data")
        return {"job_id": job_id, "status": "posted", "message": "Job created (mock mode)"}

    job = BazaarJob(
        job_id=job_id,
        title=request.title,
        description=request.description,
        required_capabilities=request.required_capabilities,
        budget_usd=request.budget_usd,
        poster_id=request.poster_id,
        poster_wallet=request.poster_wallet,
        status=JobStatus.POSTED,
        created_at=datetime.utcnow(),
    )

    await db_create_job(job.model_dump())

    # Create escrow
    escrow_txn = await create_escrow(
        job_id=job_id,
        payer_id=request.poster_id,
        payer_wallet=request.poster_wallet,
        amount_usd=request.budget_usd,
    )

    # Update job with escrow reference
    await update_job(job_id, {"escrow_txn_id": escrow_txn.txn_id})

    # Match agents
    matched_agents = await match_agents_to_job(job)

    logger.info(
        "job_created",
        job_id=job_id,
        budget=request.budget_usd,
        matched_agents=len(matched_agents),
    )

    return {
        "job_id": job_id,
        "escrow_txn_id": escrow_txn.txn_id,
        "matched_agents": [a["agent_id"] for a in matched_agents],
        "status": "posted",
    }


@app.post("/api/jobs/{job_id}/bids")
async def place_bid(
    job_id: str,
    agent_id: str,
    price_usd: float,
    estimated_quality: float,
    estimated_time_seconds: int,
    approach_summary: str,
):
    """Submit a bid for a job."""
    bid = await submit_bid(
        job_id=job_id,
        agent_id=agent_id,
        price_usd=price_usd,
        estimated_quality=estimated_quality,
        estimated_time_seconds=estimated_time_seconds,
        approach_summary=approach_summary,
    )
    return {"bid_id": bid.bid_id, "status": "submitted"}


@app.post("/api/jobs/{job_id}/select-bid/{bid_id}")
async def select_bid(job_id: str, bid_id: str):
    """Select winning bid for a job."""
    job = await select_winning_bid(job_id, bid_id)
    return {"job_id": job_id, "winning_bid_id": bid_id, "status": job["status"]}


@app.post("/api/jobs/{job_id}/execute")
async def execute_job_endpoint(job_id: str):
    """Execute the job with assigned agent."""
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    result = await execute_job(job_id)
    return result


@app.post("/api/jobs/{job_id}/complete")
async def complete_job(job_id: str, quality_score: float):
    """Complete job and process payment based on quality."""
    await update_job(job_id, {
        "status": JobStatus.COMPLETED.value,
        "quality_score": quality_score,
        "completed_at": datetime.utcnow(),
    })

    payment_result = await process_job_payment(job_id)
    return payment_result


@app.get("/api/transactions/{txn_id}")
async def get_transaction_details(txn_id: str):
    """Get transaction details."""
    txn = await get_transaction(txn_id)
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return txn


# ============================================================
# Negotiation Endpoints
# ============================================================

class CounterOfferRequest(BaseModel):
    new_price: float
    message: str
    by: str  # "poster" or "agent"


class AutoNegotiateRequest(BaseModel):
    max_budget: float
    negotiator_role: str = "poster"


@app.post("/api/bids/{bid_id}/counter")
async def counter_offer_endpoint(bid_id: str, request: CounterOfferRequest):
    """Make a counter-offer on a bid."""
    try:
        bid = await make_counter_offer(
            bid_id=bid_id,
            new_price=request.new_price,
            message=request.message,
            by=request.by,
        )
        return {
            "bid_id": bid_id,
            "status": bid["status"],
            "counter_offers": bid.get("counter_offers", []),
            "requires_approval": bid.get("requires_approval", False),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/bids/{bid_id}/accept-counter")
async def accept_counter_endpoint(bid_id: str, by: str = "poster"):
    """Accept the latest counter-offer."""
    try:
        bid = await accept_counter_offer(bid_id, by)
        return {
            "bid_id": bid_id,
            "status": bid["status"],
            "final_price": bid.get("final_price_usd"),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/bids/{bid_id}/approve")
async def approve_bid_endpoint(bid_id: str, approver_id: str):
    """Human approval for high-value bids."""
    try:
        bid = await approve_bid(bid_id, approver_id)
        return {
            "bid_id": bid_id,
            "status": "approved",
            "approved_by": approver_id,
            "final_price": bid.get("final_price_usd"),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/bids/{bid_id}/reject")
async def reject_bid_endpoint(bid_id: str, rejector_id: str, reason: str = ""):
    """Reject a bid."""
    try:
        bid = await reject_bid(bid_id, rejector_id, reason)
        return {"bid_id": bid_id, "status": "rejected"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/bids/{bid_id}/auto-negotiate")
async def auto_negotiate_endpoint(bid_id: str, request: AutoNegotiateRequest):
    """Use AI to automatically negotiate."""
    try:
        bid = await auto_negotiate(
            bid_id=bid_id,
            max_budget=request.max_budget,
            negotiator_role=request.negotiator_role,
        )
        if bid:
            return {
                "bid_id": bid_id,
                "status": bid["status"],
                "counter_offers": bid.get("counter_offers", []),
                "final_price": bid.get("final_price_usd"),
            }
        return {"bid_id": bid_id, "status": "no_action"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/approvals/pending")
async def list_pending_approvals():
    """Get all bids awaiting human approval."""
    bids = await get_pending_approvals()
    return {"pending_approvals": bids, "count": len(bids)}


# ============================================================
# Refund Endpoints
# ============================================================

@app.post("/api/jobs/{job_id}/refund")
async def refund_job_endpoint(job_id: str):
    """Refund escrowed payment for a failed/cancelled job."""
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    escrow_txn_id = job.get("escrow_txn_id")
    if not escrow_txn_id:
        raise HTTPException(status_code=400, detail="No escrow found for job")

    refund_txn = await refund_payment(escrow_txn_id)
    if not refund_txn:
        raise HTTPException(status_code=400, detail="Refund failed")

    await update_job(job_id, {"status": JobStatus.CANCELLED.value})

    return {
        "job_id": job_id,
        "status": "refunded",
        "refund_txn_id": refund_txn.txn_id,
        "amount": refund_txn.amount_usd,
    }


# ============================================================
# Thesys Generative UI Endpoint
# ============================================================

SYSTEM_PROMPT = """You are the AgentBazaar assistant, helping users interact with an AI agent marketplace.

The marketplace allows:
1. Posting jobs that AI agents can bid on
2. Browsing available AI agents with verified capabilities
3. Viewing agent bids with price, quality, and time estimates
4. Negotiating prices with counter-offers between posters and agents
5. Human-in-the-loop approval for high-value transactions (>$10)
6. Executing jobs and tracking results
7. Processing payments via x402 protocol (USDC on Base network)
8. Automatic refunds for failed or low-quality jobs

Key Features:
- NEGOTIATION: Posters can counter-bid on agent prices. Agents can accept/reject/counter.
  After multiple rounds, a final price is agreed upon.
- HUMAN APPROVAL: Transactions over $10 require human approval before execution.
- QUALITY GATES: Jobs are evaluated for quality before payment release.
- REFUNDS: If quality is below threshold, funds are automatically refunded to poster.

When users interact with you, generate rich, interactive UI components:
- Agent cards with capabilities, ratings, verified scores, and pricing
- Job listings with status indicators (posted, negotiating, awaiting approval, in progress)
- Bid comparison tables with negotiation history
- Payment flow visualizations with x402 transaction details
- Approval queues for human-in-the-loop decisions
- Forms for posting jobs and making counter-offers

Use modern, visually appealing layouts with cards, tables, progress indicators, and status badges.
Include action buttons: "Post Job", "View Bids", "Counter Offer", "Approve", "Execute", "View Payment".

The marketplace uses USDC on Base network for all payments via the x402 protocol.
"""


@app.post("/chat")
@with_c1_response()
async def chat_endpoint(request: ChatRequest):
    """Thesys Generative UI chat endpoint."""
    thread_id = request.threadId

    # Get or create conversation history
    if thread_id not in thread_store:
        thread_store[thread_id] = [{"role": "system", "content": SYSTEM_PROMPT}]

    conversation = thread_store[thread_id]
    conversation.append({"role": "user", "content": request.prompt.content})

    # Fetch current marketplace context
    agents = await get_all_agents()
    jobs = await get_all_jobs()

    # Inject marketplace context
    context_message = f"""
Current marketplace state:
- {len(agents)} registered agents
- {len(jobs)} active jobs
- Top agents: {', '.join([a.get('name', a['agent_id']) for a in agents[:3]])}

Recent jobs: {[j.get('title', j['job_id']) for j in jobs[:3]]}
"""

    messages_with_context = conversation.copy()
    messages_with_context.insert(1, {"role": "system", "content": context_message})

    # Stream response from Thesys C1
    stream = thesys_client.chat.completions.create(
        messages=messages_with_context,
        model="c1/anthropic/claude-sonnet-4/v-20250815",
        stream=True,
    )

    assistant_message = None
    for chunk in stream:
        delta = chunk.choices[0].delta
        finish_reason = chunk.choices[0].finish_reason

        if delta and delta.content:
            await write_content(delta.content)

        if finish_reason:
            assistant_message = get_assistant_message()

    # Store assistant response
    if assistant_message:
        conversation.append(assistant_message)
        thread_store[thread_id] = conversation

    logger.info("chat_completed", thread_id=thread_id)


# ============================================================
# Full-Page Generation Endpoint
# ============================================================

PAGE_GENERATION_PROMPT = """You are the AgentBazaar page generator. Your job is to generate complete, interactive marketplace pages using custom React components.

AVAILABLE CUSTOM COMPONENTS:

1. <NavigationHeader current_page="..." pending_approvals_count={N} />
   - Navigation bar with marketplace branding
   - current_page: "home" | "agents_list" | "jobs_list" | "approvals" | "transaction_history"

2. <MarketplaceStats total_agents={N} total_jobs={N} total_volume={N} active_jobs={N} />
   - Dashboard statistics grid

3. <AgentCard agent_id="..." name="..." description="..." capabilities={[{name, score}]} rating={N} jobs_completed={N} base_rate={N} status="available|busy|offline" />
   - Display an AI agent with hire button

4. <JobCard job_id="..." title="..." description="..." budget={N} status="posted|assigned|in_progress|completed" capabilities={[...]} quality_score={N} assigned_agent="..." />
   - Display a job listing with action buttons

5. <BidCard bid_id="..." job_id="..." agent_id="..." agent_name="..." price_usd={N} confidence={N} approach="..." status="pending|counter_offered|accepted" counter_offers={[...]} />
   - Display a bid with negotiation actions

6. <NegotiationPanel bid={...} job_title="..." original_budget={N} negotiation_history={[...]} can_counter={bool} can_approve={bool} can_accept={bool} />
   - Full negotiation interface

7. <ApprovalQueue pending_approvals={[{bid_id, job_title, agent_name, price_usd, approval_reason}]} />
   - Human-in-the-loop approval dashboard

8. <PostJobForm initial_title="..." suggested_budget={N} preselected_agent_id="..." preselected_agent_name="..." />
   - Job creation form

9. <TransactionDetails txn_id="..." txn_type="escrow|release|refund" job_id="..." amount_usd={N} status="..." payer_wallet="..." payee_wallet="..." />
   - x402 transaction visualization

PAGE GENERATION RULES:
1. Start with <NavigationHeader> showing the current page
2. Include <MarketplaceStats> on main pages (home, agents_list, jobs_list)
3. Use grid layouts for lists (e.g., "grid grid-cols-3 gap-4")
4. Generate components with REAL DATA from the context provided
5. Include appropriate action buttons on each component
6. For detail pages, show comprehensive information

NAVIGATION ACTIONS (these trigger page changes):
- User says "View Agents" or clicks agents nav -> Generate agents_list page
- User says "View Jobs" or clicks jobs nav -> Generate jobs_list page
- User says "View Job {id}" or clicks a job -> Generate job_detail page with bids
- User says "Post Job" -> Generate page with <PostJobForm />
- User says "Hire Agent {id}" -> Generate <PostJobForm preselected_agent_id="..." />
- User says "Negotiate {bid_id}" -> Generate page with <NegotiationPanel />
- User says "View Approvals" -> Generate page with <ApprovalQueue />
- User says "View Transactions" -> Generate transaction_history page

IMPORTANT:
- Generate complete, visually rich pages with real marketplace data
- Use the custom components - do NOT generate raw HTML/JSX
- Every page should feel like a polished web application
- Include helpful empty states when there's no data
- Use the component props exactly as documented above
"""

# Separate thread store for page generation
page_thread_store: Dict[str, List[Dict]] = {}


@app.post("/page")
@with_c1_response()
async def page_generation_endpoint(request: ChatRequest):
    """Full-page generation endpoint for Thesys C1."""
    from .component_schemas import get_component_schemas
    import json

    thread_id = request.threadId

    # Initialize with page generation prompt
    if thread_id not in page_thread_store:
        page_thread_store[thread_id] = [
            {"role": "system", "content": PAGE_GENERATION_PROMPT}
        ]

    conversation = page_thread_store[thread_id]
    user_message = request.prompt.content
    conversation.append({"role": "user", "content": user_message})

    # Fetch comprehensive marketplace context
    agents = await get_all_agents()
    jobs = await get_all_jobs()
    pending_approvals = await get_pending_approvals()

    # Calculate stats
    total_volume = sum(a.get("total_earned_usd", 0) for a in agents)
    active_jobs = len([j for j in jobs if j.get("status") in ["posted", "assigned", "in_progress", "bidding", "negotiating"]])
    available_agents = len([a for a in agents if a.get("status") == "available"])

    # Format agents for context
    agents_context = []
    for a in agents[:10]:
        caps = a.get("capabilities", {})
        if isinstance(caps, dict):
            caps_list = [{"name": k, "score": v} for k, v in caps.items()]
        else:
            caps_list = caps
        agents_context.append({
            "agent_id": a.get("agent_id"),
            "name": a.get("name", a.get("agent_id")),
            "description": a.get("description", ""),
            "capabilities": caps_list[:4] if caps_list else [],
            "rating": a.get("rating_avg", 0),
            "jobs_completed": a.get("jobs_completed", 0),
            "base_rate": a.get("base_rate_usd", 0),
            "status": a.get("status", "available"),
            "total_earned": a.get("total_earned_usd", 0),
        })

    # Format jobs for context
    jobs_context = []
    for j in jobs[:10]:
        jobs_context.append({
            "job_id": j.get("job_id"),
            "title": j.get("title", "Untitled"),
            "description": j.get("description", "")[:200],
            "budget": j.get("budget_usd", 0),
            "status": j.get("status", "posted"),
            "capabilities": j.get("required_capabilities", []),
            "quality_score": j.get("quality_score"),
            "assigned_agent_id": j.get("assigned_agent_id"),
        })

    # Format pending approvals
    approvals_context = []
    for approval in pending_approvals:
        approvals_context.append({
            "bid_id": approval.get("bid_id"),
            "job_id": approval.get("job_id"),
            "job_title": approval.get("job_title", "Unknown Job"),
            "agent_id": approval.get("agent_id"),
            "agent_name": approval.get("agent_name", "Unknown Agent"),
            "price_usd": approval.get("final_price_usd") or approval.get("price_usd", 0),
            "approval_reason": "Amount exceeds $10",
        })

    # Build rich context
    context_message = f"""
CURRENT MARKETPLACE STATE:
- Total Agents: {len(agents)} ({available_agents} available)
- Total Jobs: {len(jobs)} ({active_jobs} active)
- Total Volume: ${total_volume:.2f} USD
- Pending Approvals: {len(pending_approvals)}

MARKETPLACE STATS FOR <MarketplaceStats>:
total_agents={len(agents)}, total_jobs={len(jobs)}, total_volume={total_volume:.2f}, active_jobs={active_jobs}

AGENTS DATA (use for <AgentCard> components):
{json.dumps(agents_context, indent=2)}

JOBS DATA (use for <JobCard> components):
{json.dumps(jobs_context, indent=2)}

PENDING APPROVALS (use for <ApprovalQueue>):
{json.dumps(approvals_context, indent=2)}
"""

    messages_with_context = conversation.copy()
    messages_with_context.insert(1, {"role": "system", "content": context_message})

    # Stream from Thesys C1 with component schemas
    try:
        stream = thesys_client.chat.completions.create(
            messages=messages_with_context,
            model="c1/anthropic/claude-sonnet-4/v-20250815",
            stream=True,
            extra_body={
                "metadata": {
                    "thesys": {
                        "c1_custom_components": get_component_schemas()
                    }
                }
            }
        )

        assistant_message = None
        for chunk in stream:
            delta = chunk.choices[0].delta
            finish_reason = chunk.choices[0].finish_reason

            if delta and delta.content:
                await write_content(delta.content)

            if finish_reason:
                assistant_message = get_assistant_message()

        # Store assistant response
        if assistant_message:
            conversation.append(assistant_message)
            page_thread_store[thread_id] = conversation

        logger.info("page_generation_completed", thread_id=thread_id)

    except Exception as e:
        logger.error("page_generation_error", error=str(e), thread_id=thread_id)
        await write_content(f"Error generating page: {str(e)}")


# ============================================================
# Demo/Debug Endpoints
# ============================================================

@app.get("/api/demo/status")
async def demo_status():
    """Get demo system status."""
    agents = await get_all_agents()
    jobs = await get_all_jobs()

    return {
        "status": "operational",
        "agents_count": len(agents),
        "jobs_count": len(jobs),
        "x402_mode": os.getenv("USE_REAL_X402", "false"),
        "thesys_configured": bool(os.getenv("THESYS_API_KEY")),
    }
