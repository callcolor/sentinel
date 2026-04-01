from dataclasses import dataclass
from typing import Optional


@dataclass
class SentinelConfig:
    """Configuration for the Sentinel middleware."""

    # Provider endpoints (OpenAI-compatible format)
    embedding_provider: Optional[str] = None
    reasoning_provider: Optional[str] = None

    # API keys
    embedding_key: Optional[str] = None
    reasoning_key: Optional[str] = None

    # Model selection
    embedding_model: Optional[str] = None
    reasoning_model: Optional[str] = None
    triage_model: Optional[str] = None

    # Sensitivity: 0.0 = flag everything, 1.0 = almost never flag
    sensitivity: float = 0.7

    # Output: "log", "webhook", "dashboard", or a list
    output: str = "log"
    webhook_url: Optional[str] = None
    dashboard_port: Optional[int] = None

    # Storage
    storage_path: str = "./sentinel_data"

    # Number of observations before baseline is considered established
    baseline_threshold: int = 100

    # Cost safety valve
    max_reasoning_calls_per_hour: int = 10
