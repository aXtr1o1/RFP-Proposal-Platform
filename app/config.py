import os
import logging
from pathlib import Path
from typing import Literal
from pydantic_settings import BaseSettings
from pydantic import ConfigDict, field_validator

logger = logging.getLogger("config")


class Settings(BaseSettings):
    """
    Application settings with DALL-E and Supabase support
    """
    
    # OpenAI API
    OPENAI_API_KEY: str
    OPENAI_MODEL: str 
    
    # DALL-E Configuration
    DALL_E_MODEL: Literal["dall-e-2", "dall-e-3"] = "dall-e-3"
    DALL_E_SIZE: Literal["1024x1024", "1792x1024", "1024x1792"] = "1024x1024"
    DALL_E_QUALITY: Literal["standard", "hd"] = "standard"
    DALL_E_STYLE: Literal["natural", "vivid"] = "natural"
    
    # Supabase Configuration
    SUPABASE_URL: str
    SUPABASE_KEY: str
    SUPABASE_BUCKET: str = "proposal-ppts"
    
    # Application Settings
    APP_NAME: str = "RFP Presentation Generator"
    DEBUG: bool = False
    DEFAULT_TEMPLATE: str = "standard"
    
    # FIXED: Path resolution that works from any directory
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    
    @property
    def OUTPUT_DIR(self) -> Path:
        """Output directory for generated PPTX files"""
        return self.BASE_DIR / "output"
    
    @property
    def TEMPLATES_DIR(self) -> Path:
        """Templates directory (app/templates)"""
        return self.BASE_DIR / "app" / "templates"
    
    @property
    def ASSETS_DIR(self) -> Path:
        """Assets directory (app/assets)"""
        return self.BASE_DIR / "app" / "assets"
    
    @property
    def CACHE_DIR(self) -> Path:
        """Cache directory"""
        return self.BASE_DIR / "cache"
    
    # Pydantic v2 configuration
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )
    
    @field_validator('OPENAI_API_KEY')
    @classmethod
    def validate_openai_key(cls, v: str) -> str:
        """Validate OpenAI API key"""
        if not v or len(v) < 20:
            raise ValueError("Invalid OPENAI_API_KEY (too short)")
        if not v.startswith('sk-'):
            raise ValueError("OPENAI_API_KEY should start with 'sk-'")
        return v
    
    @field_validator('SUPABASE_URL')
    @classmethod
    def validate_supabase_url(cls, v: str) -> str:
        """Validate Supabase URL"""
        if not v:
            raise ValueError("SUPABASE_URL is required")
        if not v.startswith(('http://', 'https://')):
            raise ValueError("SUPABASE_URL must start with http:// or https://")
        return v
    
    @field_validator('SUPABASE_KEY')
    @classmethod
    def validate_supabase_key(cls, v: str) -> str:
        """Validate Supabase key"""
        if not v or len(v) < 20:
            raise ValueError("Invalid SUPABASE_KEY (too short)")
        return v
    
    def mask_secret(self, secret: str) -> str:
        """Mask secret for logging (show first 8 and last 4 chars)"""
        if not secret or len(secret) < 16:
            return "***"
        return f"{secret[:8]}...{secret[-4:]}"


# Initialize settings
settings = Settings()

# FIXED: Create directories with validation
def _initialize_directories():
    """Initialize required directories"""
    directories = {
        "Output": settings.OUTPUT_DIR,
        "Templates": settings.TEMPLATES_DIR,
        "Assets": settings.ASSETS_DIR,
        "Cache": settings.CACHE_DIR,
        "Cache/Images": settings.CACHE_DIR / "images"
    }
    
    for name, path in directories.items():
        try:
            path.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                raise RuntimeError(f"{name} directory could not be created: {path}")
            logger.info(f" {name} directory: {path}")
        except Exception as e:
            logger.error(f"Failed to create {name} directory: {e}")
            raise

# FIXED: Validate critical paths exist
def _validate_critical_paths():
    """Validate that critical paths exist"""
    critical_paths = {
        "Templates directory": settings.TEMPLATES_DIR,
        "Assets directory": settings.ASSETS_DIR,
    }
    
    missing_paths = []
    for name, path in critical_paths.items():
        if not path.exists():
            missing_paths.append(f"{name}: {path}")
    
    if missing_paths:
        error_msg = "Critical paths missing:\n" + "\n".join(f"  - {p}" for p in missing_paths)
        logger.error(f"{error_msg}")
        raise FileNotFoundError(error_msg)
    
    logger.info("All critical paths validated")

# Initialize on import
try:
    _initialize_directories()
    _validate_critical_paths()
    
    # # FIXED: Log configuration with masked secrets
    # logger.info("\n" + "="*80)
    # logger.info("🚀 Proposal PPT Generator - Configuration Loaded")
    # logger.info("="*80)
    # logger.info(f"📁 Base directory: {settings.BASE_DIR}")
    # logger.info(f"📁 Output directory: {settings.OUTPUT_DIR}")
    # logger.info(f"📁 Templates directory: {settings.TEMPLATES_DIR}")
    # logger.info(f"📁 Assets directory: {settings.ASSETS_DIR}")
    # logger.info(f"📁 Cache directory: {settings.CACHE_DIR}")
    # logger.info(f"🔑 OpenAI API Key: {settings.mask_secret(settings.OPENAI_API_KEY)}")
    # logger.info(f"🔑 OpenAI Model: {settings.OPENAI_MODEL}")
    # logger.info(f"🎨 DALL-E Model: {settings.DALL_E_MODEL}")
    # logger.info(f"🎨 DALL-E Size: {settings.DALL_E_SIZE}")
    # logger.info(f"🎨 DALL-E Quality: {settings.DALL_E_QUALITY}")
    # logger.info(f"☁️  Supabase URL: {settings.SUPABASE_URL}")
    # logger.info(f"🔑 Supabase Key: {settings.mask_secret(settings.SUPABASE_KEY)}")
    # logger.info(f"🪣 Supabase Bucket: {settings.SUPABASE_BUCKET}")
    # logger.info(f"🎯 Default Template: {settings.DEFAULT_TEMPLATE}")
    # logger.info(f"🐛 Debug Mode: {settings.DEBUG}")
    # logger.info("="*80 + "\n")
    
except Exception as e:
    logger.error(f"Configuration initialization failed: {e}")
    raise
