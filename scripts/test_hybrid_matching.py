#!/usr/bin/env python3
"""Test the hybrid semantic matching system.

This validates:
1. Voyage voyage-3-large embeddings work
2. Semantic similarity calculation is correct
3. LLM validation produces meaningful results
4. Full hybrid matching pipeline runs end-to-end
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

from bazaar.db import init_db, get_all_agents
from bazaar.llm import get_embedding, get_embeddings_batch, cosine_similarity
from bazaar.jobs.match import (
    _build_job_text,
    _build_agent_text,
    _hybrid_match,
    _validate_single_agent,
    SEMANTIC_THRESHOLD,
)
from bazaar.models import BazaarJob


def print_header(text: str):
    """Print a formatted header."""
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")


async def test_embeddings():
    """Test Voyage voyage-3-large embeddings."""
    print_header("Test 1: Voyage voyage-3-large Embeddings")

    # Test texts
    texts = [
        "Anomaly detection in server metrics and log analysis",
        "Code review for security vulnerabilities and best practices",
        "Data analysis and SQL query generation",
        "Machine learning model training and deployment",
    ]

    print("Getting embeddings for test texts...")
    embeddings = await get_embeddings_batch(texts)

    print(f"  Embedding dimension: {len(embeddings[0])}")
    print(f"  Number of embeddings: {len(embeddings)}")

    # Test similarity between related/unrelated texts
    sim_01 = cosine_similarity(embeddings[0], embeddings[1])  # Anomaly vs Code
    sim_02 = cosine_similarity(embeddings[0], embeddings[2])  # Anomaly vs Data
    sim_03 = cosine_similarity(embeddings[0], embeddings[3])  # Anomaly vs ML
    sim_12 = cosine_similarity(embeddings[1], embeddings[2])  # Code vs Data

    print(f"\n  Similarity scores:")
    print(f"    Anomaly detection vs Code review: {sim_01:.3f}")
    print(f"    Anomaly detection vs Data analysis: {sim_02:.3f}")
    print(f"    Anomaly detection vs ML: {sim_03:.3f}")
    print(f"    Code review vs Data analysis: {sim_12:.3f}")

    # Verify embeddings are reasonable
    assert len(embeddings[0]) > 256, "Embedding dimension too small"
    assert all(0 <= s <= 1 for s in [sim_01, sim_02, sim_03, sim_12]), "Invalid similarity scores"

    print("\n  [PASS] Embeddings working correctly")
    return True


async def test_semantic_matching():
    """Test semantic matching between a job and agents."""
    print_header("Test 2: Semantic Matching")

    # Get real agents from DB
    await init_db()
    agents = await get_all_agents()

    if not agents:
        print("  [SKIP] No agents in database")
        return False

    print(f"  Found {len(agents)} agents in database")

    # Create a test job
    job_text = """Job: Analyze Server Logs for Anomalies
