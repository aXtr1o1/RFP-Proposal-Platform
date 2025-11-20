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
        updated_markdown = ''
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
            "updated_markdown": updated_markdown
        }

    except Exception as e:
        logger.exception(f"[regen] Failed regeneration for uuid={uuid}, gen_id={gen_id}")
        raise

def regenerate_markdown_with_comments_streaming(
    uuid: str,
    source_markdown: str,
    gen_id: str,
    docConfig: Dict[str, Any],
    language: str = "english",
    comments: Optional[List[Dict[str, str]]] = None,
) -> Iterator[bytes]:
    """
    Streaming version of regenerate_markdown_with_comments.
    Yields SSE chunks as the markdown is regenerated.
    """
    try:
        logger.info(f"[regen-stream] Starting for uuid={uuid}, gen_id={gen_id}")
        
        yield _sse_event_json("stage", {"stage": "validating_input"})
        
        if not source_markdown:
            raise ValueError("Empty source markdown — cannot regenerate")

        comments = comments or []
        
        if not comments:
            logger.warning("No comments provided, reusing original markdown")
            yield _sse_event_json("stage", {"stage": "no_modifications"})
            updated_markdown = source_markdown
            
            # Save immediately
            yield _sse_event_json("stage", {"stage": "saving_markdown"})
            saved = save_generated_markdown(uuid, gen_id, updated_markdown)
            if not saved:
                raise RuntimeError(f"Failed to save markdown for gen_id={gen_id}")
                
        else:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("Missing OPENAI_API_KEY")

            modifier = MarkdownModifier(api_key)
            
            yield _sse_event_json("stage", {"stage": "processing_with_ai"})
            
            buffer_chunks: List[str] = []
            
            # Stream the markdown regeneration
            for chunk_bytes in modifier.process_markdown_streaming(source_markdown, comments, language):
                # Forward the chunk to client
                yield chunk_bytes
                
                # Capture chunks for final save
                if b"event: chunk" in chunk_bytes:
                    try:
                        txt = chunk_bytes.decode("utf-8")
                        for line in txt.split("\n"):
                            if line.startswith("data: "):
                                data = json.loads(line[6:])
                                buffer_chunks.append(data)
                    except Exception as ex:
                        logger.warning(f"Failed to parse chunk: {ex}")
                        pass
            
            updated_markdown = "".join(buffer_chunks) if buffer_chunks else source_markdown
            
            yield _sse_event_json("stage", {"stage": "saving_markdown"})
            saved = save_generated_markdown(uuid, gen_id, updated_markdown)
            if not saved:
                raise RuntimeError(f"Failed to save regenerated markdown for gen_id={gen_id}")

        # Generate Word document
        yield _sse_event_json("stage", {"stage": "generating_word"})
        urls = generate_word_from_markdown(
            uuid=uuid,
            gen_id=gen_id,
            markdown=updated_markdown,
            doc_config=docConfig,
            language=language.lower(),
        )

        yield _sse_event_json("done", {
            "status": "completed",
            "uuid": uuid,
            "gen_id": gen_id,
            "language": language,
            "wordLink": urls.get("proposal_word_url"),
        })

        logger.info(f"[regen-stream] Completed for uuid={uuid}, gen_id={gen_id}")

    except Exception as e:
        logger.exception(f"[regen-stream] Failed for uuid={uuid}, gen_id={gen_id}")
        yield _sse_event_json("error", {"message": str(e)})