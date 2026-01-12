#!/usr/bin/env python3
"""Multi-Agent Runner for AgentBazaar.

Runs multiple agents in a single process, loading configs from MongoDB.
This allows deploying many agents on a single Railway service.

Features:
- Loads agent configs from MongoDB (dynamic agent management)
- Runs poll loops for multiple agents concurrently
- Shares HTTP client pool for efficiency
- Hot-reload: periodically checks for new/updated agents
"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
import json

# Add paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env")

import httpx
import structlog
from motor.motor_asyncio import AsyncIOMotorClient

logger = structlog.get_logger()

# Registry of agent executors
AGENT_EXECUTORS = {}


def register_executor(agent_type: str):
    """Decorator to register an agent executor."""
    def decorator(cls):
        AGENT_EXECUTORS[agent_type] = cls
        return cls
    return decorator


class BaseAgentExecutor:
    """Base class for agent executors."""

    def __init__(self, config: dict, http_client: httpx.AsyncClient):
        self.config = config
        self.http = http_client
        self.agent_id = config.get("agent_id")
        self.name = config.get("name", "Unknown")
        self.bazaar_api_url = os.getenv("BAZAAR_API_URL", "http://localhost:8000")
        self.jobs_bid_on: set = set()

    async def execute_task(self, job_description: str, job_context: Optional[dict] = None) -> dict:
        """Execute a task. Override in subclasses."""
        raise NotImplementedError

    async def evaluate_job(self, job_description: str, job_budget: float) -> dict:
        """Evaluate whether to bid on a job. Override in subclasses."""
        raise NotImplementedError


@register_executor("schema_architect")
class SchemaArchitectExecutor(BaseAgentExecutor):
    """Executor for SchemaArchitect agent."""

    SYSTEM_PROMPT = """You are SchemaArchitect, an expert API and schema design agent.
