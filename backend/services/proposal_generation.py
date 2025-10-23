import io
from openai import OpenAI
from core.logger import get_logger
from core.config import settings
from core.utils import extract_json_array, uuid_like
from prompts.initialgen_prompt import (
    system_prompts,
    build_task_instructions_with_config,
    build_language_block,
)
from services.ppt_engine import (
    analyze_template_layouts,
    build_ppt_from_slides,
    export_pdf_from_ppt,
)
from services.supabase_service import supabase_service

logger = get_logger("proposal")


class OpenAIEngine:
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)

    def upload_pdf(self, file_bytes: bytes, filename: str = "doc.pdf") -> str:
        """
        Uploads a PDF to OpenAI as a file usable by the Responses API.
        """
        # BytesIO without a name is OK for OpenAI's Python client
        file_obj = io.BytesIO(file_bytes)
        result = self.client.files.create(file=file_obj, purpose="assistants")
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
        Calls the Responses API following the required content layout, streaming the output
        and concatenating deltas into a single JSON string.
        """
        response = self.client.responses.create(
            model=settings.OPENAI_MODEL,
            max_output_tokens=settings.MAX_OUTPUT_TOKENS,
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": lang_block},
                        {"type": "input_file", "file_id": rfp_id},
                        {"type": "input_file", "file_id": sup_id},
                        {"type": "input_text", "text": user_cfg_notes},
                        {"type": "input_text", "text": system_prompts_text},
                        {"type": "input_text", "text": task_instructions},
                    ],
                }
            ],
            stream=True,
        )

        chunks: list[str] = []
        for ev in response:
            if getattr(ev, "type", "") == "response.output_text.delta":
                delta = getattr(ev, "delta", "")
                if delta:
                    chunks.append(delta)

            elif getattr(ev, "type", "") == "response.error":
                # fail fast on API stream errors
                err = getattr(ev, "error", "OpenAI stream error")
                logger.error(f"OpenAI error: {err}")
                raise RuntimeError(str(err))

            elif getattr(ev, "type", "") == "response.completed":
                break

        return "".join(chunks)


class ProposalGenerator:
    def __init__(self, supabase, openai_engine: OpenAIEngine, cache):
        self.supabase = supabase
        self.openai = openai_engine
        self.cache = cache

    def run_initial_generation(
        self,
        uuid: str,
        template_key: str,
        user_preference: str,
        language: str,
    ):
        """
        Orchestrates the whole flow in-memory:
        - download inputs
        - analyze template
        - build prompts
        - call OpenAI Responses API
        - build PPT/PDF in-memory
        - upload outputs
        - update DB and cleanup
        """
        gen_id = uuid_like("gen")

        record = self.supabase.fetch_record_by_uuid(uuid)
        if not record:
            raise ValueError("Record not found")

        # Resolve storage keys
        rfp_key = record["rfp_file"].split(f"{settings.RFP_BUCKET}/")[-1]
        sup_key = record["supporting_file"].split(f"{settings.SUPPORTING_BUCKET}/")[-1]
        tpl_path = f"{template_key}/Template.pptx"

        # Download as raw bytes
        rfp_bytes = self.supabase.download_file(settings.RFP_BUCKET, rfp_key)
        sup_bytes = self.supabase.download_file(settings.SUPPORTING_BUCKET, sup_key)
        tpl_bytes = self.supabase.download_file(settings.PPT_TEMPLATE_BUCKET, tpl_path)

        # Analyze template for layout guidance
        tpl_analysis_text, layout_details = analyze_template_layouts(tpl_bytes)

        # Build prompt blocks (language + system + task)
        lang_block = build_language_block(language)
        # Keep user_preference as "notes" (free-form), and pass minimal user_config_json (can be '{}' or a real JSON string)
        task_instructions = build_task_instructions_with_config(
            language=language,
            user_config_json="{}",                    # adjust if you have a real JSON string
            template_analysis_text=tpl_analysis_text,
            layout_details=layout_details,
            user_config_notes=user_preference or "",
        )

        # Upload RFP + Supporting PDFs to OpenAI
        rfp_id = self.openai.upload_pdf(rfp_bytes)
        sup_id = self.openai.upload_pdf(sup_bytes)

        # Generate slides JSON (STRICT array)
        raw_json = self.openai.generate_slides(
            lang_block=lang_block,
            rfp_id=rfp_id,
            sup_id=sup_id,
            user_cfg_notes=user_preference or "",
            system_prompts_text=system_prompts,
            task_instructions=task_instructions,
        )

        # Parse array
        slides = extract_json_array(raw_json)

        # Build PPT and PDF in-memory
        ppt_bytes = build_ppt_from_slides(slides, tpl_bytes, self.cache)
        pdf_bytes = export_pdf_from_ppt(ppt_bytes)

        # Upload outputs
        ppt_url = self.supabase.upload_bytes(
            settings.PPT_BUCKET,
            f"{gen_id}.pptx",
            ppt_bytes,
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )
        pdf_url = (
            self.supabase.upload_bytes(
                settings.PDF_BUCKET,
                f"{gen_id}.pdf",
                pdf_bytes,
                "application/pdf",
            )
            if pdf_bytes
            else None
        )

        # Persist and cleanup
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
