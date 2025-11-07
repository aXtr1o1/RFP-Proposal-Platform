import os
import json
import logging
from pathlib import Path
from typing import Tuple, Optional, List

from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_ORIENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from apps.wordgenAgent.app.config_setting import build_updated_config

logger = logging.getLogger("wordcom")

# ---- Keep numeric semantics compatible with your config_setting mappings ----
WD_ALIGN_LEFT = 0
WD_ALIGN_CENTER = 1
WD_ALIGN_RIGHT = 2
WD_ALIGN_JUSTIFY = 3

WD_READINGORDER_LTR = 0
WD_READINGORDER_RTL = 1

WD_LINE_SPACE_SINGLE = 0  

# ---- Default configuration stays exactly the same ----
default_CONFIG = {
    "visible_word": False,                     
    "output_path": "output/proposal.docx",
    "language_lcid": 1025,                     
    "default_alignment": 0,
    "reading_order": 0,
    "space_before": 0,
    "space_after": 6,
    "line_spacing_rule": 0,
    "orientation": 0,                           
    "margin_top": 72,
    "margin_bottom": 72,
    "margin_left": 72,
    "margin_right": 72,

    "table_autofit": True,
    "table_preferred_width": 100,              

    "title_style": "Title",
    "heading_style": "Heading 1",
    "normal_style": "Normal",

    "font_size": 11,
    "heading_font_size": 14,
    "title_font_size": 16,
    "points_font_size": 11,
    "table_font_size": 10,

    "title_font_color": 0,
    "heading_font_color": 0,
    "content_font_color": 0,
    "table_font_color": 0,

    "table_border_visible": True,
    "table_border_color": 0,
    "table_border_line_style": 1,
    "table_border_line_width": 1,
    "table_border_preset": "grid",

    "table_header_shading_color": None,
    "table_body_shading_color": None,

    "enable_header": False,
    "enable_footer": False,
    "company_name": "",
    "company_tagline": "",
    "header_logo_path": "",
    "header_logo_width": 5,     
    "header_logo_height": 2,    
    "header_logo_max_width": 120,   
    "header_logo_max_height": 60,  
    "header_padding": 6,

    "footer_left_text": "",
    "footer_center_text": "",
    "footer_right_text": "",
    "footer_show_page_numbers": True,
    "footer_padding": 6,
}


def _bgr_int_to_rgb_tuple(bgr: int) -> Tuple[int, int, int]:
    """Convert BGR int (Word/COM style) to (R, G, B) tuple."""
    if bgr is None:
        return (0, 0, 0)
    b = (bgr >> 16) & 0xFF
    g = (bgr >> 8) & 0xFF
    r = (bgr >> 0) & 0xFF
    return (r, g, b)

def _bgr_int_to_hex(bgr: Optional[int]) -> Optional[str]:
    if bgr is None:
        return None
    r, g, b = _bgr_int_to_rgb_tuple(bgr)
    return f"{r:02X}{g:02X}{b:02X}"

def _map_align(value: int) -> WD_ALIGN_PARAGRAPH:
    mapping = {
        WD_ALIGN_LEFT: WD_ALIGN_PARAGRAPH.LEFT,
        WD_ALIGN_CENTER: WD_ALIGN_PARAGRAPH.CENTER,
        WD_ALIGN_RIGHT: WD_ALIGN_PARAGRAPH.RIGHT,
        WD_ALIGN_JUSTIFY: WD_ALIGN_PARAGRAPH.JUSTIFY,
    }
    return mapping.get(value, WD_ALIGN_PARAGRAPH.LEFT)

def _set_paragraph_bidi(paragraph, rtl: bool) -> None:
    """Apply RTL/LTR reading order at paragraph level via oxml."""
    pPr = paragraph._p.get_or_add_pPr()
    bidi = pPr.find(qn("w:bidi"))
    if bidi is None:
        bidi = OxmlElement("w:bidi")
        pPr.append(bidi)
    bidi.set(qn("w:val"), "1" if rtl else "0")

