# Sentinel: Intelligent Middleware for MCP Servers

## Project Spec v0.1

---

## Vision

MCP servers are currently dumb pipes — they receive requests and return responses with no
awareness of patterns, anomalies, or opportunities for improvement. Sentinel is a drop-in
middleware SDK for MCP servers that adds an intelligence layer: cheap passive monitoring on
every request, with the ability to escalate to real reasoning when something genuinely novel
happens, and to evolve the server's baseline behavior over time.

The long-term vision: an ecosystem where MCP servers learn from their own traffic, and
optionally contribute to shared intelligence — enabling open standards to emerge from observed
patterns rather than committees.

---

## The Problem

A solo developer builds an MCP server. Agents start calling it. The server has no idea:

- Whether agents are using it as intended or misunderstanding its schema
- Whether usage patterns suggest missing capabilities
- Whether errors indicate bugs, version mismatches, or novel use cases
- Whether two different agents are asking for the same thing in incompatible ways
- Whether a request is genuinely novel and deserves human attention

Existing tools are passive analytics dashboards (mcp-analytics-middleware, Moesif) or
security-focused anomaly detection (Datadog SIEM). Nobody is building middleware that
**comprehends** what it observes and **evolves** from it.

---

## Architecture: Three Levels of Awareness

### Level 0 — Normal Operation
Request comes in, matches known patterns, response goes out. No intelligence involved.
No latency added. This is 99%+ of all traffic.

### Level 1 — Anomaly Detection (Cheap, Fast, Every Request)
A thin layer that runs on every request/response pair. **Non-blocking** — the MCP response
has already been sent before this layer processes.

- Logs request/response fingerprints (tool called, parameter shapes, response structure)
- Maintains counters: call frequency per tool, error rates, new caller detection
- Compares against established baseline
- Optionally generates embeddings for semantic comparison (batched, async)

**Level 1 answers: "Was that normal?"**

Cost: Near zero for statistical checks. Embedding costs amortized via batching.

### Level 2 — Reasoning (Expensive, Rare, On-Demand)
Triggered only when Level 1 flags something above the sensitivity threshold. Sends the
flagged request, surrounding context, and server metadata to a reasoning model.

**Level 2 answers: "What does this mean and what should the developer know?"**

Cost: Per-invocation LLM API call. Expected: a few times per day for a typical server.

### Level 3 — Evolution (Nearly Free, Periodic)
Level 2's conclusions are fed back into Level 1's baseline. New patterns become "normal."
New capabilities get suggested. The server gets smarter over time.

**Level 3 answers: "How should our understanding of 'normal' change?"**

Cost: A data write operation. Negligible.

---

## Developer Interface

### Minimal Setup

```python
from fastmcp import FastMCP
from sentinel import SentinelMiddleware

mcp = FastMCP("MyServer")
mcp.add_middleware(SentinelMiddleware(
    reasoning_key="your-openrouter-key",
    sensitivity=0.7
))
```

### Full Configuration

```python
mcp.add_middleware(SentinelMiddleware(
    # Provider endpoints (OpenAI-compatible format)
    embedding_provider="https://api.alibaba.com/v1",    # or local
    reasoning_provider="https://openrouter.ai/api/v1",  # or local

    # API keys (not needed for local providers)
    embedding_key="your-key",
    reasoning_key="your-key",

    # Model selection
    embedding_model="alibaba/text-embedding-v3",
    reasoning_model="anthropic/claude-sonnet-4-20250514",

    # Optional triage model for smarter Level 1
    # None = pure statistical (cheapest)
    triage_model=None,

    # Sensitivity: 0.0 = wake on everything, 1.0 = almost never wake
    sensitivity=0.7,

    # Output
    output="log",         # "log", "webhook", "dashboard", or list
    webhook_url=None,
    dashboard_port=None,

    # Storage
    storage_path="./sentinel_data",

    # Baseline: requests before baseline is considered established
    baseline_threshold=100,

    # Cost safety valve
    max_reasoning_calls_per_hour=10,
))
```

### Fully Local (No API Keys, No Cloud)

```python
mcp.add_middleware(SentinelMiddleware(
    embedding_provider="http://localhost:11434",  # Ollama
    reasoning_provider="http://localhost:11434",
    embedding_model="nomic-embed-text",
    reasoning_model="llama3",
    sensitivity=0.7
))
```

### Hybrid (Local Embeddings + Cloud Reasoning)

