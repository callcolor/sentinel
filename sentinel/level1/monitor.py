"""Async, non-blocking stat collection for Level 1.

The Monitor receives tool call events, fingerprints them, checks against
the baseline, and emits structured log output — all without blocking the
MCP request/response cycle.
"""

import asyncio
import json
import logging
from typing import Any

from ..config import SentinelConfig
from .baseline import AnomalyResult, Baseline
from .fingerprint import fingerprint_tool_call

logger = logging.getLogger("sentinel")


class Monitor:
    """Level 1 monitor — cheap, fast, every request."""

    def __init__(self, config: SentinelConfig):
        self.config = config
        self.baseline = Baseline(
            db_path=f"{config.storage_path}/baseline.db",
            threshold=config.baseline_threshold,
        )
        self._initialized = False

    async def initialize(self) -> None:
        if not self._initialized:
            await self.baseline.initialize()
            self._initialized = True

    async def record_tool_call(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None,
        result: Any = None,
        *,
        is_error: bool = False,
        error_message: str | None = None,
    ) -> AnomalyResult:
        """Record a tool call and check it against the baseline.

        This is the awaitable version — use `record_tool_call_nonblocking`
        to fire-and-forget from middleware.
        """
        await self.initialize()

        fp = fingerprint_tool_call(
            tool_name=tool_name,
            arguments=arguments,
            is_error=is_error,
            error_message=error_message,
        )

        # Check BEFORE updating so the current call doesn't influence its own score
        anomaly = await self.baseline.is_anomalous(fp, self.config.sensitivity)
        await self.baseline.update(fp)

        self._emit(fp, anomaly)
        return anomaly

    def record_tool_call_nonblocking(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None,
        result: Any = None,
        *,
        is_error: bool = False,
        error_message: str | None = None,
    ) -> None:
        """Fire-and-forget wrapper — schedules analysis as a background task.

        Called from middleware so the MCP response is never delayed.
        """
        asyncio.create_task(
            self.record_tool_call(
                tool_name=tool_name,
                arguments=arguments,
                result=result,
                is_error=is_error,
                error_message=error_message,
            )
        )

    def _emit(self, fp, anomaly: AnomalyResult) -> None:
        """Emit a structured log entry for this observation."""
        entry = {
            "tool": fp.tool_name,
            "shape": fp.shape_hash,
            "is_error": fp.is_error,
            "anomaly_score": anomaly.score,
            "is_anomalous": anomaly.is_anomalous,
            "reasons": anomaly.reasons,
            "baseline_established": self.baseline.is_established,
            "observations": self.baseline._total_observations,
        }

        if anomaly.is_anomalous:
            logger.warning("sentinel anomaly: %s", json.dumps(entry))
        else:
            logger.debug("sentinel: %s", json.dumps(entry))

    async def close(self) -> None:
        await self.baseline.close()
