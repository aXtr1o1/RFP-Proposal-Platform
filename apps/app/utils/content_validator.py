import logging
from typing import List, Dict, Any
from apps.app.models.presentation import SlideContent, BulletPoint

logger = logging.getLogger("content_validator")

MAX_BULLETS_PER_SLIDE = 4            # Balanced for readability
MAX_SUB_BULLETS_PER_BULLET = 2
MAX_CONTENT_HEIGHT_INCHES = 4.0      # Slightly stricter to prevent cut‑off
CHAR_LIMIT_PER_SLIDE = 750          # Keep for overall content volume
MAX_BULLET_LENGTH = 180
AGENDA_MAX_BULLETS = 5
TABLE_MAX_ROWS = 3                   # Stricter split for tables to avoid overflow


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
                # layout_hint on next_slide may be None – normalize safely
                raw_next_layout = getattr(next_slide, 'layout_hint', None) \
                    or getattr(next_slide, 'layout_type', None) \
                    or getattr(next_slide, 'content_type', None) \
                    or ''
                next_layout = str(raw_next_layout).lower()
                
                if 'section' not in next_layout:
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
        
        # ✅ CLEAN BULLET TEXT: Remove periods from bullet points
        if has_bullets and slide.bullets:
            from apps.app.utils.text_formatter import clean_bullet_text
            for bullet in slide.bullets:
                if hasattr(bullet, 'text') and bullet.text:
                    original_text = bullet.text
                    cleaned_text = clean_bullet_text(bullet.text, remove_periods=True)
                    if cleaned_text != original_text:
                        bullet.text = cleaned_text
                        logger.debug(f"   🧹 Cleaned bullet: removed period/formatting")
        
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
    
    # Check headers
    headers = getattr(table_data, 'headers', [])
    if not headers or len(headers) == 0:
        logger.warning("  Table has no headers")
        return False
    
    rows = getattr(table_data, 'rows', [])
    if not rows or len(rows) == 0:
        logger.warning("  Table has no rows")
        return False
    
    # Check if rows have actual data
    valid_row_count = 0
    for row in rows:
        if not row or len(row) == 0:
            continue
        # Check if all cells are empty or placeholders
        non_empty_cells = [cell for cell in row if cell and len(str(cell).strip()) > 0]
        if len(non_empty_cells) > 0:
            # Check for placeholder text
            row_text = " ".join(str(cell).lower() for cell in row)
            if not any(placeholder in row_text for placeholder in ['tbd', 'pending', 'n/a', 'none', 'null', '[', ']']):
                valid_row_count += 1
    
    if valid_row_count == 0:
        logger.warning("  Table has no valid rows (all empty or placeholders)")
        return False
    
    return True


def _has_valid_chart(chart_data) -> bool:
    """Check if chart has valid data"""
    if not chart_data:
        return False
    
    # Check categories
    categories = getattr(chart_data, 'categories', None)
    if not categories or len(categories) == 0:
        logger.warning("  Chart has no categories")
        return False
    
    # Check for values (old format)
    values = getattr(chart_data, 'values', None)
    if values and len(values) > 0:
        # Check if values match categories
        if len(values) != len(categories):
            logger.warning(f"  Chart data mismatch: {len(categories)} categories but {len(values)} values")
            return False
        # Check if has non-zero values
        if any(v > 0 for v in values):
            return True
    
    # Check for series (new format)
    series = getattr(chart_data, 'series', None)
    if not series or len(series) == 0:
        logger.warning("  Chart has no series data")
        return False
    
    for s in series:
        s_values = getattr(s, 'values', []) if hasattr(s, 'values') else s.get('values', [])
        if not s_values or len(s_values) == 0:
            logger.warning("  Chart series has no values")
            continue
        
        # Check if values match categories
        if len(s_values) != len(categories):
            logger.warning(f"  Chart data mismatch: {len(categories)} categories but {len(s_values)} values in series")
            continue
        
        # Check if has non-zero values
        if any(v > 0 for v in s_values):
            return True
    
    logger.warning("  Chart has no valid numeric data")
    return False


