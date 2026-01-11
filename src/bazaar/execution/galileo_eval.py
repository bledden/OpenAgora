"""Galileo AI integration for quality evaluation.

Uses the Galileo promptquality SDK to evaluate LLM outputs with
industry-standard metrics for correctness, completeness, toxicity, etc.
"""

import structlog
from typing import Optional
import json

from ..config import get_settings

logger = structlog.get_logger()

# Galileo client singleton
_galileo_client = None
_galileo_available = False


def _init_galileo():
    """Initialize Galileo client if API key is available."""
    global _galileo_client, _galileo_available

    if _galileo_client is not None:
        return _galileo_available

    settings = get_settings()

    if not settings.galileo_api_key:
        logger.warning("galileo_not_configured", message="No Galileo API key found")
        _galileo_available = False
        return False

    try:
        import promptquality as pq
        import os

        # Set environment variables for Galileo auth
        os.environ["GALILEO_API_KEY"] = settings.galileo_api_key
        os.environ["GALILEO_CONSOLE_URL"] = settings.galileo_console_url

        # Login to Galileo with console URL
        pq.login(console_url=settings.galileo_console_url)
        _galileo_client = pq
        _galileo_available = True
        logger.info("galileo_initialized", project=settings.galileo_project)
        return True
    except Exception as e:
        logger.error("galileo_init_failed", error=str(e))
        _galileo_available = False
        return False


async def evaluate_with_galileo(
    task_description: str,
    result: dict,
    task_type: str = "analysis",
    expected_output: Optional[str] = None,
) -> Optional[dict]:
    """Evaluate an LLM output using Galileo metrics.

    Args:
        task_description: The original task/prompt given to the agent
        result: The agent's output to evaluate
        task_type: Type of task for context
        expected_output: Optional expected output for ground truth comparison

    Returns:
        Evaluation dict with Galileo metrics, or None if Galileo unavailable
    """
    if not _init_galileo():
        return None

    settings = get_settings()
    pq = _galileo_client

    try:
        # Convert result to string for evaluation
        if isinstance(result, dict):
            result_str = json.dumps(result, indent=2, default=str)
        else:
            result_str = str(result)

        # Configure scorers using Galileo Scorers enum
        # Using Luna-based (NLI) scorers which work with Galileo API key alone
        # GPT-based scorers require OpenAI/Azure credentials
        scorers = [
            # Core quality metrics (Luna - no external LLM needed)
            pq.Scorers.completeness_luna,  # completeness_nli
            pq.Scorers.context_adherence_luna,  # adherence_nli
            # Tone doesn't need external LLM
            pq.Scorers.tone,
        ]

        # Add ground truth scorer if we have expected output
        if expected_output is not None:
            scorers.append(pq.Scorers.ground_truth_adherence_plus)

        # Generate unique run name with timestamp
        import time
        run_name = f"agentbazaar_{task_type}_{int(time.time())}"

        # Create evaluation run
        run = pq.EvaluateRun(
            project_name=settings.galileo_project,
            run_name=run_name,
            scorers=scorers,
        )

        # Add the evaluation as a single step workflow
        run.add_single_step_workflow(
            input=task_description,
            output=result_str,
            model="agentbazaar-agent",  # Placeholder model name
            ground_truth=expected_output,
            metadata={"task_type": task_type, "source": "agentbazaar"},
        )

        # Execute evaluation
        results = await _run_evaluation_async(run, settings.galileo_project, run_name)

        if not results:
            return None

        # Extract scores from Galileo results
        scores = _extract_galileo_scores(results)

        logger.info(
            "galileo_evaluation_complete",
            task_type=task_type,
            overall_score=scores.get("overall", 0),
            correctness=scores.get("correctness", 0),
            completeness=scores.get("completeness", 0),
        )

        return {
            "provider": "galileo",
            "scores": scores,
            "raw_results": results,
        }

    except Exception as e:
        logger.error("galileo_evaluation_failed", error=str(e))
        return None


