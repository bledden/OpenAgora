"""Real agent execution engine for Open Agora.

Each agent type has:
1. Specialized system prompts for their domain
2. Their own model configuration (provider + model)
3. Accurate cost tracking based on their model's pricing

Agents are specialized - they use models optimized for their task type.
"""

import asyncio
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timezone
import structlog

from ..llm import call_fireworks, call_fireworks_json, LLMResponse
from ..db import get_agent, update_agent

logger = structlog.get_logger()


@dataclass
class ExecutionResult:
    """Result of agent job execution."""
    success: bool
    output: Any
    tokens_used: int
    cost_usd: float
    latency_ms: float
    model_used: str = ""
    error: Optional[str] = None


# Model pricing per 1K tokens (as of Jan 2025)
# Format: {model_id: (input_cost, output_cost)}
MODEL_PRICING = {
    # Fireworks models
    "accounts/fireworks/models/llama-v3p3-70b-instruct": (0.0009, 0.0009),
    "accounts/fireworks/models/llama-v3p1-8b-instruct": (0.0002, 0.0002),
    "accounts/fireworks/models/mixtral-8x7b-instruct": (0.0005, 0.0005),
    "accounts/fireworks/models/qwen2p5-72b-instruct": (0.0009, 0.0009),
    "accounts/fireworks/models/deepseek-v3": (0.0009, 0.0009),
    # Code-specialized
    "accounts/fireworks/models/qwen2p5-coder-32b-instruct": (0.0009, 0.0009),
    "accounts/fireworks/models/deepseek-coder-v2-instruct": (0.0012, 0.0012),
    # Default fallback
    "default": (0.0009, 0.0009),
}


# Agent-specific system prompts
AGENT_PROMPTS = {
    "agent_anomaly_hunter": """You are AnomalyHunter, an expert anomaly detection agent.

Your specialties:
- Detecting statistical outliers and anomalies in data
- Identifying unusual patterns that deviate from expected behavior
- Fraud detection and suspicious activity identification
- System monitoring and alerting on abnormal metrics
- Quality control and defect detection

When analyzing data:
1. First understand the baseline/expected behavior
2. Identify deviations using statistical methods (z-scores, IQR, etc.)
3. Classify anomalies by severity (critical, warning, info)
4. Provide actionable insights on each anomaly found
5. Suggest root causes when possible

Output structured findings with confidence scores.""",

    "agent_code_reviewer": """You are CodeReviewer Pro, an expert code review agent.

Your specialties:
- Security vulnerability detection (OWASP Top 10, injection, XSS, etc.)
- Code quality and best practices assessment
- Performance optimization suggestions
- Bug and logic error identification
- Code maintainability and readability feedback

When reviewing code:
1. Identify security issues first (highest priority)
2. Check for common bugs and edge cases
3. Assess code structure and design patterns
4. Suggest specific improvements with code examples
5. Rate overall code quality (1-10)

Be thorough but constructive. Provide line-specific feedback when possible.""",

    "agent_data_analyst": """You are DataAnalyst, an expert data analysis agent.

Your specialties:
- Transforming natural language into SQL queries
- Analyzing datasets to extract insights
- Identifying trends, patterns, and correlations
- Creating summaries and visualizations descriptions
- Business intelligence and reporting

When analyzing data:
1. Understand the question or objective clearly
2. Identify relevant data points and relationships
3. Apply appropriate analytical methods
4. Present findings in clear, actionable format
5. Include confidence levels and caveats

Provide both technical details and business-friendly summaries.""",

    "agent_researcher": """You are ResearchAgent, a deep research specialist.

Your specialties:
- Comprehensive research on any topic
- Synthesizing information from multiple perspectives
- Generating detailed reports with citations
- Market research and competitive analysis
- Literature reviews and trend analysis

When researching:
1. Break down the topic into key questions
2. Gather information from multiple angles
3. Synthesize findings into coherent narrative
4. Highlight key insights and implications
5. Provide actionable recommendations

Always cite sources and acknowledge limitations.""",

    "agent_doc_summarizer": """You are DocSummarizer, an expert document summarization agent.

Your specialties:
- Condensing lengthy documents while preserving key information
- Creating executive summaries for quick consumption
- Extracting key points, decisions, and action items
- Multi-document synthesis and comparison
- Technical document simplification

When summarizing:
1. Identify the document type and purpose
2. Extract main themes and key points
3. Preserve critical details and nuances
4. Structure output for easy scanning
5. Highlight any actionable items

Adjust summary length and detail based on the request.""",

    "agent_sentiment_pro": """You are SentimentPro, an expert sentiment analysis agent.

Your specialties:
- Emotional tone analysis (positive, negative, neutral, mixed)
- Opinion mining and stance detection
- Brand perception and reputation analysis
- Customer feedback categorization
- Social media sentiment tracking

When analyzing sentiment:
1. Identify overall sentiment polarity and intensity
2. Detect specific emotions (joy, anger, frustration, etc.)
3. Extract key opinion phrases and subjects
4. Consider context and sarcasm
5. Provide confidence scores for assessments

Output structured sentiment analysis with supporting evidence.""",
}

# Default prompt for unknown agents
DEFAULT_PROMPT = """You are a helpful AI assistant on the Open Agora marketplace.
Complete the requested task to the best of your ability.
Be thorough, accurate, and provide actionable results."""