Your specialties: REST API design, GraphQL schemas, database schemas, data modeling."""

    async def execute_task(self, job_description: str, job_context: Optional[dict] = None) -> dict:
        fireworks_key = os.getenv("FIREWORKS_API_KEY")
        if not fireworks_key:
            return {"success": False, "error": "FIREWORKS_API_KEY not set"}

        model = self.config.get("model", "accounts/fireworks/models/llama-v3p3-70b-instruct")

        task_prompt = f"## Task\n{job_description}\n"
        if job_context:
            task_prompt += f"## Context\n{json.dumps(job_context, indent=2)}\n"

        try:
            start = datetime.now(timezone.utc)
            response = await self.http.post(
                "https://api.fireworks.ai/inference/v1/chat/completions",
                headers={"Authorization": f"Bearer {fireworks_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": self.SYSTEM_PROMPT},
                        {"role": "user", "content": task_prompt},
                    ],
                    "temperature": 0.4,
                    "max_tokens": 4096,
                },
                timeout=120.0,
            )
            response.raise_for_status()
            data = response.json()
            latency_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000
            tokens = data.get("usage", {}).get("prompt_tokens", 0) + data.get("usage", {}).get("completion_tokens", 0)

            return {
                "success": True,
                "output": data["choices"][0]["message"]["content"],
                "tokens_used": tokens,
                "latency_ms": round(latency_ms, 2),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # Keywords with weights (higher = stronger match)
    KEYWORDS = {
        # Core specialty (weight 1.0)
        "schema": 1.0, "api": 1.0, "database": 1.0, "graphql": 1.0, "openapi": 1.0,
        "swagger": 1.0, "rest": 0.9, "endpoint": 0.9, "data model": 1.0,
        # Database types (weight 0.9)
        "postgresql": 0.9, "postgres": 0.9, "mysql": 0.9, "mongodb": 0.9, "dynamodb": 0.9,
        "redis": 0.8, "sqlite": 0.8, "sql": 0.9, "nosql": 0.9, "cassandra": 0.9,
        # Schema concepts (weight 0.85)
        "erd": 0.85, "entity relationship": 0.85, "normalization": 0.85, "denormalization": 0.85,
        "foreign key": 0.85, "primary key": 0.85, "index": 0.8, "migration": 0.85,
        "table": 0.7, "column": 0.7, "field": 0.6, "relationship": 0.7,
        # API concepts (weight 0.85)
        "crud": 0.85, "http": 0.7, "json": 0.6, "request": 0.5, "response": 0.5,
        "authentication": 0.7, "authorization": 0.7, "oauth": 0.8, "jwt": 0.8,
        "rate limit": 0.8, "pagination": 0.75, "versioning": 0.75,
        # Design patterns (weight 0.8)
        "microservice": 0.8, "monolith": 0.7, "serverless": 0.7, "event-driven": 0.75,
        "cqrs": 0.85, "event sourcing": 0.85, "domain driven": 0.8, "ddd": 0.8,
        # Tools (weight 0.7)
        "prisma": 0.8, "typeorm": 0.8, "sequelize": 0.8, "sqlalchemy": 0.8,
        "mongoose": 0.8, "drizzle": 0.8, "knex": 0.75,
    }

    async def evaluate_job(self, job_description: str, job_budget: float) -> dict:
        desc_lower = job_description.lower()

        # Calculate weighted match score
        matches = []
        for keyword, weight in self.KEYWORDS.items():
            if keyword in desc_lower:
                matches.append((keyword, weight))

        if not matches:
            return {"can_complete": False, "confidence": 0.2, "reasoning": "No schema/API keywords found"}

        # Calculate confidence based on matches
        total_weight = sum(w for _, w in matches)
        max_weight = max(w for _, w in matches)
        num_matches = len(matches)

        # Confidence: combination of best match + breadth of matches
        confidence = min(0.95, 0.5 + (max_weight * 0.3) + (min(num_matches, 5) * 0.03))

        base_rate = self.config.get("base_rate_usd", 0.04)
        # Higher confidence = willing to bid more competitively
        bid_multiplier = 1.0 + (confidence * 0.5)
        bid_amount = min(base_rate * bid_multiplier, job_budget * 0.85)

        matched_keywords = [kw for kw, _ in sorted(matches, key=lambda x: -x[1])[:5]]
        return {
            "can_complete": True,
            "confidence": round(confidence, 2),
            "bid_amount_usd": round(bid_amount, 3),
            "estimated_time_minutes": max(3, 10 - num_matches),  # More matches = faster
            "reasoning": f"Schema/API design match: {', '.join(matched_keywords)}",
        }


@register_executor("anomaly_hunter")
class AnomalyHunterExecutor(BaseAgentExecutor):
    """Executor for AnomalyHunter agent - anomaly detection specialist."""

    SYSTEM_PROMPT = """You are AnomalyHunter, an expert anomaly detection agent.
Your specialties: Statistical anomaly detection, time-series analysis, root cause analysis,
pattern recognition, data quality assessment, monitoring alert evaluation."""

    async def execute_task(self, job_description: str, job_context: Optional[dict] = None) -> dict:
        fireworks_key = os.getenv("FIREWORKS_API_KEY")
        if not fireworks_key:
            return {"success": False, "error": "FIREWORKS_API_KEY not set"}

        model = self.config.get("model", "accounts/fireworks/models/llama-v3p3-70b-instruct")

        task_prompt = f"""## Anomaly Detection Task
{job_description}

## Analysis Framework
1. Identify data patterns and baselines
2. Detect statistical anomalies (Z-score, IQR, etc.)
3. Analyze temporal patterns and trends
4. Generate root cause hypotheses
5. Provide actionable recommendations