def _add_page_number_field(paragraph) -> None:
    """Insert a PAGE field that Word updates on open/print."""
    run = paragraph.add_run()
    fldChar_begin = OxmlElement('w:fldChar')
    fldChar_begin.set(qn('w:fldCharType'), 'begin')

    instrText = OxmlElement('w:instrText')
    instrText.set(qn('xml:space'), 'preserve')
    instrText.text = ' PAGE '

    fldChar_separate = OxmlElement('w:fldChar')
    fldChar_separate.set(qn('w:fldCharType'), 'separate')

    fldChar_end = OxmlElement('w:fldChar')
    fldChar_end.set(qn('w:fldCharType'), 'end')

    r = run._r
    r.append(fldChar_begin)
    r.append(instrText)
    r.append(fldChar_separate)
    r.append(OxmlElement('w:t'))
    r.append(fldChar_end)

def _set_table_width_pct(table, pct: int) -> None:
    """Set table width as percentage using oxml (w:tblW type='pct')."""
    pct = max(1, min(100, int(pct or 100)))
    tblPr = table._tbl.tblPr
    tblW = tblPr.find(qn('w:tblW'))
    if tblW is None:
        tblW = OxmlElement('w:tblW')
        tblPr.append(tblW)
    tblW.set(qn('w:type'), 'pct')
    tblW.set(qn('w:w'), str(pct * 50))

def _set_table_borders(table, color_bgr: int, line_style: int, line_width: int, visible: bool) -> None:
    """Apply borders to a table via oxml."""
    tblPr = table._tbl.tblPr
    borders = tblPr.find(qn('w:tblBorders'))
    if borders is None:
        borders = OxmlElement('w:tblBorders')
        tblPr.append(borders)
    
    if not visible:
        for side in ['top', 'left', 'bottom', 'right', 'insideH', 'insideV']:
            el = borders.find(qn(f"w:{side}"))
            if el is None:
                el = OxmlElement(f"w:{side}")
                borders.append(el)
            el.set(qn('w:val'), 'nil')
        return

    color_hex = _bgr_int_to_hex(color_bgr) or "000000"
    style_map = {
        1: "single",
        2: "double",
        3: "dashed",
        4: "dotted",
    }
    val = style_map.get(line_style, "single")
    size = str(max(4, min(24, int(line_width or 8)))) 

    for side in ['top', 'left', 'bottom', 'right', 'insideH', 'insideV']:
        el = borders.find(qn(f"w:{side}"))
        if el is None:
            el = OxmlElement(f"w:{side}")
            borders.append(el)
        el.set(qn('w:val'), val)
        el.set(qn('w:sz'), size)
        el.set(qn('w:space'), "0")
        el.set(qn('w:color'), color_hex)

def _shade_cell(cell, fill_hex: Optional[str]) -> None:
    if not fill_hex:
        return
    tcPr = cell._tc.get_or_add_tcPr()
    shd = tcPr.find(qn('w:shd'))
    if shd is None:
        shd = OxmlElement('w:shd')
        tcPr.append(shd)
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), fill_hex)


def _para_format(paragraph, align, rtl: bool, space_before: int = 0, space_after: int = 6) -> None:
    paragraph.alignment = _map_align(align)
    paragraph.paragraph_format.space_before = Pt(space_before or 0)
    paragraph.paragraph_format.space_after = Pt(space_after or 0)
    paragraph.paragraph_format.line_spacing = 1.0  
    _set_paragraph_bidi(paragraph, rtl=rtl)

def _add_para(doc, text, style=None, align=WD_ALIGN_LEFT, size=None, color=None, bold=None, rtl=False):
    """Create a paragraph in the active document (python-docx)."""
    p = doc.add_paragraph()
    if style:
        try:
            p.style = style
        except Exception:
            pass
    run = p.add_run(text or "")
    if size:
        run.font.size = Pt(size)
    if color is not None:
        r, g, b = _bgr_int_to_rgb_tuple(int(color))
        run.font.color.rgb = RGBColor(r, g, b)
    if bold is not None:
        run.font.bold = bool(bold)

    _para_format(p, align, rtl=rtl, space_before=0, space_after=6)
    return p

