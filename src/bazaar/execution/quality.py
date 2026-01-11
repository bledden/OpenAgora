"""Quality evaluation using Galileo-style scoring.

This module provides AI-SUGGESTED quality scores and recommendations.
IMPORTANT: Humans make the final decision on accepting/rejecting work
and determining the final rating. AI provides suggestions only.
"""

import structlog
from typing import Optional

from ..llm import call_fireworks_json
from ..config import get_settings

logger = structlog.get_logger()


QUALITY_EVALUATOR_PROMPT = """You are a quality evaluator for AI agent outputs.
Your job is to SUGGEST scores and provide recommendations to help a human reviewer.
The human will make the final decision.

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
  "suggested_overall": 0.0-1.0,
  "recommendation": "accept" | "partial" | "reject",
  "feedback": "Detailed explanation for the human reviewer",
  "strengths": ["What the agent did well"],
  "improvements": ["What could be improved"],
  "red_flags": ["Any concerning issues (empty if none)"]
}"""


async def get_quality_suggestion(
    task_type: str,
    task_description: str,
    result: dict,
) -> dict:
    """Get AI quality suggestion for a task result.

    This provides SUGGESTIONS for human review. The human makes the final decision.

    Args:
        task_type: Type of task (analysis, summarization, etc.)
        task_description: Original task description
        result: Agent's output to evaluate

    Returns:
        Suggestion dict with scores, recommendation, and detailed feedback
    """
    settings = get_settings()

    try:
        # Build evaluation prompt
        eval_prompt = f"""Evaluate this AI agent output for quality.
Provide detailed feedback to help a human reviewer make the final decision.

## Task Type: {task_type}

## Task Description:
{task_description}

## Agent Output:
```json
{_safe_json_str(result)}
```

Provide quality scores and detailed recommendations."""

        # Call evaluator
        evaluation = await call_fireworks_json(
            prompt=eval_prompt,
            system_prompt=QUALITY_EVALUATOR_PROMPT,
            temperature=0.2,
        )

        # Build suggestion object
        suggestion = {
            "scores": {
                "relevance": _safe_score(evaluation.get("relevance", 0.5)),
                "accuracy": _safe_score(evaluation.get("accuracy", 0.5)),
                "completeness": _safe_score(evaluation.get("completeness", 0.5)),
                "clarity": _safe_score(evaluation.get("clarity", 0.5)),
                "actionability": _safe_score(evaluation.get("actionability", 0.5)),
            },
            "suggested_overall": _safe_score(evaluation.get("suggested_overall", 0.5)),
            "recommendation": evaluation.get("recommendation", "partial"),
            "feedback": evaluation.get("feedback", ""),
            "strengths": evaluation.get("strengths", []),
            "improvements": evaluation.get("improvements", []),
            "red_flags": evaluation.get("red_flags", []),
            "is_ai_suggestion": True,  # Explicit flag that this is AI-generated
            "awaiting_human_review": True,
        }

        logger.info(
            "quality_suggestion_generated",
            task_type=task_type,
            suggested_overall=suggestion["suggested_overall"],
            recommendation=suggestion["recommendation"],
        )

        return suggestion

    except Exception as e:
        logger.error("quality_suggestion_failed", error=str(e))
        # Return neutral suggestion on error
        return {
            "scores": {
                "relevance": 0.5,
                "accuracy": 0.5,
                "completeness": 0.5,
                "clarity": 0.5,
                "actionability": 0.5,
            },
            "suggested_overall": 0.5,
            "recommendation": "partial",
            "feedback": f"AI evaluation failed: {str(e)}. Please review manually.",
            "strengths": [],
            "improvements": [],
            "red_flags": ["AI evaluation failed - manual review required"],
            "is_ai_suggestion": True,
            "awaiting_human_review": True,
            "error": str(e),
        }


def get_payment_recommendation(ai_suggestion: dict) -> dict:
    """Get AI payment recommendation based on quality suggestion.

    This is a RECOMMENDATION for the human reviewer, not a final decision.

    Args:
        ai_suggestion: The AI quality suggestion dict

    Returns:
        Recommendation dict with suggested payment action
    """
    settings = get_settings()
    threshold = settings.quality_threshold
    suggested_score = ai_suggestion.get("suggested_overall", 0.5)
    recommendation = ai_suggestion.get("recommendation", "partial")

    if recommendation == "accept" or suggested_score >= threshold:
        return {
            "suggested_action": "release_payment",
            "suggested_payment_ratio": 1.0,
            "suggested_score": suggested_score,
            "threshold": threshold,
            "message": f"AI suggests FULL PAYMENT (score: {suggested_score:.2f})",
            "requires_human_approval": True,
        }
    elif recommendation == "partial" or suggested_score >= threshold * 0.7:
        return {
            "suggested_action": "partial_payment",
            "suggested_payment_ratio": 0.5,
            "suggested_score": suggested_score,
            "threshold": threshold,
            "message": f"AI suggests PARTIAL PAYMENT (score: {suggested_score:.2f})",
            "requires_human_approval": True,
        }
    else:
        return {
            "suggested_action": "refund",
            "suggested_payment_ratio": 0.0,
            "suggested_score": suggested_score,
            "threshold": threshold,
            "message": f"AI suggests REFUND (score: {suggested_score:.2f})",
            "requires_human_approval": True,
        }


# Legacy function for backwards compatibility
async def evaluate_quality(
    task_type: str,
    task_description: str,
    result: dict,
) -> float:
    """Legacy function - returns just the suggested score.

    DEPRECATED: Use get_quality_suggestion() for full human-in-the-loop flow.
    """
    suggestion = await get_quality_suggestion(task_type, task_description, result)
    return suggestion.get("suggested_overall", 0.5)


# Legacy function for backwards compatibility
async def check_quality_threshold(quality_score: float) -> dict:
    """Legacy function - check if quality score passes threshold.

    DEPRECATED: Use get_payment_recommendation() with full AI suggestion.
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
            "requires_human_approval": True,  # Added for new flow
        }
    elif quality_score >= threshold * 0.7:
        return {
            "passed": False,
            "action": "partial_payment",
            "quality_score": quality_score,
            "threshold": threshold,
            "payment_ratio": 0.5,
            "message": f"Quality score {quality_score:.2f} below threshold, partial payment suggested",
            "requires_human_approval": True,
        }
    else:
        return {
            "passed": False,
            "action": "refund",
            "quality_score": quality_score,
            "threshold": threshold,
            "message": f"Quality score {quality_score:.2f} too low, refund suggested",
            "requires_human_approval": True,
        }


def _safe_score(value) -> float:
    """Ensure score is a valid float between 0 and 1."""
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.5


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
