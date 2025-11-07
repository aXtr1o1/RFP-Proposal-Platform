import os
import re
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from html.parser import HTMLParser

from apps.wordgenAgent.app.wordcom import build_word_from_proposal, default_CONFIG
from apps.api.services.supabase_service import (
    upload_word_and_update_table,
)

logger = logging.getLogger("document")


class HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.text = []

    def handle_data(self, d):
        self.text.append(d)

    def get_data(self):
        return "".join(self.text)


def strip_html(text: str) -> str:
    s = HTMLStripper()
    try:
        s.feed(text)
        return s.get_data()
    except Exception:
        return text


def parse_markdown_to_json(markdown: str, language: str = "english") -> Dict[str, Any]:
    if not markdown or not markdown.strip():
        default_title = "Generated Proposal" if language.lower() != "arabic" else "عرض مُنشأ"
        return {"title": default_title, "sections": []}
    
    markdown = re.sub(r'```[\w]*\n', '', markdown)
    markdown = re.sub(r'```', '', markdown)
    markdown = re.sub(r'``', '', markdown)
    markdown = re.sub(r'`', '', markdown)
    
    lines = markdown.split("\n")
    title = ""
    sections: List[Dict[str, Any]] = []
    current_section: Optional[Dict[str, Any]] = None
    content_buffer: List[str] = []
    points_buffer: List[str] = []
    in_table = False
    table_headers: List[str] = []
    table_rows: List[List[str]] = []

    def flush_content():
        nonlocal content_buffer
        if content_buffer and current_section is not None:
            text = "\n".join(content_buffer).strip()
            if text:
                if current_section["content"]:
                    current_section["content"] += "\n\n" + text
                else:
                    current_section["content"] = text
            content_buffer = []

    def flush_points():
        nonlocal points_buffer
        if points_buffer and current_section is not None:
            current_section["points"].extend(points_buffer)
            points_buffer = []

    def flush_table():
        nonlocal in_table, table_headers, table_rows
        if in_table and current_section is not None:
            current_section["table"]["headers"] = table_headers
            current_section["table"]["rows"] = table_rows
        in_table = False
        table_headers = []
        table_rows = []

    def start_new_section(heading: str):
        nonlocal current_section
        flush_content()
        flush_points()
        flush_table()
        current_section = {
            "heading": heading,
            "content": "",
            "points": [],
            "table": {"headers": [], "rows": []},
        }
        sections.append(current_section)

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        stripped = strip_html(stripped)

        if stripped.startswith("# ") and not title:
            title = stripped[2:].strip()
            continue

        if stripped.startswith("## "):
            heading = stripped[3:].strip()
            start_new_section(heading)
            continue

        if stripped.startswith("### ") or (stripped.startswith("**") and stripped.endswith("**") and len(stripped) > 4):
            subheading = stripped[4:].strip() if stripped.startswith("### ") else stripped.strip("*").strip()
            start_new_section(subheading)
            continue

        if "|" in stripped and not in_table:
            in_table = True
            flush_content()
            flush_points()
            table_headers = [cell.strip() for cell in stripped.split("|") if cell.strip()]
            continue

        if in_table:
            if re.match(r"^\|[\s\-:]+\|", stripped):
                continue
            if "|" in stripped:
                row = [cell.strip() for cell in stripped.split("|") if cell.strip()]
                if row:
                    table_rows.append(row)
                continue
            else:
                flush_table()

        if re.match(r"^[\-\*\+]\s+", stripped) or re.match(r"^\d+\.\s+", stripped):
            flush_content()
            point = re.sub(r"^[\-\*\+\d\.]\s+", "", stripped).strip()
            if point:
                points_buffer.append(point)
            continue

        flush_points()
        content_buffer.append(stripped)

    flush_content()
    flush_points()
    flush_table()

    if not title:
        title = "Generated Proposal" if language.lower() != "arabic" else "عرض مُنشأ"

    return {"title": title, "sections": sections}


def generate_word_from_markdown(
    uuid: str,
    gen_id: str,
    markdown: str,
    doc_config: Optional[Dict[str, Any]],
    language: str = "english",
) -> Dict[str, str]:
    """
    Build DOCX from markdown -> upload to Supabase -> update word_gen row
    """
    try:
        logger.info(f"Parsing markdown to JSON for uuid={uuid}, gen_id={gen_id}")
        proposal_json = parse_markdown_to_json(markdown, language=language)
        effective_config = doc_config if (doc_config and isinstance(doc_config, dict)) else default_CONFIG

        out_dir = Path("output")
        out_dir.mkdir(parents=True, exist_ok=True)
        docx_path = out_dir / f"{uuid}_{gen_id}.docx"

        logger.info(f"Building Word for uuid={uuid}, gen_id={gen_id}")
        docx_abs = build_word_from_proposal(
            proposal_dict=proposal_json,
            user_config=effective_config,
            output_path=str(docx_path),
            visible=False,
        )

        proposal_word_url = ""
        if os.path.exists(docx_abs):
            with open(docx_abs, "rb") as f:
                word_bytes = f.read()
            res = upload_word_and_update_table(
                uuid=uuid,
                gen_id=gen_id,
                word_content=word_bytes,
                filename="proposal.docx",
                generated_markdown=markdown,  
            )
            if res and "word_url" in res:
                proposal_word_url = res["word_url"]

        try:
            if os.path.exists(docx_abs):
                os.remove(docx_abs)
        except Exception as e:
            logger.warning(f"Cleanup failed for {docx_abs}: {e}")

        return {"proposal_word_url": proposal_word_url}

    except Exception as e:
        logger.exception(f"generate_word_from_markdown failed for uuid={uuid}, gen_id={gen_id}")
        raise
