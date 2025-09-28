import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Tuple, Optional, List
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
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
from apps.wordgenAgent.app import prompt5 as P

logger = logging.getLogger("wordgen_api")

SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "pdf")

def _lang_flag(language: str) -> str:
    lang = (language or "").strip().lower()
    if lang == "arabic":
        return (
            "LANGUAGE_MODE: ARABIC (Modern Standard Arabic).\n"
            "TOP PRIORITY: Output ALL fields (title, headings, content, points, table headers/rows) in Arabic only.\n"
            "Do NOT mix languages except for proper nouns/acronyms required by the RFP."
        )
    return (
        "LANGUAGE_MODE: ENGLISH.\n"
        "TOP PRIORITY: Output ALL fields (title, headings, content, points, table headers/rows) in English only."
    )

class WordGenAPI:
    def __init__(self) -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required")
        self.client = OpenAI(api_key=api_key)
        logger.info("OpenAI client initialized")

    @staticmethod
    def _clean_url(url: str) -> str:
        cleaned_url = (url or "").split("?")[0]
        logger.debug(f"Cleaned URL: {cleaned_url}")
        return cleaned_url

    def _download_pdf(self, url: str) -> bytes:
        cleaned_url = self._clean_url(url)
        logger.info(f"Starting download of PDF: {cleaned_url}")
        response = requests.get(cleaned_url, timeout=15)
        response.raise_for_status()
        logger.info(f"Finished download of PDF: {cleaned_url} ({len(response.content)} bytes)")
        return response.content

    def _download_two_pdfs(self, rfp_url: str, supporting_url: str) -> Tuple[bytes, bytes]:
        logger.info("Beginning parallel download of two PDFs")
        with ThreadPoolExecutor() as executor:
            future_rfp = executor.submit(self._download_pdf, rfp_url)
            future_sup = executor.submit(self._download_pdf, supporting_url)
            rfp_bytes = future_rfp.result()
            sup_bytes = future_sup.result()
        logger.info("Completed parallel download of two PDFs")
        return rfp_bytes, sup_bytes

    def _upload_pdf_bytes_to_openai(self, pdf_bytes: bytes, filename: str) -> str:
        logger.info(f"Uploading {filename} to OpenAI")
        file_obj = self.client.files.create(file=(filename, pdf_bytes, "application/pdf"), purpose="user_data")
        logger.info(f"Uploaded {filename} as file ID: {file_obj.id}")
        return file_obj.id

    def _upload_pdf_urls_to_openai(self, rfp_url: str, supporting_url: str) -> Tuple[str, str]:
        rfp_bytes, sup_bytes = self._download_two_pdfs(rfp_url, supporting_url)
        logger.info("Beginning parallel upload of two PDFs to OpenAI")
        with ThreadPoolExecutor() as executor:
            future_rfp = executor.submit(self._upload_pdf_bytes_to_openai, rfp_bytes, "RFP.pdf")
            future_sup = executor.submit(self._upload_pdf_bytes_to_openai, sup_bytes, "Supporting.pdf")
            rfpf_id = future_rfp.result()
            supf_id = future_sup.result()
        logger.info(f"Completed parallel upload of PDFs with IDs: rfp={rfpf_id}, supporting={supf_id}")
        return rfpf_id, supf_id


    def _convert_docx_to_pdf(self, docx_path: str) -> str:
        pdf_path = os.path.splitext(docx_path)[0] + ".pdf"
        pythoncom.CoInitialize()
        try:
            convert(docx_path, pdf_path)
            logger.info(f"Converted to PDF: {pdf_path}")
        finally:
            pythoncom.CoUninitialize()
        return pdf_path

    def _build_company_digest(self, supporting_file_id: str ) -> dict:
        """Use the digest prompts (provided by you) to extract structured company info."""
        response = self.client.responses.create(
            model="gpt-4o-mini",
            input=[{
                "role": "user",
                "content": [
                    {"type": "input_file", "file_id": supporting_file_id},
                    {"type": "input_text", "text": P.COMPANY_DIGEST_SYSTEM},
                    {"type": "input_text", "text": P.COMPANY_DIGEST_SCHEMA},
                    {"type": "input_text", "text": P.build_company_digest_instructions()},
                ],
            }],
            stream=True,
        )
        chunks = []
        for event in response:
            if event.type == "response.output_text.delta":
                chunks.append(event.delta)
            elif event.type == "response.error":
                raise RuntimeError(getattr(event, "error", "stream error"))
            elif event.type == "response.completed":
                break

        raw = "".join(chunks)
        try:
            digest = proposal_cleaner(raw)
            if isinstance(digest, dict):
                return digest
        except Exception:
            pass
        return {"company_profile": {}, "capabilities": {}, "track_record": [], "contact": {}}

    @staticmethod
    def _detect_company_name(digest: dict) -> str:
        profile = digest.get("company_profile", {}) if isinstance(digest, dict) else {}
        return (
            profile.get("brand_name")
            or profile.get("legal_name")
            or "Your Company"
        )

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

        # Upload files
        rfp_id, sup_id = self._upload_pdf_urls_to_openai(rfp_url, supporting_url)

        # Build CompanyDigest
        company_digest = self._build_company_digest(sup_id)
        company_name = self._detect_company_name(company_digest)

        user_cfg_compact = user_config if isinstance(user_config, str) else "null"
        rfp_label = "RFP/BRD: requirements, evaluation criteria, project details, and timelines"
        supporting_label = "Supporting: company profile, portfolio, capabilities, certifications, differentiators"
        system_prompts = P.system_prompts
        task_instructions_base = getattr(P, "task_instructions", "") or ""
        proposal_template_text = (
            (outline.strip() if outline and outline.strip() else getattr(P, "PROPOSAL_TEMPLATE", "") or "")
        )
        user_cfg_notes = (user_config or "").strip()
        user_cfg_compact = "null"

        company_digest_json = json.dumps(company_digest, ensure_ascii=False) if company_digest else "{}"
        additive_block = P.build_task_instructions_with_config(
                        language=language,
                        user_config_json=user_cfg_compact,   
                        rfp_label=rfp_label,
                        supporting_label=supporting_label,
                        company_digest_json=company_digest_json,
                        user_config_notes=user_cfg_notes,    
                    )
        
        task_instructions = (
            f"{task_instructions_base}"
            f"\nIMPORTANT: The proposal must follow this structure:\n"
            f"{proposal_template_text}\n"
            f"{additive_block}"
        )


        # Proposal generation
        logger.info("Calling OpenAI Responses API…")
        response = self.client.responses.create(
            model=P.MODEL,
            max_output_tokens=30000,
            input=[{
                "role": "user",
                "content": [
                    {"type": "input_text", "text": _lang_flag(language)},
                    {"type": "input_file", "file_id": rfp_id},
                    {"type": "input_file", "file_id": sup_id},
                    {"type": "input_text", "text": company_digest_json},
                    {"type": "input_text", "text": (user_config if isinstance(user_config, str) else "")},
                    {"type": "input_text", "text": system_prompts},
                    {"type": "input_text", "text": task_instructions},
                ],
            }],
            stream=True,
        )
        chunks = []
        for event in response:
            if event.type == "response.output_text.delta":
                chunks.append(event.delta)
            elif event.type == "response.error":
                raise RuntimeError(getattr(event, "error", "stream error"))
            elif event.type == "response.completed":
                break

        raw = "".join(chunks)
        logger.info(f"OpenAI response chars: {len(raw)}")

        if "{" not in raw or '"sections"' not in raw:
            logger.warning("Model returned non-JSON; retrying with strict guardrail")
            strict_guard = (
                "Return ONLY a single valid JSON object matching the schema. "
                "Start with '{' and end with '}'. No explanations, no markdown, no extra text."
            )
            response = self.client.responses.create(
                model=P.MODEL,
                max_output_tokens= 30000,
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
                stream=True,
            )
            chunks = []
            for event in response:
                if event.type == "response.output_text.delta":
                    chunks.append(event.delta)
                elif event.type == "response.error":
                    raise RuntimeError(getattr(event, "error", "stream error"))
                elif event.type == "response.completed":
                    break

            raw = "".join(chunks)
            logger.info(f"[retry] OpenAI response chars: {len(raw)}")

        cleaned = proposal_cleaner(raw)


        def _normalize_proposal_shape(p: dict, company_name: str = "Your Company", language: str = "english") -> dict:
                import json
                if not isinstance(p, dict):
                    return p

                def _maybe_extract_json_blob(s: str) -> dict | None:
                    """Try to extract a full JSON object from a string by locating the outermost { ... }."""
                    if not isinstance(s, str):
                        return None
                    if "{" not in s or "}" not in s:
                        return None
                    txt = s.strip()
                    if txt.startswith("{") and txt.endswith("}"):
                        try:
                            obj = json.loads(txt)
                            return obj if isinstance(obj, dict) else None
                        except Exception:
                            pass
                    try:
                        first = txt.find("{")
                        last = txt.rfind("}")
                        if first != -1 and last > first:
                            candidate = txt[first:last+1]
                            obj = json.loads(candidate)
                            return obj if isinstance(obj, dict) else None
                    except Exception:
                        return None
                    return None
                try:
                    secs = p.get("sections") or []
                    if secs and isinstance(secs[0], dict):
                        h0_raw = secs[0].get("heading") or ""
                        h0 = h0_raw.strip().lower()
                        c0 = secs[0].get("content")
                        WRAPPER_HEADS = {
                            "draft", "generated", "wrapper", "temp", "temporary",
                            "مسودة", "نسخة أولية", "تجريبي", "اختباري"
                        }
                        if h0 in WRAPPER_HEADS and isinstance(c0, str):
                            inner = _maybe_extract_json_blob(c0)
                            if isinstance(inner, dict) and isinstance(inner.get("sections"), list) and inner["sections"]:
                                p = inner
                except Exception:
                    pass
                if "sections" in p and isinstance(p["sections"], list):
                    fixed = []
                    for s in p["sections"]:
                        if not isinstance(s, dict):
                            continue
                        heading = s.get("heading")
                        content = s.get("content")
                        points = s.get("points")
                        table = s.get("table")
                        h_norm = (heading or "").strip().lower()
                        if h_norm in {"draft", "wrapper", "generated", "temp", "temporary", "مسودة", "نسخة أولية", "تجريبي", "اختباري"}:
                            inner = _maybe_extract_json_blob(content) if isinstance(content, str) else None
                            if isinstance(inner, dict) and isinstance(inner.get("sections"), list) and inner["sections"]:
                                for s2 in inner["sections"]:
                                    if isinstance(s2, dict):
                                        fixed.append(s2)
                            continue
                        if isinstance(content, str):
                            inner = _maybe_extract_json_blob(content)
                            if isinstance(inner, dict) and "sections" in inner:
                                content = ""
                        if not isinstance(points, list):
                            points = []
                        else:
                            points = [str(x) for x in points if isinstance(x, (str, int, float))]
                        if not isinstance(table, dict):
                            table = {"headers": [], "rows": []}
                        headers = table.get("headers", [])
                        rows = table.get("rows", [])
                        headers = [str(h) for h in headers] if isinstance(headers, list) else []
                        rows = [[str(c) for c in r] for r in rows if isinstance(r, list)] if isinstance(rows, list) else []

                        fixed.append({
                            "heading": str(heading or ""),
                            "content": str(content or ""),
                            "points": points,
                            "table": {"headers": headers, "rows": rows},
                        })
                    p["sections"] = fixed

                title = (p.get("title") or "").strip()
                GENERIC_TITLES = {"generated proposal", "draft", "proposal", "generated", "عرض", "مسودة"}
                if not title or title.strip().lower() in GENERIC_TITLES:
                    if (language or "").strip().lower() == "arabic":
                        p["title"] = f"عرض فني متكامل — مُعد من قبل {company_name}"
                    else:
                        p["title"] = f"Comprehensive Technical Proposal — Prepared by {company_name}"
                if not isinstance(p.get("sections"), list):
                    p["sections"] = []

                return p
        
        cleaned = _normalize_proposal_shape(cleaned)

        # Build Word & PDF
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

        # Upload to Supabase
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