```python
mcp.add_middleware(SentinelMiddleware(
    embedding_provider="http://localhost:11434",         # cheap, local, fast
    reasoning_provider="https://openrouter.ai/api/v1",  # smart, cloud, rare
    embedding_model="nomic-embed-text",
    reasoning_model="anthropic/claude-sonnet-4-20250514",
    reasoning_key="your-openrouter-key",
    sensitivity=0.7
))
```

---

## Provider Abstraction

All providers speak OpenAI-compatible API format. This covers:

- **Cloud**: OpenRouter, OpenAI, Anthropic (via OpenRouter), Together, etc.
- **Local**: Ollama, LM Studio, vLLM, any OpenAI-compatible local server

No provider-specific code. One interface, all endpoints.

---

## Cost Control

1. **Sensitivity threshold** (0.0–1.0): Higher = less thinking = cheaper
2. **Model selection**: Cheap models for hobby, powerful for production
3. **Local vs cloud**: Fully local = free after hardware
4. **Triage model**: None (statistical only) vs. a small model (smarter Level 1)
5. **Embedding batch frequency**: Amortize cost across many requests
6. **Level 2 rate limit**: `max_reasoning_calls_per_hour` as safety valve

Expected costs (typical hobby server, moderate traffic):
- Level 1 statistical only: ~$0/month
- Level 1 with cloud embeddings (batched): ~$1–5/month
- Level 2 cloud reasoning (few times/day): ~$5–15/month
- Fully local: $0/month (hardware only)

---

## Technology Choices

- **Language**: Python (FastMCP is Python-native)
- **Framework**: FastMCP 2.9+ middleware API
- **Storage**: SQLite for baseline data; numpy/faiss for local vector similarity
- **Async**: Fully async — Level 1 never blocks request/response cycle
- **Distribution**: PyPI package — `pip install sentinel-mcp`

---

## MVP Scope (v0.1) — Build First

- [ ] FastMCP middleware that intercepts all requests/responses
- [ ] Statistical baseline (counters, error rates, parameter shapes)
- [ ] Configurable sensitivity threshold
- [ ] Level 2 reasoning via OpenAI-compatible endpoint
- [ ] Structured JSON log output
- [ ] BYOK for all providers
- [ ] Local model support via Ollama-compatible endpoints
- [ ] Cost safety valve (max reasoning calls per period)

## Defer to v0.2+

- Embedding-based semantic analysis
- Local web dashboard
- Webhook output
- Level 3 automatic baseline evolution (v0.1 logs insights, doesn't auto-evolve)
- Cross-server intelligence / cloud sync
- Hosted service

---

## Competitive Landscape

| Project | What it does | Gap |
|---|---|---|
| mcp-analytics-middleware | Passive metrics + dashboard | No intelligence, no reasoning |
| Moesif | API observability for MCP | Enterprise SaaS, not drop-in |
| FastMCP middleware | Hooks for interception | Framework only, no intelligence |
| CodeMesh | Agents improve tool use | Agent-side, not server-side |
| Datadog/SIEM | Security anomaly detection | Security-focused, not capability-focused |

**The gap**: Nobody is building middleware that makes the MCP server itself intelligent —
observing, reasoning about, and evolving from its own traffic.

---

## Suggested Project Structure

```
sentinel-mcp/
├── sentinel/
│   ├── __init__.py
│   ├── middleware.py        # SentinelMiddleware — FastMCP integration point
│   ├── level1/
│   │   ├── monitor.py      # Non-blocking stat collection
│   │   ├── baseline.py     # SQLite baseline management
│   │   └── fingerprint.py  # Request/response fingerprinting
│   ├── level2/
│   │   ├── reasoner.py     # OpenAI-compatible reasoning client
│   │   └── prompts.py      # Reasoning prompt templates
│   ├── providers/
│   │   └── openai_compat.py  # Universal provider interface
│   ├── storage/
│   │   └── sqlite.py
│   └── config.py
├── tests/
├── examples/
│   ├── minimal.py
│   ├── local_only.py
│   └── hybrid.py
├── pyproject.toml
└── README.md
```

---

## Starting Prompt for Claude Code

> Read this spec and scaffold the sentinel-mcp project. Start with:
> 1. `pyproject.toml` with dependencies (fastmcp>=2.9, aiohttp, aiosqlite)
> 2. `sentinel/middleware.py` — the `SentinelMiddleware` class with FastMCP middleware hooks
> 3. `sentinel/level1/monitor.py` — async, non-blocking stat collection
> 4. `sentinel/level1/baseline.py` — SQLite-backed baseline with `is_anomalous()` method
> 5. A minimal working example in `examples/minimal.py`
>
> Level 2 reasoning and embedding support come after the Level 1 scaffold is solid.
