"""LLM provider for AgentBazaar."""

import time
import json
import re
from typing import Optional
from dataclasses import dataclass
import httpx
import structlog

from .config import get_settings

logger = structlog.get_logger()


@dataclass
class LLMResponse:
    """Standardized LLM response."""
    content: str
    tokens_input: int
    tokens_output: int
    model: str
    latency_ms: float


async def call_fireworks(
    prompt: str,
    system_prompt: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> LLMResponse:
    """Call Fireworks AI for fast inference."""
    settings = get_settings()
    start_time = time.time()

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.fireworks.ai/inference/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.fireworks_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.fireworks_model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            timeout=120.0,
        )
        response.raise_for_status()
        data = response.json()

    latency_ms = (time.time() - start_time) * 1000

    return LLMResponse(
        content=data["choices"][0]["message"]["content"],
        tokens_input=data.get("usage", {}).get("prompt_tokens", 0),
        tokens_output=data.get("usage", {}).get("completion_tokens", 0),
        model=settings.fireworks_model,
        latency_ms=latency_ms,
    )


async def call_fireworks_json(
    prompt: str,
    system_prompt: Optional[str] = None,
    temperature: float = 0.3,
) -> dict:
    """Call Fireworks and parse JSON response."""
    json_system = (system_prompt or "") + "\n\nRespond with valid JSON only. No markdown or explanation."

    response = await call_fireworks(
        prompt=prompt,
        system_prompt=json_system,
        temperature=temperature,
    )

    content = response.content.strip()

    # Remove markdown code blocks
    if content.startswith("```json"):
        content = content[7:]
    if content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    content = content.strip()

    # Try direct parse
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # Try to find JSON in response
    json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    # Try array
    array_match = re.search(r'\[[^\[\]]*(?:\[[^\[\]]*\][^\[\]]*)*\]', content, re.DOTALL)
    if array_match:
        try:
            return json.loads(array_match.group())
        except json.JSONDecodeError:
            pass

    logger.warning("json_parse_failed", content_preview=content[:200])
    return {"error": "Failed to parse JSON", "raw": content[:500]}


async def call_nemotron(
    prompt: str,
    system_prompt: Optional[str] = None,
    temperature: float = 0.7,
) -> Optional[str]:
    """Call NVIDIA Nemotron Ultra for complex reasoning."""
    settings = get_settings()

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://integrate.api.nvidia.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.nvidia_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.nemotron_model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": 8192,
                },
                timeout=300.0,
            )
            if response.status_code != 200:
                logger.error("nemotron_error", status=response.status_code)
                return None

            data = response.json()
            message = data["choices"][0]["message"]

            # Nemotron Ultra returns reasoning in 'reasoning_content'
            content = message.get("content")
            if content is None:
                content = message.get("reasoning_content")

            return content
    except Exception as e:
        logger.error("nemotron_exception", error=str(e))
        return None


async def call_llm(
    prompt: str,
    system_prompt: Optional[str] = None,
    max_tokens: int = 1024,
    temperature: float = 0.7,
) -> str:
    """Simple LLM call returning text response.

    Convenience wrapper around call_fireworks for simple text generation.
    """
    response = await call_fireworks(
        prompt=prompt,
        system_prompt=system_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.content


async def get_embedding(text: str) -> list[float]:
    """Get Voyage AI embedding for text."""
    settings = get_settings()

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.voyageai.com/v1/embeddings",
            headers={
                "Authorization": f"Bearer {settings.voyage_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "input": text,
                "model": "voyage-2",
            },
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()

    return data["data"][0]["embedding"]
