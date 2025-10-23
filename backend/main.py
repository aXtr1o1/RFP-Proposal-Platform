from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.logger import get_logger
from routes.api import router
from core.config import settings

logger = get_logger("main")

def create_app() -> FastAPI:
    app = FastAPI(
        title="RFP PPT Proposal Generation API",
        version="1.0.0",
        description="AI-driven RFP → Proposal deck generator (OpenAI + Supabase)",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router, prefix="/api", tags=["RFP Proposal"])

    @app.on_event("startup")
    async def startup_event():
        logger.info("=" * 80)
        logger.info("🚀 Starting RFP Proposal API")
        logger.info(f"🤖 Model: {settings.OPENAI_MODEL}")
        logger.info("=" * 80)

    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info("⚠️  Shutting down API...")

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    logger.info("Launching Uvicorn server...")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
