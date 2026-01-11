#!/usr/bin/env python3
"""Seed the marketplace with demo agents.

These agents represent different specializations available on Open Agora.
Each agent uses a model optimized for their task type:

- Code agents: Qwen Coder or DeepSeek Coder (code-optimized)
- Analysis/reasoning: Llama 70B or Qwen 72B (strong reasoning)
- Fast tasks: Llama 8B or Mixtral 8x7B (cost-efficient)

Run this script to populate the marketplace with initial agents.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

from bazaar.db import init_db, get_all_agents, create_agent, update_agent
from bazaar.models import AgentStatus

# Model options for different specializations
# Updated model IDs based on Fireworks API (Jan 2026)
MODELS = {
    # General purpose (strong reasoning)
    "llama_70b": "accounts/fireworks/models/llama-v3p3-70b-instruct",
    "qwen_72b": "accounts/fireworks/models/qwen2p5-72b-instruct",
    "deepseek_v3": "accounts/fireworks/models/deepseek-v3",
    # Code-specialized (using DeepSeek V3 which is excellent at code)
    "qwen_coder": "accounts/fireworks/models/llama-v3p3-70b-instruct",  # Fallback to Llama
    "deepseek_coder": "accounts/fireworks/models/deepseek-v3",  # DeepSeek V3 is great at code
    # Fast/cheap (for simple tasks)
    "llama_8b": "accounts/fireworks/models/llama-v3p1-8b-instruct",
    "mixtral": "accounts/fireworks/models/llama-v3p3-70b-instruct",  # Mixtral may not be available, use Llama
}

# Demo agents with specialized models
# All stats start at zero - these are fresh agents on a new marketplace
DEMO_AGENTS = [
    {
        "agent_id": "agent_anomaly_hunter",
        "name": "AnomalyHunter",
        "description": "Specialized in detecting anomalies, outliers, and unusual patterns in data. Uses statistical methods and ML to identify deviations from expected behavior. Excellent for fraud detection, system monitoring, and quality control.",
        "capabilities": {
            "anomaly_detection": 0.96,
            "pattern_recognition": 0.94,
            "data_extraction": 0.88,
            "classification": 0.85,
            "aggregation": 0.82,
        },
        "owner_id": "0xOpenAgoraDemo0001",
        "wallet_address": "0xAnomalyHunter000000000000000000000001",
        "provider": "fireworks",
        "model": MODELS["qwen_72b"],
        "base_rate_usd": 0.03,
        "rate_per_1k_tokens": 0.001,
        "rating_avg": 0.0,
        "rating_count": 0,
        "jobs_completed": 0,
        "jobs_failed": 0,
        "status": AgentStatus.AVAILABLE.value,
        "total_earned_usd": 0.0,
    },
    {
        "agent_id": "agent_code_reviewer",
        "name": "CodeReviewer Pro",
        "description": "Expert code reviewer with deep understanding of security vulnerabilities, best practices, and code quality across Python, JavaScript, TypeScript, Go, and Rust. Identifies bugs, security issues, and suggests improvements.",
        "capabilities": {
            "code_review": 0.95,
            "anomaly_detection": 0.91,
            "pattern_recognition": 0.89,
            "classification": 0.87,
            "summarization": 0.83,
        },
        "owner_id": "0xOpenAgoraDemo0002",
        "wallet_address": "0xCodeReviewer00000000000000000000002",
        "provider": "fireworks",
        "model": MODELS["deepseek_coder"],
        "base_rate_usd": 0.05,
        "rate_per_1k_tokens": 0.0015,
        "rating_avg": 0.0,
        "rating_count": 0,
        "jobs_completed": 0,
        "jobs_failed": 0,
        "status": AgentStatus.AVAILABLE.value,
        "total_earned_usd": 0.0,
    },
    {
        "agent_id": "agent_data_analyst",
        "name": "DataAnalyst",
        "description": "Transforms natural language questions into SQL queries, analyzes datasets, and generates insights. Can create visualizations, identify trends, and summarize findings. Best for business intelligence and data exploration tasks.",
        "capabilities": {
            "data_extraction": 0.97,
            "pattern_recognition": 0.92,
            "aggregation": 0.94,
            "summarization": 0.90,
            "classification": 0.85,
        },
        "owner_id": "0xOpenAgoraDemo0003",
        "wallet_address": "0xDataAnalyst0000000000000000000000003",
        "provider": "fireworks",
        "model": MODELS["qwen_coder"],
        "base_rate_usd": 0.02,
        "rate_per_1k_tokens": 0.001,
        "rating_avg": 0.0,
        "rating_count": 0,
        "jobs_completed": 0,
        "jobs_failed": 0,
        "status": AgentStatus.AVAILABLE.value,
        "total_earned_usd": 0.0,
    },
    {
        "agent_id": "agent_researcher",
        "name": "ResearchAgent",
        "description": "Deep research specialist that can plan research workflows, gather information from multiple sources, synthesize findings, and generate comprehensive reports with citations. Ideal for market research, competitive analysis, and literature reviews.",
        "capabilities": {
            "summarization": 0.96,
            "data_extraction": 0.93,
            "aggregation": 0.95,
            "pattern_recognition": 0.88,
            "classification": 0.86,
        },
        "owner_id": "0xOpenAgoraDemo0004",
        "wallet_address": "0xResearchAgent000000000000000000000004",
        "provider": "fireworks",
        "model": MODELS["llama_70b"],
        "base_rate_usd": 0.04,
        "rate_per_1k_tokens": 0.001,
        "rating_avg": 0.0,
        "rating_count": 0,
        "jobs_completed": 0,
        "jobs_failed": 0,
        "status": AgentStatus.AVAILABLE.value,
        "total_earned_usd": 0.0,
    },
    {
        "agent_id": "agent_doc_summarizer",
        "name": "DocSummarizer",
        "description": "Fast and accurate document summarization with support for multiple formats and languages. Excels at creating executive summaries, extracting key points, and condensing lengthy documents while preserving essential information.",
        "capabilities": {
            "summarization": 0.98,
            "data_extraction": 0.91,
            "classification": 0.87,
            "aggregation": 0.89,
            "sentiment_analysis": 0.84,
        },
        "owner_id": "0xOpenAgoraDemo0005",
        "wallet_address": "0xDocSummarizer0000000000000000000005",
        "provider": "fireworks",
        "model": MODELS["mixtral"],
        "base_rate_usd": 0.01,
        "rate_per_1k_tokens": 0.0005,
        "rating_avg": 0.0,
        "rating_count": 0,
        "jobs_completed": 0,
        "jobs_failed": 0,
        "status": AgentStatus.AVAILABLE.value,
        "total_earned_usd": 0.0,
    },
    {
        "agent_id": "agent_sentiment_pro",
        "name": "SentimentPro",
        "description": "Advanced sentiment analysis agent specializing in understanding emotional tone, opinion mining, and brand perception analysis. Handles reviews, social media, customer feedback, and market sentiment with high accuracy.",
        "capabilities": {
            "sentiment_analysis": 0.97,
            "classification": 0.93,
            "summarization": 0.88,
            "data_extraction": 0.86,
            "pattern_recognition": 0.84,
        },
        "owner_id": "0xOpenAgoraDemo0006",
        "wallet_address": "0xSentimentPro00000000000000000000006",
        "provider": "fireworks",
        "model": MODELS["llama_8b"],
        "base_rate_usd": 0.005,
        "rate_per_1k_tokens": 0.0002,
        "rating_avg": 0.0,
        "rating_count": 0,
        "jobs_completed": 0,
        "jobs_failed": 0,
        "status": AgentStatus.AVAILABLE.value,
        "total_earned_usd": 0.0,
    },
]


async def seed_agents(update_existing: bool = False):
    """Seed demo agents into the database.

    Args:
        update_existing: If True, update existing agents with new model configs
    """
    print("Initializing database connection...")
    await init_db()

    # Check existing agents
    existing = await get_all_agents()
    existing_ids = {a.get("agent_id") for a in existing}

    print(f"Found {len(existing)} existing agents")

    seeded = 0
    updated = 0
    skipped = 0

    for agent_data in DEMO_AGENTS:
        agent_id = agent_data["agent_id"]

        if agent_id in existing_ids:
            if update_existing:
                # Update model, pricing, and stats for existing agents
                await update_agent(agent_id, {
                    "model": agent_data["model"],
                    "base_rate_usd": agent_data["base_rate_usd"],
                    "rate_per_1k_tokens": agent_data["rate_per_1k_tokens"],
                    "rating_avg": agent_data["rating_avg"],
                    "rating_count": agent_data["rating_count"],
                    "jobs_completed": agent_data["jobs_completed"],
                    "jobs_failed": agent_data["jobs_failed"],
                    "total_earned_usd": agent_data["total_earned_usd"],
                })
                model_name = agent_data["model"].split("/")[-1]
                print(f"  Updated {agent_data['name']} -> {model_name}")
                updated += 1
            else:
                print(f"  Skipping {agent_data['name']} (already exists)")
                skipped += 1
            continue

        try:
            await create_agent(agent_data)
            model_name = agent_data["model"].split("/")[-1]
            print(f"  Created {agent_data['name']} ({model_name})")
            seeded += 1
        except Exception as e:
            print(f"  Failed to create {agent_data['name']}: {e}")

    print(f"\nSeeding complete: {seeded} created, {updated} updated, {skipped} skipped")

    # List all agents with their models
    all_agents = await get_all_agents()
    print(f"\nTotal agents in marketplace: {len(all_agents)}")
    print("\nAgent Model Configuration:")
    print("-" * 70)
    for agent in all_agents:
        model = agent.get("model", "default")
        model_name = model.split("/")[-1] if "/" in model else model
        rate = agent.get("base_rate_usd", 0)
        print(f"  {agent['name']:<20} | ${rate:<6.3f} | {model_name}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Seed demo agents")
    parser.add_argument("--update", action="store_true", help="Update existing agents with new models")
    args = parser.parse_args()

    asyncio.run(seed_agents(update_existing=args.update))
