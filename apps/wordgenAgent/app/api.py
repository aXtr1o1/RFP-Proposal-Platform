import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Tuple
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

from apps.wordgenAgent.app.prompt import (
    MODEL, TEMPERATURE, MAX_OUTPUT_TOKENS,
    COMPANY_DIGEST_SYSTEM, COMPANY_DIGEST_SCHEMA, build_company_digest_instructions,
    system_prompts, task_instructions, proposal_template, JSON_SCHEMA_TEXT,
    build_task_instructions_with_config,
)

logger = logging.getLogger("wordgen_api")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "pdf")


class WordGenAPI:
    def __init__(self) -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required")
        self.client = OpenAI(api_key=api_key)

    @staticmethod
    def _clean_url(url: str) -> str:
        return (url or "").split("?")[0]

    def _upload_pdf_urls_to_openai(self, rfp_url: str, supporting_url: str) -> Tuple[str, str]:
        rfp_u = self._clean_url(rfp_url)
        sup_u = self._clean_url(supporting_url)

        logger.info(f"Downloading RFP: {rfp_u}")
        rfp_bytes = requests.get(rfp_u, timeout=60).content

        logger.info(f"Downloading Supporting: {sup_u}")
        sup_bytes = requests.get(sup_u, timeout=60).content

        rfpf = self.client.files.create(
            file=("RFP.pdf", rfp_bytes, "application/pdf"),
            purpose="user_data"
        )
        supf = self.client.files.create(
            file=("Supporting.pdf", sup_bytes, "application/pdf"),
            purpose="user_data"
        )
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

    # ---------------- Arabic depth post-pass (only if needed) ----------------
    def _maybe_expand_arabic(self, json_text: str, rfp_file_id: str, supporting_file_id: str,
                             company_digest_text: str, user_cfg: str, language: str) -> str:
        """
        If Arabic content is too short, ask the model to expand each section to ~220–450 words,
        keeping the same JSON structure and grounding in inputs. Returns JSON text.
        """
        if (language or "").strip().lower() != "arabic":
            return json_text

        try:
            obj = json.loads(json_text)
        except Exception:
            return json_text

        # crude length check: if many sections < ~140 words, expand
        contents = [s.get("content", "") for s in obj.get("sections", []) if isinstance(s, dict)]
        short_count = sum(1 for c in contents if len(c.split()) < 140)
        if not contents or short_count < max(2, len(contents)//3):
            return json_text  # already rich enough

        expansion_prompt = (
            "Expand the following proposal JSON so that each major section's 'content' contains ~220–450 Arabic words "
            "of substantive, grounded material. Keep the same headings, points, and tables where appropriate. "
            "Do NOT invent facts; use only RFP_FILE, SUPPORTING_FILE, and CompanyDigest. Keep JSON-only output."
        )

        logger.info("Arabic content appears short; calling expansion pass…")
        completion = self.client.responses.create(
            model=MODEL,
            temperature=TEMPERATURE,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            input=[{
                "role": "user",
                "content": [
                    {"type": "input_file", "file_id": rfp_file_id},
                    {"type": "input_file", "file_id": supporting_file_id},
                    {"type": "input_text", "text": "CompanyDigest:\n" + company_digest_text},
                    {"type": "input_text", "text": "UserConfiguration:\n" + (user_cfg or "null")},
                    {"type": "input_text", "text": expansion_prompt},
                    {"type": "input_text", "text": json_text},
                ],
            }],
        )
        return completion.output_text or json_text
    # ------------------------------------------------------------------------

    def _build_company_digest(self, supporting_file_id: str) -> tuple[str, dict]:
        user_msg = build_company_digest_instructions()
        logger.info("Calling OpenAI Responses API for CompanyDigest…")
        completion = self.client.responses.create(
            model=MODEL,
            temperature=TEMPERATURE,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            input=[{
                "role": "user",
                "content": [
                    {"type": "input_file", "file_id": supporting_file_id},
                    {"type": "input_text", "text": COMPANY_DIGEST_SYSTEM},
                    {"type": "input_text", "text": COMPANY_DIGEST_SCHEMA},
                    {"type": "input_text", "text": user_msg},
                ],
            }],
        )
        raw = completion.output_text or ""
        try:
            digest = json.loads(raw)
        except Exception:
            digest = json.loads(raw[raw.find("{"):raw.rfind("}")+1])
        return raw, digest

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

        # Upload PDFs
        rfp_id, sup_id = self._upload_pdf_urls_to_openai(rfp_url, supporting_url)

        # Step-1: CompanyDigest from SUPPORTING_FILE
        digest_text, digest_obj = self._build_company_digest(sup_id)

        # Prepare user config (compact) for injection
        if isinstance(doc_config, dict):
            user_cfg_compact = json.dumps(doc_config, ensure_ascii=False)
        else:
            user_cfg_compact = (user_config or "").strip() or "null"

        # File-role labels
        rfp_label = "RFP (project scope, timelines, BRD/basic requirements)"
        supporting_label = "Supporting file (company profile, portfolio, capabilities)"

        # Build extra guidance: language + file roles + digest JSON + user config
        appended_guidance = build_task_instructions_with_config(
            language=language,
            user_config_json=user_cfg_compact,
            rfp_label=rfp_label,
            supporting_label=supporting_label,
            company_digest_json=digest_text,
        )

        # Outline block (keep your original prompts intact)
        if outline and outline.strip():
            outline_block = f"\n\nIMPORTANT: The proposal must follow this structure:\n{outline.strip()}"
        else:
            outline_block = f"\n\nIMPORTANT: The proposal must follow this structure:\n{proposal_template}"

        # Final user content for Responses API
        final_user_content = [
            {"type": "input_file", "file_id": rfp_id},
            {"type": "input_file", "file_id": sup_id},
            {"type": "input_text", "text": system_prompts},
            {"type": "input_text", "text": f"{task_instructions}{outline_block}"},
            {"type": "input_text", "text": appended_guidance},  # bilingual addendum lives here
        ]

        logger.info("Calling OpenAI Responses API (proposal)…")
        completion = self.client.responses.create(
            model=MODEL,
            temperature=TEMPERATURE,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            input=[{"role": "user", "content": final_user_content}],
        )
        raw = completion.output_text or ""
        logger.info(f"OpenAI response chars: {len(raw)}")

        # Guard-rail retry if the model spills non-JSON
        if "{" not in raw or '"sections"' not in raw:
            logger.warning("Model returned non-JSON; retrying with strict guardrail")
            strict_guard = (
                "Return ONLY a single valid JSON object matching the schema. "
                "Start with '{' and end with '}'. No explanations, no markdown, no extra text."
            )
            final_user_content_retry = final_user_content + [{"type": "input_text", "text": strict_guard}]
            completion = self.client.responses.create(
                model=MODEL,
                temperature=TEMPERATURE,
                max_output_tokens=MAX_OUTPUT_TOKENS,
                input=[{"role": "user", "content": final_user_content_retry}],
            )
            raw = completion.output_text or ""
            logger.info(f"[retry] OpenAI response chars: {len(raw)}")

        cleaned = proposal_cleaner(raw)
        try:
            cleaned_text = json.dumps(cleaned, ensure_ascii=False)
            expanded_text = self._maybe_expand_arabic(
                json_text=cleaned_text,
                rfp_file_id=rfp_id,
                supporting_file_id=sup_id,
                company_digest_text=digest_text,
                user_cfg=user_cfg_compact,
                language=language,
            )
            if expanded_text and expanded_text != cleaned_text:
                cleaned = proposal_cleaner(expanded_text)
        except Exception as _e:
            logger.warning(f"Arabic expansion skipped due to error: {_e}")
        out_dir = Path("output")
        out_dir.mkdir(parents=True, exist_ok=True)
        docx_path = out_dir / f"{uuid}.docx"

        effective_cfg: Dict[str, Any] = {}
        if isinstance(doc_config, dict):
            effective_cfg = doc_config
        elif isinstance(user_config, str) and user_config.strip().startswith("{"):
            try:
                effective_cfg = json.loads(user_config)
            except Exception:
                effective_cfg = {}

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
            "model_used": MODEL,
            "language": language,
            "company_digest": digest_obj,
        }

wordgen_api = WordGenAPI()
