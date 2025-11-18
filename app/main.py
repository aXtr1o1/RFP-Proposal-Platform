import logging
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Import routes
from routes.api import router

# Import config to initialize settings
from config import settings


# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


# Initialize FastAPI app
app = FastAPI(
    title="Proposal PPT Generator API",
    description="Generate professional PowerPoint presentations with AI and Supabase integration",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)


# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include API routes
app.include_router(router)


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Proposal PPT Generator API v1.0",
        "description": "AI-powered presentation generation with Supabase storage",
        "version": "1.0.0",
    }


# Health check endpoint
@app.get("/health")
async def health():
    """Health check endpoint"""
    try:
        # Basic health check
        health_status = {
            "status": "healthy",
            "version": "1.0.0",
            "environment": {
                "debug_mode": settings.DEBUG,
                "openai_configured": bool(settings.OPENAI_API_KEY),
                "supabase_configured": bool(settings.SUPABASE_URL and settings.SUPABASE_KEY),
                "output_dir_exists": settings.OUTPUT_DIR.exists(),
                "templates_dir_exists": settings.TEMPLATES_DIR.exists(),
                "cache_dir_exists": settings.CACHE_DIR.exists()
            },
            "services": {
                "openai": "ready" if settings.OPENAI_API_KEY else "not_configured",
                "supabase": "ready" if (settings.SUPABASE_URL and settings.SUPABASE_KEY) else "not_configured",
                "dalle": "enabled",
                "templates": "loaded"
            }
        }
        
        return health_status
    
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "unhealthy",
                "error": str(e)
            }
        )


# Startup event
@app.on_event("startup")
async def startup_event():
    """Application startup event"""
    logger.info("="*80)
    logger.info("🚀 Starting Proposal PPT Generator API v1.0")
    logger.info("="*80)
    logger.info(f"📝 OpenAI Model: {settings.OPENAI_MODEL}")
    logger.info(f"🎨 DALL-E Model: {settings.DALL_E_MODEL}")
    logger.info(f"☁️  Supabase: {settings.SUPABASE_URL}")
    logger.info(f"🪣 Storage Bucket: {settings.SUPABASE_BUCKET}")
    logger.info(f"📁 Output Directory: {settings.OUTPUT_DIR}")
    logger.info(f"🎯 Default Template: {settings.DEFAULT_TEMPLATE}")
    logger.info("="*80)
    logger.info("✅ Application started successfully")
    logger.info("📚 API Documentation: http://localhost:8000/docs")
    logger.info("="*80)


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event"""
    logger.info("="*80)
    logger.info("🛑 Shutting down Proposal PPT Generator API")
    logger.info("="*80)
    logger.info("✅ Application shutdown complete")


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for unhandled errors"""
    logger.exception(f"Unhandled exception: {str(exc)}")
    
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": "An unexpected error occurred",
            "detail": str(exc) if settings.DEBUG else "Internal server error",
            "path": str(request.url)
        }
    )


# Run with: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info" if not settings.DEBUG else "debug"
    )
