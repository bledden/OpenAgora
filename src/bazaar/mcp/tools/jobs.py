"""Job-related MCP tools for AgentBazaar."""

from typing import Any

from mcp.server.fastmcp import FastMCP

from ..backends.base import BazaarBackend


def register_job_tools(mcp: FastMCP, backend: BazaarBackend) -> None:
    """Register job-related tools with the MCP server."""

    @mcp.tool()
    async def bazaar_list_jobs(
        status: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """List jobs in the AgentBazaar marketplace.

        Args:
            status: Filter by job status (open, posted, bidding, assigned, in_progress, completed)
            limit: Maximum number of jobs to return (default 50)

        Returns:
            List of jobs with their details, budgets, and current status
        """
        try:
            jobs = await backend.list_jobs(status=status, limit=limit)
            return {
                "success": True,
                "count": len(jobs),
                "jobs": jobs,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def bazaar_get_job(job_id: str) -> dict[str, Any]:
        """Get detailed information about a specific job including its bids.

        Args:
            job_id: The unique identifier of the job

        Returns:
            Job details including description, requirements, budget, bids, and status
        """
        try:
            job = await backend.get_job(job_id)
            if job is None:
                return {"success": False, "error": f"Job {job_id} not found"}
            return {"success": True, "job": job}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def bazaar_create_job(
        title: str,
        description: str,
        budget_usd: float,
        required_capabilities: list[str],
        poster_id: str = "mcp_user",
        poster_wallet: str = "0xMCPUser0000000000000000000000000000001",
    ) -> dict[str, Any]:
        """Create a new job posting in the marketplace.

        This will create an escrow for the budget amount using x402.

        Args:
            title: Short title for the job
            description: Detailed description of what needs to be done
            budget_usd: Maximum budget in USD for this job
            required_capabilities: List of required agent capabilities
            poster_id: Your user ID (default: mcp_user)
            poster_wallet: Your wallet address for x402 payments

        Returns:
            The created job with its ID and escrow transaction
        """
        try:
            job = await backend.create_job(
                title=title,
                description=description,
                budget_usd=budget_usd,
                required_capabilities=required_capabilities,
                poster_id=poster_id,
                poster_wallet=poster_wallet,
            )
            return {
                "success": True,
                "message": f"Job created successfully with ID {job.get('job_id')}",
                "job": job,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def bazaar_execute_job(job_id: str) -> dict[str, Any]:
        """Execute an assigned job.

        The job must be in 'assigned' status with a winning bid selected.
        The assigned agent will perform the task and results will be evaluated.

        Args:
            job_id: The job ID to execute

        Returns:
            Execution result including output, quality score, and payment status
        """
        try:
            result = await backend.execute_job(job_id)
            return {
                "success": True,
                "message": "Job executed successfully",
                "result": result,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def bazaar_get_job_matches(
        job_id: str,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Get recommended agents for a job based on capability matching.

        Args:
            job_id: The job ID to find matches for
            limit: Maximum number of matches to return

        Returns:
            List of matching agents ranked by suitability
        """
        try:
            matches = await backend.get_job_matches(job_id=job_id, limit=limit)
            return {
                "success": True,
                "count": len(matches),
                "matches": matches,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ============================================================
    # Human Review Tools
    # ============================================================

    @mcp.tool()
    async def bazaar_list_pending_reviews() -> dict[str, Any]:
        """List jobs pending human quality review.

        These are jobs where work is completed but awaiting human
        decision on accepting/rejecting the work and rating quality.

        Returns:
            List of pending reviews with AI quality suggestions
        """
        try:
            reviews = await backend.list_pending_reviews()
            return {
                "success": True,
                "count": len(reviews),
                "pending_reviews": reviews,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def bazaar_get_job_for_review(job_id: str) -> dict[str, Any]:
        """Get job details for human quality review.

        Shows the completed work, AI quality suggestion with scores,
        and other details needed to make a review decision.

        Args:
            job_id: The job ID to review

        Returns:
            Job details with AI suggestion including scores, strengths,
            improvements, and red flags
        """
        try:
            review = await backend.get_job_for_review(job_id)
            if review is None:
                return {"success": False, "error": f"Job {job_id} not found or not pending review"}
            return {"success": True, "review": review}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def bazaar_submit_review(
        job_id: str,
        decision: str,
        rating: float = None,
        feedback: str = "",
        reviewer_id: str = "mcp_user",
    ) -> dict[str, Any]:
        """Submit human review decision for a completed job.

        This is where you make the FINAL decision on:
        1. Whether to accept, partially accept, or reject the work
        2. Your quality rating (0.0 to 1.0)
        3. Feedback for the agent

        Payment is processed based on your decision:
        - accept: Full payment released to agent
        - partial: 50% payment released
        - reject: Full refund to poster

        Args:
            job_id: The job ID being reviewed
            decision: Your decision - "accept", "partial", or "reject"
            rating: Quality rating 0.0-1.0 (defaults based on decision)
            feedback: Optional feedback for the agent
            reviewer_id: Your user ID

        Returns:
            Review result including payment status
        """
        try:
            result = await backend.submit_review(
                job_id=job_id,
                decision=decision,
                rating=rating,
                feedback=feedback,
                reviewer_id=reviewer_id,
            )
            return {
                "success": True,
                "message": f"Review submitted: {decision}",
                "result": result,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
