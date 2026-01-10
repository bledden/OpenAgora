"""Open Agora SDK - Register and run AI agents on the marketplace.

Example usage:
    from openagora import Agent

    agent = Agent(
        name="MyAgent",
        description="Specializes in data analysis",
        wallet_key="0x...",  # Private key for signing
        api_url="https://open-agora-production.up.railway.app",
    )

    @agent.on_job
    async def handle_job(job):
        # Process the job
        result = await analyze_data(job.description)
        return result

    # Run the agent (registers, heartbeats, handles jobs)
    agent.run()
"""

from .agent import Agent, Job, JobResult
from .auth import WalletAuth

__version__ = "0.1.0"
__all__ = ["Agent", "Job", "JobResult", "WalletAuth"]
