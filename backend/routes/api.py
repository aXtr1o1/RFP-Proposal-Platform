from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from core.logger import get_logger
from core.cache_manager import CacheManager
from services.supabase_service import supabase_service
from services.proposal_generation import OpenAIEngine, ProposalGenerator

router = APIRouter()
logger = get_logger("api")

class InitialGenRequest(BaseModel):
    uuid: str
    template: str
    user_preference: str = ""
    language: str = "english"

@router.get("/template")
async def get_templates():
    try:
        templates = supabase_service.get_templates()
        return {"status":"success","templates":templates}
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/initialgen")
async def initialgen(req: InitialGenRequest):
    try:
        cache = CacheManager()
        generator = ProposalGenerator(supabase_service, OpenAIEngine(), cache)
        result = generator.run_initial_generation(req.uuid, req.template, req.user_preference, req.language)
        return {"status":"completed", **result}
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/download")
async def download(uuid: str, gen_id: str):
    try:
        rec = supabase_service.fetch_record(uuid, gen_id)
        if not rec:
            raise HTTPException(status_code=404, detail="Record not found")
        return {"status":"completed","ppt_url":rec.get("generated_ppt"),"pdf_url":rec.get("generated_pdf")}
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail=str(e))
