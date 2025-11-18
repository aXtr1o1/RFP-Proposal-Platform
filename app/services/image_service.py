import hashlib
import logging
import time
import asyncio
from pathlib import Path
from io import BytesIO
from typing import Optional, Dict
from datetime import datetime, timedelta

import requests
from openai import OpenAI, APIError, RateLimitError, APIConnectionError

from config import settings

logger = logging.getLogger("image_service")

# FIXED: Cache configuration
MAX_CACHE_SIZE_MB = 500  # Max 500MB cache
CACHE_TTL_DAYS = 7  # Cache files older than 7 days are deleted
MAX_RETRIES = 3


class ImageService:
    """
    Generate and cache professional images using DALL-E
    """
    
    def __init__(self):
        """Initialize image service with cache management"""
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is not configured")
        
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.cache_dir = settings.CACHE_DIR / "images"
        self.cache_dir.mkdir(exist_ok=True, parents=True)
        
        # Cache statistics
        self._cache_hits = 0
        self._cache_misses = 0
        self._generation_count = 0
        
        logger.info(f" ImageService initialized")
        logger.info(f"   Cache directory: {self.cache_dir}")
        logger.info(f"   DALL-E model: {settings.DALL_E_MODEL}")
        
        # FIXED: Initial cache cleanup on startup
        self._cleanup_old_cache()
    
    def generate_image_for_slide(
        self, 
        slide_title: str, 
        slide_content: str
    ) -> Optional[BytesIO]:
        """
        Generate professional business image for slide content
        
        Args:
            slide_title: Title of the slide
            slide_content: Content/context for image
            
        Returns:
            Optional[BytesIO]: Image data or None if generation fails
        """
        if not slide_title:
            logger.warning("  Empty slide title provided")
            return None
        
        try:
            # Create cache key
            cache_key = self._get_cache_key(slide_title, slide_content)
            cache_path = self.cache_dir / f"{cache_key}.png"
            
            # Check cache
            if cache_path.exists():
                # Check if cache is still valid (not expired)
                if self._is_cache_valid(cache_path):
                    logger.info(f" Using cached image for '{slide_title}'")
                    self._cache_hits += 1
                    
                    with open(cache_path, 'rb') as f:
                        return BytesIO(f.read())
                else:
                    logger.info(f" Cache expired for '{slide_title}', regenerating")
                    cache_path.unlink()  # Delete expired cache
            
            self._cache_misses += 1
            
            # Generate prompt
            prompt = self._create_image_prompt(slide_title, slide_content)
            
            logger.info(f" Generating image for '{slide_title}'...")
            logger.debug(f"   Prompt: {prompt[:100]}...")
            
            # Call DALL-E with retry logic
            image_data = self._generate_with_retry(prompt)
            
            if not image_data:
                return None
            
            # FIXED: Check cache size before saving
            self._ensure_cache_size_limit()
            
            # Cache it
            with open(cache_path, 'wb') as f:
                f.write(image_data)
            
            self._generation_count += 1
            logger.info(f" Image generated and cached ({len(image_data)} bytes)")
            
            return BytesIO(image_data)
            
        except Exception as e:
            logger.error(f" Image generation failed for '{slide_title}': {e}")
            return None
    
    def _generate_with_retry(self, prompt: str) -> Optional[bytes]:
        """
        Generate image with retry logic
        
        Args:
            prompt: DALL-E prompt
            
        Returns:
            Optional[bytes]: Image data or None
        """
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.debug(f" DALL-E attempt {attempt}/{MAX_RETRIES}")
                
                # Call DALL-E
                response = self.client.images.generate(
                    model=settings.DALL_E_MODEL,
                    prompt=prompt,
                    size=settings.DALL_E_SIZE,
                    quality=settings.DALL_E_QUALITY,
                    n=1
                )
                
                # Download image
                image_url = response.data[0].url
                
                # Download with timeout
                image_response = requests.get(image_url, timeout=30)
                image_response.raise_for_status()
                
                return image_response.content
                
            except RateLimitError as e:
                logger.warning(f"  Rate limit hit on attempt {attempt}")
                if attempt < MAX_RETRIES:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.info(f"   Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                else:
                    logger.error(" Max retries reached for rate limit")
                    return None
            
            except APIConnectionError as e:
                logger.warning(f"  Connection error on attempt {attempt}: {e}")
                if attempt < MAX_RETRIES:
                    wait_time = 2 ** attempt
                    logger.info(f"   Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                else:
                    logger.error(" Max retries reached for connection error")
                    return None
            
            except APIError as e:
                logger.error(f" DALL-E API error on attempt {attempt}: {e}")
                if attempt < MAX_RETRIES and hasattr(e, 'status_code') and e.status_code >= 500:
                    wait_time = 2 ** attempt
                    logger.info(f"   Server error, waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                else:
                    return None
            
            except requests.RequestException as e:
                logger.error(f" Image download error: {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(2)
                else:
                    return None
            
            except Exception as e:
                logger.error(f" Unexpected error: {e}")
                return None
        
        return None
    
    def _create_image_prompt(self, title: str, content: str) -> str:
        """
        Create professional image prompt based on content
        
        Args:
            title: Slide title
            content: Slide content
            
        Returns:
            str: DALL-E prompt
        """
        title_lower = title.lower()
        
        # Content-aware prompt selection
        if 'team' in title_lower or 'role' in title_lower:
            return "Professional business team meeting in modern office, diverse professionals collaborating, clean corporate aesthetic, photorealistic, business photography style"
        
        elif 'executive' in title_lower or 'summary' in title_lower:
            return "Professional business executive presenting strategy in boardroom, confident diverse professionals, modern corporate setting, photorealistic"
        
        elif 'deliver' in title_lower or 'output' in title_lower:
            return "Professional project deliverables visualization, document stacks and reports on modern desk, clean organized workspace, business photography"
        
        elif 'timeline' in title_lower or 'schedule' in title_lower:
            return "Professional project planning session, timeline chart on digital screen, modern office environment, business team, photorealistic"
        
        elif 'objective' in title_lower or 'goal' in title_lower:
            return "Professional business strategy session, target goals visualization, modern corporate boardroom, photorealistic business photography"
        
        elif 'company' in title_lower or 'about' in title_lower:
            return "Professional corporate office building exterior, modern architecture, business district, clean professional aesthetic, photorealistic"
        
        elif 'methodology' in title_lower or 'approach' in title_lower:
            return "Professional consultants presenting methodology, whiteboard session, modern office, business team collaborating, photorealistic"
        
        elif 'quality' in title_lower or 'risk' in title_lower:
            return "Professional quality assurance review, business professionals analyzing reports, modern office setting, photorealistic"
        
        else:
            # Generic professional image
            return "Professional business consultation meeting, diverse team in modern office, corporate strategy session, clean aesthetic, photorealistic business photography"
    
    def _get_cache_key(self, title: str, content: str) -> str:
        """
        Generate cache key from content
        
        Args:
            title: Slide title
            content: Slide content
            
        Returns:
            str: MD5 hash as cache key
        """
        combined = f"{title}_{content[:200]}"  # FIXED: 200 chars instead of 100
        return hashlib.md5(combined.encode()).hexdigest()
    
    def _is_cache_valid(self, cache_path: Path) -> bool:
        """
        Check if cached file is still valid (not expired)
        
        Args:
            cache_path: Path to cache file
            
        Returns:
            bool: True if cache is valid
        """
        try:
            file_age = datetime.now() - datetime.fromtimestamp(cache_path.stat().st_mtime)
            return file_age < timedelta(days=CACHE_TTL_DAYS)
        except Exception as e:
            logger.warning(f"  Error checking cache validity: {e}")
            return False
    
    def _cleanup_old_cache(self) -> None:
        """
        Cleanup old cache files based on TTL
        """
        try:
            deleted_count = 0
            total_size_freed = 0
            
            for cache_file in self.cache_dir.glob("*.png"):
                if not self._is_cache_valid(cache_file):
                    file_size = cache_file.stat().st_size
                    cache_file.unlink()
                    deleted_count += 1
                    total_size_freed += file_size
            
            if deleted_count > 0:
                logger.info(f" Cleaned up {deleted_count} expired cache files ({total_size_freed / 1024 / 1024:.2f} MB freed)")
            else:
                logger.info(" No expired cache files to clean")
                
        except Exception as e:
            logger.error(f" Cache cleanup failed: {e}")
    
    def _ensure_cache_size_limit(self) -> None:
        """
        Ensure cache directory doesn't exceed size limit
        
        FIXED: Cache size limit enforcement
        """
        try:
            # Calculate total cache size
            total_size = sum(f.stat().st_size for f in self.cache_dir.glob("*.png"))
            total_size_mb = total_size / 1024 / 1024
            
            if total_size_mb > MAX_CACHE_SIZE_MB:
                logger.warning(f"  Cache size ({total_size_mb:.2f} MB) exceeds limit ({MAX_CACHE_SIZE_MB} MB)")
                
                # Get all cache files sorted by age (oldest first)
                cache_files = sorted(
                    self.cache_dir.glob("*.png"),
                    key=lambda f: f.stat().st_mtime
                )
                
                # Delete oldest files until under limit
                deleted_count = 0
                for cache_file in cache_files:
                    if total_size_mb <= MAX_CACHE_SIZE_MB * 0.8:  # Target 80% of limit
                        break
                    
                    file_size = cache_file.stat().st_size
                    cache_file.unlink()
                    total_size_mb -= file_size / 1024 / 1024
                    deleted_count += 1
                
                logger.info(f" Deleted {deleted_count} old cache files to enforce size limit")
                
        except Exception as e:
            logger.error(f" Cache size limit enforcement failed: {e}")
    
    def clear_cache(self) -> None:
        """Clear entire image cache"""
        try:
            deleted_count = 0
            total_size_freed = 0
            
            for cache_file in self.cache_dir.glob("*.png"):
                file_size = cache_file.stat().st_size
                cache_file.unlink()
                deleted_count += 1
                total_size_freed += file_size
            
            logger.info(f" Cleared image cache: {deleted_count} files ({total_size_freed / 1024 / 1024:.2f} MB freed)")
            
            # Reset statistics
            self._cache_hits = 0
            self._cache_misses = 0
            
        except Exception as e:
            logger.error(f" Cache clear failed: {e}")
    
    def get_cache_stats(self) -> Dict[str, any]:
        """
        Get cache statistics
        
        Returns:
            Dict: Cache statistics
        """
        try:
            cache_files = list(self.cache_dir.glob("*.png"))
            total_size = sum(f.stat().st_size for f in cache_files)
            
            return {
                "cache_hits": self._cache_hits,
                "cache_misses": self._cache_misses,
                "hit_rate": self._cache_hits / (self._cache_hits + self._cache_misses) if (self._cache_hits + self._cache_misses) > 0 else 0,
                "total_files": len(cache_files),
                "total_size_mb": total_size / 1024 / 1024,
                "max_size_mb": MAX_CACHE_SIZE_MB,
                "generations_count": self._generation_count,
                "ttl_days": CACHE_TTL_DAYS
            }
        except Exception as e:
            logger.error(f" Failed to get cache stats: {e}")
            return {}
