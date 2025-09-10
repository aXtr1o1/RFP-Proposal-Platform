from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
import uuid

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory job storage (replace with Redis/database in production)
jobs_storage = {}

class JobStatus(BaseModel):
    job_id: str
    status: str
    created_at: str
    updated_at: str
    folder_name: Optional[str] = None
    progress: Optional[int] = 0
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

async def get_all_jobs():
    try:
        jobs_list = []
        for job_id, job_data in jobs_storage.items():
            jobs_list.append({
                "job_id": job_id,
                "status": job_data.get("status", "unknown"),
                "created_at": job_data.get("created_at"),
                "folder_name": job_data.get("folder_name"),
                "progress": job_data.get("progress", 0)
            })
        
        return {
            "total_jobs": len(jobs_list),
            "jobs": jobs_list,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting jobs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving jobs: {str(e)}")

async def get_job_status(job_id: str):
    try:
        if job_id not in jobs_storage:
            raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
        
        job_data = jobs_storage[job_id]
        return {
            "job_id": job_id,
            "status": job_data.get("status"),
            "created_at": job_data.get("created_at"),
            "updated_at": job_data.get("updated_at"),
            "folder_name": job_data.get("folder_name"),
            "progress": job_data.get("progress", 0),
            "error": job_data.get("error")
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job status for {job_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting job status: {str(e)}")

async def get_job_result(job_id: str):
    try:
        if job_id not in jobs_storage:
            raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
        
        job_data = jobs_storage[job_id]
        
        if job_data.get("status") != "completed":
            return {
                "job_id": job_id,
                "status": job_data.get("status"),
                "message": "Job not completed yet"
            }
        
        return {
            "job_id": job_id,
            "status": job_data.get("status"),
            "result": job_data.get("result"),
            "completed_at": job_data.get("updated_at")
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job result for {job_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting job result: {str(e)}")

async def cancel_job(job_id: str):
    try:
        if job_id not in jobs_storage:
            raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
        
        job_data = jobs_storage[job_id]
        
        if job_data.get("status") in ["completed", "failed", "cancelled"]:
            return {
                "job_id": job_id,
                "message": f"Cannot cancel job with status: {job_data.get('status')}"
            }
        
        jobs_storage[job_id].update({
            "status": "cancelled",
            "updated_at": datetime.now().isoformat()
        })
        
        return {
            "job_id": job_id,
            "status": "cancelled",
            "message": "Job cancelled successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling job {job_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error cancelling job: {str(e)}")

async def retry_job(job_id: str):
    try:
        if job_id not in jobs_storage:
            raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
        
        job_data = jobs_storage[job_id]
        
        if job_data.get("status") not in ["failed", "cancelled"]:
            return {
                "job_id": job_id,
                "message": f"Cannot retry job with status: {job_data.get('status')}"
            }
        
        # Create new job ID for retry
        new_job_id = f"retry_{job_id}_{uuid.uuid4().hex[:8]}"
        
        jobs_storage[new_job_id] = {
            "status": "queued",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "folder_name": job_data.get("folder_name"),
            "progress": 0,
            "original_job_id": job_id
        }
        
        return {
            "original_job_id": job_id,
            "new_job_id": new_job_id,
            "status": "queued",
            "message": "Job retry initiated"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrying job {job_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrying job: {str(e)}")
