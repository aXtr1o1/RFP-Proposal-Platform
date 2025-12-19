from __future__ import annotations

import logging
from typing import AsyncGenerator, Optional
from datetime import datetime

from openai import AsyncOpenAI, APIError, RateLimitError, APIConnectionError
from apps.PPT.config import settings
from apps.PPT.models.presentation import PresentationData

logger = logging.getLogger("openai_service")


class OpenAIService:
    """
    OpenAI service for generating complete presentation structure
    """

    def __init__(self):
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is not configured")
        
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self._call_count = 0
        self._total_tokens = 0
        logger.info("OpenAI Service initialized (Single Call Mode)")

    async def generate_presentation_structure(
        self,
        markdown_content: str,
        template_id: str,
        language: str,
        user_preference: str = "",
        stream_output: bool = False,
        max_retries: int = 3
    ) -> PresentationData:
        """
        Generate complete presentation with SINGLE API call
        
        Args:
            markdown_content: Source markdown
            template_id: Template to use (e.g., "standard")
            language: "English" or "Arabic"
            user_preference: User preferences
            stream_output: Enable streaming for terminal display (optional)
            max_retries: Number of retry attempts
            
        Returns:
            PresentationData: Complete presentation structure
        """
        # Validate inputs
        if not markdown_content or len(markdown_content) < 10:
            raise ValueError("Markdown content is empty or too short")
        
        if language not in ["English", "Arabic"]:
            raise ValueError(f"Invalid language: {language}")
        
        logger.info(f" Generating presentation (Language: {language}, Template: {template_id})")
        logger.info(f"   Mode: {'Streaming' if stream_output else 'Structured Output'}")
        logger.info(f"    Single API call mode")
        
        # Get prompts
        from apps.PPT.core.ppt_prompts import get_system_prompt, get_user_prompt
        
        system_prompt = get_system_prompt(language, template_id)
        user_prompt = get_user_prompt(markdown_content, language, user_preference)
        
        # Validate prompt size (rough estimate)
        total_prompt_chars = len(system_prompt) + len(user_prompt)
        estimated_tokens = total_prompt_chars // 4  # Rough estimate
        
        if estimated_tokens > 100000:
            logger.warning(f"  Large prompt: ~{estimated_tokens} tokens")
        
        # SINGLE API CALL with retry logic
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"📡 API Call attempt {attempt}/{max_retries}...")
                
                # FIXED: Single structured output call
                start_time = datetime.now()
                
                parse_response = await self.client.beta.chat.completions.parse(
                    model=settings.OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format=PresentationData,
                    # temperature=0.4,
                    # max_tokens=8000,
                )
                
                elapsed = (datetime.now() - start_time).total_seconds()
                
                # Extract result
                result: PresentationData = parse_response.choices[0].message.parsed
                
                if not result:
                    raise RuntimeError("Empty response from OpenAI")
                
                # Track usage
                self._call_count += 1
                usage = parse_response.usage
                if usage:
                    self._total_tokens += usage.total_tokens
                    logger.info(f"Token usage: {usage.total_tokens} tokens")
                    logger.info(f"   Prompt: {usage.prompt_tokens}, Completion: {usage.completion_tokens}")
                
                logger.info(f" Generated: {result.title} ({len(result.slides)} slides)")
                logger.info(f"  API call time: {elapsed:.2f}s")
                logger.info(f" Total API calls: {self._call_count}")
                logger.info(f" Total tokens used: {self._total_tokens}")
                
                return result
            
            except RateLimitError as e:
                logger.warning(f" Rate limit hit on attempt {attempt}/{max_retries}")
                if attempt < max_retries:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.info(f"   Waiting {wait_time}s before retry...")
                    import asyncio
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(" Max retries reached for rate limit")
                    raise
            
            except APIConnectionError as e:
                logger.warning(f" Connection error on attempt {attempt}/{max_retries}: {e}")
                if attempt < max_retries:
                    wait_time = 2 ** attempt
                    logger.info(f"   Waiting {wait_time}s before retry...")
                    import asyncio
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(" Max retries reached for connection error")
                    raise
            
            except APIError as e:
                logger.error(f" OpenAI API error on attempt {attempt}: {e}")
                if attempt < max_retries and e.status_code >= 500:
                    # Retry only on server errors
                    wait_time = 2 ** attempt
                    logger.info(f"   Server error, waiting {wait_time}s before retry...")
                    import asyncio
                    await asyncio.sleep(wait_time)
                else:
                    raise
            
            except Exception as e:
                logger.exception(f" Unexpected error on attempt {attempt}: {e}")
                raise
        
        # Should not reach here
        raise RuntimeError("Failed to generate presentation after all retries")

    async def stream_presentation_generation(
        self,
        system_prompt: str,
        user_prompt: str
    ) -> AsyncGenerator[str, None]:
        """
        Stream presentation generation (for terminal display only)
        
        Args:
            system_prompt: System instructions
            user_prompt: User content and instructions
            
        Yields:
            str: Text chunks as they arrive
        """
        logger.info(" Starting OpenAI streaming (display mode)...")
        
        print("\n" + "="*100)
        print(" OpenAI Live Streaming Response")
        print("="*100 + "\n")

        stream = await self.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            stream=True,
            temperature=0.3,
            max_tokens=8000,
        )

        full_response = ""
        
        async for event in stream:
            if not event.choices:
                continue
            
            delta = event.choices[0].delta
            if not delta or not hasattr(delta, 'content') or not delta.content:
                continue
            
            chunk = delta.content
            print(chunk, end="", flush=True)
            full_response += chunk
            yield chunk

        print("\n\n" + "="*100)
        print(f" Streaming Complete - {len(full_response)} characters")
        print(full_response)
        print("="*100 + "\n")
    
    def get_stats(self) -> dict:
        """Get usage statistics"""
        return {
            "total_calls": self._call_count,
            "total_tokens": self._total_tokens,
            "estimated_cost_usd": self._total_tokens * 0.00001  # Rough estimate
        }


# Thread-safe singleton implementation
_openai_service: Optional[OpenAIService] = None
_service_lock = None


def get_openai_service() -> OpenAIService:
    """
    Get singleton OpenAI service instance (thread-safe)
    """
    global _openai_service, _service_lock
    
    if _service_lock is None:
        import asyncio
        _service_lock = asyncio.Lock()
    
    if _openai_service is None:
        _openai_service = OpenAIService()
    
    return _openai_service
