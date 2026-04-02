"""HTTP reverse proxy — wraps MCP-over-HTTP and REST APIs.

Sits between clients and the target server, forwarding all traffic
while intercepting request/response pairs for Sentinel analysis.

Usage:
    sentinel proxy --target http://localhost:3000 --port 8080
    sentinel proxy --target http://localhost:5000 --port 8080 --mode rest
"""

import logging
from typing import Any

import aiohttp
from aiohttp import web

from .jsonrpc import (
    extract_tool_call,
    extract_tool_result,
    is_tool_call_request,
    parse_jsonrpc,
)
from ..level1.fingerprint import fingerprint_http_request
from ..level1.monitor import Monitor

logger = logging.getLogger("sentinel")

# Headers that must not be forwarded between hops
_HOP_BY_HOP = frozenset({
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade",
})


class HttpProxy:
    """Transparent HTTP reverse proxy with Sentinel intelligence.

    Supports two modes:
    - "mcp": parses JSON-RPC bodies to intercept MCP tool calls
    - "rest": fingerprints HTTP method + path + body shape
    """

    def __init__(self, target: str, port: int, monitor: Monitor, mode: str = "mcp"):
        self.target = target.rstrip("/")
        self.port = port
        self.monitor = monitor
        self.mode = mode
        self._session: aiohttp.ClientSession | None = None

    async def run(self) -> None:
        """Start the reverse proxy server."""
        await self.monitor.initialize()
        self._session = aiohttp.ClientSession()

        app = web.Application()
        app.router.add_route("*", "/{path_info:.*}", self._handle)
        app.on_cleanup.append(self._cleanup)

        logger.info(
            "sentinel: proxying %s on port %d (mode=%s)",
            self.target, self.port, self.mode,
        )

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", self.port)
        await site.start()

        # Run until interrupted
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            pass
        finally:
            await runner.cleanup()

    async def _handle(self, request: web.Request) -> web.Response:
        """Forward a request to the target and analyze the pair."""
        path = request.match_info.get("path_info", "")
        target_url = f"{self.target}/{path}"
        if request.query_string:
            target_url += f"?{request.query_string}"

        # Read request body
        request_body = await request.read()

        # Forward headers (strip hop-by-hop)
        headers = {
            k: v for k, v in request.headers.items()
            if k.lower() not in _HOP_BY_HOP and k.lower() != "host"
        }

        # Forward to target
        async with self._session.request(
            method=request.method,
            url=target_url,
            headers=headers,
            data=request_body,
        ) as upstream:
            response_body = await upstream.read()
            response_headers = {
                k: v for k, v in upstream.headers.items()
                if k.lower() not in _HOP_BY_HOP
            }

            # Build response to client
            response = web.Response(
                status=upstream.status,
                headers=response_headers,
                body=response_body,
            )

        # Analyze AFTER response is built (non-blocking)
        if self.mode == "mcp":
            self._analyze_mcp(request_body, response_body)
        else:
            self._analyze_rest(request.method, f"/{path}", request_body, response_body, response.status)

        return response

    def _analyze_mcp(self, request_body: bytes, response_body: bytes) -> None:
        """Extract tool call info from JSON-RPC request/response pair."""
        req_msg = parse_jsonrpc(request_body)
        if not req_msg or not is_tool_call_request(req_msg):
            return

        tool_name, arguments = extract_tool_call(req_msg)
        resp_msg = parse_jsonrpc(response_body)

        if resp_msg:
            result, is_error, error_message = extract_tool_result(resp_msg)
        else:
            result, is_error, error_message = None, True, "unparseable response"

        self.monitor.record_tool_call_nonblocking(
            tool_name=tool_name,
            arguments=arguments,
            result=result,
            is_error=is_error,
            error_message=error_message,
        )

    def _analyze_rest(
        self,
        method: str,
        path: str,
        request_body: bytes,
        response_body: bytes,
        status_code: int,
    ) -> None:
        """Fingerprint an HTTP request/response pair for REST mode."""
        # Parse request body as JSON if possible
        body_dict = None
        req_msg = parse_jsonrpc(request_body)
        if req_msg:
            body_dict = req_msg

        fp = fingerprint_http_request(
            method=method,
            path=path,
            body=body_dict,
            status_code=status_code,
        )

        self.monitor.record_tool_call_nonblocking(
            tool_name=fp.tool_name,
            arguments=body_dict,
            result=None,
            is_error=fp.is_error,
            error_message=fp.error_message,
        )

    async def _cleanup(self, app: web.Application) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
        await self.monitor.close()


# Needed for the Event().wait() in run()
import asyncio
