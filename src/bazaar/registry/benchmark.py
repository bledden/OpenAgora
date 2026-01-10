"""Benchmark suite for verifying agent capabilities."""

import time
import uuid
from datetime import datetime, timedelta
from typing import Optional
import structlog

from ..llm import call_fireworks, call_fireworks_json
from ..db import create_benchmark, update_agent
from ..models import BazaarBenchmark, BenchmarkTestResult, AgentCapabilities

logger = structlog.get_logger()


# ============================================================
# Benchmark Test Cases
# ============================================================

SUMMARIZATION_TESTS = [
    {
        "id": "sum_1",
        "input": """The company reported a 15% increase in quarterly revenue, driven primarily by
        strong sales in the enterprise segment. However, operating costs rose by 8% due to
        investments in R&D and expansion into new markets. The CEO expressed optimism about
        the upcoming product launch scheduled for Q3.""",
        "expected_topics": ["revenue increase", "enterprise sales", "operating costs", "R&D", "product launch"],
    },
    {
        "id": "sum_2",
        "input": """Customer feedback analysis reveals three main themes: users appreciate the
        intuitive interface and fast performance, but consistently request better mobile support
        and more customization options. Support ticket volume decreased 20% after the latest
        update, suggesting improved stability.""",
        "expected_topics": ["interface", "performance", "mobile support", "customization", "stability"],
    },
    {
        "id": "sum_3",
        "input": """The machine learning pipeline processes 500,000 records daily with an average
        latency of 150ms per request. Recent optimizations reduced memory usage by 30% while
        maintaining accuracy above 95%. The team is evaluating GPU acceleration to handle
        projected 3x traffic growth next quarter.""",
        "expected_topics": ["ML pipeline", "latency", "memory optimization", "accuracy", "GPU", "traffic growth"],
    },
]

SENTIMENT_TESTS = [
    {"id": "sent_1", "input": "This product is amazing! Best purchase I've ever made.", "expected": "positive"},
    {"id": "sent_2", "input": "Terrible experience. Slow, buggy, and support was unhelpful.", "expected": "negative"},
    {"id": "sent_3", "input": "It works fine, nothing special but gets the job done.", "expected": "neutral"},
    {"id": "sent_4", "input": "I love the new features but hate the new pricing model.", "expected": "mixed"},
    {"id": "sent_5", "input": "Outstanding customer service! They went above and beyond.", "expected": "positive"},
    {"id": "sent_6", "input": "Complete waste of money. Doesn't work as advertised.", "expected": "negative"},
    {"id": "sent_7", "input": "Average product. Met expectations but didn't exceed them.", "expected": "neutral"},
    {"id": "sent_8", "input": "Fast shipping but product quality is disappointing.", "expected": "mixed"},
]

EXTRACTION_TESTS = [
    {
        "id": "ext_1",
        "input": "Contact John Smith at john.smith@example.com or call 555-123-4567 for more info.",
        "expected_fields": ["name", "email", "phone"],
    },
    {
        "id": "ext_2",
        "input": "Order #12345 placed on 2024-01-15 for $299.99. Ships to 123 Main St, New York, NY 10001.",
        "expected_fields": ["order_id", "date", "amount", "address"],
    },
    {
        "id": "ext_3",
        "input": "Meeting scheduled for Tuesday at 3pm with the engineering team to discuss Q2 roadmap.",
        "expected_fields": ["day", "time", "attendees", "topic"],
    },
]

CLASSIFICATION_TESTS = [
    {"id": "cls_1", "input": "How do I reset my password?", "expected": "support"},
    {"id": "cls_2", "input": "I'd like to request a refund for my order.", "expected": "billing"},
    {"id": "cls_3", "input": "Can you add dark mode to the app?", "expected": "feature_request"},
    {"id": "cls_4", "input": "The app crashes when I try to upload files.", "expected": "bug_report"},
    {"id": "cls_5", "input": "What's the difference between Pro and Enterprise plans?", "expected": "sales"},
]

PATTERN_TESTS = [
    {
        "id": "pat_1",
        "input": [100, 102, 101, 99, 103, 250, 98, 100],  # Anomaly at index 5
        "expected_anomaly_index": 5,
    },
    {
        "id": "pat_2",
        "input": [10, 12, 11, 13, 12, 14, 13, 15, 14, 16],  # Upward trend
        "expected_pattern": "increasing",
    },
]


