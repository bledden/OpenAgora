"""Quality evaluation using Galileo-style scoring."""

import structlog

from ..llm import call_fireworks_json
from ..config import get_settings

logger = structlog.get_logger()


QUALITY_EVALUATOR_PROMPT = """You are a quality evaluator for AI agent outputs.

Evaluate the result based on these criteria:
1. Relevance (0-1): Does the output address the task?
2. Accuracy (0-1): Are the findings factually correct and well-supported?
3. Completeness (0-1): Are all aspects of the task covered?
4. Clarity (0-1): Is the output clear and well-structured?
5. Actionability (0-1): Are the findings useful and actionable?

Return JSON:
{
  "relevance": 0.0-1.0,
  "accuracy": 0.0-1.0,
  "completeness": 0.0-1.0,
  "clarity": 0.0-1.0,
  "actionability": 0.0-1.0,
  "overall": 0.0-1.0,
  "feedback": "Brief explanation of score"
}"""


async def evaluate_quality(
    task_type: str,
    task_description: str,
    result: dict,
) -> float:
    """Evaluate the quality of a task result.

    This simulates Galileo-style quality evaluation.
    In production, this would integrate with the Galileo API.

    Args:
        task_type: Type of task (analysis, summarization, etc.)
        task_description: Original task description
        result: Agent's output to evaluate

    Returns:
        Quality score from 0 to 1
    """
    settings = get_settings()

    try:
        # Build evaluation prompt
        eval_prompt = f"""Evaluate this AI agent output for quality.

## Task Type: {task_type}

## Task Description:
{task_description}

## Agent Output:
```json
{_safe_json_str(result)}
```

Provide quality scores."""

        # Call evaluator
        evaluation = await call_fireworks_json(
            prompt=eval_prompt,
            system_prompt=QUALITY_EVALUATOR_PROMPT,
            temperature=0.2,
        )

        # Extract overall score
        overall_score = evaluation.get("overall", 0.5)

        # Ensure it's a valid float between 0 and 1
        overall_score = max(0.0, min(1.0, float(overall_score)))

        logger.info(
            "quality_evaluated",
            task_type=task_type,
            overall_score=overall_score,
            relevance=evaluation.get("relevance"),
            accuracy=evaluation.get("accuracy"),
            completeness=evaluation.get("completeness"),
        )

        return overall_score

    except Exception as e:
        logger.error("quality_evaluation_failed", error=str(e))
        # Default to neutral score on error
        return 0.5


async def check_quality_threshold(quality_score: float) -> dict:
    """Check if quality score passes the threshold.

    Returns:
        Decision dict with action to take
    """
    settings = get_settings()
    threshold = settings.quality_threshold

    if quality_score >= threshold:
        return {
            "passed": True,
            "action": "release_payment",
            "quality_score": quality_score,
            "threshold": threshold,
            "message": f"Quality score {quality_score:.2f} meets threshold {threshold}",
        }
    elif quality_score >= threshold * 0.7:
        # Borderline - partial payment
        return {
            "passed": False,
            "action": "partial_payment",
            "quality_score": quality_score,
            "threshold": threshold,
            "payment_ratio": 0.5,
            "message": f"Quality score {quality_score:.2f} below threshold, partial payment",
        }
    else:
        # Failed - refund
        return {
            "passed": False,
            "action": "refund",
            "quality_score": quality_score,
            "threshold": threshold,
            "message": f"Quality score {quality_score:.2f} too low, refunding",
        }


def _safe_json_str(obj: dict, max_length: int = 2000) -> str:
    """Convert dict to JSON string, truncating if too long."""
    import json
    try:
        s = json.dumps(obj, indent=2, default=str)
        if len(s) > max_length:
            return s[:max_length] + "\n... (truncated)"
        return s
    except Exception:
        return str(obj)[:max_length]
