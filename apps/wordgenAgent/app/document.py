import os
import re
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from html.parser import HTMLParser

import pythoncom
from docx2pdf import convert

from apps.wordgenAgent.app.wordcom import build_word_from_proposal, default_CONFIG
from apps.api.services.supabase_service import (
    upload_file_to_storage, 
    update_proposal_in_data_table
)

logger = logging.getLogger("document")


class HTMLStripper(HTMLParser):
    """Remove HTML tags from text."""
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.text = []

    def handle_data(self, d):
        self.text.append(d)

    def get_data(self):
        return ''.join(self.text)


def strip_html(text: str) -> str:
    """Strip HTML tags from text (e.g., <div align='right'>)."""
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
        """Flush accumulated content into current section."""
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
        """Flush accumulated points into current section."""
        nonlocal points_buffer
        if points_buffer and current_section is not None:
            current_section["points"].extend(points_buffer)
            points_buffer = []
    
    def flush_table():
        """Flush accumulated table into current section."""
        nonlocal in_table, table_headers, table_rows
        if in_table and current_section is not None:
            current_section["table"]["headers"] = table_headers
            current_section["table"]["rows"] = table_rows
        in_table = False
        table_headers = []
        table_rows = []
    
    def start_new_section(heading: str):
        """Start a new section (main or sub) with the given heading."""
        nonlocal current_section
        flush_content()
        flush_points()
        flush_table()
        current_section = {
            "heading": heading,
            "content": "",
            "points": [],
            "table": {"headers": [], "rows": []}
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
            if stripped.startswith("### "):
                subheading = stripped[4:].strip()
            else:
                subheading = stripped.strip("*").strip()
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
    
    return {
        "title": title,
        "sections": sections
    }


def generate_word_and_pdf_from_markdown(
    uuid: str,
    markdown: str,
    doc_config: Optional[Dict[str, Any]],
    language: str = "english"
) -> Dict[str, str]:
    try:
        # Parse markdown to JSON structure
        logger.info(f"Parsing markdown to JSON for uuid={uuid}")
        proposal_json = parse_markdown_to_json(markdown, language=language)
        logger.info(f"Parsed proposal: title='{proposal_json.get('title')}', sections={len(proposal_json.get('sections', []))}")
        
        for i, sec in enumerate(proposal_json.get('sections', [])):
            logger.debug(f"Section {i}: heading='{sec.get('heading')}', points={len(sec.get('points', []))}, content_len={len(sec.get('content', ''))}")
    
        effective_config = doc_config if (doc_config and isinstance(doc_config, dict)) else default_CONFIG
        logger.info(f"Using {'custom' if doc_config else 'default'} document config")
        
        # Generate DOCX 
        out_dir = Path("output")
        out_dir.mkdir(parents=True, exist_ok=True)
        docx_path = out_dir / f"{uuid}.docx"
        
        logger.info(f"Building Word document for uuid={uuid}")
        docx_abs = build_word_from_proposal(
            proposal_dict=proposal_json,
            user_config=effective_config,
            output_path=str(docx_path),
            language=language,
            visible=False,
        )
        logger.info(f"Word document created: {docx_abs}")
        
        # Convert DOCX to PDF 
        pdf_path = ""
        try:
            pythoncom.CoInitialize()
            pdf_path = os.path.splitext(docx_abs)[0] + ".pdf"
            logger.info(f"Converting DOCX to PDF: {pdf_path}")
            convert(docx_abs, pdf_path)
            logger.info(f"PDF conversion complete: {pdf_path}")
        except Exception as e:
            logger.error(f"PDF conversion failed: {e}")
        finally:
            pythoncom.CoUninitialize()
        
        # Upload DOCX to Supabase
        proposal_word_url = ""
        try:
            if os.path.exists(docx_abs):
                with open(docx_abs, "rb") as f:
                    word_bytes = f.read()
                proposal_word_url = upload_file_to_storage(
                    word_bytes, 
                    f"{uuid}/proposal.docx", 
                    "proposal.docx"
                )
                logger.info(f"Uploaded Word to Supabase: {proposal_word_url}")
        except Exception as e:
            logger.error(f"Upload DOCX failed: {e}")
        
        # Upload PDF to Supabase
        proposal_pdf_url = ""
        if pdf_path and os.path.exists(pdf_path):
            try:
                with open(pdf_path, "rb") as f:
                    pdf_bytes = f.read()
                proposal_pdf_url = upload_file_to_storage(
                    pdf_bytes, 
                    f"{uuid}/proposal.pdf", 
                    "proposal.pdf"
                )
                logger.info(f"Uploaded PDF to Supabase: {proposal_pdf_url}")
            except Exception as e:
                logger.error(f"Upload PDF failed: {e}")
        try:
            updated = update_proposal_in_data_table(uuid, proposal_pdf_url, proposal_word_url)
            if updated:
                logger.info(f"Data_Table updated for uuid={uuid}")
            else:
                logger.warning(f"Data_Table update returned False for uuid={uuid}")
        except Exception as e:
            logger.error(f"Data_Table update failed: {e}")
        try:
            if os.path.exists(docx_abs):
                os.remove(docx_abs)
                logger.info(f"Cleaned up local DOCX: {docx_abs}")
            if pdf_path and os.path.exists(pdf_path):
                os.remove(pdf_path)
                logger.info(f"Cleaned up local PDF: {pdf_path}")
        except Exception as e:
            logger.warning(f"Cleanup failed: {e}")
        
        return {
            "proposal_word_url": proposal_word_url,
            "proposal_pdf_url": proposal_pdf_url
        }
    
    except Exception as e:
        logger.exception(f"Document generation failed for uuid={uuid}")
        raise
