"""Sentinel with fully local models via Ollama — no API keys, no cloud."""

from fastmcp import FastMCP
from sentinel import SentinelMiddleware

mcp = FastMCP("LocalServer")

mcp.add_middleware(SentinelMiddleware(
    sensitivity=0.7,

    # Level 2 reasoning via local Ollama
    reasoning_provider="http://localhost:11434/v1",
    reasoning_model="llama3",
    max_reasoning_calls_per_hour=50,  # local = free, can be generous
))


@mcp.tool()
def search_docs(query: str, limit: int = 10) -> dict:
    return {"query": query, "results": [], "total": 0}


if __name__ == "__main__":
    mcp.run()
