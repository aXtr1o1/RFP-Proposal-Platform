import re
import json
import ast
from typing import Any, Dict, List, Union

def first_balanced_brace_block(s: str) -> str:
    """
    Return the first balanced {...} block from s (handles extra garbage/duplicates after it).
    """
    start = s.find('{')
    if start == -1:
        raise ValueError("No opening '{' found in input.")
    depth = 0
    for i in range(start, len(s)):
        ch = s[i]
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return s[start:i+1]
    raise ValueError("No balanced closing '}' found.")

def normalize_quotes(s: str) -> str:
    """
    Normalize curly quotes and weird punctuation that often appear in copy-pastes.
    """
    s = s.replace('\u2018', "'").replace('\u2019', "'")
    s = s.replace('\u201c', '"').replace('\u201d', '"')
    s = s.replace('،', ',')
    return s

def normalize_json_punctuation(s: str) -> str:
    """
    Very targeted fixups to make Arabic/English JSON parseable without changing content meaning.
    Only touches characters that break JSON (Arabic comma, smart quotes).
    """
    return normalize_quotes(s)

def clean_corrupted_json_text(s: str) -> str:
    """
    Clean corrupted/duplicated text that appears in malformed JSON strings.
    """
    lines = s.split('\n')
    clean_lines = []
    seen_content = set()
    for line in lines:
        line_clean = line.strip()
        if not line_clean:
            continue
        if line_clean in seen_content and len(line_clean) > 50:
            continue
        clean_lines.append(line)
        if len(line_clean) > 20:
            seen_content.add(line_clean)
    return '\n'.join(clean_lines)

def safe_literal_eval(s: str) -> Any:
    """
    Try multiple strategies to parse Python/JSON-like text robustly.
    """
    try:
        return ast.literal_eval(s)
    except Exception as e1:
        try:
            cleaned = clean_corrupted_json_text(s)
            block = first_balanced_brace_block(cleaned)
            return ast.literal_eval(block)
        except Exception as e2:
            pass
        try:
            fixed = re.sub(r',\s*([}\]])', r'\1', s)   
            fixed = re.sub(r',\s*,', r', ', fixed)     
            block = first_balanced_brace_block(fixed)
            return ast.literal_eval(block)
        except Exception as e3:
            pass
        try:
            block = first_balanced_brace_block(s)
            block = normalize_json_punctuation(block)
            return json.loads(block)
        except Exception as e4:
            raise ValueError(f"Could not parse input.\n{e1}\n{e2}\n{e3}\n{e4}")

def dedupe_sections_by_heading(obj: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove duplicate sections by 'heading' while preserving the first occurrence.
    Also removes sections with empty or missing headings.
    """
    sections = obj.get("sections", [])
    seen = set()
    deduped: List[Dict[str, Any]] = []
    for sec in sections:
        heading = (sec.get("heading") or "").strip()
        if heading and heading not in seen:
            seen.add(heading)
            cleaned_section = clean_section_content(sec)
            deduped.append(cleaned_section)
    obj["sections"] = deduped
    return obj

def clean_section_content(section: Dict[str, Any]) -> Dict[str, Any]:
    """
    Clean individual section content, removing duplicates and fixing formatting.
    """
    cleaned: Dict[str, Any] = {}
    heading = (section.get("heading") or "").strip()
    cleaned["heading"] = heading

    content = (section.get("content") or "").strip()
    if content:
        cleaned["content"] = re.sub(r'\s+', ' ', content).strip()
    else:
        cleaned["content"] = ""

    points = section.get("points") or []
    if points:
        uniq, seen = [], set()
        for p in points:
            t = str(p).strip()
            if t and t not in seen:
                uniq.append(t)
                seen.add(t)
        cleaned["points"] = uniq
    else:
        cleaned["points"] = []

    table = section.get("table") or {}
    cleaned_table: Dict[str, Any] = {"headers": [], "rows": []}
    if isinstance(table, dict):
        headers = table.get("headers") or []
        if headers:
            cleaned_table["headers"] = [str(h).strip() for h in headers if str(h).strip()]
        rows = table.get("rows") or []
        if rows:
            out_rows = []
            for row in rows:
                if isinstance(row, list):
                    r = [str(c).strip() for c in row if str(c).strip()]
                    if r:
                        out_rows.append(r)
            cleaned_table["rows"] = out_rows
    cleaned["table"] = cleaned_table

    if "mermaid_diagram" in section:
        cleaned["mermaid_diagram"] = section["mermaid_diagram"]

    return cleaned

def validate_proposal_structure(obj: Any) -> Dict[str, Any]:
    """
    Validate and ensure the proposal has the correct structure.
    """
    if not isinstance(obj, dict):
        raise ValueError("Proposal must be a dictionary")

    if "title" not in obj:
        obj["title"] = "Generated Proposal"

    if "sections" not in obj or not isinstance(obj["sections"], list):
        obj["sections"] = []

    obj["title"] = str(obj["title"]).strip()
    return obj

def proposal_cleaner(input_text: str) -> Union[str, Dict[str, Any]]:
    """
    Clean and parse proposal text into a well-formatted JSON structure.
    Returns cleaned proposal as dict (preferred) or JSON string.
    Includes a final minimal-JSON fallback to avoid pipeline failures.
    """
    try:
        normalized = normalize_quotes(input_text or "")
        block = first_balanced_brace_block(normalized)
        block = normalize_json_punctuation(block)
        try:
            parsed = json.loads(block)
        except Exception:
            parsed = safe_literal_eval(block)

        if isinstance(parsed, dict):
            parsed = validate_proposal_structure(parsed)
            parsed = dedupe_sections_by_heading(parsed)
        return parsed

    except Exception:
        try:
            m = re.search(r'\{[^{}]*"sections"[^{}]*\}|\{.*"sections".*\}', input_text or "", re.DOTALL)
            if m:
                blk = normalize_json_punctuation(normalize_quotes(m.group(0)))
                parsed = json.loads(blk)
                parsed = validate_proposal_structure(parsed)
                parsed = dedupe_sections_by_heading(parsed)
                return parsed
        except Exception:
            pass

        minimal = {
            "title": "Generated Proposal",
            "sections": [{
                "heading": "Draft",
                "content": (input_text or "").strip(),
                "points": [],
                "table": {"headers": [], "rows": []}
            }]
        }
        return minimal
