import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Tuple, Optional, Dict, Any

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR, MSO_AUTO_SIZE
from pptx.oxml import parse_xml
from pptx.util import Inches, Pt

from config import settings
from models.presentation import PresentationData, SlideContent, TableData
from services.chart_service import ChartService
from services.icon_service import IconService
from services.image_service import ImageService
from services.table_service import TableService
from services.template_service import TemplateService

logger = logging.getLogger("pptx_generator")

# FIXED: Constants instead of magic numbers
MAX_BULLETS_PER_SLIDE = 6
MAX_TABLE_ROWS_PER_SLIDE = 8
SLIDE_WIDTH_INCHES = 10.0
SLIDE_HEIGHT_INCHES = 5.625


class PptxGenerator:
    """
    Enhanced PPT Generator with perfect section header centering
    """

    def __init__(self, template_id: str = "standard"):
        """Initialize generator with template"""
        self.template_id = template_id
        
        # Initialize services
        self.template_service = TemplateService()
        self.icon_service = IconService()
        self.chart_service = ChartService(template_id=template_id)
        self.table_service = TableService(template_id=template_id)
        self.image_service = ImageService()
        
        # Load template configuration
        self.template = self.template_service.get_template(template_id)
        self.config = self.template["config"]
        self.theme = self.config["theme"]
        self.typography = self.config["typography"]
        
        # Presentation instance
        self.prs: Optional[Presentation] = None
        
        # FIXED: Cache for calculated values
        self._font_size_cache: Dict[str, int] = {}
        self._scrubbed_titles: Dict[str, str] = {}
        
        logger.info(f" PptxGenerator initialized with template: {template_id}")

    # ==================== UTILITY METHODS ====================

    @staticmethod
    def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
        """
        Convert hex color to RGB tuple
        """
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    def _auto_fit_textbox(self, text_frame, min_pt: int = 12, max_pt: int = 44) -> None:
        """Use native PowerPoint auto-fit"""
        try:
            text_frame.word_wrap = True
            text_frame.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
            for p in text_frame.paragraphs:
                if p.font.size is None:
                    p.font.size = Pt(max_pt)
        except Exception as e:
            logger.warning(f"  Auto-fit failed: {e}")

    def _calculate_text_width(self, text: str, font_size_pt: int) -> float:
        """Estimate text width in inches for centering calculations"""
        # Average character width is ~0.5 * font_size in points
        char_width_pt = font_size_pt * 0.5
        total_width_pt = len(text) * char_width_pt
        return total_width_pt / 72.0  # Convert to inches

    def _scrub_title(self, title: str) -> str:
        """
        Remove '(continued)' and page markers
        """
        if not title:
            return ""
        
        # Check cache
        if title in self._scrubbed_titles:
            return self._scrubbed_titles[title]
        
        # Scrub
        t = title.strip()
        t = re.sub(r"\(\s*continued\s*\)", "", t, flags=re.IGNORECASE)
        t = re.sub(r"\(\s*\d+\s*/\s*\d+\s*\)", "", t)
        result = re.sub(r"\s{2,}", " ", t).strip(" -–—·")
        
        # Cache result
        self._scrubbed_titles[title] = result
        return result

    def _dynamic_font_size(self, text: str, base_size: int, max_chars: int) -> int:
        """
        Dynamically adjust font size based on text length
        """
        cache_key = f"{text[:50]}_{base_size}_{max_chars}"
        
        if cache_key in self._font_size_cache:
            return self._font_size_cache[cache_key]
        
        text_len = len(text)
        
        if text_len <= max_chars * 0.5:
            size = base_size
        elif text_len <= max_chars * 0.75:
            size = max(int(base_size - 4), int(base_size * 0.8))
        elif text_len <= max_chars:
            size = max(int(base_size - 8), int(base_size * 0.7))
        else:
            size = max(int(base_size - 12), int(base_size * 0.6))
        
        self._font_size_cache[cache_key] = size
        return size

    # ==================== BACKGROUND & DECORATIVE ELEMENTS ====================

    def apply_gradient_background(self, slide, gradient_config: Dict) -> None:
        """Apply gradient background to slide"""
        try:
            stops = gradient_config.get("stops", [])
            if len(stops) < 2:
                logger.warning("  Gradient needs at least 2 stops")
                return
            
            angle = gradient_config.get("angle", 90)
            
            gradient_xml = f"""
            <p:bg xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
                  xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
              <p:bgPr>
                <a:gradFill>
                  <a:gsLst>
            """
            
            for stop in stops:
                pos = int(stop["position"] * 1000) if stop["position"] <= 1 else int(stop["position"])
                color_hex = stop["color"].lstrip("#")
                gradient_xml += f'<a:gs pos="{pos}"><a:srgbClr val="{color_hex}"/></a:gs>'
            
            gradient_xml += f"""
                  </a:gsLst>
                  <a:lin ang="{angle * 60000}" scaled="0"/>
                </a:gradFill>
              </p:bgPr>
            </p:bg>
            """
            
            bg_element = parse_xml(gradient_xml)
            slide._element.insert(0, bg_element)
            
        except Exception as e:
            logger.error(f" Gradient background failed: {e}")

    def add_decorative_shape(self, slide, shape_config: Dict) -> Optional[Any]:
        """Add decorative shape"""
        try:
            pos = shape_config["position"]
            size = shape_config["size"]
            left, top = Inches(pos["left"]), Inches(pos["top"])
            width, height = Inches(size["width"]), Inches(size["height"])

            shape_type = shape_config.get("shape_type", "rectangle")
            if shape_type == "rounded_rectangle":
                shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
            elif shape_type == "circle":
                shape = slide.shapes.add_shape(MSO_SHAPE.OVAL, left, top, width, height)
            else:
                shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)

            shape.fill.solid()
            shape.fill.fore_color.rgb = RGBColor(*self.hex_to_rgb(shape_config["fill_color"]))

            if "opacity" in shape_config:
                shape.fill.fore_color.transparency = 1 - shape_config["opacity"]

            if shape_config.get("border_width", 0) > 0:
                shape.line.color.rgb = RGBColor(*self.hex_to_rgb(shape_config.get("border_color", "#000000")))
                shape.line.width = Pt(shape_config["border_width"])
            else:
                shape.line.fill.background()

            return shape
            
        except Exception as e:
            logger.error(f" Shape error: {e}")
            return None

    # ==================== SECTION HEADER ====================

    def _add_centered_section_header(self, slide, title: str, icon_name: str) -> None:
        """
        Add perfectly centered section header with icon above title
        Icon and title are centered as a unit on the slide
        """
        try:
            # Configuration
            icon_size_pt = 72
            icon_size_in = icon_size_pt / 72.0
            
            # Dynamic font size (cached)
            title_font_size = self._dynamic_font_size(title, base_size=40, max_chars=40)
            
            # Estimate title width
            title_width_in = self._calculate_text_width(title, title_font_size)
            
            # Calculate center position for title
            title_left = (SLIDE_WIDTH_INCHES - title_width_in) / 2.0
            title_top = 2.8
            title_height = 1.0
            
            # Icon centered above title
            icon_gap = 0.4
            icon_top = title_top - icon_size_in - icon_gap
            icon_left = (SLIDE_WIDTH_INCHES - icon_size_in) / 2.0
            
            # Add icon
            icon_image = self.icon_service.render_to_png(icon_name, icon_size_pt, "#FFFFFF")
            if icon_image:
                slide.shapes.add_picture(
                    icon_image,
                    Inches(icon_left),
                    Inches(icon_top),
                    width=Inches(icon_size_in),
                    height=Inches(icon_size_in)
                )
            
            # Add title textbox
            textbox_left = max(0.5, title_left - 0.5)
            textbox_width = min(9.0, title_width_in + 1.0)
            
            textbox = slide.shapes.add_textbox(
                Inches(textbox_left),
                Inches(title_top),
                Inches(textbox_width),
                Inches(title_height)
            )
            
            tf = textbox.text_frame
            tf.clear()
            tf.word_wrap = False
            tf.vertical_anchor = MSO_ANCHOR.MIDDLE
            
            p = tf.paragraphs[0]
            p.text = title  # Already scrubbed
            p.alignment = PP_ALIGN.CENTER
            p.font.bold = True
            p.font.size = Pt(title_font_size)
            p.font.color.rgb = RGBColor(255, 255, 255)
            p.font.name = self.typography.get("heading_font", "Calibri")
            
            # Underline
            underline_width = min(3.5, title_width_in + 0.3)
            underline_left = (SLIDE_WIDTH_INCHES - underline_width) / 2.0
            underline = slide.shapes.add_shape(
                MSO_SHAPE.RECTANGLE,
                Inches(underline_left),
                Inches(3.9),
                Inches(underline_width),
                Inches(0.05)
            )
            underline.fill.solid()
            underline.fill.fore_color.rgb = RGBColor(255, 255, 255)
            underline.fill.fore_color.transparency = 0.3
            underline.line.fill.background()
            
            logger.info(f" Centered section header: '{title}' with icon '{icon_name}'")
            
        except Exception as e:
            logger.error(f" Section header centering failed: {e}")

    # ==================== CONTENT METRICS ====================

    def _calculate_content_metrics(self, slide_data: SlideContent) -> Dict[str, Any]:
        """
        Calculate content density metrics
        """
        metrics = {
            "bullet_count": 0,
            "total_text_length": 0,
            "sub_bullet_count": 0,
            "has_long_bullets": False,
            "content_density": "low",
        }

        if slide_data.bullets:
            metrics["bullet_count"] = len(slide_data.bullets)
            for bullet in slide_data.bullets:
                text_len = len(bullet.text or "")
                metrics["total_text_length"] += text_len
                if text_len > 80:
                    metrics["has_long_bullets"] = True
                if bullet.sub_bullets:
                    metrics["sub_bullet_count"] += len(bullet.sub_bullets)
                    metrics["total_text_length"] += sum(len(s or "") for s in bullet.sub_bullets)

        # Determine density
        if metrics["bullet_count"] <= 2 and metrics["total_text_length"] < 200:
            metrics["content_density"] = "low"
        elif metrics["bullet_count"] <= 4 and metrics["total_text_length"] < 500:
            metrics["content_density"] = "medium"
        else:
            metrics["content_density"] = "high"

        return metrics

    def _get_dynamic_layout_config(self, slide_data: SlideContent, metrics: Dict) -> Dict[str, Any]:
        """Determine layout configuration based on content"""
        if not getattr(slide_data, "needs_image", False):
            return {
                "use_image": False,
                "content_width": 8.5,
                "content_left": 0.85,
                "image_config": None,
            }

        if metrics["content_density"] == "low":
            return {
                "use_image": True,
                "layout_style": "image_prominent",
                "content_width": 4.2,
                "content_left": 0.85,
                "image_config": {"left": 5.4, "top": 1.2, "width": 4.0, "height": 4.0, "card_padding": 0.15},
            }
        elif metrics["content_density"] == "medium":
            return {
                "use_image": True,
                "layout_style": "balanced",
                "content_width": 4.6,
                "content_left": 0.85,
                "image_config": {"left": 5.8, "top": 1.5, "width": 3.6, "height": 3.5, "card_padding": 0.1},
            }
        else:
            return {
                "use_image": True,
                "layout_style": "compact",
                "content_width": 5.2,
                "content_left": 0.85,
                "image_config": {"left": 6.4, "top": 1.3, "width": 3.0, "height": 2.8, "card_padding": 0.08},
            }

    # ==================== MAIN GENERATION ====================

    def generate(self, presentation_data: PresentationData, generate_images: bool = True) -> str:
        """
        Generate complete presentation
        """
        logger.info(" Starting PPTX generation...")
        
        # Initialize presentation
        self.prs = Presentation()
        self.prs.slide_width = Inches(self.config["slide_dimensions"]["width"])
        self.prs.slide_height = Inches(self.config["slide_dimensions"]["height"])

        # FIXED: Scrub all titles ONCE at the start
        for slide_data in presentation_data.slides:
            if slide_data.title:
                slide_data.title = self._scrub_title(slide_data.title)

        # Title slide
        self._add_title_slide(presentation_data.title, presentation_data.subtitle, presentation_data.author)

        # Content slides
        for slide_data in presentation_data.slides:
            # FIXED: Use constant instead of magic number
            if slide_data.bullets and len(slide_data.bullets) > MAX_BULLETS_PER_SLIDE:
                self._add_paginated_slides(slide_data, generate_images)
            elif slide_data.table_data and len(slide_data.table_data.rows) > MAX_TABLE_ROWS_PER_SLIDE:
                self._add_paginated_table_slides(slide_data)
            else:
                self._add_enhanced_slide(slide_data, generate_images)

        # Save
        output_path = self._get_output_path(presentation_data.title)
        self.prs.save(output_path)
        
        logger.info(f" PPTX generated: {output_path}")
        return output_path

    # ==================== TITLE SLIDE ====================

    def _add_title_slide(self, title: str, subtitle: Optional[str], author: Optional[str]) -> None:
        """Add title slide"""
        slide = self.prs.slides.add_slide(self.prs.slide_layouts[6])
        
        # Background
        if "backgrounds" in self.config and "title_slide" in self.config["backgrounds"]:
            self.apply_gradient_background(slide, self.config["backgrounds"]["title_slide"])

        # Top orange bar
        top_bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(10), Inches(0.12))
        top_bar.fill.solid()
        top_bar.fill.fore_color.rgb = RGBColor(249, 115, 22)
        top_bar.line.fill.background()

        # Icon
        icon_name = self.icon_service.auto_select_icon(title, subtitle or "")
        icon_image = self.icon_service.render_to_png(icon_name, 80, "#FFFFFF")
        if icon_image:
            slide.shapes.add_picture(icon_image, Inches(4.3), Inches(1.5), width=Inches(80/72), height=Inches(80/72))

        # Title
        title_box = slide.shapes.add_textbox(Inches(0.8), Inches(2.6), Inches(8.4), Inches(1.4))
        tf = title_box.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        p.text = title
        p.alignment = PP_ALIGN.CENTER
        p.font.bold = True
        p.font.size = Pt(self._dynamic_font_size(title, 44, 50))
        p.font.color.rgb = RGBColor(255, 255, 255)

        # Subtitle
        if subtitle or author:
            subtitle_text = f"{subtitle or ''}\n{author or ''}".strip()
            subtitle_box = slide.shapes.add_textbox(Inches(1.5), Inches(4.1), Inches(7), Inches(0.6))
            tf = subtitle_box.text_frame
            p = tf.paragraphs[0]
            p.text = subtitle_text
            p.alignment = PP_ALIGN.CENTER
            p.font.size = Pt(20)
            p.font.color.rgb = RGBColor(209, 213, 219)

        # Decorative circle
        circle1 = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(8.2), Inches(1.0), Inches(1.5), Inches(1.5))
        circle1.fill.solid()
        circle1.fill.fore_color.rgb = RGBColor(6, 182, 212)
        circle1.fill.fore_color.transparency = 0.7
        circle1.line.fill.background()
        
        logger.info(f" Title slide added: {title}")

    # ==================== CONTENT SLIDES ====================

    def _add_enhanced_slide(self, slide_data: SlideContent, generate_images: bool = True) -> None:
        """Add content slide with appropriate layout"""
        slide = self.prs.slides.add_slide(self.prs.slide_layouts[6])

        # Section header special handling
        if slide_data.layout_type == "section":
            if "backgrounds" in self.config and "section_header" in self.config["backgrounds"]:
                self.apply_gradient_background(slide, self.config["backgrounds"]["section_header"])
            
            # Top orange bar
            top_bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(10), Inches(0.15))
            top_bar.fill.solid()
            top_bar.fill.fore_color.rgb = RGBColor(249, 115, 22)
            top_bar.line.fill.background()
            
            # Centered header (title already scrubbed)
            self._add_centered_section_header(slide, slide_data.title, slide_data.icon_name or "circle")
            return

        # Apply content background
        if "backgrounds" in self.config and "content_slide" in self.config["backgrounds"]:
            self.apply_gradient_background(slide, self.config["backgrounds"]["content_slide"])

        # Sidebar
        sidebar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(0.15), Inches(5.625))
        sidebar.fill.solid()
        sidebar.fill.fore_color.rgb = RGBColor(30, 41, 59)
        sidebar.line.fill.background()

        # Icon
        if slide_data.icon_name:
            icon_image = self.icon_service.render_to_png(slide_data.icon_name, 36, "#06B6D4")
            if icon_image:
                slide.shapes.add_picture(icon_image, Inches(0.35), Inches(0.4), width=Inches(0.5), height=Inches(0.5))

        # Title (already scrubbed, cached font size)
        title_font_size = self._dynamic_font_size(slide_data.title, 28, 50)
        title_box = slide.shapes.add_textbox(Inches(0.95), Inches(0.38), Inches(8.5), Inches(0.55))
        tf = title_box.text_frame
        p = tf.paragraphs[0]
        p.text = slide_data.title
        p.font.bold = True
        p.font.size = Pt(title_font_size)
        p.font.color.rgb = RGBColor(31, 41, 55)

        # Divider line
        divider = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.35), Inches(1.0), Inches(9.4), Inches(0.02))
        divider.fill.solid()
        divider.fill.fore_color.rgb = RGBColor(6, 182, 212)
        divider.line.fill.background()

        # FIXED: Calculate metrics once
        metrics = self._calculate_content_metrics(slide_data)
        layout_config = self._get_dynamic_layout_config(slide_data, metrics)

        # Content based on type
        if slide_data.chart_data:
            self._add_chart(slide, slide_data.chart_data, 0.85, 1.3, 8.5, 3.75)
        elif slide_data.table_data:
            self._add_table(slide, slide_data.table_data, 0.85, 1.3, 8.5, 3.7)
        elif slide_data.bullets:
            self._add_bullets(slide, slide_data, layout_config)
        
        # Add image if needed
        if (generate_images and layout_config["use_image"] and 
            slide_data.bullets and not slide_data.table_data and not slide_data.chart_data):
            self._add_generated_image(slide, slide_data, layout_config["image_config"])

    def _add_bullets(self, slide, slide_data: SlideContent, layout_config: Dict) -> None:
        """Add bullet content with dynamic sizing"""
        content_left = layout_config["content_left"]
        content_width = layout_config["content_width"]
        
        textbox = slide.shapes.add_textbox(
            Inches(content_left),
            Inches(1.35),
            Inches(content_width),
            Inches(3.7)
        )
        tf = textbox.text_frame
        tf.word_wrap = True
        tf.margin_top = Inches(0.05)
        tf.margin_bottom = Inches(0.05)
        
        bullets = slide_data.bullets or []
        num_bullets = len(bullets)
        
        # Dynamic font sizing based on bullet count
        if num_bullets <= 2:
            main_size, sub_size = 18, 15
            main_spacing, sub_spacing = 1.3, 1.2
            space_after_main, space_after_sub = 10, 6
        elif num_bullets == 3:
            main_size, sub_size = 17, 14
            main_spacing, sub_spacing = 1.25, 1.15
            space_after_main, space_after_sub = 8, 5
        else:  # 4+ bullets
            main_size, sub_size = 16, 13
            main_spacing, sub_spacing = 1.2, 1.1
            space_after_main, space_after_sub = 6, 4
        
        for idx, bullet in enumerate(bullets):
            # Main bullet
            p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
            clean_text = (bullet.text or "").replace("**", "").replace("*", "").strip()
            p.text = clean_text
            p.font.bold = True
            p.font.size = Pt(main_size)
            p.font.color.rgb = RGBColor(16, 185, 129)
            p.line_spacing = main_spacing
            p.space_after = Pt(space_after_main)
            p.space_before = Pt(8 if idx > 0 else 0)
            p.level = 0
            
            # Sub-bullets
            if bullet.sub_bullets:
                for sub in bullet.sub_bullets[:4]:
                    sp = tf.add_paragraph()
                    clean_sub = (sub or "").replace("**", "").replace("*", "").strip()
                    sp.text = f"○ {clean_sub}"
                    sp.font.size = Pt(sub_size)
                    sp.font.color.rgb = RGBColor(107, 114, 128)
                    sp.line_spacing = sub_spacing
                    sp.space_after = Pt(space_after_sub)
                    sp.space_before = Pt(2)
                    sp.level = 1
        
        # Apply auto-fit as fallback
        self._auto_fit_textbox(tf, min_pt=12, max_pt=main_size)

    def _add_generated_image(self, slide, slide_data: SlideContent, image_config: Optional[Dict]) -> None:
        """Add AI-generated image with card"""
        if not image_config:
            return
        
        try:
            image_content = " ".join([bullet.text for bullet in (slide_data.bullets or [])[:1]])
            image_bytes = self.image_service.generate_image_for_slide(slide_data.title, image_content)
            if not image_bytes:
                return

            # Card
            padding = image_config["card_padding"]
            card_left = Inches(image_config["left"] - padding)
            card_top = Inches(image_config["top"] - padding)
            card_width = Inches(image_config["width"] + 2 * padding)
            card_height = Inches(image_config["height"] + padding * 4)

            card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, card_left, card_top, card_width, card_height)
            card.fill.solid()
            card.fill.fore_color.rgb = RGBColor(255, 255, 255)
            card.line.color.rgb = RGBColor(229, 231, 235)
            card.line.width = Pt(1)

            # Image
            slide.shapes.add_picture(
                image_bytes,
                Inches(image_config["left"]),
                Inches(image_config["top"]),
                width=Inches(image_config["width"]),
                height=Inches(image_config["height"])
            )

            # Accent bar
            accent_bar = slide.shapes.add_shape(
                MSO_SHAPE.RECTANGLE,
                card_left,
                Inches(image_config["top"] + image_config["height"] + padding),
                card_width,
                Inches(0.15)
            )
            accent_bar.fill.solid()
            accent_bar.fill.fore_color.rgb = RGBColor(249, 115, 22)
            accent_bar.line.fill.background()

            logger.info(f" Added image for '{slide_data.title}'")
            
        except Exception as e:
            logger.warning(f" Image generation failed: {e}")

    def _add_chart(self, slide, chart_data, left: float, top: float, width: float, height: float) -> None:
        """Add chart to slide"""
        try:
            self.chart_service.add_native_chart(
                slide=slide,
                chart_data=chart_data.dict() if hasattr(chart_data, "dict") else chart_data,
                position={"left": left, "top": top},
                size={"width": width, "height": height},
                background_rgb=self.hex_to_rgb("#ECFDF5")
            )
            logger.info(" Chart added")
        except Exception as e:
            logger.error(f" Chart error: {e}")

    def _add_table(self, slide, table_data, left: float, top: float, width: float, height: float) -> None:
        """Add table to slide with improved styling"""
        try:
            table_dict = table_data.dict() if hasattr(table_data, "dict") else table_data
            headers = table_dict.get("headers", [])
            rows = table_dict.get("rows", [])
            
            if not headers or not rows:
                logger.warning(" Table missing data")
                return

            num_cols = len(headers)
            num_rows = len(rows) + 1
            
            table_shape = slide.shapes.add_table(
                num_rows, num_cols,
                Inches(left), Inches(top),
                Inches(width), Inches(height)
            )
            table = table_shape.table
            
            # Dynamic font sizing
            header_font_size = 14 if num_cols <= 3 else 12
            cell_font_size = 13 if num_cols <= 3 else 11
            
            # Header row
            for col_idx, header in enumerate(headers):
                cell = table.cell(0, col_idx)
                cell.text = str(header)
                cell.fill.solid()
                cell.fill.fore_color.rgb = RGBColor(6, 182, 212)
                
                for paragraph in cell.text_frame.paragraphs:
                    paragraph.font.bold = True
                    paragraph.font.size = Pt(header_font_size)
                    paragraph.font.color.rgb = RGBColor(255, 255, 255)
                    paragraph.alignment = PP_ALIGN.CENTER
                
                cell.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
                cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            
            # Data rows
            for row_idx, row in enumerate(rows, start=1):
                for col_idx, cell_value in enumerate(row):
                    cell = table.cell(row_idx, col_idx)
                    cell.text = str(cell_value)
                    
                    cell.fill.solid()
                    if row_idx % 2 == 0:
                        cell.fill.fore_color.rgb = RGBColor(248, 249, 250)
                    else:
                        cell.fill.fore_color.rgb = RGBColor(255, 255, 255)
                    
                    for paragraph in cell.text_frame.paragraphs:
                        paragraph.font.size = Pt(cell_font_size)
                        paragraph.font.color.rgb = RGBColor(31, 41, 55)
                        if col_idx == 0 or len(str(cell_value)) > 50:
                            paragraph.alignment = PP_ALIGN.LEFT
                        else:
                            paragraph.alignment = PP_ALIGN.CENTER
                    
                    cell.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
                    cell.text_frame.word_wrap = True
                    cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            
            # Set widths and heights
            col_width = Inches(width / num_cols)
            for col_idx in range(num_cols):
                table.columns[col_idx].width = col_width
            
            row_height = Inches(height / num_rows)
            for row_idx in range(num_rows):
                table.rows[row_idx].height = row_height
            
            logger.info(f" Table added: {num_cols} cols × {num_rows} rows")
            
        except Exception as e:
            logger.error(f" Table error: {e}")

    # ==================== PAGINATION ====================

    def _add_paginated_slides(self, slide_data: SlideContent, generate_images: bool = True) -> None:
        """
        Split large bullet lists across slides
        """
        total_bullets = len(slide_data.bullets)
        num_slides = (total_bullets + MAX_BULLETS_PER_SLIDE - 1) // MAX_BULLETS_PER_SLIDE

        for page in range(num_slides):
            start_idx = page * MAX_BULLETS_PER_SLIDE
            end_idx = min(start_idx + MAX_BULLETS_PER_SLIDE, total_bullets)

            # FIXED: Create new object instead of deepcopy
            page_slide = SlideContent(
                layout_type=slide_data.layout_type,
                title=slide_data.title,  # Already scrubbed
                icon_name=slide_data.icon_name,
                bullets=slide_data.bullets[start_idx:end_idx],
                needs_image=(generate_images and page == 0)
            )
            
            self._add_enhanced_slide(page_slide, generate_images and page == 0)

    def _add_paginated_table_slides(self, slide_data: SlideContent) -> None:
        """
        Split large tables across slides
        """
        headers = slide_data.table_data.headers
        all_rows = slide_data.table_data.rows
        num_slides = (len(all_rows) + MAX_TABLE_ROWS_PER_SLIDE - 1) // MAX_TABLE_ROWS_PER_SLIDE

        for page in range(num_slides):
            start_idx = page * MAX_TABLE_ROWS_PER_SLIDE
            end_idx = min(start_idx + MAX_TABLE_ROWS_PER_SLIDE, len(all_rows))

            # FIXED: Create new objects
            page_slide = SlideContent(
                layout_type=slide_data.layout_type,
                title=slide_data.title,  # Already scrubbed
                icon_name=slide_data.icon_name,
                table_data=TableData(headers=headers, rows=all_rows[start_idx:end_idx])
            )
            
            self._add_enhanced_slide(page_slide, False)

    # ==================== OUTPUT ====================

    def _get_output_path(self, title: str) -> str:
        """Generate output file path with safe filename"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # FIXED: Better filename sanitization
        safe_title = (title or "Presentation").strip()
        safe_title = re.sub(r'[<>:"/\\|?*]', '', safe_title)  # Remove invalid chars
        safe_title = safe_title.replace(" ", "_")[:50]  # Limit length
        
        filename = f"{safe_title}_{timestamp}.pptx"
        output_dir = Path(settings.OUTPUT_DIR)
        output_dir.mkdir(exist_ok=True, parents=True)
        
        return str(output_dir / filename)
