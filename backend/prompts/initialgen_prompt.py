from typing import Optional, Dict, Tuple, List

def build_language_block(language: str) -> str:
    """
    Compact language directive block consumed as the first content part.
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


def summarize_available_layouts(layout_details: Dict[int, Dict]) -> Tuple[str, List[Tuple[str, int, str, int]]]:
    """
    Build a one-line-per-layout description string and a typed list of available layout tuples:
    """
    if not layout_details:
        default = [
            ("TITLE_ONLY",     0, "Title Slide",         0),
            ("SINGLE_CONTENT", 1, "Title and Content",   1),
            ("TWO_CONTENT",    2, "Two Content",         2),
            ("MULTI_CONTENT",  3, "Multi Content",       3),
        ]
        text = "\n".join([f"- idx {idx}: {name} (type={lt}, content_slots={slots})" for lt, idx, name, slots in default])
        return text, default

    avail: List[Tuple[str, int, str, int]] = []
    lines: List[str] = []
    for idx, det in layout_details.items():
        has_title = det.get("title_idx") is not None
        n = len(det.get("content_indices", []))
        name = det.get("name", f"Layout {idx}")
        lt: Optional[str] = None
        if has_title and n == 0:
            lt = "TITLE_ONLY"
        elif has_title and n == 1:
            lt = "SINGLE_CONTENT"
        elif has_title and n == 2:
            lt = "TWO_CONTENT"
        elif has_title and n >= 3:
            lt = "MULTI_CONTENT"

        if lt is None:
            continue

        avail.append((lt, idx, name, n))
        lines.append(f"- idx {idx}: {name} (type={lt}, content_slots={n})")

    return "\n".join(lines), avail


def preferred_layout_index(available_layouts: List[Tuple[str, int, str, int]], want_type: str, default_idx: int) -> int:
    """
    From the list of (type, idx, name, slots) pick the first matching layout index of 'want_type'.
    """
    want_type = (want_type or "").upper()
    for lt, idx, _, _ in available_layouts:
        if lt == want_type:
            return idx
    return default_idx

def build_system_prompt(*, language: str, template_analysis_text: str, layout_details: Dict[int, Dict]) -> str:
    """
    Builds a strict system prompt that:
      - Enforces “content arrays per layout” contract
      - Defines CHART schema consistently (optional single caption array allowed)
      - Ties layout_index to actual template indices
    """
    lang_block = build_language_block(language)
    layout_text, available_layouts = summarize_available_layouts(layout_details)

    title_idx  = preferred_layout_index(available_layouts, "TITLE_ONLY", 0)
    single_idx = preferred_layout_index(available_layouts, "SINGLE_CONTENT", 1)
    two_idx    = preferred_layout_index(available_layouts, "TWO_CONTENT", 2)
    multi_idx  = preferred_layout_index(available_layouts, "MULTI_CONTENT", 3)

    return f"""{lang_block}

You are an expert technical proposal slide writer with data visualization skills for PowerPoint.
Your output MUST be a STRICT JSON array of slide objects (no prose, no Markdown fences).

SCOPE & RULES:
1) Scope: Build a complete presentation deck aligned with the RFP and the Supporting (Company) document.
2) Sources: Use only the provided RFP and Supporting files. Do NOT invent clients, partners, or certifications.
3) Language: Follow the LANGUAGE_MODE above. Do not mix languages.
4) Style: Slides must be concise and executive-friendly. Use short bullets (≤ 15 words each).
5) Data: Extract real numeric values (budgets, dates, KPIs, team sizes) when available; otherwise infer realistic figures grounded in the documents.
6) Charts: Place 2–3 chart slides in the middle of the deck using actual numbers from the documents.
7) Output Format: Return ONLY valid JSON (array of slide objects). No extra text before or after the array.

TEMPLATE LAYOUTS (type + index + slots):
{layout_text}

CONTENT ARRAYS PER LAYOUT (CRITICAL CONTRACT):
- "TITLE_ONLY": content MUST be [] (exactly zero arrays).
- "SINGLE_CONTENT": content MUST be a SINGLE array of bullets, e.g. ["bullet 1","bullet 2"]. DO NOT return multiple arrays.
- "TWO_CONTENT": content MUST be TWO arrays, e.g. [ ["left bullet 1",...], ["right bullet 1",...] ].
- "MULTI_CONTENT": content MUST have EXACTLY the same number of arrays as the layout’s content placeholders in THIS template.
- "CHART": you MAY include a single optional caption array in "content" (e.g., ["Key message 1","Key message 2"]); otherwise set "content": [].

