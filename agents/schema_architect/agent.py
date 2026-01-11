#!/usr/bin/env python3
"""SchemaArchitect - Local agent for API and schema design.

This agent specializes in:
- REST API design and OpenAPI spec generation
- GraphQL schema design
- Database schema design (SQL, MongoDB)
- Schema validation and best practices review
- Data model optimization

Run this agent locally and connect it to Open Agora marketplace.
"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
import json

# Add parent paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env")

import httpx
import structlog

logger = structlog.get_logger()

# Agent configuration
AGENT_CONFIG = {
    "agent_id": "agent_24a17a8f",  # Server-assigned ID from previous registration
    "name": "SchemaArchitect",
    "description": """Expert in API and data schema design. Specializes in REST API design,
OpenAPI/Swagger specs, GraphQL schemas, database modeling (SQL & NoSQL), and schema validation.
Provides best practices recommendations and identifies design anti-patterns.""",
    "capabilities": {
        "schema_design": 0.96,
        "code_review": 0.88,
        "data_extraction": 0.85,
        "pattern_recognition": 0.90,
        "classification": 0.82,
    },
    "provider": "fireworks",
    "model": "accounts/fireworks/models/llama-v3p3-70b-instruct",
    "base_rate_usd": 0.04,
    "rate_per_1k_tokens": 0.001,
}

SYSTEM_PROMPT = """You are SchemaArchitect, an expert API and schema design agent.

Your specialties:
- REST API design following OpenAPI 3.0+ specifications
- GraphQL schema design with best practices
- Database schema design for SQL (PostgreSQL, MySQL) and NoSQL (MongoDB, DynamoDB)
- Data model optimization for performance and scalability
- Schema validation and anti-pattern detection
- Migration strategy recommendations

When designing or reviewing schemas:
1. Analyze requirements and identify entities/relationships
2. Apply normalization rules (for SQL) or embedding strategies (for NoSQL)
3. Consider query patterns and access patterns
4. Identify potential scaling issues
5. Suggest indexing strategies
6. Provide concrete schema examples with comments

Output format:
- For API design: Provide OpenAPI YAML or GraphQL SDL
- For database design: Provide SQL DDL or MongoDB schema validation
- For reviews: List issues by severity (critical, warning, suggestion)

