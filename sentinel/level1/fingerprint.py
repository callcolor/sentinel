"""Request/response fingerprinting for Level 1 anomaly detection."""

import hashlib
import json
import re
import time
from dataclasses import dataclass
from typing import Any

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I
)


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


def _parameterize_path(path: str) -> str:
    """Replace dynamic path segments with :id placeholders.

    Numeric segments and UUIDs become :id so that /users/123 and /users/456
    produce the same fingerprint identity.
    """
    segments = path.strip("/").split("/")
    result = []
    for seg in segments:
        if not seg:
            continue
        if seg.isdigit() or _UUID_RE.match(seg):
            result.append(":id")
        else:
            result.append(seg)
    return "/" + "/".join(result) if result else "/"


def fingerprint_http_request(
    method: str,
    path: str,
    query_params: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
    status_code: int | None = None,
) -> RequestFingerprint:
    """Create a fingerprint from an HTTP request for REST mode.

    Identity is METHOD + parameterized path (e.g. "POST /api/users/:id").
    Shape is derived from query params + request body structure.
    """
    tool_name = f"{method.upper()} {_parameterize_path(path)}"

    # Combine query params and body keys for shape
    combined: dict[str, Any] = {}
    if query_params:
        combined.update(query_params)
    if body:
        combined.update(body)

    is_error = status_code is not None and status_code >= 400
    error_message = f"HTTP {status_code}" if is_error else None

    return fingerprint_tool_call(
        tool_name=tool_name,
        arguments=combined if combined else None,
        is_error=is_error,
        error_message=error_message,
    )