Severity Scale: 1-10 (10 = critical)
Confidence: 0.0-1.0
"""
        if job_context:
            task_prompt += f"\n## Context\n{json.dumps(job_context, indent=2)}\n"

        try:
            start = datetime.now(timezone.utc)
            response = await self.http.post(
                "https://api.fireworks.ai/inference/v1/chat/completions",
                headers={"Authorization": f"Bearer {fireworks_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": self.SYSTEM_PROMPT},
                        {"role": "user", "content": task_prompt},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 4096,
                },
                timeout=120.0,
            )
            response.raise_for_status()
            data = response.json()
            latency_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000
            tokens = data.get("usage", {}).get("prompt_tokens", 0) + data.get("usage", {}).get("completion_tokens", 0)

            return {
                "success": True,
                "output": data["choices"][0]["message"]["content"],
                "tokens_used": tokens,
                "latency_ms": round(latency_ms, 2),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # Keywords with weights (higher = stronger match)
    KEYWORDS = {
        # Core specialty (weight 1.0)
        "anomaly": 1.0, "anomalies": 1.0, "outlier": 1.0, "outliers": 1.0,
        "anomaly detection": 1.0, "outlier detection": 1.0,
        # Time-series (weight 0.95)
        "time-series": 0.95, "time series": 0.95, "timeseries": 0.95, "temporal": 0.9,
        "trend": 0.85, "seasonality": 0.9, "forecast": 0.85, "forecasting": 0.85,
        # Monitoring/Observability (weight 0.9)
        "monitoring": 0.9, "observability": 0.9, "alert": 0.85, "alerting": 0.85,
        "dashboard": 0.7, "metrics": 0.85, "telemetry": 0.9, "logs": 0.7,
        "sre": 0.85, "devops": 0.7, "incident": 0.8, "on-call": 0.75,
        # Statistical concepts (weight 0.9)
        "spike": 0.9, "drift": 0.9, "deviation": 0.9, "variance": 0.85,
        "baseline": 0.9, "threshold": 0.85, "z-score": 0.95, "zscore": 0.95,
        "iqr": 0.9, "percentile": 0.8, "standard deviation": 0.9, "mean": 0.6,
        "statistical": 0.85, "statistics": 0.8,
        # Pattern recognition (weight 0.85)
        "pattern": 0.85, "unusual": 0.85, "abnormal": 0.9, "normal": 0.5,
        "expected": 0.6, "unexpected": 0.85, "strange": 0.7, "weird": 0.7,
        # Data quality (weight 0.8)
        "data quality": 0.85, "missing data": 0.8, "null": 0.5, "corrupt": 0.8,
        "validation": 0.7, "integrity": 0.75, "consistency": 0.7,
        # ML/Detection methods (weight 0.85)
        "isolation forest": 0.95, "dbscan": 0.9, "clustering": 0.8,
        "autoencoder": 0.9, "lstm": 0.85, "prophet": 0.85, "arima": 0.85,
        # Root cause (weight 0.9)
        "root cause": 0.95, "diagnosis": 0.85, "investigate": 0.8, "troubleshoot": 0.85,
        "debug": 0.7, "why": 0.4, "cause": 0.6,
        # Industry terms (weight 0.8)
        "apm": 0.85, "prometheus": 0.8, "grafana": 0.75, "datadog": 0.8,
        "splunk": 0.8, "elastic": 0.75, "kibana": 0.75, "newrelic": 0.8,
        "cloudwatch": 0.8, "sentry": 0.75,
    }

    async def evaluate_job(self, job_description: str, job_budget: float) -> dict:
        desc_lower = job_description.lower()

        # Calculate weighted match score
        matches = []
        for keyword, weight in self.KEYWORDS.items():
            if keyword in desc_lower:
                matches.append((keyword, weight))

        if not matches:
            return {"can_complete": False, "confidence": 0.2, "reasoning": "No anomaly/monitoring keywords found"}

        # Calculate confidence based on matches
        total_weight = sum(w for _, w in matches)
        max_weight = max(w for _, w in matches)
        num_matches = len(matches)

        # Confidence: combination of best match + breadth of matches
        confidence = min(0.95, 0.5 + (max_weight * 0.3) + (min(num_matches, 5) * 0.03))

        base_rate = self.config.get("base_rate_usd", 0.05)
        bid_multiplier = 1.0 + (confidence * 0.5)
        bid_amount = min(base_rate * bid_multiplier, job_budget * 0.85)

        matched_keywords = [kw for kw, _ in sorted(matches, key=lambda x: -x[1])[:5]]
        return {
            "can_complete": True,
            "confidence": round(confidence, 2),
            "bid_amount_usd": round(bid_amount, 3),
            "estimated_time_minutes": max(2, 8 - num_matches),
            "reasoning": f"Anomaly detection match: {', '.join(matched_keywords)}",
        }


@register_executor("code_reviewer")
class CodeReviewerExecutor(BaseAgentExecutor):
    """Executor for CodeReviewer agent."""

    SYSTEM_PROMPT = """You are CodeReviewer, an expert code review agent.
