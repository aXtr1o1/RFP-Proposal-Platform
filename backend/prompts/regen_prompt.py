from typing import List, Dict
import json

def build_regen_system_prompt() -> str:
    return """You are a precise PowerPoint content editor specializing in selective modifications.
            TASK: CONTENT MODIFICATION ONLY
            You will receive:
            1. ORIGINAL SLIDES (complete JSON array)
            2. MODIFICATION REQUESTS (user comments specifying what to change)

            YOUR RESPONSIBILITIES:
            - Locate the exact content specified in each modification request
            - Apply the requested changes precisely
            - Preserve ALL other content exactly as it was
            - Maintain the same slide count and structure
            - Keep the same layout types and indices

            CRITICAL RULES:
            1. DO NOT add new slides - preserve slide count
            2. DO NOT change themes - preserve layout_type and layout_index
            3. ONLY modify content explicitly mentioned in requests
            4. Maintain all chart specifications unless specifically modified
            5. Preserve JSON structure and format
            6. Output COMPLETE JSON array (all slides with modifications applied)

            MODIFICATION SCOPE:
            ✓ Title text changes
            ✓ Bullet point content updates
            ✓ Chart data modifications
            ✓ Text replacements
            ✗ Adding new slides
            ✗ Removing slides
            ✗ Changing themes/layouts (unless content requires different layout)

            OUTPUT FORMAT:
            - Valid JSON array with same structure as input
            - All slides included (modified + unmodified)
            - Same JSON schema as original
            - NO markdown fences, NO explanations

            Begin."""


def build_regen_task_prompt(
    original_slides: List[Dict],
    regen_comments: List[Dict[str, str]],
    template_info: str,
    language: str = "english"
) -> str:
    original_json_str = json.dumps(original_slides, indent=2, ensure_ascii=False)
    modifications_text = format_modification_requests(regen_comments)
    lang_instruction = (
        "OUTPUT LANGUAGE: ENGLISH (Keep all content in English)"
        if language.lower() == "english"
        else "OUTPUT LANGUAGE: ARABIC (Modern Standard Arabic - keep all content in Arabic)"
    )
    
    return f"""REGENERATION TASK
            ================================================================================
            ORIGINAL PRESENTATION JSON:
            ================================================================================
            {original_json_str}

            ================================================================================
            MODIFICATION REQUESTS:
            ================================================================================
            {modifications_text}

            ================================================================================
            TEMPLATE LAYOUT INFORMATION:
            ================================================================================
            {template_info}

            ================================================================================
            LANGUAGE REQUIREMENT:
            ================================================================================
            {lang_instruction}

            ================================================================================
            INSTRUCTIONS:
            ================================================================================
            1. Review each modification request carefully
            2. Locate the original_content in the specified slide
            3. Apply the modification exactly as described
            4. Keep all other content unchanged
            5. Preserve slide structure (layout_type, layout_index, chart specs)
            6. Output complete JSON array with ALL slides (modified + unmodified)

            VALIDATION CHECKLIST:
            ☐ Same number of slides as original
            ☐ All unmodified slides preserved exactly
            ☐ Requested modifications applied correctly
            ☐ JSON structure maintained
            ☐ No markdown fences or explanations

            BEGIN REGENERATION NOW. Output ONLY the JSON array:
            """


def format_modification_requests(regen_comments: List[Dict[str, str]]) -> str:
    if not regen_comments:
        return "(No modifications requested)"
    
    formatted_lines = []
    
    for i, comment in enumerate(regen_comments, 1):
        slide_num = comment.get("slide", "?")
        original = comment.get("original_content", "")
        modification = comment.get("modification", "")
        location = comment.get("location", "auto-detect")
        
        formatted_lines.append(
            f"MODIFICATION #{i}:\n"
            f"  Slide Number: {slide_num}\n"
            f"  Location: {location}\n"
            f"  Find Content: \"{original}\"\n"
            f"  Apply Change: \"{modification}\"\n"
        )
    
    return "\n".join(formatted_lines)


def build_modification_summary(regen_comments: List[Dict[str, str]]) -> str:
    slide_nums = [str(c.get("slide", "?")) for c in regen_comments]
    return f"{len(regen_comments)} modification(s) on slide(s): {', '.join(slide_nums)}"