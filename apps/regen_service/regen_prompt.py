import os
import json
import logging
from typing import Dict, Any, List

from openai import OpenAI
from dotenv import load_dotenv

from apps.api.services.supabase_service import (
    supabase,
    DATA_TABLE,
    get_generated_markdown,
    save_generated_markdown
)

load_dotenv()
logger = logging.getLogger("regen_prompt")


class MarkdownModifier:
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)
    
    def create_modification_instructions(self, items: List[Dict[str, str]]) -> str:
        """Create clear instructions for content modifications"""
        if not items:
            return "No modifications requested."
        
        instructions = "You must modify ONLY the following specific content pieces in the markdown:\n\n"
        
        for i, item in enumerate(items, 1):
            instructions += f"{i}. FIND THIS EXACT TEXT:\n"
            instructions += f'"{item["selected_content"]}"\n\n'
            instructions += f"MODIFICATION INSTRUCTION: {item['comment']}\n\n"
            instructions += "---\n\n"
        
        instructions += """
                        IMPORTANT RULES:
                        1. Locate each `selected_content` in the markdown **exactly as provided**.
                        2. Apply **only** the modifications specified in the corresponding comment.
                        3. Keep all other content in the markdown **unchanged**.
                        4. Maintain the original **markdown structure** (headers, lists, tables, formatting).
                        5. Ensure the modified content integrates **seamlessly** into the original context.
                        6. Do **not** add any new information, context, or assumptions.
                        7. Do **not** paraphrase or reword untouched sections; keep them **identical**.
                        8. Modify text **only** where an explicit instruction is provided.
                        9. Preserve markdown formatting: `#`, `##`, `###`, `**bold**`, lists (`-`, `1.`), tables (`|`).
                        10. Return ONLY the complete updated markdown — no JSON, no commentary, no extra text.
                        11. Maintain proper spacing and line breaks between sections.
                        """
        return instructions
    
    def process_markdown(self, markdown: str, items: List[Dict[str, str]], language: str) -> str:
        logger.info("Starting OpenAI markdown regeneration")

        modification_instructions = self.create_modification_instructions(items)
        
        system_prompt = f"""You are an expert in technical and development proposal writing.

                        You will receive:
                        1. The full markdown content of a proposal
                        2. Specific content pieces that need modification with their modification instructions

                        Your task:
                        1. Analyze and understand the entire markdown content
                        2. Find each specified content piece in the markdown
                        3. Apply ONLY the requested modifications to those specific pieces
                        4. Keep everything else exactly the same
                        5. Maintain all markdown formatting (headers, lists, tables, bold, etc.)
                        6. Generate output only in this language: {language}
                        7. Maintain correct spacing between words
                        8. Return ONLY the complete updated Github markdown — no JSON, no explanations, no wrappers

                        CRITICAL: Your output must be pure GitHub-flavored markdown that can be rendered directly."""

        user_prompt = f"""
                        ORIGINAL MARKDOWN:
                        {markdown}

                        MODIFICATION INSTRUCTIONS:
                        {modification_instructions}

                        Process this markdown and return the complete updated version with only the specified modifications applied.
                        Return ONLY the updated markdown — no JSON, no commentary, no code blocks.
                        """

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3
            )
            
            content = response.choices[0].message.content
            if not content:
                raise ValueError("Empty response from OpenAI")
            content = content.strip()
            if content.startswith("```"):
                content = content[3:].strip()
            if content.endswith("```"):
                content = content[:-3].strip()
            
            logger.info(f"Markdown regenerated successfully, length: {len(content)} chars")
            return content
            
        except Exception as e:
            logger.exception("Error processing with OpenAI")
            raise Exception(f"Error processing with OpenAI: {str(e)}")


def get_comments_for_uuid(uuid: str) -> List[Dict[str, str]]:
    try:
        logger.info(f"Fetching comments for uuid={uuid}")
        res = supabase.table("Comments").select("selected_content, comment").eq("uuid", uuid).execute()
        items = res.data if res.data else []
        
        logger.info(f"Found {len(items)} comments for uuid={uuid}")
        return items
        
    except Exception as e:
        logger.error(f"Failed to fetch comments for uuid={uuid}: {e}")
        raise

def regenerate_markdown_with_comments(
    uuid: str,
    language: str = "english"
) -> Dict[str, Any]:
    try:
        logger.info(f"Fetching existing markdown for uuid={uuid}")
        original_markdown = get_generated_markdown(uuid)
        if not original_markdown:
            raise ValueError(f"No generated markdown found for uuid={uuid}. Run /initialgen first.")
        
        logger.info(f"Original markdown length: {len(original_markdown)} chars")
        
        comments = get_comments_for_uuid(uuid)
        if not comments:
            logger.warning(f"No comments found for uuid={uuid}, returning original markdown")
            return {
                "status": "success",
                "uuid": uuid,
                "updated_markdown": original_markdown,
                "modifications_applied": 0,
                "message": "No modifications to apply"
            }
        
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("Missing OPENAI_API_KEY in environment variables")
        
        modifier = MarkdownModifier(api_key)
        updated_markdown = modifier.process_markdown(
            markdown=original_markdown,
            items=comments,
            language=language
        )
        
        logger.info(f"Updated markdown length: {len(updated_markdown)} chars")
        
        logger.info(f"Saving updated markdown to Supabase for uuid={uuid}")
        saved = save_generated_markdown(uuid, updated_markdown)
        if not saved:
            raise Exception("Failed to save updated markdown to Supabase")
        
        logger.info(f"Successfully saved updated markdown for uuid={uuid}")
        
        return {
            "status": "success",
            "uuid": uuid,
            "updated_markdown": updated_markdown,
            "modifications_applied": len(comments),
            "language": language
        }
    
    except Exception as e:
        logger.exception(f"Markdown regeneration failed for uuid={uuid}")
        raise
