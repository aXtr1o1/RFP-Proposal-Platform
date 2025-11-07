import os
import logging
from typing import Dict, List

from core.openai_service import get_json_from_stream
from core.supabase_service import (
    sb, PPT_TABLE,  
    insert_regen_row,
    upload_pptx,
    update_row_with_ppt,
)
from core.ppt_builder import json_to_pptx
from prompt.regeneration_prompt import build_regen_system_prompt, build_regen_user_prompt

logger = logging.getLogger("ppt_regeneration")

async def _fetch_base_generated_content(uuid: str, gen_id: str, ppt_genid: str) -> str:
    logger.info("Fetching base generated_content for regeneration…")
    res = sb.table(PPT_TABLE).select("generated_content").eq("uuid", uuid).eq("gen_id", gen_id).eq("ppt_genid", ppt_genid).single().execute()
    data = (res.data or {})
    base = data.get("generated_content")
    if not base:
        raise RuntimeError("Base generated_content not found")
    return base

async def run_regeneration(*, uuid: str, gen_id: str, base_ppt_genid: str, language: str, regen_comments: List[Dict]) -> Dict:
    try:
        logger.info("Regeneration started")

        # 1) pull base JSON
        base_json = await _fetch_base_generated_content(uuid, gen_id, base_ppt_genid)

        # 2) prompts
        system_prompt = build_regen_system_prompt(language)
        user_prompt = build_regen_user_prompt(base_json, regen_comments)

        # 3) OpenAI stream → JSON text
        regenerated_json_text = await get_json_from_stream(system_prompt, user_prompt)

        # 4) Append a new row with the new version
        new_ppt_genid = await insert_regen_row(
            uuid_str=uuid,
            gen_id=gen_id,
            language=language,
            regen_comments=regen_comments,
            generated_content=regenerated_json_text,
        )

        # 5) Build PPTX
        os.makedirs("outputs", exist_ok=True)
        pptx_path = f"outputs/{uuid}_{new_ppt_genid}.pptx"
        json_to_pptx(regenerated_json_text, pptx_path)

        # 6) Upload
        remote_key = f"{uuid}/{new_ppt_genid}.pptx"
        ppt_url = await upload_pptx(pptx_path, remote_key)

        # 7) Update row with proposal_ppt
        await update_row_with_ppt(uuid, gen_id, new_ppt_genid, ppt_url)

        logger.info("Regeneration completed")
        return {
            "ppt_genid": new_ppt_genid,
            "ppt_url": ppt_url,
            "generated_content": regenerated_json_text,
        }
    except Exception as e:
        logger.exception("run_regeneration failed")
        raise
