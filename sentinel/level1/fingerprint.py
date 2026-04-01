"""Request/response fingerprinting for Level 1 anomaly detection."""

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RequestFingerprint:
    """Immutable fingerprint of a single tool call."""

    tool_name: str
    param_keys: frozenset[str]
    param_types: dict[str, str]  # key -> type name
    shape_hash: str
    timestamp: float
    is_error: bool = False
    error_message: str | None = None


def fingerprint_tool_call(
    tool_name: str,
    arguments: dict[str, Any] | None,
    *,
    is_error: bool = False,
    error_message: str | None = None,
) -> RequestFingerprint:
    """Create a fingerprint from a tool call's name and arguments.

    The shape_hash captures the structural signature (which keys, what types)
    so we can detect novel parameter shapes without storing full payloads.
    """
    args = arguments or {}
    param_keys = frozenset(args.keys())
    param_types = {k: type(v).__name__ for k, v in sorted(args.items())}

    # Deterministic hash of the parameter shape
    shape_data = json.dumps(
        {"keys": sorted(param_keys), "types": param_types}, sort_keys=True
    )
    shape_hash = hashlib.sha256(shape_data.encode()).hexdigest()[:16]

    return RequestFingerprint(
        tool_name=tool_name,
        param_keys=param_keys,
        param_types=param_types,
        shape_hash=shape_hash,
        timestamp=time.time(),
        is_error=is_error,
        error_message=error_message,
    )
