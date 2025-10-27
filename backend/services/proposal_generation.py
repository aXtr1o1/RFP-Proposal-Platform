import io
import os
import tempfile
from typing import Dict, List

from openai import OpenAI
from core.config import settings
from core.logger import get_logger
from core.utils import extract_json_array, short_kb, uuid_like
from prompts.initialgen_prompt import (
    build_system_prompt,                 
    build_task_instructions_with_config,
    build_language_block,
)
from services.ppt_engine import (
    analyze_template_layouts,
    build_ppt_from_slides,
    export_pdf_from_ppt_bytes,
    convert_ppt_to_pdf,
)

def _placeholder_count(layout_details: Dict[int, Dict], layout_index: int) -> int:
    det = layout_details.get(int(layout_index) if layout_index is not None else -1, {})
    return len(det.get("content_indices", [])) if det else 0

def _normalize_slides_to_template(slides: List[dict], layout_details: Dict[int, Dict]) -> List[dict]:
    """
    Force each slide.content to match the number of content placeholders in the chosen layout_index.
    """
    norm = []

    for s in slides:
        lt = (s.get("layout_type") or "").upper()
        li = int(s.get("layout_index", 0))
        content = s.get("content", [])
        flat: List[str] = []
        if isinstance(content, list):
            for seg in content:
                if isinstance(seg, list):
                    flat.extend([str(x) for x in seg])
                elif seg is not None:
                    flat.append(str(seg))
        elif content:
            flat = [str(content)]

        slots = _placeholder_count(layout_details, li)

        if lt == "TITLE_ONLY":
            s["content"] = []

        elif lt == "SINGLE_CONTENT":
            s["content"] = [flat] if flat else [[]]

        elif lt == "TWO_CONTENT":
            buckets = [[], []]
            for i, x in enumerate(flat):
                buckets[i % 2].append(x)
            s["content"] = buckets

        elif lt == "CHART":
            s["content"] = [flat] if flat else []

        else:
            if slots <= 0:
                s["content"] = []
            else:
                buckets = [[] for _ in range(slots)]
                for i, x in enumerate(flat):
                    buckets[i % slots].append(x)
                s["content"] = buckets

        norm.append(s)

    return norm


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
        system_prompt_text: str,
        lang_block: str,
        rfp_id: str,
        sup_id: str,
        user_cfg_notes: str,
        task_instructions: str,
    ) -> str:
        """
        Streams tokens to stdout while collecting final text.
        """
        self.logger.info("generating slides (streaming) ... started")

        response = self.client.responses.create(
            model=settings.OPENAI_MODEL,
            max_output_tokens=settings.MAX_OUTPUT_TOKENS,
            input=[
                {"role": "system", "content": [{"type": "input_text", "text": system_prompt_text}]},
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": lang_block},
                        {"type": "input_file", "file_id": rfp_id},
                        {"type": "input_file", "file_id": sup_id},
                        {"type": "input_text", "text": user_cfg_notes or ""},
                        {"type": "input_text", "text": task_instructions},
                    ],
                },
            ],
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
        template_analysis_text, layout_details = analyze_template_layouts(tpl_bytes)

        # Build prompts
        lang_block = build_language_block(language)
        system_prompt_text = build_system_prompt(
            language=language,
            template_analysis_text=template_analysis_text,
            layout_details=layout_details,
        )
        task_instructions = build_task_instructions_with_config(
            language=language,
            user_config_json="{}",
            template_analysis_text=template_analysis_text,
            layout_details=layout_details,
            user_config_notes=user_preference or "",
            template_overview_for_order=None,  
        )
        
        # OpenAI: upload & generate
        rfp_id = self.openai.upload_pdf(rfp_bytes, filename="rfp.pdf")
        sup_id = self.openai.upload_pdf(sup_bytes, filename="supporting.pdf")
        
        raw_json = self.openai.generate_slides(
            system_prompt_text=system_prompt_text,
            lang_block=lang_block,
            rfp_id=rfp_id,
            sup_id=sup_id,
            user_cfg_notes=user_preference or "",
            task_instructions=task_instructions,
        )
        
        # Parse JSON
        slides = extract_json_array(raw_json)
        slides = _normalize_slides_to_template(slides, layout_details)

        # Build PPT
        self.logger.info("building PowerPoint...")
        ppt_bytes = build_ppt_from_slides(slides, tpl_bytes, self.cache)
        self.logger.info(f"PPT ready in memory (size={short_kb(len(ppt_bytes))} KB)")
        
        # Export PDF if available
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
        
        # Get template URL
        template_url = self.supabase.client.storage.from_(settings.PPT_TEMPLATE_BUCKET).get_public_url(
            f"{template_key}/Template.pptx"
        )
        self.logger.info("updating record with new generation")
        
        self.supabase.update_record_by_uuid(
            uuid,
            {
                "gen_id": gen_id,
                "ppt_template": template_url,
                "generated_ppt": ppt_url,
                "generated_pdf": pdf_url,
                "generated_json": slides,
                "general_preference": user_preference,
            },
        )
        
        self.cache.cleanup()
        return {"gen_id": gen_id, "ppt_url": ppt_url, "pdf_url": pdf_url}