def get_model_cost(model: str) -> tuple[float, float]:
    """Get pricing for a model (input_cost, output_cost) per 1K tokens."""
    return MODEL_PRICING.get(model, MODEL_PRICING["default"])


async def execute_agent_job(
    agent_id: str,
    job_description: str,
    job_context: Optional[Dict[str, Any]] = None,
) -> ExecutionResult:
    """Execute a job using the specified agent's configured model.

    Each agent has its own model configuration optimized for its specialty.
    Cost is calculated based on the specific model used.

    Args:
        agent_id: The agent to use for execution
        job_description: The job/task description
        job_context: Optional additional context

    Returns:
        ExecutionResult with output and metrics
    """
    start_time = datetime.now(timezone.utc)

    # Get agent details
    agent = await get_agent(agent_id)
    if not agent:
        return ExecutionResult(
            success=False,
            output=None,
            tokens_used=0,
            cost_usd=0,
            latency_ms=0,
            error=f"Agent {agent_id} not found",
        )

    # Get agent's configured model (or default)
    agent_model = agent.get("model", "accounts/fireworks/models/llama-v3p3-70b-instruct")
    agent_provider = agent.get("provider", "fireworks")

    # Get specialized prompt or default
    system_prompt = agent.get("system_prompt") or AGENT_PROMPTS.get(agent_id, DEFAULT_PROMPT)

    # Build the task prompt
    task_prompt = f"""## Task
{job_description}

"""
    if job_context:
        task_prompt += f"""## Additional Context
{job_context}

"""
    task_prompt += """## Instructions
Complete this task thoroughly. Provide structured output when appropriate.
If the task requires analysis, include your methodology and confidence levels.
"""

    try:
        # Call the LLM with agent's configured model
        response: LLMResponse = await call_fireworks(
            prompt=task_prompt,
            system_prompt=system_prompt,
            temperature=0.4,  # Lower temp for more consistent results
            max_tokens=4096,
            model=agent_model,
        )

        # Calculate cost based on agent's model
        input_cost, output_cost = get_model_cost(agent_model)
        tokens_used = response.tokens_input + response.tokens_output
        cost_usd = (
            (response.tokens_input / 1000) * input_cost +
            (response.tokens_output / 1000) * output_cost
        )

        logger.info(
            "agent_execution_complete",
            agent_id=agent_id,
            model=agent_model,
            tokens_in=response.tokens_input,
            tokens_out=response.tokens_output,
            cost_usd=round(cost_usd, 6),
            latency_ms=round(response.latency_ms, 2),
        )

        # Update agent stats
        await update_agent(agent_id, {
            "jobs_completed": (agent.get("jobs_completed", 0) + 1),
            "total_earned_usd": (agent.get("total_earned_usd", 0) + cost_usd * 10),  # Agent earns 10x cost
            "last_active": datetime.now(timezone.utc),
        })

        return ExecutionResult(
            success=True,
            output=response.content,
            tokens_used=tokens_used,
            cost_usd=cost_usd,
            latency_ms=response.latency_ms,
            model_used=agent_model,
        )

    except Exception as e:
        logger.error("agent_execution_failed", agent_id=agent_id, model=agent_model, error=str(e))

        # Update failure stats
        await update_agent(agent_id, {
            "jobs_failed": (agent.get("jobs_failed", 0) + 1),
            "last_active": datetime.now(timezone.utc),
        })

        return ExecutionResult(
            success=False,
            output=None,
            tokens_used=0,
            cost_usd=0,
            latency_ms=(datetime.now(timezone.utc) - start_time).total_seconds() * 1000,
            error=str(e),
        )


async def get_agent_bid(
    agent_id: str,
    job_description: str,
    job_budget: float,
) -> Dict[str, Any]:
    """Have an agent evaluate a job and generate a bid.

    Uses the agent's configured model for evaluation.

    Args:
        agent_id: The agent evaluating the job
        job_description: The job description
        job_budget: The poster's budget

    Returns:
        Bid details including price and confidence
    """
    agent = await get_agent(agent_id)
    if not agent:
        return {"error": "Agent not found"}

    # Get agent's model for bid evaluation
    agent_model = agent.get("model", "accounts/fireworks/models/llama-v3p3-70b-instruct")

    system_prompt = f"""You are {agent.get('name', 'an AI agent')} evaluating a job for bidding.

Your capabilities: {agent.get('capabilities', {})}
Your base rate: ${agent.get('base_rate_usd', 0.10)} per task
Your model: {agent_model}

Evaluate if you can complete this job and at what price.
Consider your actual compute costs when pricing."""

    prompt = f"""## Job Description
{job_description}

## Poster's Budget
${job_budget}

## Your Task
Evaluate this job and provide a bid. Consider:
1. Does this match your capabilities?
2. How complex is the task?
3. What's a fair price given the budget and your skills?

Respond with JSON:
{{
    "can_complete": true/false,
    "confidence": 0.0-1.0,
    "bid_amount_usd": <your bid>,
    "estimated_time_minutes": <estimate>,
    "reasoning": "<brief explanation>"
}}"""

    try:
        result = await call_fireworks_json(prompt, system_prompt, model=agent_model)
        return result
    except Exception as e:
        logger.error("bid_generation_failed", agent_id=agent_id, error=str(e))
        return {
            "can_complete": False,
            "confidence": 0,
            "bid_amount_usd": 0,
            "error": str(e),
        }
