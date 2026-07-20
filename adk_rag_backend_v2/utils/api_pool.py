"""
utils/api_pool.py
"""
import asyncio
import logging
from typing import List, Callable, Any, Awaitable

logger = logging.getLogger("adk_rag.utils.api_pool")


class AsyncAPIKeyPool:
    """
    Manages a pool of API keys and transpa  rently cycles them when
    a 429 Rate Limit / Resource Exhausted error is encountered.
    """

    def __init__(self, api_keys: List[str]):
        # Filter out empty strings or None values
        self.api_keys = [k for k in api_keys if k and k.strip()]
        if not self.api_keys:
            raise ValueError("Must provide at least one valid API key.")

        self.current_index = 0
        self._lock = asyncio.Lock()

    async def get_key(self) -> str:
        """Get the currently active API key safely."""
        async with self._lock:
            return self.api_keys[self.current_index]

    async def rotate(self, failed_key: str):
        """Rotate to the next key, ensuring we don't double-skip if multiple requests fail at once."""
        async with self._lock:
            if self.api_keys[self.current_index] == failed_key:
                old_index = self.current_index
                self.current_index = (self.current_index + 1) % len(self.api_keys)
                logger.warning(
                    f"API Key at index {old_index} rate-limited. "
                    f"Switched to Key {self.current_index}."
                )

    async def execute(self, func: Callable[[str], Awaitable[Any]]) -> Any:
        """
        Executes an async function that takes an API key as its argument.
        Automatically catches 429s, rotates the key, and retries.
        """
        # Try each key at least twice before completely failing
        max_attempts = len(self.api_keys) * 2

        for attempt in range(max_attempts):
            current_key = await self.get_key()

            try:
                # Pass the current API key to your worker function
                return await func(current_key)

            except Exception as e:
                error_msg = str(e).lower()
                is_429 = False

                if getattr(e, "code", None) in (429, 503):
                    is_retryable = True
                    # Detect OpenAI / Groq SDK specific errors
                elif e.__class__.__name__ in ("RateLimitError", "APIConnectionError", "InternalServerError"):
                    is_retryable = True
                    # Generic string fallback for raw HTTP requests
                elif any(term in error_msg for term in
                         ["429", "503", "resource_exhausted", "quota", "unavailable", "overloaded"]):
                    is_retryable = True

                if is_retryable:
                    logger.warning(
                        f"Rate limit or Server Overload hit. Rotating/Retrying... (Attempt {attempt + 1}/{max_attempts})")
                    await self.rotate(current_key)
                    # 1-second backoff to allow servers to breathe
                    await asyncio.sleep(1.0)
                else:
                    # If it's a Bad Request (400) or generic crash, rotating keys won't fix it.
                    raise e

        raise RuntimeError("All API keys in the pool are currently rate-limited or exhausted.")