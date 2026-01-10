"""Abstract backend interface for AgentBazaar operations."""

from abc import ABC, abstractmethod
from typing import Any


class BazaarBackend(ABC):
    """Abstract backend for AgentBazaar marketplace operations.

    Implementations can connect directly to MongoDB or via HTTP API.
    """

    # ============================================================
    # Agent Operations
    # ============================================================

    @abstractmethod
    async def list_agents(
        self,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List marketplace agents with optional filtering."""
        ...

    @abstractmethod
    async def get_agent(self, agent_id: str) -> dict[str, Any] | None:
        """Get agent details by ID."""
        ...

    @abstractmethod
    async def search_agents(
        self,
        capabilities: list[str],
        min_rating: float = 0.0,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search agents by capabilities."""
        ...

    # ============================================================
    # Job Operations
    # ============================================================

    @abstractmethod
    async def list_jobs(
        self,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List jobs with optional status filter."""
        ...

    @abstractmethod
    async def get_job(self, job_id: str) -> dict[str, Any] | None:
        """Get job details including bids."""
        ...

    @abstractmethod
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
        ...

    @abstractmethod
    async def execute_job(self, job_id: str) -> dict[str, Any]:
        """Execute an assigned job."""
        ...

    @abstractmethod
    async def get_job_matches(
        self,
        job_id: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get matching agents for a job."""
        ...

    # ============================================================
    # Bidding Operations
    # ============================================================

    @abstractmethod
    async def submit_bid(
        self,
        job_id: str,
        agent_id: str,
        price_usd: float,
        approach_summary: str,
    ) -> dict[str, Any]:
        """Submit a bid on a job."""
        ...

    @abstractmethod
    async def select_bid(
        self,
        job_id: str,
        bid_id: str,
    ) -> dict[str, Any]:
        """Select winning bid for a job."""
        ...

    @abstractmethod
    async def counter_offer(
        self,
        bid_id: str,
        new_price: float,
        message: str,
    ) -> dict[str, Any]:
        """Make a counter-offer on a bid."""
        ...

    # ============================================================
    # System Operations
    # ============================================================

    @abstractmethod
    async def get_status(self) -> dict[str, Any]:
        """Get marketplace status."""
        ...

    async def close(self) -> None:
        """Clean up resources."""
        pass
