"""Sentinel with Level 2 reasoning via OpenRouter."""

from fastmcp import FastMCP
from sentinel import SentinelMiddleware

mcp = FastMCP("WeatherServer")

mcp.add_middleware(SentinelMiddleware(
    # Level 1 — always on, free
    sensitivity=0.7,
    baseline_threshold=50,

    # Level 2 — reasoning on anomalies via OpenRouter
    reasoning_provider="https://openrouter.ai/api/v1",
    reasoning_key="your-openrouter-key",
    reasoning_model="anthropic/claude-sonnet-4-20250514",
    max_reasoning_calls_per_hour=10,
))


@mcp.tool()
def get_weather(city: str) -> dict:
    return {"city": city, "temp_f": 72, "condition": "sunny"}


if __name__ == "__main__":
    mcp.run()
