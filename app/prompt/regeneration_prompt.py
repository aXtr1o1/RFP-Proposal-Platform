from typing import List, Dict

def build_regen_system_prompt(language: str) -> str:
    return f"""
You are updating an existing proposal presentation. Apply the user comments
precisely and regenerate the slide JSON (same schema). Preserve structure and tone.
All output must be in {language} and ONLY valid JSON array of slide objects.
""".strip()

def build_regen_user_prompt(base_json: str, regen_comments: List[Dict]) -> str:
    comments_txt = "\n".join(
        f"- CHANGE REQUEST:\n  ORIGINAL:\n{c.get('comment1')}\n  INSTRUCTION:\n{c.get('comment2')}\n"
        for c in regen_comments
    )
    return f"""
Here is the current slide JSON:
{base_json}

Apply the following change requests and regenerate the full, corrected slide JSON:
{comments_txt}
Return ONLY the final JSON array (no Markdown).
""".strip()