async def _run_evaluation_async(run, project_name: str, run_name: str) -> Optional[dict]:
    """Run Galileo evaluation asynchronously and retrieve results."""
    import asyncio
    import time

    pq = _galileo_client

    try:
        # Run in executor since promptquality finish() is sync
        loop = asyncio.get_event_loop()

        # Finish the run (submits to Galileo cloud)
        await loop.run_in_executor(None, lambda: run.finish(wait=True, silent=True))

        # Wait a moment for processing
        await asyncio.sleep(2)

        # Try to retrieve results from Galileo
        try:
            samples = await loop.run_in_executor(
                None,
                lambda: pq.get_evaluate_samples(
                    project_name=project_name,
                    run_name=run_name
                )
            )

            if samples and samples.samples:
                # Get the first sample's scores
                sample = samples.samples[0]
                return {"sample": sample, "metrics": getattr(sample, "metrics", {})}
        except Exception as fetch_error:
            logger.warning("galileo_fetch_results_failed", error=str(fetch_error))

        # Return basic success if we can't fetch detailed results
        return {"status": "submitted", "metrics": {}}

    except Exception as e:
        logger.error("galileo_run_failed", error=str(e))
        return None


def _extract_galileo_scores(results: dict) -> dict:
    """Extract normalized scores from Galileo results.

    Maps Galileo metrics to our standard scoring format.
    """
    scores = {
        "correctness": 0.5,
        "completeness": 0.5,
        "instruction_adherence": 0.5,
        "toxicity": 0.0,  # Lower is better
        "pii_detected": False,
        "prompt_injection_detected": False,
        "overall": 0.5,
    }

    try:
        # Handle different result formats
        metrics = {}

        if isinstance(results, dict):
            # Check for sample object in results
            sample = results.get("sample")
            if sample:
                # Get metrics from sample's model_extra (pydantic extra fields)
                if hasattr(sample, "model_extra") and sample.model_extra:
                    metrics = sample.model_extra
                # Also try direct dict access
                elif hasattr(sample, "model_dump"):
                    sample_dict = sample.model_dump()
                    # Metrics might be stored as extra fields
                    for key in sample_dict:
                        if key not in ["id", "input", "output", "target", "cost", "children"]:
                            metrics[key] = sample_dict[key]

            # Also check for metrics key directly
            if not metrics:
                metrics = results.get("metrics", results)
        else:
            # Try to access as object attributes
            metrics = getattr(results, "metrics", {})
            if not metrics and hasattr(results, "model_extra"):
                metrics = results.model_extra or {}

        if not metrics:
            logger.debug("galileo_no_metrics_found", results_type=type(results).__name__)
            return scores

        # Map Galileo metrics to our scores
        score_mapping = {
            "correctness": ["factuality", "adherence_nli"],  # adherence as proxy
            "completeness": ["completeness_nli", "completeness_gpt"],
            "instruction_adherence": ["instruction_adherence", "adherence_nli"],
            "toxicity": ["toxicity", "toxicity_gpt"],
            "ground_truth": ["ground_truth_adherence"],
            "tone": ["tone"],
        }

        for our_key, galileo_keys in score_mapping.items():
            for gk in galileo_keys:
                if gk in metrics:
                    value = metrics[gk]
                    if isinstance(value, (int, float)):
                        scores[our_key] = float(value)
                        break

        # Check for PII detection
        if "pii" in metrics:
            scores["pii_detected"] = bool(metrics["pii"])

        # Check for prompt injection
        if "prompt_injection" in metrics:
            scores["prompt_injection_detected"] = bool(metrics["prompt_injection"])

        # Calculate overall score (weighted average of key metrics)
        quality_scores = [
            scores.get("correctness", 0.5),
            scores.get("completeness", 0.5),
            scores.get("instruction_adherence", 0.5),
        ]
        scores["overall"] = sum(quality_scores) / len(quality_scores)

        # Penalize for safety issues
        if scores.get("toxicity", 0) > 0.5:
            scores["overall"] *= 0.5
        if scores.get("pii_detected"):
            scores["overall"] *= 0.7
        if scores.get("prompt_injection_detected"):
            scores["overall"] *= 0.3

    except Exception as e:
        logger.warning("galileo_score_extraction_failed", error=str(e))

    return scores


def is_galileo_available() -> bool:
    """Check if Galileo is properly configured and available."""
    return _init_galileo()


def get_galileo_metrics_info() -> dict:
    """Get information about available Galileo metrics."""
    return {
        "quality_metrics": [
            "correctness",
            "completeness_plus",
            "instruction_adherence_plus",
        ],
        "safety_metrics": [
            "toxicity_plus",
            "pii",
            "prompt_injection_plus",
        ],
        "context_metrics": [
            "ground_truth_adherence_plus",
            "context_adherence_plus",
            "context_relevance",
        ],
        "description": "Galileo provides enterprise-grade LLM evaluation with Luna models for cost-effective, low-latency scoring.",
    }
