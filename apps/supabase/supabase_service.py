import os
from typing import Any, Dict
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from supabase import create_client
import dotenv
dotenv.load_dotenv()
import logging
import httpx

logger = logging.getLogger(__name__)
# Load credentials
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY) # type: ignore



def upload_and_save_pdf(file_path, file_name,uuid, pdf_share_url):

    bucket_name = "pdf"
    with open(file_path, "rb") as f:
        data = f.read()


    with open(file_path, "rb") as f:
        data = f.read()

    resp = supabase.storage.from_("pdf").upload(
        file_name,
        data,
        {"content-type": "application/pdf", "x-upsert": "true"}
    )



    pdf_supabase_url = supabase.storage.from_(bucket_name).get_public_url(file_name)
    logger.info("✅ Public URL:", pdf_supabase_url)
    logger.info("✅ Uploaded to Supabase bucket:", file_name)


    payload = {
        "uuid": uuid,
        "pdf_share_url": pdf_share_url,
        "pdf_final_url": pdf_supabase_url,
    }
    resp = supabase.table("pdf_table").insert(payload).execute()
    logger.info(f"✅ Row inserted into pdf_table: {resp.data}")
    return pdf_supabase_url




def upload_and_save_files(word_file_path, word_file_name, pdf_file_path, pdf_file_name, uuid):

    pdf_bucket = "pdf"
    word_bucket = "word"

    # --- Upload Word File ---
    with open(word_file_path, "rb") as f:
        word_data = f.read()

    resp_word = supabase.storage.from_(word_bucket).upload(
        word_file_name,
        word_data,
        {"content-type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "x-upsert": "true"}
    )


    word_supabase_url = supabase.storage.from_(word_bucket).get_public_url(word_file_name)
    logger.info(f"✅ Public Word URL: {word_supabase_url}")
    logger.info(f"✅ Uploaded to Supabase bucket: {word_file_name}")

    # --- Upload PDF File ---
    with open(pdf_file_path, "rb") as f:
        pdf_data = f.read()

    resp_pdf = supabase.storage.from_(pdf_bucket).upload(
        pdf_file_name,
        pdf_data,
        {"content-type": "application/pdf", "x-upsert": "true"}
    )


    pdf_supabase_url = supabase.storage.from_(pdf_bucket).get_public_url(pdf_file_name)
    logger.info(f"✅ Public PDF URL: {pdf_supabase_url}")
    logger.info(f"✅ Uploaded to Supabase bucket: {pdf_file_name}")

    payload = {
        "uuid": uuid,
        "Proposal_pdf": pdf_supabase_url,
        "Proposal_word": word_supabase_url,
    }
    resp = supabase.table("Data_Table").insert(payload).execute()
    logger.info(f"✅ Row inserted into Data_Table: {resp.data}")

    return {"pdf_url": pdf_supabase_url, "word_url": word_supabase_url}



def get_comments_base(uuid: str)-> Dict[str, Any]:
    try:
        resp = (
            supabase
            .table("proposal_comments")
            .select("selected_content, comments, proposal_url, created_at")
            .eq("uuid", uuid)
            .execute()
        )
        logger.info(f"got the resp from get_comments_base da ")

        rows = resp.data or []

        logger.info(f"this is the row paathuko : {rows}")
        if not rows:
            resp =(supabase.table("Data_Table").select("Proposal_pdf").eq("uuid",uuid).order("created_at", desc=False).execute())
            proposal_url = resp.data[0].get("Proposal_pdf")
            payload: Dict[str, Any] = {
                "uuid": uuid,
                "proposal_url": proposal_url,
                "items": [
                    {
                        "selected_content": "None",
                        "comment": "None"
                    }
  
                ],
                "count": 1
            }

            logger.info(f"this is the proposal url 1 from the supabase : {proposal_url}")
            return payload
        

        else:
            urls = {r.get("proposal_url") for r in rows if r.get("proposal_url")}
            proposal_url = next(iter(urls), None)

            payload: Dict[str, Any] = {
                "uuid": uuid,
                "proposal_url": proposal_url,
                "items": [
                    {
                        "selected_content": r.get("selected_content", ""),
                        "comment": r.get("comments", "")
                    }
                    for r in rows
                ],
                "count": len(rows)
            }

            logger.info(f"this is the proposal url 2 from the supabase : {proposal_url}")
            return payload

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Regenerate failed: {e!s}")
    