Be thorough but practical. Prioritize real-world usability."""


class SchemaArchitectAgent:
    """Local agent that connects to Open Agora marketplace."""

    def __init__(self):
        self.config = AGENT_CONFIG
        self.fireworks_api_key = os.getenv("FIREWORKS_API_KEY")
        self.bazaar_api_url = os.getenv("BAZAAR_API_URL", "http://localhost:8000")
        self.registered = False
        self.jobs_bid_on = set()  # Track job IDs we've already bid on

    async def register_with_marketplace(self) -> bool:
        """Register this agent with the Open Agora marketplace."""
        registration_data = {
            **self.config,
            "owner_id": os.getenv("AGENT_OWNER_ID", "local_owner"),
            "wallet_address": os.getenv("AGENT_WALLET", "0xLocalSchemaArchitect000000000001"),
            "status": "available",
            "webhook_url": os.getenv("AGENT_WEBHOOK_URL"),  # Optional webhook for job notifications
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.bazaar_api_url}/api/agents/register",
                    json=registration_data,
                    timeout=30.0,
                )

                if response.status_code in [200, 201]:
                    data = response.json()
                    # Capture the server-assigned agent_id
                    if "agent_id" in data:
                        self.config["agent_id"] = data["agent_id"]
                    logger.info("agent_registered", agent_id=self.config["agent_id"])
                    self.registered = True
                    return True
                elif response.status_code == 409:
                    logger.info("agent_already_registered", agent_id=self.config["agent_id"])
                    self.registered = True
                    return True
                else:
                    logger.error("registration_failed", status=response.status_code, body=response.text)
                    return False

        except Exception as e:
            logger.error("registration_error", error=str(e))
            return False

    async def execute_task(self, job_description: str, job_context: Optional[dict] = None) -> dict:
        """Execute a task using the agent's specialized model."""
        if not self.fireworks_api_key:
            return {"success": False, "error": "FIREWORKS_API_KEY not set"}

        # Build the task prompt
        task_prompt = f"""## Task
{job_description}

"""
        if job_context:
            task_prompt += f"""## Additional Context
{json.dumps(job_context, indent=2)}

"""
        task_prompt += """## Instructions
Complete this task thoroughly. Provide concrete, usable output.
For schemas, include comments explaining design decisions.
"""

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": task_prompt},
        ]

        try:
            start_time = datetime.now(timezone.utc)

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.fireworks.ai/inference/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.fireworks_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.config["model"],
                        "messages": messages,
                        "temperature": 0.4,
                        "max_tokens": 4096,
                    },
                    timeout=120.0,
                )
                response.raise_for_status()
                data = response.json()

            latency_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            tokens_in = data.get("usage", {}).get("prompt_tokens", 0)
            tokens_out = data.get("usage", {}).get("completion_tokens", 0)

            # Calculate cost (Llama 70B pricing)
            cost_usd = (tokens_in + tokens_out) / 1000 * 0.0009

            return {
                "success": True,
                "output": data["choices"][0]["message"]["content"],
                "tokens_used": tokens_in + tokens_out,
                "cost_usd": round(cost_usd, 6),
                "latency_ms": round(latency_ms, 2),
                "model": self.config["model"],
            }

        except Exception as e:
            logger.error("execution_failed", error=str(e))
            return {"success": False, "error": str(e)}

    async def evaluate_job(self, job_description: str, job_budget: float) -> dict:
        """Evaluate a job and generate a bid."""
        # Simple evaluation based on task complexity
        keywords_high = ["design", "architecture", "schema", "api", "graphql", "database", "model"]
        keywords_medium = ["review", "validate", "check", "optimize"]

        desc_lower = job_description.lower()
        complexity = sum(1 for kw in keywords_high if kw in desc_lower)
        complexity += sum(0.5 for kw in keywords_medium if kw in desc_lower)

        # Determine if we can complete this
        can_complete = any(kw in desc_lower for kw in ["schema", "api", "database", "graphql", "model", "endpoint"])

        if not can_complete:
            return {
                "can_complete": False,
                "confidence": 0.3,
                "reasoning": "Task doesn't match my specialization in API/schema design.",
            }

        # Calculate bid based on complexity
        base_bid = self.config["base_rate_usd"]
        complexity_multiplier = 1 + (complexity * 0.5)
        bid_amount = min(base_bid * complexity_multiplier, job_budget * 0.8)

        return {
            "can_complete": True,
            "confidence": min(0.95, 0.7 + complexity * 0.05),
            "bid_amount_usd": round(bid_amount, 3),
            "estimated_time_minutes": 2 + int(complexity * 2),
            "reasoning": f"Schema/API design task matches my expertise. Complexity score: {complexity:.1f}",
        }

    async def poll_for_jobs(self, interval_seconds: int = 30):
        """Poll the marketplace for matching jobs."""
        logger.info("starting_job_poll", interval=interval_seconds)

        while True:
            try:
                async with httpx.AsyncClient() as client:
                    # Get posted jobs (jobs awaiting bids)
                    response = await client.get(
                        f"{self.bazaar_api_url}/api/jobs",
                        params={"status": "posted", "limit": 10},
                        timeout=30.0,
                    )

                    if response.status_code == 200:
                        data = response.json()
                        jobs = data.get("jobs", []) if isinstance(data, dict) else data
                        for job in jobs:
                            await self._consider_job(job)

            except Exception as e:
                logger.warning("poll_error", error=str(e))

            await asyncio.sleep(interval_seconds)

    async def _consider_job(self, job: dict):
        """Consider bidding on a job."""
        job_id = job.get("job_id")

        # Skip jobs we've already bid on (local cache)
        if job_id in self.jobs_bid_on:
            logger.debug("already_bid_on_job", job_id=job_id)
            return

        # Check if we already have a bid on this job (API check for persistence across restarts)
        if await self._has_existing_bid(job_id):
            logger.debug("existing_bid_found", job_id=job_id)
            self.jobs_bid_on.add(job_id)
            return

        description = job.get("description", "")
        budget = job.get("budget_usd", 0)

        # Evaluate the job
        evaluation = await self.evaluate_job(description, budget)

        if evaluation.get("can_complete"):
            logger.info(
                "submitting_bid",
                job_id=job_id,
                confidence=evaluation.get("confidence"),
                bid=evaluation.get("bid_amount_usd"),
            )
            # Submit the bid
            await self._submit_bid(job_id, evaluation)
            # Mark job as bid on (regardless of success to avoid retries)
            self.jobs_bid_on.add(job_id)

    async def _has_existing_bid(self, job_id: str) -> bool:
        """Check if this agent already has a bid on the job."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.bazaar_api_url}/api/jobs/{job_id}/bids",
                    timeout=10.0,
                )
                if response.status_code == 200:
                    data = response.json()
                    bids = data.get("bids", [])
                    # Check if any bid is from this agent
                    for bid in bids:
                        if bid.get("agent_id") == self.config["agent_id"]:
                            return True
                return False
        except Exception as e:
            logger.warning("bid_check_error", job_id=job_id, error=str(e))
            return False

    async def _submit_bid(self, job_id: str, evaluation: dict):
        """Submit a bid on a job."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.bazaar_api_url}/api/jobs/{job_id}/bids",
                    params={
                        "agent_id": self.config["agent_id"],
                        "price_usd": evaluation.get("bid_amount_usd"),
                        "estimated_quality": evaluation.get("confidence"),
                        "estimated_time_seconds": evaluation.get("estimated_time_minutes", 5) * 60,
                        "approach_summary": evaluation.get("reasoning", "API/Schema design expertise"),
                    },
                    timeout=30.0,
                )

                if response.status_code in (200, 201):
                    logger.info("bid_submitted", job_id=job_id, response=response.json())
                else:
                    logger.warning("bid_failed", job_id=job_id, status=response.status_code, body=response.text)

        except Exception as e:
            logger.error("bid_submission_error", job_id=job_id, error=str(e))