Your specialties: Code quality analysis, security review, performance optimization,
best practices enforcement, refactoring suggestions."""

    async def execute_task(self, job_description: str, job_context: Optional[dict] = None) -> dict:
        fireworks_key = os.getenv("FIREWORKS_API_KEY")
        if not fireworks_key:
            return {"success": False, "error": "FIREWORKS_API_KEY not set"}

        model = self.config.get("model", "accounts/fireworks/models/llama-v3p3-70b-instruct")

        task_prompt = f"## Code Review Task\n{job_description}\n"
        if job_context:
            task_prompt += f"## Context\n{json.dumps(job_context, indent=2)}\n"

        try:
            start = datetime.now(timezone.utc)
            response = await self.http.post(
                "https://api.fireworks.ai/inference/v1/chat/completions",
                headers={"Authorization": f"Bearer {fireworks_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": self.SYSTEM_PROMPT},
                        {"role": "user", "content": task_prompt},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 4096,
                },
                timeout=120.0,
            )
            response.raise_for_status()
            data = response.json()
            latency_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000
            tokens = data.get("usage", {}).get("prompt_tokens", 0) + data.get("usage", {}).get("completion_tokens", 0)

            return {
                "success": True,
                "output": data["choices"][0]["message"]["content"],
                "tokens_used": tokens,
                "latency_ms": round(latency_ms, 2),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # Keywords with weights (higher = stronger match)
    KEYWORDS = {
        # Core specialty (weight 1.0)
        "code review": 1.0, "review code": 1.0, "pull request": 0.95, "pr review": 0.95,
        "code quality": 1.0, "refactor": 0.95, "refactoring": 0.95,
        # Security (weight 0.95)
        "security": 0.95, "vulnerability": 0.95, "vulnerabilities": 0.95, "exploit": 0.9,
        "injection": 0.9, "xss": 0.95, "csrf": 0.95, "sql injection": 0.95,
        "authentication": 0.85, "authorization": 0.85, "owasp": 0.95, "penetration": 0.85,
        "secure": 0.7, "insecure": 0.85, "hardening": 0.85,
        # Code analysis (weight 0.9)
        "lint": 0.9, "linting": 0.9, "static analysis": 0.95, "code smell": 0.9,
        "complexity": 0.85, "cyclomatic": 0.9, "maintainability": 0.85,
        "technical debt": 0.9, "clean code": 0.9, "solid": 0.8, "dry": 0.75,
        # Testing (weight 0.85)
        "test": 0.75, "testing": 0.8, "unit test": 0.9, "integration test": 0.9,
        "coverage": 0.85, "tdd": 0.85, "bdd": 0.8, "mock": 0.7, "stub": 0.7,
        "jest": 0.75, "pytest": 0.75, "mocha": 0.75, "cypress": 0.8,
        # Bug fixing (weight 0.85)
        "bug": 0.85, "fix": 0.7, "debug": 0.8, "debugging": 0.85, "error": 0.6,
        "issue": 0.5, "problem": 0.4, "broken": 0.7, "crash": 0.8,
        # Performance (weight 0.85)
        "performance": 0.85, "optimize": 0.85, "optimization": 0.85, "slow": 0.7,
        "fast": 0.5, "speed": 0.7, "memory": 0.75, "leak": 0.8, "profiling": 0.85,
        "bottleneck": 0.85, "latency": 0.8, "throughput": 0.8,
        # Languages/Frameworks (weight 0.7)
        "python": 0.7, "javascript": 0.7, "typescript": 0.7, "java": 0.7,
        "react": 0.7, "node": 0.65, "go": 0.65, "rust": 0.7, "c++": 0.7,
        # Best practices (weight 0.8)
        "best practice": 0.85, "convention": 0.75, "standard": 0.6, "pattern": 0.7,
        "anti-pattern": 0.9, "architecture": 0.8, "design pattern": 0.85,
        # Documentation (weight 0.7)
        "documentation": 0.7, "comment": 0.6, "docstring": 0.75, "readme": 0.65,
        # CI/CD (weight 0.75)
        "ci": 0.7, "cd": 0.65, "pipeline": 0.7, "github actions": 0.75,
        "jenkins": 0.7, "gitlab": 0.7, "build": 0.5,
    }

    async def evaluate_job(self, job_description: str, job_budget: float) -> dict:
        desc_lower = job_description.lower()

        # Calculate weighted match score
        matches = []
        for keyword, weight in self.KEYWORDS.items():
            if keyword in desc_lower:
                matches.append((keyword, weight))

        if not matches:
            return {"can_complete": False, "confidence": 0.2, "reasoning": "No code review keywords found"}

        # Calculate confidence based on matches
        total_weight = sum(w for _, w in matches)
        max_weight = max(w for _, w in matches)
        num_matches = len(matches)

        # Confidence: combination of best match + breadth of matches
        confidence = min(0.95, 0.5 + (max_weight * 0.3) + (min(num_matches, 5) * 0.03))

        base_rate = self.config.get("base_rate_usd", 0.03)
        bid_multiplier = 1.0 + (confidence * 0.5)
        bid_amount = min(base_rate * bid_multiplier, job_budget * 0.85)

        matched_keywords = [kw for kw, _ in sorted(matches, key=lambda x: -x[1])[:5]]
        return {
            "can_complete": True,
            "confidence": round(confidence, 2),
            "bid_amount_usd": round(bid_amount, 3),
            "estimated_time_minutes": max(3, 10 - num_matches),
            "reasoning": f"Code review match: {', '.join(matched_keywords)}",
        }


class MultiAgentRunner:
    """Runs multiple agents from MongoDB configs in a single process."""

    def __init__(self):
        self.mongo_uri = os.getenv("MONGODB_URI")
        self.bazaar_api_url = os.getenv("BAZAAR_API_URL", "http://localhost:8000")
        self.poll_interval = int(os.getenv("AGENT_POLL_INTERVAL", "30"))
        self.reload_interval = int(os.getenv("AGENT_RELOAD_INTERVAL", "300"))  # 5 min

        self.agents: dict[str, BaseAgentExecutor] = {}
        self.http_client: Optional[httpx.AsyncClient] = None
        self.mongo_client: Optional[AsyncIOMotorClient] = None
        self.running = False

    async def start(self):
        """Start the multi-agent runner."""
        logger.info("starting_multi_agent_runner")

        # Initialize shared HTTP client
        self.http_client = httpx.AsyncClient(timeout=60.0)

        # Initialize MongoDB client if URI provided
        if self.mongo_uri:
            self.mongo_client = AsyncIOMotorClient(self.mongo_uri)
            logger.info("mongodb_connected")

        self.running = True

        # Load initial agents
        await self._load_agents()

        # Start tasks
        tasks = [
            asyncio.create_task(self._poll_loop()),
            asyncio.create_task(self._reload_loop()),
        ]

        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("runner_shutting_down")
        finally:
            await self._cleanup()

    async def _load_agents(self):
        """Load agent configs from MongoDB or environment."""

        if self.mongo_client:
            await self._load_agents_from_mongo()
        else:
            # Fallback: load from environment/hardcoded configs
            await self._load_default_agents()

    async def _load_agents_from_mongo(self):
        """Load active agents from MongoDB agents collection."""
        try:
            db = self.mongo_client.get_database("bazaar")
            collection = db.get_collection("agents")

            # Find agents marked as "managed" (run by this runner)
            cursor = collection.find({
                "managed": True,
                "status": {"$in": ["available", "busy"]},
            })

            agent_count = 0
            async for agent_doc in cursor:
                agent_id = agent_doc.get("agent_id")
                agent_type = agent_doc.get("agent_type", "schema_architect")

                if agent_id in self.agents:
                    continue  # Already loaded

                executor_cls = AGENT_EXECUTORS.get(agent_type)
                if executor_cls:
                    self.agents[agent_id] = executor_cls(agent_doc, self.http_client)
                    agent_count += 1
                    logger.info("agent_loaded", agent_id=agent_id, type=agent_type)
                else:
                    logger.warning("unknown_agent_type", type=agent_type)

            logger.info("agents_loaded_from_mongo", count=agent_count)

        except Exception as e:
            logger.error("mongo_load_failed", error=str(e))

    async def _load_default_agents(self):
        """Load default agents (when MongoDB not available)."""

        # Register agents via API and add to runner
        default_agents = [
            {
                "agent_id": None,  # Will be assigned by server
                "name": "SchemaArchitect",
                "agent_type": "schema_architect",
                "description": "Expert in API and schema design. REST, GraphQL, databases.",
                "capabilities": {
                    "schema_design": 0.96,
                    "code_review": 0.88,
                    "data_extraction": 0.85,
                },
                "base_rate_usd": 0.04,
                "model": "accounts/fireworks/models/llama-v3p3-70b-instruct",
            },
            {
                "agent_id": None,
                "name": "AnomalyHunter",
                "agent_type": "anomaly_hunter",
                "description": "Anomaly detection specialist. Time-series, patterns, root cause.",
                "capabilities": {
                    "anomaly_detection": 0.95,
                    "pattern_recognition": 0.92,
                    "data_extraction": 0.88,
                    "classification": 0.85,
                },
                "base_rate_usd": 0.05,
                "model": "accounts/fireworks/models/llama-v3p3-70b-instruct",
            },
            {
                "agent_id": None,
                "name": "CodeReviewer",
                "agent_type": "code_reviewer",
                "description": "Code review expert. Security, quality, performance.",
                "capabilities": {
                    "code_review": 0.94,
                    "security_analysis": 0.90,
                    "code_generation": 0.85,
                },
                "base_rate_usd": 0.03,
                "model": "accounts/fireworks/models/llama-v3p3-70b-instruct",
            },
        ]

        for agent_config in default_agents:
            try:
                # Register with marketplace
                reg_data = {
                    **agent_config,
                    "owner_id": os.getenv("AGENT_OWNER_ID", "multi_runner"),
                    "wallet_address": os.getenv("AGENT_WALLET", f"0xMultiRunner{agent_config['name']}"),
                    "status": "available",
                }

                response = await self.http_client.post(
                    f"{self.bazaar_api_url}/api/agents/register",
                    json=reg_data,
                    timeout=30.0,
                )

                if response.status_code in [200, 201, 409]:
                    data = response.json()
                    agent_id = data.get("agent_id") or agent_config.get("agent_id")

                    if agent_id:
                        agent_config["agent_id"] = agent_id
                        executor_cls = AGENT_EXECUTORS.get(agent_config["agent_type"])
                        if executor_cls:
                            self.agents[agent_id] = executor_cls(agent_config, self.http_client)
                            logger.info("agent_registered", agent_id=agent_id, name=agent_config["name"])
                else:
                    logger.warning("agent_registration_failed",
                                   name=agent_config["name"],
                                   status=response.status_code)

            except Exception as e:
                logger.error("agent_init_failed", name=agent_config["name"], error=str(e))

        logger.info("default_agents_loaded", count=len(self.agents))

    async def _poll_loop(self):
        """Main polling loop for all agents."""

        while self.running:
            try:
                # Poll jobs for each agent concurrently
                tasks = [
                    self._poll_for_agent(agent_id, executor)
                    for agent_id, executor in self.agents.items()
                ]

                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)

            except Exception as e:
                logger.warning("poll_loop_error", error=str(e))

            await asyncio.sleep(self.poll_interval)

    async def _poll_for_agent(self, agent_id: str, executor: BaseAgentExecutor):
        """Poll for jobs for a specific agent."""

        try:
            # Send heartbeat
            await self.http_client.post(
                f"{self.bazaar_api_url}/api/agents/{agent_id}/heartbeat",
                json={"status": "available", "current_capacity": 1},
                timeout=10.0,
            )

            # Get posted jobs
            response = await self.http_client.get(
                f"{self.bazaar_api_url}/api/jobs",
                params={"status": "posted", "limit": 10},
                timeout=30.0,
            )

            if response.status_code == 200:
                data = response.json()
                jobs = data.get("jobs", []) if isinstance(data, dict) else data

                for job in jobs:
                    await self._consider_job_for_agent(job, agent_id, executor)

        except Exception as e:
            logger.warning("agent_poll_error", agent_id=agent_id, error=str(e))

    async def _consider_job_for_agent(self, job: dict, agent_id: str, executor: BaseAgentExecutor):
        """Consider bidding on a job for a specific agent."""

        job_id = job.get("job_id")

        # Check if already bid
        if job_id in executor.jobs_bid_on:
            return

        # Check if agent meets required capabilities
        required_caps = job.get("required_capabilities", [])
        if required_caps:
            agent_caps = executor.config.get("capabilities", {})
            min_score = job.get("min_capability_score", 0.7)
            can_meet_requirements = True
            for cap in required_caps:
                if agent_caps.get(cap, 0) < min_score:
                    can_meet_requirements = False
                    break
            if not can_meet_requirements:
                executor.jobs_bid_on.add(job_id)  # Don't check again
                return

        # Check for existing bid via API
        try:
            response = await self.http_client.get(
                f"{self.bazaar_api_url}/api/jobs/{job_id}/bids",
                timeout=10.0,
            )
            if response.status_code == 200:
                bids = response.json().get("bids", [])
                for bid in bids:
                    if bid.get("agent_id") == agent_id:
                        executor.jobs_bid_on.add(job_id)
                        return
        except Exception:
            pass

        # Evaluate job
        description = job.get("description", "")
        budget = job.get("budget_usd", 0)

        evaluation = await executor.evaluate_job(description, budget)

        if evaluation.get("can_complete"):
            # Submit bid
            try:
                response = await self.http_client.post(
                    f"{self.bazaar_api_url}/api/jobs/{job_id}/bids",
                    params={
                        "agent_id": agent_id,
                        "price_usd": evaluation.get("bid_amount_usd"),
                        "estimated_quality": evaluation.get("confidence"),
                        "estimated_time_seconds": evaluation.get("estimated_time_minutes", 5) * 60,
                        "approach_summary": evaluation.get("reasoning"),
                    },
                    timeout=30.0,
                )

                if response.status_code in (200, 201):
                    logger.info("bid_submitted",
                               agent_id=agent_id,
                               job_id=job_id,
                               price=evaluation.get("bid_amount_usd"))

            except Exception as e:
                logger.warning("bid_failed", agent_id=agent_id, job_id=job_id, error=str(e))

        executor.jobs_bid_on.add(job_id)

    async def _reload_loop(self):
        """Periodically reload agents from MongoDB."""

        while self.running:
            await asyncio.sleep(self.reload_interval)

            if self.mongo_client:
                logger.info("reloading_agents")
                await self._load_agents_from_mongo()

    async def _cleanup(self):
        """Cleanup resources."""

        if self.http_client:
            await self.http_client.aclose()

        if self.mongo_client:
            self.mongo_client.close()


async def main():
    """Main entry point."""
    runner = MultiAgentRunner()
    await runner.start()


if __name__ == "__main__":
    asyncio.run(main())
