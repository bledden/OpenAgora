"""Bidding and negotiation MCP tools for AgentBazaar."""

from typing import Any

from mcp.server.fastmcp import FastMCP

from ..backends.base import BazaarBackend


def register_bidding_tools(mcp: FastMCP, backend: BazaarBackend) -> None:
    """Register bidding-related tools with the MCP server."""

    @mcp.tool()
    async def bazaar_submit_bid(
        job_id: str,
        agent_id: str,
        price_usd: float,
        approach_summary: str,
    ) -> dict[str, Any]:
        """Submit a bid on a job from an agent.

        Args:
            job_id: The job to bid on
            agent_id: The agent submitting the bid
            price_usd: Proposed price in USD
            approach_summary: Brief description of how the agent will complete the task

        Returns:
            The created bid with its ID
        """
        try:
            bid = await backend.submit_bid(
                job_id=job_id,
                agent_id=agent_id,
                price_usd=price_usd,
                approach_summary=approach_summary,
            )
            return {
                "success": True,
                "message": f"Bid submitted successfully",
                "bid": bid,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def bazaar_select_bid(
        job_id: str,
        bid_id: str,
    ) -> dict[str, Any]:
        """Select a winning bid for a job.

        This will assign the job to the bidding agent and prepare for execution.

        Args:
            job_id: The job ID
            bid_id: The winning bid ID to select

        Returns:
            Updated job and bid status
        """
        try:
            result = await backend.select_bid(job_id=job_id, bid_id=bid_id)
            return {
                "success": True,
                "message": "Bid selected and job assigned",
                "result": result,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def bazaar_counter_offer(
        bid_id: str,
        new_price: float,
        message: str = "",
    ) -> dict[str, Any]:
        """Make a counter-offer on an existing bid.

        Both job posters and agents can make counter-offers during negotiation.

        Args:
            bid_id: The bid to counter
            new_price: The proposed new price in USD
            message: Optional message explaining the counter-offer

        Returns:
            Updated bid with counter-offer details
        """
        try:
            result = await backend.counter_offer(
                bid_id=bid_id,
                new_price=new_price,
                message=message,
            )
            return {
                "success": True,
                "message": "Counter-offer submitted",
                "result": result,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def bazaar_get_status() -> dict[str, Any]:
        """Get the current status of the AgentBazaar marketplace.

        Returns:
            Marketplace statistics including agent count, job count, and system status
        """
        try:
            status = await backend.get_status()
            return {
                "success": True,
                "marketplace": "AgentBazaar",
                "status": status,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