def will_overflow(slide: SlideContent) -> bool:
    """Strict overflow detection: 4 bullets max, each bullet strictly 2 lines max"""
    layout_hint = getattr(slide, 'layout_hint', None) or getattr(slide, 'content_type', '')
    
    # Agenda slides
    if 'agenda' in layout_hint.lower():
        bullet_count = len(slide.bullets) if slide.bullets else 0
        return bullet_count > AGENDA_MAX_BULLETS
    
    # Four-box slides should have exactly 4 items
    if 'four' in layout_hint.lower() and 'box' in layout_hint.lower():
        bullet_count = len(slide.bullets) if slide.bullets else 0
        return bullet_count != 4
    
    # Table overflow detection - KEEP THIS (working well per user)
    if hasattr(slide, 'table_data') and slide.table_data:
        table_rows = getattr(slide.table_data, 'rows', [])
        if table_rows and len(table_rows) > TABLE_MAX_ROWS:
            logger.info(f"📊 Table overflow detected: {len(table_rows)} rows (max {TABLE_MAX_ROWS})")
            return True
    
    # Bullet overflow detection - STRICT: 4 bullets max, each strictly 2 lines max
    if slide.bullets:
        bullet_count = len(slide.bullets)
        
        # Rule 1: More than 4 bullets = overflow
        if bullet_count > MAX_BULLETS_PER_SLIDE:
            logger.info(f"📝 Bullet count overflow: {bullet_count} bullets (max {MAX_BULLETS_PER_SLIDE})")
            return True
        
        # Rule 2: Check if any bullet exceeds 2 lines (strictly)
        # Using ~55 characters per line, so max 110 characters per bullet for 2 lines
        MAX_CHARS_PER_BULLET = 110  # Strictly 2 lines max
        
        for idx, bullet in enumerate(slide.bullets):
            bullet_text = getattr(bullet, 'text', '') or ''
            bullet_len = len(bullet_text)
            
            # Check main bullet text
            if bullet_len > MAX_CHARS_PER_BULLET:
                logger.info(f"📝 Bullet {idx+1} exceeds 2 lines: {bullet_len} chars (max {MAX_CHARS_PER_BULLET})")
                return True
            
            # Check sub-bullets (if any sub-bullet exceeds 2 lines, overflow)
            if bullet.sub_bullets:
                for sub_idx, sub in enumerate(bullet.sub_bullets[:MAX_SUB_BULLETS_PER_BULLET]):
                    sub_text = getattr(sub, 'text', sub) if hasattr(sub, 'text') else str(sub)
                    sub_len = len(sub_text or "")
                    if sub_len > MAX_CHARS_PER_BULLET:
                        logger.info(f"📝 Sub-bullet {idx+1}.{sub_idx+1} exceeds 2 lines: {sub_len} chars (max {MAX_CHARS_PER_BULLET})")
                        return True
        
        # Rule 3: Estimate height as secondary check (shouldn't exceed max height)
        estimated_height = estimate_content_height(slide.bullets)
        if estimated_height > MAX_CONTENT_HEIGHT_INCHES:
            logger.info(f"📏 Height overflow: {estimated_height:.2f} inches (max {MAX_CONTENT_HEIGHT_INCHES})")
            return True
        
        # All checks passed - fits within limits
        logger.debug(f"   ✅ Fits: {bullet_count} bullets (max {MAX_BULLETS_PER_SLIDE}), all ≤2 lines, {estimated_height:.2f} inches")
    
    return False


