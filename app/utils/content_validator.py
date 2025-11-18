import logging
from typing import List, Dict, Any
from models.presentation import SlideContent, BulletPoint

logger = logging.getLogger("content_validator")

MAX_BULLETS_PER_SLIDE = 4
MAX_SUB_BULLETS_PER_BULLET = 2
MAX_CONTENT_HEIGHT_INCHES = 4.5
CHAR_LIMIT_PER_SLIDE = 800
AGENDA_MAX_BULLETS = 5
TABLE_MAX_ROWS = 6


def validate_presentation(slides: List[SlideContent]) -> List[SlideContent]:
    """
    Enhanced validation with proper chart/table/Thank You preservation
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
        "blank_removed": 0,
        "orphaned_sections_fixed": 0
    }
    
    i = 0
    while i < len(slides):
        slide = slides[i]
        
        # Get layout info
        layout_type = getattr(slide, 'layout_type', '')
        content_type = getattr(slide, 'content_type', '')
        layout_hint = getattr(slide, 'layout_hint', '') or layout_type or content_type
        
        # CRITICAL: Check for section headers
        if 'section' in layout_hint.lower():
            # Section headers should NEVER have bullets
            if slide.bullets and len(slide.bullets) > 0:
                logger.warning(f"⚠️  REMOVED {len(slide.bullets)} bullets from section: '{slide.title}'")
                slide.bullets = []
            
            # SPECIAL CASE: Thank You slide should ALWAYS be kept
            if any(word in slide.title.lower() for word in ['thank', 'thanks', 'شكر']):
                logger.info(f"✅ Preserving Thank You slide: '{slide.title}'")
                stats["section_headers"] += 1
                validated_slides.append(slide)
                i += 1
                continue
            
            # Check if next slide has content
            has_content_after = False
            if i + 1 < len(slides):
                next_slide = slides[i + 1]
                next_layout = getattr(next_slide, 'layout_hint', '')
                
                if 'section' not in next_layout.lower():
                    next_bullets = getattr(next_slide, 'bullets', [])
                    next_content = getattr(next_slide, 'content', None)
                    next_table = getattr(next_slide, 'table_data', None)
                    next_chart = getattr(next_slide, 'chart_data', None)
                    
                    has_content_after = (
                        (next_bullets and len(next_bullets) > 0) or
                        (next_content and len(next_content.strip()) > 0) or
                        (next_table and _has_valid_table(next_table)) or
                        (next_chart and _has_valid_chart(next_chart))
                    )
            
            if not has_content_after:
                logger.warning(f"⚠️  ORPHANED section removed: '{slide.title}'")
                stats["orphaned_sections_fixed"] += 1
                i += 1
                continue
            
            stats["section_headers"] += 1
            validated_slides.append(slide)
            i += 1
            continue
        
        # Check content types
        has_bullets = slide.bullets and len(slide.bullets) > 0
        has_content = False
        content_text = getattr(slide, 'content', None)
        if content_text and len(content_text.strip()) > 0:
            has_content = True
        
        # Check table (CRITICAL: Proper validation)
        has_table = False
        table_data = getattr(slide, 'table', None) or getattr(slide, 'table_data', None)
        if table_data and _has_valid_table(table_data):
            has_table = True
        
        # Check chart (CRITICAL: Proper validation)
        has_chart = False
        chart_data = getattr(slide, 'chart', None) or getattr(slide, 'chart_data', None)
        if chart_data and _has_valid_chart(chart_data):
            has_chart = True
        
        # Skip ONLY completely blank slides
        if not (has_bullets or has_table or has_chart or has_content):
            logger.info(f"⚠️  BLANK SLIDE REMOVED: '{slide.title}'")
            stats["blank_removed"] += 1
            i += 1
            continue
        
        # Handle table splitting
        if has_table and table_data:
            table_rows = getattr(table_data, 'rows', [])
            if len(table_rows) > TABLE_MAX_ROWS:
                logger.info(f"✂️  Splitting table '{slide.title}' ({len(table_rows)} rows)")
                table_splits = split_table_to_slides(table_data, slide.title)
                
                for idx, split_data in enumerate(table_splits):
                    new_slide = SlideContent(
                        title=slide.title,
                        subtitle=split_data["subtitle"],
                        content_type=content_type,
                        layout_type=layout_type,
                        layout_hint='table_slide',
                        bullets=None,
                        content=None,
                        table_data=type(table_data)(
                            rows=split_data["table_rows"],
                            headers=getattr(table_data, 'headers', [])
                        ),
                        chart_data=None
                    )
                    validated_slides.append(new_slide)
                    stats["table_slides"] += 1
                    if idx > 0:
                        stats["split_slides"] += 1
                i += 1
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
                    layout_hint=layout_hint,
                    bullets=split_data["bullets"],
                    content=None,
                    table_data=None,
                    chart_data=None
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
                logger.info(f"✅ Chart slide preserved: '{slide.title}'")
            if has_table:
                stats["table_slides"] += 1
                logger.info(f"✅ Table slide preserved: '{slide.title}'")
            
            if 'agenda' in layout_hint.lower():
                stats["agenda_slides"] += 1
            elif 'four' in layout_hint.lower() and 'box' in layout_hint.lower():
                stats["four_box_slides"] += 1
        
        i += 1
    
    # Final validation warnings
    if stats["chart_slides"] < 3:
        logger.warning(f"⚠️  WARNING: Only {stats['chart_slides']} chart slides (need 3+)")
    if stats["four_box_slides"] < 2:
        logger.warning(f"⚠️  WARNING: Only {stats['four_box_slides']} four-box slides (need 2+)")
    if stats["table_slides"] < 1:
        logger.warning(f"⚠️  WARNING: Only {stats['table_slides']} table slides (need 1+)")
    
    logger.info(f"✅ Validation complete: {len(slides)} → {len(validated_slides)} slides")
    logger.info(f"   Stats: {stats}")
    
    return validated_slides


def _has_valid_table(table_data) -> bool:
    """Check if table has valid data"""
    if not table_data:
        return False
    
    rows = getattr(table_data, 'rows', [])
    if not rows or len(rows) == 0:
        return False
    
    # Check if rows have actual data
    for row in rows:
        if not row or len(row) == 0:
            return False
        # Check if all cells are empty
        if all(not cell or len(str(cell).strip()) == 0 for cell in row):
            return False
    
    return True


def _has_valid_chart(chart_data) -> bool:
    """Check if chart has valid data"""
    if not chart_data:
        return False
    
    # Check for values (old format)
    values = getattr(chart_data, 'values', None)
    if values and len(values) > 0 and any(v > 0 for v in values):
        return True
    
    # Check for series (new format)
    series = getattr(chart_data, 'series', None)
    if series and len(series) > 0:
        for s in series:
            s_values = getattr(s, 'values', [])
            if s_values and len(s_values) > 0 and any(v > 0 for v in s_values):
                return True
    
    return False


def will_overflow(slide: SlideContent) -> bool:
    """Check if slide will overflow"""
    layout_hint = getattr(slide, 'layout_hint', None) or getattr(slide, 'content_type', '')
    
    if 'agenda' in layout_hint.lower():
        bullet_count = len(slide.bullets) if slide.bullets else 0
        return bullet_count > AGENDA_MAX_BULLETS
    
    if 'four' in layout_hint.lower() and 'box' in layout_hint.lower():
        bullet_count = len(slide.bullets) if slide.bullets else 0
        return bullet_count != 4
    
    if hasattr(slide, 'table_data') and slide.table_data:
        table_rows = getattr(slide.table_data, 'rows', [])
        if table_rows and len(table_rows) > TABLE_MAX_ROWS:
            return True
    
    if slide.bullets:
        bullet_count = len(slide.bullets)
        
        if bullet_count > MAX_BULLETS_PER_SLIDE:
            return True
        
        estimated_height = estimate_content_height(slide.bullets)
        if estimated_height > MAX_CONTENT_HEIGHT_INCHES:
            return True
        
        total_chars = count_total_characters(slide.bullets)
        if total_chars > CHAR_LIMIT_PER_SLIDE:
            return True
    
    return False


def estimate_content_height(bullets: List[BulletPoint]) -> float:
    """Estimate content height"""
    if not bullets:
        return 0.5
    
    total_height = 0.15
    for bullet in bullets:
        main_text_len = len(bullet.text or "")
        main_lines = max(1, main_text_len // 80)
        main_height = 0.3 * main_lines
        
        sub_height = 0.0
        if bullet.sub_bullets:
            for sub in bullet.sub_bullets[:MAX_SUB_BULLETS_PER_BULLET]:
                sub_text = getattr(sub, 'text', sub) if hasattr(sub, 'text') else str(sub)
                sub_len = len(sub_text or "")
                sub_lines = max(1, sub_len // 70)
                sub_height += 0.25 * sub_lines
        
        spacing = 0.15 if bullet.sub_bullets else 0.1
        total_height += main_height + sub_height + spacing
    
    return total_height


def count_total_characters(bullets: List[BulletPoint]) -> int:
    """Count total characters"""
    total = 0
    for bullet in bullets:
        total += len(bullet.text or "")
        if bullet.sub_bullets:
            for sub in bullet.sub_bullets:
                sub_text = getattr(sub, 'text', sub) if hasattr(sub, 'text') else str(sub)
                total += len(sub_text or "")
    return total


def smart_split_bullets(bullets: List[BulletPoint], slide_title: str, layout_hint: str = None) -> List[Dict]:
    """Intelligently split bullets"""
    if not bullets:
        return []
    
    layout_hint = (layout_hint or "").lower()
    
    if 'four' in layout_hint and 'box' in layout_hint:
        splits = []
        for i in range(0, len(bullets), 4):
            chunk = bullets[i:i+4]
            while len(chunk) < 4:
                chunk.append(BulletPoint(text="", sub_bullets=[]))
            
            subtitle = f"Part {i//4 + 1}" if i > 0 else None
            splits.append({"bullets": chunk, "subtitle": subtitle})
        return splits
    
    if 'agenda' in layout_hint:
        splits = []
        for i in range(0, len(bullets), AGENDA_MAX_BULLETS):
            chunk = bullets[i:i+AGENDA_MAX_BULLETS]
            subtitle = "Continued" if i > 0 else None
            splits.append({"bullets": chunk, "subtitle": subtitle})
        return splits
    
    splits = []
    current_chunk = []
    current_chars = 0
    
    for bullet in bullets:
        bullet_chars = len(bullet.text or "")
        if bullet.sub_bullets:
            for sub in bullet.sub_bullets:
                sub_text = getattr(sub, 'text', sub) if hasattr(sub, 'text') else str(sub)
                bullet_chars += len(sub_text or "")
        
        would_overflow = (
            len(current_chunk) >= MAX_BULLETS_PER_SLIDE or
            current_chars + bullet_chars > CHAR_LIMIT_PER_SLIDE
        )
        
        if would_overflow and current_chunk:
            subtitle = "Continued" if splits else None
            splits.append({"bullets": current_chunk[:], "subtitle": subtitle})
            current_chunk = [bullet]
            current_chars = bullet_chars
        else:
            current_chunk.append(bullet)
            current_chars += bullet_chars
    
    if current_chunk:
        subtitle = "Continued" if splits else None
        splits.append({"bullets": current_chunk, "subtitle": subtitle})
    
    return splits


def split_table_to_slides(table_data: Any, slide_title: str) -> List[Dict]:
    """Split large tables"""
    if hasattr(table_data, 'rows'):
        all_rows = table_data.rows
    else:
        return []
    
    if not all_rows:
        return []
    
    has_header = getattr(table_data, 'has_header', True)
    
    if has_header and len(all_rows) > 0:
        header = all_rows[0]
        data_rows = all_rows[1:]
    else:
        header = None
        data_rows = all_rows
    
    if len(data_rows) <= TABLE_MAX_ROWS:
        return [{"table_rows": all_rows, "has_header": has_header, "subtitle": None}]
    
    splits = []
    for i in range(0, len(data_rows), TABLE_MAX_ROWS):
        chunk_rows = data_rows[i:i+TABLE_MAX_ROWS]
        
        if header is not None:
            final_rows = [header] + chunk_rows
        else:
            final_rows = chunk_rows
        
        subtitle = f"(Part {i//TABLE_MAX_ROWS + 1})" if i > 0 else None
        splits.append({"table_rows": final_rows, "has_header": has_header, "subtitle": subtitle})
    
    return splits