import os
import json
import logging
from typing import Dict

from core.openai_service import get_json_from_stream
from core.supabase_service import (
    fetch_word_markdown,
    insert_initial_row,
    upload_pptx,
    update_row_with_ppt,
)
from core.ppt_builder import json_to_pptx
from prompt.generation_prompt import build_system_prompt, build_user_prompt

logger = logging.getLogger("ppt_generation")

# a light, static template summary; you can make it dynamic later
TEMPLATE_SUMMARY = {
    "path": "ppt_template/general",
    "layouts": [
        {"index": 0, "name": "Title", "has_title": True, "has_subtitle": True, "content_slots": 1},
        {"index": 1, "name": "Content", "has_title": True, "content_slots": 1},
        {"index": 2, "name": "Two Column", "has_title": True, "content_slots": 2},
        {"index": 3, "name": "Chart", "has_title": True, "content_slots": 1},
    ],
}

async def run_initial_generation(*, uuid: str, gen_id: str, language: str, user_preference: str) -> Dict:
    try:
        logger.info("Initial generation started")

        # 1) fetch markdown
        markdown = await fetch_word_markdown(uuid, gen_id)

        # 2) prompts
        system_prompt = build_system_prompt(language, TEMPLATE_SUMMARY)
        user_prompt = build_user_prompt(language, markdown, user_preference)

        # 3) OpenAI stream → JSON text
        generated_json_text = await get_json_from_stream(system_prompt, user_prompt)

        # 4) Save version (insert row) with generated_content
        ppt_genid = await insert_initial_row(
            uuid_str=uuid,
            gen_id=gen_id,
            language=language,
            user_pref=user_preference,
            generated_content=generated_json_text,
        )

        # 5) Build PPTX
        os.makedirs("outputs", exist_ok=True)
        pptx_path = f"outputs/{uuid}_{ppt_genid}.pptx"
        json_to_pptx(generated_json_text, pptx_path)

        # 6) Upload to bucket "ppt/uuid/ppt_genid.pptx"
        remote_key = f"{uuid}/{ppt_genid}.pptx"
        ppt_url = await upload_pptx(pptx_path, remote_key)

        # 7) Update row with proposal_ppt url
        await update_row_with_ppt(uuid, gen_id, ppt_genid, ppt_url)

        logger.info("Initial generation completed")
        return {
            "ppt_genid": ppt_genid,
            "ppt_url": ppt_url,
            "generated_content": generated_json_text,
        }
    except Exception as e:
        logger.exception("run_initial_generation failed")
        raise
