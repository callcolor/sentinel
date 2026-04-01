"""Level 2 reasoning — expensive, rare, on-demand.

Triggered only when Level 1 flags something above the sensitivity threshold.
Sends the flagged request, surrounding context, and server metadata to a
reasoning model via the OpenAI-compatible provider interface.

Level 2 answers: "What does this mean and what should the developer know?"
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from ..providers.openai_compat import ProviderClient, ProviderError
from .prompts import build_anomaly_prompt

logger = logging.getLogger("sentinel")


@dataclass
class Insight:
    """Structured output from Level 2 reasoning."""

    tool_name: str
    anomaly_score: float
    reasons: list[str]
    analysis: str
    timestamp: float = field(default_factory=time.time)


class RateLimiter:
    """Sliding window rate limiter for Level 2 invocations."""

    def __init__(self, max_calls_per_hour: int):
        self.max_calls = max_calls_per_hour
        self._timestamps: list[float] = []

    def allow(self) -> bool:
        now = time.time()
        cutoff = now - 3600
        self._timestamps = [t for t in self._timestamps if t > cutoff]
        if len(self._timestamps) >= self.max_calls:
            return False
        self._timestamps.append(now)
        return True

    @property
    def remaining(self) -> int:
        now = time.time()
        cutoff = now - 3600
        active = sum(1 for t in self._timestamps if t > cutoff)
        return max(0, self.max_calls - active)


class Reasoner:
    """Level 2 reasoner — sends anomalies to a reasoning model for analysis."""

    def __init__(
        self,
        provider_url: str,
        api_key: Optional[str] = None,
        model: str = "anthropic/claude-sonnet-4",
        max_calls_per_hour: int = 10,
    ):
        self.client = ProviderClient(
            base_url=provider_url,
            api_key=api_key,
            model=model,
            timeout=60.0,
        )
        self.rate_limiter = RateLimiter(max_calls_per_hour)

    async def analyze(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None,
        anomaly_score: float,
        reasons: list[str],
        baseline_summary: dict,
    ) -> Optional[Insight]:
        """Send an anomaly to the reasoning model for analysis.

        Returns None if rate-limited or if the provider call fails.
        Failures are logged but never raised — Level 2 must not break Level 0.
        """
        if not self.rate_limiter.allow():
            logger.warning(
                "sentinel L2: rate limited (0 of %d calls remaining this hour)",
                self.rate_limiter.max_calls,
            )
            return None

        messages = build_anomaly_prompt(
            tool_name=tool_name,
            arguments=arguments,
            anomaly_score=anomaly_score,
            reasons=reasons,
            baseline_summary=baseline_summary,
        )

        try:
            analysis = await self.client.chat(messages)
        except ProviderError as e:
            logger.error("sentinel L2: provider error: %s", e)
            return None
        except Exception as e:
            logger.error("sentinel L2: unexpected error: %s: %s", type(e).__name__, e)
            return None

        insight = Insight(
            tool_name=tool_name,
            anomaly_score=anomaly_score,
            reasons=reasons,
            analysis=analysis,
        )

        logger.info(
            "sentinel L2 insight: %s",
            json.dumps({
                "tool": insight.tool_name,
                "score": insight.anomaly_score,
                "analysis": insight.analysis[:200],
                "remaining_calls": self.rate_limiter.remaining,
            }),
        )

        return insight

    async def close(self) -> None:
        await self.client.close()
