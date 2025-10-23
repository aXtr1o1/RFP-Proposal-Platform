from typing import Optional, Dict, Tuple, List

def build_language_block(language: str) -> str:
    """
    Returns a compact language directive block consumed as the first content part.
    """
    lang = (language or "english").strip().lower()
    if lang == "arabic":
        return (
            "LANGUAGE_MODE: ARABIC (Modern Standard Arabic)\n"
            "Priority: Output EVERYTHING in Arabic. No English words unless absolutely necessary.\n"
            "Renderer handles RTL; do NOT include alignment or layout instructions."
        )
    return (
        "LANGUAGE_MODE: ENGLISH\n"
        "Priority: Output EVERYTHING in English. Keep it concise and professional."
    )


def summarize_available_layouts(layout_details: Dict[int, Dict]) -> Tuple[str, List[Tuple[str, int, str]]]:
    """
    Build a one-line per layout description string and a typed list of available layout triples.
    """
    if not layout_details:
        default = [
            ("TITLE_ONLY", 0, "Title Slide"),
            ("SINGLE_CONTENT", 1, "Title and Content"),
            ("TWO_CONTENT", 3, "Two Content"),
        ]
        text = "\n".join([f"- idx {idx}: {name} (type={lt})" for lt, idx, name in default])
        return text, default

    avail: List[Tuple[str, int, str]] = []
    lines: List[str] = []
    for idx, det in layout_details.items():
        has_title = det.get("title_idx") is not None
        n = len(det.get("content_indices", []))
        name = det.get("name", f"Layout {idx}")
        if has_title and n == 0:
            lt = "TITLE_ONLY"
        elif has_title and n == 1:
            lt = "SINGLE_CONTENT"
        elif has_title and n == 2:
            lt = "TWO_CONTENT"
        elif has_title and n >= 3:
            lt = "MULTI_CONTENT"
        else:
            continue
        avail.append((lt, idx, name))
        lines.append(f"- idx {idx}: {name} (type={lt}, content_slots={n})")
    return "\n".join(lines), avail


def preferred_layout_index(available_layouts: List[Tuple[str, int, str]], want_type: str, default_idx: int) -> int:
    """
    From the list of (type, idx, name) pick the first matching layout index of 'want_type'.
    If not found, return default_idx.
    """
    for lt, idx, _ in available_layouts:
        if lt == want_type:
            return idx
    return default_idx

system_prompts = """You are an expert technical proposal slide writer with data visualization skills for PowerPoint.
Your output must be a STRICT JSON array of slide objects (no prose, no Markdown fences).

Rules:
1) Scope: Build a complete presentation deck aligned with the RFP and the Supporting (Company) document.
2) Sources: Use only the provided RFP and Supporting files. Do NOT invent clients, partners, or certifications.
3) Language: Follow the language directive provided separately (LANGUAGE_MODE block). Do not mix languages.
4) Style: Slides must be concise and executive-friendly. Use short bullets (<= 15 words each).
5) Data: Extract real numeric values (budgets, dates, KPIs, team sizes) from the files when available.
6) Charts: Place 2–3 chart slides in the middle of the deck using actual numbers from the documents.
7) Output Format: Return ONLY valid JSON (array of slide objects). No extra text before or after the array.

Slide JSON Schema (STRICT):
[
  {
    "layout_type": "TITLE_ONLY" | "SINGLE_CONTENT" | "TWO_CONTENT" | "MULTI_CONTENT" | "CHART",
    "layout_index": <integer>,      // must match the provided template layout indices
    "title": "<string>",
    "content": [                    // OMIT this field entirely for CHART slides
      ["bullet 1", "bullet 2", "bullet 3"],   // slot 1 (string array)
      ["bullet 1", "bullet 2"]                // slot 2 (if slide has another content placeholder)
    ],
    "chart": {                      // REQUIRED only for CHART slides
      "chart_type": "bar" | "column" | "line" | "pie" | "scatter",
      "title": "<string>",
      "data": {                     // EITHER single-series or multi-series (see examples below)
        "labels": ["A", "B", "C"],
        "values": [100, 200, 150]
        // or
        // "series": [{"name":"2023","values":[...]}, {"name":"2024","values":[...]}]
      },
      "x_label": "<string optional>",
      "y_label": "<string optional>"
    }
  },
  ...
]

Chart Examples (STRICT):
1) Single-series BAR:
{
  "chart_type": "bar",
  "title": "Budget Allocation",
  "data": {"labels": ["Personnel","Equipment","Travel"], "values": [450000, 120000, 30000]},
  "x_label": "Category",
  "y_label": "Amount (USD)"
}

2) Multi-series COLUMN:
{
  "chart_type": "column",
  "title": "YoY Comparison",
  "data": {
    "labels": ["Q1","Q2","Q3","Q4"],
    "series": [{"name":"2024","values":[100,140,170,210]},{"name":"2025","values":[120,160,190,230]}]
  },
  "x_label": "Quarter",
  "y_label": "Revenue (k USD)"
}

3) LINE (Timeline):
{
  "chart_type": "line",
  "title": "Project Timeline",
  "data": {"labels": ["M1","M2","M3","M4","M5","M6"], "values": [10,25,45,65,85,100]},
  "x_label": "Month",
  "y_label": "Completion (%)"
}

Strict JSON Rules:
- Output ONLY a JSON array: [ {...}, {...}, ... ]
- NO trailing commas, NO comments, NO code fences.
- All string keys and values in double quotes.
- All numeric values must be numbers (not strings).
- "content" is required for non-CHART slides and must match the number of content placeholders in that layout.
- "chart" must be present only for CHART slides and omitted for others.
"""

