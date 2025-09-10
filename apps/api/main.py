from fastapi import FastAPI, HTTPException, Request, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List
import logging
import os
from datetime import datetime
from dotenv import load_dotenv
import sys

# Load environment variables FIRST before any other imports
load_dotenv()

# Now import routes after environment is loaded
from routes import rfp, jobs

# Configure logging
log_level = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="RFP Proposal Platform API",
    description="OneDrive integration with OCR processing for RFP documents and proposals",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(rfp.router, prefix="/api/v1/rfp")
app.include_router(jobs.router, prefix="/api/v1/jobs")

@app.get("/")
async def root():
    return {
        "message": "RFP Proposal Platform API",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "environment": os.getenv("ENVIRONMENT", "development")
    }

# === MERGED ENDPOINT 1: GET ALL SUBFOLDERS AND FILES FROM RFP-UPLOADS ===
@app.get("/api/v1/rfp/rfp-uploads/files")
async def get_rfp_uploads_files():
    """
    MERGED ENDPOINT 1: Fetch all subfolders and their files from RFP-Uploads
    
    This will show you the two subfolders you see in OneDrive:
    - ^4af8aa8-e825-44d8-a725-253c0da86f73 (2 items)
    - ^edbcf640-43ab-4d9f-a73e-c2be2f807ee3 (2 items)
    """
    return await rfp.get_rfp_uploads_files()

# === MERGED ENDPOINT 2: PROCESS SPECIFIC SUBFOLDER WITH OCR ===
@app.post("/api/v1/rfp/folders/{folder_name}/ocr")
async def process_folder_with_ocr(
    folder_name: str,
    background_tasks: BackgroundTasks = None
):
    """
    MERGED ENDPOINT 2: Process a specific subfolder with OCR
    
    Usage examples:
    - Process specific subfolder: POST /folders/edbcf640-43ab-4d9f-a73e-c2be2f807ee3/ocr
    - Process other subfolder: POST /folders/^4af8aa8-e825-44d8-a725-253c0da86f73/ocr
    - Process all RFP-Uploads subfolders: POST /folders/RFP-Uploads/ocr
    """
    return await rfp.process_folder_with_ocr(folder_name, background_tasks)

# === BONUS ENDPOINT: GET FILES FROM SPECIFIC SUBFOLDER ===
@app.get("/api/v1/rfp/rfp-uploads/subfolder/{subfolder_name}/files")
async def get_subfolder_files(subfolder_name: str):
    """
    BONUS: Get files from a specific subfolder within RFP-Uploads
    
    Usage:
    - GET /rfp-uploads/subfolder/^4af8aa8-e825-44d8-a725-253c0da86f73/files
    - GET /rfp-uploads/subfolder/edbcf640-43ab-4d9f-a73e-c2be2f807ee3/files
    
    This lets you see what files are in each subfolder before processing
    """
    return await rfp.get_specific_subfolder_files(subfolder_name)

@app.get("/health")
async def health_check():
    try:
        env_status = {
            "tenant_id": "configured" if os.getenv("TENANT_ID") else "missing",
            "client_id": "configured" if os.getenv("CLIENT_ID") else "missing", 
            "client_secret": "configured" if os.getenv("CLIENT_SECRET") else "missing",
            "ocr_key": "configured" if os.getenv("OCR_KEY") else "missing",
            "ocr_endpoint": "configured" if os.getenv("OCR_ENDPOINT") else "missing"
        }
        
        overall_status = "healthy" if all(
            status == "configured" for status in env_status.values()
        ) else "degraded"
        
        return {
            "status": overall_status,
            "timestamp": datetime.now().isoformat(),
            "environment": env_status
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            }
        )

if __name__ == "__main__":
    import uvicorn
    
    host = os.getenv("APP_HOST", "0.0.0.0")
    port = int(os.getenv("APP_PORT", 8000))
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=os.getenv("ENVIRONMENT") == "development",
        log_level=os.getenv("LOG_LEVEL", "info").lower()
    )
