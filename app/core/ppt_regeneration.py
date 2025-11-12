import logging
import json
import os
from uuid import uuid4
from typing import Dict, Any, List, Optional
from pathlib import Path

from services.pptx_generator import PptxGenerator
from services.openai_service import get_openai_service
from core.supabase_service import SupabaseService
from core.ppt_prompts import get_system_prompt, get_regeneration_prompt
from config import settings
from models.presentation import PresentationData

logger = logging.getLogger("ppt_regeneration")


async def run_regeneration(
    uuid: str,
    gen_id: str,
    base_ppt_genid: str,
    language: str,
    template_id: str,
    regen_comments: List[Dict[str, str]]
) -> Dict[str, Any]:
    """
    Regenerate presentation with feedback using local backend template
    """
    output_path: Optional[str] = None
    new_ppt_genid: Optional[str] = None
    
    try:
        logger.info("="*80)
        logger.info("PPT REGENERATION")
        logger.info("="*80)
        logger.info(f"   UUID: {uuid}")
        logger.info(f"   Gen ID: {gen_id}")
        logger.info(f"   Base PPT Gen ID: {base_ppt_genid}")
        logger.info(f"   Language: {language}")
        logger.info(f"   Template ID: {template_id}")
        logger.info(f"   Template Path: {Path(settings.TEMPLATES_DIR) / template_id}")
        logger.info(f"   Feedback comments: {len(regen_comments)}")
        logger.info("="*80)
        
        # Validate inputs
        if not uuid or not gen_id or not base_ppt_genid:
            raise ValueError("UUID, Gen ID, and Base PPT Gen ID are required")
        
        if not regen_comments:
            raise ValueError("Regeneration comments are required")
        
        if language not in ["English", "Arabic"]:
            raise ValueError(f"Invalid language: {language}. Must be English or Arabic")
        
        # Validate template
        template_path = Path(settings.TEMPLATES_DIR) / template_id
        if not template_path.exists():
            raise FileNotFoundError(f"Template '{template_id}' not found at {template_path}")
        
        logger.info(f"Template found: {template_path}")
        
        # Initialize services
        supabase = SupabaseService()
        openai_service = get_openai_service()
        
        # STEP 1: Fetch markdown
        logger.info("\nSTEP 1: Fetching original markdown...")
        markdown_content = await supabase.fetch_markdown_content(uuid, gen_id)
        
        if not markdown_content or len(markdown_content) < 10:
            raise ValueError("Markdown content is empty or too short")
        
        logger.info(f"Fetched: {len(markdown_content)} characters")
        
        # STEP 2: Fetch previous content
        logger.info("\nSTEP 2: Fetching previous generation...")
        prev_content = await supabase.get_generation_content(uuid, gen_id, base_ppt_genid)
        prev_template = prev_content.get("template_id", "standard")
        
        logger.info(f"Previous generation retrieved")
        logger.info(f"   Previous template: {prev_template}")
        logger.info(f"   New template: {template_id}")
        
        # STEP 3: Display feedback
        logger.info("\nSTEP 3: User Feedback:")
        for idx, comment in enumerate(regen_comments, 1):
            logger.info(f"   {idx}. {comment['comment1']}: {comment['comment2']}")
        
        # STEP 4: Regenerate with OpenAI (FIXED: Single API call with structured output)
        logger.info(f"\nSTEP 4: Regenerating with OpenAI...")
        logger.info(f"   Mode: Single structured API call (streaming disabled for parsing)")
        logger.info(f"   FIXED: No more double API calls")
        
        system_prompt = get_system_prompt(language, template_id)
        user_prompt = get_regeneration_prompt(
            markdown_content=markdown_content,
            language=language,
            regen_comments=regen_comments,
            user_preference=""
        )
        
        # FIXED: Single API call with structured output (no double call)
        logger.info("   Calling OpenAI with structured output...")
        parse_response = await openai_service.client.beta.chat.completions.parse(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format=PresentationData,
            temperature=0.3,
            max_tokens=8000,
        )
        
        presentation_data = parse_response.choices[0].message.parsed
        
        if not presentation_data or not presentation_data.slides:
            raise RuntimeError("OpenAI returned empty presentation data")
        
        logger.info(f"Regenerated: {presentation_data.title}")
        logger.info(f"   Total slides: {len(presentation_data.slides)}")
        
        # Calculate stats (reuse from ppt_generation)
        from core.ppt_generation import _calculate_presentation_stats
        stats = _calculate_presentation_stats(presentation_data)
        
        logger.info(f"   • Section headers: {stats['sections']}")
        logger.info(f"   • Content slides: {stats['content_slides']}")
        logger.info(f"   • Charts: {stats['charts']}")
        logger.info(f"   • Tables: {stats['tables']}")
        logger.info(f"   • Images to generate: {stats['images']}")
        
        # STEP 5: Generate new PPTX with local template
        new_ppt_genid = str(uuid4())
        
        logger.info(f"\n STEP 5: Creating PPTX with local template '{template_id}'...")
        logger.info(f"   Template directory: {template_path}")
        
        generator = PptxGenerator(template_id=template_id)
        output_path = generator.generate(
            presentation_data,
            generate_images=True
        )
        
        logger.info(f"PPTX generated: {output_path}")
        
        # STEP 6: Upload
        logger.info("\n STEP 6: Uploading to Supabase...")
        ppt_url = await supabase.upload_pptx(output_path, uuid, gen_id, new_ppt_genid)
        logger.info(f"Uploaded: {ppt_url}")
        
        # STEP 7: Save record
        logger.info("\n STEP 7: Saving regeneration record...")
        generated_content = {
            "title": presentation_data.title,
            "subtitle": presentation_data.subtitle,
            "template_id": template_id,
            "template_path": str(template_path),
            "language": language,
            "slides": [slide.model_dump() for slide in presentation_data.slides],
            "base_ppt_genid": base_ppt_genid,
            "regen_comments": regen_comments,
            "stats": stats
        }
        
        await supabase.save_regeneration_record(
            uuid_str=uuid,
            gen_id=gen_id,
            ppt_genid=new_ppt_genid,
            ppt_url=ppt_url,
            generated_content=generated_content,
            language=language,
            regen_comments=regen_comments
        )
        
        logger.info(f"Record saved: {new_ppt_genid}")
        
        # STEP 8: Cleanup (FIXED: delete local PPTX file after upload)
        from core.ppt_generation import _cleanup_temp_file
        _cleanup_temp_file(output_path)
        
        logger.info("\n" + "="*80)
        logger.info("REGENERATION COMPLETE")
        logger.info("="*80)
        logger.info(f"   New PPT Gen ID: {new_ppt_genid}")
        logger.info(f"   PPT URL: {ppt_url}")
        logger.info(f"   Template: {template_id}")
        logger.info(f"   Base PPT Gen ID: {base_ppt_genid}")
        logger.info("="*80 + "\n")
        
        return {
            "ppt_genid": new_ppt_genid,
            "ppt_url": ppt_url,
            "generated_content": json.dumps(generated_content)
        }
    
    except Exception as e:
        logger.exception(" Regeneration failed")
        
        # ROLLBACK: Cleanup on failure
        if output_path:
            from core.ppt_generation import _cleanup_temp_file
            _cleanup_temp_file(output_path)

