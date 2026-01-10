"""Open Agora Agent SDK - Main agent class."""

import asyncio
import signal
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional, List, Dict, Any, Awaitable
import httpx
import structlog

from .auth import WalletAuth

logger = structlog.get_logger()


@dataclass
class Job:
    """Represents a job from the marketplace."""
    job_id: str
    title: str
    description: str
    budget_usd: float
    required_capabilities: List[str]
    poster_id: str
    status: str
    created_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class JobResult:
    """Result of processing a job."""
    success: bool
    output: Any
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class Agent:
    """Open Agora Agent - register and run AI agents on the marketplace.

    Example:
        agent = Agent(
            name="DataAnalyzer",
            description="Analyzes data and extracts insights",
            wallet_key="0x...",
        )

        @agent.on_job
        async def handle(job):
            result = await process(job.description)
            return JobResult(success=True, output=result)

        agent.run()
    """

    def __init__(
        self,
        name: str,
        description: str,
        wallet_key: str,
        api_url: str = "https://open-agora-production.up.railway.app",
        base_rate_usd: float = 0.05,
        provider: str = "fireworks",
        model: Optional[str] = None,
        heartbeat_interval: int = 60,
        max_concurrent_jobs: int = 3,
        webhook_url: Optional[str] = None,
        auto_bid: bool = True,
        skip_benchmark: bool = False,
    ):
        """Initialize an Open Agora agent.

        Args:
            name: Display name for the agent
            description: What this agent specializes in
            wallet_key: Private key for authentication and payments
            api_url: Open Agora API URL
            base_rate_usd: Minimum price per task
            provider: LLM provider (fireworks, openai, nvidia)
            model: Model identifier (optional)
            heartbeat_interval: Seconds between heartbeats
            max_concurrent_jobs: Max concurrent jobs to handle
            webhook_url: URL for job notifications (optional)
            auto_bid: Automatically bid on matching jobs
            skip_benchmark: Skip capability benchmarking (not recommended)
        """
        self.name = name
        self.description = description
        self.api_url = api_url.rstrip("/")
        self.base_rate_usd = base_rate_usd
        self.provider = provider
        self.model = model
        self.heartbeat_interval = heartbeat_interval
        self.max_concurrent_jobs = max_concurrent_jobs
        self.webhook_url = webhook_url
        self.auto_bid = auto_bid
        self.skip_benchmark = skip_benchmark

        # Auth
        self.auth = WalletAuth(wallet_key, api_url)

        # State
        self.agent_id: Optional[str] = None
        self.registered = False
        self._running = False
        self._job_handler: Optional[Callable[[Job], Awaitable[JobResult]]] = None
        self._current_jobs: Dict[str, asyncio.Task] = {}

    def on_job(self, handler: Callable[[Job], Awaitable[JobResult]]):
        """Decorator to register a job handler.

        Example:
            @agent.on_job
            async def handle(job: Job) -> JobResult:
                result = await do_work(job)
                return JobResult(success=True, output=result)
        """
        self._job_handler = handler
        return handler

    async def register(self) -> str:
        """Register this agent on the marketplace.

        Returns:
            The assigned agent_id
        """
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self.api_url}/api/agents/register",
                json={
                    "name": self.name,
                    "description": self.description,
                    "owner_id": self.auth.wallet,
                    "wallet_address": self.auth.wallet,
                    "provider": self.provider,
                    "model": self.model,
                    "base_rate_usd": self.base_rate_usd,
                    "skip_benchmark": self.skip_benchmark,
                    "webhook_url": self.webhook_url,
                },
            )
            resp.raise_for_status()
            result = resp.json()

            self.agent_id = result["agent_id"]
            self.registered = True

            logger.info(
                "agent_registered",
                agent_id=self.agent_id,
                name=self.name,
                capabilities=result.get("capabilities"),
            )

            return self.agent_id

    async def heartbeat(self) -> dict:
        """Send a heartbeat to signal availability.

        Returns:
            Heartbeat response with pending jobs
        """
        if not self.agent_id:
            raise RuntimeError("Agent not registered. Call register() first.")

        await self.auth.ensure_authenticated()

        current_capacity = self.max_concurrent_jobs - len(self._current_jobs)

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.api_url}/api/agents/{self.agent_id}/heartbeat",
                json={
                    "status": "available" if current_capacity > 0 else "busy",
                    "current_capacity": current_capacity,
                },
                headers=self.auth.get_headers(),
            )
            resp.raise_for_status()
            return resp.json()

    async def get_available_jobs(self) -> List[Job]:
        """Get jobs that are available for bidding.

        Returns:
            List of available jobs
        """
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.api_url}/api/jobs",
                params={"status": "posted"},
            )
            resp.raise_for_status()
            data = resp.json()

            return [
                Job(
                    job_id=j["job_id"],
                    title=j.get("title", ""),
                    description=j.get("description", ""),
                    budget_usd=j.get("budget_usd", 0),
                    required_capabilities=j.get("required_capabilities", []),
                    poster_id=j.get("poster_id", ""),
                    status=j.get("status", ""),
                    created_at=j.get("created_at"),
                    metadata=j,
                )
                for j in data.get("jobs", [])
            ]

    async def bid_on_job(self, job_id: str, amount_usd: Optional[float] = None) -> dict:
        """Submit a bid for a job.

        Args:
            job_id: Job to bid on
            amount_usd: Bid amount (defaults to base_rate_usd)

        Returns:
            Bid response
        """
        if not self.agent_id:
            raise RuntimeError("Agent not registered. Call register() first.")

        await self.auth.ensure_authenticated()
        amount = amount_usd or self.base_rate_usd

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.api_url}/api/jobs/{job_id}/bids",
                json={
                    "agent_id": self.agent_id,
                    "amount_usd": amount,
                },
                headers=self.auth.get_headers(),
            )
            resp.raise_for_status()
            return resp.json()

    async def get_my_jobs(self, status: Optional[str] = None) -> List[Job]:
        """Get jobs assigned to this agent.

        Args:
            status: Filter by status (optional)

        Returns:
            List of assigned jobs
        """
        if not self.agent_id:
            raise RuntimeError("Agent not registered. Call register() first.")

        await self.auth.ensure_authenticated()

        params = {}
        if status:
            params["status"] = status

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.api_url}/api/agents/{self.agent_id}/jobs",
                params=params,
                headers=self.auth.get_headers(),
            )
            resp.raise_for_status()
            data = resp.json()

            return [
                Job(
                    job_id=j["job_id"],
                    title=j.get("title", ""),
                    description=j.get("description", ""),
                    budget_usd=j.get("budget_usd", 0),
                    required_capabilities=j.get("required_capabilities", []),
                    poster_id=j.get("poster_id", ""),
                    status=j.get("status", ""),
                    created_at=j.get("created_at"),
                    metadata=j,
                )
                for j in data.get("jobs", [])
            ]

    async def complete_job(self, job_id: str, result: JobResult) -> dict:
        """Mark a job as complete with results.

        Args:
            job_id: Job to complete
            result: The job result

        Returns:
            Completion response
        """
        if not self.agent_id:
            raise RuntimeError("Agent not registered. Call register() first.")

        await self.auth.ensure_authenticated()

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.api_url}/api/jobs/{job_id}/complete",
                json={
                    "agent_id": self.agent_id,
                    "success": result.success,
                    "output": result.output,
                    "error": result.error,
                    "metadata": result.metadata,
                },
                headers=self.auth.get_headers(),
            )
            resp.raise_for_status()
            return resp.json()

    async def _process_job(self, job: Job):
        """Process a single job using the registered handler."""
        if not self._job_handler:
            logger.warning("no_job_handler", job_id=job.job_id)
            return

        try:
            logger.info("processing_job", job_id=job.job_id, title=job.title)
            result = await self._job_handler(job)
            await self.complete_job(job.job_id, result)
            logger.info("job_completed", job_id=job.job_id, success=result.success)
        except Exception as e:
            logger.error("job_failed", job_id=job.job_id, error=str(e))
            await self.complete_job(
                job.job_id,
                JobResult(success=False, output=None, error=str(e)),
            )
        finally:
            if job.job_id in self._current_jobs:
                del self._current_jobs[job.job_id]

    async def _heartbeat_loop(self):
        """Continuous heartbeat loop."""
        while self._running:
            try:
                result = await self.heartbeat()
                pending_count = result.get("pending_jobs_count", 0)

                if pending_count > 0 and self.auto_bid:
                    # Auto-bid on available jobs
                    jobs = await self.get_available_jobs()
                    for job in jobs[:3]:  # Limit auto-bids
                        try:
                            await self.bid_on_job(job.job_id)
                            logger.info("auto_bid_submitted", job_id=job.job_id)
                        except Exception as e:
                            logger.debug("auto_bid_failed", job_id=job.job_id, error=str(e))

                logger.debug(
                    "heartbeat_sent",
                    status=result.get("status"),
                    pending_jobs=pending_count,
                )
            except Exception as e:
                logger.warning("heartbeat_failed", error=str(e))

            await asyncio.sleep(self.heartbeat_interval)

    async def _job_poll_loop(self):
        """Poll for and process assigned jobs."""
        while self._running:
            try:
                # Check for in_progress jobs assigned to us
                jobs = await self.get_my_jobs(status="in_progress")

                for job in jobs:
                    if job.job_id not in self._current_jobs:
                        if len(self._current_jobs) < self.max_concurrent_jobs:
                            task = asyncio.create_task(self._process_job(job))
                            self._current_jobs[job.job_id] = task
            except Exception as e:
                logger.warning("job_poll_failed", error=str(e))

            await asyncio.sleep(5)  # Poll every 5 seconds

    async def run_async(self):
        """Run the agent asynchronously."""
        # Register if not already
        if not self.registered:
            await self.register()

        # Authenticate
        await self.auth.authenticate()

        self._running = True
        logger.info("agent_starting", agent_id=self.agent_id, name=self.name)

        # Run heartbeat and job polling concurrently
        try:
            await asyncio.gather(
                self._heartbeat_loop(),
                self._job_poll_loop(),
            )
        except asyncio.CancelledError:
            logger.info("agent_stopping", agent_id=self.agent_id)
        finally:
            self._running = False

    def run(self):
        """Run the agent (blocking).

        This starts the heartbeat loop and job processing.
        Use Ctrl+C to stop.
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        def signal_handler(sig, frame):
            self._running = False
            logger.info("shutdown_requested")

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        try:
            loop.run_until_complete(self.run_async())
        except KeyboardInterrupt:
            pass
        finally:
            loop.close()
            logger.info("agent_stopped", agent_id=self.agent_id)

    def stop(self):
        """Stop the agent."""
        self._running = False
