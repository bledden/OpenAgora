"""AgentBazaar API with Thesys Generative UI integration.

This combines the marketplace backend with Thesys C1 for dynamic UI generation.
"""

import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
import structlog
import httpx

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
    update_agent as db_update_agent,
    delete_agent as db_delete_agent,
    get_stale_agents,
    cancel_pending_bids_by_agent,
)
from .registry.register import register_agent as do_register_agent
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
from .auth import (
    create_challenge,
    verify_signature,
    create_session,
    verify_session,
    invalidate_session,
    get_current_agent,
    require_auth,
    require_agent_owner,
    require_job_poster,
    require_bid_poster,
    AuthenticatedAgent,
    cleanup_expired,
)
from .webhooks import notify_agents_of_job, notify_bid_selected
from .files import (
    save_upload,
    get_file_path,
    delete_file,
    is_allowed_file,
    get_file_category,
    format_file_size,
    JobAttachment,
    ExportFormat,
    export_result_as_json,
    export_result_as_csv,
    export_result_as_markdown,
    export_result_as_text,
    MAX_FILE_SIZE_MB,
    MAX_FILES_PER_JOB,
    ALLOWED_EXTENSIONS,
    FileCategory,
)

load_dotenv()
logger = structlog.get_logger()

app = FastAPI(
    title="Open Agora",
    description="AI Agent Marketplace with x402 Payments and Generative UI",
    version="0.1.0",
)

# Serve static UI files (built React app)
# On Railway, the app is at /app, so check both locations
UI_DIST_PATH = Path(__file__).parent.parent.parent / "ui" / "dist"
if not UI_DIST_PATH.exists():
    UI_DIST_PATH = Path("/app/ui/dist")

# Only mount assets if both dist and assets directories exist
if UI_DIST_PATH.exists() and (UI_DIST_PATH / "assets").exists():
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


class AgentRegisterRequest(BaseModel):
    """Request to register a new agent on the marketplace."""
    name: str
    description: str
    owner_id: str  # Owner's wallet or identifier
    wallet_address: str  # x402 payment address for receiving payments

    # Execution mode: self_hosted (agent polls), webhook (we call you), hosted (we run LLM)
    execution_mode: str = "self_hosted"
    webhook_url: Optional[str] = None  # Required if execution_mode == "webhook"

    # Only needed for hosted execution
    provider: str = "fireworks"  # LLM provider: fireworks, nvidia, openai
    model: Optional[str] = None  # Model identifier (defaults by provider)

    # Pricing
    base_rate_usd: float = 0.01  # Minimum price per task
    rate_per_1k_tokens: float = 0.001  # Token-based pricing

    # Optional
    capabilities: Optional[Dict[str, float]] = None  # Optional capability scores
    skip_benchmark: bool = False  # Skip benchmark (for testing only)


class AgentUpdateRequest(BaseModel):
    """Request to update agent settings."""
    name: Optional[str] = None
    description: Optional[str] = None
    base_rate_usd: Optional[float] = None
    rate_per_1k_tokens: Optional[float] = None
    status: Optional[str] = None  # available, busy, offline
    webhook_url: Optional[str] = None


class AgentHeartbeatRequest(BaseModel):
    """Agent heartbeat to signal availability."""
    status: str = "available"  # available, busy, offline
    current_capacity: int = 1  # How many concurrent jobs agent can handle
    metadata: Optional[Dict[str, Any]] = None  # Custom metadata


class AuthVerifyRequest(BaseModel):
    """Request to verify a wallet signature."""
    wallet: str
    signature: str
    nonce: str


# Rate limiting for registration (simple in-memory, per owner)
_registration_cooldowns: Dict[str, datetime] = {}
REGISTRATION_COOLDOWN_SECONDS = 10  # 10 seconds between registrations per owner


# ============================================================
# Authentication Endpoints
# ============================================================

@app.get("/api/auth/challenge")
async def get_auth_challenge(wallet: str):
    """Get a challenge to sign for authentication.

    The client should sign the returned message/typed_data with their wallet,
    then call /api/auth/verify with the signature.
    """
    if not wallet or len(wallet) != 42 or not wallet.startswith("0x"):
        raise HTTPException(status_code=400, detail="Invalid wallet address")

    challenge = create_challenge(wallet)
    return challenge


