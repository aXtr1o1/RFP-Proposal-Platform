import os
import json
import logging
from pathlib import Path

import pythoncom
import win32com
from win32com.client import gencache, Dispatch, makepy

from apps.wordgenAgent.app.config_setting import build_updated_config

logger = logging.getLogger("wordcom")

WD_ALIGN_LEFT = 0
WD_ALIGN_CENTER = 1
WD_ALIGN_RIGHT = 2
WD_ALIGN_JUSTIFY = 3
WD_READINGORDER_LTR = 0
WD_READINGORDER_RTL = 1
WD_LINE_SPACE_SINGLE = 0
WD_TABLE_DIRECTION_LTR = 1
WD_TABLE_DIRECTION_RTL = 2
WD_FORMAT_DOCX = 12

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

def _repair_genpy_cache():
    import shutil
    gen_path = getattr(win32com, "__gen_path__", None)
    if gen_path and os.path.isdir(gen_path):
        try:
            shutil.rmtree(gen_path, ignore_errors=True)
            logger.warning(f"Cleared win32com gen_py cache: {gen_path}")
        except Exception as e:
            logger.warning(f"Failed to clear gen_py cache: {e}")
    for spec in (
        "Microsoft Word 16.0 Object Library",
        "Microsoft Word 15.0 Object Library",
        "Microsoft Word 14.0 Object Library",
        "Microsoft Word 12.0 Object Library",
    ):
        try:
            makepy.GenerateFromTypeLibSpec(spec)
            logger.info(f"Generated makepy wrappers: {spec}")
            break
        except Exception:
            pass

def _get_word_app(visible: bool = False):
    pythoncom.CoInitialize()
    try:
        app = gencache.EnsureDispatch("Word.Application")
    except Exception as e:
        logger.warning(f"EnsureDispatch failed: {e}; repairing cache…")
        _repair_genpy_cache()
        try:
            app = gencache.EnsureDispatch("Word.Application")
        except Exception:
            app = Dispatch("Word.Application")
    app.Visible = bool(visible)
    app.DisplayAlerts = 0
    return app

def _para_format(paragraph, align, rtl: bool):
    pf = paragraph.Format
    pf.ReadingOrder = WD_READINGORDER_RTL if rtl else WD_READINGORDER_LTR
    pf.Alignment = align
    pf.SpaceBefore = 0
    pf.SpaceAfter = 6
    pf.LineSpacingRule = WD_LINE_SPACE_SINGLE

def _add_para(doc, text, style=None, align=WD_ALIGN_LEFT, size=None, color=None, bold=None, rtl=False):
    p = doc.Paragraphs.Add()
    if style:
        try:
            p.Style = style
        except Exception:
            pass
    p.Range.Text = text
    _para_format(p, align, rtl=rtl)
    try:
        if size:
            p.Range.Font.Size = size
        if color is not None:
            p.Range.Font.Color = int(color)
        if bold is not None:
            p.Range.Font.Bold = 1 if bold else 0
    except Exception:
        pass
    p.Range.InsertParagraphAfter()
    return p

def _add_table(doc, headers, rows, cfg, rtl: bool):
    if not headers and not rows:
        return
    n_rows = max(1, len(rows) + (1 if headers else 0))
    n_cols = max(1, len(headers) if headers else (len(rows[0]) if rows and rows[0] else 1))

    anchor = doc.Paragraphs.Add().Range
    table = doc.Tables.Add(anchor, n_rows, n_cols)

    try:
        table.Rows.LeftIndent = 0
        page_width = doc.PageSetup.PageWidth - doc.PageSetup.LeftMargin - doc.PageSetup.RightMargin
        table.PreferredWidth = page_width
        table.PreferredWidthType = 1

        try:
            table.Direction = WD_TABLE_DIRECTION_RTL if rtl else WD_TABLE_DIRECTION_LTR
        except Exception:
            pass

        borders = table.Borders
        if cfg.get("table_border_visible", True):
            style = cfg.get("table_border_line_style", 1)
            color = int(cfg.get("table_border_color", 0))
            borders.Enable = 1
            borders.OutsideLineStyle = style
            borders.OutsideColor = color
            borders.InsideLineStyle = style
            borders.InsideColor = color
        else:
            borders.Enable = 0
    except Exception:
        pass

    row_i = 1
    if headers:
        for j, h in enumerate(headers, 1):
            if j <= n_cols:
                cell = table.Cell(row_i, j)
                cell.Range.Text = str(h)
                try:
                    cell.Range.ParagraphFormat.ReadingOrder = WD_READINGORDER_RTL if rtl else WD_READINGORDER_LTR
                    cell.Range.ParagraphFormat.Alignment = 1
                    cell.Range.Bold = True
                    cell.Range.Font.Size = cfg["table_font_size"]
                    cell.Range.Font.Color = int(cfg.get("table_font_color", 0))
                except Exception:
                    pass
        row_i += 1

    for r in rows:
        if row_i <= n_rows:
            for j, v in enumerate(r[:n_cols], 1):
                cell = table.Cell(row_i, j)
                cell.Range.Text = str(v)
                try:
                    cell.Range.ParagraphFormat.ReadingOrder = WD_READINGORDER_RTL if rtl else WD_READINGORDER_LTR
                    cell.Range.ParagraphFormat.Alignment = 1
                    cell.Range.Font.Size = cfg["table_font_size"]
                    cell.Range.Font.Color = int(cfg.get("table_font_color", 0))
                except Exception:
                    pass
            row_i += 1

    try:
        table.AutoFitBehavior(2)
    except Exception:
        pass

