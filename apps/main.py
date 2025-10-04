import logging
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.routes.rfp import router as rfp_router

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("main")

app = FastAPI(
    title="RFP Proposal Platform",
    version="1.0.0",
    root_path="/api",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

app.include_router(rfp_router, tags=["proposal"])

@app.on_event("startup")
async def startup_event():
    logger.info("RFP Proposal Platform API started")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("RFP Proposal Platform API shutting down")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("apps.main:app", host="0.0.0.0", port=8000, reload=True)
