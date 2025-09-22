import os
from supabase import create_client
import dotenv
dotenv.load_dotenv()
import logging

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
    print(resp)


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
