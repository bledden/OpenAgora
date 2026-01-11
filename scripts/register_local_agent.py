#!/usr/bin/env python3
"""Register the local SchemaArchitect agent with the marketplace."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

from bazaar.db import init_db, create_agent, get_agent, update_agent
from bazaar.models import AgentStatus

SCHEMA_ARCHITECT = {
    "agent_id": "agent_schema_architect",
    "name": "SchemaArchitect",
    "description": """Expert in API and data schema design. Specializes in REST API design,
OpenAPI/Swagger specs, GraphQL schemas, database modeling (SQL & NoSQL), and schema validation.
Provides best practices recommendations and identifies design anti-patterns. LOCAL AGENT.""",
    "capabilities": {
        "schema_design": 0.96,
        "code_review": 0.88,
        "data_extraction": 0.85,
        "pattern_recognition": 0.90,
        "classification": 0.82,
    },
    "owner_id": "local_demo",
    "wallet_address": "0xSchemaArchitect00000000000000000001",
    "provider": "fireworks",
    "model": "accounts/fireworks/models/llama-v3p3-70b-instruct",
    "base_rate_usd": 0.04,
    "rate_per_1k_tokens": 0.001,
    "rating_avg": 4.85,
    "rating_count": 12,
    "jobs_completed": 15,
    "jobs_failed": 0,
    "status": AgentStatus.AVAILABLE.value,
    "total_earned_usd": 45.20,
    "is_local": True,  # Flag to indicate this is a locally-run agent
}


async def register():
    print("Connecting to database...")
    await init_db()

    # Check if already exists
    existing = await get_agent(SCHEMA_ARCHITECT["agent_id"])

    if existing:
        print(f"Agent {SCHEMA_ARCHITECT['name']} already exists. Updating...")
        await update_agent(SCHEMA_ARCHITECT["agent_id"], SCHEMA_ARCHITECT)
        print("Updated!")
    else:
        print(f"Registering {SCHEMA_ARCHITECT['name']}...")
        await create_agent(SCHEMA_ARCHITECT)
        print("Registered!")

    print(f"\nAgent: {SCHEMA_ARCHITECT['name']}")
    print(f"ID: {SCHEMA_ARCHITECT['agent_id']}")
    print(f"Model: {SCHEMA_ARCHITECT['model'].split('/')[-1]}")
    print(f"Base rate: ${SCHEMA_ARCHITECT['base_rate_usd']}")
    print(f"Capabilities: {list(SCHEMA_ARCHITECT['capabilities'].keys())}")


if __name__ == "__main__":
    asyncio.run(register())
