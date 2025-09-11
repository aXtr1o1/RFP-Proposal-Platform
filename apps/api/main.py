from fastapi import FastAPI, HTTPException, BackgroundTasks, Path, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import os
from datetime import datetime
from dotenv import load_dotenv
import sys

load_dotenv()

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="RFP Proposal Platform API",
    description="OneDrive integration with OCR processing and Vector Database",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from routes import rfp, jobs
app.include_router(rfp.router, prefix="/api/v1/rfp")
app.include_router(jobs.router, prefix="/api/v1/jobs")

@app.get("/")
async def root():
    return {
        "message": "RFP Proposal Platform API",
        "version": "1.0.0",
        "endpoints": {
            "/files": "GET - View available folders in RFP-Uploads",
            "/ocr/{folder_name}": "POST - Process folder with OCR + Auto Vector Storage",
            "/milvus-data": "GET - View stored vector documents",
            "/search": "GET - Vector similarity search",
            "/api/v1/jobs": "GET - List all jobs",
            "/api/v1/jobs/{job_id}": "GET - Get job status"
        },
        "timestamp": datetime.now().isoformat(),
        "environment": os.getenv("ENVIRONMENT", "development")
    }


@app.get("/files")
async def get_available_folders():
    """View available folders inside RFP-Uploads"""
    return await rfp.get_available_folders()

@app.post("/ocr/{folder_name}")
async def process_folder_ocr(
    folder_name: str = Path(..., description="Folder name to process"),
    background_tasks: BackgroundTasks = None
):
    """Process folder with OCR and automatically save to Milvus"""
    return await rfp.process_folder_with_ocr_and_vectors(folder_name, background_tasks)

@app.get("/milvus-data")
async def view_milvus_data():
    """View all stored vector documents"""
    return await rfp.get_milvus_data()

@app.get("/search")
async def search_documents(
    query: str = Query(..., description="Search query"),
    limit: int = Query(10, description="Number of results")
):
    """Search documents using vector similarity"""
    try:
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'vdb'))
        from milvus_client import get_milvus_client
        
        milvus_client = get_milvus_client()
        
        if not milvus_client.is_available():
            raise HTTPException(status_code=503, detail="Vector search not available")
        
        results = milvus_client.search_similar_documents(query, limit)
        
        return {
            "query": query,
            "results_count": len(results),
            "results": results,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    try:
        env_status = {
            "tenant_id": "configured" if os.getenv("TENANT_ID") else "missing",
            "client_id": "configured" if os.getenv("CLIENT_ID") else "missing", 
            "client_secret": "configured" if os.getenv("CLIENT_SECRET") else "missing",
            "ocr_key": "configured" if os.getenv("OCR_KEY") else "missing",
            "ocr_endpoint": "configured" if os.getenv("OCR_ENDPOINT") else "missing",
            "milvus_uri": "configured" if os.getenv("MILVUS_URI") else "missing"
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
