"""HTTP backend for connecting to deployed AgentBazaar API."""

from typing import Any

import httpx

from .base import BazaarBackend


class HTTPBazaarBackend(BazaarBackend):
    """HTTP client backend for connecting to deployed Vercel API."""

    def __init__(self, base_url: str, api_key: str | None = None):
        self.base_url = base_url.rstrip("/")
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=30.0,
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

    # ============================================================
    # Agent Operations
    # ============================================================

    async def list_agents(
        self,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List marketplace agents."""
        params: dict[str, Any] = {"limit": limit}
        if status:
            params["status"] = status

        response = await self.client.get("/api/agents", params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("agents", [])

    async def get_agent(self, agent_id: str) -> dict[str, Any] | None:
        """Get agent details by ID."""
        response = await self.client.get(f"/api/agents/{agent_id}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    async def search_agents(
        self,
        capabilities: list[str],
        min_rating: float = 0.0,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search agents by capabilities."""
        # Use list_agents and filter client-side for now
        # A proper implementation would have a search endpoint
        agents = await self.list_agents(status="available", limit=100)

        matching = []
        for agent in agents:
            agent_caps = agent.get("capabilities", {})
            rating = agent.get("rating_avg", 0)

            if rating < min_rating:
                continue

            # Check if agent has all required capabilities
            has_caps = all(cap in agent_caps for cap in capabilities)
            if has_caps:
                matching.append(agent)

        return matching[:limit]

    # ============================================================
    # Job Operations
    # ============================================================

    async def list_jobs(
        self,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List jobs with optional status filter."""
        params: dict[str, Any] = {"limit": limit}
        if status:
            params["status"] = status

        response = await self.client.get("/api/jobs", params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("jobs", [])

    async def get_job(self, job_id: str) -> dict[str, Any] | None:
        """Get job details including bids."""
        response = await self.client.get(f"/api/jobs/{job_id}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    async def create_job(
        self,
        title: str,
        description: str,
        budget_usd: float,
        required_capabilities: list[str],
        poster_id: str,
        poster_wallet: str,
    ) -> dict[str, Any]:
        """Create a new job posting."""
        payload = {
            "title": title,
            "description": description,
            "budget_usd": budget_usd,
            "required_capabilities": required_capabilities,
            "poster_id": poster_id,
            "poster_wallet": poster_wallet,
        }
        response = await self.client.post("/api/jobs", json=payload)
        response.raise_for_status()
        return response.json()

    async def execute_job(self, job_id: str) -> dict[str, Any]:
        """Execute an assigned job."""
        response = await self.client.post(f"/api/jobs/{job_id}/execute")
        response.raise_for_status()
        return response.json()

    async def get_job_matches(
        self,
        job_id: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get matching agents for a job.

        Note: This may need a dedicated endpoint. For now, get job
        and search for matching agents based on required capabilities.
        """
        job = await self.get_job(job_id)
        if not job:
            return []

        required_caps = job.get("required_capabilities", [])
        if not required_caps:
            return await self.list_agents(status="available", limit=limit)

        return await self.search_agents(capabilities=required_caps, limit=limit)

    # ============================================================
    # Bidding Operations
    # ============================================================

    async def submit_bid(
        self,
        job_id: str,
        agent_id: str,
        price_usd: float,
        approach_summary: str,
    ) -> dict[str, Any]:
        """Submit a bid on a job."""
        payload = {
            "agent_id": agent_id,
            "price_usd": price_usd,
            "approach_summary": approach_summary,
        }
        response = await self.client.post(f"/api/jobs/{job_id}/bids", json=payload)
        response.raise_for_status()
        return response.json()

    async def select_bid(
        self,
        job_id: str,
        bid_id: str,
    ) -> dict[str, Any]:
        """Select winning bid for a job."""
        response = await self.client.post(f"/api/jobs/{job_id}/select-bid/{bid_id}")
        response.raise_for_status()
        return response.json()

    async def counter_offer(
        self,
        bid_id: str,
        new_price: float,
        message: str,
    ) -> dict[str, Any]:
        """Make a counter-offer on a bid."""
        payload = {
            "new_price": new_price,
            "message": message,
        }
        response = await self.client.post(f"/api/bids/{bid_id}/counter", json=payload)
        response.raise_for_status()
        return response.json()

    # ============================================================
    # Human Review Operations
    # ============================================================

    async def list_pending_reviews(self) -> list[dict[str, Any]]:
        """List jobs pending human quality review."""
        response = await self.client.get("/api/reviews/pending")
        response.raise_for_status()
        data = response.json()
        return data.get("pending_reviews", [])

    async def get_job_for_review(self, job_id: str) -> dict[str, Any] | None:
        """Get job details for human review."""
        response = await self.client.get(f"/api/jobs/{job_id}/review")
        if response.status_code == 404:
            return None
        if response.status_code == 400:
            # Job not pending review
            return None
        response.raise_for_status()
        return response.json()

    async def submit_review(
        self,
        job_id: str,
        decision: str,
        rating: float | None,
        feedback: str,
        reviewer_id: str,
    ) -> dict[str, Any]:
        """Submit human review decision."""
        payload = {
            "decision": decision,
            "feedback": feedback,
            "reviewer_id": reviewer_id,
        }
        # Default rating based on decision if not provided
        if rating is not None:
            payload["rating"] = rating
        else:
            payload["rating"] = {"accept": 1.0, "partial": 0.5, "reject": 0.2}.get(decision, 0.5)

        response = await self.client.post(f"/api/jobs/{job_id}/review", json=payload)
        response.raise_for_status()
        return response.json()

    # ============================================================
    # System Operations
    # ============================================================

    async def get_status(self) -> dict[str, Any]:
        """Get marketplace status."""
        response = await self.client.get("/api/demo/status")
        response.raise_for_status()
        return response.json()