def _add_table(doc, headers, rows, cfg, rtl: bool):
    """Create a table with headers/rows and apply width/borders/shading."""
    headers = headers or []
    rows = rows or []

    n_rows = max(1, len(rows) + (1 if headers else 0))
    n_cols = max(1, len(headers) if headers else (len(rows[0]) if rows and rows[0] else 1))

    table = doc.add_table(rows=n_rows, cols=n_cols)
    table.autofit = bool(cfg.get("table_autofit", True))
    _set_table_width_pct(table, cfg.get("table_preferred_width", 100))
    _set_table_borders(
        table=table,
        color_bgr=int(cfg.get("table_border_color", 0) or 0),
        line_style=int(cfg.get("table_border_line_style", 1) or 1),
        line_width=int(cfg.get("table_border_line_width", 1) or 1),
        visible=bool(cfg.get("table_border_visible", True)),
    )
    header_fill = _bgr_int_to_hex(cfg.get("table_header_shading_color"))
    body_fill = _bgr_int_to_hex(cfg.get("table_body_shading_color"))
    font_rgb = _bgr_int_to_rgb_tuple(int(cfg.get("table_font_color", 0) or 0))

    r_idx = 0
    if headers:
        for c_idx in range(min(n_cols, len(headers))):
            cell = table.cell(r_idx, c_idx)
            cell.text = ""
            p = cell.paragraphs[0]
            run = p.add_run(str(headers[c_idx]))
            run.font.size = Pt(cfg.get("table_font_size", 10))
            run.font.color.rgb = RGBColor(*font_rgb)
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            _set_paragraph_bidi(p, rtl)
            _shade_cell(cell, header_fill)
        r_idx += 1

    for r in rows[: n_rows - r_idx]:
        for c_idx in range(min(n_cols, len(r))):
            cell = table.cell(r_idx, c_idx)
            cell.text = ""
            p = cell.paragraphs[0]
            run = p.add_run(str(r[c_idx]))
            run.font.size = Pt(cfg.get("table_font_size", 10))
            run.font.color.rgb = RGBColor(*font_rgb)
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            _set_paragraph_bidi(p, rtl)
            _shade_cell(cell, body_fill)
        r_idx += 1


def _apply_header_footer(doc: Document, cfg: dict, rtl: bool) -> None:
    section = doc.sections[0]
    if int(cfg.get("orientation", 0) or 0) == 1:
        section.orientation = WD_ORIENT.LANDSCAPE
    else:
        section.orientation = WD_ORIENT.PORTRAIT

    section.top_margin = Pt(cfg.get("margin_top", 72) or 72)
    section.bottom_margin = Pt(cfg.get("margin_bottom", 72) or 72)
    section.left_margin = Pt(cfg.get("margin_left", 72) or 72)
    section.right_margin = Pt(cfg.get("margin_right", 72) or 72)

    if cfg.get("enable_header"):
        header = section.header
        header.is_linked_to_previous = False
        tbl = header.add_table(rows=1, cols=2, width=section.page_width)
        tbl.autofit = True

        logo_path = (cfg.get("header_logo_path") or "").strip()
        if logo_path and os.path.exists(logo_path):
            cell = tbl.cell(0, 0)
            p = cell.paragraphs[0]
            try:
                p.add_run().add_picture(logo_path, width=Inches(float(cfg.get("header_logo_width", 5) or 5)))
            except Exception as e:
                logger.warning(f"Header logo add failed: {e}")
        else:
            tbl.cell(0, 0).text = ""
        name = (cfg.get("company_name") or "").strip()
        tag = (cfg.get("company_tagline") or "").strip()
        cell = tbl.cell(0, 1)
        cell.text = ""
        p = cell.paragraphs[0]
        if name:
            r = p.add_run(name)
            r.font.bold = True
            r.font.size = Pt(max(cfg.get("heading_font_size", 14), 12))
        if tag:
            p.add_run("\n")
            r2 = p.add_run(tag)
            r2.font.size = Pt(cfg.get("font_size", 11))
        p.alignment = _map_align(cfg.get("default_alignment", 0))
        _set_paragraph_bidi(p, rtl)
        
    if cfg.get("enable_footer"):
        footer = section.footer
        footer.is_linked_to_previous = False
        tbl = footer.add_table(rows=1, cols=3, width=section.page_width)
        tbl.autofit = True

        left = (cfg.get("footer_left_text") or "").strip()
        center = (cfg.get("footer_center_text") or "").strip()
        right = (cfg.get("footer_right_text") or "").strip()
        p = tbl.cell(0, 0).paragraphs[0]
        if left:
            p.add_run(left)
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        _set_paragraph_bidi(p, rtl)
        p = tbl.cell(0, 1).paragraphs[0]
        if center:
            p.add_run(center + " ")
        if cfg.get("footer_show_page_numbers", True):
            _add_page_number_field(p)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _set_paragraph_bidi(p, rtl)
        p = tbl.cell(0, 2).paragraphs[0]
        if right:
            p.add_run(right)
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        _set_paragraph_bidi(p, rtl)

