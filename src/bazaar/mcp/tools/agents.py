"""Agent-related MCP tools for AgentBazaar."""

from typing import Any

from mcp.server.fastmcp import FastMCP

from ..backends.base import BazaarBackend


def register_agent_tools(mcp: FastMCP, backend: BazaarBackend) -> None:
    """Register agent-related tools with the MCP server."""

    @mcp.tool()
    async def bazaar_list_agents(
        status: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """List all agents in the AgentBazaar marketplace.

        Args:
            status: Filter by agent status (available, busy, offline)
            limit: Maximum number of agents to return (default 50)

        Returns:
            List of agents with their capabilities, ratings, and availability
        """
        try:
            agents = await backend.list_agents(status=status, limit=limit)
            return {
                "success": True,
                "count": len(agents),
                "agents": agents,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def bazaar_get_agent(agent_id: str) -> dict[str, Any]:
        """Get detailed information about a specific agent.

        Args:
            agent_id: The unique identifier of the agent

        Returns:
            Agent details including capabilities, rating, jobs completed, and rates
        """
        try:
            agent = await backend.get_agent(agent_id)
            if agent is None:
                return {"success": False, "error": f"Agent {agent_id} not found"}
            return {"success": True, "agent": agent}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def bazaar_search_agents(
        capabilities: list[str],
        min_rating: float = 0.0,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Search for agents with specific capabilities.

        Args:
            capabilities: List of required capabilities (e.g., ["summarization", "sentiment_analysis"])
            min_rating: Minimum agent rating (0.0 to 5.0)
            limit: Maximum number of agents to return

        Returns:
            List of matching agents sorted by relevance
        """
        try:
            agents = await backend.search_agents(
                capabilities=capabilities,
                min_rating=min_rating,
                limit=limit,
            )
            return {
                "success": True,
                "count": len(agents),
                "capabilities_searched": capabilities,
                "agents": agents,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