@app.post("/api/auth/verify")
async def verify_auth(request: AuthVerifyRequest):
    """Verify a wallet signature and get a session token.

    After getting a challenge from /api/auth/challenge, sign it and
    submit the signature here to get a session token.
    """
    if not verify_signature(request.wallet, request.signature, request.nonce):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Look up if this wallet owns an agent
    agent_id = None
    agents = await get_all_agents()
    for agent in agents:
        if agent.get("wallet_address", "").lower() == request.wallet.lower():
            agent_id = agent.get("agent_id")
            break
        if agent.get("owner_id", "").lower() == request.wallet.lower():
            agent_id = agent.get("agent_id")
            break

    session_token = create_session(request.wallet, agent_id)

    return {
        "success": True,
        "session_token": session_token,
        "wallet": request.wallet.lower(),
        "agent_id": agent_id,
        "message": "Authentication successful. Include token in Authorization header as: Bearer <token>",
    }


@app.post("/api/auth/logout")
async def logout(auth: AuthenticatedAgent = Depends(require_auth)):
    """Invalidate the current session."""
    if auth.session_token:
        invalidate_session(auth.session_token)
    return {"success": True, "message": "Logged out"}


@app.get("/api/auth/me")
async def get_current_user(auth: AuthenticatedAgent = Depends(require_auth)):
    """Get the current authenticated user/agent."""
    result = {
        "wallet": auth.wallet,
        "agent_id": auth.agent_id,
        "authenticated": True,
    }

    # If they own an agent, include agent details
    if auth.agent_id:
        agent = await get_agent(auth.agent_id)
        if agent:
            result["agent"] = agent

    return result


# ============================================================
# Marketplace REST Endpoints
# ============================================================

# Background task for stale agent cleanup
_cleanup_task = None

async def cleanup_stale_agents_loop():
    """Background task that marks stale agents as offline and cancels their bids."""
    import asyncio
    STALE_THRESHOLD_MINUTES = 5
    CHECK_INTERVAL_SECONDS = 60

    while True:
        try:
            stale_agents = await get_stale_agents(STALE_THRESHOLD_MINUTES)

            for agent in stale_agents:
                agent_id = agent.get("agent_id")
                logger.info("marking_agent_offline", agent_id=agent_id, last_active=agent.get("last_active"))

                # Mark agent as offline
                await db_update_agent(agent_id, {"status": "offline"})

                # Cancel all pending bids from this agent
                cancelled_count = await cancel_pending_bids_by_agent(agent_id)
                if cancelled_count > 0:
                    logger.info("cancelled_stale_bids", agent_id=agent_id, count=cancelled_count)

        except Exception as e:
            logger.error("stale_agent_cleanup_error", error=str(e))

        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


@app.on_event("startup")
async def startup():
    import asyncio
    global _cleanup_task
    await init_db()
    # Start background cleanup task
    _cleanup_task = asyncio.create_task(cleanup_stale_agents_loop())
    logger.info("agentbazaar_api_started", stale_agent_cleanup="enabled")


@app.on_event("shutdown")
async def shutdown():
    global _cleanup_task
    if _cleanup_task:
        _cleanup_task.cancel()
        try:
            await _cleanup_task
        except asyncio.CancelledError:
            pass
    logger.info("agentbazaar_api_stopped")


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


# SPA fallback routes - serve index.html for client-side routing
@app.get("/agents")
@app.get("/jobs")
@app.get("/reviews")
def spa_fallback():
    """Serve React app for SPA routes."""
    index_path = UI_DIST_PATH / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"error": "UI not built"}


@app.get("/api/agents")
async def list_agents():
    """Get all registered agents."""
    agents = await get_all_agents()
    return {"agents": agents, "count": len(agents)}


@app.get("/api/agents/{agent_id}")
async def get_agent_details(agent_id: str):
    """Get details for a specific agent."""
    agent = await get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@app.post("/api/agents/register")
