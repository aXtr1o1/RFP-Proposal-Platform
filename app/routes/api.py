import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from core.ppt_generation import run_initial_generation
from core.ppt_regeneration import run_regeneration
from core.supabase_service import get_proposal_url

logger = logging.getLogger("api")
router = APIRouter(prefix="", tags=["PPT"])


# ==================== SCHEMAS ====================

class PPTInitialGenRequest(BaseModel):
    uuid: str
    gen_id: str
    language: str = Field(..., pattern="^(English|Arabic)$")
    template_id: str = Field(
        default="arweqah", 
        description="Template identifier (e.g., 'standard'). Corresponds to app/templates/{template_id}/"
    )
    user_preference: str = Field(default="", description="User preferences")


class PPTInitialGenResponse(BaseModel):
    status: str
    ppt_genid: str
    ppt_url: Optional[str]
    template_used: str  # Which template was used
    generated_content: str


class RegenComment(BaseModel):
    comment1: str
    comment2: str


class PPTRegenRequest(BaseModel):
    uuid: str
    gen_id: str
    ppt_genid: str
    language: str = Field(..., pattern="^(English|Arabic)$")
    template_id: str = Field(
        default="arweqah",
        description="Template identifier to use for regeneration"
    )
    regen_comments: list[RegenComment]


class PPTRegenResponse(BaseModel):
    status: str
    new_ppt_genid: str
    ppt_url: Optional[str]
    template_used: str
    generated_content: str


class DownloadResponse(BaseModel):
    proposal_ppt: Optional[str]


# ==================== ENDPOINTS ====================

@router.post("/ppt-initialgen", response_model=PPTInitialGenResponse)
async def ppt_initialgen(body: PPTInitialGenRequest):
    """
    Generate initial presentation with local template
    
    Flow:
    1. Validate template_id (must exist in app/templates/)
    2. Generate content with OpenAI
    3. Apply local template styling
    4. Generate complete PPTX with images, icons, charts, tables
    5. Upload to Supabase
    """
    try:
        logger.info("="*80)
        logger.info("Received /ppt-initialgen request")
        logger.info(f"   UUID: {body.uuid}")
        logger.info(f"   Gen ID: {body.gen_id}")
        logger.info(f"   Language: {body.language}")
        logger.info(f"   Template ID: {body.template_id}")
        logger.info(f"   Template Path: app/templates/{body.template_id}/")
        logger.info("="*80)
        
        # Validate template exists locally
        from pathlib import Path
        from config import settings
        
        template_path = Path(settings.TEMPLATES_DIR) / body.template_id
        if not template_path.exists():
            available_templates = [d.name for d in Path(settings.TEMPLATES_DIR).iterdir() if d.is_dir()]
            raise HTTPException(
                status_code=400,
                detail=f"Template '{body.template_id}' not found. Available templates: {available_templates}"
            )
        
        logger.info(f"Template '{body.template_id}' found locally")
        
        # Run generation with local template
        result = await run_initial_generation(
            uuid=body.uuid,
            gen_id=body.gen_id,
            language=body.language,
            template_id=body.template_id,
            user_preference=body.user_preference,
        )
        
        return PPTInitialGenResponse(
            status="success",
            ppt_genid=result["ppt_genid"],
            ppt_url=result["ppt_url"],
            template_used=body.template_id,
            generated_content=result["generated_content"],
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("ppt-initialgen failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ppt-regeneration", response_model=PPTRegenResponse)
async def ppt_regeneration(body: PPTRegenRequest):
    """
    Regenerate presentation with feedback using local template
    
    Flow:
    1. Validate template_id
    2. Fetch previous generation
    3. Regenerate with feedback
    4. Apply local template styling
    5. Upload new PPTX to Supabase
    """
    try:
        logger.info("="*80)
        logger.info("Received /ppt-regeneration request")
        logger.info(f"   UUID: {body.uuid}")
        logger.info(f"   Gen ID: {body.gen_id}")
        logger.info(f"   Base PPT Gen ID: {body.ppt_genid}")
        logger.info(f"   Language: {body.language}")
        logger.info(f"   Template ID: {body.template_id}")
        logger.info(f"   Template Path: app/templates/{body.template_id}/")
        logger.info(f"   Comments: {len(body.regen_comments)}")
        logger.info("="*80)
        
        # Validate template exists locally
        from pathlib import Path
        from config import settings
        
        template_path = Path(settings.TEMPLATES_DIR) / body.template_id
        if not template_path.exists():
            available_templates = [d.name for d in Path(settings.TEMPLATES_DIR).iterdir() if d.is_dir()]
            raise HTTPException(
                status_code=400,
                detail=f"Template '{body.template_id}' not found. Available templates: {available_templates}"
            )
        
        logger.info(f"Template '{body.template_id}' found locally")
        
        # Run regeneration with local template
        result = await run_regeneration(
            uuid=body.uuid,
            gen_id=body.gen_id,
            base_ppt_genid=body.ppt_genid,
            language=body.language,
            template_id=body.template_id,
            regen_comments=[c.model_dump() for c in body.regen_comments],
        )
        
        return PPTRegenResponse(
            status="success",
            new_ppt_genid=result["ppt_genid"],
            ppt_url=result["ppt_url"],
            template_used=body.template_id,
            generated_content=result["generated_content"],
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("ppt-regeneration failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download", response_model=DownloadResponse)
async def download(
    uuid: str = Query(...),
    gen_id: str = Query(...),
    ppt_genid: str = Query(...)
):
    """Download generated presentation from Supabase"""
    try:
        logger.info(f"Download request: {ppt_genid}")
        
        url = await get_proposal_url(uuid, gen_id, ppt_genid)
        
        if not url:
            raise HTTPException(status_code=404, detail="Presentation not found")
        
        logger.info(f"Retrieved URL: {url}")
        return DownloadResponse(proposal_ppt=url)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("/download failed")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== UTILITY ENDPOINTS ====================

@router.get("/templates")
async def list_available_templates():
    """List all available local templates"""
    try:
        from pathlib import Path
        from config import settings
        
        templates_dir = Path(settings.TEMPLATES_DIR)
        
        if not templates_dir.exists():
            return {"templates": [], "error": "Templates directory not found"}
        
        templates = []
        for template_dir in templates_dir.iterdir():
            if template_dir.is_dir() and not template_dir.name.startswith('.'):
                config_file = template_dir / "config.json"
                
                if config_file.exists():
                    import json
                    with open(config_file, 'r') as f:
                        config = json.load(f)
                    
                    templates.append({
                        "id": template_dir.name,
                        "name": config.get("name", template_dir.name),
                        "description": config.get("description", ""),
                        "version": config.get("version", "1.0.0")
                    })
                else:
                    templates.append({
                        "id": template_dir.name,
                        "name": template_dir.name,
                        "description": "Template configuration not found",
                        "version": "unknown"
                    })
        
        return {
            "templates": templates,
            "total": len(templates)
        }
    
    except Exception as e:
        logger.exception("/templates failed")
        raise HTTPException(status_code=500, detail=str(e))