async def run_interactive():
    """Run the agent in interactive mode for testing."""
    agent = SchemaArchitectAgent()

    print("=" * 60)
    print("  SchemaArchitect - Local Agent")
    print("=" * 60)
    print(f"\nAgent ID: {agent.config['agent_id']}")
    print(f"Model: {agent.config['model']}")
    print(f"Base rate: ${agent.config['base_rate_usd']}")
    print("\nCapabilities:")
    for cap, score in agent.config["capabilities"].items():
        print(f"  - {cap}: {score:.2f}")

    print("\n" + "-" * 60)
    print("Enter a task (or 'quit' to exit):")
    print("-" * 60)

    while True:
        try:
            task = input("\nTask> ").strip()
            if task.lower() in ["quit", "exit", "q"]:
                break
            if not task:
                continue

            print("\nExecuting task...")
            result = await agent.execute_task(task)

            if result["success"]:
                print(f"\n[Success] Tokens: {result['tokens_used']} | Cost: ${result['cost_usd']:.4f} | Latency: {result['latency_ms']:.0f}ms")
                print("-" * 60)
                print(result["output"])
                print("-" * 60)
            else:
                print(f"\n[Error] {result['error']}")

        except KeyboardInterrupt:
            break
        except EOFError:
            break

    print("\nGoodbye!")


async def register_agent():
    """Register the agent with the marketplace."""
    agent = SchemaArchitectAgent()

    print("Registering SchemaArchitect with Open Agora marketplace...")
    success = await agent.register_with_marketplace()

    if success:
        print("Registration successful!")
    else:
        print("Registration failed. Check logs for details.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SchemaArchitect Agent")
    parser.add_argument("--register", action="store_true", help="Register agent with marketplace")
    parser.add_argument("--poll", action="store_true", help="Poll for jobs continuously")
    parser.add_argument("--interactive", action="store_true", help="Run in interactive mode")
    args = parser.parse_args()

    if args.register:
        asyncio.run(register_agent())
    elif args.poll:
        agent = SchemaArchitectAgent()
        asyncio.run(agent.poll_for_jobs())
    else:
        # Default to interactive mode
        asyncio.run(run_interactive())
