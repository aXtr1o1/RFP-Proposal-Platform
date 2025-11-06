import os
import logging
from typing import Dict, Optional, List
from supabase import create_client, Client
from dotenv import load_dotenv, find_dotenv
import uuid as uuid_lib

load_dotenv(find_dotenv(), override=True)
logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_KEY are required")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

WORD_GEN_TABLE = os.getenv("SUPABASE_WORD_GEN_TABLE", "word_gen")
PPT_GEN_TABLE = os.getenv("SUPABASE_PPT_GEN_TABLE", "ppt_gen")
WORD_BUCKET = os.getenv("SUPABASE_WORD_BUCKET", "word")

def clean_supabase_url(url: str) -> str:
    """Remove query parameters from Supabase URL."""
    return (url or "").split("?")[0]


def get_uploaded_files(uuid: str) -> Optional[Dict[str, str]]:
    """
    Fetch most recent RFP and Supporting file URLs for a UUID from word_gen.
    """
    try:
        res = (
            supabase.table(WORD_GEN_TABLE)
            .select("uuid, rfp_files, supporting_files")
            .eq("uuid", uuid)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )

        if not res.data:
            logger.warning(f"{WORD_GEN_TABLE} row not found for uuid={uuid}")
            return None

        raw_rfp = res.data[0].get("rfp_files")
        raw_sup = res.data[0].get("supporting_files")
        rfp_url = clean_supabase_url(raw_rfp)
        supporting_url = clean_supabase_url(raw_sup)
        logger.info(f"Fetched files for {uuid}: rfp={rfp_url}, sup={supporting_url}")
        return {"rfp_url": rfp_url, "supporting_url": supporting_url}
    except Exception:
        logger.exception(f"get_uploaded_files failed for uuid={uuid}")
        return None

get_pdf_urls_by_uuid = get_uploaded_files


def generate_new_gen_id() -> str:
    """Generate a new UUID for gen_id."""
    return str(uuid_lib.uuid4())


