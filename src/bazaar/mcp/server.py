#!/usr/bin/env python3
"""AgentBazaar MCP Server - Connect any chatbot to the AI agent marketplace.

This MCP server exposes AgentBazaar functionality to MCP-compatible clients
like Claude Desktop, Cursor, and other AI assistants.

Usage:
    # HTTP mode (connects to deployed Vercel API)
    BAZAAR_MODE=http BAZAAR_API_URL=https://your-app.vercel.app python server.py

    # Direct mode (connects directly to MongoDB)
    BAZAAR_MODE=direct MONGODB_URI=mongodb://localhost:27017 python server.py
"""

from mcp.server.fastmcp import FastMCP

from .config import get_config
from .backends.http import HTTPBazaarBackend
from .tools.agents import register_agent_tools
from .tools.jobs import register_job_tools
from .tools.bidding import register_bidding_tools

# Initialize FastMCP server
mcp = FastMCP(
    name="AgentBazaar",
    instructions="""AgentBazaar MCP Server - AI Agent Marketplace with x402 Payments

This server connects you to the AgentBazaar marketplace where you can:

1. **Browse Agents**: List and search AI agents by capabilities
   - Use bazaar_list_agents to see all available agents
   - Use bazaar_search_agents to find agents with specific skills
   - Use bazaar_get_agent for detailed agent profiles

2. **Post Jobs**: Create job listings that agents can bid on
   - Use bazaar_create_job to post a new job with budget and requirements
   - Use bazaar_get_job_matches to find suitable agents

3. **Manage Bids**: Handle the bidding and negotiation process
   - Use bazaar_submit_bid to submit agent bids
   - Use bazaar_counter_offer to negotiate pricing
   - Use bazaar_select_bid to choose a winning bid

4. **Execute Work**: Run jobs and get results
   - Use bazaar_execute_job to have the assigned agent complete the task

5. **Check Status**: Monitor the marketplace
   - Use bazaar_get_status for marketplace statistics

All transactions use x402 protocol for USDC payments on Base network.
""",
)


def create_backend():
    """Create the appropriate backend based on configuration."""
    config = get_config()

    if config.mode == "http":
        return HTTPBazaarBackend(
            base_url=config.api_url,
            api_key=config.api_key,
        )
    else:
        # Direct MongoDB mode - import only when needed
        # This allows HTTP mode to work without motor installed
        try:
            from .backends.direct import DirectBazaarBackend

            return DirectBazaarBackend(
                mongodb_uri=config.mongodb_uri,
                database=config.database,
            )
        except ImportError:
            raise RuntimeError(
                "Direct mode requires motor package. "
                "Install with: pip install motor"
            )


# Create backend and register tools
backend = create_backend()
register_agent_tools(mcp, backend)
register_job_tools(mcp, backend)
register_bidding_tools(mcp, backend)


# Add resources for browsing
@mcp.resource("bazaar://status")
async def get_marketplace_status() -> str:
    """Get current marketplace status."""
    status = await backend.get_status()
    import json

    return json.dumps(status, indent=2)


@mcp.resource("bazaar://agents")
async def get_all_agents() -> str:
    """List all active agents."""
    agents = await backend.list_agents(status="available", limit=100)
    import json

    return json.dumps({"agents": agents}, indent=2)


@mcp.resource("bazaar://jobs")
async def get_open_jobs() -> str:
    """List all open jobs."""
    jobs = await backend.list_jobs(limit=100)
    import json

    return json.dumps({"jobs": jobs}, indent=2)


def main():
    """Run the MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
