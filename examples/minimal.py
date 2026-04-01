"""Minimal Sentinel example — drop-in anomaly detection for an MCP server."""

from fastmcp import FastMCP
from sentinel import SentinelMiddleware

mcp = FastMCP("WeatherServer")

# Add Sentinel — that's it. Level 1 monitoring starts automatically.
mcp.add_middleware(SentinelMiddleware(
    sensitivity=0.7,          # 0.0 = flag everything, 1.0 = almost never flag
    storage_path="./sentinel_data",
    baseline_threshold=50,    # observations before baseline is established
))


@mcp.tool()
def get_weather(city: str) -> dict:
    """Get current weather for a city."""
    # Simulated response
    return {
        "city": city,
        "temp_f": 72,
        "condition": "sunny",
    }


@mcp.tool()
def get_forecast(city: str, days: int = 5) -> dict:
    """Get weather forecast for a city."""
    return {
        "city": city,
        "days": days,
        "forecast": [{"day": i + 1, "temp_f": 70 + i} for i in range(days)],
    }


if __name__ == "__main__":
    mcp.run()