def get_latest_gen_id(uuid: str) -> Optional[str]:
    """Get the most recent gen_id for a given UUID."""
    try:
        res = (
            supabase.table(WORD_GEN_TABLE)
            .select("gen_id")
            .eq("uuid", uuid)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if not res.data:
            logger.warning(f"No gen_id found for uuid={uuid}")
            return None
        gen_id = res.data[0].get("gen_id")
        logger.info(f"Latest gen_id for uuid={uuid}: {gen_id}")
        return gen_id
    except Exception:
        logger.exception(f"get_latest_gen_id failed for uuid={uuid}")
        return None


def get_all_versions(uuid: str) -> Optional[List[Dict]]:
    """List all generations for a uuid (chronologically ascending)."""
    try:
        res = (
            supabase.table(WORD_GEN_TABLE)
            .select("gen_id, created_at, regen_comments, proposal, general_preference")
            .eq("uuid", uuid)
            .order("created_at", desc=False)
            .execute()
        )
        if not res.data:
            logger.warning(f"No versions found for uuid={uuid}")
            return None
        return res.data
    except Exception:
        logger.exception(f"get_all_versions failed for uuid={uuid}")
        return None

def ensure_ppt_gen_row(
    gen_id: str,
    uuid: Optional[str] = None,
) -> bool:
    """
    Ensure a parent row exists in ppt_gen for the given gen_id so the FK on word_gen passes.
    """
    try:
        exists = (
            supabase.table(PPT_GEN_TABLE)
            .select("gen_id")
            .eq("gen_id", gen_id)
            .limit(1)
            .execute()
        )
        if exists.data:
            return True

        payload = {
            "gen_id": gen_id,
            "ppt_genid": str(uuid_lib.uuid4()),  
        }
        if uuid is not None:
            payload["uuid"] = uuid

        supabase.table(PPT_GEN_TABLE).insert(payload).execute()
        logger.info(f"Inserted parent ppt_gen row for gen_id={gen_id}")
        return True
    except Exception:
        logger.exception(f"ensure_ppt_gen_row failed for gen_id={gen_id}")
        return False

def _fetch_latest_files_for_uuid(uuid: str) -> Optional[Dict[str, str]]:
    """Internal: get latest RFP/supporting for uuid to reuse in new gen rows."""
    try:
        res = (
            supabase.table(WORD_GEN_TABLE)
            .select("rfp_files, supporting_files")
            .eq("uuid", uuid)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if not res.data:
            return None
        return {
            "rfp_files": res.data[0].get("rfp_files"),
            "supporting_files": res.data[0].get("supporting_files"),
        }
    except Exception:
        logger.exception(f"_fetch_latest_files_for_uuid failed for uuid={uuid}")
        return None

def create_generation_row(
    uuid: str,
    new_gen_id: str,
    general_preference: Optional[str] = None
) -> bool:
    """
    Create a new initial generation row.
    """
    try:
        files = _fetch_latest_files_for_uuid(uuid)
        if not files:
            logger.error(
                f"Cannot create generation row: no existing files found for uuid={uuid}. "
                "Ensure an earlier row captured rfp_files/supporting_files."
            )
            return False
        if not ensure_ppt_gen_row(new_gen_id, uuid=uuid, general_preference=general_preference):
            logger.error(f"Cannot create generation row: failed to ensure ppt_gen for gen_id={new_gen_id}")
            return False

        payload = {
            "uuid": uuid,
            "gen_id": new_gen_id,
            "rfp_files": files["rfp_files"],
            "supporting_files": files["supporting_files"],
            "general_preference": general_preference,
        }
        supabase.table(WORD_GEN_TABLE).insert(payload).execute()
        logger.info(f"Created initial generation row for uuid={uuid}, gen_id={new_gen_id}")
        return True
    except Exception:
        logger.exception(f"create_generation_row failed for uuid={uuid}, gen_id={new_gen_id}")
        return False


def create_regeneration_row(
    uuid: str,
    new_gen_id: str,
    regen_comments: Optional[str],
    general_preference: Optional[str] = None
) -> bool:
    """Create a new row for regeneration (same uuid, new gen_id)."""
    try:
        files = _fetch_latest_files_for_uuid(uuid)
        if not files:
            logger.error(f"Cannot create regeneration row: no existing files found for uuid={uuid}")
            return False

        if not ensure_ppt_gen_row(
            new_gen_id,
            uuid=uuid,
        ):
            logger.error(f"Cannot create regeneration row: failed to ensure ppt_gen for gen_id={new_gen_id}")
            return False

        payload = {
            "uuid": uuid,
            "gen_id": new_gen_id,
            "rfp_files": files["rfp_files"],
            "supporting_files": files["supporting_files"],
            "regen_comments": regen_comments,
            "general_preference": general_preference,
        }
        supabase.table(WORD_GEN_TABLE).insert(payload).execute()
        logger.info(f"Created regeneration row for uuid={uuid}, gen_id={new_gen_id}")
        return True
    except Exception:
        logger.exception(f"create_regeneration_row failed for uuid={uuid}, gen_id={new_gen_id}")
        return False

def save_generated_markdown(uuid: str, gen_id: str, markdown: str) -> bool:
    """Save or overwrite markdown for a (uuid, gen_id)."""
    try:
        supabase.table(WORD_GEN_TABLE).update(
            {"generated_markdown": markdown}
        ).eq("uuid", uuid).eq("gen_id", gen_id).execute()
        logger.info(f"Saved markdown for uuid={uuid}, gen_id={gen_id}")
        return True
    except Exception:
        logger.exception(f"save_generated_markdown failed for uuid={uuid}, gen_id={gen_id}")
        return False


def get_markdown_content(uuid: str, gen_id: str) -> Optional[str]:
    """Fetch markdown for a specific (uuid, gen_id)."""
    try:
        res = (
            supabase.table(WORD_GEN_TABLE)
            .select("generated_markdown")
            .eq("uuid", uuid)
            .eq("gen_id", gen_id)
            .maybe_single()
            .execute()
        )
        if not res.data:
            logger.warning(f"No markdown found for uuid={uuid}, gen_id={gen_id}")
            return None
        return res.data.get("generated_markdown") or ""
    except Exception:
        logger.exception(f"get_markdown_content failed for uuid={uuid}, gen_id={gen_id}")
        return None


def get_generated_markdown(uuid: str, gen_id: Optional[str] = None) -> Optional[str]:
    """Convenience wrapper to fetch markdown for latest or specific gen."""
    try:
        active_gen_id = gen_id or get_latest_gen_id(uuid)
        if not active_gen_id:
            return None
        return get_markdown_content(uuid, active_gen_id)
    except Exception:
        logger.exception(f"get_generated_markdown failed for uuid={uuid}, gen_id={gen_id}")
        return None

def upload_word_and_update_table(
    uuid: str,
    gen_id: str,
    word_content: bytes,
    filename: str,
    generated_markdown: Optional[str] = None,
    general_preference: Optional[str] = None
) -> Optional[Dict[str, str]]:
    """
    Upload Word to storage and update word_gen row
    """
    try:
        file_path = f"{uuid}/{gen_id}/{filename}"
        content_type = (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            if filename.lower().endswith(".docx")
            else "application/octet-stream"
        )

        supabase.storage.from_(WORD_BUCKET).upload(
            file_path,
            word_content,
            {"content-type": content_type, "x-upsert": "true"},
        )
        word_url = clean_supabase_url(
            supabase.storage.from_(WORD_BUCKET).get_public_url(file_path)
        )
        logger.info(f"Uploaded Word: {word_url}")

        payload = {"proposal": word_url}
        if generated_markdown is not None:
            payload["generated_markdown"] = generated_markdown
        if general_preference is not None:
            payload["general_preference"] = general_preference

        supabase.table(WORD_GEN_TABLE).update(payload).eq("uuid", uuid).eq("gen_id", gen_id).execute()
        logger.info(f"Updated {WORD_GEN_TABLE} with proposal + markdown for uuid={uuid}, gen_id={gen_id}")
        return {"word_url": word_url}
    except Exception:
        logger.exception(f"upload_word_and_update_table failed for uuid={uuid}, gen_id={gen_id}")
        return None
