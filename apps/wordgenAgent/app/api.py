import os
import sys
import json
import logging
from typing import Dict, Any, Tuple, Optional, List, Iterator
from concurrent.futures import ThreadPoolExecutor

import requests
from openai import OpenAI

from dotenv import load_dotenv
load_dotenv(override=True)

def _emit_stdout(text: str) -> None:
    """Write UTF-8 output safely even on non-UTF-8 consoles (e.g., Windows cp1252)."""
    data = (text + "\n").encode("utf-8", errors="replace")
    buffer = getattr(sys.stdout, "buffer", None)
    if buffer is not None:
        try:
            buffer.write(data)
            buffer.flush()
            return
        except Exception:
            pass

    safe_text = (text + "\n").encode("ascii", errors="replace").decode("ascii")
    print(safe_text, end="", flush=True)

from apps.api.services.supabase_service import (
    save_generated_markdown,   
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
        )
    return (
        "LANGUAGE_MODE: ENGLISH.\n"
        "TOP PRIORITY: Output ALL fields (title, headings, content, points, table headers/rows) in English only."
    )


def _sse_event_raw(event: str, data: str) -> bytes:
    """
    Format an SSE frame with JSON-encoded data to preserve ALL characters exactly.
    This ensures newlines, spaces, and special characters are preserved.
    """
    if data is None:
        data = ""
    
    # JSON-encode the data to preserve all special characters including newlines
    encoded_data = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {encoded_data}\n\n".encode("utf-8")


def _sse_event_json(event: str, obj: Dict[str, Any]) -> bytes:
    """
    SSE event for small JSON status/stage messages.
    """
    return f"event: {event}\ndata: {json.dumps(obj, ensure_ascii=False)}\n\n".encode("utf-8")


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
        response = requests.get(cleaned_url, timeout=60)
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

    def generate_complete_proposal(
        self,
        uuid: str,
        rfp_url: str,
        supporting_url: str,
        user_config: str = "",
        doc_config: Dict[str, Any] | None = None,
        language: str = "english",
        outline: str | None = None,
    ) -> Iterator[bytes]:
        try:
            yield _sse_event_json("stage", {"stage": "starting"})
            yield _sse_event_json("stage", {"stage": "downloading_and_uploading_pdfs"})
            rfp_id, sup_id = self._upload_pdf_urls_to_openai(rfp_url, supporting_url)
            rfp_label = "RFP/BRD: requirements, evaluation criteria, project details, and timelines"
            supporting_label = "Supporting: company profile, portfolio, capabilities, certifications, differentiators"
            system_prompts = P.system_prompts
            lang_block = _lang_flag(language)
            user_cfg_notes = user_config if isinstance(user_config, str) else ""

            additive_block = P.build_task_instructions_with_config(
                language=language,
                user_config_json=(user_config if isinstance(user_config, str) else "null"),
                rfp_label=rfp_label,
                supporting_label=supporting_label,
                user_config_notes=user_cfg_notes,
            )
            task_instructions = f"\nIMPORTANT: The proposal must follow this structure:\n{additive_block}"
            yield _sse_event_json("stage", {"stage": "prompting_model"})

            # Generate Proposal
            logger.info("Calling OpenAI Responses API…")
            response = self.client.responses.create(
                model=P.MODEL,
                max_output_tokens=18000,
                input=[{
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": lang_block},
                        {"type": "input_file", "file_id": rfp_id},
                        {"type": "input_file", "file_id": sup_id},
                        {"type": "input_text", "text": user_cfg_notes},
                        {"type": "input_text", "text": system_prompts},
                        {"type": "input_text", "text": task_instructions},
                    ],
                }],
                reasoning= {
                    "effort": "minimal"
                },
                stream=True,
            )

            buffer_chunks: List[str] = []
            line_buffer = ""

            for event in response:
                et = getattr(event, "type", "")
                if et == "response.output_text.delta":
                    delta = getattr(event, "delta", "")
                    if not delta:
                        continue
                    buffer_chunks.append(delta)
                    yield _sse_event_raw("chunk", delta)

                    line_buffer += delta
                    while "\n" in line_buffer:
                        line, line_buffer = line_buffer.split("\n", 1)
                        _emit_stdout(line)

                elif et == "response.error":
                    err_msg = getattr(event, "error", "stream error")
                    logger.error(f"OpenAI stream error: {err_msg}")
                    yield _sse_event_json("error", {"message": str(err_msg)})
                    return

                elif et == "response.completed":
                    break
            if line_buffer:
                _emit_stdout(line_buffer)
                line_buffer = ""

            full_markdown = "".join(buffer_chunks)  
            _emit_stdout(full_markdown)
            yield _sse_event_json("stage", {"stage": "saving_generated_text"})


            saved_ok = False
            try:
                saved_ok = save_generated_markdown(uuid, full_markdown)
                if saved_ok:
                    logger.info(f"Generated_Markdown saved for uuid={uuid}")
                else:
                    logger.error(f"Failed to save Generated_Markdown for uuid={uuid}")
            except Exception as e:
                logger.exception("Failed to save Generated_Markdown")
                yield _sse_event_json("error", {"message": f"save error: {str(e)}"})

            yield _sse_event_json("done", {"status": "saved" if saved_ok else "not_saved"})

        except Exception as e:
            logger.exception("Generate Proposal Failed failed")
            yield _sse_event_json("error", {"message": str(e)})
            
wordgen_api = WordGenAPI()