async def register_agent(request: AgentRegisterRequest):
    """Register a new agent on the marketplace.

    Execution modes:
    - self_hosted: Agent polls for assigned jobs and submits results
    - webhook: OpenAgora POSTs jobs to your webhook_url, you return results
    - hosted: OpenAgora executes using your LLM config (requires provider/model)

    For self_hosted and webhook modes, benchmarking is skipped.
    Rate limited to 1 registration per owner per 5 minutes.
    """
    # Validate execution mode
    valid_modes = ["self_hosted", "webhook", "hosted"]
    if request.execution_mode not in valid_modes:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid execution_mode. Must be one of: {valid_modes}"
        )

    # Validate webhook URL for webhook mode
    if request.execution_mode == "webhook" and not request.webhook_url:
        raise HTTPException(
            status_code=400,
            detail="webhook_url is required when execution_mode is 'webhook'"
        )

    # Rate limiting check
    now = datetime.utcnow()
    last_registration = _registration_cooldowns.get(request.owner_id)
    if last_registration:
        elapsed = (now - last_registration).total_seconds()
        if elapsed < REGISTRATION_COOLDOWN_SECONDS:
            remaining = int(REGISTRATION_COOLDOWN_SECONDS - elapsed)
            raise HTTPException(
                status_code=429,
                detail=f"Rate limited. Please wait {remaining} seconds before registering another agent."
            )

    # Skip benchmark for self_hosted and webhook modes
    skip_benchmark = request.skip_benchmark or request.execution_mode in ["self_hosted", "webhook"]

    try:
        agent = await do_register_agent(
            name=request.name,
            description=request.description,
            owner_id=request.owner_id,
            provider=request.provider,
            model=request.model,
            wallet_address=request.wallet_address,
            base_rate_usd=request.base_rate_usd,
            rate_per_1k_tokens=request.rate_per_1k_tokens,
            skip_benchmark=skip_benchmark,
        )

        # Update cooldown
        _registration_cooldowns[request.owner_id] = now

        # Store execution mode and webhook URL
        updates = {"execution_mode": request.execution_mode}
        if request.webhook_url:
            updates["webhook_url"] = request.webhook_url
        if request.capabilities:
            updates["capabilities"] = request.capabilities
        await db_update_agent(agent.agent_id, updates)

        logger.info(
            "agent_registered_via_api",
            agent_id=agent.agent_id,
            name=agent.name,
            owner_id=request.owner_id,
            execution_mode=request.execution_mode,
        )

        return {
            "success": True,
            "agent_id": agent.agent_id,
            "name": agent.name,
            "execution_mode": request.execution_mode,
            "status": agent.status.value if hasattr(agent.status, 'value') else agent.status,
            "wallet_address": request.wallet_address,
            "message": f"Agent registered with {request.execution_mode} execution mode.",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("agent_registration_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")


@app.put("/api/agents/{agent_id}")
async def update_agent(
    agent_id: str,
    request: AgentUpdateRequest,
    auth: Optional[AuthenticatedAgent] = Depends(get_current_agent),
):
    """Update agent settings.

    Allows agents to update their name, description, pricing, status, and webhook URL.
    Requires authentication - caller must own the agent.
    """
    # Verify agent exists
    agent = await get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Verify ownership (if auth is enabled)
    if auth:
        owner_id = agent.get("owner_id", "").lower()
        wallet_address = agent.get("wallet_address", "").lower()
        if auth.wallet.lower() not in [owner_id, wallet_address]:
            raise HTTPException(status_code=403, detail="You don't own this agent")

    # Build update dict from non-None fields
    updates = {}
    if request.name is not None:
        updates["name"] = request.name
    if request.description is not None:
        updates["description"] = request.description
    if request.base_rate_usd is not None:
        updates["base_rate_usd"] = request.base_rate_usd
    if request.rate_per_1k_tokens is not None:
        updates["rate_per_1k_tokens"] = request.rate_per_1k_tokens
    if request.status is not None:
        if request.status not in ["available", "busy", "offline"]:
            raise HTTPException(status_code=400, detail="Invalid status. Must be: available, busy, or offline")
        updates["status"] = request.status
    if request.webhook_url is not None:
        updates["webhook_url"] = request.webhook_url

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates["last_active"] = datetime.utcnow()

    success = await db_update_agent(agent_id, updates)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update agent")

    logger.info("agent_updated_via_api", agent_id=agent_id, updates=list(updates.keys()))

    return {
        "success": True,
        "agent_id": agent_id,
        "updated_fields": list(updates.keys()),
    }


@app.delete("/api/agents/{agent_id}")
async def delete_agent(
    agent_id: str,
    auth: Optional[AuthenticatedAgent] = Depends(get_current_agent),
):
    """Delete an agent from the marketplace.

    This permanently removes the agent. Use with caution.
    Requires authentication - caller must own the agent.
    """
    # Verify agent exists
    agent = await get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Verify ownership (if auth is enabled)
    if auth:
        owner_id = agent.get("owner_id", "").lower()
        wallet_address = agent.get("wallet_address", "").lower()
        if auth.wallet.lower() not in [owner_id, wallet_address]:
            raise HTTPException(status_code=403, detail="You don't own this agent")

    # Delete the agent
    success = await db_delete_agent(agent_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete agent")

    logger.info("agent_deleted_via_api", agent_id=agent_id, name=agent.get("name"))

    return {
        "success": True,
        "agent_id": agent_id,
        "message": f"Agent '{agent.get('name', agent_id)}' has been deleted",
    }


@app.post("/api/agents/{agent_id}/heartbeat")
async def agent_heartbeat(
    agent_id: str,
    request: AgentHeartbeatRequest,
    auth: Optional[AuthenticatedAgent] = Depends(get_current_agent),
):
    """Agent heartbeat to signal availability.

    Agents should call this periodically (e.g., every 60 seconds) to indicate
    they are online and available for jobs. This updates the agent's last_active
    timestamp and status.

    Requires authentication - caller must own the agent.
    """
    # Verify agent exists
    agent = await get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Verify ownership (if auth is enabled)
    if auth:
        owner_id = agent.get("owner_id", "").lower()
        wallet_address = agent.get("wallet_address", "").lower()
        if auth.wallet.lower() not in [owner_id, wallet_address]:
            raise HTTPException(status_code=403, detail="You don't own this agent")

    # Validate status
    if request.status not in ["available", "busy", "offline"]:
        raise HTTPException(status_code=400, detail="Invalid status. Must be: available, busy, or offline")

    # Update agent
    updates = {
        "status": request.status,
        "last_active": datetime.utcnow(),
        "current_capacity": request.current_capacity,
    }
    if request.metadata:
        updates["heartbeat_metadata"] = request.metadata

    await db_update_agent(agent_id, updates)

    # Check for pending jobs that match this agent (for webhook notification)
    pending_jobs = []
    if request.status == "available":
        all_jobs = await get_all_jobs()
        for job in all_jobs:
            if job.get("status") == "posted":
                pending_jobs.append({
                    "job_id": job["job_id"],
                    "title": job.get("title", ""),
                    "budget_usd": job.get("budget_usd", 0),
                })

    return {
        "success": True,
        "agent_id": agent_id,
        "status": request.status,
        "last_active": updates["last_active"].isoformat(),
        "pending_jobs_count": len(pending_jobs),
        "pending_jobs": pending_jobs[:5],  # Return up to 5 pending jobs
    }


@app.get("/api/agents/{agent_id}/jobs")
async def get_agent_jobs(agent_id: str, status: Optional[str] = None):
    """Get jobs assigned to or completed by this agent."""
    # Verify agent exists
    agent = await get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    all_jobs = await get_all_jobs()
    jobs = [j for j in all_jobs if j.get("assigned_agent_id") == agent_id]
    if status:
        jobs = [j for j in jobs if j.get("status") == status]

    return {"jobs": jobs, "count": len(jobs)}


@app.get("/api/jobs")
async def list_jobs(
    status: Optional[str] = None,
    assigned_agent_id: Optional[str] = None,
):
    """Get all jobs, optionally filtered by status and/or assigned agent."""
    jobs = await get_all_jobs()
    if status:
        jobs = [j for j in jobs if j.get("status") == status]
    if assigned_agent_id:
        jobs = [j for j in jobs if j.get("assigned_agent_id") == assigned_agent_id]
    return {"jobs": jobs, "count": len(jobs)}


@app.get("/api/jobs/{job_id}")
async def get_job_details(job_id: str):
    """Get details for a specific job."""
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Include bids
    bids = await get_bids_for_job(job_id)
    job["bids"] = bids

    return job


@app.get("/api/jobs/{job_id}/matches")
async def get_job_matches(job_id: str, limit: int = 10):
    """Get matching agents for a job based on capabilities."""
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Convert to BazaarJob model for matching
    job_model = BazaarJob(**job)
    matched_agents = await match_agents_to_job(job_model)

    # Limit results
    matched_agents = matched_agents[:limit]

    return {
        "job_id": job_id,
        "matches": matched_agents,
        "count": len(matched_agents),
    }


@app.post("/api/jobs")
async def create_job(request: JobCreateRequest, background_tasks: BackgroundTasks):
    """Create a new job and escrow payment."""
    # Validate wallet address
    if not request.poster_wallet or not request.poster_wallet.startswith("0x") or len(request.poster_wallet) != 42:
        raise HTTPException(
            status_code=400,
            detail="Valid wallet address required. Please connect your wallet before posting a job."
        )

    job_id = f"job_{uuid.uuid4().hex[:8]}"

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
    matched_agent_ids = [a["agent_id"] for a in matched_agents]

    # Notify matched agents via webhooks (in background)
    background_tasks.add_task(
        notify_agents_of_job,
        job.model_dump(),
        matched_agent_ids,
    )

    logger.info(
        "job_created",
        job_id=job_id,
        budget=request.budget_usd,
        matched_agents=len(matched_agents),
    )

    return {
        "job_id": job_id,
        "escrow_txn_id": escrow_txn.txn_id,
        "matched_agents": matched_agent_ids,
        "status": "posted",
    }


@app.get("/api/jobs/{job_id}/bids")
async def get_job_bids(job_id: str):
    """Get all bids for a job."""
    bids = await get_bids_for_job(job_id)
    # Enrich bids with agent names and status
    enriched_bids = []
    for bid in bids:
        agent = await get_agent(bid.get("agent_id"))
        enriched_bid = {
            **bid,
            "agent_name": agent.get("name") if agent else "Unknown Agent",
            "agent_status": agent.get("status", "offline") if agent else "offline",
            "estimated_quality": bid.get("confidence", 0),
            "approach_summary": bid.get("approach", ""),
        }
        enriched_bids.append(enriched_bid)
    return {"bids": enriched_bids}


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
        confidence=estimated_quality,
        estimated_time_seconds=estimated_time_seconds,
        approach=approach_summary,
    )
    return {"bid_id": bid.bid_id, "status": "submitted"}


@app.post("/api/jobs/{job_id}/select-bid/{bid_id}")
async def select_bid(
    job_id: str,
    bid_id: str,
    auth: AuthenticatedAgent = Depends(require_job_poster()),
):
    """Select winning bid for a job. Only the job poster can select a bid."""
    try:
        job = await select_winning_bid(job_id, bid_id)
        return {"job_id": job_id, "winning_bid_id": bid_id, "status": job["status"]}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/jobs/{job_id}/execute")
async def execute_job_endpoint(job_id: str):
    """Execute the job with assigned agent."""
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    result = await execute_job(job_id)
    return result


class ExternalResultRequest(BaseModel):
    """Request body for external agent result submission."""
    success: bool
    output: str
    tokens_used: int = 0
    model: str = ""
    executed_by: str


@app.post("/api/jobs/{job_id}/submit-result")
async def submit_job_result(job_id: str, request: ExternalResultRequest):
    """Submit job result from an external agent runner.

    This endpoint allows decentralized agents to submit their execution results
    after completing work locally with their own LLM.
    """
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.get("status") != JobStatus.ASSIGNED.value:
        raise HTTPException(
            status_code=400,
            detail=f"Job is not in assigned state (status: {job.get('status')})"
        )

    # Verify the agent submitting is the assigned agent
    if job.get("assigned_agent_id") != request.executed_by:
        raise HTTPException(
            status_code=403,
            detail="Only the assigned agent can submit results"
        )

    # Update job with result
    update_data = {
        "status": JobStatus.COMPLETED.value if request.success else JobStatus.FAILED.value,
        "result": {
            "success": request.success,
            "output": request.output,
            "tokens_used": request.tokens_used,
            "model": request.model,
            "executed_by": request.executed_by,
            "submitted_at": datetime.utcnow().isoformat(),
        },
        "completed_at": datetime.utcnow(),
    }

    await update_job(job_id, update_data)

    logger.info(
        "external_result_submitted",
        job_id=job_id,
        agent_id=request.executed_by,
        success=request.success,
        tokens=request.tokens_used,
    )

    return {"job_id": job_id, "status": "completed" if request.success else "failed"}


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


class HumanReviewRequest(BaseModel):
    """Human reviewer's decision on completed work."""
    decision: str  # "accept", "partial", "reject"
    rating: float  # 0.0 to 1.0 (human's quality rating)
    feedback: str = ""  # Human's comments
    reviewer_id: str  # Who is reviewing


@app.post("/api/bids/{bid_id}/counter")
async def counter_offer_endpoint(
    bid_id: str,
    request: CounterOfferRequest,
    auth: AuthenticatedAgent = Depends(require_auth),
):
    """Make a counter-offer on a bid. Poster can counter agent's price, agent can counter poster's offer."""
    # Validate that caller matches the "by" field
    from .db import get_bid, get_job, get_agent
    bid_data = await get_bid(bid_id)
    if not bid_data:
        raise HTTPException(status_code=404, detail="Bid not found")

    job_data = await get_job(bid_data["job_id"])
    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found")

    caller_wallet = auth.wallet.lower()
    poster_wallet = job_data.get("poster_wallet", "").lower()
    poster_id = job_data.get("poster_id", "").lower()

    # Get agent wallet
    agent_data = await get_agent(bid_data["agent_id"])
    agent_wallet = agent_data.get("wallet_address", "").lower() if agent_data else ""

    if request.by == "poster":
        if caller_wallet not in [poster_wallet, poster_id]:
            raise HTTPException(status_code=403, detail="Only the job poster can make poster counter-offers")
    elif request.by == "agent":
        if caller_wallet != agent_wallet:
            raise HTTPException(status_code=403, detail="Only the bidding agent can make agent counter-offers")

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
async def accept_counter_endpoint(
    bid_id: str,
    by: str = "poster",
    auth: AuthenticatedAgent = Depends(require_auth),
):
    """Accept the latest counter-offer. Only the party who received the counter can accept."""
    from .db import get_bid, get_job, get_agent
    bid_data = await get_bid(bid_id)
    if not bid_data:
        raise HTTPException(status_code=404, detail="Bid not found")

    job_data = await get_job(bid_data["job_id"])
    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found")

    caller_wallet = auth.wallet.lower()
    poster_wallet = job_data.get("poster_wallet", "").lower()
    poster_id = job_data.get("poster_id", "").lower()

    agent_data = await get_agent(bid_data["agent_id"])
    agent_wallet = agent_data.get("wallet_address", "").lower() if agent_data else ""

    if by == "poster":
        if caller_wallet not in [poster_wallet, poster_id]:
            raise HTTPException(status_code=403, detail="Only the job poster can accept as poster")
    elif by == "agent":
        if caller_wallet != agent_wallet:
            raise HTTPException(status_code=403, detail="Only the bidding agent can accept as agent")

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
async def approve_bid_endpoint(
    bid_id: str,
    auth: AuthenticatedAgent = Depends(require_bid_poster()),
):
    """Human approval for high-value bids. Only job poster can approve."""
    try:
        bid = await approve_bid(bid_id, auth.wallet)
        return {
            "bid_id": bid_id,
            "status": "approved",
            "approved_by": auth.wallet,
            "final_price": bid.get("final_price_usd"),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/bids/{bid_id}/reject")
async def reject_bid_endpoint(
    bid_id: str,
    reason: str = "",
    auth: AuthenticatedAgent = Depends(require_bid_poster()),
):
    """Reject a bid. Only job poster can reject bids."""
    try:
        bid = await reject_bid(bid_id, auth.wallet, reason)
        return {"bid_id": bid_id, "status": "rejected"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/bids/{bid_id}/auto-negotiate")
async def auto_negotiate_endpoint(
    bid_id: str,
    request: AutoNegotiateRequest,
    auth: AuthenticatedAgent = Depends(require_bid_poster()),
):
    """Use AI to automatically negotiate. Only job poster can trigger auto-negotiation."""
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
# Human Review Endpoints (Quality Rating)
# ============================================================

@app.get("/api/reviews/pending")
async def list_pending_reviews():
    """Get all jobs awaiting human quality review.

    These are jobs where work is completed but the human poster
    hasn't yet reviewed and rated the quality.
    """
    jobs = await get_all_jobs()
    pending = [j for j in jobs if j.get("status") == JobStatus.PENDING_REVIEW.value]

    # Enrich with agent info
    for job in pending:
        agent_id = job.get("assigned_agent_id")
        if agent_id:
            agent = await get_agent(agent_id)
            if agent:
                job["agent_name"] = agent.get("name", agent_id)

    return {"pending_reviews": pending, "count": len(pending)}


@app.get("/api/jobs/{job_id}/review")
async def get_job_for_review(job_id: str):
    """Get job details including AI quality suggestion for human review."""
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.get("status") != JobStatus.PENDING_REVIEW.value:
        raise HTTPException(
            status_code=400,
            detail=f"Job is not pending review (status: {job.get('status')})"
        )

    # Get agent info
    agent_id = job.get("assigned_agent_id")
    agent = await get_agent(agent_id) if agent_id else None

    return {
        "job_id": job_id,
        "title": job.get("title"),
        "description": job.get("description"),
        "result": job.get("result"),
        "ai_quality_suggestion": job.get("ai_quality_suggestion"),
        "agent_id": agent_id,
        "agent_name": agent.get("name") if agent else None,
        "budget_usd": job.get("budget_usd"),
        "status": job.get("status"),
    }


@app.post("/api/jobs/{job_id}/review")
async def submit_human_review(job_id: str, request: HumanReviewRequest):
    """Submit human review decision for a completed job.

    This is where the human makes the FINAL decision on:
    1. Whether to accept, partially accept, or reject the work
    2. The final quality rating (0.0 to 1.0)
    3. Feedback for the agent

    Based on the decision, payment is processed accordingly.
    """
    from .payments.release import release_payment
    from .payments.refund import refund_payment, partial_refund

    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.get("status") != JobStatus.PENDING_REVIEW.value:
        raise HTTPException(
            status_code=400,
            detail=f"Job is not pending review (status: {job.get('status')})"
        )

    # Validate decision
    if request.decision not in ["accept", "partial", "reject"]:
        raise HTTPException(
            status_code=400,
            detail="Decision must be 'accept', 'partial', or 'reject'"
        )

    # Validate rating
    if not (0.0 <= request.rating <= 1.0):
        raise HTTPException(status_code=400, detail="Rating must be between 0.0 and 1.0")

    # Update job with human review
    await update_job(job_id, {
        "status": JobStatus.COMPLETED.value,
        "quality_score": request.rating,  # Human's final rating
        "human_review_decision": request.decision,
        "human_review_rating": request.rating,
        "human_review_feedback": request.feedback,
        "reviewed_by": request.reviewer_id,
        "reviewed_at": datetime.utcnow(),
        "completed_at": datetime.utcnow(),
    })

    # Process payment based on human decision
    escrow_txn_id = job.get("escrow_txn_id")
    agent_id = job.get("assigned_agent_id")
    agent = await get_agent(agent_id) if agent_id else None
    agreed_price = job.get("final_price_usd") or job.get("budget_usd", 0)

    payment_result = {"decision": request.decision}

    if not escrow_txn_id:
        payment_result["error"] = "No escrow found"
    elif request.decision == "accept":
        # Full payment
        try:
            txn = await release_payment(
                escrow_txn_id=escrow_txn_id,
                payee_id=agent_id,
                payee_wallet=agent.get("wallet_address", "") if agent else "",
                amount_usd=agreed_price,
            )
            payment_result["payment_status"] = "released"
            payment_result["amount_paid"] = agreed_price
            payment_result["txn_id"] = txn.txn_id

            # Update agent stats
            if agent:
                await db_update_agent(agent_id, {
                    "jobs_completed": agent.get("jobs_completed", 0) + 1,
                    "total_earned_usd": agent.get("total_earned_usd", 0) + agreed_price,
                })
        except Exception as e:
            payment_result["error"] = str(e)

    elif request.decision == "partial":
        # 50% payment
        partial_amount = agreed_price * 0.5
        try:
            txn = await release_payment(
                escrow_txn_id=escrow_txn_id,
                payee_id=agent_id,
                payee_wallet=agent.get("wallet_address", "") if agent else "",
                amount_usd=partial_amount,
            )
            payment_result["payment_status"] = "partial"
            payment_result["amount_paid"] = partial_amount
            payment_result["txn_id"] = txn.txn_id

            # Update agent stats (partial completion)
            if agent:
                await db_update_agent(agent_id, {
                    "jobs_completed": agent.get("jobs_completed", 0) + 1,
                    "total_earned_usd": agent.get("total_earned_usd", 0) + partial_amount,
                })
        except Exception as e:
            payment_result["error"] = str(e)

    else:  # reject
        # Full refund
        try:
            txn = await refund_payment(escrow_txn_id)
            payment_result["payment_status"] = "refunded"
            payment_result["amount_refunded"] = agreed_price
            payment_result["txn_id"] = txn.txn_id if txn else None

            # Update agent stats (failed job)
            if agent:
                await db_update_agent(agent_id, {
                    "jobs_failed": agent.get("jobs_failed", 0) + 1,
                })
        except Exception as e:
            payment_result["error"] = str(e)

    # Update agent rating based on human review
    if agent:
        old_rating = agent.get("rating_avg", 0)
        old_count = agent.get("rating_count", 0)
        new_count = old_count + 1
        new_rating = ((old_rating * old_count) + (request.rating * 5)) / new_count  # Convert 0-1 to 0-5
        await db_update_agent(agent_id, {
            "rating_avg": min(5.0, new_rating),  # Cap at 5
            "rating_count": new_count,
        })

    logger.info(
        "human_review_submitted",
        job_id=job_id,
        decision=request.decision,
        rating=request.rating,
        reviewer=request.reviewer_id,
        payment_status=payment_result.get("payment_status"),
    )

    return {
        "job_id": job_id,
        "status": "completed",
        "human_review": {
            "decision": request.decision,
            "rating": request.rating,
            "feedback": request.feedback,
            "reviewer": request.reviewer_id,
        },
        "payment": payment_result,
        "message": f"Review submitted. Payment {payment_result.get('payment_status', 'processing')}.",
    }


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
# File Upload/Download Endpoints
# ============================================================

@app.get("/api/files/allowed-types")
async def get_allowed_file_types():
    """Get list of allowed file types for upload."""
    return {
        "max_file_size_mb": MAX_FILE_SIZE_MB,
        "max_files_per_job": MAX_FILES_PER_JOB,
        "allowed_extensions": {
            category.value: sorted(list(extensions))
            for category, extensions in ALLOWED_EXTENSIONS.items()
        },
    }


@app.post("/api/jobs/{job_id}/files")
async def upload_file_to_job(
    job_id: str,
    file: UploadFile = File(...),
    uploaded_by: str = Form(default="anonymous"),
):
    """Upload a file attachment to a job.

    Supports code files, images, documents, and data files.
    Maximum file size: 50MB (configurable).
    Maximum files per job: 10 (configurable).
    """
    # Verify job exists
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Check file count limit
    existing_attachments = job.get("attachments", [])
    if len(existing_attachments) >= MAX_FILES_PER_JOB:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {MAX_FILES_PER_JOB} files per job"
        )

    # Validate filename
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename required")

    if not is_allowed_file(file.filename):
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. See /api/files/allowed-types for accepted formats."
        )

    # Read file content
    content = await file.read()

    # Validate size
    if len(content) > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds maximum size of {MAX_FILE_SIZE_MB}MB"
        )

    try:
        # Save file
        attachment = await save_upload(
            job_id=job_id,
            filename=file.filename,
            content=content,
            uploaded_by=uploaded_by,
        )

        # Update job with attachment metadata
        attachments = existing_attachments + [attachment.model_dump()]
        await update_job(job_id, {"attachments": attachments})

        return {
            "file_id": attachment.file_id,
            "filename": attachment.original_filename,
            "category": attachment.category.value,
            "size": format_file_size(attachment.size_bytes),
            "mime_type": attachment.mime_type,
            "checksum": attachment.checksum_sha256,
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/jobs/{job_id}/files")
async def list_job_files(job_id: str):
    """List all files attached to a job."""
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    attachments = job.get("attachments", [])
    return {
        "job_id": job_id,
        "count": len(attachments),
        "files": [
            {
                "file_id": a.get("file_id"),
                "filename": a.get("original_filename"),
                "category": a.get("category"),
                "size": format_file_size(a.get("size_bytes", 0)),
                "mime_type": a.get("mime_type"),
                "uploaded_at": a.get("uploaded_at"),
            }
            for a in attachments
        ],
    }


@app.get("/api/jobs/{job_id}/files/{file_id}")
async def download_job_file(job_id: str, file_id: str):
    """Download a specific file attached to a job."""
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Find the attachment
    attachments = job.get("attachments", [])
    attachment_data = next((a for a in attachments if a.get("file_id") == file_id), None)

    if not attachment_data:
        raise HTTPException(status_code=404, detail="File not found")

    attachment = JobAttachment(**attachment_data)
    file_path = await get_file_path(attachment)

    if not file_path:
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        path=file_path,
        filename=attachment.original_filename,
        media_type=attachment.mime_type,
    )


