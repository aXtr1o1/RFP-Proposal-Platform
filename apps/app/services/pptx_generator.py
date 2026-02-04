"""
PPTX Generator Module - Native Template Mode
Generates PowerPoint presentations using native PPTX templates.

This generator creates slides that match the sample template layout by:
1. Using the blank layout as base
2. Adding background images
3. Creating text boxes at exact positions from config
4. Adding separators, icons, and page numbers
"""

import hashlib
import logging
import re
import json
from datetime import datetime
from pathlib import Path
from typing import Tuple, Optional, Dict, Any, List

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE, MSO_SHAPE_TYPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt, Emu

from ..config import settings
from ..models.presentation import PresentationData, SlideContent, TableData, BulletPoint
from ..models.template_manifest import TemplateManifest
from .chart_service import ChartService
from .icon_service import IconService
from ..utils.content_validator import validate_presentation

logger = logging.getLogger("pptx_generator")


# Icon keyword mappings for intelligent icon selection
ICON_KEYWORDS = {
    # Business & Management
    'strategy': ['strategy', 'strategic', 'plan', 'planning', 'roadmap'],
    'team': ['team', 'staff', 'people', 'workforce', 'employees', 'personnel', 'group'],
    'leadership': ['leader', 'leadership', 'management', 'executive', 'director'],
    'goals': ['goal', 'goals', 'objective', 'objectives', 'target', 'targets', 'kpi'],
    'growth': ['growth', 'expand', 'expansion', 'scale', 'scaling', 'increase'],
    
    # Technical
    'technology': ['technology', 'tech', 'digital', 'software', 'system', 'systems'],
    'data': ['data', 'analytics', 'analysis', 'statistics', 'metrics', 'insights'],
    'security': ['security', 'secure', 'protection', 'safety', 'compliance'],
    'process': ['process', 'workflow', 'procedure', 'operation', 'operations'],
    'infrastructure': ['infrastructure', 'network', 'architecture', 'platform'],
    
    # Communication
    'communication': ['communication', 'communicate', 'messaging', 'contact'],
    'presentation': ['presentation', 'present', 'overview', 'summary', 'introduction'],
    'report': ['report', 'reporting', 'documentation', 'document'],
    
    # Financial
    'finance': ['finance', 'financial', 'budget', 'cost', 'investment', 'revenue'],
    'money': ['money', 'payment', 'pricing', 'fee', 'profit', 'earnings'],
    
    # Project
    'project': ['project', 'initiative', 'program', 'delivery'],
    'timeline': ['timeline', 'schedule', 'milestone', 'deadline', 'phase'],
    'quality': ['quality', 'excellence', 'standard', 'standards', 'benchmark'],
    
    # Service
    'service': ['service', 'services', 'support', 'assistance', 'help'],
    'customer': ['customer', 'client', 'user', 'guest', 'visitor', 'pilgrim'],
    'experience': ['experience', 'journey', 'satisfaction', 'feedback'],
    
    # Specific domains
    'training': ['training', 'education', 'learning', 'development', 'skill'],
    'health': ['health', 'medical', 'wellness', 'care', 'safety'],
    'environment': ['environment', 'sustainability', 'green', 'eco'],
    'location': ['location', 'place', 'site', 'venue', 'facility', 'facilities'],
    'transport': ['transport', 'transportation', 'logistics', 'travel', 'mobility'],
    'food': ['food', 'catering', 'meal', 'dining', 'nutrition'],
    'accommodation': ['accommodation', 'housing', 'hotel', 'lodging', 'stay'],
    
    # Generic
    'solution': ['solution', 'solutions', 'approach', 'method', 'methodology'],
    'benefit': ['benefit', 'benefits', 'advantage', 'value', 'impact'],
    'challenge': ['challenge', 'challenges', 'issue', 'problem', 'risk'],
    'success': ['success', 'achievement', 'result', 'results', 'outcome'],
    'innovation': ['innovation', 'innovative', 'new', 'modern', 'advanced'],
}


