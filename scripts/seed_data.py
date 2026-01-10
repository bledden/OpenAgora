"""Seed AgentBazaar with demo data."""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bazaar.db import setup_indexes, get_collection, get_db
from bazaar.registry import register_agent
from bazaar.models import AgentCapabilities


async def seed_customer_feedback():
    """Seed customer feedback data (if not exists from agentmesh-r)."""
    db = await get_db()
    collection = db["customer_feedback"]

    count = await collection.count_documents({})
    if count > 0:
        print(f"  customer_feedback already has {count} documents")
        return

    # Sample customer feedback
    feedback = [
        {
            "id": "fb_001",
            "customer_id": "cust_abc123",
            "product": "AgentBazaar Pro",
            "category": "feature_request",
            "sentiment_score": 0.3,
            "priority": "medium",
            "feedback_text": "Would love to see more payment options. Currently only USDC is supported but I'd prefer to pay with ETH or other tokens.",
            "tags": ["payments", "tokens", "feature"],
            "resolved": False,
        },
        {
            "id": "fb_002",
            "customer_id": "cust_def456",
            "product": "AgentBazaar API",
            "category": "praise",
            "sentiment_score": 0.9,
            "priority": "low",
            "feedback_text": "The agent matching is incredibly accurate! Found exactly the right agent for my data analysis needs within seconds.",
            "tags": ["matching", "speed", "positive"],
            "resolved": True,
        },
        {
            "id": "fb_003",
            "customer_id": "cust_ghi789",
            "product": "AgentBazaar Pro",
            "category": "complaint",
            "sentiment_score": -0.7,
            "priority": "high",
            "feedback_text": "Support response times are too slow. Waited 3 days for a response about a payment issue.",
            "tags": ["support", "payments", "response-time"],
            "resolved": False,
        },
        {
            "id": "fb_004",
            "customer_id": "cust_jkl012",
            "product": "AgentBazaar Enterprise",
            "category": "bug",
            "sentiment_score": -0.4,
            "priority": "critical",
            "feedback_text": "Benchmark results sometimes show incorrect scores. Had to re-run benchmarks multiple times.",
            "tags": ["benchmarks", "accuracy", "bug"],
            "resolved": False,
        },
        {
            "id": "fb_005",
            "customer_id": "cust_mno345",
            "product": "AgentBazaar API",
            "category": "suggestion",
            "sentiment_score": 0.5,
            "priority": "medium",
            "feedback_text": "It would be helpful to have a bulk job posting feature for enterprise users with multiple tasks.",
            "tags": ["enterprise", "bulk", "feature"],
            "resolved": False,
        },
        {
            "id": "fb_006",
            "customer_id": "cust_pqr678",
            "product": "AgentBazaar Pro",
            "category": "praise",
            "sentiment_score": 0.85,
            "priority": "low",
            "feedback_text": "The quality scoring by Galileo is a game-changer. Finally have objective measures for agent work quality.",
            "tags": ["quality", "galileo", "positive"],
            "resolved": True,
        },
        {
            "id": "fb_007",
            "customer_id": "cust_stu901",
            "product": "AgentBazaar Enterprise",
            "category": "complaint",
            "sentiment_score": -0.6,
            "priority": "high",
            "feedback_text": "Pricing is not transparent. Hidden fees appeared after completing several jobs.",
            "tags": ["pricing", "transparency", "fees"],
            "resolved": False,
        },
        {
            "id": "fb_008",
            "customer_id": "cust_vwx234",
            "product": "AgentBazaar API",
            "category": "question",
            "sentiment_score": 0.0,
            "priority": "medium",
            "feedback_text": "Is there documentation for the webhook notifications? Can't find it in the docs.",
            "tags": ["documentation", "webhooks", "question"],
            "resolved": True,
        },
    ]

    await collection.insert_many(feedback)
    print(f"  Seeded {len(feedback)} customer feedback documents")


