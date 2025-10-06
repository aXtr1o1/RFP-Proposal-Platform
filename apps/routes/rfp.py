import logging
import os
from pathlib import Path
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Body, Path
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
import asyncio
from concurrent.futures import ThreadPoolExecutor

from apps.wordgenAgent.app.api import wordgen_api
from apps.api.services.supabase_service import (
    get_pdf_urls_by_uuid,
    get_generated_markdown
)

from apps.regen_services.regen_prompt import regenerate_markdown_with_comments

from apps.wordgenAgent.app.document import generate_word_and_pdf_from_markdown

logger = logging.getLogger("routes.rfp")
router = APIRouter()

background_executor = ThreadPoolExecutor(max_workers=2)

class InitialGenRequest(BaseModel):
    config: Optional[str] = None
    docConfig: Optional[Dict[str, Any]] = None
    timestamp: Optional[str] = None
    language: Optional[str] = "english"

@router.post("/initialgen/{uuid}")
def initialgen(uuid: str = Path(...), request: InitialGenRequest = Body(...)):
    try:
        logger.info(f"Starting initialgen with streaming for uuid={uuid}")
        logger.info(f"Config: {request.config}, DocConfig: {request.docConfig}, Language: {request.language}")

        urls = get_pdf_urls_by_uuid(uuid)
        if not urls or not urls.get("rfp_url") or not urls.get("supporting_url"):
            raise HTTPException(status_code=404, detail="RFP/Supporting URLs not found for UUID")
        
        logger.info(f"URLs fetched for uuid={uuid}")
        
        outline = None
        if request.docConfig and isinstance(request.docConfig, dict):
            outline = request.docConfig.get("outline")
        
        def gen():
            generator = wordgen_api.generate_complete_proposal(
                uuid=uuid,
                rfp_url=urls["rfp_url"],
                supporting_url=urls["supporting_url"],
                user_config=request.config or "",
                doc_config=request.docConfig or {},
                language=(request.language or "english").lower(),
                outline=outline,
            )
            
            for chunk in generator:
                yield chunk
            logger.info("Streaming complete, triggering background Word/PDF generation...")
            background_executor.submit(
                convert_markdown_to_files_background,
                uuid,
                request.docConfig,
                (request.language or "english").lower()
            )
        
        return StreamingResponse(gen(), media_type="text/event-stream")

    except HTTPException:
        logger.exception("initialgen HTTP error")
        raise
    except Exception as e:
        logger.exception("initialgen failed")
        raise HTTPException(status_code=500, detail=str(e))


def convert_markdown_to_files_background(uuid: str, doc_config: Optional[Dict[str, Any]], language: str):
    try:
        import time
        time.sleep(2)
        
        logger.info(f"Background: Fetching markdown for uuid={uuid}")
        final_markdown = get_generated_markdown(uuid)
        if not final_markdown:
            logger.error(f"Background: No markdown found for uuid={uuid}")
            return
        
        logger.info(f"Background: Converting markdown to Word/PDF for uuid={uuid}")
        urls_result = generate_word_and_pdf_from_markdown(
            uuid=uuid,
            markdown=final_markdown,
            doc_config=doc_config,
            language=language
        )
        
        logger.info(f"Background: Word URL: {urls_result['proposal_word_url']}")
        logger.info(f"Background: PDF URL: {urls_result['proposal_pdf_url']}")
        logger.info(f"Background: Conversion complete for uuid={uuid}")
        
    except Exception as e:
        logger.exception(f"Background conversion failed for uuid={uuid}: {e}")



@router.post("/regenerate/{uuid}")
def regeneration_process(
    uuid: str = Path(..., description="UUID for the proposal to regenerate"),
    request: InitialGenRequest = Body(...)
):

    try:
        logger.info(f"Starting markdown regeneration for uuid={uuid}")
        logger.info(f"Language: {request.language}")
    
        result = regenerate_markdown_with_comments(
            uuid=uuid,
            language=request.language or "english"
        )
        
        updated_markdown = result.get("updated_markdown", "")
        if not updated_markdown:
            raise HTTPException(status_code=500, detail="Regeneration failed: no markdown returned")
        
        logger.info(f"Markdown regenerated, length: {len(updated_markdown)} chars")

        logger.info("Converting updated markdown to Word and PDF...")
        urls_result = generate_word_and_pdf_from_markdown(
            uuid=uuid,
            markdown=updated_markdown,
            doc_config=request.docConfig,
            language=(request.language or "english").lower()
        )
        
        logger.info(f"Word URL: {urls_result['proposal_word_url']}")
        logger.info(f"PDF URL: {urls_result['proposal_pdf_url']}")
        
        return JSONResponse({
            "status": "success",
            "uuid": uuid,
            "updated_markdown": updated_markdown,
            "modifications_applied": result.get("modifications_applied", 0),
            "proposal_word_url": urls_result["proposal_word_url"],
            "proposal_pdf_url": urls_result["proposal_pdf_url"],
            "language": request.language or "english"
        })
    
    except HTTPException:
        logger.exception(f"regenerate HTTP error for uuid={uuid}")
        raise
    except Exception as e:
        logger.exception(f"regenerate failed for uuid={uuid}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/download/{uuid}")
def download_proposal(
    uuid: str = Path(..., description="UUID for this proposal"),
    language: Optional[str] = "english"
):
    try:
        from apps.api.services.supabase_service import supabase, DATA_TABLE
        
        logger.info(f"Fetching saved Word/PDF URLs for uuid={uuid}")
    
        res = supabase.table(DATA_TABLE).select(
            "Proposal_word, Proposal_pdf"
        ).eq("uuid", uuid).maybe_single().execute()
        
        if not res.data:
            raise HTTPException(
                status_code=404,
                detail=f"No proposal files found for uuid={uuid}. Run /initialgen first."
            )
        
        proposal_word_url = res.data.get("Proposal_word", "")
        proposal_pdf_url = res.data.get("Proposal_pdf", "")
        
        if not proposal_word_url and not proposal_pdf_url:
            raise HTTPException(
                status_code=404,
                detail="Proposal files not generated yet. Run /initialgen first."
            )
        
        logger.info(f"Word URL: {proposal_word_url}")
        logger.info(f"PDF URL: {proposal_pdf_url}")
        
        return JSONResponse({
            "status": "success",
            "uuid": uuid,
            "proposal_word_url": proposal_word_url,
            "proposal_pdf_url": proposal_pdf_url,
            "language": language or "english"
        })
    
    except HTTPException:
        logger.exception(f"download HTTP error for uuid={uuid}")
        raise
    except Exception as e:
        logger.exception(f"download failed for uuid={uuid}")
        raise HTTPException(status_code=500, detail=str(e))
