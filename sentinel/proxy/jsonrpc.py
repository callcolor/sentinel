"""JSON-RPC 2.0 parsing utilities for MCP message interception.

Used by both the stdio and HTTP proxy modes to extract tool call
information from JSON-RPC messages without depending on mcp/fastmcp types.
"""

import json
import logging
from typing import Any

logger = logging.getLogger("sentinel")


def parse_jsonrpc(data: bytes | str) -> dict | None:
    """Safely parse a JSON-RPC message. Returns None on failure."""
    try:
        if isinstance(data, bytes):
            data = data.decode("utf-8", errors="replace")
        data = data.strip()
        if not data:
            return None
        msg = json.loads(data)
        if isinstance(msg, dict):
            return msg
        return None
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def get_request_id(msg: dict) -> int | str | None:
    """Extract the JSON-RPC request/response ID."""
    return msg.get("id")


def is_tool_call_request(msg: dict) -> bool:
    """Check if this is a tools/call request."""
    return msg.get("method") == "tools/call" and "id" in msg


def extract_tool_call(msg: dict) -> tuple[str, dict[str, Any] | None]:
    """Extract (tool_name, arguments) from a tools/call request.

    Expects: {"method": "tools/call", "params": {"name": "...", "arguments": {...}}}
    """
    params = msg.get("params", {})
    tool_name = params.get("name", "")
    arguments = params.get("arguments")
    return tool_name, arguments


def extract_tool_result(msg: dict) -> tuple[Any, bool, str | None]:
    """Extract (result, is_error, error_message) from a JSON-RPC response.

    Handles both success responses (with optional isError flag) and
    JSON-RPC error responses.

    Returns:
        (result_data, is_error, error_message)
    """
    # JSON-RPC error response
    if "error" in msg:
        err = msg["error"]
        error_message = err.get("message", "unknown error")
        return None, True, error_message

    # Success response — check MCP's isError flag
    result = msg.get("result", {})
    if isinstance(result, dict) and result.get("isError"):
        # Tool returned an error through MCP's structured error mechanism
        content = result.get("content", [])
        error_text = ""
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                error_text = item.get("text", "")
                break
        return result, True, error_text or "tool error"

    return result, False, None
