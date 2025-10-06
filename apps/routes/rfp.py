import logging
import os
from pathlib import Path
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Body, Path
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

from apps.wordgenAgent.app.api import wordgen_api
from apps.api.services.supabase_service import (
    get_pdf_urls_by_uuid,
    get_generated_markdown
)


from apps.regen_services.regen_prompt import regenerate_markdown_with_comments, regenerate_markdown_with_comments_streaming

from apps.wordgenAgent.app.document import generate_word_and_pdf_from_markdown

logger = logging.getLogger("routes.rfp")
router = APIRouter()


class InitialGenRequest(BaseModel):
    config: Optional[str] = None
    docConfig: Optional[Dict[str, Any]] = None
    timestamp: Optional[str] = None
    language: Optional[str] = "english" 
    commentConfig: Optional[Dict[str, Any]] = None


@router.post("/initialgen/{uuid}")
def initialgen(uuid: str = Path(...), request: InitialGenRequest = Body(...)):
    try:
        user_config = request.config
        doc_config = request.docConfig
        language = request.language

        logger.info(f"Received config: {user_config}")
        logger.info(f"Received docConfig: {doc_config}")
        logger.info(f"language received: {language}")

        urls = get_pdf_urls_by_uuid(uuid)
        if not urls or not urls.get("rfp_url") or not urls.get("supporting_url"):
            raise HTTPException(status_code=404, detail="RFP/Supporting URLs not found for UUID")
        
        logger.info(f"initialgen: uuid={uuid} urls-ok language={request.language}")
        outline = None
        if request.docConfig and isinstance(request.docConfig, dict):
            outline = request.docConfig.get("outline")
        
        def stream_generator():
            for chunk in wordgen_api.generate_complete_proposal(
                uuid=uuid,
                rfp_url=urls["rfp_url"],
                supporting_url=urls["supporting_url"],
                user_config=request.config or "",
                doc_config=request.docConfig or {},
                language=(request.language or "english").lower(),
                outline=outline,
            ):
                yield chunk
        
        return StreamingResponse(stream_generator(), media_type="text/event-stream")

    except HTTPException:
        logger.exception("initialgen HTTP error")
        raise
    except Exception as e:
        logger.exception("initialgen failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/regenerate/{uuid}")
def regeneration_process(
    uuid: str = Path(..., description="UUID for the proposal to regenerate"),
    request: InitialGenRequest = Body(...)
):

    try:
        logger.info(f"Starting streaming markdown regeneration for uuid={uuid}")
        logger.info(f"Language: {request.language}")
       
        def stream_generator():
            for chunk in regenerate_markdown_with_comments_streaming(
                uuid=uuid,
                language=request.language or "english",
                docConfig=request.docConfig or {},
            ):
                yield chunk
        
        return StreamingResponse(stream_generator(), media_type="text/event-stream")
    
    except HTTPException:
        logger.exception(f"regenerate HTTP error for uuid={uuid}")
        raise
    except Exception as e:
        logger.exception(f"regenerate failed for uuid={uuid}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chat-stream/{uuid}")
def chat_stream(uuid: str = Path(..., description="UUID for this proposal"),
                language: Optional[str] = "english"):
    try:
        urls = get_pdf_urls_by_uuid(uuid)
        if not urls or not urls.get("rfp_url") or not urls.get("supporting_url"):
            raise HTTPException(status_code=404, detail="RFP/Supporting URLs not found for UUID")
        
        logger.info(f"chat-stream: uuid={uuid} lang={language}")

        def gen():
            for chunk in wordgen_api.iter_initialgen_stream(
                uuid=uuid,
                rfp_url=urls["rfp_url"],
                supporting_url=urls["supporting_url"],
                language=(language or "english").lower(),
            ):
                yield chunk

        return StreamingResponse(gen(), media_type="text/event-stream")

    except HTTPException:
        logger.exception("chat_stream HTTP error")
        raise
    except Exception as e:
        logger.exception("chat_stream failed")
        raise HTTPException(status_code=500, detail=str(e))

class DownloadRequest(BaseModel):
    docConfig: Optional[Dict[str, Any]] = None
    language: Optional[str] = "english"


@router.post("/download/{uuid}")
def download_proposal(
    uuid: str = Path(..., description="UUID for this proposal"),
    request: DownloadRequest = Body(...)
):
    try:
        logger.info(f"Fetching generated markdown for uuid={uuid}")
        md = get_generated_markdown(uuid)
        if not md:
            raise HTTPException(
                status_code=404, 
                detail="No generated content found. Run /initialgen or /chat-stream first."
            )
        
        logger.info(f"Markdown retrieved for uuid={uuid}, length={len(md)} chars")
        logger.info(f"Starting document generation for uuid={uuid}, language={request.language}")
        
        urls = generate_word_and_pdf_from_markdown(
            uuid=uuid,
            markdown=md,
            doc_config=request.docConfig,
            language=(request.language or "english").lower()
        )
        
        logger.info(f"Document generation completed for uuid={uuid}")
        logger.info(f"Word URL: {urls['proposal_word_url']}")
        logger.info(f"PDF URL: {urls['proposal_pdf_url']}")
        
        return JSONResponse({
            "status": "success",
            "uuid": uuid,
            "proposal_word_url": urls["proposal_word_url"],
            "proposal_pdf_url": urls["proposal_pdf_url"],
            "language": request.language or "english",
        })
    
    except HTTPException:
        logger.exception(f"download HTTP error for uuid={uuid}")
        raise
    except Exception as e:
        logger.exception(f"download failed for uuid={uuid}")
        raise HTTPException(status_code=500, detail=str(e))