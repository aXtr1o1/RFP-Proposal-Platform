# backend/services/proposal_generation.py
import io
import os
import tempfile
from openai import OpenAI

from core.config import settings
from core.logger import get_logger
from core.utils import extract_json_array, short_kb, uuid_like

from prompts.initialgen_prompt import (
    system_prompts,
    build_task_instructions_with_config,
    build_language_block,
)

from services.ppt_engine import (
    analyze_template_layouts,
    build_ppt_from_slides,
    export_pdf_from_ppt_bytes,   
    convert_ppt_to_pdf,         
)



class OpenAIEngine:
    def __init__(self, logger=None):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.logger = logger or get_logger("openai")

    def upload_pdf(self, file_bytes: bytes, filename: str = "document.pdf") -> str:
        if not filename.lower().endswith(".pdf"):
            filename = f"{filename}.pdf"
        if not file_bytes.startswith(b"%PDF-"):
            self.logger.warning("upload appears not to be a PDF (missing %PDF- header)")
        file_obj = io.BytesIO(file_bytes)
        file_obj.name = filename
        result = self.client.files.create(file=file_obj, purpose="assistants")
        self.logger.info("files uploaded")
        return result.id

    def generate_slides(
        self,
        *,
        lang_block: str,
        rfp_id: str,
        sup_id: str,
        user_cfg_notes: str,
        system_prompts_text: str,
        task_instructions: str,
    ) -> str:
        """
        Streams tokens to terminal (stdout) while collecting final text.
        """
        self.logger.info("generating slides (streaming) ... started")
        response = self.client.responses.create(
            model=settings.OPENAI_MODEL,
            max_output_tokens=settings.MAX_OUTPUT_TOKENS,
            input=[{
                "role": "user",
                "content": [
                    {"type": "input_text", "text": lang_block},
                    {"type": "input_file", "file_id": rfp_id},
                    {"type": "input_file", "file_id": sup_id},
                    {"type": "input_text", "text": user_cfg_notes},
                    {"type": "input_text", "text": system_prompts_text},
                    {"type": "input_text", "text": task_instructions},
                ],
            }],
            stream=True,
        )

        print("\n" + "=" * 80)
        print("OPENAI STREAM (slides JSON):\n")
        chunks: list[str] = []
        for ev in response:
            ev_type = getattr(ev, "type", "")
            if ev_type == "response.output_text.delta":
                delta = getattr(ev, "delta", "")
                if delta:
                    chunks.append(delta)
                    print(delta, end="", flush=True)  
            elif ev_type == "response.error":
                err = getattr(ev, "error", "OpenAI stream error")
                print(f"\n\n[ERROR] {err}\n", flush=True)
                self.logger.error(f"OpenAI error: {err}")
                raise RuntimeError(str(err))
            elif ev_type == "response.completed":
                break

        print("\n" + "=" * 80 + "\n")
        raw = "".join(chunks)
        self.logger.info(f"slide content generated (chars={len(raw)})")
        return raw


class ProposalGenerator:
    def __init__(self, supabase, openai_engine: OpenAIEngine, cache, logger=None):
        self.supabase = supabase
        self.openai = openai_engine
        self.cache = cache
        self.logger = logger or get_logger("proposal")

    def run_initial_generation(
        self,
        uuid: str,
        template_key: str,
        user_preference: str,
        language: str,
    ):
        # Fetch record
        self.logger.info("fetching record by uuid...")
        record = self.supabase.fetch_record_by_uuid(uuid)
        if not record:
            self.logger.error("record not found")
            raise ValueError("Record not found")
        self.logger.info("record found")

        # Resolve storage keys
        rfp_key = record["rfp_file"].split(f"{settings.RFP_BUCKET}/")[-1]
        sup_key = record["supporting_file"].split(f"{settings.SUPPORTING_BUCKET}/")[-1]
        tpl_path = f"{template_key}/Template.pptx"

        # Download inputs
        rfp_bytes = self.supabase.download_file(settings.RFP_BUCKET, rfp_key)
        sup_bytes = self.supabase.download_file(settings.SUPPORTING_BUCKET, sup_key)
        tpl_bytes = self.supabase.download_file(settings.PPT_TEMPLATE_BUCKET, tpl_path)
        self.logger.info(
            "downloads complete "
            f"(rfp={short_kb(len(rfp_bytes))} KB, supporting={short_kb(len(sup_bytes))} KB, template={short_kb(len(tpl_bytes))} KB)"
        )

        # Analyze template
        _, layout_details = analyze_template_layouts(tpl_bytes)

        # Build prompts
        lang_block = build_language_block(language)
        task_instructions = build_task_instructions_with_config(
            language=language,
            user_config_json="{}",
            template_analysis_text="(omitted in logs)",
            layout_details=layout_details,
            user_config_notes=user_preference or "",
        )

        # OpenAI: upload and generate
        rfp_id = self.openai.upload_pdf(rfp_bytes, filename="rfp.pdf")
        sup_id = self.openai.upload_pdf(sup_bytes, filename="supporting.pdf")
        raw_json = self.openai.generate_slides(
            lang_block=lang_block,
            rfp_id=rfp_id,
            sup_id=sup_id,
            user_cfg_notes=user_preference or "",
            system_prompts_text=system_prompts,
            task_instructions=task_instructions,
        )

        # Parse and build PPT (bytes)
        slides = extract_json_array(raw_json)
        self.logger.info("building PowerPoint...")
        ppt_bytes = build_ppt_from_slides(slides, tpl_bytes, self.cache)
        self.logger.info(f"PPT ready in memory (size={short_kb(len(ppt_bytes))} KB)")
        self.logger.info("exporting PDF via LibreOffice...")
        pdf_bytes = None
        if os.name == "nt":
            with tempfile.TemporaryDirectory() as tdir:
                ppt_path = os.path.join(tdir, "deck.pptx")
                pdf_path = os.path.join(tdir, "deck.pdf")
                with open(ppt_path, "wb") as f:
                    f.write(ppt_bytes)
                final_pdf_path = convert_ppt_to_pdf(ppt_path, pdf_path)
                if final_pdf_path and os.path.exists(final_pdf_path):
                    with open(final_pdf_path, "rb") as f:
                        pdf_bytes = f.read()
        else:
            pdf_bytes = export_pdf_from_ppt_bytes(ppt_bytes)

        if pdf_bytes:
            self.logger.info(f"PDF ready in memory (size={short_kb(len(pdf_bytes))} KB)")
        else:
            self.logger.warning("PDF export skipped (LibreOffice not found or conversion failed)")

        # Upload outputs 
        gen_id = uuid_like("gen")
        ppt_url = self.supabase.upload_bytes(
            settings.PPT_BUCKET,
            f"{gen_id}.pptx",
            ppt_bytes,
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )
        pdf_url = (
            self.supabase.upload_bytes(settings.PDF_BUCKET, f"{gen_id}.pdf", pdf_bytes, "application/pdf")
            if pdf_bytes else None
        )
        self.logger.info(f"outputs uploaded (ppt_url={ppt_url}, pdf_url={pdf_url})")

        # Update DB
        self.supabase.update_record_by_uuid(
            uuid,
            {
                "gen_id": gen_id,
                "generated_ppt": ppt_url,
                "generated_pdf": pdf_url,
                "general_preference": user_preference,
            },
        )
        self.cache.cleanup()

        return {"gen_id": gen_id, "ppt_url": ppt_url, "pdf_url": pdf_url}
