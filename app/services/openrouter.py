import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

TIMEOUT = httpx.Timeout(60.0, connect=10.0)


class OpenRouterError(Exception):
    pass


class OpenRouterClient:
    """Thin async client for OpenRouter /v1/chat/completions."""

    def __init__(self) -> None:
        self.base_url = settings.OPENROUTER_BASE_URL.rstrip("/")
        self.api_key = settings.OPENROUTER_API_KEY
        self._headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://llmgame.local",
            "X-Title": "LLM Game",
        }

    async def chat(
        self,
        model: str,
        messages: list[dict],
        max_tokens: int = 300,
        temperature: float = 0.9,
    ) -> str:
        """Send a chat completion request and return the assistant text."""
        if not self.api_key:
            raise OpenRouterError("OPENROUTER_API_KEY is not set in .env")

        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "reasoning": {"enabled": False},
        }
        logger.debug("OpenRouter request model=%s messages_count=%d", model, len(messages))

        response = await self._send(payload, model)
        if response.status_code != 200 and self._should_retry_with_reasoning_enabled(response):
            logger.warning(
                "Reasoning disable is not supported for %s, retrying with reasoning enabled.",
                model,
            )
            payload.pop("reasoning", None)
            response = await self._send(payload, model)

        if response.status_code != 200:
            logger.error(
                "OpenRouter returned %d: %s", response.status_code, response.text[:500]
            )
            raise OpenRouterError(
                f"OpenRouter error {response.status_code}: {response.text[:300]}"
            )

        data = response.json()
        try:
            message = data["choices"][0]["message"]
            content = message.get("content")
        except (KeyError, IndexError, TypeError) as exc:
            logger.error("Unexpected OpenRouter response structure: %s", data)
            raise OpenRouterError(f"Unexpected response structure: {exc}") from exc

        text = self._extract_text(content)
        if not text:
            logger.error("Empty OpenRouter content for model %s: %s", model, data)
            raise OpenRouterError(f"Empty response content for model {model}")

        logger.debug("OpenRouter response length=%d", len(text))
        return text.strip()

    @staticmethod
    def _extract_text(content: object) -> str:
        if isinstance(content, str):
            return content

        # Some providers return content as a list of parts, e.g. [{"type":"text","text":"..."}].
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    text_part = item.get("text")
                    if isinstance(text_part, str):
                        parts.append(text_part)
            return "\n".join(parts).strip()

        return ""

    async def _send(self, payload: dict, model: str) -> httpx.Response:
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                return await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._headers,
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            logger.error("OpenRouter timeout for model %s: %s", model, exc)
            raise OpenRouterError(f"Request timed out for model {model}") from exc
        except httpx.RequestError as exc:
            logger.error("OpenRouter request error: %s", exc)
            raise OpenRouterError(f"Network error: {exc}") from exc

    @staticmethod
    def _should_retry_with_reasoning_enabled(response: httpx.Response) -> bool:
        if response.status_code != 400:
            return False
        body = response.text.lower()
        return ("reasoning" in body) and (
            "unsupported" in body
            or "not allowed" in body
            or "invalid" in body
            or "unknown" in body
        )


# module-level singleton
openrouter_client = OpenRouterClient()
