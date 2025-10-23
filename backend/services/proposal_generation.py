import io
from openai import OpenAI
from core.logger import get_logger
from core.config import settings
from core.utils import extract_json_array, uuid_like
from prompts.initialgen_prompt import build_system_prompt, build_task_prompt
from services.ppt_engine import analyze_template_layouts, build_ppt_from_slides, export_pdf_from_ppt
from services.supabase_service import supabase_service

logger = get_logger("proposal")

class OpenAIEngine:
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)

    def upload_pdf(self, file_bytes: bytes, filename="doc.pdf") -> str:
        file_obj = io.BytesIO(file_bytes)
        result = self.client.files.create(file=file_obj, purpose="assistants")
        return result.id

    def generate_slides(self, lang_block, rfp_id, sup_id, user_cfg_notes, system_prompts, task_instructions):
        response = self.client.responses.create(
            model=settings.OPENAI_MODEL,
            max_output_tokens=settings.MAX_OUTPUT_TOKENS,
            input=[{
                "role": "user",
                "content": [
                    {"type":"input_text","text":lang_block},
                    {"type":"input_file","file_id":rfp_id},
                    {"type":"input_file","file_id":sup_id},
                    {"type":"input_text","text":user_cfg_notes},
                    {"type":"input_text","text":system_prompts},
                    {"type":"input_text","text":task_instructions},
                ]
            }],
            stream=True,
        )
        chunks=[]
        for ev in response:
            if getattr(ev,"type","")== "response.output_text.delta":
                delta = getattr(ev,"delta","")
                if delta: chunks.append(delta)
        return "".join(chunks)

class ProposalGenerator:
    def __init__(self, supabase, openai_engine, cache):
        self.supabase = supabase
        self.openai = openai_engine
        self.cache = cache

    def run_initial_generation(self, uuid, template_key, user_preference, language):
        gen_id = uuid_like("gen")
        record = self.supabase.fetch_record_by_uuid(uuid)
        if not record:
            raise ValueError("Record not found")
        rfp_key = record["rfp_file"].split(f"{settings.RFP_BUCKET}/")[-1]
        sup_key = record["supporting_file"].split(f"{settings.SUPPORTING_BUCKET}/")[-1]
        tpl_path = f"{template_key}/Template.pptx"

        rfp_bytes = self.supabase.download_file(settings.RFP_BUCKET, rfp_key)
        sup_bytes = self.supabase.download_file(settings.SUPPORTING_BUCKET, sup_key)
        tpl_bytes = self.supabase.download_file(settings.PPT_TEMPLATE_BUCKET, tpl_path)

        tpl_analysis, layout_details = analyze_template_layouts(tpl_bytes)
        system_prompt = build_system_prompt(language, tpl_analysis, layout_details)
        task_prompt = build_task_prompt(user_preference, layout_details)

        rfp_id = self.openai.upload_pdf(rfp_bytes)
        sup_id = self.openai.upload_pdf(sup_bytes)
        raw_json = self.openai.generate_slides(language, rfp_id, sup_id, user_preference, system_prompt, task_prompt)
        slides = extract_json_array(raw_json)

        ppt_bytes = build_ppt_from_slides(slides, tpl_bytes, self.cache)
        pdf_bytes = export_pdf_from_ppt(ppt_bytes)

        ppt_url = self.supabase.upload_bytes(settings.PPT_BUCKET, f"{gen_id}.pptx", ppt_bytes, "application/vnd.openxmlformats-officedocument.presentationml.presentation")
        pdf_url = self.supabase.upload_bytes(settings.PDF_BUCKET, f"{gen_id}.pdf", pdf_bytes, "application/pdf") if pdf_bytes else None

        self.supabase.update_record_by_uuid(uuid,{
            "gen_id": gen_id,
            "generated_ppt": ppt_url,
            "generated_pdf": pdf_url,
            "general_preference": user_preference,
        })
        self.cache.cleanup()
        return {"gen_id": gen_id, "ppt_url": ppt_url, "pdf_url": pdf_url}
