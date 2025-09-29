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

        user_config = request.config
        doc_config = request.docConfig
        language = request.language

        logger.info(f"Received config: {user_config}")
        logger.info(f"Received docConfig: {doc_config}")
        logger.info(f"laguage received: {language}")

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




from apps.regen_services.regen_prompt import regen_proposal_chat
from apps.wordgenAgent.app.wordcom import build_word_from_proposal
import time
from apps.supabase.supabase_service import upload_and_save_files , get_comments_base
from docx2pdf import convert
import pythoncom


@router.post("/regenerate/{uuid}")
def regeneration_process(uuid: str = Path(..., description="Folder name to process"), request: InitialGenRequest = Body(...)):
    try:
        user_config = request.config
        doc_config = request.docConfig
        language = request.language

        logger.info(f"Received config: {user_config}")
        logger.info(f"Received docConfig: {doc_config}")
        logger.info(f"laguage received: {language}")

        payload = get_comments_base(uuid=uuid)
        

        context = regen_proposal_chat(payload=payload, language=language)

        build_word_from_proposal(context, output_path=f"output/{uuid}.docx", visible=False , user_config=doc_config, language=language)
        
        local_docx = os.path.join("output", f"{uuid}.docx")
        local_pdf = os.path.join("output", f"{uuid}.pdf")
        
        try:
            pythoncom.CoInitialize()
            convert(local_docx, local_pdf)
            logger.info(f"Converted DOCX to PDF: {local_pdf}")
            url = upload_and_save_files(word_file_path=local_docx, word_file_name=f"{uuid}.docx", pdf_file_path=local_pdf, pdf_file_name=f"{uuid}.pdf", uuid = uuid)
        finally:
            pythoncom.CoUninitialize()
            os.remove(local_docx)
            os.remove(local_pdf)

        print("regen has been Completed !!!")
        return url

    except ImportError as e:   
        logger.info(f"domething somthing cumthing pumthing")

    