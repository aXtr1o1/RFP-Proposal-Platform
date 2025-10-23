from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from core.logger import get_logger
from core.utils import uuid_like
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
        logger.info(f"templates listed (count={len(templates)})")
        return {"status": "success", "templates": templates}
    except Exception as e:
        logger.error(f"templates listing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/initialgen")
async def initialgen(req: InitialGenRequest):
    logger.info(
        "initial generation requested "
        f"(uuid={req.uuid[:8]}..., template={req.template[:8]}..., "
        f'pref="{req.user_preference}", lang={req.language[:2]})'
    )
    try:
        cache = CacheManager()
        generator = ProposalGenerator(supabase_service, OpenAIEngine(), cache, logger=get_logger("proposal"))
        result = generator.run_initial_generation(
            req.uuid, req.template, req.user_preference, req.language
        )
        logger.info(
            f"generation complete (ppt_url={result['ppt_url']}, pdf_url={result['pdf_url']})"
        )
        return {"status": "completed", **result}
    except (ValueError, RuntimeError) as e:
        logger.error(f"bad request: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"internal error: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.get("/download")
async def download(uuid: str, gen_id: str):
    logger.info(f"download requested (uuid={uuid[:8]}..., gen_id={gen_id[:8]}...)")
    try:
        rec = supabase_service.fetch_record(uuid, gen_id)
        if not rec:
            logger.info("record not found")
            raise HTTPException(status_code=404, detail="Record not found")
        logger.info("download urls ready")
        return {
            "status": "completed",
            "ppt_url": rec.get("generated_ppt"),
            "pdf_url": rec.get("generated_pdf"),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"download failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
