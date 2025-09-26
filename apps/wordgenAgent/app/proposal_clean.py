import re
import json
import ast
from typing import Any, Dict, List, Union

AR_RANGE = re.compile(r'[\u0600-\u06FF]')

def first_balanced_brace_block(s: str) -> str:
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
    s = s.replace('\u2018', "'").replace('\u2019', "'")
    s = s.replace('\u201c', '"').replace('\u201d', '"')
    # keep Arabic punctuation for content; JSON parsing tolerates commas only
    return s

def normalize_json_punctuation(s: str) -> str:
    # Only swap Arabic comma to ASCII comma inside JSON delimiters when necessary.
    # We'll restore Arabic punctuation later based on language.
    return s.replace('،', ',')

def clean_corrupted_json_text(s: str) -> str:
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

def _split_multiline_points(points: List[Any]) -> List[str]:
    """Split bullet list items that came with embedded newlines or delimiters."""
    out: List[str] = []
    for p in points or []:
        text = str(p or "").strip()
        if not text:
            continue
        # split on newlines or "•" or " - " while keeping content
        parts = re.split(r'(?:\n+|•|\u2022|^\s*-\s+)', text)
        for part in parts:
            t = str(part or "").strip()
            if t:
                out.append(t)
    return out

def safe_literal_eval(s: str) -> Any:
    try:
        return ast.literal_eval(s)
    except Exception as e1:
        try:
            cleaned = clean_corrupted_json_text(s)
            block = first_balanced_brace_block(cleaned)
            return ast.literal_eval(block)
        except Exception:
            pass
        try:
            fixed = re.sub(r',\s*([}\]])', r'\1', s)
            fixed = re.sub(r',\s*,', r', ', fixed)
            block = first_balanced_brace_block(fixed)
            return ast.literal_eval(block)
        except Exception:
            pass
        try:
            block = first_balanced_brace_block(s)
            block = normalize_json_punctuation(block)
            return json.loads(block)
        except Exception as e4:
            raise ValueError(f"Could not parse input.\n{e1}\n{e4}")

def dedupe_sections_by_heading(obj: Dict[str, Any]) -> Dict[str, Any]:
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
    cleaned: Dict[str, Any] = {}
    heading = (section.get("heading") or "").strip()
    cleaned["heading"] = heading

    content = (section.get("content") or "").strip()
    cleaned["content"] = re.sub(r'\s+', ' ', content).strip() if content else ""

    # split multiline bullets safely
    points = _split_multiline_points(section.get("points") or [])
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
    if not isinstance(obj, dict):
        raise ValueError("Proposal must be a dictionary")
    if "title" not in obj:
        obj["title"] = "Generated Proposal"
    if "sections" not in obj or not isinstance(obj["sections"], list):
        obj["sections"] = []
    obj["title"] = str(obj["title"]).strip()
    return obj

def _localize_ar_punct_in_text(txt: str) -> str:
    # convert ASCII comma/period to Arabic forms inside Arabic runs
    def repl(match: re.Match) -> str:
        chunk = match.group(0)
        chunk = chunk.replace(",", "،")
        # Arabic sentence-ending period stays ".", but for clarity you can use Arabic full stop "۔"
        # chunk = chunk.replace(".", "۔")
        return chunk
    return AR_RANGE.sub(lambda m: m.group(0), txt) and re.sub(r'([\u0600-\u06FF][^a-zA-Z0-9]*)', repl, txt)

def localize_proposal_punctuation(obj: Dict[str, Any], language: str) -> Dict[str, Any]:
    if (language or "").lower() != "arabic":
        return obj
    # Title
    obj["title"] = _localize_ar_punct_in_text(obj.get("title", ""))
    # Sections
    new_secs = []
    for s in obj.get("sections", []):
        s["heading"] = _localize_ar_punct_in_text(s.get("heading", ""))
        s["content"] = _localize_ar_punct_in_text(s.get("content", ""))
        s["points"] = [_localize_ar_punct_in_text(p) for p in (s.get("points") or [])]
        tbl = s.get("table") or {"headers": [], "rows": []}
        tbl["headers"] = [_localize_ar_punct_in_text(h) for h in (tbl.get("headers") or [])]
        tbl["rows"] = [[_localize_ar_punct_in_text(c) for c in row] for row in (tbl.get("rows") or [])]
        s["table"] = tbl
        new_secs.append(s)
    obj["sections"] = new_secs
    return obj

def proposal_cleaner(input_text: str) -> Union[str, Dict[str, Any]]:
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