def estimate_content_height(bullets: List[BulletPoint]) -> float:
    """Content height estimation - assumes max 2 lines per bullet for 4 bullets max"""
    if not bullets:
        return 0.5
    
    total_height = 0.15  # Base padding
    
    for bullet in bullets:
        # Calculate main bullet height
        main_text = getattr(bullet, 'text', '') or ''
        main_text_len = len(main_text)
        
        # Use ~55 characters per line for bullets to match visual wrapping
        # For strict 2-line limit, cap at 2 lines
        main_lines = max(1, min(2, (main_text_len + 54) // 55))  # Cap at 2 lines
        main_height = 0.35 * main_lines
        
        # Calculate sub-bullets height (also capped at 2 lines each)
        sub_height = 0.0
        if bullet.sub_bullets:
            for sub in bullet.sub_bullets[:MAX_SUB_BULLETS_PER_BULLET]:
                sub_text = getattr(sub, 'text', sub) if hasattr(sub, 'text') else str(sub)
                sub_len = len(sub_text or "")
                # Sub-bullets also capped at 2 lines
                sub_lines = max(1, min(2, (sub_len + 44) // 45))  # Cap at 2 lines
                sub_height += 0.28 * sub_lines
        
        # Add spacing between bullets
        spacing = 0.18 if bullet.sub_bullets else 0.12
        
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
    """Intelligently split bullets with enhanced overflow handling"""
    if not bullets:
        return []
    
    layout_hint = (layout_hint or "").lower()
    
    # Four-box slides need exactly 4 items per slide
    if 'four' in layout_hint and 'box' in layout_hint:
        splits = []
        for i in range(0, len(bullets), 4):
            chunk = bullets[i:i+4]
            while len(chunk) < 4:
                chunk.append(BulletPoint(text="", sub_bullets=[]))
            
            part_num = (i // 4) + 1
            subtitle = f"Part {part_num}" if i > 0 else None
            splits.append({"bullets": chunk, "subtitle": subtitle})
        return splits
    
    # Agenda slides - keep items together, avoid single-item slides
    if 'agenda' in layout_hint:
        total = len(bullets)
        # If all items can reasonably fit on one slide, don't split
        if total <= AGENDA_MAX_BULLETS + 2:
            logger.info(f"   ✅ Agenda content fits on single slide: {total} items")
            return [{"bullets": bullets, "subtitle": None}]

        # Otherwise, split into chunks but avoid single-item last slide
        raw_chunks: List[List[BulletPoint]] = []
        for i in range(0, total, AGENDA_MAX_BULLETS):
            raw_chunks.append(bullets[i:i+AGENDA_MAX_BULLETS])

        # If last chunk has only one item, rebalance with previous chunk
        if len(raw_chunks) > 1 and len(raw_chunks[-1]) == 1:
            logger.info("   ⚠️  Agenda split produced single-item slide, rebalancing")
            prev = raw_chunks[-2]
            last = raw_chunks[-1]
            if len(prev) > 2:  # only move if previous has enough items
                moved = prev.pop()        # move last from previous
                last.insert(0, moved)     # now last has at least 2
                logger.info(f"   ✅ Rebalanced agenda: {len(prev)} + {len(last)} items")

        splits = []
        for idx, chunk in enumerate(raw_chunks):
            subtitle = "Continued" if idx > 0 else None
            splits.append({"bullets": chunk, "subtitle": subtitle})

        logger.info(f"✂️  Agenda split into {len(splits)} slides: " +
                    ", ".join(str(len(c)) for c in raw_chunks) + " items")
        return splits
    
    # Regular bullet slides - even distribution to prevent single-bullet hangers
    total_bullets = len(bullets)
    
    # ✅ FIRST: Check if content fits in single slide
    total_height = estimate_content_height(bullets)
    total_chars = count_total_characters(bullets)
    
    # Be conservative - only split if truly needed
    needs_split = (
        total_bullets > MAX_BULLETS_PER_SLIDE + 1 or
        total_height > MAX_CONTENT_HEIGHT_INCHES or
        (total_bullets > MAX_BULLETS_PER_SLIDE and total_chars > CHAR_LIMIT_PER_SLIDE)
    )
    
    if not needs_split:
        # Content fits in one slide - don't split
        logger.info(f"   ✅ Content fits: {total_bullets} bullets, {total_chars} chars, {total_height:.2f} inches")
        return [{"bullets": bullets, "subtitle": None, "chars": total_chars, "height": total_height}]
    
    # ✅ SECOND: Calculate EVEN distribution to avoid single-bullet hangers
    if total_bullets <= MAX_BULLETS_PER_SLIDE * 2:
        # Can fit in 2 slides - distribute evenly
        mid = total_bullets // 2
        splits = [
            {"bullets": bullets[:mid], "subtitle": None},
            {"bullets": bullets[mid:], "subtitle": "Part 2"}
        ]
        logger.info(f"✂️  Even split into 2 slides: {mid} + {total_bullets - mid} bullets")
        return splits
    
    # ✅ THIRD: For larger splits, use smart algorithm with even distribution
    # Calculate optimal bullets per slide to avoid single-bullet hangers
    num_slides_needed = (total_bullets + MAX_BULLETS_PER_SLIDE - 1) // MAX_BULLETS_PER_SLIDE
    optimal_per_slide = (total_bullets + num_slides_needed - 1) // num_slides_needed
    
    logger.info(f"✂️  Splitting {total_bullets} bullets → {num_slides_needed} slides (~{optimal_per_slide} bullets each)")
    
    splits = []
    current_chunk = []
    current_chars = 0
    current_height = 0.15  # Base padding
    
    for idx, bullet in enumerate(bullets):
        # Calculate bullet metrics
        bullet_text = getattr(bullet, 'text', '') or ''
        bullet_chars = len(bullet_text)
        
        # Add sub-bullet characters
        if bullet.sub_bullets:
            for sub in bullet.sub_bullets[:MAX_SUB_BULLETS_PER_BULLET]:
                sub_text = getattr(sub, 'text', sub) if hasattr(sub, 'text') else str(sub)
                bullet_chars += len(sub_text or "")
        
        # Estimate bullet height
        bullet_lines = max(1, (len(bullet_text) + 69) // 70)
        bullet_height = 0.35 * bullet_lines
        if bullet.sub_bullets:
            num_subs = min(len(bullet.sub_bullets), MAX_SUB_BULLETS_PER_BULLET)
            bullet_height += 0.28 * num_subs
        bullet_height += 0.15 if bullet.sub_bullets else 0.12  # Spacing
        
        # Add to current chunk
        current_chunk.append(bullet)
        current_chars += bullet_chars
        current_height += bullet_height
        
        # Check if we should split now (based on optimal distribution)
        remaining_bullets = total_bullets - (idx + 1)
        remaining_slides = num_slides_needed - len(splits) - 1
        
        should_split = False
        if remaining_slides > 0:
            # Calculate if we should split now to achieve even distribution
            optimal_remaining_per_slide = remaining_bullets / remaining_slides if remaining_slides > 0 else 0
            
            # Split if:
            # 1. We have enough bullets for this slide (at optimal)
            # 2. OR height would overflow
            should_split = (
                len(current_chunk) >= optimal_per_slide or
                current_height + 0.5 > MAX_CONTENT_HEIGHT_INCHES  # Leave buffer for next bullet
            )
        
        if should_split and current_chunk and remaining_bullets >= 2:  # Ensure at least 2 bullets remain
            part_num = len(splits) + 1
            subtitle = f"Part {part_num}" if splits else None
            splits.append({
                "bullets": current_chunk[:],
                "subtitle": subtitle,
                "chars": current_chars,
                "height": current_height
            })
            current_chunk = []
            current_chars = 0
            current_height = 0.15
    
    # Add remaining bullets
    if current_chunk:
        # ✅ FIX: If only 1 bullet remains, redistribute from previous split
        if len(current_chunk) == 1 and len(splits) > 0:
            logger.info(f"   ⚠️  Single bullet hanger detected - redistributing")
            # Take last bullet from previous split and add to this one
            prev_split = splits[-1]
            if len(prev_split['bullets']) > 2:  # Only if previous has more than 2
                moved_bullet = prev_split['bullets'].pop()
                current_chunk.insert(0, moved_bullet)
                logger.info(f"   ✅ Redistributed: moved 1 bullet from Part {len(splits)} to Part {len(splits)+1}")
        
        part_num = len(splits) + 1
        subtitle = f"Part {part_num}" if splits else None
        splits.append({
            "bullets": current_chunk,
            "subtitle": subtitle,
            "chars": current_chars,
            "height": current_height
        })
    
    # Log split results
    if len(splits) > 1:
        logger.info(f"✂️  Split '{slide_title}' into {len(splits)} slides (even distribution)")
        for idx, split in enumerate(splits):
            logger.info(f"   Part {idx+1}: {len(split['bullets'])} bullets, {split.get('chars', 0)} chars, {split.get('height', 0):.2f} inches")
    
    return splits


def split_table_to_slides(table_data: Any, slide_title: str) -> List[Dict]:
    """Enhanced table splitting with proper header handling"""
    # Extract rows and headers
    if hasattr(table_data, 'rows'):
        all_rows = table_data.rows
    else:
        return []
    
    if not all_rows:
        return []
    
    # Get headers separately
    headers = getattr(table_data, 'headers', None)
    
    # Determine if first row is header
    has_header = getattr(table_data, 'has_header', True)
    
    # ✅ FIX: Check for duplicate headers in first row
    if headers and len(headers) > 0 and len(all_rows) > 0:
        first_row = all_rows[0]
        # Check if first row is the same as headers (case-insensitive)
        if len(first_row) == len(headers):
            first_row_clean = [str(cell).strip().lower() for cell in first_row]
            headers_clean = [str(h).strip().lower() for h in headers]
            
            if first_row_clean == headers_clean:
                logger.warning(f"   ⚠️  Duplicate headers in '{slide_title}' - removing first row")
                all_rows = all_rows[1:]  # Skip the duplicate header row
    
    # If we have explicit headers, use them
    if headers and len(headers) > 0:
        data_rows = all_rows
        header_row = headers
    elif has_header and len(all_rows) > 0:
        header_row = all_rows[0]
        data_rows = all_rows[1:]
    else:
        header_row = None
        data_rows = all_rows
    
    # If table fits, return as is
    if len(data_rows) <= TABLE_MAX_ROWS:
        logger.info(f"📊 Table '{slide_title}': {len(data_rows)} rows (within {TABLE_MAX_ROWS} limit)")
        return [{"table_rows": all_rows, "headers": headers, "has_header": has_header, "subtitle": None}]
    
    # Split table into multiple slides
    splits = []
    total_parts = (len(data_rows) + TABLE_MAX_ROWS - 1) // TABLE_MAX_ROWS
    
    logger.info(f"✂️  Splitting table '{slide_title}': {len(data_rows)} rows → {total_parts} slides")
    
    for i in range(0, len(data_rows), TABLE_MAX_ROWS):
        chunk_rows = data_rows[i:i+TABLE_MAX_ROWS]
        part_num = (i // TABLE_MAX_ROWS) + 1
        
        # Add header to each split
        if header_row is not None:
            if isinstance(header_row, list):
                final_rows = [header_row] + chunk_rows
            else:
                final_rows = chunk_rows
        else:
            final_rows = chunk_rows
        
        # Create subtitle for continuation slides
        if total_parts > 1:
            subtitle = f"(Part {part_num} of {total_parts})"
        else:
            subtitle = None
        
        splits.append({
            "table_rows": final_rows,
            "headers": headers,
            "has_header": has_header,
            "subtitle": subtitle
        })
        
        logger.info(f"   Part {part_num}: {len(chunk_rows)} data rows + header")
    
    return splits