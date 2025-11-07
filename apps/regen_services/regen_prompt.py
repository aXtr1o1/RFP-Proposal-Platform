import os
import json
import logging
from typing import Dict, Any, List, Optional, Iterator
from openai import OpenAI
from dotenv import load_dotenv
from apps.api.services.supabase_service import (
    supabase,
    save_generated_markdown,
)
from apps.wordgenAgent.app.document import generate_word_from_markdown
load_dotenv(override=True)
logger = logging.getLogger("regen_prompt")


def _sse_event_raw(event: str, data: str) -> bytes:
    """
    Format an SSE frame with JSON-encoded data to preserve ALL characters exactly.
    """
    if data is None:
        data = ""
    encoded_data = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {encoded_data}\n\n".encode("utf-8")


def _sse_event_json(event: str, obj: Dict[str, Any]) -> bytes:
    """SSE event for JSON messages."""
    return f"event: {event}\ndata: {json.dumps(obj, ensure_ascii=False)}\n\n".encode("utf-8")

def _get_latest_markdown_excluding(uuid: str, exclude_gen_id: Optional[str]) -> str:
    """
    Get the most recent markdown for uuid, excluding the row with exclude_gen_id (the new regen row).
    Falls back to latest if exclusion yields nothing.
    """
    try:
        q = (
            supabase.table("word_gen")
            .select("generated_markdown, gen_id, created_at")
            .eq("uuid", uuid)
            .order("created_at", desc=True)
        )
        res = q.execute()
        if not res.data:
            raise ValueError("No rows for this uuid")

        for row in res.data:
            if exclude_gen_id and row.get("gen_id") == exclude_gen_id:
                continue
            md = (row.get("generated_markdown") or "").strip()
            if md:
                return md
        return (res.data[0].get("generated_markdown") or "")
    except Exception as e:
        logger.exception(f"_get_latest_markdown_excluding failed for uuid={uuid}")
        raise


def _get_comments_for_uuid(uuid: str) -> List[Dict[str, str]]:
    try:
        res = supabase.table("proposal_comments").select("comments").eq("uuid", uuid).limit(1).execute()
        if not res.data:
            return []
        items = res.data[0].get("comments") or []
        valid = []
        for it in items:
            if isinstance(it, dict) and ("comment1" in it or "comment2" in it):
                valid.append({"comment1": it.get("comment1", ""), "comment2": it.get("comment2", "")})
        return valid
    except Exception:
        logger.exception("fetch comments failed")
        return []

class MarkdownModifier:
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)

    def create_modification_instructions(self, items: List[Dict[str, str]]) -> str:
        if not items:
            return "No modifications requested."
        instructions = "You must modify ONLY the following specific content pieces in the markdown:\n\n"
        for i, item in enumerate(items, 1):
            instructions += f"{i}. FIND THIS EXACT TEXT:\n"
            instructions += f"{item.get('comment1','')}"
            instructions += f"\n\nMODIFICATION INSTRUCTION: {item.get('comment2','')}\n\n---\n\n"
        instructions += (
            "IMPORTANT RULES:\n"
            "1. Modify only the specified spots.\n"
            "2. Keep all other content unchanged.\n"
            "3. Preserve markdown structure and formatting.\n"
            "4. Return ONLY the full updated markdown (no JSON, no commentary).\n"
        )
        return instructions

    def process_markdown(self, markdown: str, items: List[Dict[str, str]], language: str) -> str:
        logger.info("Starting OpenAI markdown regeneration")
        modification_instructions = self.create_modification_instructions(items)

        system_prompt = (
            "You are an expert in proposal writing and precise markdown editing.\n"
            f"Generate output only in this language: {language}.\n"
            "Return ONLY the updated markdown — no JSON or explanations."
        )

        user_prompt = (
            f"ORIGINAL MARKDOWN:\n{markdown}\n\n"
            f"MODIFICATION INSTRUCTIONS:\n{modification_instructions}\n\n"
            "Process and return the full updated markdown."
        )

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
        )
        content = response.choices[0].message.content or ""
        if not content.strip():
            raise ValueError("Empty response from OpenAI")
        return content

    def process_markdown_streaming(self, markdown: str, items: List[Dict[str, str]], language: str) -> Iterator[bytes]:
        logger.info("Starting OpenAI markdown regeneration with streaming")
        modification_instructions = self.create_modification_instructions(items)

        system_prompt = (
            "You are an expert in proposal writing and precise markdown editing.\n"
            f"Generate output only in this language: {language}.\n"
            "Return ONLY the updated markdown — no JSON or explanations."
        )
        user_prompt = (
            f"ORIGINAL MARKDOWN:\n{markdown}\n\n"
            f"MODIFICATION INSTRUCTIONS:\n{modification_instructions}\n\n"
            "Process and return the full updated markdown."
        )

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            stream=True,
        )

        buffer_chunks: List[str] = []
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content is not None:
                content = chunk.choices[0].delta.content
                buffer_chunks.append(content)
                yield _sse_event_raw("chunk", content)

        full_markdown = "".join(buffer_chunks)
        logger.info(f"Streaming regen completed, length: {len(full_markdown)} chars")
        yield _sse_event_json("stage", {"stage": "saving_generated_text"})
        yield _sse_event_json("result", {"markdown": full_markdown})

