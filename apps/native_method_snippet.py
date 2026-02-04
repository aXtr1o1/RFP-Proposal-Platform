
# ========================================================================
# NATIVE MODE GENERATION
# ========================================================================

def _create_slide_native(self, slide_data: SlideContent, layout_name: str) -> None:
    """
    Create slide using native PowerPoint placeholders.
    
    Args:
        slide_data: Content for the slide
        layout_name: Logical layout name (e.g., 'title', 'content', 'two_column')
    """
    # 1. Resolve Layout Index
    # Config should map logical names to layout indices or names in the PPTX master
    layout_mapping = self.config.get("layout_mapping", {})
    
    # Default mapping if not provided (standard PPT layouts)
    default_mapping = {
        "title": 0,           # Title Slide
        "title_and_content": 1,
        "section": 2,         # Section Header
        "two_column": 4,      # Two Content
        "comparison": 4,
        "title_only": 5,
        "blank": 6,
        "content": 1,         # Map generic content to Title and Content
        "bullets": 1,
        "table": 1,
        "chart": 1
    }
    
    # Try to find the layout index/name
    # Check specific mapping first, then fall back to default
    target_layout_id = layout_mapping.get(layout_name)
    if target_layout_id is None:
            # Try mapping from content_type_mapping logic (which gives us e.g. 'title_slide', 'agenda_slide')
            # But here we passed 'layout_name' which comes from slide_data.layout_type
            # formatting it to match keys might be needed
            target_layout_id = default_mapping.get(layout_name, 1) # Default to 1 (Title and Content)

    layout = None
    if isinstance(target_layout_id, int):
        if target_layout_id < len(self.prs.slide_layouts):
            layout = self.prs.slide_layouts[target_layout_id]
    elif isinstance(target_layout_id, str):
        # Find by name
        for l in self.prs.slide_layouts:
            if l.name == target_layout_id:
                layout = l
                break
    
    if not layout:
        logger.warning(f"⚠️  Layout '{target_layout_id}' not found. Using default (1).")
        layout = self.prs.slide_layouts[1]

    # 2. Create Slide
    slide = self.prs.slides.add_slide(layout)
    
    # 3. Populate Placeholders
    # We iterate through placeholders and try to match them with content
    for shape in slide.placeholders:
        ph_type = shape.placeholder_format.type
        ph_idx = shape.placeholder_format.idx
        ph_name = shape.name.lower()
        
        # --- TITLE ---
        if ph_type == 1 or ph_type == 3: # Title or Center Title
            if slide_data.title:
                shape.text = self._scrub_title(slide_data.title)
        
        # --- SUBTITLE --- (Often on Title Slides)
        elif ph_type == 4: # Subtitle
            subtitle_parts = []
            if slide_data.subtitle:
                subtitle_parts.append(slide_data.subtitle)
            if slide_data.author:
                subtitle_parts.append(slide_data.author)
            if subtitle_parts:
                shape.text = "\n".join(subtitle_parts)
        
        # --- BODY / CONTENT ---
        elif ph_type == 2 or ph_type == 7: # Body or Object
            # Check what content we have
            if slide_data.bullets:
                tf = shape.text_frame
                tf.clear()
                for bullet in slide_data.bullets:
                    p = tf.add_paragraph()
                    p.text = bullet.text
                    p.level = 0
            elif slide_data.content:
                shape.text = slide_data.content
            elif slide_data.table_data:
                # Creating native table is complex inside a placeholder, 
                # usually better to delete placeholder and add table, 
                # or if the placeholder supports it.
                # For MVP native mode, we might skip complex objects or implement basic text fallback.
                pass
        
        # --- PICTURE ---
        elif ph_type == 18: # Picture
                if slide_data.image_path:
                    # Insert image into placeholder
                    # enable image insertion logic here
                    pass
                    
        # --- DATE / FOOTER / SLIDE NUM ---
        elif ph_type == 15 or ph_type == 16:
            pass # Usually handled by master, but can be overridden

    logger.info(f"   Created native slide: {slide_data.title} (Layout: {layout.name})")

