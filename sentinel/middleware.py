"""SentinelMiddleware — FastMCP integration point.

Drop-in middleware that adds intelligence to any FastMCP server.
Intercepts tool calls, lets them execute normally, then fires off non-blocking
Level 1 analysis. When anomalies are detected and a reasoning provider is
configured, escalates to Level 2 for deeper analysis.
"""

import logging
from typing import Any, Optional

import mcp.types as mt
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext

from .config import SentinelConfig
from .level1.monitor import Monitor

logger = logging.getLogger("sentinel")


class SentinelMiddleware(Middleware):
    """Intelligent middleware for MCP servers.

    Usage::

        from fastmcp import FastMCP
        from sentinel import SentinelMiddleware

        mcp = FastMCP("MyServer")
        mcp.add_middleware(SentinelMiddleware(sensitivity=0.7))
    """

    def __init__(
        self,
        *,
        # Provider endpoints
        embedding_provider: Optional[str] = None,
        reasoning_provider: Optional[str] = None,
        embedding_key: Optional[str] = None,
        reasoning_key: Optional[str] = None,
        embedding_model: Optional[str] = None,
        reasoning_model: Optional[str] = None,
        triage_model: Optional[str] = None,
        # Core
        sensitivity: float = 0.7,
        output: str = "log",
        webhook_url: Optional[str] = None,
        dashboard_port: Optional[int] = None,
        storage_path: str = "./sentinel_data",
        baseline_threshold: int = 100,
        max_reasoning_calls_per_hour: int = 10,
    ):
        self.config = SentinelConfig(
            embedding_provider=embedding_provider,
            reasoning_provider=reasoning_provider,
            embedding_key=embedding_key,
            reasoning_key=reasoning_key,
            embedding_model=embedding_model,
            reasoning_model=reasoning_model,
            triage_model=triage_model,
            sensitivity=sensitivity,
            output=output,
            webhook_url=webhook_url,
            dashboard_port=dashboard_port,
            storage_path=storage_path,
            baseline_threshold=baseline_threshold,
            max_reasoning_calls_per_hour=max_reasoning_calls_per_hour,
        )
        self.monitor = Monitor(self.config)

    async def on_call_tool(
        self,
        context: MiddlewareContext[mt.CallToolRequestParams],
        call_next: CallNext[mt.CallToolRequestParams, Any],
    ) -> Any:
        """Intercept tool calls for Level 1 analysis.

        The tool executes normally via call_next. After the result (or error)
        is captured, analysis is dispatched as a non-blocking background task
        so the MCP response is never delayed.
        """
        tool_name = context.message.name
        arguments = context.message.arguments

        result = None
        is_error = False
        error_message = None

        try:
            result = await call_next(context)
            return result
        except Exception as e:
            is_error = True
            error_message = str(e)
            raise
        finally:
            self.monitor.record_tool_call_nonblocking(
                tool_name=tool_name,
                arguments=arguments,
                result=result,
                is_error=is_error,
                error_message=error_message,
            )
