from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import logging

from core.ppt_generation import run_initial_generation
from core.ppt_regeneration import run_regeneration

logger = logging.getLogger("api")

router = APIRouter(prefix="", tags=["PPT"])

# ---------- Schemas ----------

class PPTInitialGenRequest(BaseModel):
    uuid: str
    gen_id: str
    language: str = Field(..., pattern="^(English|Arabic)$", description="English or Arabic")
    user_preference: str = Field("", description="Free text user preferences")

class PPTInitialGenResponse(BaseModel):
    status: str
    ppt_genid: str
    ppt_url: Optional[str]
    generated_content: str  

class RegenComment(BaseModel):
    comment1: str
    comment2: str

class PPTRegenRequest(BaseModel):
    uuid: str
    gen_id: str
    ppt_genid: str
    language: str = Field(..., pattern="^(English|Arabic)$", description="English or Arabic")
    regen_comments: List[RegenComment]

class PPTRegenResponse(BaseModel):
    status: str
    new_ppt_genid: str
    ppt_url: Optional[str]
    generated_content: str

# ---------- Endpoints ----------

@router.post("/ppt-initialgen", response_model=PPTInitialGenResponse)
async def ppt_initialgen(body: PPTInitialGenRequest):
    try:
        logger.info("Received /ppt-initialgen request")
        result = await run_initial_generation(
            uuid=body.uuid,
            gen_id=body.gen_id,
            language=body.language,
            user_preference=body.user_preference,
        )
        return PPTInitialGenResponse(
            status="success",
            ppt_genid=result["ppt_genid"],
            ppt_url=result["ppt_url"],
            generated_content=result["generated_content"],
        )
    except Exception as e:
        logger.exception("ppt-initialgen failed")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/ppt-regeneration", response_model=PPTRegenResponse)
async def ppt_regeneration(body: PPTRegenRequest):
    try:
        logger.info("Received /ppt-regeneration request")
        result = await run_regeneration(
            uuid=body.uuid,
            gen_id=body.gen_id,
            base_ppt_genid=body.ppt_genid,
            language=body.language,
            regen_comments=[c.model_dump() for c in body.regen_comments],
        )
        return PPTRegenResponse(
            status="success",
            new_ppt_genid=result["ppt_genid"],
            ppt_url=result["ppt_url"],
            generated_content=result["generated_content"],
        )
    except Exception as e:
        logger.exception("ppt-regeneration failed")
        raise HTTPException(status_code=500, detail=str(e))