def build_word_from_proposal(proposal_dict, user_config, output_path, visible=False):
    """
    Build a DOCX using python-docx. Language-aware (Arabic/English) formatting.
    Renders 'points' as lines prefixed by '- ' (kept from your COM logic).
    """
    logger.info("word started to build ra bois")
    if isinstance(proposal_dict, str):
        proposal_dict = json.loads(proposal_dict)

    cfg = build_updated_config(default_CONFIG, user_config)

    rtl = bool(cfg.get("reading_order", WD_READINGORDER_LTR))

    title = (proposal_dict.get("title") or "").strip()
    sections = proposal_dict.get("sections", [])
    logger.info(f"Generating Word doc with title: {title} and {len(sections)} sections")

    doc = Document()
    _apply_header_footer(doc, cfg, rtl)

    if title:
        _add_para(
            doc, title, style=cfg.get("title_style", "Title"),
            align=cfg.get("default_alignment", WD_ALIGN_LEFT),
            size=cfg.get("title_font_size", 16),
            color=cfg.get("title_font_color", 0),
            bold=True, rtl=rtl
        )

    for sec in sections:
        heading = (sec.get("heading") or "").strip()
        content = (sec.get("content") or "").strip()
        points = sec.get("points") or []
        table = sec.get("table") or {}
        headers = table.get("headers") or []
        rows = table.get("rows") or []

        if heading:
            _add_para(
                doc, heading, style=cfg.get("heading_style", "Heading 1"),
                align=cfg.get("default_alignment", WD_ALIGN_LEFT),
                size=cfg.get("heading_font_size", 14),
                color=cfg.get("heading_font_color", 0),
                bold=True, rtl=rtl
            )

        if content:
            for para in content.split("\n"):
                t = (para or "").strip()
                if t:
                    _add_para(
                        doc, t, style=cfg.get("normal_style", "Normal"),
                        align=cfg.get("default_alignment", WD_ALIGN_LEFT),
                        size=cfg.get("font_size", 11),
                        color=cfg.get("content_font_color", 0),
                        bold=False, rtl=rtl
                    )

        if points:
            for ptxt in points:
                t = str(ptxt or "").strip()
                if not t:
                    continue
                _add_para(
                    doc, f"- {t}", style=cfg.get("normal_style", "Normal"),
                    align=cfg.get("default_alignment", WD_ALIGN_LEFT),
                    size=cfg.get("points_font_size", 11),
                    color=cfg.get("content_font_color", 0),
                    bold=False, rtl=rtl
                )

        if headers or rows:
            _add_table(doc, headers, rows, cfg, rtl=rtl)

    abs_out = str(Path(output_path or default_CONFIG["output_path"]).resolve())
    Path(abs_out).parent.mkdir(parents=True, exist_ok=True)
    doc.save(abs_out)
    logger.info(f"Document saved: {abs_out}")
    return abs_out