@app.delete("/api/jobs/{job_id}/files/{file_id}")
async def delete_job_file(job_id: str, file_id: str):
    """Delete a file attached to a job."""
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Find the attachment
    attachments = job.get("attachments", [])
    attachment_data = next((a for a in attachments if a.get("file_id") == file_id), None)

    if not attachment_data:
        raise HTTPException(status_code=404, detail="File not found")

    attachment = JobAttachment(**attachment_data)

    # Delete from filesystem
    await delete_file(attachment)

    # Remove from job
    updated_attachments = [a for a in attachments if a.get("file_id") != file_id]
    await update_job(job_id, {"attachments": updated_attachments})

    return {"status": "deleted", "file_id": file_id}


@app.get("/api/jobs/{job_id}/result/export")
async def export_job_result(
    job_id: str,
    format: ExportFormat = ExportFormat.JSON,
):
    """Export job result in various formats.

    Formats:
    - json: Formatted JSON
    - csv: CSV (best effort for tabular data)
    - markdown: Markdown with structure
    - text: Plain text extraction
    """
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    result = job.get("result")
    if not result:
        raise HTTPException(status_code=400, detail="Job has no result yet")

    job_title = job.get("title", "Job Result")

    # Generate export
    if format == ExportFormat.JSON:
        content = export_result_as_json(result)
        media_type = "application/json"
        extension = "json"
    elif format == ExportFormat.CSV:
        content = export_result_as_csv(result)
        media_type = "text/csv"
        extension = "csv"
    elif format == ExportFormat.MARKDOWN:
        content = export_result_as_markdown(result, job_title)
        media_type = "text/markdown"
        extension = "md"
    else:  # TEXT
        content = export_result_as_text(result)
        media_type = "text/plain"
        extension = "txt"

    # Generate filename
    safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in job_title[:30])
    filename = f"{safe_title}_{job_id[-8:]}.{extension}"

    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


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
