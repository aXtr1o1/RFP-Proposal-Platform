import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in .env file")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY must be set in .env file")

OPENAI_MODEL = "gpt-4o-mini"
MAX_OUTPUT_TOKENS = 16000

RFP_BUCKET = "rfp"
SUPPORTING_BUCKET = "supporting"
PPT_TEMPLATE_BUCKET = "ppt_template"
PPT_BUCKET = "ppt"
PDF_BUCKET = "pdf"
TABLE_NAME = "ppt_table"

CHARTS_DIR = "generated_charts"
TEMP_DIR = "temp_files"

os.makedirs(CHARTS_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)