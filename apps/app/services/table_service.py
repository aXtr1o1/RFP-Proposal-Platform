import json
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.xmlchemy import OxmlElement
from typing import Dict, Union, Tuple
from pathlib import Path

from apps.app.config import settings

class TableService:
    """Table generation with multilingual RTL/LTR support - fully dynamic from constraints.json"""

    def __init__(self, template_id="arweqah", language="en"):
        self.template_id = template_id
        self.language = language
        
        # Load constraints dynamically
        self.constraints = self._load_constraints(template_id)
        
        # Get table configuration from constraints
        tbl = self.constraints.get("table", {})
        colors = self.constraints.get("colors", {})
        typography = self.constraints.get("typography", {})
        
        # Get language-specific fonts
        fonts = typography.get('fonts', {})
        lang_fonts = fonts.get(language, fonts.get('en', {}))
        
        # Colors from constraints
        self.header_color = self._get_color_rgb(tbl, 'header_bg', colors, "#01415C")
        self.header_text_color = self._get_color_rgb(tbl, 'header_text', colors, "#FFFCEC")
        self.alt_row_color = self._get_color_rgb(tbl, 'alternate_row_bg', colors, "#F7F4E7")
        self.text_color = self._get_color_rgb(tbl, 'body_text', colors, "#0D2026")
        self.border_color = self._get_color_rgb(tbl, 'border_color', colors, "#C6C3BE")
        
        # Configuration from constraints
        self.border_width = tbl.get("border_width", 1)
        self.rounded_corners = tbl.get("rounded_corners", True)
        self.corner_radius = tbl.get("corner_radius", 8000)
        self.max_rows_per_slide = tbl.get("max_rows", 20)
        self.cell_padding = tbl.get("cell_padding", 0.1)
        
        # Fonts from constraints (language-specific)
        self.header_font = lang_fonts.get('heading', 'Cairo')
        self.body_font = lang_fonts.get('body', 'Tajawal')
        
        # Font sizes from constraints
        font_sizes = typography.get('font_sizes', {})
        self.header_font_size = tbl.get("header_font_size", font_sizes.get('table_header', 16))
        self.body_font_size = tbl.get("body_font_size", font_sizes.get('table_body', 14))
        
        # Alignment from constraints (language-specific)
        self.header_alignment = tbl.get("header_alignment", "center")
        self.header_bold = tbl.get("header_bold", True)
        
        # Get language-specific body alignment from constraints
        alignment_config = self.constraints.get('alignment', {})
        lang_alignment = alignment_config.get(language, alignment_config.get('en', {}))
        
        if language == "ar":
            self.body_alignment = tbl.get("body_alignment_ar", lang_alignment.get('table_body', 'right'))
        else:
            self.body_alignment = tbl.get("body_alignment_en", lang_alignment.get('table_body', 'left'))
        
        # RTL support
        self.rtl_support = tbl.get("rtl_support", False)
        self.is_rtl = (language == "ar")
        
        logger_name = "table_service"
        import logging
        self.logger = logging.getLogger(logger_name)
        self.logger.info(f"✅ TableService initialized (template={template_id}, lang={language}, RTL={self.is_rtl})")

    def _get_color_rgb(self, config: Dict, key: str, colors_fallback: Dict, default: str) -> Tuple[int, int, int]:
        """Get color as RGB from config, with fallback to colors section"""
        # Try to get from table config first
        color_hex = config.get(key)
        
        # If not found, try colors section
        if not color_hex:
            color_hex = colors_fallback.get(key, default)
        
        return self._hex_to_rgb(color_hex)

    def add_table(self, slide, table_data: Union[Dict, object], position: Dict, size: Dict):
        """Add table with RTL/LTR support - fully styled from constraints"""
        try:
            # Extract data
            if isinstance(table_data, dict):
                headers = table_data.get('headers', [])
                rows = table_data.get('rows', [])
            else:
                headers = getattr(table_data, 'headers', [])
                rows = getattr(table_data, 'rows', [])

            if not headers or not rows:
                self.logger.warning("  Table missing headers or rows")
                return None
            
            # Clean headers
            headers = [str(h).strip() for h in headers]
            
            # Validate rows (use max_rows from constraints)
            validated_rows = []
            for row in rows[:self.max_rows_per_slide]:
                clean_row = [str(cell).strip() if cell else '' for cell in row]
                if len(clean_row) < len(headers):
                    clean_row.extend([''] * (len(headers) - len(clean_row)))
                elif len(clean_row) > len(headers):
                    clean_row = clean_row[:len(headers)]
                validated_rows.append(clean_row)

            num_cols = len(headers)
            num_rows = len(validated_rows) + 1
            left, top = Inches(position['left']), Inches(position['top'])
            width, height = Inches(size['width']), Inches(size['height'])

            # Add rounded rectangle background (if enabled in constraints)
            if self.rounded_corners:
                bg_shape = slide.shapes.add_shape(
                    MSO_SHAPE.ROUNDED_RECTANGLE,
                    left - Inches(0.03), top - Inches(0.03),
                    width + Inches(0.06), height + Inches(0.06)
                )
                bg_shape.fill.solid()
                bg_shape.fill.fore_color.rgb = RGBColor(255, 255, 255)
                bg_shape.line.color.rgb = RGBColor(*self.border_color)
                bg_shape.line.width = Pt(self.border_width)
                try:
                    bg_shape.adjustments[0] = 0.08
                except:
                    pass

            # Create table
            table_shape = slide.shapes.add_table(num_rows, num_cols, left, top, width, height)
            table = table_shape.table
            
            # Set column widths
            col_width_emu = int(width / num_cols)
            for col_idx in range(num_cols):
                table.columns[col_idx].width = col_width_emu

            # Style header row (using constraints)
            for col_idx, header in enumerate(headers):
                cell = table.cell(0, col_idx)
                cell.text = header
                cell.text_frame.word_wrap = True
                cell.text_frame.margin_left = Inches(self.cell_padding)
                cell.text_frame.margin_right = Inches(self.cell_padding)
                cell.text_frame.margin_top = Inches(0.08)
                cell.text_frame.margin_bottom = Inches(0.08)
                
                # Header background (from constraints)
                cell.fill.solid()
                cell.fill.fore_color.rgb = RGBColor(*self.header_color)
                
                # Header text (from constraints)
                paragraph = cell.text_frame.paragraphs[0]
                paragraph.font.bold = self.header_bold
                paragraph.font.size = Pt(self.header_font_size)
                paragraph.font.color.rgb = RGBColor(*self.header_text_color)
                paragraph.font.name = self.header_font
                paragraph.alignment = self._get_alignment(self.header_alignment)
                cell.vertical_anchor = MSO_ANCHOR.MIDDLE
                
                self._remove_cell_borders(cell)

            # Style body rows (using constraints)
            for row_idx, row_data in enumerate(validated_rows, start=1):
                for col_idx, cell_value in enumerate(row_data):
                    cell = table.cell(row_idx, col_idx)
                    cell.text = cell_value
                    cell.text_frame.word_wrap = True
                    cell.text_frame.margin_left = Inches(self.cell_padding)
                    cell.text_frame.margin_right = Inches(self.cell_padding)
                    cell.text_frame.margin_top = Inches(0.05)
                    cell.text_frame.margin_bottom = Inches(0.05)
                    
                    # Alternating row colors (from constraints)
                    if row_idx % 2 == 0:
                        cell.fill.solid()
                        cell.fill.fore_color.rgb = RGBColor(*self.alt_row_color)
                    else:
                        cell.fill.solid()
                        cell.fill.fore_color.rgb = RGBColor(255, 255, 255)
                    
                    # Body text (from constraints)
                    paragraph = cell.text_frame.paragraphs[0]
                    paragraph.font.size = Pt(self.body_font_size)
                    paragraph.font.color.rgb = RGBColor(*self.text_color)
                    paragraph.font.name = self.body_font
                    paragraph.line_spacing = 1.2
                    cell.vertical_anchor = MSO_ANCHOR.MIDDLE
                    
                    # Language-specific alignment (from constraints)
                    if col_idx == 0:
                        # First column follows body alignment (RTL/LTR aware)
                        paragraph.alignment = self._get_alignment(self.body_alignment)
                    else:
                        # Other columns center-aligned
                        paragraph.alignment = PP_ALIGN.CENTER
                    
                    self._add_subtle_inner_borders(cell, row_idx, col_idx, num_rows, num_cols)
            
            self.logger.info(f"✅ Table rendered: {num_cols} cols, {len(validated_rows)} rows (RTL={self.is_rtl})")
            return table
        except Exception as e:
            self.logger.error(f"  Table error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _get_alignment(self, alignment: str) -> PP_ALIGN:
        """Convert alignment string to PP_ALIGN enum"""
        alignment = alignment.lower()
        if alignment == 'center':
            return PP_ALIGN.CENTER
        elif alignment == 'right':
            return PP_ALIGN.RIGHT
        elif alignment == 'justify':
            return PP_ALIGN.JUSTIFY
        else:
            return PP_ALIGN.LEFT

    def _remove_cell_borders(self, cell):
        """Remove cell borders"""
        try:
            tc = cell._tc
            tcPr = tc.get_or_add_tcPr()
            for border_name in ['lnL', 'lnR', 'lnT', 'lnB']:
                existing = tcPr.find(f'.//{{{tcPr.nsmap.get("a", "http://schemas.openxmlformats.org/drawingml/2006/main")}}}{border_name}')
                if existing is not None:
                    tcPr.remove(existing)
                ln = OxmlElement(f'a:{border_name}')
                ln.set('w', '0')
                noFill = OxmlElement('a:noFill')
                ln.append(noFill)
                tcPr.append(ln)
        except:
            pass

    def _add_subtle_inner_borders(self, cell, row_idx, col_idx, num_rows, num_cols):
        """Add subtle inner borders (using border color from constraints)"""
        try:
            tc = cell._tc
            tcPr = tc.get_or_add_tcPr()
            if col_idx < num_cols - 1:
                self._set_border(tcPr, 'lnR', self.border_color, width=6350)
            if row_idx < num_rows - 1:
                self._set_border(tcPr, 'lnB', self.border_color, width=6350)
        except:
            pass

    def _set_border(self, tcPr, border_name: str, color_rgb: tuple, width: int = 12700):
        """Set cell border"""
        try:
            ln = OxmlElement(f'a:{border_name}')
            ln.set('w', str(width))
            solidFill = OxmlElement('a:solidFill')
            srgbClr = OxmlElement('a:srgbClr')
            srgbClr.set('val', '%02x%02x%02x' % color_rgb)
            solidFill.append(srgbClr)
            ln.append(solidFill)
            tcPr.append(ln)
        except:
            pass

    def _load_constraints(self, template_id):
        """Load constraints.json from template directory"""
        path = Path(settings.TEMPLATES_DIR) / template_id / "constraints.json"
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)

    def _hex_to_rgb(self, hex_color) -> Tuple[int, int, int]:
        """Convert hex to RGB"""
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    def add_table(self, slide, table_data: Union[Dict, object], position: Dict, size: Dict):
        """Add table with RTL/LTR support"""
        try:
            # Extract data
            if isinstance(table_data, dict):
                headers = table_data.get('headers', [])
                rows = table_data.get('rows', [])
            else:
                headers = getattr(table_data, 'headers', [])
                rows = getattr(table_data, 'rows', [])

            if not headers or not rows:
                print("  Table missing headers or rows")
                return None
            
            # Clean headers
            headers = [str(h).strip() for h in headers]
            
            # Validate rows
            validated_rows = []
            for row in rows[:self.max_rows_per_slide]:
                clean_row = [str(cell).strip() if cell else '' for cell in row]
                if len(clean_row) < len(headers):
                    clean_row.extend([''] * (len(headers) - len(clean_row)))
                elif len(clean_row) > len(headers):
                    clean_row = clean_row[:len(headers)]
                validated_rows.append(clean_row)

            num_cols = len(headers)
            num_rows = len(validated_rows) + 1
            left, top = Inches(position['left']), Inches(position['top'])
            width, height = Inches(size['width']), Inches(size['height'])

            # Add rounded rectangle background
            if self.rounded_corners:
                bg_shape = slide.shapes.add_shape(
                    MSO_SHAPE.ROUNDED_RECTANGLE,
                    left - Inches(0.03), top - Inches(0.03),
                    width + Inches(0.06), height + Inches(0.06)
                )
                bg_shape.fill.solid()
                bg_shape.fill.fore_color.rgb = RGBColor(255, 255, 255)
                bg_shape.line.color.rgb = RGBColor(*self.border_color)
                bg_shape.line.width = Pt(self.border_width)
                try:
                    bg_shape.adjustments[0] = 0.08
                except:
                    pass

            # Create table
            table_shape = slide.shapes.add_table(num_rows, num_cols, left, top, width, height)
            table = table_shape.table
            
            # Set column widths
            col_width_emu = int(width / num_cols)
            for col_idx in range(num_cols):
                table.columns[col_idx].width = col_width_emu

            # Style header row
            for col_idx, header in enumerate(headers):
                cell = table.cell(0, col_idx)
                cell.text = header
                cell.text_frame.word_wrap = True
                cell.text_frame.margin_left = Inches(0.1)
                cell.text_frame.margin_right = Inches(0.1)
                cell.text_frame.margin_top = Inches(0.08)
                cell.text_frame.margin_bottom = Inches(0.08)
                
                # Header background
                cell.fill.solid()
                cell.fill.fore_color.rgb = RGBColor(*self.header_color)
                
                # Header text
                paragraph = cell.text_frame.paragraphs[0]
                paragraph.font.bold = True
                paragraph.font.size = Pt(self.header_font_size)
                paragraph.font.color.rgb = RGBColor(*self.header_text_color)
                paragraph.font.name = self.header_font
                paragraph.alignment = self._get_alignment(self.header_alignment)
                cell.vertical_anchor = MSO_ANCHOR.MIDDLE
                
                self._remove_cell_borders(cell)

            # Style body rows
            for row_idx, row_data in enumerate(validated_rows, start=1):
                for col_idx, cell_value in enumerate(row_data):
                    cell = table.cell(row_idx, col_idx)
                    cell.text = cell_value
                    cell.text_frame.word_wrap = True
                    cell.text_frame.margin_left = Inches(0.1)
                    cell.text_frame.margin_right = Inches(0.1)
                    cell.text_frame.margin_top = Inches(0.05)
                    cell.text_frame.margin_bottom = Inches(0.05)
                    
                    # Alternating row colors
                    if row_idx % 2 == 0:
                        cell.fill.solid()
                        cell.fill.fore_color.rgb = RGBColor(*self.alt_row_color)
                    else:
                        cell.fill.solid()
                        cell.fill.fore_color.rgb = RGBColor(255, 255, 255)
                    
                    # Body text
                    paragraph = cell.text_frame.paragraphs[0]
                    paragraph.font.size = Pt(self.body_font_size)
                    paragraph.font.color.rgb = RGBColor(*self.text_color)
                    paragraph.font.name = self.body_font
                    paragraph.line_spacing = 1.2
                    cell.vertical_anchor = MSO_ANCHOR.MIDDLE
                    
                    # Language-specific alignment
                    if col_idx == 0:
                        # First column follows body alignment
                        paragraph.alignment = self._get_alignment(self.body_alignment)
                    else:
                        # Other columns center-aligned
                        paragraph.alignment = PP_ALIGN.CENTER
                    
                    self._add_subtle_inner_borders(cell, row_idx, col_idx, num_rows, num_cols)
            
            return table
        except Exception as e:
            print(f"  Table error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _get_alignment(self, alignment: str) -> PP_ALIGN:
        """Convert alignment string to PP_ALIGN enum"""
        alignment = alignment.lower()
        if alignment == 'center':
            return PP_ALIGN.CENTER
        elif alignment == 'right':
            return PP_ALIGN.RIGHT
        elif alignment == 'justify':
            return PP_ALIGN.JUSTIFY
        else:
            return PP_ALIGN.LEFT

    def _remove_cell_borders(self, cell):
        """Remove cell borders"""
        try:
            tc = cell._tc
            tcPr = tc.get_or_add_tcPr()
            for border_name in ['lnL', 'lnR', 'lnT', 'lnB']:
                existing = tcPr.find(f'.//{{{tcPr.nsmap.get("a", "http://schemas.openxmlformats.org/drawingml/2006/main")}}}{border_name}')
                if existing is not None:
                    tcPr.remove(existing)
                ln = OxmlElement(f'a:{border_name}')
                ln.set('w', '0')
                noFill = OxmlElement('a:noFill')
                ln.append(noFill)
                tcPr.append(ln)
        except:
            pass

    def _add_subtle_inner_borders(self, cell, row_idx, col_idx, num_rows, num_cols):
        """Add subtle inner borders"""
        try:
            tc = cell._tc
            tcPr = tc.get_or_add_tcPr()
            if col_idx < num_cols - 1:
                self._set_border(tcPr, 'lnR', self.border_color, width=6350)
            if row_idx < num_rows - 1:
                self._set_border(tcPr, 'lnB', self.border_color, width=6350)
        except:
            pass

    def _set_border(self, tcPr, border_name: str, color_rgb: tuple, width: int = 12700):
        """Set cell border"""
        try:
            ln = OxmlElement(f'a:{border_name}')
            ln.set('w', str(width))
            solidFill = OxmlElement('a:solidFill')
            srgbClr = OxmlElement('a:srgbClr')
            srgbClr.set('val', '%02x%02x%02x' % color_rgb)
            solidFill.append(srgbClr)
            ln.append(solidFill)
            tcPr.append(ln)
        except:
            pass

    def _load_constraints(self, template_id):
        """Load constraints.json"""
        path = Path(settings.TEMPLATES_DIR) / template_id / "constraints.json"
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)

    def _hex_to_rgb(self, hex_color) -> Tuple[int, int, int]:
        """Convert hex to RGB"""
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))