def regenerate_markdown_with_comments(
    uuid: str,
    source_markdown: str,
    gen_id: str,
    docConfig: Dict[str, Any],
    language: str = "english",
    comments: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """
    Regenerate markdown from a given source_markdown using user comments.
    """
    try:
        logger.info(f"[regen] Starting regeneration for uuid={uuid}, new_gen_id={gen_id}")

        if not source_markdown:
            raise ValueError("Empty source markdown — cannot regenerate")

        comments = comments or []
        if not comments:
            logger.warning("No comments provided, reusing original markdown")
            updated_markdown = source_markdown
        else:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("Missing OPENAI_API_KEY")

            modifier = MarkdownModifier(api_key)
            updated_markdown = modifier.process_markdown(
                markdown=source_markdown,
                items=comments,
                language=language,
            )
        saved = save_generated_markdown(uuid, gen_id, updated_markdown)
        if not saved:
            raise RuntimeError(f"Failed to save regenerated markdown for gen_id={gen_id}")
        urls = generate_word_from_markdown(
            uuid=uuid,
            gen_id=gen_id,
            markdown=updated_markdown,
            doc_config=docConfig,
            language=language.lower(),
        )

        logger.info(f"[regen] Completed regeneration for uuid={uuid}, gen_id={gen_id}")
        return {
            "status": "success",
            "uuid": uuid,
            "gen_id": gen_id,
            "language": language,
            "wordLink": urls.get("proposal_word_url"),
        }

    except Exception as e:
        logger.exception(f"[regen] Failed regeneration for uuid={uuid}, gen_id={gen_id}")
        raise

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
from apps.wordgenAgent.app.document import generate_word_from_markdown

logger = logging.getLogger("wordgen_api")


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
    if data is None:
        data = ""
    encoded_data = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {encoded_data}\n\n".encode("utf-8")


def _sse_event_json(event: str, obj: Dict[str, Any]) -> bytes:
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
        gen_id: str,
        rfp_url: str,
        supporting_url: str,
        user_config: str = "",
        doc_config: Optional[Dict[str, Any]] = None,
        language: str = "english",
        outline: Optional[str] = None,
    ) -> Iterator[bytes]:
        try:
            yield _sse_event_json("stage", {"stage": "starting"})
            yield _sse_event_json("stage", {"stage": "uploading_files"})
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
                reasoning={"effort": "minimal"},
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

            full_markdown = "".join(buffer_chunks)
            _emit_stdout(full_markdown)
            yield _sse_event_json("stage", {"stage": "saving_markdown"})

            saved_ok = False
            try:
                saved_ok = save_generated_markdown(uuid, gen_id, full_markdown)
            except Exception as e:
                logger.exception("Failed to save generated markdown")
                yield _sse_event_json("error", {"message": f"save error: {str(e)}"})
            yield _sse_event_json("stage", {"stage": "building_word"})
            try:
                _ = generate_word_from_markdown(
                    uuid=uuid,
                    gen_id=gen_id,
                    markdown=full_markdown,
                    doc_config=doc_config,
                    language=(language or "english").lower(),
                )
            except Exception as e:
                logger.exception("Word generation/upload failed")
                yield _sse_event_json("error", {"message": f"word build error: {str(e)}"})

            yield _sse_event_json("done", {"status": "saved" if saved_ok else "not_saved"})

        except Exception as e:
            logger.exception("generate_complete_proposal failed")
            yield _sse_event_json("error", {"message": str(e)})


wordgen_api = WordGenAPI()
