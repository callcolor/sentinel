"""Stdio proxy — wraps any MCP server over stdio.

Spawns the target command as a subprocess, sits between the MCP client
and the server, forwarding all traffic while intercepting tool calls
for Level 1/2 analysis.

Usage: sentinel wrap -- node my-server.js
"""

import asyncio
import logging
import sys
from typing import Any

from .jsonrpc import (
    extract_tool_call,
    extract_tool_result,
    get_request_id,
    is_tool_call_request,
    parse_jsonrpc,
)
from ..level1.monitor import Monitor

logger = logging.getLogger("sentinel")


class StdioProxy:
    """Transparent stdio proxy for MCP servers.

    Spawns the target command and pipes stdin/stdout between the MCP client
    and the child process. Intercepts JSON-RPC messages to feed Sentinel's
    intelligence layer without adding latency.
    """

    def __init__(self, command: list[str], monitor: Monitor):
        self.command = command
        self.monitor = monitor
        # Pending tool calls: request_id -> (tool_name, arguments)
        self._pending: dict[int | str, tuple[str, dict[str, Any] | None]] = {}

    async def run(self) -> int:
        """Run the proxy. Returns the child process exit code."""
        await self.monitor.initialize()

        child = await asyncio.create_subprocess_exec(
            *self.command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        logger.info("sentinel: wrapping %s (pid %d)", self.command, child.pid)

        stdin_task = asyncio.create_task(self._pipe_client_to_server(child))
        stdout_task = asyncio.create_task(self._pipe_server_to_client(child))
        stderr_task = asyncio.create_task(self._pipe_stderr(child))

        # Wait for output readers to drain (they finish when child closes its pipes)
        await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)

        # Output fully drained — cancel stdin reader (may be blocked on thread readline)
        stdin_task.cancel()
        try:
            await stdin_task
        except asyncio.CancelledError:
            pass

        if child.returncode is None:
            child.terminate()
            try:
                await asyncio.wait_for(child.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                child.kill()

        await self.monitor.close()
        return child.returncode or 0

    async def _pipe_client_to_server(self, child: asyncio.subprocess.Process) -> None:
        """Read from own stdin, inspect, forward to child stdin."""
        loop = asyncio.get_running_loop()

        while True:
            # Windows can't do async stdin — use thread pool
            line = await loop.run_in_executor(None, sys.stdin.buffer.readline)
            if not line:
                # Client closed stdin — signal child to shut down
                child.stdin.close()
                return

            # Inspect for tool call requests
            msg = parse_jsonrpc(line)
            if msg and is_tool_call_request(msg):
                req_id = get_request_id(msg)
                tool_name, arguments = extract_tool_call(msg)
                if req_id is not None:
                    self._pending[req_id] = (tool_name, arguments)
                    logger.debug("sentinel: tracking tools/call id=%s tool=%s", req_id, tool_name)

            # Forward verbatim — never modify the message
            child.stdin.write(line)
            await child.stdin.drain()

    async def _pipe_server_to_client(self, child: asyncio.subprocess.Process) -> None:
        """Read from child stdout, inspect, forward to own stdout."""
        while True:
            line = await child.stdout.readline()
            if not line:
                return

            # Forward immediately — before analysis
            sys.stdout.buffer.write(line)
            sys.stdout.buffer.flush()

            # Inspect for responses to pending tool calls
            msg = parse_jsonrpc(line)
            if msg:
                req_id = get_request_id(msg)
                if req_id is not None and req_id in self._pending:
                    tool_name, arguments = self._pending.pop(req_id)
                    result, is_error, error_message = extract_tool_result(msg)
                    self.monitor.record_tool_call_nonblocking(
                        tool_name=tool_name,
                        arguments=arguments,
                        result=result,
                        is_error=is_error,
                        error_message=error_message,
                    )

    async def _pipe_stderr(self, child: asyncio.subprocess.Process) -> None:
        """Pass through child stderr to own stderr."""
        while True:
            line = await child.stderr.readline()
            if not line:
                return
            sys.stderr.buffer.write(line)
            sys.stderr.buffer.flush()
