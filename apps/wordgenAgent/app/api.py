import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Tuple, Optional, List
from pathlib import Path

import requests
import pythoncom
from docx2pdf import convert
from openai import OpenAI

from apps.wordgenAgent.app.wordcom import build_word_from_proposal
from apps.wordgenAgent.app.proposal_clean import proposal_cleaner
from apps.api.services.supabase_service import (
    upload_file_to_storage,
    update_proposal_in_data_table,
)
# All prompt text & model knobs live here (kept additive to user’s originals)
from apps.wordgenAgent.app import prompt as P

logger = logging.getLogger("wordgen_api")

SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "pdf")


# ----------------------------
# Small utilities (length etc.)
# ----------------------------
def _count_words_ar_en(text: str) -> int:
    return len([t for t in (text or "").split() if t.strip()])


def _short_sections(
    proposal: dict,
    min_words_per_section: int = 1000,   # your requirement: aim 1000–1500 words/section
    take: int = 8
) -> List[int]:
    secs = proposal.get("sections", [])
    scored = []
    for i, s in enumerate(secs):
        w = _count_words_ar_en(s.get("content", ""))
        scored.append((w, i))
    scored.sort(key=lambda x: x[0])  # shortest first
    return [idx for (w, idx) in scored if w < min_words_per_section][:take]


def _safe_json_loads(s: str) -> Optional[dict]:
    try:
        return json.loads(s)
    except Exception:
        return None


