import logging
from fastapi import APIRouter, HTTPException, Body, Path
from pydantic import BaseModel
from typing import Optional, Dict, Any

from apps.wordgenAgent.app.api import wordgen_api
from apps.api.services.supabase_service import get_pdf_urls_by_uuid

logger = logging.getLogger("routes.rfp")
router = APIRouter()

class InitialGenRequest(BaseModel):
    config: Optional[str] = None           
    docConfig: Optional[Dict[str, Any]] = None
    timestamp: Optional[str] = None
    language: Optional[str] = "english"   

@router.post("/initialgen/{uuid}")
def initialgen(uuid: str = Path(...), request: InitialGenRequest = Body(...)):
    try:
        urls = get_pdf_urls_by_uuid(uuid)
        if not urls or not urls.get("rfp_url") or not urls.get("supporting_url"):
            raise HTTPException(status_code=404, detail="RFP/Supporting URLs not found for UUID")
        logger.info(f"initialgen: uuid={uuid} urls-ok language={request.language}")
        outline = None
        if request.docConfig and isinstance(request.docConfig, dict):
            outline = request.docConfig.get("outline")
        result = wordgen_api.generate_complete_proposal(
            uuid=uuid,
            rfp_url=urls["rfp_url"],
            supporting_url=urls["supporting_url"],
            user_config=request.config or "",
            doc_config=request.docConfig or {},
            language=(request.language or "english").lower(),
            outline=outline,
        )
        return result
    except HTTPException:
        logger.exception("initialgen HTTP error")
        raise
    except Exception as e:
        logger.exception("initialgen failed")
        raise HTTPException(status_code=500, detail=str(e))

from fastapi.responses import FileResponse
import os

@router.get("/download/{filename}")
def download(filename: str):
    path = os.path.join("output", filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path=path, filename=filename)