def build_word_from_proposal(proposal_dict, user_config, output_path, language, visible=False):
    """
    Build a DOCX using Word COM. Language-aware (Arabic/English) formatting.
    Now renders 'points' as plain paragraphs (no Word bullets) to avoid bidi bullet glitches.
    """
    if isinstance(proposal_dict, str):
        proposal_dict = json.loads(proposal_dict)

    cfg = build_updated_config(default_CONFIG, user_config)

    lang = (language).lower()
    rtl = (lang == "arabic")

    if rtl:
        cfg["reading_order"] = WD_READINGORDER_RTL
        cfg["language_lcid"] = 1025  # Arabic
    else:
        cfg["reading_order"] = WD_READINGORDER_LTR
        cfg["language_lcid"] = 1033  # English

    title = (proposal_dict.get("title") or "").strip()
    sections = proposal_dict.get("sections", [])
    logger.info(f"Generating Word doc with title: {title} and {len(sections)} sections")

    word = _get_word_app(visible=visible)
    doc = None
    try:
        doc = word.Documents.Add()

        ps = doc.PageSetup
        ps.Orientation = cfg["orientation"]
        ps.TopMargin = cfg["margin_top"]
        ps.BottomMargin = cfg["margin_bottom"]
        ps.LeftMargin = cfg["margin_left"]
        ps.RightMargin = cfg["margin_right"]

        try:
            doc.Content.LanguageID = cfg["language_lcid"]
        except Exception:
            pass

        if title:
            _add_para(
                doc, title, style=cfg.get("title_style", "Title"),
                align=cfg["default_alignment"], size=cfg["title_font_size"],
                color=cfg.get("title_font_color", 0), bold=True, rtl=rtl
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
                    align=cfg["default_alignment"], size=cfg["heading_font_size"],
                    color=cfg.get("heading_font_color", 0), bold=True, rtl=rtl
                )

            if content:
                for para in content.split("\n"):
                    t = para.strip()
                    if t:
                        _add_para(
                            doc, t, style=cfg.get("normal_style", "Normal"),
                            align=cfg["default_alignment"], size=cfg["font_size"],
                            color=cfg.get("content_font_color", 0), bold=False, rtl=rtl
                        )

            # Render points as normal paragraphs prefixed by "- " (no Word bullet lists)
            if points:
                for p in points:
                    t = str(p).strip()
                    if not t:
                        continue
                    _add_para(
                        doc, f"- {t}", style=cfg.get("normal_style", "Normal"),
                        align=cfg["default_alignment"], size=cfg["points_font_size"],
                        color=cfg.get("content_font_color", 0), bold=False, rtl=rtl
                    )

            if headers or rows:
                _add_table(doc, headers, rows, cfg, rtl=rtl)

        abs_out = str(Path(output_path).resolve())
        Path(abs_out).parent.mkdir(parents=True, exist_ok=True)
        doc.SaveAs(abs_out, FileFormat=WD_FORMAT_DOCX)
        logger.info(f"Document saved: {abs_out}")
        return abs_out

    finally:
        if doc:
            try:
                doc.Close(SaveChanges=False)
            except Exception:
                pass
        try:
            word.Quit()
        except Exception:
            pass
        pythoncom.CoUninitialize()
