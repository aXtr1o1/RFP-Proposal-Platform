"""
Prompt builders for presentation generation and regeneration.
Used by openai_service (initial generation) and ppt_regeneration (feedback-based regeneration).
"""

from typing import List, Dict, Any


def get_system_prompt(language: str, template_id: str) -> str:
    """
    System instructions for generating a presentation as structured data (PresentationData).
    """
    lang_instruction = (
        "Output the entire presentation in Arabic (RTL). Use Arabic for title, subtitle, and all slide titles and content."
        if language and language.lower() in ("arabic", "ar")
        else "Output the entire presentation in English. Use English for title, subtitle, and all slide titles and content."
    )
    return f"""You are an expert presentation designer. Your task is to convert the user's content into a structured presentation specification.

{lang_instruction}

Template: {template_id}. Use layout types supported by this template: title, content, section, bullets, paragraph, table, chart, agenda, two_column, comparison, blank.

Rules:
- First slide is the title slide (title, subtitle, optional author).
- Use "section" or "section_header" for major section dividers (one short title per slide).
- Use "agenda" for an agenda slide when the content lists topics; put agenda items as bullets.
- Use "content" or "bullets" for slides with bullet points; keep titles concise (<= 100 chars).
- Use "table" when the content is tabular; provide headers and rows.
- Use "chart" when the content describes data to visualize; provide chart_type (bar, column, line, pie), categories, and series (name + values).
- Use "paragraph" for prose or long text without bullets.
- Preserve the user's meaning and structure. Be concise. No placeholder or lorem text.
- Each slide must have a title. Use layout_type and optionally layout_hint to match the template.
- For charts: include title, categories, and at least one series with name and values.
- For tables: include headers and rows as lists of strings.
- For bullets: use BulletPoint with text and optional sub_bullets (list of strings).
"""


def get_user_prompt(
    markdown_content: str,
    language: str,
    user_preference: str = "",
) -> str:
    """
    User prompt for initial presentation generation from markdown.
    """
    pref = f"\n\nUser preferences: {user_preference}" if user_preference else ""
    return f"""Convert the following content into a structured presentation. Output valid JSON matching the PresentationData schema (title, subtitle, author, language, slides array). Each slide: title, layout_type, and the appropriate content (bullets, paragraph, table_data, chart_data, etc.).{pref}

Content:
---
{markdown_content}
---
"""


def get_regeneration_prompt(
    markdown_content: str,
    language: str,
    regen_comments: List[Dict[str, str]],
    user_preference: str = "",
) -> str:
    """
    User prompt for regeneration: apply feedback comments to the existing (markdown) content
    and output updated PresentationData.
    """
    comments_text = "\n".join(
        f"- {c.get('slide', 'General')}: {c.get('comment', c.get('feedback', ''))}"
        for c in regen_comments
    )
    pref = f"\n\nUser preferences: {user_preference}" if user_preference else ""
    return f"""Apply the following feedback to the presentation. Regenerate the full presentation structure (PresentationData JSON) incorporating these changes. Keep everything that was not mentioned in the feedback.{pref}

Feedback:
{comments_text}

Original content (for context):
---
{markdown_content[:12000]}
---
Output the complete updated presentation as structured data (PresentationData)."""
