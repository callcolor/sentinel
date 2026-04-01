"""Universal OpenAI-compatible provider client.

Speaks the OpenAI API format, which covers:
- Cloud: OpenRouter, OpenAI, Together, Anthropic (via OpenRouter)
- Local: Ollama, LM Studio, vLLM, any OpenAI-compatible server

No provider-specific code. One interface, all endpoints.
"""

import logging
from typing import Any, Optional

import aiohttp

logger = logging.getLogger("sentinel")


class ProviderClient:
    """Async client for OpenAI-compatible chat completion endpoints."""

    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        model: str = "gpt-3.5-turbo",
        timeout: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            self._session = aiohttp.ClientSession(
                headers=headers, timeout=self.timeout
            )
        return self._session

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> str:
        """Send a chat completion request. Returns the assistant's message content."""
        session = await self._get_session()
        url = f"{self.base_url}/chat/completions"

        payload: dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        async with session.post(url, json=payload) as resp:
            if resp.status != 200:
                body = await resp.text()
                logger.error(
                    "provider error: status=%d body=%s", resp.status, body[:500]
                )
                raise ProviderError(
                    f"Provider returned {resp.status}: {body[:200]}"
                )

            data = await resp.json()
            return data["choices"][0]["message"]["content"]

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None


class ProviderError(Exception):
    """Raised when a provider request fails."""