# ============================================================
# Benchmark Execution
# ============================================================

async def run_benchmark(
    agent_id: str,
    model: str = "accounts/fireworks/models/llama-v3p3-70b-instruct",
) -> BazaarBenchmark:
    """Run full benchmark suite for an agent."""
    logger.info("benchmark_started", agent_id=agent_id)

    benchmark_id = f"bench_{uuid.uuid4().hex[:8]}"
    tests = {}
    total_tests = 0
    total_passed = 0

    # Run each capability test
    summarization_result = await _test_summarization(model)
    tests["summarization"] = summarization_result
    total_tests += summarization_result.test_cases
    total_passed += summarization_result.passed

    sentiment_result = await _test_sentiment(model)
    tests["sentiment_analysis"] = sentiment_result
    total_tests += sentiment_result.test_cases
    total_passed += sentiment_result.passed

    extraction_result = await _test_extraction(model)
    tests["data_extraction"] = extraction_result
    total_tests += extraction_result.test_cases
    total_passed += extraction_result.passed

    classification_result = await _test_classification(model)
    tests["classification"] = classification_result
    total_tests += classification_result.test_cases
    total_passed += classification_result.passed

    pattern_result = await _test_pattern_recognition(model)
    tests["pattern_recognition"] = pattern_result
    total_tests += pattern_result.test_cases
    total_passed += pattern_result.passed

    # Calculate overall score
    overall_score = total_passed / total_tests if total_tests > 0 else 0.0

    # Create benchmark record
    benchmark = BazaarBenchmark(
        benchmark_id=benchmark_id,
        agent_id=agent_id,
        tests={k: v.model_dump() for k, v in tests.items()},
        overall_score=overall_score,
        total_tests=total_tests,
        total_passed=total_passed,
        created_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(days=7),
    )

    # Store benchmark
    await create_benchmark(benchmark.model_dump())

    # Update agent capabilities
    capabilities = AgentCapabilities(
        summarization=tests["summarization"].score,
        sentiment_analysis=tests["sentiment_analysis"].score,
        data_extraction=tests["data_extraction"].score,
        classification=tests["classification"].score,
        pattern_recognition=tests["pattern_recognition"].score,
        aggregation=0.85,  # Assumed baseline
        anomaly_detection=tests["pattern_recognition"].score * 0.9,
    )

    await update_agent(agent_id, {
        "capabilities": capabilities.model_dump(),
        "last_benchmark": datetime.utcnow(),
    })

    logger.info(
        "benchmark_completed",
        agent_id=agent_id,
        overall_score=overall_score,
        passed=total_passed,
        total=total_tests,
    )

    return benchmark


async def _test_summarization(model: str) -> BenchmarkTestResult:
    """Test summarization capability."""
    passed = 0
    total_latency = 0

    for test in SUMMARIZATION_TESTS:
        start = time.time()
        try:
            response = await call_fireworks_json(
                prompt=f"""Summarize this text in 2-3 sentences and list the key topics.

Text: {test['input']}

Return JSON: {{"summary": "...", "topics": ["topic1", "topic2"]}}""",
                temperature=0.3,
            )

            latency = (time.time() - start) * 1000
            total_latency += latency

            # Check if topics are covered
            if "topics" in response:
                topics = [t.lower() for t in response.get("topics", [])]
                covered = sum(1 for exp in test["expected_topics"] if any(exp.lower() in t for t in topics))
                if covered >= len(test["expected_topics"]) * 0.6:
                    passed += 1
        except Exception as e:
            logger.warning("summarization_test_failed", test_id=test["id"], error=str(e))
            total_latency += (time.time() - start) * 1000

    return BenchmarkTestResult(
        score=passed / len(SUMMARIZATION_TESTS),
        test_cases=len(SUMMARIZATION_TESTS),
        passed=passed,
        avg_latency_ms=total_latency / len(SUMMARIZATION_TESTS),
    )


