import os
import logging
from typing import Dict, Optional
from supabase import create_client, Client
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(), override=False) 

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_KEY are required")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
DATA_TABLE = os.getenv("SUPABASE_DATA_TABLE", "Data_Table")
BUCKET = os.getenv("SUPABASE_BUCKET", "pdf")

def clean_supabase_url(url: str) -> str:
    return (url or "").split("?")[0]

def get_pdf_urls_by_uuid(uuid: str) -> Optional[Dict[str, str]]:
    try:
        res = supabase.table(DATA_TABLE).select(
            "uuid, RFP_Files, Supporting_Files"
        ).eq("uuid", uuid).maybe_single().execute()

        if not res.data:
            logger.warning(f"Data_Table row not found for uuid={uuid}")
            return None

        raw_rfp = res.data.get("RFP_Files")
        raw_sup = res.data.get("Supporting_Files")
        rfp_url = clean_supabase_url(raw_rfp)
        supporting_url = clean_supabase_url(raw_sup)
        logger.info(f"Data_Table urls for {uuid}: rfp={rfp_url}, sup={supporting_url}")
        return {"rfp_url": rfp_url, "supporting_url": supporting_url}
    except Exception as e:
        logger.exception("get_pdf_urls_by_uuid failed")
        return None

def upload_file_to_storage(file_content: bytes, file_path: str, filename: str, bucket_name: str = BUCKET) -> str:
    content_type = (
        "application/pdf" if filename.endswith(".pdf")
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if filename.endswith(".docx") else "application/octet-stream"
    )
    supabase.storage.from_(bucket_name).upload(
        file_path, file_content, {"content-type": content_type, "x-upsert": "true"}
    )
    url = supabase.storage.from_(bucket_name).get_public_url(file_path)
    url = clean_supabase_url(url)
    logger.info(f"Uploaded {filename} -> {url}")
    return url

def update_proposal_in_data_table(uuid: str, pdf_url: str, word_url: str) -> bool:
    """
    Update proposal (JSON), Proposal_pdf, Proposal_word.
    """
    payload_full = {
        "Proposal_pdf": pdf_url,
        "Proposal_word": word_url,
    }
    payload_fallback = {
        "Proposal_pdf": pdf_url,
        "Proposal_word": word_url,
    }
    try:
        supabase.table(DATA_TABLE).update(payload_full).eq("uuid", uuid).execute()
        logger.info(f"Updated {DATA_TABLE} with proposal/pdf/word for uuid={uuid}")
        return True
    except Exception as e:
        msg = str(e)
        logger.error(f"update_proposal_in_data_table (full) failed: {msg}")
        if "proposal" in msg.lower() and "not find" in msg.lower():
            try:
                supabase.table(DATA_TABLE).update(payload_fallback).eq("uuid", uuid).execute()
                logger.info(f"Updated {DATA_TABLE} with pdf/word only for uuid={uuid} (no proposal column)")
                return True
            except Exception:
                logger.exception("update_proposal_in_data_table (fallback) failed")
                return False
        return False