# ---------------------------------------
# Main class
# ---------------------------------------
class WordGenAPI:
    def __init__(self) -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required")
        self.client = OpenAI(api_key=api_key)

    @staticmethod
    def _clean_url(url: str) -> str:
        return (url or "").split("?")[0]

    def _download_two_pdfs(self, rfp_url: str, supporting_url: str) -> Tuple[bytes, bytes]:
        rfp_u = self._clean_url(rfp_url)
        sup_u = self._clean_url(supporting_url)
        logger.info(f"Downloading RFP: {rfp_u}")
        rfp_bytes = requests.get(rfp_u, timeout=60).content
        logger.info(f"Downloading Supporting: {sup_u}")
        sup_bytes = requests.get(sup_u, timeout=60).content
        return rfp_bytes, sup_bytes

    def _upload_pdf_urls_to_openai(self, rfp_url: str, supporting_url: str) -> Tuple[str, str]:
        rfp_bytes, sup_bytes = self._download_two_pdfs(rfp_url, supporting_url)
        rfpf = self.client.files.create(file=("RFP.pdf", rfp_bytes, "application/pdf"), purpose="user_data")
        supf = self.client.files.create(file=("Supporting.pdf", sup_bytes, "application/pdf"), purpose="user_data")
        logger.info(f"OpenAI files uploaded: rfp={rfpf.id}, supporting={supf.id}")
        return rfpf.id, supf.id

    def _convert_docx_to_pdf(self, docx_path: str) -> str:
        pdf_path = os.path.splitext(docx_path)[0] + ".pdf"
        pythoncom.CoInitialize()
        try:
            convert(docx_path, pdf_path)
            logger.info(f"Converted to PDF: {pdf_path}")
        finally:
            pythoncom.CoUninitialize()
        return pdf_path

    # -------------------------------
    # Stage 1: CompanyDigest (supporting file)
    # -------------------------------
    def _build_company_digest(self, supporting_file_id: str, max_out: int) -> dict:
        """Use the digest prompts (provided by you) to extract structured company info."""
        completion = self.client.responses.create(
            model=P.MODEL,
            temperature=min(P.TEMPERATURE, 0.25),
            max_output_tokens=max_out // 4,  # digest is compact
            input=[{
                "role": "user",
                "content": [
                    {"type": "input_file", "file_id": supporting_file_id},
                    {"type": "input_text", "text": P.COMPANY_DIGEST_SYSTEM},
                    {"type": "input_text", "text": P.COMPANY_DIGEST_SCHEMA},
                    {"type": "input_text", "text": P.build_company_digest_instructions()},
                ],
            }],
        )
        raw = completion.output_text or ""
        try:
            digest = proposal_cleaner(raw)
            if isinstance(digest, dict):
                return digest
        except Exception:
            pass
        # Minimal fallback
        return {"company_profile": {}, "capabilities": {}, "track_record": [], "contact": {}}

    @staticmethod
    def _detect_company_name(digest: dict) -> str:
        profile = digest.get("company_profile", {}) if isinstance(digest, dict) else {}
        return (
            profile.get("brand_name")
            or profile.get("legal_name")
            or "Your Company"
        )

    # --------------------------------
    # Stage 2b: Expand short sections
    # --------------------------------
    def _expand_short_sections(
        self,
        proposal_json: dict,
        short_idxs: List[int],
        language: str,
        rfp_id: str,
        sup_id: str,
        system_prompts: str,
        task_instructions: str,
        max_out: int,
    ) -> dict:
        if not short_idxs:
            return proposal_json
        try:
            payload = {
                "proposal": proposal_json,
                "expand_indices": short_idxs,
                "language": language,
            }
            expand_driver = (
                "You will receive a JSON proposal and a list of section indices that are too short. "
                "Return ONLY a JSON with the SAME schema but with those sections expanded to ~1000–1500 words each, "
                "grounded strictly in RFP_FILE, SUPPORTING_FILE, CompanyDigest and UserConfiguration. "
                "No extra sections. Prefer paragraphs; use 'points' only for true lists."
            )
            completion = self.client.responses.create(
                model=P.MODEL,
                temperature=0.5 if (language or "").lower() == "arabic" else P.TEMPERATURE,
                max_output_tokens=max_out,
                input=[{
                    "role": "user",
                    "content": [
                        {"type": "input_file", "file_id": rfp_id},
                        {"type": "input_file", "file_id": sup_id},
                        {"type": "input_text", "text": system_prompts},
                        {"type": "input_text", "text": task_instructions},
                        {"type": "input_text", "text": expand_driver},
                        {"type": "input_text", "text": f"JSON to expand:\n{json.dumps(payload, ensure_ascii=False)}"},
                        {"type": "input_text", "text": "Return ONE JSON object only."},
                    ],
                }],
            )
            raw = completion.output_text or ""
            expanded = proposal_cleaner(raw)
            base_secs = proposal_json.get("sections", [])
            new_secs = expanded.get("sections", [])
            for idx in short_idxs:
                if 0 <= idx < len(base_secs) and 0 <= idx < len(new_secs):
                    base_secs[idx] = new_secs[idx]
            proposal_json["sections"] = base_secs
            if expanded.get("title"):
                proposal_json["title"] = expanded["title"]
            return proposal_json
        except Exception as e:
            logger.warning(f"Top-up expansion failed: {e}")
            return proposal_json

    # --------------------------------
    # Public entry
    # --------------------------------
    def generate_complete_proposal(
        self,
        uuid: str,
        rfp_url: str,
        supporting_url: str,
        user_config: str = "",
        doc_config: Dict[str, Any] | None = None,
        language: str = "english",
        outline: str | None = None,
    ) -> Dict[str, Any]:

        start = datetime.now()
        logger.info(f"[initialgen] START for uuid={uuid}")

        # 0) Upload files
        rfp_id, sup_id = self._upload_pdf_urls_to_openai(rfp_url, supporting_url)

        # 1) Build CompanyDigest
        max_out = P.MAX_OUTPUT_TOKENS
        company_digest = self._build_company_digest(sup_id, max_out=max_out)
        company_name = self._detect_company_name(company_digest)

        # 2) Prepare task instructions (additive over original prompts)
        #    - user_config may be a string (free text) from the UI; keep verbatim
        #    - also pass a compact JSON if parseable
        user_cfg_obj = _safe_json_loads(user_config) if isinstance(user_config, str) else None
        user_cfg_compact = json.dumps(user_cfg_obj, ensure_ascii=False) if user_cfg_obj else "null"

        # labels for file roles shown in the prompt
        rfp_label = "RFP/BRD: requirements, evaluation criteria, project details, and timelines"
        supporting_label = "Supporting: company profile, portfolio, capabilities, certifications, differentiators"

        # Your original prompts (kept as-is)
        system_prompts = P.system_prompts
        company_digest_json = json.dumps(company_digest, ensure_ascii=False)
        additive_block = P.build_task_instructions_with_config(
            language=language,
            user_config_json=user_cfg_compact,
            rfp_label=rfp_label,
            supporting_label=supporting_label,
            company_digest_json=company_digest_json,
            user_config_notes=user_config if isinstance(user_config, str) else "",
        )

        # Final task block: your original + additive, plus the outline you already keep
        task_instructions = (
            P.task_instructions
            + "\nIMPORTANT: The proposal must follow this structure:\n"
            + (outline.strip() if outline and outline.strip() else P.PROPOSAL_TEMPLATE)
            + "\n"
            + additive_block
        )

        # 3) First pass generation
        logger.info("Calling OpenAI Responses API…")
        completion = self.client.responses.create(
            model=P.MODEL,
            temperature=0.5 if (language or "").lower() == "arabic" else P.TEMPERATURE,
            max_output_tokens=max_out,
            input=[{
                "role": "user",
                "content": [
                    {"type": "input_file", "file_id": rfp_id},
                    {"type": "input_file", "file_id": sup_id},
                    {"type": "input_text", "text": system_prompts},
                    {"type": "input_text", "text": task_instructions},
                ],
            }],
        )
        raw = completion.output_text or ""
        logger.info(f"OpenAI response chars: {len(raw)}")

        if "{" not in raw or '"sections"' not in raw:
            logger.warning("Model returned non-JSON; retrying with strict guardrail")
            strict_guard = (
                "Return ONLY a single valid JSON object matching the schema. "
                "Start with '{' and end with '}'. No explanations, no markdown, no extra text."
            )
            completion = self.client.responses.create(
                model=P.MODEL,
                temperature=0.5 if (language or "").lower() == "arabic" else P.TEMPERATURE,
                max_output_tokens=max_out,
                input=[{
                    "role": "user",
                    "content": [
                        {"type": "input_file", "file_id": rfp_id},
                        {"type": "input_file", "file_id": sup_id},
                        {"type": "input_text", "text": system_prompts},
                        {"type": "input_text", "text": task_instructions},
                        {"type": "input_text", "text": strict_guard},
                    ],
                }],
            )
            raw = completion.output_text or ""
            logger.info(f"[retry] OpenAI response chars: {len(raw)}")

        cleaned = proposal_cleaner(raw)

        # 4) Length top-up (expand shortest sections to ~1000–1500 words)
        try:
            min_words = 1000 
            short_idxs = _short_sections(cleaned, min_words_per_section=min_words, take=8)
            if short_idxs:
                logger.info(f"Expanding short sections (indices): {short_idxs}")
                cleaned = self._expand_short_sections(
                    proposal_json=cleaned,
                    short_idxs=short_idxs,
                    language=language,
                    rfp_id=rfp_id,
                    sup_id=sup_id,
                    system_prompts=system_prompts,
                    task_instructions=task_instructions,
                    max_out=max_out,
                )
        except Exception as e:
            logger.warning(f"Length analysis/expansion skipped: {e}")

        # 5) Build Word & PDF
        out_dir = Path("output")
        out_dir.mkdir(parents=True, exist_ok=True)
        docx_path = out_dir / f"{uuid}.docx"

        effective_cfg = doc_config or {}
        docx_abs = build_word_from_proposal(
            proposal_dict=cleaned,
            user_config=effective_cfg,
            output_path=str(docx_path),
            language=language,
            visible=False,
        )

        pdf_path = ""
        try:
            pdf_path = self._convert_docx_to_pdf(docx_abs)
        except Exception as e:
            logger.warning(f"PDF conversion failed: {e}")

        # 6) Upload to Supabase
        word_url = ""
        pdf_url = ""
        try:
            with open(docx_abs, "rb") as f:
                word_bytes = f.read()
            word_url = upload_file_to_storage(
                word_bytes, f"{uuid}/proposal.docx", "proposal.docx", bucket_name=SUPABASE_BUCKET
            )
        except Exception as e:
            logger.error(f"Upload DOCX failed: {e}")

        if pdf_path and os.path.exists(pdf_path):
            try:
                with open(pdf_path, "rb") as f:
                    pdf_bytes = f.read()
                pdf_url = upload_file_to_storage(
                    pdf_bytes, f"{uuid}/proposal.pdf", "proposal.pdf", bucket_name=SUPABASE_BUCKET
                )
            except Exception as e:
                logger.error(f"Upload PDF failed: {e}")

        # 7) Update table (resilient)
        updated = update_proposal_in_data_table(
            uuid,
            json.dumps(cleaned, ensure_ascii=False),
            pdf_url,
            word_url
        )

        elapsed = (datetime.now() - start).total_seconds()
        logger.info(f"[initialgen] DONE uuid={uuid} in {elapsed:.2f}s")

        return {
            "status": "success",
            "uuid": uuid,
            "proposal_content": cleaned,
            "word_file_path": docx_abs,
            "proposal_word_url": word_url,
            "proposal_pdf_url": pdf_url,
            "data_table_updated": updated,
            "processing_time": f"{elapsed:.2f}s",
            "model_used": P.MODEL,
            "language": language,
            "company_name": company_name,
        }
    
wordgen_api = WordGenAPI()
