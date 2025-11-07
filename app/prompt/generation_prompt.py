from typing import Dict

def get_language_instructions(language: str) -> str:
    return f"""LANGUAGE REQUIREMENT:
All generated content MUST be in {language}. Every title, body text, caption,
and label must use {language} only."""

def build_system_prompt(language: str, template_summary: Dict) -> str:
    layouts_txt = "\n".join(
        f"- {l['index']}: {l['name']} | title={l.get('has_title')} | subtitle={l.get('has_subtitle')} | content_slots={l.get('content_slots')}"
        for l in (template_summary.get("layouts") or [])
    )
    return f"""
You are an expert PowerPoint writer that fits content to an existing template.
Template path: {template_summary.get('path')}

Available TEMPLATE LAYOUTS (index → capability):
{layouts_txt}

RULES:
1) Use one of:
   "TITLE_SLIDE" | "TITLE_ONLY" | "SINGLE_CONTENT" | "TWO_CONTENT" | "CHART" | "IMAGE".
2) Set "layout_index" to a valid index shown above.
3) Constrain bullets to content slots.
4) Title ≤ 60 chars; bullet ≤ 100 chars.
5) Output ONLY VALID JSON (array of slide objects), no Markdown.

SLIDE JSON SCHEMA:
{{
  "layout_type": "...",
  "layout_index": <int>,
  "title": "string",
  "content": [...],
  "notes": "optional",
  "chart_data": {{
    "type": "bar" | "pie" | "line",
    "title": "Chart Title",
    "data": {{"labels": ["A","B"], "values": [10,20]}}
  }},
  "image_path": "optional"
}}

Start with a TITLE_SLIDE and end with a CONCLUSION slide.

{get_language_instructions(language)}
""".strip()

def build_user_prompt(language: str, markdown: str, user_preferences: str) -> str:
    base = f"""
Based on the RFP materials below, generate a complete 10–15 slide proposal in {language}.
Ensure titles and bullets are concise and professional.

SOURCE MATERIAL (Markdown):
---
{markdown}
---
"""
    if user_preferences:
        base += f"\nAdditional user preferences:\n{user_preferences}\n"
    return base.strip()
