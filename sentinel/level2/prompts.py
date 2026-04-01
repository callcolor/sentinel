"""Reasoning prompt templates for Level 2 analysis.

When Level 1 flags an anomaly above the sensitivity threshold, Level 2
sends the flagged request + surrounding context to a reasoning model.

Level 2 answers: "What does this mean and what should the developer know?"
"""

SYSTEM_PROMPT = """\
You are Sentinel, an intelligent monitoring system for MCP (Model Context Protocol) servers.

An anomaly has been detected in the server's traffic. Your job is to analyze the flagged \
event, determine what it means, and produce a concise insight for the server developer.

Focus on:
1. Is this a legitimate new use case, a misunderstanding of the API, or a potential problem?
2. What should the developer know or consider?
3. Should the server's baseline be updated to treat this as normal going forward?

Be concise and actionable. The developer is technical — skip obvious explanations.\
"""


def build_anomaly_prompt(
    tool_name: str,
    arguments: dict | None,
    anomaly_score: float,
    reasons: list[str],
    baseline_summary: dict,
) -> list[dict[str, str]]:
    """Build the message list for a Level 2 reasoning call."""
    context_parts = [
        f"**Flagged tool call:** `{tool_name}`",
        f"**Arguments:** `{arguments}`",
        f"**Anomaly score:** {anomaly_score:.2f}",
        f"**Reasons:** {', '.join(reasons)}",
        "",
        "**Baseline context:**",
    ]

    for key, value in baseline_summary.items():
        context_parts.append(f"- {key}: {value}")

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(context_parts)},
    ]