class PptxGenerator:
    """
    Native PPTX Generator that creates slides matching the sample template layout.
    
    Uses element_positions from config to place content at exact positions.
    """

    def __init__(self, template_id: str, language: str = "en"):
        """Initialize the PPTX generator."""
        self.template_id = template_id
        self.target_language = self._normalize_language_code(language)
        
        # Template paths
        self.template_dir = Path(settings.TEMPLATES_DIR) / template_id
        logger.info(f"Initializing generator: {self.template_dir}")
        
        if not self.template_dir.exists():
            raise FileNotFoundError(f"Template directory not found: {self.template_dir}")
        
        self.backgrounds_dir = self.template_dir / "Background"
        if not self.backgrounds_dir.exists():
            self.backgrounds_dir = self.template_dir / "backgrounds"
        
        # Load configurations
        self.config = self._load_json("config.json")
        self.constraints = self._load_json("constraints.json") if (self.template_dir / "constraints.json").exists() else {}
        self.theme = self._load_json("theme.json") if (self.template_dir / "theme.json").exists() else self._get_default_theme()
        
        # Load manifest if exists
        self.manifest: Optional[TemplateManifest] = None
        manifest_path = self.template_dir / "manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.manifest = TemplateManifest(**data)
                logger.info(f"  Manifest loaded: {len(self.manifest.layouts)} layouts")
            except Exception as e:
                logger.warning(f"  Could not load manifest: {e}")
        
        # Initialize services
        try:
            self.icon_service = IconService(template_id=template_id)
        except Exception as e:
            logger.warning(f"  IconService failed: {e}")
            self.icon_service = None
        
        try:
            self.chart_service = ChartService(template_id=template_id)
        except Exception as e:
            logger.warning(f"  ChartService failed: {e}")
            self.chart_service = None
        
        # Runtime state
        self.prs: Optional[Presentation] = None
        self.lang_config: Dict[str, Any] = {}
        
        # Load element positions (prefer config, fallback to manifest)
        self.element_positions: Dict[str, Any] = self.config.get('element_positions', {})
        if not self.element_positions and self.manifest and self.manifest.element_positions:
            self.element_positions = self.manifest.element_positions
        
        # Load fonts config (prefer config, fallback to manifest)
        self.fonts_config: Dict[str, Any] = self.config.get('fonts', {})
        if not self.fonts_config and self.manifest and self.manifest.fonts:
            self.fonts_config = self.manifest.fonts.model_dump() if hasattr(self.manifest.fonts, 'model_dump') else {}
        
        # Load icons config (prefer config, fallback to manifest)
        self.icons_config: Dict[str, Any] = self.config.get('icons', {})
        if not self.icons_config and self.manifest and self.manifest.icons:
            self.icons_config = {
                'default_title': self.manifest.icons.default_title,
                'default_section': self.manifest.icons.default_section,
                'agenda_items': self.manifest.icons.agenda_items,
                'box_icons': self.manifest.icons.box_icons
            }
        
        # Load colors config (prefer config, fallback to manifest)
        self.colors_config: Dict[str, Any] = self.config.get('colors', {})
        if not self.colors_config and self.manifest and self.manifest.colors:
            self.colors_config = self.manifest.colors.model_dump() if hasattr(self.manifest.colors, 'model_dump') else {}
        
        # Build available icons list (section falls back to title icons if no section icons)
        self.available_title_icons = self._get_available_icons('title')
        self.available_section_icons = self._get_available_icons('section')
        if not self.available_section_icons and self.available_title_icons:
            self.available_section_icons = list(self.available_title_icons)
        self.icon_index = 0  # Fallback counter for cycling when no keyword match
        # Load icon keyword rules (new format: rules with priority/keywords/icons) or legacy category_to_icon
        self.icon_keyword_rules: List[Dict] = []  # [{priority, keywords, icons: {title?, section?, alt?}}, ...]
        self.category_to_icon: Dict[str, str] = {}
        icon_kw_path = self.template_dir / "icon_keywords.json"
        if icon_kw_path.exists():
            try:
                kw_data = self._load_json("icon_keywords.json")
                rules = kw_data.get("rules") or []
                if rules:
                    # Sort by priority desc (higher wins); Python sort is stable so order preserved for ties
                    self.icon_keyword_rules = sorted(rules, key=lambda r: -int(r.get("priority", 0)))
                    # Normalize: precompute keyword list and icons dict for fast matching
                    for r in self.icon_keyword_rules:
                        r["_keywords"] = [str(k).strip().lower() for k in (r.get("keywords") or []) if k]
                        r["_icons"] = r.get("icons") or {}
                    logger.info(f"  Icon keyword rules: {len(self.icon_keyword_rules)} rules (priority-based)")
                else:
                    raw = kw_data.get("category_to_icon") or {}
                    for cat, path in raw.items():
                        if path and (self.template_dir / path).exists():
                            self.category_to_icon[cat] = path
                    if self.category_to_icon:
                        logger.info(f"  Icon keyword mapping: {len(self.category_to_icon)} categories (legacy)")
            except Exception as e:
                logger.debug(f"Could not load icon_keywords.json: {e}")
        
        logger.info(f"Generator initialized: {template_id}, lang={self.target_language}")
        logger.info(f"  Available icons: {len(self.available_title_icons)} title, {len(self.available_section_icons)} section")
    
    # ========================================================================
    # CONFIGURATION LOADING
    # ========================================================================
    
    def _load_json(self, filename: str) -> Dict:
        """Load JSON configuration file"""
        json_path = self.template_dir / filename
        if not json_path.exists():
            return {}
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _get_default_theme(self) -> Dict:
        """Get default theme configuration"""
        return {
            "colors": {
                "primary": "#01415C",
                "secondary": "#84BA93",
                "text_primary": "#0D2026",
                "text_inverse": "#FFFCEC"
            },
            "typography": {
                "font_families": {"primary": "Calibri Light", "body": "Calibri"},
                "font_sizes": {"title": 44, "heading_1": 32, "body": 18}
            }
        }
    
    # ========================================================================
    # LANGUAGE CONFIGURATION
    # ========================================================================
    
    def _normalize_language_code(self, language: str) -> str:
        """Normalize language to 2-letter code"""
        if not language:
            return 'en'
        lang_lower = language.lower().strip()
        language_map = {'arabic': 'ar', 'ar': 'ar', 'english': 'en', 'en': 'en'}
        return language_map.get(lang_lower, 'en')
    
    def _configure_language(self, presentation_data: PresentationData) -> None:
        """Configure language settings"""
        lang_settings = self.config.get('language_settings', {})
        
        if presentation_data and hasattr(presentation_data, 'language') and presentation_data.language:
            self.target_language = self._normalize_language_code(presentation_data.language)
        
        self.lang_config = lang_settings.get(self.target_language, {
            'rtl': False,
            'default_font': 'Calibri',
            'heading_font': 'Calibri Light',
            'alignment': 'left'
        })
        
        logger.info(f"Language: {self.target_language}, RTL={self.lang_config.get('rtl', False)}")
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    def _get_alignment(self, force_center: bool = False) -> PP_ALIGN:
        """Get text alignment based on language"""
        if force_center:
            return PP_ALIGN.CENTER
        alignment = self.lang_config.get('alignment', 'left')
        if alignment == 'right':
            return PP_ALIGN.RIGHT
        elif alignment == 'center':
            return PP_ALIGN.CENTER
        return PP_ALIGN.LEFT
    
    # ========================================================================
    # ICON SELECTION METHODS
    # ========================================================================
    
    def _get_available_icons(self, icon_type: str = 'title') -> List[str]:
        """Get list of available icons from template directory"""
        icons_dir = self.template_dir / "Icons"
        if not icons_dir.exists():
            return []
        
        prefix = f"icon_{icon_type}_"
        icons = []
        for f in icons_dir.iterdir():
            if f.is_file() and f.name.startswith(prefix):
                icons.append(f"Icons/{f.name}")
        
        return sorted(icons)
    
    def _normalize_heading_for_icon_match(self, text: str) -> str:
        """Normalize heading for icon keyword match: lowercase, trim, collapse spaces."""
        if not text:
            return ""
        return re.sub(r"\s+", " ", text.strip().lower())

    def _pick_icon_path_from_rule(self, rule: Dict, icon_type: str) -> Optional[str]:
        """From a rule's icons dict, pick the best path for title vs section. Returns path if file exists."""
        icons = rule.get("_icons") or rule.get("icons") or {}
        candidates = []
        if icon_type == "section":
            if icons.get("section"):
                candidates.append(icons["section"])
            if icons.get("title"):
                candidates.append(icons["title"])
        else:
            if icons.get("title"):
                candidates.append(icons["title"])
        alt = icons.get("alt") or []
        if isinstance(alt, list):
            candidates.extend(alt)
        else:
            if alt:
                candidates.append(alt)
        for path in candidates:
            if path and (self.template_dir / path).exists():
                return path
        return None

    def _select_icon_for_content(self, title: str, icon_type: str = 'title') -> Optional[str]:
        """
        Select an appropriate icon based on slide title content.
        Uses template icon_keywords.json: if "rules" format, matches by keywords (substring) and
        priority (higher wins), then picks icons.title or icons.section; falls back to legacy
        category_to_icon or config default or cycling when no match.
        """
        icons = self.available_title_icons if icon_type == 'title' else self.available_section_icons

        def _default_icon() -> Optional[str]:
            cand = self.icons_config.get('default_section' if icon_type == 'section' else 'default_title')
            if cand and (self.template_dir / cand).exists():
                return cand
            if icons:
                return icons[0]
            other = self.available_title_icons or self.available_section_icons
            return other[0] if other else None

        if not icons:
            return _default_icon()

        title_norm = self._normalize_heading_for_icon_match(title or "")

        # New format: rules with priority + keywords + icons.title / icons.section / icons.alt
        if self.icon_keyword_rules:
            for rule in self.icon_keyword_rules:
                keywords = rule.get("_keywords") or []
                for kw in keywords:
                    if kw and kw in title_norm:
                        path = self._pick_icon_path_from_rule(rule, icon_type)
                        if path:
                            return path
                        break
            # No rule matched; fall back to default or cycle
            if not icons:
                return _default_icon()
            self.icon_index += 1
            return icons[self.icon_index % len(icons)]

        # Legacy format: category_to_icon + ICON_KEYWORDS
        best_match = None
        best_score = 0
        for category, keywords in ICON_KEYWORDS.items():
            for keyword in keywords:
                if keyword in title_norm:
                    score = len(keyword)
                    if score > best_score:
                        best_score = score
                        best_match = category
        if best_match and best_match in self.category_to_icon:
            mapped = self.category_to_icon[best_match]
            if (self.template_dir / mapped).exists():
                return mapped
        if best_match and icons:
            return icons[hash(best_match) % len(icons)]
        self.icon_index += 1
        return icons[self.icon_index % len(icons)] if icons else _default_icon()

    def _ensure_header_icon(self, icon_path: Optional[str], icon_type: str = 'title') -> Optional[str]:
        """Ensure we have an icon for a slide header; every slide with a header must show an icon."""
        if icon_path:
            return icon_path
        icons = self.available_title_icons if icon_type == 'title' else self.available_section_icons
        default = self.icons_config.get('default_section' if icon_type == 'section' else 'default_title')
        if default and (self.template_dir / default).exists():
            return default
        if icons:
            return icons[0]
        return (self.available_title_icons or self.available_section_icons)[0] if (self.available_title_icons or self.available_section_icons) else None
    
    def _get_font(self, font_type: str = 'body') -> str:
        """Get font based on type and language"""
        if font_type in ['title', 'heading']:
            return self.lang_config.get('heading_font', 'Calibri Light')
        return self.lang_config.get('default_font', 'Calibri')
    
    def _get_slide_tone(self, content_type: Optional[str]) -> str:
        """Return 'light' or 'dark' for the slide background. Used to pick contrasting text/icon colors."""
        if not content_type:
            return 'light'
        slide_color = self.config.get('slide_color') or self.constraints.get('slide_color') or {}
        tone = slide_color.get(content_type, slide_color.get('content', 'light'))
        return (tone or 'light').lower()

    def _get_text_color_for_slide(self, content_type: Optional[str]) -> str:
        """When slide_color is light → use dark font; when dark → use light font. Returns hex (no #)."""
        text_colors = self.colors_config.get('text', {})
        dark_hex = (text_colors.get('dark') or '0D2026').lstrip('#')
        light_hex = (text_colors.get('light') or 'FFFCEC').lstrip('#')
        tone = self._get_slide_tone(content_type)
        return dark_hex if tone == 'light' else light_hex

    def _get_separator_color_for_slide(self, content_type: Optional[str]) -> str:
        """Separator/line color adapted to slide: dark line on light slides, light line on dark slides."""
        return self._get_text_color_for_slide(content_type)

    def _get_font_config(self, slide_type: str, element: str, content_type: Optional[str] = None) -> Dict:
        """Get font configuration. If content_type is set, text color is derived from slide_color (light slide → dark font, dark slide → light font)."""
        font_key = 'name_ar' if self.target_language == 'ar' else 'name_en'
        slide_fonts = self.fonts_config.get(slide_type, {})
        element_fonts = slide_fonts.get(element, {})
        default_color = self.colors_config.get('text', {}).get('dark', '0D2026')
        if isinstance(default_color, str):
            default_color = default_color.lstrip('#')
        if content_type:
            color = self._get_text_color_for_slide(content_type)
        else:
            color = element_fonts.get('color', default_color)
            if isinstance(color, str):
                color = color.lstrip('#')
        return {
            'name': element_fonts.get(font_key, element_fonts.get('name', self._get_font('body'))),
            'size': element_fonts.get('size', 18),
            'bold': element_fonts.get('bold', False),
            'color': color
        }

    def _get_color(self, color_path: str, default: str = '0D2026') -> str:
        """Get color from config by path (e.g., 'text.dark', 'elements.separator_line')"""
        parts = color_path.split('.')
        value = self.colors_config
        
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return default
        
        return value if isinstance(value, str) else default
    
    def _get_tinted_icon_path(self, icon_path: str, tint_hex: str) -> Optional[str]:
        """
        Treat PNG as alpha mask: replace RGB with tint color, preserve alpha.
        Dark slide → light tint (#FFFCEC); light slide → dark tint (#0D2026).
        Returns path to cached tinted PNG, or None if tinting fails (caller can use original).
        """
        if not icon_path or not tint_hex:
            return None
        full_path = self.template_dir / icon_path
        if not full_path.exists():
            return None
        hex_clean = tint_hex.lstrip("#").upper()
        if len(hex_clean) != 6:
            return None
        try:
            r, g, b = int(hex_clean[0:2], 16), int(hex_clean[2:4], 16), int(hex_clean[4:6], 16)
        except ValueError:
            return None
        cache_key = hashlib.sha256(f"{icon_path}:{hex_clean}".encode()).hexdigest()[:16]
        cache_dir = self.template_dir / ".icon_tint_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        out_path = cache_dir / f"{cache_key}.png"
        if out_path.exists():
            return str(out_path)
        try:
            from PIL import Image
            img = Image.open(full_path).convert("RGBA")
            w, h = img.size
            # Replace RGB with tint, keep original alpha (alpha-mask behavior)
            r_band = Image.new("L", (w, h), r)
            g_band = Image.new("L", (w, h), g)
            b_band = Image.new("L", (w, h), b)
            _, _, _, a_band = img.split()
            tinted = Image.merge("RGBA", (r_band, g_band, b_band, a_band))
            tinted.save(str(out_path), "PNG")
            return str(out_path)
        except Exception as e:
            logger.debug(f"Icon tint failed {icon_path}: {e}")
            return None

    def _add_icon(
        self,
        slide,
        icon_path: str,
        pos: Dict,
        content_type: Optional[str] = None,
    ) -> None:
        """
        Add an icon to the slide. If content_type is set, the icon is tinted to the slide's
        foreground color (light slide → dark icon, dark slide → light icon) so it never
        conflicts with the theme. Every slide header should call this with an icon.
        """
        if not icon_path:
            return
        full_path = self.template_dir / icon_path
        if not full_path.exists():
            logger.debug(f"Icon not found: {full_path}")
            return
        path_to_add = str(full_path)
        if content_type:
            tint_hex = self._get_text_color_for_slide(content_type)
            tinted = self._get_tinted_icon_path(icon_path, tint_hex)
            if tinted:
                path_to_add = tinted
        try:
            slide.shapes.add_picture(
                path_to_add,
                Inches(pos.get('x', 0)),
                Inches(pos.get('y', 0)),
                Inches(pos.get('width', 0.5)),
                Inches(pos.get('height', 0.5))
            )
        except Exception as e:
            logger.debug(f"Icon error: {e}")
    
    def _hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """Convert hex color to RGB tuple"""
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def _scrub_title(self, title: str) -> str:
        """Clean title text"""
        if not title:
            return ""
        t = title.strip()
        t = re.sub(r"\(\s*continued\s*\)", "", t, flags=re.IGNORECASE)
        return re.sub(r"\s{2,}", " ", t).strip()
    
    def _set_rtl_paragraph(self, paragraph) -> None:
        """Set RTL on a paragraph"""
        if not self.lang_config.get('rtl', False):
            return
        try:
            pPr = paragraph._element.get_or_add_pPr()
            pPr.set('rtl', '1')
        except:
            pass
    
    # ========================================================================
    # BACKGROUND AND PAGE NUMBERS
    # ========================================================================
    
    def _add_background(self, slide, content_type: str) -> None:
        """Add background image to slide"""
        bg_images = self.config.get('background_images', {})
        bg_path_str = bg_images.get(content_type)
        
        if not bg_path_str:
            # Try fallback
            bg_path_str = bg_images.get('content')
        
        if not bg_path_str:
            return
        
        bg_path = self.template_dir / bg_path_str
        if not bg_path.exists():
            logger.debug(f"Background not found: {bg_path}")
            return
        
        try:
            picture = slide.shapes.add_picture(
                str(bg_path),
                Inches(0), Inches(0),
                width=self.prs.slide_width,
                height=self.prs.slide_height
            )
            # Send to back
            slide.shapes._spTree.remove(picture._element)
            slide.shapes._spTree.insert(2, picture._element)
        except Exception as e:
            logger.warning(f"Background error: {e}")
    
    def _add_page_number(self, slide, page_num: int, content_type: Optional[str] = None) -> None:
        """Add page number diamond in the same position as the Agenda slide's embedded rhombus (bottom-right), so all slides match. Text color adapts to slide_color. Double-digit numbers use a wider shape so text stays horizontal."""
        try:
            page_config = self.config.get('page_numbering', {})
            if not page_config.get('enabled', True):
                return

            # Use the same position as the Agenda slide's embedded rhombus (bottom-right) for all slides
            position = page_config.get('position_unified') or page_config.get('position_ar', page_config.get('position_en', {}))
            offset_x = float(position.get('offset_x', 12.73))
            offset_y = float(position.get('offset_y', 6.8))

            shape_config = page_config.get('shape', {})
            base_w = float(shape_config.get('width', 0.4))
            base_h = float(shape_config.get('height', 0.4))
            # Slightly larger shape for double-digit page numbers so digits stay horizontal (not stacked)
            two_digits = page_num >= 10
            shape_w = base_w * 1.25 if two_digits else base_w
            shape_h = base_h

            diamond = slide.shapes.add_shape(
                MSO_SHAPE.DIAMOND,
                Inches(offset_x), Inches(offset_y),
                Inches(shape_w), Inches(shape_h)
            )

            bg_color = self._get_color('elements.page_number_bg', shape_config.get('fill_color', 'C6C3BE'))
            fill_color = self._hex_to_rgb(bg_color)
            diamond.fill.solid()
            diamond.fill.fore_color.rgb = RGBColor(*fill_color)
            diamond.line.fill.background()

            tf = diamond.text_frame
            tf.clear()
            tf.word_wrap = False
            p = tf.paragraphs[0]
            p.text = str(page_num)
            p.alignment = PP_ALIGN.CENTER

            pn_font = self.fonts_config.get('page_number', {})
            font_config = page_config.get('font', {})

            p.font.size = Pt(pn_font.get('size', font_config.get('size', 14)))
            p.font.name = pn_font.get('name', font_config.get('name', 'Cairo'))
            p.font.bold = pn_font.get('bold', font_config.get('bold', False))

            if content_type:
                text_color_hex = self._get_text_color_for_slide(content_type)
            else:
                text_color_hex = self._get_color('elements.page_number_text', pn_font.get('color', 'FFFCEC'))
            text_color = self._hex_to_rgb(text_color_hex)
            p.font.color.rgb = RGBColor(*text_color)
            tf.vertical_anchor = MSO_ANCHOR.MIDDLE

        except Exception as e:
            logger.warning(f"Page number error: {e}")
    
    def _add_separator_line(self, slide, pos: Dict, content_type: Optional[str] = None) -> None:
        """Add a separator line. Color adapts to slide_color (light slide → dark line, dark slide → light line)."""
        try:
            line = slide.shapes.add_shape(
                MSO_SHAPE.RECTANGLE,
                Inches(pos.get('x', 1.7)),
                Inches(pos.get('y', 1.55)),
                Inches(pos.get('width', 9.6)),
                Inches(pos.get('height', 0.02))
            )
            line.fill.solid()
            if content_type:
                separator_color = self._get_separator_color_for_slide(content_type)
            else:
                separator_color = self.colors_config.get('elements', {}).get('separator_line', '01415C')
            if isinstance(separator_color, str):
                separator_color = separator_color.lstrip('#')
            line.fill.fore_color.rgb = RGBColor(*self._hex_to_rgb(separator_color))
            line.line.fill.background()
        except Exception as e:
            logger.debug(f"Separator error: {e}")
    
    # ========================================================================
    # TEXT BOX CREATION
    # ========================================================================
    
    def _add_text_box(self, slide, text: str, pos: Dict, 
                      font_name: str = None, font_size: int = None,
                      bold: bool = False, color: str = None,
                      alignment: PP_ALIGN = None) -> Any:
        """Add a text box at specified position"""
        if not text:
            return None
        
        try:
            shape = slide.shapes.add_textbox(
                Inches(pos.get('x', 0)),
                Inches(pos.get('y', 0)),
                Inches(pos.get('width', 10)),
                Inches(pos.get('height', 1))
            )
            
            tf = shape.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.text = text
            
            # Apply formatting
            p.font.name = font_name or self._get_font('body')
            if font_size:
                p.font.size = Pt(font_size)
            p.font.bold = bold
            
            if color:
                p.font.color.rgb = RGBColor(*self._hex_to_rgb(color))
            
            if alignment:
                p.alignment = alignment
            else:
                p.alignment = self._get_alignment()
            
            self._set_rtl_paragraph(p)
            
            return shape
        except Exception as e:
            logger.warning(f"Text box error: {e}")
            return None
    
    def _add_bullets_textbox(self, slide, bullets: List[BulletPoint], pos: Dict, content_type: Optional[str] = None) -> Any:
        """Add a text box with bullet points. Colors adapt to slide_color when content_type is set."""
        if not bullets:
            return None
        
        try:
            shape = slide.shapes.add_textbox(
                Inches(pos.get('x', 1)),
                Inches(pos.get('y', 1.8)),
                Inches(pos.get('width', 11)),
                Inches(pos.get('height', 5))
            )
            
            tf = shape.text_frame
            tf.word_wrap = True
            
            bullet_font = self._get_font_config('content', 'bullet', content_type=content_type)
            sub_bullet_font = self._get_font_config('content', 'sub_bullet', content_type=content_type)
            
            for i, bullet in enumerate(bullets):
                if i == 0:
                    p = tf.paragraphs[0]
                else:
                    p = tf.add_paragraph()
                
                # Clean bullet text
                text = (bullet.text or "").replace("●", "").replace("**", "").strip()
                p.text = f"• {text}"
                p.font.name = bullet_font['name']
                p.font.size = Pt(bullet_font['size'])
                p.font.bold = bullet_font['bold']
                if bullet_font['color']:
                    p.font.color.rgb = RGBColor(*self._hex_to_rgb(bullet_font['color']))
                p.level = 0
                p.alignment = self._get_alignment()
                self._set_rtl_paragraph(p)
                
                # Sub-bullets
                if hasattr(bullet, 'sub_bullets') and bullet.sub_bullets:
                    for sub in bullet.sub_bullets:
                        sub_p = tf.add_paragraph()
                        sub_text = sub.text if hasattr(sub, 'text') else str(sub)
                        sub_p.text = f"   ○ {sub_text.strip()}"
                        sub_p.font.name = sub_bullet_font['name']
                        sub_p.font.size = Pt(sub_bullet_font['size'])
                        sub_p.font.bold = sub_bullet_font['bold']
                        if sub_bullet_font['color']:
                            sub_p.font.color.rgb = RGBColor(*self._hex_to_rgb(sub_bullet_font['color']))
                        sub_p.level = 1
                        sub_p.alignment = self._get_alignment()
                        self._set_rtl_paragraph(sub_p)
            
            return shape
        except Exception as e:
            logger.warning(f"Bullets error: {e}")
            return None
    
    # ========================================================================
    # SLIDE TYPE CREATION
    # ========================================================================
    
    def _get_blank_layout(self):
        """Get the blank layout"""
        layout_idx = self.config.get('layout_mapping', {}).get('blank', 6)
        try:
            return self.prs.slide_layouts[layout_idx]
        except IndexError:
            return self.prs.slide_layouts[0]
    
    def _create_title_slide(self, presentation_data: PresentationData) -> None:
        """Create title slide matching sample layout"""
        slide = self.prs.slides.add_slide(self._get_blank_layout())
        
        # Add background
        self._add_background(slide, 'title_slide')
        content_type = 'title_slide'
        # Get positions
        positions = self.element_positions.get('title_slide', {})
        title_pos = positions.get('title', {'x': 1.5, 'y': 2.8, 'width': 10.33, 'height': 1.5})
        subtitle_pos = positions.get('subtitle', {'x': 2.0, 'y': 4.5, 'width': 9.33, 'height': 1.0})
        # Get font config (colors adapted to slide_color: dark slide → light text)
        title_font = self._get_font_config('title_slide', 'title', content_type=content_type)
        subtitle_font = self._get_font_config('title_slide', 'subtitle', content_type=content_type)
        
        # Add title
        title = presentation_data.title or "Untitled Presentation"
        self._add_text_box(
            slide, self._scrub_title(title), title_pos,
            font_name=title_font['name'],
            font_size=title_font['size'],
            bold=title_font['bold'],
            color=title_font['color'],
            alignment=PP_ALIGN.CENTER
        )
        
        # Add subtitle
        subtitle_parts = []
        if presentation_data.subtitle:
            subtitle_parts.append(presentation_data.subtitle)
        if presentation_data.author:
            subtitle_parts.append(presentation_data.author)
        
        if subtitle_parts:
            self._add_text_box(
                slide, "\n".join(subtitle_parts), subtitle_pos,
                font_name=subtitle_font['name'],
                font_size=subtitle_font['size'],
                bold=subtitle_font['bold'],
                color=subtitle_font['color'],
                alignment=PP_ALIGN.CENTER
            )
        
        logger.info("Title slide created")
    
    def _create_section_slide(self, slide_data: SlideContent, page_num: int = None) -> None:
        """Create section header slide matching sample layout"""
        slide = self.prs.slides.add_slide(self._get_blank_layout())
        
        # Add background
        self._add_background(slide, 'section')
        content_type = 'section'
        # Get positions
        positions = self.element_positions.get('section_header', {})
        icon_pos = positions.get('icon', {'x': 6.07, 'y': 2.2, 'width': 1.2, 'height': 1.2})
        title_pos = positions.get('title', {'x': 1.0, 'y': 3.8, 'width': 11.33, 'height': 1.8})
        # Get font config (colors adapted to slide_color: dark section → light text)
        title_font = self._get_font_config('section_header', 'title', content_type=content_type)
        # Every section slide has an icon; tint to slide foreground (dark slide → light icon)
        section_icon = self._ensure_header_icon(
            self._select_icon_for_content(slide_data.title, icon_type='section'),
            icon_type='section'
        )
        if section_icon:
            self._add_icon(slide, section_icon, icon_pos, content_type=content_type)
        # Add title
        self._add_text_box(
            slide, self._scrub_title(slide_data.title), title_pos,
            font_name=title_font['name'],
            font_size=title_font['size'],
            bold=title_font['bold'],
            color=title_font['color'],
            alignment=PP_ALIGN.CENTER
        )
        if page_num:
            self._add_page_number(slide, page_num, content_type=content_type)
    
    def _create_agenda_slide(self, slide_data: SlideContent, page_num: int = None) -> None:
        """
        Create agenda slide: left (beige) = topics with icons, right (dark) = AGENDA label centered.
        Uses bg_blank_3246436f.jpg which has beige left and dark right split.
        """
        slide = self.prs.slides.add_slide(self._get_blank_layout())
        self._add_background(slide, 'agenda')
        positions = self.element_positions.get('agenda', {})
        agenda_label_pos = positions.get('agenda_label', {'x': 7.20, 'y': 2.80, 'width': 4.90, 'height': 1.80})
        items_pos = positions.get('items', {'x': 0.70, 'y': 1.35, 'width': 5.50, 'height': 5.00})
        icon_size = positions.get('icon_size', {'width': 0.45, 'height': 0.45})
        item_height = float(positions.get('item_height', 0.85))
        # Right side (dark): AGENDA label → light text. Left side (light): items → dark text.
        agenda_label_font = self._get_font_config('agenda', 'agenda_label', content_type='agenda')
        agenda_text = self.config.get('localization', {}).get(self.target_language, {}).get('agenda_title', 'Agenda')
        if self.target_language == 'ar':
            agenda_text = self.config.get('localization', {}).get('ar', {}).get('agenda_title', agenda_text)
        
        self._add_text_box(
            slide, agenda_text, agenda_label_pos,
            font_name=agenda_label_font.get('name', agenda_label_font.get('name_en', 'Cairo')),
            font_size=agenda_label_font.get('size', 36),
            bold=agenda_label_font.get('bold', True),
            color=agenda_label_font.get('color', 'FFFCEC'),
            alignment=PP_ALIGN.CENTER
        )
        
        # Left side (beige): Agenda items with icons. Keep content above page-number zone (y >= 6.25).
        items_font = self._get_font_config('agenda', 'items', content_type='agenda_items')
        bullets = slide_data.bullets or []
        items_top = float(items_pos.get('y', 1.35))
        items_width = float(items_pos.get('width', 5.50))
        items_left = float(items_pos.get('x', 0.70))
        agenda_bottom_safe = 6.25  # Page number zone starts ~6.8; leave margin
        max_agenda_items = 6
        num_items = min(len(bullets), max_agenda_items)
        if num_items > 0:
            item_height = min(item_height, (agenda_bottom_safe - items_top - 0.2) / num_items)
        for i, bullet in enumerate(bullets):
            if i >= max_agenda_items:
                break
            text = getattr(bullet, 'text', bullet) if hasattr(bullet, 'text') else str(bullet)
            if not text:
                continue
            y = items_top + i * item_height
            icon_path = self._ensure_header_icon(self._select_icon_for_content(text, icon_type='title'), icon_type='title')
            if icon_path:
                self._add_icon(slide, icon_path, {
                    'x': items_left, 'y': y + 0.1,
                    'width': icon_size.get('width', 0.45),
                    'height': icon_size.get('height', 0.45)
                }, content_type='agenda_items')

            text_box_pos = {
                'x': items_left + 0.6,
                'y': y,
                'width': items_width - 0.6,
                'height': item_height
            }
            self._add_text_box(
                slide, text, text_box_pos,
                font_name=items_font.get('name', items_font.get('name_en', 'Open Sans')),
                font_size=items_font.get('size', 20),
                bold=items_font.get('bold', False),
                color=items_font.get('color', '0D2026'),
                alignment=self._get_alignment()
            )
        
        if page_num:
            self._add_page_number(slide, page_num, content_type='agenda')
    
    def _create_content_slide(self, slide_data: SlideContent, page_num: int = None) -> None:
        """Create content slide matching sample layout"""
        slide = self.prs.slides.add_slide(self._get_blank_layout())
        
        # Determine content type for background
        if slide_data.table_data:
            content_type = 'table'
        elif slide_data.chart_data:
            content_type = 'chart'
        else:
            content_type = 'content'
        
        # Add background
        self._add_background(slide, content_type)
        # Get positions
        positions = self.element_positions.get('content', {})
        icon_pos = positions.get('icon', {'x': 1.0, 'y': 0.65, 'width': 0.5, 'height': 0.5})
        title_pos = positions.get('title', {'x': 1.7, 'y': 0.6, 'width': 9.6, 'height': 0.8})
        separator_pos = positions.get('separator', {'x': 1.7, 'y': 1.55, 'width': 9.6, 'height': 0.02})
        body_pos = positions.get('body', {'x': 1.0, 'y': 1.8, 'width': 11.33, 'height': 5.2})
        # Get font configs (colors adapted to slide_color for this content_type)
        title_font = self._get_font_config('content', 'title', content_type=content_type)
        body_font = self._get_font_config('content', 'body', content_type=content_type)
        # Every content slide has a header icon; tint to slide foreground (light/dark by content_type)
        title_icon = self._ensure_header_icon(
            self._select_icon_for_content(slide_data.title, icon_type='title'),
            icon_type='title'
        )
        if title_icon:
            self._add_icon(slide, title_icon, icon_pos, content_type=content_type)
        # Add title
        self._add_text_box(
            slide, self._scrub_title(slide_data.title), title_pos,
            font_name=title_font['name'],
            font_size=title_font['size'],
            bold=title_font['bold'],
            color=title_font['color'],
            alignment=self._get_alignment()
        )
        # Add separator line (color adapted to slide)
        self._add_separator_line(slide, separator_pos, content_type=content_type)
        
        # Add content based on type
        content_added = False
        
        if slide_data.table_data and slide_data.table_data.rows:
            self._add_table(slide, slide_data.table_data, body_pos)
            content_added = True
        elif slide_data.chart_data and self.chart_service:
            self._add_chart(slide, slide_data, body_pos)
            content_added = True
        elif slide_data.bullets:
            self._add_bullets_textbox(slide, slide_data.bullets, body_pos, content_type=content_type)
            content_added = True
        elif slide_data.paragraph:
            self._add_text_box(
                slide, slide_data.paragraph, body_pos,
                font_name=body_font['name'],
                font_size=body_font['size'],
                bold=body_font['bold'],
                color=body_font['color']
            )
            content_added = True
        elif slide_data.content:
            self._add_text_box(
                slide, slide_data.content, body_pos,
                font_name=body_font['name'],
                font_size=body_font['size'],
                bold=body_font['bold'],
                color=body_font['color']
            )
            content_added = True
        
        # Log warning if no content was added
        if not content_added:
            logger.warning(f"Slide '{slide_data.title}' has no body content (no bullets, paragraph, table, or chart data)")
        
        if page_num:
            self._add_page_number(slide, page_num, content_type=content_type)
    
    def _add_table(self, slide, table_data: TableData, pos: Dict) -> None:
        """Add table at specified position"""
        if not table_data or not table_data.rows:
            return
        
        rows = len(table_data.rows) + (1 if table_data.headers else 0)
        cols = len(table_data.headers) if table_data.headers else len(table_data.rows[0])
        
        if rows == 0 or cols == 0:
            return
        
        try:
            table_shape = slide.shapes.add_table(
                rows, cols,
                Inches(pos.get('x', 1.0)),
                Inches(pos.get('y', 1.8)),
                Inches(pos.get('width', 11.0)),
                Inches(pos.get('height', 5.0))
            )
            table = table_shape.table
            
            # Fill headers
            row_idx = 0
            if table_data.headers:
                for col_idx, header in enumerate(table_data.headers):
                    cell = table.cell(0, col_idx)
                    cell.text = str(header)
                    for p in cell.text_frame.paragraphs:
                        p.font.bold = True
                        p.font.name = self._get_font('heading')
                        p.font.size = Pt(14)
                row_idx = 1
            
            # Fill data
            for data_row in table_data.rows:
                for col_idx, value in enumerate(data_row):
                    if col_idx < cols:
                        cell = table.cell(row_idx, col_idx)
                        cell.text = str(value)
                        for p in cell.text_frame.paragraphs:
                            p.font.name = self._get_font('body')
                            p.font.size = Pt(12)
                row_idx += 1
                
        except Exception as e:
            logger.warning(f"Table error: {e}")
    
    def _add_chart(self, slide, slide_data: SlideContent, pos: Dict) -> None:
        """Add chart at specified position"""
        if not self.chart_service or not slide_data.chart_data:
            return
        
        try:
            self.chart_service.create_chart(
                slide=slide,
                chart_data=slide_data.chart_data,
                left=float(pos.get('x', 1.5)),
                top=float(pos.get('y', 1.8)),
                width=float(pos.get('width', 10.0)),
                height=float(pos.get('height', 5.0))
            )
        except Exception as e:
            logger.warning(f"Chart error: {e}")
    
    # ========================================================================
    # MAIN GENERATION
    # ========================================================================
    
    def _determine_content_type(self, slide_data: SlideContent) -> str:
        """Determine content type from slide data"""
        layout_hint = getattr(slide_data, 'layout_hint', None) or ''
        if layout_hint and 'agenda' in layout_hint.lower():
            return 'agenda'
        
        if slide_data.layout_type:
            lt = slide_data.layout_type.lower()
            if lt in ['section', 'section_header']:
                return 'section'
            if lt == 'agenda':
                return 'agenda'
            return lt
        
        if slide_data.table_data:
            return "table"
        if slide_data.chart_data:
            return "chart"
        if slide_data.bullets:
            return "bullets"
        if slide_data.paragraph:
            return "paragraph"
        
        return "content"
    
    def generate(self, presentation_data: PresentationData) -> str:
        """Generate PowerPoint presentation."""
        logger.info("=" * 60)
        logger.info("Starting presentation generation...")
        
        # Configure language
        self._configure_language(presentation_data)
        
        logger.info(f"  Template: {self.template_id}")
        logger.info(f"  Language: {self.target_language}")
        
        # Validate slides
        presentation_data.slides = validate_presentation(presentation_data.slides)
        
        # Load template PPTX to get layouts
        template_pptx = self.template_dir / "template.pptx"
        if template_pptx.exists():
            logger.info(f"  Loading template: {template_pptx.name}")
            self.prs = Presentation(str(template_pptx))
            
            # Clear existing slides - we only want the layouts
            existing_count = len(self.prs.slides)
            if existing_count > 0:
                logger.info(f"  Clearing {existing_count} template slides...")
                for i in range(existing_count - 1, -1, -1):
                    rId = self.prs.slides._sldIdLst[i].rId
                    self.prs.part.drop_rel(rId)
                    del self.prs.slides._sldIdLst[i]
        else:
            logger.info("  Creating blank presentation")
            self.prs = Presentation()
            self.prs.slide_width = Inches(13.333)
            self.prs.slide_height = Inches(7.5)
        
        # Clean titles
        for slide_data in presentation_data.slides:
            if slide_data.title:
                slide_data.title = self._scrub_title(slide_data.title)
        
        # Create title slide
        try:
            self._create_title_slide(presentation_data)
        except Exception as e:
            logger.error(f"Title slide error: {e}")
            import traceback
            traceback.print_exc()
        
        # Create content slides
        page_num = 2  # Start from 2 (title is 1, but usually not numbered)
        for idx, slide_data in enumerate(presentation_data.slides):
            content_type = self._determine_content_type(slide_data)
            logger.info(f"Creating slide {idx + 2}: {content_type} - {slide_data.title[:30] if slide_data.title else 'No title'}...")
            
            try:
                if content_type in ['section', 'section_header']:
                    self._create_section_slide(slide_data, page_num=page_num)
                elif content_type == 'agenda':
                    self._create_agenda_slide(slide_data, page_num=page_num)
                else:
                    self._create_content_slide(slide_data, page_num=page_num)
                
                page_num += 1
                    
            except Exception as e:
                logger.error(f"Slide error: {e}")
                import traceback
                traceback.print_exc()
        
        # Save presentation
        output_path = self._get_output_path(presentation_data.title)
        self.prs.save(output_path)
        
        logger.info(f"Generated: {output_path}")
        logger.info(f"  Total slides: {len(self.prs.slides)}")
        logger.info("=" * 60)
        
        return output_path
    
    def _get_output_path(self, title: str) -> str:
        """Generate output file path"""
        output_dir = Path(settings.OUTPUT_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        safe_title = re.sub(r'[^\w\s-]', '', title or 'presentation')[:50]
        safe_title = safe_title.strip().replace(' ', '_')
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        lang_code = self.target_language[:2]
        
        filename = f"{self.template_id}_{lang_code}_{safe_title}_{timestamp}.pptx"
        return str(output_dir / filename)
    
    def generate_to_bytes(self, presentation_data: PresentationData) -> bytes:
        """Generate presentation and return as bytes"""
        output_path = self.generate(presentation_data)
        with open(output_path, 'rb') as f:
            return f.read()
