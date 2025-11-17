import logging
from typing import List, Dict, Any
from models.presentation import SlideContent, BulletPoint

logger = logging.getLogger("content_validator")

# Enhanced limits
MAX_BULLETS_PER_SLIDE = 4  # Standard content slides (changed from 6)
MAX_SUB_BULLETS_PER_BULLET = 3
MAX_CONTENT_HEIGHT_INCHES = 4.5
CHAR_LIMIT_PER_SLIDE = 800
AGENDA_MAX_BULLETS = 5  # Agenda max (changed from 8)
TABLE_MAX_ROWS = 6  # NEW: Max table rows per slide

def estimate_bullet_height(bullet: BulletPoint) -> float:
    """
    Accurately estimate bullet point height
    
    Args:
        bullet: Bullet point to measure
        
    Returns:
        Estimated height in inches
    """
    # Main bullet height (varies by text length)
    main_text_len = len(bullet.text or "")
    main_lines = max(1, main_text_len // 80)  # ~80 chars per line
    main_height = 0.3 * main_lines  # 0.3 inches per line
    
    # Sub-bullets height
    sub_height = 0.0
    if bullet.sub_bullets:
        for sub in bullet.sub_bullets[:MAX_SUB_BULLETS_PER_BULLET]:
            sub_text = getattr(sub, 'text', sub) if hasattr(sub, 'text') else str(sub)
            sub_len = len(sub_text or "")
            sub_lines = max(1, sub_len // 70)  # ~70 chars per line for sub-bullets
            sub_height += 0.25 * sub_lines
    
    # Spacing
    spacing = 0.15 if bullet.sub_bullets else 0.1
    
    return main_height + sub_height + spacing

def estimate_content_height(bullets: List[BulletPoint]) -> float:
    """
    Estimate total content height for bullets
    
    Args:
        bullets: List of bullet points
        
    Returns:
        Estimated height in inches
    """
    if not bullets:
        return 0.5
    
    total_height = 0.15  # Initial padding
    for bullet in bullets:
        total_height += estimate_bullet_height(bullet)
    
    return total_height

def count_total_characters(bullets: List[BulletPoint]) -> int:
    """Count total characters in bullets and sub-bullets"""
    total = 0
    for bullet in bullets:
        total += len(bullet.text or "")
        if bullet.sub_bullets:
            for sub in bullet.sub_bullets:
                sub_text = getattr(sub, 'text', sub) if hasattr(sub, 'text') else str(sub)
                total += len(sub_text or "")
    return total

def will_overflow(slide: SlideContent) -> bool:
    """
    Check if slide will overflow with layout-specific rules
    
    Args:
        slide: Slide to check
        
    Returns:
        True if overflow detected
    """
    # Get layout hint
    layout_hint = getattr(slide, 'layout_hint', None) or getattr(slide, 'content_type', '')
    
    # Special handling for agenda slides
    if 'agenda' in layout_hint.lower():
        bullet_count = len(slide.bullets) if slide.bullets else 0
        return bullet_count > AGENDA_MAX_BULLETS
    
    # Four boxes MUST be exactly 4
    if 'four' in layout_hint.lower() and 'box' in layout_hint.lower():
        bullet_count = len(slide.bullets) if slide.bullets else 0
        return bullet_count != 4
    
    # Table row limit check
    if hasattr(slide, 'table') and slide.table:
        table_rows = getattr(slide.table, 'rows', [])
        if table_rows and len(table_rows) > TABLE_MAX_ROWS:
            return True
    elif hasattr(slide, 'table_data') and slide.table_data:
        table_rows = getattr(slide.table_data, 'rows', [])
        if table_rows and len(table_rows) > TABLE_MAX_ROWS:
            return True
    
    # Standard overflow checks for bullets
    if slide.bullets:
        bullet_count = len(slide.bullets)
        
        # Check bullet count
        if bullet_count > MAX_BULLETS_PER_SLIDE:
            return True
        
        # Check height
        estimated_height = estimate_content_height(slide.bullets)
        if estimated_height > MAX_CONTENT_HEIGHT_INCHES:
            return True
        
        # Check character count
        total_chars = count_total_characters(slide.bullets)
        if total_chars > CHAR_LIMIT_PER_SLIDE:
            return True
    
    return False

def smart_split_bullets(bullets: List[BulletPoint], slide_title: str, layout_hint: str = None) -> List[Dict]:
    """
    Intelligently split bullets into multiple slides with descriptive subtitles
    
    Args:
        bullets: All bullets to split
        slide_title: Original slide title
        layout_hint: Layout hint for special handling
        
    Returns:
        List of dicts with 'bullets' and 'subtitle' keys
    """
    if not bullets:
        return []
    
    # Normalize layout hint
    layout_hint = (layout_hint or "").lower()
    
    # Special handling for four_box layouts
    if 'four' in layout_hint and 'box' in layout_hint:
        splits = []
        for i in range(0, len(bullets), 4):
            chunk = bullets[i:i+4]
            # Pad to exactly 4 if less
            while len(chunk) < 4:
                chunk.append(BulletPoint(text="", sub_bullets=[]))
            
            subtitle = f"Part {i//4 + 1}" if i > 0 else None
            splits.append({
                "bullets": chunk,
                "subtitle": subtitle
            })
        return splits
    
    # Special handling for agenda
    if 'agenda' in layout_hint:
        splits = []
        for i in range(0, len(bullets), AGENDA_MAX_BULLETS):
            chunk = bullets[i:i+AGENDA_MAX_BULLETS]
            subtitle = "Continued" if i > 0 else None
            splits.append({
                "bullets": chunk,
                "subtitle": subtitle
            })
        return splits
    
    # Standard splitting for title_and_content
    splits = []
    current_chunk = []
    current_chars = 0
    
    for bullet in bullets:
        bullet_chars = len(bullet.text or "")
        if bullet.sub_bullets:
            for sub in bullet.sub_bullets:
                sub_text = getattr(sub, 'text', sub) if hasattr(sub, 'text') else str(sub)
                bullet_chars += len(sub_text or "")
        
        # Check if adding this bullet would overflow
        would_overflow = (
            len(current_chunk) >= MAX_BULLETS_PER_SLIDE or
            current_chars + bullet_chars > CHAR_LIMIT_PER_SLIDE or
            (current_chunk and estimate_content_height(current_chunk + [bullet]) > MAX_CONTENT_HEIGHT_INCHES)
        )
        
        if would_overflow and current_chunk:
            # Create descriptive subtitle from first bullet (first 4 words)
            if current_chunk[0].text:
                first_bullet_words = current_chunk[0].text.split()[:4]
                subtitle = " ".join(first_bullet_words) if splits else None
            else:
                subtitle = "Continued" if splits else None
            
            splits.append({
                "bullets": current_chunk[:],
                "subtitle": subtitle
            })
            current_chunk = [bullet]
            current_chars = bullet_chars
        else:
            current_chunk.append(bullet)
            current_chars += bullet_chars
    
    # Add remaining bullets
    if current_chunk:
        section_names = ["Overview", "Key Points", "Details", "Additional Information"]
        if splits:
            if len(splits) < len(section_names):
                subtitle = section_names[len(splits)]
            else:
                subtitle = "Continued"
        else:
            subtitle = None
        
        splits.append({
            "bullets": current_chunk,
            "subtitle": subtitle
        })
    
    return splits

def split_table_to_slides(table_data: Any, slide_title: str) -> List[Dict]:
    """
    Split large tables into multiple slides (max 6 rows per slide + header)
    
    Args:
        table_data: Table data object with rows
        slide_title: Original slide title
        
    Returns:
        List of dicts with 'table_rows', 'has_header', and 'subtitle' keys
    """
    # Get rows from table object
    if hasattr(table_data, 'rows'):
        all_rows = table_data.rows
    else:
        return []
    
    if not all_rows or len(all_rows) == 0:
        return []
    
    # Determine if table has header
    has_header = getattr(table_data, 'has_header', True)
    
    if has_header and len(all_rows) > 0:
        header = all_rows[0]
        data_rows = all_rows[1:]
    else:
        header = None
        data_rows = all_rows
    
    # If table fits in one slide, return as is
    if len(data_rows) <= TABLE_MAX_ROWS:
        return [{
            "table_rows": all_rows,
            "has_header": has_header,
            "subtitle": None
        }]
    
    # Split data rows into chunks of TABLE_MAX_ROWS
    splits = []
    for i in range(0, len(data_rows), TABLE_MAX_ROWS):
        chunk_rows = data_rows[i:i+TABLE_MAX_ROWS]
        
        # Add header back for each split
        if header is not None:
            final_rows = [header] + chunk_rows
        else:
            final_rows = chunk_rows
        
        # Create subtitle for continuation pages
        subtitle = f"(Continued {i//TABLE_MAX_ROWS + 1})" if i > 0 else None
        
        splits.append({
            "table_rows": final_rows,
            "has_header": has_header,
            "subtitle": subtitle
        })
    
    logger.info(f"✂️  Split table '{slide_title}' into {len(splits)} slides (6 rows max per slide)")
    return splits

def validate_presentation(slides: List[SlideContent]) -> List[SlideContent]:
    """
    Validate entire presentation and optimize content distribution
    - Remove bullets from section headers
    - Remove blank slides
    - Split overflowing slides
    - Split large tables
    
    Args:
        slides: List of all slides
        
    Returns:
        Optimized list of slides
    """
    logger.info(f"🔍 Validating {len(slides)} slides...")
    
    validated_slides = []
    stats = {
        "total_bullets": 0,
        "section_headers": 0,
        "agenda_slides": 0,
        "chart_slides": 0,
        "table_slides": 0,
        "four_box_slides": 0,
        "split_slides": 0,
        "blank_removed": 0
    }
    
    for slide in slides:
        # Get layout type/content type
        layout_type = getattr(slide, 'layout_type', '')
        content_type = getattr(slide, 'content_type', '')
        layout_hint = layout_type or content_type
        
        # CRITICAL: Section headers should NEVER have bullets
        if 'section' in layout_hint.lower():
            if slide.bullets and len(slide.bullets) > 0:
                logger.warning(f"⚠️  REMOVED {len(slide.bullets)} bullets from section header: '{slide.title}'")
                slide.bullets = []
            stats["section_headers"] += 1
            validated_slides.append(slide)
            continue
        
        # Check if slide has content
        has_bullets = slide.bullets and len(slide.bullets) > 0
        
        # Check table
        has_table = False
        table_data = getattr(slide, 'table', None) or getattr(slide, 'table_data', None)
        if table_data:
            table_rows = getattr(table_data, 'rows', [])
            has_table = table_rows and len(table_rows) > 0
        
        # Check chart
        has_chart = False
        chart_data = getattr(slide, 'chart', None) or getattr(slide, 'chart_data', None)
        if chart_data:
            chart_values = getattr(chart_data, 'values', [])
            has_chart = chart_values and len(chart_values) > 0
        
        # Skip completely blank slides
        if not (has_bullets or has_table or has_chart):
            logger.info(f"⚠️  BLANK SLIDE REMOVED: '{slide.title}' (no content)")
            stats["blank_removed"] += 1
            continue
        
        # Handle table splitting
        if has_table and table_data:
            table_rows = getattr(table_data, 'rows', [])
            if len(table_rows) > TABLE_MAX_ROWS:
                logger.info(f"✂️  Splitting table slide '{slide.title}' ({len(table_rows)} rows)")
                table_splits = split_table_to_slides(table_data, slide.title)
                
                for idx, split_data in enumerate(table_splits):
                    # Create new slide for each table chunk
                    new_slide = SlideContent(
                        title=slide.title,
                        subtitle=split_data["subtitle"],
                        content_type=content_type,
                        layout_type=layout_type,
                        bullets=[],
                        table=type(table_data)(
                            rows=split_data["table_rows"],
                            has_header=split_data["has_header"]
                        ),
                        chart=None
                    )
                    validated_slides.append(new_slide)
                    stats["table_slides"] += 1
                    if idx > 0:
                        stats["split_slides"] += 1
                continue
        
        # Handle bullet overflow
        if will_overflow(slide):
            logger.info(f"✂️  Splitting overflowing slide: '{slide.title}'")
            splits = smart_split_bullets(slide.bullets or [], slide.title, layout_hint)
            
            for idx, split_data in enumerate(splits):
                new_slide = SlideContent(
                    title=slide.title,
                    subtitle=split_data["subtitle"],
                    content_type=content_type,
                    layout_type=layout_type,
                    bullets=split_data["bullets"],
                    table=None,
                    chart=None
                )
                validated_slides.append(new_slide)
                stats["total_bullets"] += len(split_data["bullets"])
                
                if 'agenda' in layout_hint.lower():
                    stats["agenda_slides"] += 1
                elif 'four' in layout_hint.lower() and 'box' in layout_hint.lower():
                    stats["four_box_slides"] += 1
                
                if idx > 0:
                    stats["split_slides"] += 1
        else:
            # No overflow - add as is
            validated_slides.append(slide)
            
            if slide.bullets:
                stats["total_bullets"] += len(slide.bullets)
            if has_chart:
                stats["chart_slides"] += 1
            if has_table:
                stats["table_slides"] += 1
            
            if 'agenda' in layout_hint.lower():
                stats["agenda_slides"] += 1
            elif 'four' in layout_hint.lower() and 'box' in layout_hint.lower():
                stats["four_box_slides"] += 1
    
    logger.info(f"✅ Validation complete: {len(slides)} → {len(validated_slides)} slides")
    logger.info(f"   Stats: {stats}")
    
    return validated_slides

def calculate_content_density(slide: SlideContent) -> Dict[str, Any]:
    """
    Calculate comprehensive content metrics
    
    Args:
        slide: Slide content
        
    Returns:
        Dictionary with detailed metrics
    """
    if not slide.bullets:
        return {
            "bullet_count": 0,
            "sub_bullet_count": 0,
            "total_chars": 0,
            "estimated_height": 0.5,
            "density": "empty",
            "will_overflow": False
        }
    
    bullet_count = len(slide.bullets)
    sub_bullet_count = sum(len(getattr(b, 'sub_bullets', []) or []) for b in slide.bullets)
    total_chars = count_total_characters(slide.bullets)
    estimated_height = estimate_content_height(slide.bullets)
    
    # Determine density
    if bullet_count <= 2 and total_chars < 300:
        density = "low"
    elif bullet_count <= 4 and total_chars < 600:
        density = "medium"
    elif bullet_count <= 6 and total_chars < 900:
        density = "high"
    else:
        density = "very_high"
    
    return {
        "bullet_count": bullet_count,
        "sub_bullet_count": sub_bullet_count,
        "total_chars": total_chars,
        "estimated_height": estimated_height,
        "density": density,
        "will_overflow": will_overflow(slide),
        "recommended_split": will_overflow(slide)
    }
