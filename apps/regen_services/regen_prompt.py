import os
import json
import logging
from typing import Dict, Any, List,Optional

from openai import OpenAI
from dotenv import load_dotenv

from apps.api.services.supabase_service import (
    supabase,
    save_generated_markdown
)
from apps.wordgenAgent.app.document import generate_word_and_pdf_from_markdown
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
            logger.info(f'Content, Comments: {item}')
            instructions += f"{i}. FIND THIS EXACT TEXT:\n"
            instructions += f"{item.get('comment1')}"
            instructions += f"\n\nMODIFICATION INSTRUCTION: {item.get('comment2')}\n\n"
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
        
        # System prompt
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
                        8. Return ONLY the complete updated markdown — no JSON, no explanations, no wrappers

                        CRITICAL: Your output must be pure GitHub-flavored markdown that can be rendered directly."""
        
        # user prompt
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
            
            logger.info(f"Markdown regenerated successfully, length: {len(content)} chars")
            return content
            
        except Exception as e:
            logger.exception("Error processing with OpenAI")
            raise Exception(f"Error processing with OpenAI: {str(e)}")


def get_generated_markdown_from_data_table(uuid: str) -> str:
    try:
        logger.info(f"Fetching Generated_Markdown from Data_Table for uuid={uuid}")
        
        res = supabase.table("Data_Table").select("Generated_Markdown").eq("uuid", uuid).maybe_single().execute()
        
        if not res.data:
            raise ValueError(f"No record found in Data_Table for uuid={uuid}")
        
        markdown = res.data.get("Generated_Markdown", "")
        
        if not markdown:
            raise ValueError(f"Generated_Markdown is empty for uuid={uuid}")
        
        logger.info(f"Successfully fetched markdown for uuid={uuid}, length: {len(markdown)} chars")
        return markdown
        
    except Exception as e:
        logger.error(f"Failed to fetch Generated_Markdown for uuid={uuid}: {e}")
        raise


def get_comments_for_uuid(uuid: str) -> List[Dict[str, str]]:
    try:
        logger.info(f"Fetching comments for uuid={uuid}")
        res = supabase.table("proposal_comments").select("comments").eq("uuid", uuid).execute()
        print("List:", res.data)
        items = res.data[0].get('comments') if res.data else []
    
        
        logger.info(f"Returning {len(items)} valid comments for uuid={uuid}")
        return items
        
    except Exception as e:
        logger.error(f"Failed to fetch comments for uuid={uuid}: {e}")
        return []


def regenerate_markdown_with_comments(
    uuid: str,
    docConfig: Dict[str,any],
    language: str = "english",
 
    
) -> Dict[str, Any]:
    try:
        logger.info(f"Fetching existing markdown for uuid={uuid}")
        original_markdown = get_generated_markdown_from_data_table(uuid)
        
        logger.info(f"Original markdown length: {len(original_markdown)} chars")
    
        comments = get_comments_for_uuid(uuid)
        logger.info(f"Comments from supabase:{comments}")

        if not comments:
            logger.warning(f"No valid comments found for uuid={uuid}, returning original markdown")
            return {
                "status": "success",
                "uuid": uuid,
                "updated_markdown": original_markdown,
                "modifications_applied": 0,
                "message": "No modifications to apply"
            }
        
        logger.info(f"Processing {len(comments)} modifications")
    
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
        
        logger.info(f"Saving updated markdown to Data_Table for uuid={uuid}")
        saved = save_generated_markdown(uuid, updated_markdown)
        if not saved:
            raise Exception("Failed to save updated markdown to Supabase")
        
        logger.info(f"Successfully saved updated markdown for uuid={uuid}")
        urls = generate_word_and_pdf_from_markdown(
            uuid=uuid,
            markdown=updated_markdown,
            doc_config=docConfig,
            language=(language or "english").lower()
        )
        return {
            "status": "success",
            "uuid": uuid,
            "updated_markdown": updated_markdown,
            "modifications_applied": len(comments),
            "language": language,
            "wordLink":urls['proposal_word_url'],
            "pdfLink":urls['proposal_pdf_url']
        }
    
    except Exception as e:
        logger.exception(f"Markdown regeneration failed for uuid={uuid}")
        raise
