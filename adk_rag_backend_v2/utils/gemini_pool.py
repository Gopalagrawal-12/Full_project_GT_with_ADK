"""
utils/gemini_pool.py
-----------------------
Dynamically finds the ADK class, intercepts the generator method, and injects
a new Google Client with a rotated API key whenever a 429 or 503 is hit.
"""
import os
import asyncio
import logging
from google.genai import Client
import google.adk.models.google_llm as google_llm_module
from utils.api_pool import AsyncAPIKeyPool

logger = logging.getLogger("adk_rag.utils.gemini_pool")

# 1. Initialize the pool
gemini_pool = AsyncAPIKeyPool([
    os.getenv("GEMINI_API_KEY_1"),
    os.getenv("GEMINI_API_KEY_2"),
    os.getenv("GEMINI_API_KEY_3"),
])

def apply_adk_patch():
    """Dynamically finds the correct ADK class and overwrites the generator."""

    # 2. Dynamically search the module for the class that handles async generation
    TargetClass = None
    for attr_name in dir(google_llm_module):
        attr = getattr(google_llm_module, attr_name)
        if isinstance(attr, type) and hasattr(attr, "generate_content_async") and not attr_name.startswith("_"):
            TargetClass = attr
            break

    if not TargetClass:
        logger.error("Could not find the LLM class in google.adk.models.google_llm to patch!")
        return

    # 3. Save the original ADK generation method we found
    original_generate_content_async = TargetClass.generate_content_async

    # 4. Create the generator-safe wrapper
    async def pooled_generate_content_async(self, *args, **kwargs):
        max_attempts = len(gemini_pool.api_keys) * 3

        for attempt in range(max_attempts):
            active_key = await gemini_pool.get_key()

            # INJECT the fresh API key into ADK's internal client right before it fires
            self.api_client = Client(api_key=active_key)

            try:
                # Execute the original method
                agen = original_generate_content_async(self, *args, **kwargs)

                # Consume the generator safely
                async for chunk in agen:
                    yield chunk

                # If we finish yielding without errors, the request succeeded!
                return

            except Exception as e:
                error_name = type(e).__name__
                error_msg = str(e)

                # Catch ADK's specific wrapper errors or raw 429/503s
                if "ResourceExhausted" in error_name or "429" in error_msg or "503" in error_msg:
                    logger.warning(f"ADK Quota Hit! Rotating API Key... (Attempt {attempt+1}/{max_attempts})")
                    await gemini_pool.rotate(active_key)
                    await asyncio.sleep(1.5)  # Let the server breathe before retry
                    continue # Loop back and retry with the new key
                else:
                    # If it's a real error (like a bad prompt), let it crash
                    raise e

        raise RuntimeError("All Gemini API keys in the pool are exhausted.")

    # 5. Apply the patch to the found class
    TargetClass.generate_content_async = pooled_generate_content_async
    logger.info(f"Successfully locked ADK to the API Key Pool. (Loaded {len(gemini_pool.api_keys)} keys)")