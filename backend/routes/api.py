from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, validator
from typing import List, Dict, Any

from core.logger import get_logger
from core.utils import uuid_like
from core.cache_manager import CacheManager

from services.supabase_service import supabase_service
from services.proposal_generation import OpenAIEngine, ProposalGenerator
from services.regen_engine import RegenerationEngine

router = APIRouter()
logger = get_logger("api")


class InitialGenRequest(BaseModel):
    uuid: str
    template: str
    user_preference: str = ""
    language: str = "english"


class RegenRequest(BaseModel):
    uuid: str
    gen_id: str  
    regen_comments: List[Dict[str, Any]]
    language: str = "english"
    
    @validator('regen_comments')
    def validate_comments(cls, v):
        """Validate comment structure"""
        if not v:
            raise ValueError("regen_comments cannot be empty")
        
        for comment in v:
            if 'slide' not in comment:
                raise ValueError("Each comment must have 'slide' field")
            if 'original_content' not in comment:
                raise ValueError("Each comment must have 'original_content' field")
            if 'modification' not in comment:
                raise ValueError("Each comment must have 'modification' field")
            if not isinstance(comment['slide'], int):
                raise ValueError("'slide' field must be an integer")
        
        return v


@router.get("/template")
async def get_templates():
    """List all available PPT templates"""
    try:
        templates = supabase_service.get_templates()
        logger.info(f"templates listed (count={len(templates)})")
        return {"status": "success", "templates": templates}
    except Exception as e:
        logger.error(f"templates listing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/initialgen")
async def initialgen(req: InitialGenRequest):
    """Generate initial proposal presentation"""
    logger.info(
        "initial generation requested "
        f"(uuid={req.uuid[:8]}..., template={req.template[:8]}..., "
        f'pref="{req.user_preference}", lang={req.language[:2]})'
    )
    
    try:
        cache = CacheManager()
        generator = ProposalGenerator(
            supabase_service,
            OpenAIEngine(),
            cache,
            logger=get_logger("proposal")
        )
        
        result = generator.run_initial_generation(
            req.uuid,
            req.template,
            req.user_preference,
            req.language
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


@router.post("/regen")
async def regenerate_proposal(req: RegenRequest):
    """
    Regenerate presentation with modifications.
    """
    logger.info(
        f"regeneration requested "
        f"(uuid={req.uuid[:8]}..., prev_gen_id={req.gen_id[:8]}..., "
        f"modifications={len(req.regen_comments)}, lang={req.language[:2]})"
    )
    
    try:
        cache = CacheManager()
        openai_engine = OpenAIEngine(logger=get_logger("openai"))
        regen_engine = RegenerationEngine(
            supabase_service,
            openai_engine,
            cache,
            logger=get_logger("regen")
        )
        
        result = regen_engine.run_regeneration(
            uuid=req.uuid,
            previous_gen_id=req.gen_id,
            regen_comments=req.regen_comments,
            language=req.language
        )
        
        logger.info(
            f"regeneration complete (new_gen_id={result['gen_id']}, "
            f"modifications_applied={result['modifications_applied']})"
        )
        
        return result
        
    except ValueError as e:
        logger.error(f"validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"regeneration failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download")
async def download(uuid: str, gen_id: str):
    """Download generated PPT and PDF URLs"""
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