def build_task_instructions_with_config(
    *,
    language: str,
    user_config_json: str,
    template_analysis_text: str,
    layout_details: Dict[int, Dict],
    user_config_notes: Optional[str] = None,
) -> str:
    """
    Produces the task-instructions string tailored for our PPT JSON deck generation.
    This is meant to be used in the 'task_instructions' slot of the OpenAI call.

    Parameters:
      - language: "english" or "arabic" (affects guidance text elsewhere via LANGUAGE_MODE)
      - user_config_json: serialized JSON of user preferences / directives (string)
      - template_analysis_text: human-readable analysis of the PPT template (from analyzer)
      - layout_details: dict of layout info from analyzer (indices, title/content placeholders)
      - user_config_notes: free-form notes string (optional)
    """
    layout_text, available_layouts = summarize_available_layouts(layout_details)

    title_idx   = preferred_layout_index(available_layouts, "TITLE_ONLY", 0)
    single_idx  = preferred_layout_index(available_layouts, "SINGLE_CONTENT", 1)
    two_idx     = preferred_layout_index(available_layouts, "TWO_CONTENT", 3)
    multi_idx   = preferred_layout_index(available_layouts, "MULTI_CONTENT", 4)

    slide_plan = (
        f"- Slide 1: TITLE_ONLY (layout_index={title_idx}) for the deck title\n"
        f"- Slides 2–4: SINGLE_CONTENT or TWO_CONTENT (idx={single_idx}/{two_idx}) for intro, objectives, approach\n"
        f"- Slides 5–7: 2–3 CHART slides (use SINGLE_CONTENT idx={single_idx} as base) with REAL numeric data\n"
        f"- Slides 8–12: SINGLE_CONTENT/TWO_CONTENT/MULTI_CONTENT (idx={single_idx}/{two_idx}/{multi_idx}) "
        f"for methodology, team, deliverables, risks, KPIs, compliance\n"
        f"- Final slide: SINGLE_CONTENT (idx={single_idx}) with conclusion/contact"
    )

    notes_block = f'\nUserNotes: "{(user_config_notes or "").strip()}"\n'

    return (
        f"TARGET LANGUAGE: {language}\n"
        f"\nTEMPLATE ANALYSIS (for your awareness):\n{template_analysis_text}\n"
        f"\nAVAILABLE LAYOUTS (type + index):\n{layout_text}\n"
        f"\nUSER CONFIGURATION (JSON):\n{user_config_json or 'null'}\n"
        f"{notes_block}"
        "\nOBJECTIVE:\n"
        "- Generate a complete presentation as a STRICT JSON array of slide objects (see System Prompt schema).\n"
        "- Use ONLY information/figures derivable from the RFP and Supporting files.\n"
        "- If an exact number is not available, infer a realistic figure from context; never output placeholders.\n"
        "\nSLIDE PLAN (use appropriate layout_index values):\n"
        f"{slide_plan}\n"
        "\nCHART REQUIREMENTS:\n"
        "- Include 2–3 chart slides in the middle of the deck (budget breakdown, timeline, resource mix, KPIs, or comparisons).\n"
        "- Use 'bar'/'column' for comparisons and budgets; 'line' for timelines; 'pie' for distributions.\n"
        "- Ensure all labels are strings and all values are numbers.\n"
        "- Omit 'content' field on CHART slides (only 'chart' object is allowed).\n"
        "\nSTRICT OUTPUT:\n"
        "- Return ONLY a JSON array of slides. No prose, no Markdown, no commentary.\n"
        "- Respect the exact schema and JSON rules from the System Prompt.\n"
    )
