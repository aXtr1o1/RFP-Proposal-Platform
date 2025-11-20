import logging
import re
import json
from datetime import datetime
from pathlib import Path
from typing import Tuple, Optional, Dict, Any, List
from io import BytesIO

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.oxml import parse_xml
from pptx.util import Inches, Pt

from apps.app.config import settings
from apps.app.models.presentation import PresentationData, SlideContent, TableData, BulletPoint
from apps.app.services.chart_service import ChartService
from apps.app.services.icon_service import IconService
from apps.app.utils.content_validator import validate_presentation

logger = logging.getLogger("pptx_generator")


class PptxGenerator:
    """Enhanced Multilingual PPTX Generator with Full RTL/LTR Support"""

    MASTER_LAYOUT_INDEX = {
        "title": 0,
        "title_and_content": 1,
        "section_header": 2,
        "two_content": 3,
        "comparison": 4,
        "title_only": 5,
        "blank": 6,
        "content_with_caption": 7,
        "picture_with_caption": 8
    }

    def __init__(self, template_id, language):
        self.template_id = template_id
        self.target_language = self._normalize_language_code(language) if language else None
        logger.info(f"🔍 PptxGenerator init: language={language} → normalized={self.target_language}")
   

        self.template_dir = Path(settings.TEMPLATES_DIR) / template_id
        logger.info(f"🔍 Initializing MULTILINGUAL generator: {self.template_dir}")

        if not self.template_dir.exists():
            raise FileNotFoundError(f"Template directory not found: {self.template_dir}")

        self.backgrounds_dir = self.template_dir / "Background"
        if not self.backgrounds_dir.exists():
            self.backgrounds_dir = self.template_dir / "backgrounds"

        # Load JSON configurations
        self.config = self._load_json("config.json")
        self.theme = self._load_json("theme.json") if (self.template_dir / "theme.json").exists() else self._get_default_theme()
        self.constraints = self._load_json("constraints.json")
        self.layouts = self._load_json("layouts.json")

        # Initialize services
        try:
            self.icon_service = IconService(template_id=template_id)
            logger.info("✅ IconService loaded")
        except Exception as e:
            logger.warning(f"⚠️  IconService failed: {e}")
            self.icon_service = None

        try:
            self.chart_service = ChartService(template_id=template_id)
            logger.info("✅ ChartService loaded")
        except Exception as e:
            logger.warning(f"⚠️  ChartService failed: {e}")
            self.chart_service = None

        self.prs: Optional[Presentation] = None
        self.lang_config = None
        self.section_header_counter = 0

        logger.info(f"✅ MULTILINGUAL Generator initialized")

    def _load_json(self, filename: str) -> Dict:
        json_path = self.template_dir / filename
        if not json_path.exists():
            raise FileNotFoundError(f"Required: {json_path}")
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _get_default_theme(self) -> Dict:
        return {
            "colors": {
                "primary": "#F5F0E8",
                "text_primary": "#0D2026",
                "text_inverse": "#FFFCEC",
                "accent_teal": "#01415C"
            },
            "typography": {
                "font_families": {"primary": "Cairo", "body": "Tajawal"},
                "font_sizes": {"title": 44, "body": 18}
            }
        }

    # ========================================================================
    # LANGUAGE CONFIGURATION - ENHANCED
    # ========================================================================
    def _normalize_language_code(self, language: str) -> str:
        """Normalize to 2-letter code matching config keys"""
        if not language:
            return 'en'
        
        lang_lower = language.lower().strip()
        
        language_map = {
            'arabic': 'ar',
            'ar': 'ar',
            'Arabic': 'ar',
            'english': 'en',
            'en': 'en',
            'English': 'en',
        }
        
        return language_map.get(lang_lower, 'en')

    def _detect_and_configure_language(self, presentation_data: PresentationData):
        """Detect and configure language with proper precedence"""
        lang_settings = self.config.get('language_settings', {})
        
        # *** FIX 1: Check presentation_data.language first ***
        if presentation_data and hasattr(presentation_data, 'language'):
            presentation_lang = presentation_data.language
            if presentation_lang:
                self.target_language = self._normalize_language_code(presentation_lang)
                logger.info(f"🌐 Language from presentation_data: {presentation_lang} → {self.target_language}")
                # Don't return - continue to configure
        
        # *** FIX 2: If still no language, use config default ***
        if not self.target_language:
            self.target_language = lang_settings.get('default', 'en')
            logger.info(f"🌐 Using default language: {self.target_language}")
        
        # *** FIX 3: Validate language exists in config ***
        if self.target_language not in lang_settings:
            logger.warning(f"⚠️  Language '{self.target_language}' not in config, using 'en'")
            self.target_language = 'en'
        
        # *** FIX 4: Get language configuration ***
        self.lang_config = lang_settings.get(self.target_language, {
            'rtl': False,
            'default_font': 'Arial',
            'heading_font': 'Arial',
            'alignment': 'left'
        })
        
        is_rtl = self.lang_config.get('rtl', False)
        text_direction = self.lang_config.get('text_direction', 'ltr' if not is_rtl else 'rtl')
        alignment = self.lang_config.get('alignment', 'left')
        icon_position = self.lang_config.get('icon_position', 'left')

        logger.info(f"   ✅ Language configured: {self.target_language}")
        logger.info(f"   RTL: {is_rtl}, Direction: {text_direction}")
        logger.info(f"   Alignment: {alignment}, Icon Position: {icon_position}")


    def get_language_suffix(self) -> str:
        """Get language suffix for position keys - MUST be 2-letter code"""
        # Ensure we have normalized 2-letter code
        normalized = self._normalize_language_code(self.target_language)
        return f"_{normalized}" 

    def get_position(self, element: Dict, key: str = "position") -> Dict:
        """Get position with language-specific fallback"""
        lang_suffix = self.get_language_suffix()
        lang_key = f"{key}{lang_suffix}"
        
        # Try language-specific position first
        if lang_key in element:
            return element[lang_key]
        
        # Fallback to default position
        return element.get(key, {})

    def get_style_value(self, style: Dict, key: str, default=None):
        """Get style value with language-specific fallback"""
        if not style:
            return default
        
        lang_suffix = self.get_language_suffix()
        lang_key = f"{key}{lang_suffix}"
        
        # Try language-specific value first
        if lang_key in style:
            return style[lang_key]
        
        # Fallback to default value
        return style.get(key, default)

    def get_text_alignment(self, style: Dict = None, force_center: bool = False) -> PP_ALIGN:
        """Get correct alignment based on language and style"""
        if force_center:
            return PP_ALIGN.CENTER
        
        # Try to get alignment from style first
        if style:
            alignment = self.get_style_value(style, 'alignment')
            if alignment:
                return self._alignment_enum(alignment)
        
        # Get from constraints
        constraints_alignment = self.constraints.get('alignment', {})
        lang_alignment = constraints_alignment.get(self.target_language, {})
        default_align = lang_alignment.get('default', 'left')
        
        return self._alignment_enum(default_align)

    def _alignment_enum(self, alignment: str) -> PP_ALIGN:
        """Convert alignment string to PP_ALIGN enum"""
        alignment = (alignment or '').lower()
        
        if alignment == 'center':
            return PP_ALIGN.CENTER
        elif alignment == 'right':
            return PP_ALIGN.RIGHT
        elif alignment == 'justify':
            return PP_ALIGN.JUSTIFY
        else:
            return PP_ALIGN.LEFT

    # ========================================================================
    # DYNAMIC FONT AND COLOR RETRIEVAL
    # ========================================================================

    def get_font(self, font_type: str = 'body') -> str:
        """Get font from constraints based on language"""
        typography = self.constraints.get('typography', {})
        fonts = typography.get('fonts', {})
        lang_fonts = fonts.get(self.target_language, {})
        
        if font_type in ['title', 'heading', 'heading_font']:
            return lang_fonts.get('heading', 'Arial')
        elif font_type in ['bold', 'bold_font']:
            return lang_fonts.get('bold', 'Arial')
        else:
            return lang_fonts.get('body', 'Arial')

    def get_font_size(self, size_key: str) -> int:
        """Get font size from constraints"""
        typography = self.constraints.get('typography', {})
        font_sizes = typography.get('font_sizes', {})
        return font_sizes.get(size_key, 18)

    def get_line_spacing(self, spacing_key: str) -> float:
        """Get line spacing from constraints"""
        typography = self.constraints.get('typography', {})
        line_spacing = typography.get('line_spacing', {})
        return line_spacing.get(spacing_key, 1.5)

    def get_color_hex(self, color_key: str) -> str:
        """Get color from constraints"""
        colors = self.constraints.get('colors', {})
        return colors.get(color_key, '#000000')

    def hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """Convert hex to RGB"""
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    def get_color_rgb(self, color_key: str) -> Tuple[int, int, int]:
        """Get color as RGB tuple"""
        hex_color = self.get_color_hex(color_key)
        return self.hex_to_rgb(hex_color)

    # ========================================================================
    # LAYOUT SELECTION
    # ========================================================================

    def get_layout_for_content(self, content_type: str, slide_data=None) -> Dict:
        """Select correct layout with proper detection"""
        content_mapping = self.config.get('content_type_mapping', {})
        layout_name = None

        layout_hint = self._get_layout_hint(slide_data)
        
        if content_type == 'section':
            # *** FIX: Don't cycle through section layouts blindly ***
            section_layouts = content_mapping.get('section', ['section_header_dark'])
            
            if isinstance(section_layouts, list):
                # *** FIX: Log which layout we're using ***
                layout_name = section_layouts[self.section_header_counter % len(section_layouts)]
                logger.info(f"Section layout choice: {layout_name} (index {self.section_header_counter % len(section_layouts)})")
                self.section_header_counter += 1
            else:
                layout_name = section_layouts
            
            # *** FIX: Verify layout exists BEFORE using it ***
            if layout_name not in self.layouts:
                logger.error(f"❌ Section layout '{layout_name}' NOT FOUND in layouts.json")
                logger.error(f"Available layouts: {list(self.layouts.keys())}")
                layout_name = 'section_header_dark'
        
        # Try layout hint first
        if layout_hint:
            hint_lower = layout_hint.lower().strip().replace('_', '').replace('-', '')
            
            if layout_hint in content_mapping:
                layout_name = content_mapping[layout_hint]
            elif hint_lower in ['chartslide', 'chart']:
                layout_name = 'chart_slide'
            elif hint_lower in ['tableslide', 'table']:
                layout_name = 'table_slide'
            elif hint_lower in ['agenda', 'agendaslide']:
                layout_name = 'agenda_slide'
            elif 'fourbox' in hint_lower:
                layout_name = 'four_box_with_icons' if 'icon' in hint_lower else 'four_boxes'
            elif hint_lower in ['contentparagraph', 'paragraph']:
                layout_name = 'content_paragraph'
            elif hint_lower in ['twocontent', 'twocolumn', 'comparison']:
                layout_name = 'two_content'

        # Use content_type if no layout from hint
        if not layout_name:
            if content_type == 'section':
                section_layouts = content_mapping.get('section', ['section_header_dark'])
                if isinstance(section_layouts, list):
                    layout_name = section_layouts[self.section_header_counter % len(section_layouts)]
                    self.section_header_counter += 1
                else:
                    layout_name = section_layouts
            else:
                layout_name = content_mapping.get(content_type)
                if not layout_name:
                    if content_type == 'chart':
                        layout_name = 'chart_slide'
                    elif content_type == 'table':
                        layout_name = 'table_slide'
                    elif content_type == 'agenda':
                        layout_name = 'agenda_slide'
                    else:
                        layout_name = 'title_and_content'

        layout_config = self.layouts.get(layout_name)

        if not layout_config:
            logger.warning(f"⚠️  Layout '{layout_name}' not found, using title_and_content")
            layout_config = self.layouts.get('title_and_content', {})
            layout_name = 'title_and_content'

        logger.info(f"   ✓ Layout: '{layout_name}' (hint={layout_hint}, type={content_type})")
        return layout_config

    def _get_layout_hint(self, slide_data) -> Optional[str]:
        """Extract layout hint"""
        if slide_data is None:
            return None

        hint = None
        if isinstance(slide_data, dict):
            hint = slide_data.get('layout_hint')
        else:
            hint = getattr(slide_data, 'layout_hint', None)

        if isinstance(hint, str):
            hint_clean = hint.strip().lower()
            
            if 'agenda' in hint_clean:
                return 'agenda'
            elif 'four' in hint_clean and 'box' in hint_clean:
                return 'four_box_with_icons' if 'icon' in hint_clean else 'four_boxes'
            elif 'table' in hint_clean:
                return 'table_slide'
            elif 'chart' in hint_clean:
                return 'chart_slide'
            elif 'two' in hint_clean and ('column' in hint_clean or 'content' in hint_clean):
                return 'two_content'
            
            return hint_clean
        
        return None

    def _get_slide_layout(self, layout_config: Dict):
        """Get PowerPoint slide layout"""
        layout_index = layout_config.get('master_layout_index')
        if isinstance(layout_index, int) and 0 <= layout_index < len(self.prs.slide_layouts):
            return self.prs.slide_layouts[layout_index]

        layout_key = str(layout_config.get('master_layout', 'blank')).lower()
        mapped_index = self.MASTER_LAYOUT_INDEX.get(layout_key, self.MASTER_LAYOUT_INDEX['blank'])
        mapped_index = min(mapped_index, len(self.prs.slide_layouts) - 1)
        return self.prs.slide_layouts[mapped_index]

    def _clear_default_placeholders(self, slide):
        """Clear default placeholders"""
        for shape in list(slide.shapes):
            if getattr(shape, "is_placeholder", False):
                element = shape._element
                element.getparent().remove(element)

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def _get_data_value(self, data, key: Optional[str]):
        if not data or not key:
            return None
        if isinstance(data, dict):
            return data.get(key)
        return getattr(data, key, None)

    def _extract_text_value(self, data, element_id: str) -> str:
        text = self._get_data_value(data, element_id)

        if not text:
            if element_id == 'title' and hasattr(data, 'title'):
                text = data.title
            elif element_id == 'subtitle' and hasattr(data, 'subtitle'):
                text = getattr(data, 'subtitle', '')
            elif element_id == 'content' and hasattr(data, 'content'):
                text = getattr(data, 'content', '')

        if not text and hasattr(data, 'bullets') and data.bullets and element_id == 'content':
            text = " ".join(
                bullet.text for bullet in data.bullets if getattr(bullet, 'text', None)
            )

        if isinstance(text, list):
            text = "\n".join(str(item) for item in text if item)

        return (text or "").strip()

    def _coerce_bullet_points(self, value: Any) -> List[BulletPoint]:
        bullets: List[BulletPoint] = []
        if not value:
            return bullets

        if isinstance(value, list):
            for item in value:
                if isinstance(item, BulletPoint):
                    bullets.append(item)
                elif isinstance(item, dict):
                    try:
                        bullets.append(BulletPoint(**item))
                    except Exception:
                        text = item.get('text')
                        if text:
                            bullets.append(BulletPoint(text=text))
                elif item:
                    bullets.append(BulletPoint(text=str(item)))
        elif isinstance(value, str):
            bullets.append(BulletPoint(text=value))

        return bullets

    def _extract_bullet_items(self, data, element_id: Optional[str]) -> List[BulletPoint]:
        prioritized_value = None
        if element_id and element_id not in ('content', 'bullets'):
            prioritized_value = self._get_data_value(data, element_id)

        if prioritized_value:
            bullets = self._coerce_bullet_points(prioritized_value)
            if bullets:
                return bullets

        if hasattr(data, 'bullets') and data.bullets:
            return list(data.bullets)

        return []

    def _scrub_title(self, title: str) -> str:
        if not title:
            return ""
        t = title.strip()
        t = re.sub(r"\(\s*continued\s*\)", "", t, flags=re.IGNORECASE)
        return re.sub(r"\s{2,}", " ", t).strip()

    # ========================================================================
    # BACKGROUND & PAGE NUMBER
    # ========================================================================

    def _add_background(self, slide, bg_config: Dict) -> None:
        """Add background image"""
        try:
            if bg_config.get('type') == 'image':
                bg_path = self.template_dir / bg_config.get('path', '')

                if not bg_path.exists():
                    logger.warning(f"⚠️  Background not found: {bg_path}")
                    return

                width = Inches(self.constraints['layout']['slide_width'])
                height = Inches(self.constraints['layout']['slide_height'])

                picture = slide.shapes.add_picture(
                    str(bg_path), Inches(0), Inches(0),
                    width=width, height=height
                )

                slide.shapes._spTree.remove(picture._element)
                slide.shapes._spTree.insert(2, picture._element)

                logger.debug(f"✅ Background: {bg_path.name}")

        except Exception as e:
            logger.warning(f"⚠️  Background error: {e}")

    def add_page_number(self, slide, page_num: int) -> None:
        """Add page number diamond with language-specific positioning"""
        
        try:
            page_num_config = self.config.get("page_numbering", {})
            
            # Get language-specific position
            pos_key = f"position_{self.target_language}"
            position = page_num_config.get(pos_key, page_num_config.get("position_en", {}))
            
            shape_config = page_num_config.get("shape", {})
            
            # Create diamond shape
            diamond = slide.shapes.add_shape(
                MSO_SHAPE.DIAMOND,
                Inches(position.get("offset_x", 0.2)),
                Inches(position.get("offset_y", 6.8)),
                Inches(shape_config.get("width", 0.4)),
                Inches(shape_config.get("height", 0.4))
            )
            
            # Style diamond
            fill_color = self.hex_to_rgb(shape_config.get("fill_color", "C6C3BE"))
            diamond.fill.solid()
            diamond.fill.fore_color.rgb = RGBColor(*fill_color)
            diamond.line.fill.background()
            
            # Add text ONCE
            tf = diamond.text_frame
            tf.clear()  # ✅ Clear any default text
            
            # ✅ FIX: Set text ONLY on first paragraph (no duplication)
            p = tf.paragraphs[0]
            p.text = str(page_num)  # ← SET TEXT ONCE
            p.alignment = PP_ALIGN.CENTER
            
            # Font styling
            font_config = page_num_config.get("font", {})
            p.font.size = Pt(font_config.get("size", 14))
            p.font.name = font_config.get("name", "Cairo")
            
            text_color = self.hex_to_rgb(shape_config.get("text_color", "FFFCEC"))
            p.font.color.rgb = RGBColor(*text_color)
            p.font.bold = font_config.get("bold", False)
            
            # ✅ FIX: Vertical alignment
            tf.vertical_anchor = MSO_ANCHOR.MIDDLE
            
            logger.debug(f"✅ Page number {page_num} added at ({position.get('offset_x')}, {position.get('offset_y')})")
            
        except Exception as e:
            logger.warning(f"⚠️  Page number failed: {e}")


    # ========================================================================
    # LOGO POSITIONING
    # ========================================================================

    def _add_logo(self, slide, element: Dict) -> None:
        """Add logo with language-specific positioning"""
        try:
            logo_path = self.template_dir / element.get('path', 'logo.png')
            if not logo_path.exists():
                return
            
            pos = self.get_position(element, 'position')
            size = element.get('size', {})
            
            slide.shapes.add_picture(
                str(logo_path),
                Inches(pos.get('left', 0.5)),
                Inches(pos.get('top', 0.5)),
                width=Inches(size.get('width', 1.5)),
                height=Inches(size.get('height', 0.8))
            )
        except Exception as e:
            logger.warning(f"⚠️  Logo failed: {e}")

    # ========================================================================
    # MAIN GENERATION
    # ========================================================================

    def generate(self, presentation_data: PresentationData) -> str:
        """Generate presentation"""
        logger.info("="*80)
        logger.info("🎨 Starting MULTILINGUAL generation...")
        logger.info(f"   Presentation language: {getattr(presentation_data, 'language', 'NOT SET')}")
        logger.info(f"   Target language (init): {self.target_language}")
        
        # Detect and configure
        self._detect_and_configure_language(presentation_data)
        
        logger.info(f"   Target language (after detect): {self.target_language}")
        logger.info(f"   Language config: {self.lang_config}")
        logger.info(f"   Is RTL: {self.lang_config.get('rtl', False)}")
        logger.info("="*80)

        presentation_data.slides = validate_presentation(presentation_data.slides)

        self.prs = Presentation()
        self.prs.slide_width = Inches(self.constraints['layout']['slide_width'])
        self.prs.slide_height = Inches(self.constraints['layout']['slide_height'])

        for slide_data in presentation_data.slides:
            if slide_data.title:
                slide_data.title = self._scrub_title(slide_data.title)

        # Title slide
        try:
            self._create_title_slide_dynamic(presentation_data)
        except Exception as e:
            logger.error(f"❌ Title slide: {e}")

        # Content slides
        for idx, slide_data in enumerate(presentation_data.slides):
            logger.info(f"🔨 Slide {idx + 2}: {slide_data.title[:50]}...")

            try:
                layout_type = (slide_data.layout_type or "content").lower()
                layout_hint = self._get_layout_hint(slide_data)

                if layout_type == "section":
                    content_type = "section"
                elif layout_type == "two_column":
                    content_type = "two_column"
                elif layout_hint:
                    content_type = layout_hint
                elif slide_data.table_data:
                    content_type = "table"
                elif slide_data.chart_data:
                    content_type = "chart"
                elif slide_data.bullets:
                    content_type = "bullets"
                else:
                    content_type = "content"

                self._create_slide_from_json(content_type, slide_data, page_num=idx + 2)

            except Exception as e:
                logger.error(f"❌ Slide error: {e}")
                logger.exception(e)

        output_path = self._get_output_path(presentation_data.title)
        self.prs.save(output_path)

        logger.info(f"✅ Generated: {output_path}")
        logger.info(f"   Slides: {len(self.prs.slides)}, Language: {self.target_language}")

        return output_path

    # ========================================================================
    # TITLE SLIDE
    # ========================================================================

    def _create_title_slide_dynamic(self, presentation_data: PresentationData) -> None:
        """Create title slide with language-specific positioning"""
        layout_config = self.layouts.get('title_slide', {})
        slide_layout = self._get_slide_layout(layout_config)
        slide = self.prs.slides.add_slide(slide_layout)
        self._clear_default_placeholders(slide)

        bg_config = layout_config.get('background', {})
        if bg_config.get('type') == 'image':
            self._add_background(slide, bg_config)

        elements = layout_config.get('elements', [])
        
        # Logo
        for element in elements:
            if element.get('type') == 'image' and element.get('id') == 'logo':
                self._add_logo(slide, element)

        # Title
        title = presentation_data.title or "Untitled Presentation"
        max_title_length = self.constraints['text_constraints']['max_title_length']
        if len(title) > max_title_length:
            title = title[:max_title_length - 3] + "..."
        
        title_element = next((e for e in elements if e.get('id') == 'title'), None)
        
        if title_element:
            pos = self.get_position(title_element, 'position')
            size = title_element.get('size', {})
            style = title_element.get('style', {})

            base_font_size = self.get_font_size('title')
            if len(title) > 60:
                font_size = 36
            elif len(title) > 40:
                font_size = 40
            else:
                font_size = base_font_size

            char_per_line = 50 if font_size >= 40 else 60
            lines = max(1, len(title) / char_per_line)
            required_height = lines * 0.6
            actual_height = max(size.get('height', 1.5), required_height)
            
            textbox = slide.shapes.add_textbox(
                Inches(pos.get('left', 1.5)),
                Inches(pos.get('top', 2.8)),
                Inches(size.get('width', 10.33)),
                Inches(actual_height)
            )

            tf = textbox.text_frame
            tf.word_wrap = True
            tf.clear()
            tf.vertical_anchor = MSO_ANCHOR.MIDDLE

            p = tf.paragraphs[0]
            p.text = title
            p.font.size = Pt(font_size)
            p.font.name = self.get_font('heading')
            p.font.bold = True
            
            text_color = self.get_style_value(style, 'color', '#FFFCEC')
            p.font.color.rgb = RGBColor(*self.hex_to_rgb(text_color))
            p.alignment = PP_ALIGN.CENTER
            p.line_spacing = self.get_line_spacing('title')

        # Subtitle
        subtitle_parts = []
        if presentation_data.subtitle and presentation_data.subtitle != "None":
            subtitle_parts.append(presentation_data.subtitle)
        if presentation_data.author and presentation_data.author != "None":
            subtitle_parts.append(presentation_data.author)
        
        subtitle = "\n".join(subtitle_parts).strip()
        
        subtitle_element = next((e for e in elements if e.get('id') == 'subtitle'), None)
        
        if subtitle_element and subtitle:
            pos = self.get_position(subtitle_element, 'position')
            size = subtitle_element.get('size', {})
            style = subtitle_element.get('style', {})

            subtitle_top = pos.get('top', 4.5)
            if lines > 1.5:
                subtitle_top += 0.3

            textbox = slide.shapes.add_textbox(
                Inches(pos.get('left', 2.0)),
                Inches(subtitle_top),
                Inches(size.get('width', 9.33)),
                Inches(size.get('height', 1.0))
            )

            tf = textbox.text_frame
            tf.word_wrap = True
            tf.clear()

            p = tf.paragraphs[0]
            p.text = subtitle
            p.font.size = Pt(self.get_style_value(style, 'font_size', 24))
            p.font.name = self.get_font('body')
            
            text_color = self.get_style_value(style, 'color', '#FFFCEC')
            p.font.color.rgb = RGBColor(*self.hex_to_rgb(text_color))
            p.alignment = PP_ALIGN.CENTER

    # ========================================================================
    # AGENDA SLIDE - ENHANCED WITH RTL SUPPORT
    # ========================================================================

    def _create_agenda_slide_enhanced(self, slide, layout_config: Dict, data) -> None:
        """Enhanced agenda with RTL/LTR support and proper localization"""
        # Background
        bg_config = layout_config.get('background', {})
        if bg_config.get('type') == 'image':
            self._add_background(slide, bg_config)
        
        # *** FIX 1: Use localized agenda title ***
        localization = self.config.get('localization', {})
        lang_strings = localization.get(self.target_language, {})
        agenda_title_text = lang_strings.get('agenda_title', 'Agenda')
        
        # Add "Agenda" text on dark side
        elements = layout_config.get('elements', [])
        agenda_title_elem = next((e for e in elements if e.get('id') == 'agenda_title'), None)
        
        if agenda_title_elem:
            pos = self.get_position(agenda_title_elem, 'position')
            size = agenda_title_elem.get('size', {})
            style = agenda_title_elem.get('style', {})
            
            agenda_textbox = slide.shapes.add_textbox(
                Inches(pos.get('left', 7.5)),
                Inches(pos.get('top', 3.0)),
                Inches(size.get('width', 4.5)),
                Inches(size.get('height', 1.5))
            )
            
            tf = agenda_textbox.text_frame
            tf.clear()
            tf.vertical_anchor = MSO_ANCHOR.MIDDLE
            
            # *** FIX: Set RTL for agenda title ***
            is_rtl = self.lang_config.get('rtl', False)
            self._set_text_frame_rtl(tf, is_rtl)
            
            p = tf.paragraphs[0]
            p.text = agenda_title_text
            p.font.size = Pt(self.get_font_size('agenda_title'))
            p.font.name = self.get_font('heading')
            p.font.bold = True
            
            text_color = self.get_style_value(style, 'color', '#FFFCEC')
            p.font.color.rgb = RGBColor(*self.hex_to_rgb(text_color))
            p.alignment = PP_ALIGN.CENTER
        
        # Logo
        logo_elem = next((e for e in elements if e.get('id') == 'logo'), None)
        if logo_elem:
            self._add_logo(slide, logo_elem)
        
        # Content bullets with icons
        content_elem = next((e for e in elements if e.get('id') == 'content'), None)
        if not content_elem:
            return
        
        bullets = self._extract_bullet_items(data, 'content')
        if not bullets:
            bullets = self._extract_bullet_items(data, 'bullets')
        
        if not bullets:
            logger.warning("⚠️  Agenda slide has no content")
            return
        
        # Get agenda constraints
        agenda_config = self.constraints.get('agenda', {})
        max_items = agenda_config.get('max_items', 5)
        bullets = bullets[:max_items]
        
        # Get positioning
        pos = self.get_position(content_elem, 'position')
        size = content_elem.get('size', {})
        style = content_elem.get('style', {})
        bullet_style = content_elem.get('bullet_style', {})
        
        # Calculate vertical centering
        num_items = len(bullets)
        item_spacing = agenda_config.get('item_spacing', 0.85)
        total_height = num_items * item_spacing
        start_y = (7.5 - total_height) / 2
        
        # Text styling
        text_color = self.get_style_value(style, 'color', '#0D2026')
        text_rgb = self.hex_to_rgb(text_color)
        font_name = self.get_font('body')
        font_size = agenda_config.get('item_font_size', 20)
        line_spacing = agenda_config.get('line_spacing', 1.8)
        
        # Icon configuration
        icon_size = bullet_style.get('icon_size', 0.45)
        is_rtl = self.lang_config.get('rtl', False)
        
        # Get icon positioning based on language
        if is_rtl:
            icon_offset = bullet_style.get('icon_offset_ar', 0.6)
            text_left = pos.get('left', 6.83)
            icon_align = 'right'
        else:
            icon_offset = bullet_style.get('icon_offset_en', 0.3)
            text_left = pos.get('left', 0.7) + icon_size + icon_offset
            icon_align = 'left'
        
        # Render each agenda item
        for idx, bullet in enumerate(bullets):
            item_y = start_y + (idx * item_spacing)
            
            # Add icon
            if self.icon_service and agenda_config.get('use_icons', True):
                icon_name = self.icon_service.auto_select_icon(bullet.text or "", "")
                try:
                    icon_data = self.icon_service.render_to_png(
                        icon_name,
                        size=int(icon_size * 96),
                        color=text_color
                    )
                    if icon_data:
                        if is_rtl:
                            # *** FIX: Icon on the RIGHT for RTL ***
                            icon_left = Inches(text_left + size.get('width', 5.8) - icon_size - 0.2)
                        else:
                            # Icon on the left for LTR
                            icon_left = Inches(pos.get('left', 0.7))
                        
                        icon_top = Inches(item_y + 0.15)
                        
                        slide.shapes.add_picture(
                            icon_data,
                            icon_left,
                            icon_top,
                            width=Inches(icon_size),
                            height=Inches(icon_size)
                        )
                except Exception as e:
                    logger.debug(f"Icon skip: {e}")
            
            # Add text
            text_width = size.get('width', 5.8) - icon_size - icon_offset
            text_box = slide.shapes.add_textbox(
                Inches(text_left),
                Inches(item_y),
                Inches(text_width),
                Inches(0.7)
            )
            
            tf = text_box.text_frame
            tf.clear()
            tf.word_wrap = True
            tf.vertical_anchor = MSO_ANCHOR.MIDDLE
            tf.margin_left = tf.margin_right = Inches(0.05)
            
            # *** FIX: Set RTL for agenda items ***
            self._set_text_frame_rtl(tf, is_rtl)
            
            p = tf.paragraphs[0]
            p.text = (bullet.text or "").strip()
            p.font.size = Pt(font_size)
            p.font.name = font_name
            p.font.color.rgb = RGBColor(*text_rgb)
            p.font.bold = False
            
            # *** FIX: Use constraint-based alignment ***
            alignment_config = self.constraints.get('alignment', {})
            lang_alignment = alignment_config.get(self.target_language, {})
            agenda_alignment = lang_alignment.get('agenda', 'left')
            p.alignment = self._alignment_enum(agenda_alignment)
            p.line_spacing = line_spacing
        
        logger.info(f"✅ Agenda created: {len(bullets)} items, RTL={is_rtl}")

    # ========================================================================
    # SLIDE CREATION FROM JSON
    # ========================================================================

    def _create_slide_from_json(self, content_type: str, data, page_num: int = None) -> None:
        """Create slide with RTL/LTR support"""
        try:
            # Check for agenda
            layout_hint = self._get_layout_hint(data)
            if layout_hint and 'agenda' in layout_hint.lower():
                content_type = 'agenda'
            
            layout_config = self.get_layout_for_content(content_type, data)
            slide_layout = self._get_slide_layout(layout_config)
            slide = self.prs.slides.add_slide(slide_layout)
            self._clear_default_placeholders(slide)
            
            # Background
            bg_config = layout_config.get('background', {})
            if bg_config.get('type') == 'image':
                self._add_background(slide, bg_config)
            
            # Special: Agenda
            if content_type == 'agenda' or (layout_hint and 'agenda' in layout_hint.lower()):
                self._create_agenda_slide_enhanced(slide, layout_config, data)
                if page_num:
                    self.add_page_number(slide, page_num)
                return
            
            elements = layout_config.get('elements', [])
            
            # Special: Section headers
            if content_type == 'section':
                title_text = self._extract_text_value(data, 'title')
                
                max_title = self.constraints['text_constraints']['max_title_length']
                if len(title_text) > max_title:
                    title_text = title_text[:max_title - 3] + "..."
                    data.title = title_text
                
                # *** FIX: Use correct layout for section ***
                layout_config = self.get_layout_for_content(content_type, data)
                
                # Log what layout we got
                logger.info(f"Section layout config: {list(layout_config.keys())}")
                
                # Add background for section headers
                bg_config = layout_config.get('background', {})
                if bg_config.get('type') == 'image':
                    self._add_background(slide, bg_config)
                    logger.info(f"✓ Section background added: {bg_config.get('path')}")
                
                # Add centered icon for section
                if self.icon_service and title_text:
                    # *** FIX: Localized thank you detection ***
                    is_thank_you = any(
                        word in title_text.lower() 
                        for word in ['thank', 'thanks', 'شكر', 'شكراً', 'شكرا']
                    )
                    
                    if is_thank_you:
                        icon_name = 'hand-waving'
                    else:
                        icon_name = self.icon_service.auto_select_icon(title_text, "")
                    
                    self._add_centered_section_icon(slide, icon_name, title_text, layout_config)
                
                # Add title text
                for element in elements:
                    if element.get('type') == 'text' and element.get('id') == 'title':
                        self._add_text_master(slide, element, data, content_type)
                
                logger.info(f"✓ Section slide complete: {title_text}")
                return
            
            # Detect content type from data
            has_chart = bool(getattr(data, 'chart_data', None) or getattr(data, 'chart', None))
            has_table = bool(getattr(data, 'table_data', None) or getattr(data, 'table', None))
            has_paragraph = bool(getattr(data, 'content', None) and len(str(getattr(data, 'content', '')).strip()) > 0)
            has_bullets = bool(getattr(data, 'bullets', None) and len(getattr(data, 'bullets', [])) > 0)
            
            if has_chart:
                logger.info(f"   → Chart slide detected")
            if has_table:
                logger.info(f"   → Table slide detected")
            if has_paragraph:
                logger.info(f"   → Paragraph slide detected")
            if has_bullets:
                logger.info(f"   → Bullets slide detected")
            
            # Process elements
            title_element = None
            content_rendered = False
            
            for element in elements:
                try:
                    element_type = element.get('type')
                    element_id = element.get('id', 'unknown')
                    
                    # Logo
                    if element_type == 'image' and element_id == 'logo':
                        self._add_logo(slide, element)
                    
                    # Title with icon
                    elif element_type == 'text' and element_id == 'title':
                        title_element = element
                        title_text = self._extract_text_value(data, 'title')
                        
                        max_title = self.constraints['text_constraints']['max_title_length']
                        if len(title_text) > max_title:
                            title_text = title_text[:max_title - 3] + "..."
                            data.title = title_text
                        
                        # Add icon to title
                        if self.icon_service and title_text and not (has_chart or has_table):
                            icon_name = self.icon_service.auto_select_icon(title_text, "")
                            self._add_icon_to_title(slide, icon_name, element)
                        
                        self._add_text_master(slide, element, data, content_type)
                    
                    # Title underline
                    elif element_type == 'line' and element_id == 'title_line':
                        if title_element:
                            self._add_title_underline(slide, title_element)
                    
                    # Chart
                    elif element_type == 'chart' and has_chart and not content_rendered:
                        logger.info(f"   → Rendering CHART")
                        self._add_chart_master(slide, element, data)
                        content_rendered = True
                    
                    # Table
                    elif element_type == 'table' and has_table and not content_rendered:
                        logger.info(f"   → Rendering TABLE")
                        self._add_table_master(slide, element, data)
                        content_rendered = True
                    
                    # Paragraph
                    elif element_type == 'text_paragraph' and has_paragraph and not content_rendered:
                        logger.info(f"   → Rendering PARAGRAPH")
                        self._add_paragraph_text(slide, element, data)
                        content_rendered = True
                    
                    # Bullets
                    elif (element_type in ['bullets', 'text_bullets'] or element_id == 'content') and has_bullets and not content_rendered:
                        logger.info(f"   → Rendering BULLETS")
                        self._add_bullets_master(slide, element, data)
                        content_rendered = True
                    
                    # Four-box layout
                    elif element_type == 'boxes' and element_id == 'content_boxes':
                        logger.info(f"   → Rendering FOUR-BOX")
                        self._add_content_box_with_icon_enhanced(slide, element, data)
                        content_rendered = True
                    
                    # Standalone icons
                    elif element_type == 'icon' and element_id != 'icon':
                        self._add_icon_master(slide, element, data)
                    
                    # Content boxes
                    elif element_type == 'content_box':
                        self._add_content_box_master(slide, element, data)
                
                except Exception as e:
                    logger.warning(f"⚠️  Element '{element_id}' error: {e}")
            
            # Add page number
            if page_num and self.config.get('page_numbering', {}).get('enabled', True):
                # Check if this slide type should have page numbers
                skip_title = self.config['page_numbering'].get('skip_title_slide', True)
                skip_sections = self.config['page_numbering'].get('skip_section_headers', False)
                
                should_add = True
                
                if content_type == "section" and skip_sections:
                    should_add = False
                
                if should_add:
                    self.add_page_number(slide, page_num)  # ← CALLED ONLY ONCE HERE
        
        except Exception as e:
            logger.error(f"❌ Slide creation error: {e}")
            raise

    # ========================================================================
    # ICON INTEGRATION - RTL/LTR AWARE
    # ========================================================================

    def _add_icon_to_title(self, slide, icon_name: str, title_element: Dict) -> None:
        """Add icon next to title with language-specific positioning"""
        if not self.icon_service:
            return
        
        try:
            pos = self.get_position(title_element, 'position')
            style = title_element.get('style', {})
            
            text_color = self.get_style_value(style, 'color', '#01415C')
            
            # Get icon positioning from constraints
            positioning = self.constraints.get('positioning', {})
            lang_pos = positioning.get(self.target_language, {})
            
            is_rtl = self.lang_config.get('rtl', False)
            
            if is_rtl:
                # Icon on the right for RTL
                icon_left = lang_pos.get('icon_offset', 11.83)
            else:
                # Icon on the left for LTR
                icon_left = lang_pos.get('icon_offset', 1.0)
            
            icon_top = pos.get('top', 0.6) + 0.05
            
            icon_config = self.constraints.get('icons', {})
            icon_size = icon_config.get('size', 0.5)
            
            icon_data = self.icon_service.render_to_png(
                icon_name,
                size=int(icon_size * 96),
                color=text_color
            )
            
            if icon_data:
                slide.shapes.add_picture(
                    icon_data,
                    Inches(icon_left),
                    Inches(icon_top),
                    width=Inches(icon_size),
                    height=Inches(icon_size)
                )
                logger.debug(f"✅ Icon added: {icon_name} ({'RTL' if is_rtl else 'LTR'})")
        except Exception as e:
            logger.warning(f"⚠️  Icon render failed: {e}")

    def _add_centered_section_icon(self, slide, icon_name: str, title_text: str, layout_config: Dict) -> None:
        """Add icon centered above title for section headers"""
        if not self.icon_service:
            return
        
        try:
            elements = layout_config.get('elements', [])
            title_element = next((e for e in elements if e.get('id') == 'title'), None)
            
            if not title_element:
                return
            
            title_style = title_element.get('style', {})
            text_color = self.get_style_value(title_style, 'color', '#FFFCEC')
            
            slide_width = self.constraints['layout']['slide_width']
            
            icon_config = self.constraints.get('icons', {})
            icon_size = icon_config.get('section_icon_size', 1.2)
            
            icon_left = (slide_width - icon_size) / 2
            icon_top = 2.2
            
            icon_data = self.icon_service.render_to_png(
                icon_name,
                size=int(icon_size * 96),
                color=text_color
            )
            
            if icon_data:
                slide.shapes.add_picture(
                    icon_data,
                    Inches(icon_left),
                    Inches(icon_top),
                    width=Inches(icon_size),
                    height=Inches(icon_size)
                )
                logger.info(f"✅ Section icon: {icon_name}")
        
        except Exception as e:
            logger.warning(f"⚠️  Section icon failed: {e}")

    def _add_title_underline(self, slide, title_element: Dict) -> None:
        """Add horizontal line below title"""
        try:
            line_config = {
                'left': 1.0,
                'top': 1.5,
                'width': 11.33,
                'height': 0.02
            }
            
            line_shape = slide.shapes.add_shape(
                MSO_SHAPE.RECTANGLE,
                Inches(line_config['left']),
                Inches(line_config['top']),
                Inches(line_config['width']),
                Inches(line_config['height'])
            )
            
            line_shape.fill.solid()
            line_color = self.get_color_rgb('accent_teal')
            line_shape.fill.fore_color.rgb = RGBColor(*line_color)
            line_shape.line.fill.background()
            
            logger.debug("✅ Title underline added")
        
        except Exception as e:
            logger.warning(f"⚠️  Title underline failed: {e}")

    # ========================================================================
    # TEXT ELEMENTS - RTL/LTR AWARE
    # ========================================================================

    def _add_text_master(self, slide, element: Dict, data, content_type: str) -> None:
        """Add text with proper RTL/LTR support including alignment"""
        pos = self.get_position(element, 'position')
        size = element.get('size', {})
        style = element.get('style', {})
        element_id = element.get('id', '')

        # Extract text
        if element_id == 'title':
            text = self._extract_text_value(data, 'title')
        elif element_id == 'content':
            text = self._extract_text_value(data, 'content')
        else:
            text = self._extract_text_value(data, element_id)

        if not text:
            return

        textbox = slide.shapes.add_textbox(
            Inches(pos.get('left', 0)),
            Inches(pos.get('top', 0)),
            Inches(size.get('width', 5)),
            Inches(size.get('height', 1))
        )

        tf = textbox.text_frame
        tf.word_wrap = True
        tf.clear()
        tf.vertical_anchor = MSO_ANCHOR.TOP

        # *** FIX: Set RTL/LTR at text frame level ***
        is_rtl = self.lang_config.get('rtl', False)
        self._set_text_frame_rtl(tf, is_rtl)

        padding = float(style.get('padding', 0))
        margin_value = Inches(max(padding, 0))
        
        # *** FIX: Language-specific margins ***
        if is_rtl:
            tf.margin_left = Inches(0.1)
            tf.margin_right = margin_value
        else:
            tf.margin_left = margin_value
            tf.margin_right = Inches(0.1)
        
        tf.margin_top = tf.margin_bottom = margin_value

        line_spacing = self.get_style_value(style, 'line_spacing', 1.45)
        
        # *** FIX: Proper alignment logic for sections and titles ***
        if content_type in ['title']:
            # Title slide - always center
            alignment = PP_ALIGN.CENTER
        elif content_type == 'section':
            # Section headers - always center
            alignment = PP_ALIGN.CENTER
        else:
            # Content slides - follow constraints
            alignment = self.get_text_alignment(style)
        
        # Get text color
        text_color = self.get_style_value(style, 'color')
        if not text_color:
            if content_type in ['title', 'section']:
                text_color = '#FFFCEC'
            else:
                text_color = '#0D2026'
        
        # Get font
        font_name = self.get_style_value(style, 'font')
        if not font_name:
            if element_id == 'title':
                font_name = self.get_font('heading')
            else:
                font_name = self.get_font('body')

        # Split into paragraphs
        paragraphs = [line.strip() for line in str(text).splitlines() if line.strip()]
        if not paragraphs:
            paragraphs = [str(text).strip()]

        for idx, line in enumerate(paragraphs):
            paragraph = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
            paragraph.text = line
            
            font_size = self.get_style_value(style, 'font_size', 18)
            paragraph.font.size = Pt(font_size)
            paragraph.font.name = font_name
            
            if self.get_style_value(style, 'bold'):
                paragraph.font.bold = True

            rgb = self.hex_to_rgb(text_color)
            paragraph.font.color.rgb = RGBColor(*rgb)

            paragraph.line_spacing = line_spacing
            paragraph.space_after = Pt(self.get_style_value(style, 'space_after', 6))
            
            # *** FIX: Apply alignment ***
            paragraph.alignment = alignment
            
            logger.debug(f"Paragraph: '{line[:30]}...' align={alignment} rtl={is_rtl}")


    def _set_text_frame_rtl(self, text_frame, is_rtl: bool) -> None:
        """Set text frame direction to RTL or LTR via XML manipulation"""
        try:
            from pptx.oxml import parse_xml
            
            tf_element = text_frame._element
            
            # Find or create bodyPr (body properties)
            bodyPr = tf_element.find('.//{http://schemas.openxmlformats.org/drawingml/2006/main}bodyPr')
            
            if bodyPr is not None:
                # Set RTL attribute
                if is_rtl:
                    bodyPr.set('rtlCol', '1')
                    bodyPr.set('anchor', 'ctr')
                else:
                    # Remove RTL for LTR
                    if 'rtlCol' in bodyPr.attrib:
                        del bodyPr.attrib['rtlCol']
                    bodyPr.set('anchor', 'ctr')
            
            logger.debug(f"Text frame direction set to {'RTL' if is_rtl else 'LTR'}")
        except Exception as e:
            logger.debug(f"Could not set text frame direction: {e}")

    def _add_paragraph_text(self, slide, element: Dict, data) -> None:
        """Render paragraph content with proper RTL/LTR support"""
        pos = self.get_position(element, 'position')
        size = element.get('size', {})
        style = element.get('style', {})

        # Get text
        text = getattr(data, 'content', None)
        
        if not text or len(str(text).strip()) == 0:
            if hasattr(data, 'bullets') and data.bullets:
                text = "\n\n".join(b.text for b in data.bullets if getattr(b, 'text', None))

        text = (text or "").strip()
        if not text:
            logger.warning(f"⚠️  No paragraph text found")
            return

        # Create textbox
        textbox = slide.shapes.add_textbox(
            Inches(pos.get('left', 1.5)),
            Inches(pos.get('top', 2.0)),
            Inches(size.get('width', 10.33)),
            Inches(size.get('height', 4.8))
        )

        tf = textbox.text_frame
        tf.word_wrap = True
        tf.clear()
        tf.vertical_anchor = MSO_ANCHOR.TOP  # ✅ Keep TOP alignment
        
        # Set RTL direction for text frame
        is_rtl = self.lang_config.get('rtl', False)
        self._set_text_frame_rtl(tf, is_rtl)
        
        # Language-aware margins
        padding = float(style.get('padding', 0.2))
        if is_rtl:
            tf.margin_left = Inches(0.1)
            tf.margin_right = Inches(padding)
            tf.margin_top = Inches(0.1)
            tf.margin_bottom = Inches(0.1)
        else:
            tf.margin_left = Inches(padding)
            tf.margin_right = Inches(0.1)
            tf.margin_top = Inches(0.1)
            tf.margin_bottom = Inches(0.1)

        # Split into paragraphs (prioritize double line breaks)
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        if not paragraphs:
            # Fallback to single line breaks
            paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
        if not paragraphs:
            paragraphs = [text]

        # Get styling
        font_name = self.get_font('body')  # or self.get_font_body() depending on your method
        text_color = self.get_style_value(style, 'color', '#0D2026')
        font_size = self.get_font_size('body')
        line_spacing = self.get_line_spacing('body')
        alignment = self.get_text_alignment(style)

        # Add paragraphs
        for idx, chunk in enumerate(paragraphs):
            paragraph = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
            paragraph.text = chunk
            paragraph.font.size = Pt(font_size)
            paragraph.font.name = font_name
            paragraph.line_spacing = line_spacing
            paragraph.space_after = Pt(12)
            paragraph.alignment = alignment

            # Set color
            rgb = self.hex_to_rgb(text_color)
            paragraph.font.color.rgb = RGBColor(*rgb)
            
            # ✅ FIX: Set paragraph-level RTL if needed
            if is_rtl:
                pPr = paragraph._element.get_or_add_pPr()
                pPr.set('rtl', '1')
        
        logger.info(f"   ✅ Paragraph: {len(paragraphs)} blocks, RTL={is_rtl}")

    def _add_bullets_master(self, slide, element: Dict, data) -> None:
        """Add bullets with proper RTL/LTR alignment using native PowerPoint bullets"""
        element_id = element.get('id')
        bullets = self._extract_bullet_items(data, element_id)
        if not bullets:
            return
        
        # Get constraints
        bullet_config = self.constraints.get('bullets', {})
        max_bullets = bullet_config.get('max_bullets_per_slide', 6)
        bullets = bullets[:max_bullets]
        
        pos = self.get_position(element, 'position')
        size = element.get('size', {})
        style = element.get('style', {})
        bullet_style_cfg = element.get('bullet_style', {})
        
        # Create textbox
        textbox = slide.shapes.add_textbox(
            Inches(pos.get('left', 0)),
            Inches(pos.get('top', 0)),
            Inches(size.get('width', 5)),
            Inches(size.get('height', 3))
        )
        
        tf = textbox.text_frame
        tf.clear()
        tf.word_wrap = True
        tf.vertical_anchor = MSO_ANCHOR.TOP  # ✅ Keep TOP alignment
        
        # Set RTL at text frame level
        is_rtl = self.lang_config.get('rtl', False)
        self._set_text_frame_rtl(tf, is_rtl)
        
        # Language-aware margins
        padding = float(self.get_style_value(style, 'padding', 0.1))
        if is_rtl:
            tf.margin_left = Inches(0.05)
            tf.margin_right = Inches(padding)
        else:
            tf.margin_left = Inches(padding)
            tf.margin_right = Inches(0.05)
        
        # Get styling
        font_size = self.get_font_size('body')
        line_spacing = bullet_config.get('line_spacing', 1.75)
        font_name = self.get_font('body')
        text_color = self.get_style_value(style, 'color', '#0D2026')
        text_rgb = self.hex_to_rgb(text_color)
        
        # Get alignment from constraints
        alignment_config = self.constraints.get('alignment', {})
        lang_alignment = alignment_config.get(self.target_language, {})
        bullets_alignment_str = lang_alignment.get('bullets', 'right' if is_rtl else 'left')
        text_alignment = self._alignment_enum(bullets_alignment_str)
        
        # Get bullet symbols
        bullet_symbols = bullet_config.get('bullet_symbols', {})
        bullet_char = bullet_symbols.get('level_1', '●')
        bullet_color = self.get_style_value(bullet_style_cfg, 'bullet_color', '#01415C')
        bullet_rgb = self.hex_to_rgb(bullet_color)
        
        logger.info(f"   Bullets: lang={self.target_language}, align={bullets_alignment_str}, RTL={is_rtl}")
        
        # Add bullets
        for idx, bullet in enumerate(bullets):
            paragraph = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
            
            # Clean bullet text (remove manual symbols)
            bullet_text = (bullet.text or "").replace("●", "").replace("**", "").strip()
            
            # ✅ FIX: Set text WITHOUT manual bullet symbol
            paragraph.text = bullet_text
            paragraph.level = 0  # Level 0 = main bullet
            
            # Font styling
            paragraph.font.bold = self.get_style_value(style, 'bold', False)
            paragraph.font.size = Pt(font_size)
            paragraph.font.name = font_name
            paragraph.font.color.rgb = RGBColor(*text_rgb)
            
            # Alignment
            paragraph.alignment = text_alignment
            paragraph.line_spacing = line_spacing
            
            # Spacing
            spacing_before = bullet_config.get('spacing_before', 6)
            spacing_after = bullet_config.get('spacing_after', 6)
            paragraph.space_before = Pt(spacing_before)
            paragraph.space_after = Pt(spacing_after)
            
            # ✅ FIX: Set paragraph RTL property
            if is_rtl:
                pPr = paragraph._element.get_or_add_pPr()
                pPr.set('rtl', '1')
            
            # ✅ FIX: Apply native PowerPoint bullet formatting
            pPr = paragraph._element.get_or_add_pPr()
            
            # Add bullet formatting
            buFont = parse_xml(f'<a:buFont xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" typeface="{font_name}"/>')
            buChar = parse_xml(f'<a:buChar xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" char="{bullet_char}"/>')
            
            # Add bullet color
            buClr = parse_xml(f'''<a:buClr xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
                <a:srgbClr val="{bullet_color.replace("#", "")}"/>
            </a:buClr>''')
            
            pPr.append(buFont)
            pPr.append(buChar)
            pPr.append(buClr)
            
            # Handle sub-bullets
            if getattr(bullet, 'sub_bullets', None):
                sub_bullet_char = bullet_symbols.get('level_2', '○')
                max_sub = bullet_config.get('max_sub_bullets_per_bullet', 3)
                
                for sub in bullet.sub_bullets[:max_sub]:
                    sp = tf.add_paragraph()
                    sub_text = str(sub).replace("○", "").replace("●", "").strip()
                    
                    sp.text = sub_text
                    sp.level = 1  # Level 1 = sub-bullet
                    
                    sp.font.size = Pt(max(font_size - 2, 14))
                    sp.font.name = font_name
                    sp.font.color.rgb = RGBColor(*text_rgb)
                    sp.alignment = text_alignment
                    sp.line_spacing = line_spacing
                    
                    # RTL for sub-bullet
                    if is_rtl:
                        spPr = sp._element.get_or_add_pPr()
                        spPr.set('rtl', '1')
                    
                    # Apply sub-bullet formatting
                    spPr = sp._element.get_or_add_pPr()
                    sub_buFont = parse_xml(f'<a:buFont xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" typeface="{font_name}"/>')
                    sub_buChar = parse_xml(f'<a:buChar xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" char="{sub_bullet_char}"/>')
                    sub_buClr = parse_xml(f'''<a:buClr xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
                        <a:srgbClr val="{bullet_color.replace("#", "")}"/>
                    </a:buClr>''')
                    
                    spPr.append(sub_buFont)
                    spPr.append(sub_buChar)
                    spPr.append(sub_buClr)
        
        logger.info(f"   ✅ Bullets: {len(bullets)} items added")


    # ========================================================================
    # TABLE - RTL/LTR AWARE
    # ========================================================================

    def _add_table_master(self, slide, element: Dict, data) -> None:
        """Add table with RTL/LTR support and proper language context"""
        table_data_obj = getattr(data, 'table_data', None) or getattr(data, 'table', None)
        
        if not table_data_obj:
            logger.warning(f"⚠️  No table_data found")
            return
        
        pos = self.get_position(element, 'position')
        size = element.get('size', {})
        style = element.get('style', {})
        
        # *** FIX: Import and initialize TableService with language ***
        from apps.app.services.table_service import TableService
        
        try:
            # Initialize TableService with template and language
            table_service = TableService(
                template_id=self.template_id,
                language=self.target_language  # Pass the target language
            )
            
            # Add table
            table_service.add_table(
                slide=slide,
                table_data=table_data_obj,
                position=pos,
                size=size
            )
            
            logger.info(f"✅ Table rendered (RTL={self.lang_config.get('rtl', False)})")
            
        except Exception as e:
            logger.error(f"❌ Table error: {e}")
            logger.exception(e)

    # ========================================================================
    # CHART - RTL/LTR AWARE
    # ========================================================================

    def _add_chart_master(self, slide, element: Dict, data) -> None:
        """Add chart with RTL/LTR support"""
        if not self.chart_service:
            logger.warning("⚠️  ChartService not available")
            return
        
        chart_data_obj = getattr(data, 'chart_data', None) or getattr(data, 'chart', None)
        
        if not chart_data_obj:
            logger.warning(f"⚠️  No chart_data found")
            return
        
        pos = self.get_position(element, 'position')
        size = element.get('size', {})
        style = element.get('style', {})
        
        try:
            # Convert to dict
            if hasattr(chart_data_obj, 'dict'):
                chart_data = chart_data_obj.dict()
            elif isinstance(chart_data_obj, dict):
                chart_data = chart_data_obj
            else:
                chart_data = chart_data_obj.__dict__
            
            logger.info(f"   → Chart type: {chart_data.get('chart_type')}")
            
            # Get chart config from constraints
            chart_config = self.constraints.get('chart', {})
            
            # Apply styling from constraints
            chart_data['font_color'] = chart_config.get('font_color', '#FFFFFF')
            chart_data['data_label_color'] = chart_config.get('data_label_color', '#FFFFFF')
            chart_data['axis_color'] = chart_config.get('axis_color', '#FFFFFF')
            chart_data['axis_label_color'] = chart_config.get('axis_label_color', '#FFFFFF')
            chart_data['grid_color'] = chart_config.get('grid_color', '#5C6F7A')
            chart_data['legend_font_color'] = chart_config.get('legend_font_color', '#FFFFFF')
            chart_data['title_color'] = chart_config.get('title_color', '#FFFCEC')
            
            bg_color = chart_config.get('background_color', '#0D2026')
            bg_rgb = self.hex_to_rgb(bg_color)
            
            self.chart_service.add_native_chart(
                slide=slide,
                chart_data=chart_data,
                position={"left": pos.get('left', 1.5), "top": pos.get('top', 2.0)},
                size={"width": size.get('width', 10.33), "height": size.get('height', 5.0)},
                background_rgb=bg_rgb
            )
            
            logger.info(f"✅ Chart rendered")
        except Exception as e:
            logger.error(f"❌ Chart error: {e}")
            logger.exception(e)

    # ========================================================================
    # FOUR-BOX LAYOUT - RTL/LTR AWARE
    # ========================================================================

    def _add_content_box_with_icon_enhanced(self, slide, element: Dict, data) -> None:
        """Enhanced four-box layout with RTL/LTR support"""
        box_config = element
        bullets = self._extract_bullet_items(data, 'content')
        
        if not bullets or len(bullets) == 0:
            return
        
        # Get box configuration from constraints
        box_constraints = self.constraints.get('boxes', {})
        max_boxes = box_constraints.get('max_boxes', 4)
        bullets = bullets[:max_boxes]
        
        layout_type = box_config.get('layout', '2x2')
        position = box_config.get('position', {})
        size = box_config.get('size', {})
        box_style = box_config.get('box_style', {})
        
        # Box dimensions
        box_width = box_constraints.get('width', 5.4)
        box_height = box_constraints.get('height', 2.2)
        gap_h = box_constraints.get('gap_horizontal', 0.53)
        gap_v = box_constraints.get('gap_vertical', 0.4)
        
        # Colors
        colors = self.constraints.get('colors', {}).get('box_colors', ['#B1D8BE', '#F9D462', '#C6C3BE', '#E09059'])
        text_color = box_style.get('text_color', '#0D2026')
        font_name = self.get_font('body')
        font_size = box_constraints.get('font_size', 16)
        icon_size = box_constraints.get('icon_size', 0.6)
        
        # Base position
        base_left = position.get('left', 1.0)
        base_top = position.get('top', 2.0)
        
        # Get alignment
        is_rtl = self.lang_config.get('rtl', False)
        text_alignment = PP_ALIGN.CENTER  # Boxes are always centered
        
        # Render each box
        for idx, bullet in enumerate(bullets[:4]):
            # Calculate grid position (2x2)
            row = idx // 2
            col = idx % 2
            
            # Calculate box position
            box_left = Inches(base_left + col * (box_width + gap_h))
            box_top = Inches(base_top + row * (box_height + gap_v))
            box_w = Inches(box_width)
            box_h = Inches(box_height)
            
            # 1. Create colored box
            box_shape = slide.shapes.add_shape(
                MSO_SHAPE.ROUNDED_RECTANGLE,
                box_left, box_top, box_w, box_h
            )
            
            box_color = colors[idx % len(colors)]
            box_rgb = self.hex_to_rgb(box_color)
            
            box_shape.fill.solid()
            box_shape.fill.fore_color.rgb = RGBColor(*box_rgb)
            box_shape.line.fill.background()
            
            # 2. Add icon INSIDE box (top-center)
            if self.icon_service:
                icon_name = self.icon_service.auto_select_icon(bullet.text or "", "")
                
                try:
                    icon_data = self.icon_service.render_to_png(
                        icon_name,
                        size=int(icon_size * 96),
                        color=text_color
                    )
                    
                    if icon_data:
                        # Center icon horizontally within box
                        icon_left = box_left + (box_w - Inches(icon_size)) / 2
                        icon_top = box_top + Inches(box_constraints.get('icon_top_padding', 0.25))
                        
                        slide.shapes.add_picture(
                            icon_data,
                            icon_left,
                            icon_top,
                            Inches(icon_size),
                            Inches(icon_size)
                        )
                except Exception as e:
                    logger.debug(f"Icon render skipped for box {idx + 1}: {e}")
            
            # 3. Add text BELOW icon (inside box)
            text_top = box_top + Inches(icon_size + box_constraints.get('text_top_offset', 0.35))
            text_height = box_h - Inches(icon_size + 0.5)
            
            padding = box_constraints.get('padding', 0.3)
            text_box = slide.shapes.add_textbox(
                box_left + Inches(padding),
                text_top,
                box_w - Inches(padding * 2),
                text_height
            )
            
            tf = text_box.text_frame
            tf.word_wrap = True
            tf.clear()
            tf.vertical_anchor = MSO_ANCHOR.TOP
            tf.margin_left = tf.margin_right = Inches(0.1)
            
            p = tf.paragraphs[0]
            p.text = (bullet.text or "").strip()
            p.font.name = font_name
            p.font.size = Pt(font_size)
            p.font.bold = True
            p.font.color.rgb = RGBColor(*self.hex_to_rgb(text_color))
            p.alignment = text_alignment
            p.line_spacing = box_constraints.get('line_spacing', 1.3)
            
            logger.debug(f"✅ Four-box item {idx + 1}")

    # ========================================================================
    # ICON MASTER - RTL/LTR AWARE
    # ========================================================================

    def _add_icon_master(self, slide, element: Dict, data) -> None:
        """Add standalone icon with RTL/LTR positioning"""
        if not self.icon_service:
            return

        element_id = element.get("id", "")
        pos = self.get_position(element, 'position')
        size = element.get('size', {})
        style = element.get('style', {})

        # Determine content for icon selection
        content = ""
        
        if element_id == "icon":
            if hasattr(data, "title") and data.title:
                content = data.title
        elif element_id.endswith("_icon"):
            box_id = element_id.replace("_icon", "")
            if hasattr(data, "bullets") and data.bullets:
                try:
                    idx = int(box_id.replace("box", "")) - 1
                    if 0 <= idx < len(data.bullets):
                        content = data.bullets[idx].text
                except:
                    content = getattr(data, "title", "")

        if not content:
            content = getattr(data, "title", "") or ""

        if not content.strip():
            return

        # Select icon
        icon_name = self.icon_service.auto_select_icon(content, "")
        
        # Get icon config
        icon_config = self.constraints.get('icons', {})
        icon_color = self.get_style_value(style, 'color', '#0D2026')

        try:
            icon_data = self.icon_service.render_to_png(
                icon_name,
                size=int(size.get("width", 0.6) * 96),
                color=icon_color
            )

            if not icon_data:
                return

            slide.shapes.add_picture(
                icon_data,
                Inches(pos.get("left", 0)),
                Inches(pos.get("top", 0)),
                width=Inches(size.get("width", 0.6)),
                height=Inches(size.get("height", 0.6))
            )

            logger.debug(f"✅ Icon added: {icon_name}")

        except Exception as e:
            logger.warning(f"⚠️ Icon render failed: {e}")

    # ========================================================================
    # CONTENT BOX MASTER
    # ========================================================================

    def _add_content_box_master(self, slide, element: Dict, data) -> None:
        """Add colored content box with RTL/LTR support"""
        box_id = element.get('id', '')
        pos = self.get_position(element, 'position')
        size = element.get('size', {})
        style = element.get('style', {})
        
        content = ""
        if isinstance(data, dict):
            content = data.get(box_id, '')
        elif hasattr(data, 'bullets') and data.bullets:
            box_num = int(box_id.replace('box', '')) - 1
            if box_num < len(data.bullets):
                content = data.bullets[box_num].text
        
        if not content:
            return
        
        box = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            Inches(pos.get('left', 0)),
            Inches(pos.get('top', 0)),
            Inches(size.get('width', 3)),
            Inches(size.get('height', 2))
        )
        
        bg_color = self.get_style_value(style, 'background_color', '#FFFFFF')
        box.fill.solid()
        box.fill.fore_color.rgb = RGBColor(*self.hex_to_rgb(bg_color))
        box.line.fill.background()
        
        padding = self.get_style_value(style, 'padding', 0.3)
        textbox = slide.shapes.add_textbox(
            Inches(pos.get('left') + padding),
            Inches(pos.get('top') + padding),
            Inches(size.get('width') - 2*padding),
            Inches(size.get('height') - 2*padding)
        )
        
        tf = textbox.text_frame
        tf.word_wrap = True
        tf.clear()
        tf.vertical_anchor = MSO_ANCHOR.TOP
        tf.margin_left = tf.margin_right = Inches(0.05)
        
        p = tf.paragraphs[0]
        p.text = content
        p.font.size = Pt(self.get_style_value(style, 'font_size', 16))
        p.font.name = self.get_font('body')
        p.alignment = self.get_text_alignment(style)
        p.line_spacing = self.get_style_value(style, 'line_spacing', 1.45)
        p.space_after = Pt(self.get_style_value(style, 'space_after', 4))
        
        text_color = self.get_style_value(style, 'text_color', '#0D2026')
        p.font.color.rgb = RGBColor(*self.hex_to_rgb(text_color))

    # ========================================================================
    # OUTPUT PATH
    # ========================================================================

    def _get_output_path(self, title: str) -> str:
        """Generate output path for presentation"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = (title or "Presentation").strip()
        safe_title = re.sub(r'[<>:"/\\\\|?*]', '', safe_title).replace(" ", "_")[:50]
        filename = f"{self.template_id}_{self.target_language}_{safe_title}_{timestamp}.pptx"
        output_dir = Path(settings.OUTPUT_DIR)
        output_dir.mkdir(exist_ok=True, parents=True)
        return str(output_dir / filename)