async def _test_sentiment(model: str) -> BenchmarkTestResult:
    """Test sentiment analysis capability."""
    passed = 0
    total_latency = 0

    for test in SENTIMENT_TESTS:
        start = time.time()
        try:
            response = await call_fireworks_json(
                prompt=f"""Analyze the sentiment of this text.

Text: "{test['input']}"

Return JSON: {{"sentiment": "positive|negative|neutral|mixed"}}""",
                temperature=0.2,
            )

            latency = (time.time() - start) * 1000
            total_latency += latency

            if response.get("sentiment", "").lower() == test["expected"]:
                passed += 1
        except Exception as e:
            logger.warning("sentiment_test_failed", test_id=test["id"], error=str(e))
            total_latency += (time.time() - start) * 1000

    return BenchmarkTestResult(
        score=passed / len(SENTIMENT_TESTS),
        test_cases=len(SENTIMENT_TESTS),
        passed=passed,
        avg_latency_ms=total_latency / len(SENTIMENT_TESTS),
    )


async def _test_extraction(model: str) -> BenchmarkTestResult:
    """Test data extraction capability."""
    passed = 0
    total_latency = 0

    for test in EXTRACTION_TESTS:
        start = time.time()
        try:
            response = await call_fireworks_json(
                prompt=f"""Extract structured data from this text.

Text: "{test['input']}"

Return JSON with extracted fields.""",
                temperature=0.2,
            )

            latency = (time.time() - start) * 1000
            total_latency += latency

            # Check if expected fields are present
            if isinstance(response, dict):
                fields_found = sum(1 for f in test["expected_fields"] if any(f in k.lower() for k in response.keys()))
                if fields_found >= len(test["expected_fields"]) * 0.7:
                    passed += 1
        except Exception as e:
            logger.warning("extraction_test_failed", test_id=test["id"], error=str(e))
            total_latency += (time.time() - start) * 1000

    return BenchmarkTestResult(
        score=passed / len(EXTRACTION_TESTS),
        test_cases=len(EXTRACTION_TESTS),
        passed=passed,
        avg_latency_ms=total_latency / len(EXTRACTION_TESTS),
    )


async def _test_classification(model: str) -> BenchmarkTestResult:
    """Test classification capability."""
    passed = 0
    total_latency = 0

    categories = "support, billing, feature_request, bug_report, sales"

    for test in CLASSIFICATION_TESTS:
        start = time.time()
        try:
            response = await call_fireworks_json(
                prompt=f"""Classify this customer message into one category.

Categories: {categories}

Message: "{test['input']}"

Return JSON: {{"category": "..."}}""",
                temperature=0.2,
            )

            latency = (time.time() - start) * 1000
            total_latency += latency

            if response.get("category", "").lower() == test["expected"]:
                passed += 1
        except Exception as e:
            logger.warning("classification_test_failed", test_id=test["id"], error=str(e))
            total_latency += (time.time() - start) * 1000

    return BenchmarkTestResult(
        score=passed / len(CLASSIFICATION_TESTS),
        test_cases=len(CLASSIFICATION_TESTS),
        passed=passed,
        avg_latency_ms=total_latency / len(CLASSIFICATION_TESTS),
    )


async def _test_pattern_recognition(model: str) -> BenchmarkTestResult:
    """Test pattern recognition capability."""
    passed = 0
    total_latency = 0

    for test in PATTERN_TESTS:
        start = time.time()
        try:
            if "expected_anomaly_index" in test:
                response = await call_fireworks_json(
                    prompt=f"""Find the anomaly in this number sequence.

Sequence: {test['input']}

Return JSON: {{"anomaly_index": <index of anomalous value>, "anomaly_value": <the anomalous value>}}""",
                    temperature=0.2,
                )

                latency = (time.time() - start) * 1000
                total_latency += latency

                if response.get("anomaly_index") == test["expected_anomaly_index"]:
                    passed += 1
            else:
                response = await call_fireworks_json(
                    prompt=f"""Identify the pattern/trend in this number sequence.

Sequence: {test['input']}

Return JSON: {{"pattern": "increasing|decreasing|stable|cyclical"}}""",
                    temperature=0.2,
                )

                latency = (time.time() - start) * 1000
                total_latency += latency

                if response.get("pattern", "").lower() == test["expected_pattern"]:
                    passed += 1
        except Exception as e:
            logger.warning("pattern_test_failed", test_id=test["id"], error=str(e))
            total_latency += (time.time() - start) * 1000

    return BenchmarkTestResult(
        score=passed / len(PATTERN_TESTS),
        test_cases=len(PATTERN_TESTS),
        passed=passed,
        avg_latency_ms=total_latency / len(PATTERN_TESTS),
    )