SLIDE JSON SCHEMA (STRICT):
[
  {{
    "layout_type": "TITLE_ONLY" | "SINGLE_CONTENT" | "TWO_CONTENT" | "MULTI_CONTENT" | "CHART",
    "layout_index": <integer>,      // must match the template's indices above
    "title": "<string>",
    "content": [ <array(s) of bullet strings per content placeholder> ],
    "chart": {{                      // REQUIRED only for CHART slides
      "chart_type": "bar" | "column" | "line" | "pie" | "scatter",
      "title": "<string>",
      "data": {{
        // EITHER single-series:
        "labels": ["A","B","C"], "values": [100,200,150]
        // OR multi-series:
        // "labels": ["Q1","Q2","Q3","Q4"],
        // "series": [{{"name":"2024","values":[...] }}, {{"name":"2025","values":[...] }}]
      }},
      "x_label": "<string optional>",
      "y_label": "<string optional>"
    }}
  }},
  ...
]

STRICT JSON RULES:
- Output ONLY a JSON array: [ {{...}}, {{...}} ].
- NO trailing commas, NO comments, NO code fences.
- All keys/strings in double quotes; numeric values as numbers (not strings).
- "content" is REQUIRED for non-CHART slides and MUST match the target placeholder count (per layout_type and layout_index).
- "chart" MUST be present ONLY for CHART slides and omitted for others.

GUIDANCE FOR LAYOUT INDEX CHOICES:
- Prefer: TITLE_ONLY → idx {title_idx}; SINGLE_CONTENT → idx {single_idx}; TWO_CONTENT → idx {two_idx}; MULTI_CONTENT → idx {multi_idx}.
- If a recommended index does not exist, use the closest valid index of that layout_type from the list above.

TEMPLATE ANALYSIS CONTEXT:
{template_analysis_text}
"""

def build_task_instructions_with_config(
    *,
    language: str,
    user_config_json: str,
    template_analysis_text: str,
    layout_details: Dict[int, Dict],
    template_overview_for_order: Optional[List[Dict]] = None,
    user_config_notes: Optional[str] = None,
) -> str:
    """
    Builds the task prompt
    """
    layout_text, available_layouts = summarize_available_layouts(layout_details)
    title_idx   = preferred_layout_index(available_layouts, "TITLE_ONLY", 0)
    single_idx  = preferred_layout_index(available_layouts, "SINGLE_CONTENT", 1)
    two_idx     = preferred_layout_index(available_layouts, "TWO_CONTENT", 2)
    multi_idx   = preferred_layout_index(available_layouts, "MULTI_CONTENT", 3)

    order_block = ""
    if template_overview_for_order:
        order_lines = []
        for d in template_overview_for_order:
            hints = ", ".join(d.get("hints", [])[:2])
            order_lines.append(f"- Slide {d.get('slide_index')}: {hints}")
        order_block = "TEMPLATE HINTS (ordered):\n" + "\n".join(order_lines) + "\n"

    slide_plan = (
        f"- Slide 1: TITLE_ONLY (layout_index={title_idx}) → deck title\n"
        f"- Slides 2–4: SINGLE_CONTENT or TWO_CONTENT (idx={single_idx}/{two_idx}) → intro, objectives, approach\n"
        f"- Slides 5–7: 2–3 CHART slides (use indices that best fit charts) with REAL numeric data\n"
        f"- Slides 8–12: SINGLE_CONTENT/TWO_CONTENT/MULTI_CONTENT (idx={single_idx}/{two_idx}/{multi_idx}) "
        f"→ methodology, team, deliverables, risks, KPIs, compliance\n"
        f"- Final slide: SINGLE_CONTENT (idx={single_idx}) → conclusion/contact"
    )

    notes_block = f'UserNotes: "{(user_config_notes or "").strip()}"\n' if user_config_notes else ""

    return (
        f"TARGET LANGUAGE: {language}\n"
        f"\n{order_block}"
        f"AVAILABLE LAYOUTS (type + index):\n{layout_text}\n"
        f"\nUSER CONFIGURATION (JSON):\n{user_config_json or 'null'}\n"
        f"{notes_block}"
        f"{template_analysis_text}"
        "\nOBJECTIVE:\n"
        "- Generate a complete presentation as a STRICT JSON array of slide objects (see System Prompt schema).\n"
        "- Use ONLY information/figures derivable from the RFP and Supporting files. If an exact number is not available, infer a realistic figure from context (no placeholders).\n"
        "\nSLIDE PLAN (choose appropriate layout_index values):\n"
        f"{slide_plan}\n"
        "\nCHART REQUIREMENTS:\n"
        "- Include 2–3 chart slides in the middle of the deck (budget breakdown, timeline, resource mix, KPIs, comparisons).\n"
        "- Use 'bar'/'column' for comparisons and budgets; 'line' for timelines; 'pie' for distributions; 'scatter' for correlations.\n"
        "- Ensure labels are strings and values are numbers. If multi-series, include 'series'.\n"
        "- For CHART slides, you MAY include a single optional caption array in 'content'; otherwise set it to [].\n"
        "\nSTRICT OUTPUT:\n"
        "- Return ONLY a JSON array of slides. No prose, no Markdown, no commentary.\n"
        "- Obey the CONTENT ARRAYS PER LAYOUT contract (SINGLE_CONTENT → exactly ONE array; TWO_CONTENT → exactly TWO arrays; etc.).\n"
    )