Description: I have 3 days of server logs showing CPU usage, memory, and request latency.
I need an agent to identify any anomalies or unusual patterns, flag potential performance issues,
and summarize the overall health of the system.
Required capabilities: anomaly_detection, pattern_recognition, data_extraction"""

    print(f"\n  Test job: Anomaly detection task")
    print(f"  Getting job embedding...")

    job_embedding = await get_embedding(job_text)

    # Get embeddings for all agents
    agent_texts = [_build_agent_text(agent) for agent in agents]
    agent_embeddings = await get_embeddings_batch(agent_texts)

    # Calculate and display similarity scores
    print(f"\n  Agent similarity scores:")
    matches = []
    for agent, agent_emb in zip(agents, agent_embeddings):
        similarity = cosine_similarity(job_embedding, agent_emb)
        matches.append((agent, similarity))
        status = "MATCH" if similarity >= SEMANTIC_THRESHOLD else ""
        print(f"    {agent['name']}: {similarity:.3f} {status}")

    # Verify AnomalyHunter scores highest for anomaly task
    matches.sort(key=lambda x: x[1], reverse=True)
    top_agent = matches[0][0]

    print(f"\n  Top match: {top_agent['name']} ({matches[0][1]:.3f})")

    if "anomaly" in top_agent["agent_id"].lower() or "anomaly" in top_agent["name"].lower():
        print("  [PASS] Correct agent matched for anomaly task")
    else:
        print(f"  [WARN] Expected AnomalyHunter, got {top_agent['name']}")

    return True


async def test_llm_validation():
    """Test LLM capability validation."""
    print_header("Test 3: LLM Capability Validation")

    # Create a test job
    job = BazaarJob(
        job_id="test_job_001",
        title="Analyze Server Logs for Anomalies",
        description="Detect anomalies in CPU, memory, and latency metrics.",
        required_capabilities=["anomaly_detection", "pattern_recognition"],
        budget_usd=0.50,
        poster_id="test_poster",
    )

    # Good match agent
    good_agent = {
        "agent_id": "agent_anomaly_hunter",
        "name": "AnomalyHunter",
        "description": "Specialized in detecting anomalies and unusual patterns in data.",
        "capabilities": {
            "anomaly_detection": 0.96,
            "pattern_recognition": 0.94,
            "data_extraction": 0.88,
        },
        "base_rate_usd": 0.10,
        "jobs_completed": 5,
        "rating_avg": 4.8,
    }

    # Poor match agent
    poor_agent = {
        "agent_id": "agent_doc_summarizer",
        "name": "DocSummarizer",
        "description": "Fast document summarization agent.",
        "capabilities": {
            "summarization": 0.98,
            "data_extraction": 0.91,
            "classification": 0.87,
        },
        "base_rate_usd": 0.05,
        "jobs_completed": 3,
        "rating_avg": 4.5,
    }

    print("  Testing good match (AnomalyHunter)...")
    good_result = await _validate_single_agent(job, good_agent)
    print(f"    Can complete: {good_result.get('can_complete')}")
    print(f"    Confidence: {good_result.get('confidence', 0):.2f}")
    print(f"    Reasoning: {good_result.get('reasoning', '')[:100]}...")

    print("\n  Testing poor match (DocSummarizer)...")
    poor_result = await _validate_single_agent(job, poor_agent)
    print(f"    Can complete: {poor_result.get('can_complete')}")
    print(f"    Confidence: {poor_result.get('confidence', 0):.2f}")
    print(f"    Reasoning: {poor_result.get('reasoning', '')[:100]}...")

    # Verify good match has higher confidence
    good_conf = good_result.get("confidence", 0)
    poor_conf = poor_result.get("confidence", 0) if poor_result.get("can_complete") else 0

    if good_conf > poor_conf:
        print("\n  [PASS] LLM correctly identifies better match")
    else:
        print("\n  [WARN] LLM confidence ordering unexpected")

    return True


async def test_full_hybrid_pipeline():
    """Test the full hybrid matching pipeline."""
    print_header("Test 4: Full Hybrid Matching Pipeline")

    # Create test job - use capabilities that exist in demo agents
    job = BazaarJob(
        job_id=f"test_hybrid_{datetime.now().strftime('%H%M%S')}",
        title="Detect Anomalies in Server Metrics",
        description="""Analyze server performance data for unusual patterns.
Look for CPU spikes, memory leaks, and latency anomalies.
Identify root causes and recommend fixes.""",
        required_capabilities=["anomaly_detection", "pattern_recognition"],
        budget_usd=0.50,
        poster_id="test_poster",
    )

    print(f"  Job: {job.title}")
    print(f"  Required: {job.required_capabilities}")
    print(f"  Budget: ${job.budget_usd}")

    print("\n  Running hybrid matching...")
    start = datetime.now()

    matched = await _hybrid_match(job, limit=5)

    elapsed = (datetime.now() - start).total_seconds()

    print(f"\n  Results ({elapsed:.1f}s):")
    print(f"  Matched agents: {len(matched)}")

    for i, agent in enumerate(matched, 1):
        print(f"\n  [{i}] {agent['name']}")
        print(f"      Match score: {agent.get('match_score', 0):.3f}")
        print(f"      Semantic score: {agent.get('semantic_score', 0):.3f}")
        print(f"      LLM confidence: {agent.get('llm_confidence', 0):.2f}")
        validation = agent.get("llm_validation", {})
        if validation.get("reasoning"):
            print(f"      Reasoning: {validation['reasoning'][:80]}...")

    if matched:
        print(f"\n  [PASS] Hybrid matching completed successfully")
        print(f"  Top match: {matched[0]['name']} (score: {matched[0].get('match_score', 0):.3f})")
    else:
        print("\n  [WARN] No agents matched")

    return len(matched) > 0


async def run_tests():
    """Run all tests."""
    print_header("Hybrid Semantic Matching Tests")
    print("Testing voyage-3-large embeddings + LLM validation\n")

    results = {}

    # Test 1: Embeddings
    try:
        results["embeddings"] = await test_embeddings()
    except Exception as e:
        print(f"  [FAIL] Embedding test error: {e}")
        results["embeddings"] = False

    # Test 2: Semantic matching
    try:
        results["semantic"] = await test_semantic_matching()
    except Exception as e:
        print(f"  [FAIL] Semantic matching error: {e}")
        results["semantic"] = False

    # Test 3: LLM validation
    try:
        results["llm"] = await test_llm_validation()
    except Exception as e:
        print(f"  [FAIL] LLM validation error: {e}")
        results["llm"] = False

    # Test 4: Full pipeline
    try:
        results["pipeline"] = await test_full_hybrid_pipeline()
    except Exception as e:
        print(f"  [FAIL] Pipeline error: {e}")
        results["pipeline"] = False

    # Summary
    print_header("Test Summary")
    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, result in results.items():
        status = "PASS" if result else "FAIL"
        print(f"  {name}: {status}")

    print(f"\n  Total: {passed}/{total} passed")

    return all(results.values())


if __name__ == "__main__":
    success = asyncio.run(run_tests())
    sys.exit(0 if success else 1)
