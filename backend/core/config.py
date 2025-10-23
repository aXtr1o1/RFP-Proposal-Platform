import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

class Settings:
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    MAX_OUTPUT_TOKENS = int(os.getenv("MAX_OUTPUT_TOKENS", 18000))

    RFP_BUCKET = "rfp"
    SUPPORTING_BUCKET = "supporting"
    PPT_TEMPLATE_BUCKET = "ppt_template"
    PPT_BUCKET = "ppt"
    PDF_BUCKET = "pdf"
    TABLE_NAME = "ppt_table"

    OUTPUT_CHARTS_DIR = Path("output/charts")
    OUTPUT_CHARTS_DIR.mkdir(parents=True, exist_ok=True)

settings = Settings()
