import logging
from typing import Optional, Dict, Any, List
import json
from fastapi import APIRouter, HTTPException, Body, Path
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from apps.wordgenAgent.app.api import wordgen_api
from apps.api.services.supabase_service import (
    get_pdf_urls_by_uuid,
    get_generated_markdown,
    get_latest_gen_id,
)
from apps.wordgenAgent.app.document import generate_word_from_markdown

logger = logging.getLogger("routes.rfp")
router = APIRouter()


class InitialGenRequest(BaseModel):
    config: Optional[str] = None
    docConfig: Optional[Dict[str, Any]] = None
    timestamp: Optional[str] = None
    language: Optional[str] = "english"
    commentConfig: Optional[Dict[str, Any]] = None

class RegenRequest(BaseModel):
    uuid: str
    gen_id: str
    docConfig: Optional[Dict[str, Any]] = None
    timestamp: Optional[str] = None
    language: Optional[str] = "english"
    commentConfig: Optional[List[Dict[str, str]]] = None



@router.post("/initialgen/{uuid}")
def initialgen(uuid: str = Path(...), request: InitialGenRequest = Body(...)):
    try:
        urls = get_pdf_urls_by_uuid(uuid)
        if not urls or not urls.get("rfp_url") or not urls.get("supporting_url"):
            raise HTTPException(status_code=404, detail="RFP/Supporting URLs not found for UUID")
        gen_id = get_latest_gen_id(uuid)
        if not gen_id:
            raise HTTPException(status_code=404, detail="No existing gen_id found for this UUID")

        outline = None
        if request.docConfig and isinstance(request.docConfig, dict):
            outline = request.docConfig.get("outline")

        def stream_generator():
            for chunk in wordgen_api.generate_complete_proposal(
                uuid=uuid,
                gen_id=gen_id, 
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


@router.post("/regenerate")
async def regenerate(request: RegenRequest):
    """
    Regenerates the proposal based on the previous gen_id (base version) - STREAMING.
    """
    from apps.api.services import supabase_service
    from apps.regen_services import regen_prompt

    uuid = request.uuid
    base_gen_id = request.gen_id 
    new_gen_id = supabase_service.generate_new_gen_id()  

    doc_config = request.docConfig or {}
    language = request.language or "english"
    comments = request.commentConfig or []

    try:
        base_markdown = supabase_service.get_markdown_content(uuid, base_gen_id)
        if not base_markdown:
            raise HTTPException(status_code=404, detail=f"No markdown found for gen_id={base_gen_id}")
        
        regen_comments_str = json.dumps(comments, ensure_ascii=False)
        ok = supabase_service.create_regeneration_row(
            uuid=uuid,
            new_gen_id=new_gen_id,
            regen_comments=regen_comments_str,
        )
        if not ok:
            raise HTTPException(status_code=400, detail="Failed to create regeneration version row")

        def stream_generator():
            for chunk in regen_prompt.regenerate_markdown_with_comments_streaming(
                uuid=uuid,
                source_markdown=base_markdown,
                gen_id=new_gen_id,
                docConfig=doc_config,
                language=language,
                comments=comments,
            ):
                yield chunk

        return StreamingResponse(stream_generator(), media_type="text/event-stream")

    except Exception as e:
        logger.exception("regenerate endpoint failed")
        raise HTTPException(status_code=500, detail=f"Regeneration failed: {str(e)}")

class DownloadRequest(BaseModel):
    docConfig: Optional[Dict[str, Any]] = None
    language: Optional[str] = "english"
    gen_id: Optional[str] = None  


@router.post("/download/{uuid}")
def download_proposal(
    uuid: str = Path(..., description="UUID for this proposal"),
    request: DownloadRequest = Body(...),
):
    """
    Rebuilds Word from saved markdown for a specific (uuid, gen_id).
    If gen_id not provided, the latest gen is used.
    """
    try:
        active_gen_id = request.gen_id or get_latest_gen_id(uuid)
        if not active_gen_id:
            raise HTTPException(status_code=404, detail="No generation found for this UUID")

        md = get_generated_markdown(uuid, gen_id=active_gen_id)
        if not md:
            raise HTTPException(status_code=404, detail="No generated content found. Run /initialgen or /regenerate first.")

        res = generate_word_from_markdown(
            uuid=uuid,
            gen_id=active_gen_id,
            markdown=md,
            doc_config=request.docConfig,
            language=(request.language or "english").lower(),
        )

        return JSONResponse(
            {
                "status": "success",
                "uuid": uuid,
                "gen_id": active_gen_id,
                "proposal_word_url": res.get("proposal_word_url", ""),
                "language": request.language or "english",
            }
        )

    except HTTPException:
        logger.exception(f"download HTTP error for uuid={uuid}")
        raise
    except Exception as e:
        logger.exception(f"download failed for uuid={uuid}")
        raise HTTPException(status_code=500, detail=str(e))
