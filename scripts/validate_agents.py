#!/usr/bin/env python3
"""Validate each demo agent performs correctly before adding to platform.

This runs test prompts through each agent's specialized system prompt
and validates the output quality.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

from bazaar.llm import call_fireworks

# Import the agent prompts directly
from bazaar.agents.executor import AGENT_PROMPTS, COST_PER_1K_INPUT, COST_PER_1K_OUTPUT


# Test cases for each agent
TEST_CASES = {
    "agent_anomaly_hunter": {
        "name": "AnomalyHunter",
        "test_prompt": """Analyze this server metrics data for anomalies:

Timestamp,CPU%,Memory%,Latency_ms,Requests/sec
2025-01-10 10:00, 45, 62, 120, 150
2025-01-10 10:05, 48, 63, 118, 155
2025-01-10 10:10, 52, 61, 125, 148
2025-01-10 10:15, 47, 64, 122, 152
2025-01-10 10:20, 89, 78, 450, 89    <- suspicious
2025-01-10 10:25, 51, 65, 130, 145
2025-01-10 10:30, 95, 82, 520, 45    <- suspicious
2025-01-10 10:35, 48, 63, 125, 150
2025-01-10 10:40, 50, 62, 122, 153

Identify all anomalies and explain the likely cause.""",
        "expected_keywords": ["anomaly", "spike", "CPU", "latency", "10:20", "10:30"],
    },

    "agent_code_reviewer": {
        "name": "CodeReviewer Pro",
        "test_prompt": """Review this Python code for security issues and quality:

```python
import os
import sqlite3

def get_user(user_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    query = f"SELECT * FROM users WHERE id = {user_id}"
    cursor.execute(query)
    return cursor.fetchone()

def run_command(cmd):
    os.system(cmd)

def login(username, password):
    user = get_user(username)
    if user and user['password'] == password:
        return True
    return False
```

Identify all security vulnerabilities and suggest fixes.""",
        "expected_keywords": ["SQL injection", "command injection", "os.system", "password", "plaintext", "parameterized"],
    },

    "agent_data_analyst": {
        "name": "DataAnalyst",
        "test_prompt": """I have a sales database with tables:
- orders (order_id, customer_id, product_id, quantity, total_price, order_date)
- customers (customer_id, name, region, signup_date)
- products (product_id, name, category, unit_price)

Write SQL queries to answer:
1. What are the top 5 selling products by total revenue?
2. Which region has the highest average order value?
3. What's the month-over-month growth rate for the last 6 months?

Explain your approach for each query.""",
        "expected_keywords": ["SELECT", "GROUP BY", "ORDER BY", "SUM", "AVG", "JOIN"],
    },

    "agent_researcher": {
        "name": "ResearchAgent",
        "test_prompt": """Research question: What are the main approaches to AI agent orchestration?

Provide a structured research summary covering:
1. Key frameworks and their approaches
2. Multi-agent vs single-agent architectures
3. Common patterns for task decomposition
4. Challenges and current limitations

Be thorough but concise.""",
        "expected_keywords": ["LangChain", "AutoGPT", "orchestration", "multi-agent", "task", "framework"],
    },

    "agent_doc_summarizer": {
        "name": "DocSummarizer",
        "test_prompt": """Summarize this technical document:

---
Title: Microservices Architecture Best Practices

Abstract: This document outlines key considerations for designing and implementing microservices architectures in enterprise environments.

Chapter 1: Service Boundaries
Defining proper service boundaries is crucial. Each service should represent a single business capability and own its data. Avoid creating services that are too fine-grained (nano-services) or too coarse (distributed monoliths). Use domain-driven design principles to identify bounded contexts.

Chapter 2: Communication Patterns
Services communicate via synchronous (REST, gRPC) or asynchronous (message queues, event streaming) patterns. Synchronous calls are simpler but create tight coupling. Asynchronous patterns improve resilience but add complexity. Consider the CAP theorem when designing data consistency strategies.

Chapter 3: Deployment and Operations
Each service should be independently deployable. Use containers and orchestration (Kubernetes) for consistent deployment. Implement proper health checks, logging, and distributed tracing. Circuit breakers prevent cascade failures.

Chapter 4: Security
Implement zero-trust security. Use API gateways for authentication. Secure service-to-service communication with mTLS. Follow the principle of least privilege for service accounts.
---

Provide an executive summary with key takeaways.""",
        "expected_keywords": ["summary", "microservices", "boundaries", "communication", "deployment", "security"],
    },

    "agent_sentiment_pro": {
        "name": "SentimentPro",
        "test_prompt": """Analyze the sentiment of these customer reviews:

1. "Absolutely love this product! Best purchase I've made all year. Fast shipping too!"

2. "Terrible experience. Product arrived broken and customer support was unhelpful. Waited 2 weeks for a refund that never came."

3. "It's okay. Does what it says but nothing special. Probably wouldn't buy again but not disappointed either."

4. "The features are amazing but the price is ridiculous. Hard to recommend despite the quality."

5. "Five stars! This company really cares about their customers. Will definitely buy again."

For each review, provide:
- Overall sentiment (positive/negative/neutral/mixed)
- Sentiment intensity (1-5)
- Key emotional indicators
- Brief reasoning""",
        "expected_keywords": ["positive", "negative", "neutral", "mixed", "sentiment", "intensity"],
    },
}


def print_result(agent_name: str, passed: bool, details: str = ""):
    """Print a test result."""
    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"  [{status}] {agent_name}")
    if details:
        print(f"          {details}")


async def validate_agent(agent_id: str, test_case: dict) -> dict:
    """Run validation test for a single agent."""
    name = test_case["name"]
    prompt = test_case["test_prompt"]
    expected = test_case["expected_keywords"]
    system_prompt = AGENT_PROMPTS.get(agent_id, "You are a helpful AI assistant.")

    print(f"\nTesting {name}...")
    print(f"  Prompt: {prompt[:80]}...")

    start = datetime.now()

    try:
        response = await call_fireworks(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.4,
            max_tokens=2048,
        )

        elapsed = (datetime.now() - start).total_seconds()
        tokens = response.tokens_input + response.tokens_output
        cost = (response.tokens_input / 1000) * COST_PER_1K_INPUT + \
               (response.tokens_output / 1000) * COST_PER_1K_OUTPUT

        # Check for expected keywords
        output_lower = response.content.lower()
        found_keywords = [kw for kw in expected if kw.lower() in output_lower]
        keyword_score = len(found_keywords) / len(expected)

        passed = keyword_score >= 0.5 and len(response.content) > 200

        result = {
            "agent_id": agent_id,
            "name": name,
            "passed": passed,
            "keyword_score": keyword_score,
            "keywords_found": found_keywords,
            "keywords_missing": [kw for kw in expected if kw.lower() not in output_lower],
            "tokens": tokens,
            "cost_usd": cost,
            "latency_sec": elapsed,
            "output_length": len(response.content),
            "output_preview": response.content[:500],
        }

        status = "PASS" if passed else "FAIL"
        print(f"  Status: {status}")
        print(f"  Keywords: {len(found_keywords)}/{len(expected)} found")
        print(f"  Tokens: {tokens} (${cost:.4f})")
        print(f"  Latency: {elapsed:.1f}s")
        print(f"  Output: {len(response.content)} chars")

        if not passed:
            print(f"  Missing: {result['keywords_missing']}")

        return result

    except Exception as e:
        print(f"  ERROR: {e}")
        return {
            "agent_id": agent_id,
            "name": name,
            "passed": False,
            "error": str(e),
        }


async def run_validation():
    """Run validation for all agents."""
    print("=" * 60)
    print("  Open Agora Agent Validation")
    print("=" * 60)
    print(f"\nTesting {len(TEST_CASES)} agents...")

    results = []
    total_cost = 0

    for agent_id, test_case in TEST_CASES.items():
        result = await validate_agent(agent_id, test_case)
        results.append(result)
        total_cost += result.get("cost_usd", 0)

    # Summary
    print("\n" + "=" * 60)
    print("  Validation Summary")
    print("=" * 60)

    passed = sum(1 for r in results if r.get("passed", False))
    failed = len(results) - passed

    print(f"\n  Passed: {passed}/{len(results)}")
    print(f"  Failed: {failed}/{len(results)}")
    print(f"  Total cost: ${total_cost:.4f}")

    print("\n  Results by agent:")
    for result in results:
        status = "✓" if result.get("passed") else "✗"
        name = result["name"]
        if result.get("error"):
            print(f"    {status} {name}: ERROR - {result['error'][:50]}")
        else:
            score = result.get("keyword_score", 0)
            print(f"    {status} {name}: {score:.0%} keywords, {result.get('tokens', 0)} tokens")

    if failed > 0:
        print("\n  Failed agents need review before deployment.")
        print("  Check their system prompts in executor.py")
    else:
        print("\n  All agents validated! Ready for deployment.")

    return results


if __name__ == "__main__":
    results = asyncio.run(run_validation())

    # Exit with error code if any failed
    if any(not r.get("passed") for r in results):
        sys.exit(1)
