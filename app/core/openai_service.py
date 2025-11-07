import os
import json
import logging
from typing import AsyncGenerator, Tuple
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()
logger = logging.getLogger("openai_service")

OPENAI_MODEL = os.getenv("OPENAI_MODEL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is required")

_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

async def stream_chat_completion(system_prompt: str, user_prompt: str) -> AsyncGenerator[str, None]:
    """
    Yields content chunks (strings) from Chat Completions stream.
    """
    logger.info("Calling OpenAI Chat Completions (stream=True)…")
    stream = await _client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        stream=True,
        temperature=0.3,
    )
    async for event in stream:
        delta = event.choices[0].delta
        if delta and delta.content:
            yield delta.content

async def get_json_from_stream(system_prompt: str, user_prompt: str) -> str:
    """
    Streams and concatenates into a single string, then minimally validates JSON.
    Returns raw JSON string (stored in generated_content).
    """
    try:
        buf = ""
        async for chunk in stream_chat_completion(system_prompt, user_prompt):
            buf += chunk
        # best effort trim to JSON array/object
        trimmed = buf.strip()
        logger.info("Validating JSON from OpenAI output…")
        try:
            _ = json.loads(trimmed)  
        except Exception as e:
            logger.warning(f"Raw output not strict JSON, attempting to fix: {e}")
            # fallback: try to find first [ ... ] block
            start = trimmed.find("[")
            end = trimmed.rfind("]")
            if start != -1 and end != -1 and end > start:
                trimmed = trimmed[start : end + 1]
                _ = json.loads(trimmed)
            else:
                raise
        return trimmed
    except Exception as e:
        logger.exception("Failed to collect/validate streamed JSON")
        raise
