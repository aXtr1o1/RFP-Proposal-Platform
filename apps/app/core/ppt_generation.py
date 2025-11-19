import logging
import json
import os
from uuid import uuid4
from typing import Dict, Any, Optional
from pathlib import Path

from apps.app.services.pptx_generator import PptxGenerator
from apps.app.services.openai_service import get_openai_service
from apps.app.core.supabase_service import SupabaseService
from apps.app.config import settings

logger = logging.getLogger("ppt_generation")


async def run_initial_generation(
    uuid: str,
    gen_id: str,
    language: str,
    template_id: str,
    user_preference: str = ""
) -> Dict[str, Any]:
    """
    Generate complete presentation using local backend template
    """
    output_path: Optional[str] = None
    ppt_genid: Optional[str] = None
    
    try:
        logger.info("="*80)
        logger.info("INITIAL PPT GENERATION")
        logger.info("="*80)
        logger.info(f"   UUID: {uuid}")
        logger.info(f"   Gen ID: {gen_id}")
        logger.info(f"   Language: {language}")
        logger.info(f"   Template ID: {template_id}")
        logger.info(f"   Template Path: {Path(settings.TEMPLATES_DIR) / template_id}")
        logger.info("="*80)
        
        # Validate inputs
        if not uuid or not gen_id:
            raise ValueError("UUID and Gen ID are required")
        
        if language not in ["English", "Arabic"]:
            raise ValueError(f"Invalid language: {language}. Must be English or Arabic")
        
        # Validate template exists
        template_path = Path(settings.TEMPLATES_DIR) / template_id
        if not template_path.exists():
            raise FileNotFoundError(
                f"Template '{template_id}' not found at {template_path}. "
                f"Ensure template directory exists with config.json, layouts.json, theme.json"
            )
        
        logger.info(f"Template found: {template_path}")
        
        # Check required template files
        required_files = ["config.json", "layouts.json", "theme.json"]
        missing_files = [f for f in required_files if not (template_path / f).exists()]
        
        if missing_files:
            logger.warning(f"Missing template files: {missing_files}")
        else:
            logger.info(f"All template files present: {required_files}")
        
        # Initialize services
        supabase = SupabaseService()
        openai_service = get_openai_service()
        
        # STEP 1: Fetch markdown
        logger.info("\nSTEP 1: Fetching markdown from Supabase...")
        markdown_content = await supabase.fetch_markdown_content(uuid, gen_id)
        
        if not markdown_content or len(markdown_content) < 10:
            raise ValueError("Markdown content is empty or too short")
        
        logger.info(f"Fetched: {len(markdown_content)} characters")
        
        # STEP 2: Generate structure with OpenAI (streaming enabled)
        logger.info(f"\nSTEP 2: Generating presentation structure...")
        logger.info(f"   Model: {settings.OPENAI_MODEL}")
        logger.info(f"   Language: {language}")
        logger.info(f"   Template: {template_id}")
        logger.info(f"   Streaming: Enabled")
        
        presentation_data = await openai_service.generate_presentation_structure(
            markdown_content=markdown_content,
            template_id=template_id,
            language=language,
            user_preference=user_preference,
            stream_output=True
        )
        
        if not presentation_data or not presentation_data.slides:
            raise RuntimeError("OpenAI returned empty presentation data")
        
        logger.info(f"\nStructure generated: {presentation_data.title}")
        logger.info(f"   Total slides: {len(presentation_data.slides)}")
        
        # STEP 2.5: Calculate stats ONCE (FIXED: removed duplicate calculation)
        stats = _calculate_presentation_stats(presentation_data)
        
        logger.info(f"   • Section headers: {stats['sections']}")
        logger.info(f"   • Content slides: {stats['content_slides']}")
        logger.info(f"   • Charts: {stats['charts']}")
        logger.info(f"   • Tables: {stats['tables']}")
        logger.info(f"   • Images to generate: {stats['images']}")
        
        # STEP 3: Generate PPTX with local template
        logger.info(f"\nSTEP 3: Creating PPTX with local template '{template_id}'...")
        logger.info(f"   Template directory: {template_path}")
        logger.info(f"   Including:")
        logger.info(f"      Template styling (colors, fonts, layouts)")
        logger.info(f"      Icons ({stats['icons_count']} slides)")
        logger.info(f"      Images (generating {stats['images']} via DALL-E)")
        logger.info(f"      Charts ({stats['charts']} native PowerPoint charts)")
        logger.info(f"      Tables ({stats['tables']} styled tables)")
        
        ppt_genid = str(uuid4())
        
        # PptxGenerator will load local template from app/templates/{template_id}/
        generator = PptxGenerator(template_id=template_id, language=language)
        output_path = generator.generate(
            presentation_data
        )
        
        logger.info(f"PPTX generated: {output_path}")
        
        # STEP 4: Upload to Supabase
        logger.info(f"\n STEP 4: Uploading to Supabase storage...")
        ppt_url = await supabase.upload_pptx(output_path, uuid, gen_id, ppt_genid)
        logger.info(f"Uploaded: {ppt_url}")
        
        # STEP 5: Save record
        logger.info(f"\nSTEP 5: Saving generation record...")
        generated_content = {
            "title": presentation_data.title,
            "template_id": template_id,
            "language": language,
            "slides": [slide.model_dump() for slide in presentation_data.slides],
            "stats": stats 
        }
        
        await supabase.save_generation_record(
            uuid_str=uuid,
            gen_id=gen_id,
            ppt_genid=ppt_genid,
            ppt_url=ppt_url,
            generated_content=generated_content,
            language=language,
            template_id=template_id,  
            user_preference=user_preference
        )
        logger.info("\n" + "="*80)
        logger.info(f"Record saved: {ppt_genid}")
        logger.info("="*80)
        
        # STEP 6: Cleanup (FIXED: delete local PPTX file after upload)
        _cleanup_temp_file(output_path)
        
        logger.info("\n" + "="*80)
        logger.info("INITIAL GENERATION COMPLETE")
        logger.info("="*80)
        logger.info(f"   PPT Gen ID: {ppt_genid}")
        logger.info(f"   PPT URL: {ppt_url}")
        logger.info(f"   Template: {template_id}")
        logger.info(f"   Language: {language}")
        logger.info("="*80 + "\n")
        
        return {
            "ppt_genid": ppt_genid,
            "ppt_url": ppt_url,
            "generated_content": json.dumps(generated_content)
        }
    
    except Exception as e:
        logger.exception("Initial generation failed")
        
        # ROLLBACK: Cleanup on failure
        if output_path:
            _cleanup_temp_file(output_path)


def _calculate_presentation_stats(presentation_data) -> Dict[str, int]:
    """
    Calculate presentation statistics ONCE
    """
    stats = {
        "total_slides": len(presentation_data.slides),
        "sections": 0,
        "content_slides": 0,
        "two_column_slides": 0,
        "charts": 0,
        "tables": 0,
        "images": 0,
        "icons_count": 0,
    }
    
    for slide in presentation_data.slides:
        # Count layout types
        if slide.layout_type == "section":
            stats["sections"] += 1
        elif slide.layout_type == "content":
            stats["content_slides"] += 1
        elif slide.layout_type == "two_column":
            stats["two_column_slides"] += 1
        
        # Count elements
        if slide.chart_data:
            stats["charts"] += 1
        
        if slide.table_data:
            stats["tables"] += 1
        
        if getattr(slide, "needs_image", False):
            stats["images"] += 1
        
        if slide.icon_name:
            stats["icons_count"] += 1
    
    return stats


def _cleanup_temp_file(file_path: Optional[str]) -> None:
    """
    Cleanup temporary PPTX file
    """
    if not file_path:
        return
    
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Cleaned up temp file: {file_path}")
    except Exception as e:
        logger.warning(f"Failed to cleanup temp file {file_path}: {e}")