async def seed_agents_quick():
    """Seed pre-configured agents (skip benchmark for speed)."""
    db = await get_db()
    collection = db["bazaar_agents"]

    # Check if agents exist
    count = await collection.count_documents({})
    if count >= 5:
        print(f"  bazaar_agents already has {count} agents")
        return

    # Clear existing agents to re-seed with full set
    if count > 0:
        await collection.delete_many({})
        print(f"  Cleared {count} existing agents to re-seed")

    # Pre-configured agents with realistic scores
    agents = [
        {
            "agent_id": "agent_analyzer",
            "name": "AnalyzerBot",
            "description": "Expert in data analysis, pattern recognition, and extracting insights from structured data",
            "owner_id": "demo_owner",
            "provider": "fireworks",
            "model": "accounts/fireworks/models/llama-v3p3-70b-instruct",
            "capabilities": {
                "summarization": 0.88,
                "sentiment_analysis": 0.82,
                "data_extraction": 0.91,
                "pattern_recognition": 0.89,
                "classification": 0.85,
                "aggregation": 0.92,
                "anomaly_detection": 0.78,
                "code_review": 0.65,
            },
            "capability_embedding": [],  # Would be generated by Voyage
            "base_rate_usd": 0.02,
            "rate_per_1k_tokens": 0.001,
            "rating_avg": 4.7,
            "rating_count": 42,
            "jobs_completed": 42,
            "jobs_failed": 2,
            "total_earned_usd": 156.50,
            "dispute_rate": 0.02,
            "status": "available",
            "wallet_address": "0x1234567890abcdef1234567890abcdef12345678",
        },
        {
            "agent_id": "agent_summarizer",
            "name": "SummaryPro",
            "description": "Specializes in summarization, sentiment analysis, and content condensation",
            "owner_id": "demo_owner",
            "provider": "fireworks",
            "model": "accounts/fireworks/models/llama-v3p3-70b-instruct",
            "capabilities": {
                "summarization": 0.94,
                "sentiment_analysis": 0.91,
                "data_extraction": 0.75,
                "pattern_recognition": 0.72,
                "classification": 0.88,
                "aggregation": 0.70,
                "anomaly_detection": 0.65,
                "code_review": 0.55,
            },
            "capability_embedding": [],
            "base_rate_usd": 0.015,
            "rate_per_1k_tokens": 0.0008,
            "rating_avg": 4.9,
            "rating_count": 67,
            "jobs_completed": 65,
            "jobs_failed": 1,
            "total_earned_usd": 203.25,
            "dispute_rate": 0.01,
            "status": "available",
            "wallet_address": "0xabcdef1234567890abcdef1234567890abcdef12",
        },
        {
            "agent_id": "agent_miner",
            "name": "DataMiner",
            "description": "Focused on data extraction, classification, and structured data processing",
            "owner_id": "demo_owner",
            "provider": "fireworks",
            "model": "accounts/fireworks/models/llama-v3p3-70b-instruct",
            "capabilities": {
                "summarization": 0.72,
                "sentiment_analysis": 0.68,
                "data_extraction": 0.95,
                "pattern_recognition": 0.85,
                "classification": 0.92,
                "aggregation": 0.88,
                "anomaly_detection": 0.82,
                "code_review": 0.78,
            },
            "capability_embedding": [],
            "base_rate_usd": 0.025,
            "rate_per_1k_tokens": 0.0012,
            "rating_avg": 4.5,
            "rating_count": 28,
            "jobs_completed": 26,
            "jobs_failed": 2,
            "total_earned_usd": 89.75,
            "dispute_rate": 0.04,
            "status": "available",
            "wallet_address": "0x567890abcdef1234567890abcdef1234567890ab",
        },
        {
            "agent_id": "agent_coderev",
            "name": "CodeReviewer",
            "description": "Expert code reviewer specializing in security, performance, and best practices",
            "owner_id": "demo_owner",
            "provider": "fireworks",
            "model": "accounts/fireworks/models/llama-v3p3-70b-instruct",
            "capabilities": {
                "summarization": 0.75,
                "sentiment_analysis": 0.55,
                "data_extraction": 0.80,
                "pattern_recognition": 0.92,
                "classification": 0.78,
                "aggregation": 0.65,
                "anomaly_detection": 0.88,
                "code_review": 0.96,
            },
            "capability_embedding": [],
            "base_rate_usd": 0.05,
            "rate_per_1k_tokens": 0.002,
            "rating_avg": 4.8,
            "rating_count": 35,
            "jobs_completed": 33,
            "jobs_failed": 1,
            "total_earned_usd": 275.00,
            "dispute_rate": 0.02,
            "status": "available",
            "wallet_address": "0xCodeReview12345678901234567890123456789ab",
        },
        {
            "agent_id": "agent_anomaly",
            "name": "AnomalyHunter",
            "description": "Specialized in detecting anomalies, fraud patterns, and outlier detection",
            "owner_id": "demo_owner",
            "provider": "fireworks",
            "model": "accounts/fireworks/models/llama-v3p3-70b-instruct",
            "capabilities": {
                "summarization": 0.68,
                "sentiment_analysis": 0.72,
                "data_extraction": 0.85,
                "pattern_recognition": 0.94,
                "classification": 0.88,
                "aggregation": 0.78,
                "anomaly_detection": 0.97,
                "code_review": 0.60,
            },
            "capability_embedding": [],
            "base_rate_usd": 0.04,
            "rate_per_1k_tokens": 0.0015,
            "rating_avg": 4.6,
            "rating_count": 19,
            "jobs_completed": 18,
            "jobs_failed": 1,
            "total_earned_usd": 142.50,
            "dispute_rate": 0.03,
            "status": "available",
            "wallet_address": "0xAnomalyHunt12345678901234567890123456789cd",
        },
    ]

    await collection.insert_many(agents)
    print(f"  Seeded {len(agents)} pre-configured agents")


async def main():
    print("=" * 50)
    print("AgentBazaar Seed Data")
    print("=" * 50)

    # Setup indexes
    print("\n[1] Setting up indexes...")
    await setup_indexes()
    print("  Indexes created")

    # Seed customer feedback
    print("\n[2] Seeding customer feedback...")
    await seed_customer_feedback()

    # Seed agents (quick mode - no benchmarks)
    print("\n[3] Seeding demo agents...")
    await seed_agents_quick()

    print("\n" + "=" * 50)
    print("Seed complete!")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
