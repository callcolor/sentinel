"""Sentinel CLI — intelligent proxy for MCP servers and REST APIs.

Usage:
    sentinel wrap -- node my-server.js
    sentinel proxy --target http://localhost:3000 --port 8080
    sentinel proxy --target http://localhost:5000 --port 8080 --mode rest
"""

import asyncio
import logging
import os
import sys
from typing import Annotated, Optional

import cyclopts

from .config import SentinelConfig
from .level1.monitor import Monitor

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = cyclopts.App(
    name="sentinel",
    help="Intelligent proxy for MCP servers and REST APIs",
)


def _env(name: str, default: str | None = None) -> str | None:
    """Read from SENTINEL_* env var with fallback."""
    return os.environ.get(f"SENTINEL_{name.upper()}", default)


def _build_config(
    sensitivity: float,
    storage_path: str,
    baseline_threshold: int,
    reasoning_provider: str | None,
    reasoning_key: str | None,
    reasoning_model: str | None,
    max_reasoning_calls_per_hour: int,
) -> SentinelConfig:
    """Build SentinelConfig from CLI flags with env var fallbacks."""
    return SentinelConfig(
        sensitivity=sensitivity,
        storage_path=storage_path,
        baseline_threshold=baseline_threshold,
        reasoning_provider=reasoning_provider or _env("REASONING_PROVIDER"),
        reasoning_key=reasoning_key or _env("REASONING_KEY"),
        reasoning_model=reasoning_model or _env("REASONING_MODEL"),
        max_reasoning_calls_per_hour=max_reasoning_calls_per_hour,
    )


def _setup_logging() -> None:
    """Configure structured logging to stderr."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )


@app.command
def wrap(
    *,
    sensitivity: float = 0.7,
    storage_path: str = "./sentinel_data",
    baseline_threshold: int = 100,
    reasoning_provider: Optional[str] = None,
    reasoning_key: Optional[str] = None,
    reasoning_model: Optional[str] = None,
    max_reasoning_calls_per_hour: int = 10,
) -> None:
    """Wrap an MCP server over stdio.

    Usage: sentinel wrap -- node server.js
    Everything after -- is the command to run.
    """
    _setup_logging()

    command = _child_command
    if not command:
        print("Error: no command specified. Usage: sentinel wrap -- <command>", file=sys.stderr)
        sys.exit(1)

    config = _build_config(
        sensitivity=sensitivity,
        storage_path=storage_path,
        baseline_threshold=baseline_threshold,
        reasoning_provider=reasoning_provider,
        reasoning_key=reasoning_key,
        reasoning_model=reasoning_model,
        max_reasoning_calls_per_hour=max_reasoning_calls_per_hour,
    )

    from .proxy.stdio import StdioProxy

    monitor = Monitor(config)
    proxy = StdioProxy(command=command, monitor=monitor)
    exit_code = asyncio.run(proxy.run())
    sys.exit(exit_code)


@app.command
def proxy(
    *,
    target: str,
    port: int = 8080,
    mode: str = "mcp",
    sensitivity: float = 0.7,
    storage_path: str = "./sentinel_data",
    baseline_threshold: int = 100,
    reasoning_provider: Optional[str] = None,
    reasoning_key: Optional[str] = None,
    reasoning_model: Optional[str] = None,
    max_reasoning_calls_per_hour: int = 10,
) -> None:
    """Reverse-proxy an HTTP server.

    Usage: sentinel proxy --target http://localhost:3000 --port 8080
    """
    _setup_logging()

    if mode not in ("mcp", "rest"):
        print(f"Error: mode must be 'mcp' or 'rest', got '{mode}'", file=sys.stderr)
        sys.exit(1)

    config = _build_config(
        sensitivity=sensitivity,
        storage_path=storage_path,
        baseline_threshold=baseline_threshold,
        reasoning_provider=reasoning_provider,
        reasoning_key=reasoning_key,
        reasoning_model=reasoning_model,
        max_reasoning_calls_per_hour=max_reasoning_calls_per_hour,
    )

    from .proxy.http import HttpProxy

    monitor = Monitor(config)
    http_proxy = HttpProxy(target=target, port=port, monitor=monitor, mode=mode)
    asyncio.run(http_proxy.run())


_child_command: list[str] = []


def main() -> None:
    global _child_command
    argv = sys.argv[1:]  # strip program name

    # Split at -- to separate sentinel flags from child command
    if "--" in argv:
        idx = argv.index("--")
        sentinel_args = argv[:idx]
        _child_command = argv[idx + 1:]
    else:
        sentinel_args = argv
        _child_command = []

    app(sentinel_args)


if __name__ == "__main__":
    main()
