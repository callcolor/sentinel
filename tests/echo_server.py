"""Minimal MCP-like echo server over stdio for testing the proxy.

Reads JSON-RPC lines from stdin, responds to tools/call with an echo.
"""

import json
import sys


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue

        if msg.get("method") == "tools/call":
            tool_name = msg.get("params", {}).get("name", "")
            arguments = msg.get("params", {}).get("arguments", {})
            response = {
                "jsonrpc": "2.0",
                "id": msg.get("id"),
                "result": {
                    "content": [{"type": "text", "text": f"echo: {tool_name}({arguments})"}],
                    "isError": False,
                },
            }
            print(json.dumps(response), flush=True)
        elif msg.get("method") == "initialize":
            response = {
                "jsonrpc": "2.0",
                "id": msg.get("id"),
                "result": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "echo-server", "version": "0.1"},
                },
            }
            print(json.dumps(response), flush=True)


if __name__ == "__main__":
    main()
