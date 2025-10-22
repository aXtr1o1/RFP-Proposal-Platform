from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime

from routes.api import router
from routes.logging import logger
from routes.config import OPENAI_MODEL, SUPABASE_URL


# =============================
# FASTAPI APP INITIALIZATION
# =============================

app = FastAPI(
    title="RFP PPT Proposal Generation API",
    version="1.0.0",
    description="""
    Automated RFP proposal presentation generation using OpenAI and Supabase.
    
    Features:
    - Template selection from Supabase bucket
    - AI-powered content generation with chart support
    - Automatic PPT and PDF creation
    - English and Arabic language support
    """,
    docs_url="/docs",
    redoc_url="/redoc"
)


# =============================
# CORS MIDDLEWARE
# =============================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================
# INCLUDE ROUTERS
# =============================

app.include_router(router, prefix="/api", tags=["RFP Proposal"])


# =============================
# ROOT ENDPOINTS
# =============================

@app.get("/")
async def root():
    """
    Root endpoint - API information
    """
    return {
        "message": "RFP PPT Proposal Generation API",
        "status": "running",
        "version": "1.0.0",
        "description": "Automated proposal presentation generation",
        "endpoints": {
            "templates": "/api/ppt_templates",
            "generate": "/api/initialgen",
            "download": "/api/download",
            "docs": "/docs"
        }
    }


@app.get("/health")
async def health():
    """
    Health check endpoint
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "rfp-ppt-api",
        "version": "1.0.0"
    }


# =============================
# STARTUP EVENT
# =============================

@app.on_event("startup")
async def startup_event():
    """
    Execute on application startup
    """
    logger.info("=" * 80)
    logger.info("🚀 RFP PPT PROPOSAL GENERATION API")
    logger.info("=" * 80)
    logger.info(f"📅 Started at: {datetime.utcnow().isoformat()}")
    logger.info(f"🌐 Supabase URL: {SUPABASE_URL}")
    logger.info(f"🤖 OpenAI Model: {OPENAI_MODEL}")
    logger.info(f"📚 API Documentation: http://localhost:8000/docs")
    logger.info("=" * 80)
    logger.info("✅ Application started successfully")
    logger.info("=" * 80)


# =============================
# SHUTDOWN EVENT
# =============================

@app.on_event("shutdown")
async def shutdown_event():
    """
    Execute on application shutdown
    """
    logger.info("=" * 80)
    logger.info("⚠️  RFP PPT API SHUTTING DOWN")
    logger.info(f"📅 Shutdown at: {datetime.utcnow().isoformat()}")
    logger.info("=" * 80)


# =============================
# EXCEPTION HANDLER
# =============================

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """
    Global exception handler for unhandled errors
    """
    logger.error(f"❌ Unhandled exception: {exc}")
    logger.error(f"   Request: {request.method} {request.url}")
    
    return {
        "error": "Internal server error",
        "message": str(exc),
        "status_code": 500
    }


# =============================
# RUN APPLICATION
# =============================

if __name__ == "__main__":
    import uvicorn
    
    logger.info("Starting Uvicorn server...")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  
        log_level="info"
    )
