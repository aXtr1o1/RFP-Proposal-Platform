import os
import logging
import uuid
from typing import Any, Dict, Optional
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()
logger = logging.getLogger("supabase_service")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
WORD_TABLE = os.getenv("WORD_TABLE", "word_gen")
PPT_TABLE  = os.getenv("PPT_TABLE", "ppt_gen")
PPT_BUCKET = os.getenv("PPT_BUCKET", "ppt")  

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Supabase URL/KEY missing")

sb: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------- word side ----------

async def fetch_word_markdown(uuid_str: str, gen_id: str) -> str:
    """
    Reads 'generated_markdown' from word_gen by uuid/gen_id
    """
    try:
        logger.info("Fetching word markdown from word_gen…")
        res = sb.table(WORD_TABLE).select("generated_markdown").eq("uuid", uuid_str).eq("gen_id", gen_id).single().execute()
        data = (res.data or {})
        md = data.get("generated_markdown")
        if not md:
            raise RuntimeError("generated_markdown not found in word_gen")
        return md
    except Exception as e:
        logger.exception("fetch_word_markdown failed")
        raise

# ---------- ppt side ----------

async def insert_initial_row(uuid_str: str, gen_id: str, language: str, user_pref: str, generated_content: str) -> str:
    """
    Inserts a new row (version) into ppt_gen; returns newly created ppt_genid (uuid).
    """
    try:
        logger.info("Inserting new version row into ppt_gen…")
        new_ppt_genid = str(uuid.uuid4())
        payload = {
            "uuid": uuid_str,
            "gen_id": gen_id,
            "ppt_genid": new_ppt_genid,
            "general_preference": user_pref,
            "generated_content": generated_content,  
            "ppt_template": None,
            "proposal_ppt": None,
            "regen_comments": None,
        }
        sb.table(PPT_TABLE).insert(payload).execute()
        return new_ppt_genid
    except Exception as e:
        logger.exception("insert_initial_row failed")
        raise

async def insert_regen_row(uuid_str: str, gen_id: str, language: str, regen_comments: list, generated_content: str) -> str:
    """
    Appends a new row for regeneration versioning. Returns ppt_genid.
    """
    try:
        logger.info("Appending regeneration row into ppt_gen…")
        new_ppt_genid = str(uuid.uuid4())
        payload = {
            "uuid": uuid_str,
            "gen_id": gen_id,
            "ppt_genid": new_ppt_genid,
            "general_preference": None,
            "generated_content": generated_content, 
            "ppt_template": None,
            "proposal_ppt": None,
            "regen_comments": regen_comments,  
        }
        sb.table(PPT_TABLE).insert(payload).execute()
        return new_ppt_genid
    except Exception as e:
        logger.exception("insert_regen_row failed")
        raise

async def upload_pptx(local_path: str, remote_key: str) -> str:
    """
    Uploads PPTX to 'ppt' bucket; returns public URL
    """
    try:
        logger.info(f"Uploading PPTX to bucket={PPT_BUCKET}, key={remote_key}")
        with open(local_path, "rb") as f:
            # Allow overwrite: if key exists, remove first
            try:
                sb.storage.from_(PPT_BUCKET).remove([remote_key])
            except Exception:
                pass
            sb.storage.from_(PPT_BUCKET).upload(remote_key, f, {
                "content-type": "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            })
        url = sb.storage.from_(PPT_BUCKET).get_public_url(remote_key)
        logger.info(f"Uploaded: {url}")
        return url
    except Exception as e:
        logger.exception("upload_pptx failed")
        raise

async def update_row_with_ppt(uuid_str: str, gen_id: str, ppt_genid: str, ppt_url: str):
    try:
        logger.info("Updating proposal_ppt in ppt_gen…")
        sb.table(PPT_TABLE).update({"proposal_ppt": ppt_url}).eq("uuid", uuid_str).eq("gen_id", gen_id).eq("ppt_genid", ppt_genid).execute()
    except Exception as e:
        logger.exception("update_row_with_ppt failed")
        raise
