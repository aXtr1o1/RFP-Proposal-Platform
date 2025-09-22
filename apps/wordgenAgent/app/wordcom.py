import json
import logging
import os
from pathlib import Path
from apps.wordgenAgent.app.config_setting import build_updated_config


try:
    import win32com.client as win32
except Exception as e:
    raise RuntimeError("win32com is required. Install with: pip install pywin32") from e

default_CONFIG = {
    "visible_word": False,         
    "output_path": "output/proposal.docx",
    "language_lcid": 1025,         
    "default_alignment": 2,        
    "reading_order": 1,           
    "space_before": 0,
    "space_after": 6,
    "line_spacing_rule": 0,     
    "orientation": 0,             
    "margin_top": 72,              
    "margin_bottom": 72,
    "margin_left": 72,
    "margin_right": 72,

    "table_autofit": True,
    "table_preferred_width": None, 
    "title_style": "Title",
    "heading_style": "Heading 1",
    "normal_style": "Normal",
    "font_size": 14,        
    "heading_font_size": 16, 
    "title_font_size": 20,
    "points_font_size": 14,  
    "table_font_size": 12,   
    "title_font_color": 0,
    "heading_font_color": 0,
    "content_font_color": 0,

    "table_font_color": 0,           
    "table_border_visible": True,    
    "table_border_color": 0,        
    "table_border_line_style": 1,    
    "table_border_line_width": 1,   
    "table_border_preset": "all",    
    "table_header_shading_color": None, 
    "table_body_shading_color": None,   
    
    "enable_header": False,
    "enable_footer": False,
    "company_name": "aXtrLabs",
    "company_tagline": "Your Trusted Partner in Hajj and Umrah Services",
    "header_logo_path": r"C:\Users\sanje_3wfdh8z\OneDrive\Desktop\RFP\RFP-Proposal-Platform\apps\wordgen-agent\app\asserts\download.png",   # absolute or relative to project root
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


import pythoncom
from win32com.client import gencache
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("wordcom")

def build_word_from_proposal(proposal_dict, user_config, output_path, language, visible=False):
    """Create a Word docx from the labeled Arabic proposal JSON via Word COM with VERTICAL architecture diagram support."""
    import json
    if isinstance(proposal_dict, str):
        try:
            proposal_dict = json.loads(proposal_dict)
            logger.log(logging.WARNING, "⚠️ proposal_dict was str, parsed as JSON")
        except Exception as e:
            logger.error(f"❌ proposal_dict is str and not valid JSON: {e}")
            raise
    global CONFIG
    CONFIG = build_updated_config(default_CONFIG,user_config)
    native_language = language
    print(CONFIG)
    title = proposal_dict.get("title", "").strip()
    sections = proposal_dict.get("sections", [])
    logger.info(f"Generating Word doc with title: {title} and {len(sections)} sections")
    
    pythoncom.CoInitialize() 
    word = gencache.EnsureDispatch("Word.Application")  
    word.Visible = bool(visible)
    word.DisplayAlerts = 0  
    doc = None

    try:
        doc = word.Documents.Add()
        logger.debug("📄 New Word document created")

        # Page setup
        ps = doc.PageSetup
        ps.Orientation = CONFIG["orientation"]
        ps.TopMargin = CONFIG["margin_top"]
        ps.BottomMargin = CONFIG["margin_bottom"]
        ps.LeftMargin = CONFIG["margin_left"]
        ps.RightMargin = CONFIG["margin_right"]

        # Set language
        try:
            doc.Content.LanguageID = CONFIG["language_lcid"]
            logger.debug("🌐 Language applied")
        except Exception:
            logger.warning("⚠️ Failed to apply language")
            pass
        setup_header_footer(doc)
        logger.debug("🔖 Header and footer applied")

        # Title
        if title:
            add_rtl_paragraph(
                doc,
                title,
                style_name="Title",
                align=CONFIG["default_alignment"],
                font_size=CONFIG["title_font_size"],
                font_color=CONFIG.get("title_font_color", 0),
                bold=True,
            )
            logger.debug("🏷️ Title added")

        # Separator after title
        sep = doc.Paragraphs.Add()
        rtl_paragraph(sep, align=CONFIG["default_alignment"])

        # Process sections
        for i, sec in enumerate(sections):
            heading = (sec.get("heading") or "").strip()
            content = (sec.get("content") or "").strip()
            points = sec.get("points") or []
            table = sec.get("table") or {}
            headers = table.get("headers") or []
            rows = table.get("rows") or []

            logger.debug(f"Processing section {i+1}: {heading}")

            # Heading
            if heading:
                add_rtl_paragraph(
                    doc,
                    heading,
                    style_name="Heading 1",
                    align=CONFIG["default_alignment"],
                    font_size=CONFIG["heading_font_size"],
                    font_color=CONFIG.get("heading_font_color", 0),
                    bold=True,
                )

            # *** HANDLE ARCHITECTURE DIAGRAM FIRST ***
            if _handle_architecture_diagram_section(doc, sec):
                logger.info(f"✅ VERTICAL architecture diagram processed in section {i+1}")

            # Content
            if content:
                for para_text in content.split("\n"):
                    if para_text.strip():
                        add_rtl_paragraph(
                            doc,
                            para_text.strip(),
                            style_name="Normal",
                            align=CONFIG["default_alignment"],
                            font_size=CONFIG["font_size"],
                            font_color=CONFIG.get("content_font_color", 0),
                            bold=False,
                        )

            # Bullet points
            # if points:
            #     add_bullet_list(doc, points)
            if native_language == "english":

                if points:
                    logger.debug(f"Adding bullet points for section {i+1}")
                    for point in points:
                        add_rtl_paragraph(
                            doc,
                            point.strip(),
                            style_name="List Bullet",
                            align=CONFIG["default_alignment"],
                            font_size=CONFIG["font_size"],
                            font_color=CONFIG.get("content_font_color", 0),
                            bold=False,
                        )

            if native_language == "arabic":
                if points:
                    logger.debug(f"Adding bullet points for section {i+1}")
                    for point in points:
                        add_rtl_paragraph(
                            doc,
                            point.strip(),
                            # style_name="List Bullet",
                            align=CONFIG["default_alignment"],
                            font_size=CONFIG["font_size"],
                            font_color=CONFIG.get("content_font_color", 0),
                            bold=False,
                        )


            # Table
            if headers or rows:
                add_table_rtl(doc, headers, rows)

        # Save document
        output_path = str(Path(output_path).resolve())
        logger.info(f"💾 Attempting to save document: {output_path}")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        try:
            doc.SaveAs(output_path, FileFormat=WD_FORMAT_DOCX)
            logger.info(f"✅ Document saved successfully at {output_path}")
        except Exception as save_error:
            print(f"Save error: {save_error}")
            base, ext = os.path.splitext(output_path)
            counter = 1
            while counter <= 10:
                try:
                    new_path = f"{base}_{counter}{ext}"
                    doc.SaveAs(new_path, FileFormat=WD_FORMAT_DOCX)
                    output_path = new_path
                    print(f"Saved as: {output_path}")
                    logger.info(f"✅ Document saved with fallback name: {output_path}")
                    break
                except Exception:
                    counter += 1
            else:
                raise save_error
        
        return output_path
        
    finally:
        if doc:
            try:
                doc.Close(SaveChanges=False)
            except:
                pass
        try:
            word.Quit()
        except:
            pass


WD_ALIGN_LEFT = 0
WD_ALIGN_CENTER = 1
WD_ALIGN_RIGHT = 2
WD_ALIGN_JUSTIFY = 3

WD_READINGORDER_LTR = 0
WD_READINGORDER_RTL = 1

WD_LINE_SPACE_SINGLE = 0

WD_TABLE_DIRECTION_LTR = 1
WD_TABLE_DIRECTION_RTL = 2

WD_ORIENTATION_PORTRAIT = 0
WD_ORIENTATION_LANDSCAPE = 1

WD_FORMAT_DOCX = 16  
ARABIC_LCID = 1025

def is_valid_image_file(file_path):
    """Check if the file exists and is a valid image format for Word."""
    if not file_path or not os.path.exists(file_path):
        return False
    
    valid_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.tif', '.emf', '.wmf'}
    file_ext = Path(file_path).suffix.lower()
    
    if file_ext not in valid_extensions:
        return False
    
    try:
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            return False
        
        with open(file_path, 'rb') as f:
            f.read(1) 
        return True
    except Exception:
        return False


def rtl_paragraph(paragraph, align=WD_ALIGN_RIGHT):
    """Apply RTL defaults to a paragraph."""
    pf = paragraph.Format
    pf.ReadingOrder = WD_READINGORDER_RTL
    pf.Alignment = align
    pf.SpaceBefore = 0
    pf.SpaceAfter = 6
    pf.LineSpacingRule = WD_LINE_SPACE_SINGLE

def add_rtl_paragraph(doc, text, style_name=None, align=WD_ALIGN_RIGHT, font_size=None, font_color=None, bold=None):
    """Insert a paragraph with RTL formatting and an optional style."""
    para = doc.Paragraphs.Add()
    if style_name:
        try:
            para.Style = style_name
        except Exception:
            pass
    para.Range.Text = text
    rtl_paragraph(para, align=align)
    
    try:
        if font_size:
            para.Range.Font.Size = font_size
        if font_color is not None:
            para.Range.Font.Color = int(font_color)
        if bold is not None:
            para.Range.Font.Bold = 1 if bold else 0
    except Exception:
        pass
    
    para.Range.InsertParagraphAfter()
    return para


# def add_rtl_paragraph(doc, text, style_name=None, align=3, font_size=None, font_color=None, bold=None):
#     """Insert a paragraph with RTL formatting and an optional style using Word COM."""
#     para = doc.Paragraphs.Add()
    
#     # Apply the specified style
#     if style_name:
#         try:
#             para.Style = style_name
#         except Exception:
#             pass
    
#     # Set the paragraph text
#     para.Range.Text = text
    
#     # Set the paragraph alignment (for RTL, typically align = 3)
#     para.Range.ParagraphFormat.Alignment = align  # Right alignment (for RTL)

#     # Apply bullet style if style is 'List Bullet'
#     if style_name == "List Bullet":
#         para.Range.ListFormat.ApplyBulletDefault()

#     try:
#         # Set font size, color, and bold if specified
#         if font_size:
#             para.Range.Font.Size = font_size
#         if font_color is not None:
#             para.Range.Font.Color = int(font_color)
#         if bold is not None:
#             para.Range.Font.Bold = 1 if bold else 0
#     except Exception as e:
#         pass
    
#     # Ensure paragraph is added to the document
#     para.Range.InsertParagraphAfter()
#     return para



def add_bullet_list(doc, items):
    """Add a bullet list with RTL formatting."""
    if not items:
        return

    for it in items:
        p = doc.Paragraphs.Add()
        p.Range.Text = it
        rtl_paragraph(p, align=WD_ALIGN_RIGHT)
        
        try:
            p.Range.Font.Size = CONFIG["points_font_size"]
        except Exception:
            pass

    tail = doc.Paragraphs.Add()
    rtl_paragraph(tail, align=WD_ALIGN_RIGHT)

# ***Architecture Diagram Handler ***
def _handle_architecture_diagram_section(doc, section):
    """
    Handle VERTICAL architecture diagram section in Word document.
    Updated to display vertical diagrams with proper sizing.
    """
    logger = logging.getLogger("wordcom")
    
    mermaid_diagram = section.get("mermaid_diagram")
    if not mermaid_diagram:
        return False  
    
    logger.info("📊 Processing VERTICAL architecture diagram section")
    
    diagram_description = (
        "يوضح المخطط التالي الهندسة المعمارية المقترحة للنظام بتصميم عمودي يظهر طبقات النظام:"
        if "العربية" in section.get("content", "") or "هندسة" in section.get("heading", "") or "التقنية" in section.get("heading", "")
        else "The following VERTICAL diagram shows the proposed system architecture with layered design:"
    )
    
    add_rtl_paragraph(
        doc,
        diagram_description,
        style_name="Normal",
        align=WD_ALIGN_RIGHT,
        font_size=CONFIG["font_size"],
        font_color=CONFIG.get("content_font_color", 0),
        bold=False
    )
    
    # insert PNG image
    image_path = mermaid_diagram.get("image_path", "")
    image_inserted = False
    
    if image_path and os.path.exists(image_path):
        try:
            logger.info(f"🎨 Inserting VERTICAL architecture diagram: {image_path}")
            
            img_para = doc.Paragraphs.Add()
            img_range = img_para.Range
            
            inline_shape = img_range.InlineShapes.AddPicture(
                FileName=os.path.abspath(image_path),
                LinkToFile=False,
                SaveWithDocument=True
            )
            
            inline_shape.Width = 350   
            inline_shape.Height = 450  
            
            img_para.Format.Alignment = WD_ALIGN_CENTER
            img_para.Range.InsertParagraphAfter()
            
            spacer = doc.Paragraphs.Add()
            rtl_paragraph(spacer, align=WD_ALIGN_RIGHT)
            
            image_inserted = True
            logger.info("✅ VERTICAL architecture diagram image inserted successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to insert vertical diagram image: {e}")
    
    if not image_inserted:
        mermaid_code = mermaid_diagram.get("code", "")
        if mermaid_code:
            logger.info("📝 Adding VERTICAL Mermaid code as text (image insertion failed)")
            
            add_rtl_paragraph(
                doc,
                "VERTICAL Architecture Diagram Code (Mermaid):",
                style_name="Normal",
                align=WD_ALIGN_RIGHT,
                font_size=10,
                font_color=CONFIG.get("content_font_color", 0),
                bold=True
            )
            
            code_para = doc.Paragraphs.Add()
            code_para.Range.Text = mermaid_code
            rtl_paragraph(code_para, align=WD_ALIGN_LEFT) 
            
            try:
                code_para.Range.Font.Name = "Courier New"
                code_para.Range.Font.Size = 9
                code_para.Range.Font.Bold = False
            except Exception:
                pass
            
            code_para.Range.InsertParagraphAfter()
            
            spacer = doc.Paragraphs.Add()
            rtl_paragraph(spacer, align=WD_ALIGN_RIGHT)
    
    layout_note = (
        "ملاحظة: المخطط مصمم بشكل عمودي لإظهار طبقات النظام المختلفة وتدفق البيانات من الأعلى إلى الأسفل بوضوح."
        if "هندسة" in section.get("heading", "") or "التقنية" in section.get("heading", "")
        else "Note: The diagram is designed VERTICALLY to clearly show different system layers and top-to-bottom data flow."
    )
    
    add_rtl_paragraph(
        doc,
        layout_note,
        style_name="Normal",
        align=WD_ALIGN_RIGHT,
        font_size=9,
        font_color=CONFIG.get("content_font_color", 0),
        bold=False
    )
    
    return True 

def add_table_rtl(doc, headers, rows):
    """Add an RTL table with a header row aligned to the right margin."""
    if not headers and not rows:
        return  
    
    n_rows = max(1, len(rows) + (1 if headers else 0))
    n_cols = max(1, len(headers) if headers else (len(rows[0]) if rows and rows[0] else 1))

    anchor = doc.Paragraphs.Add()
    rng = anchor.Range

    table = doc.Tables.Add(rng, n_rows, n_cols)

    try:
        table.Rows.LeftIndent = 0
        page_width = doc.PageSetup.PageWidth - doc.PageSetup.LeftMargin - doc.PageSetup.RightMargin
        table.PreferredWidth = page_width
        table.PreferredWidthType = 1  

        try:
            borders = table.Borders
            preset = str(CONFIG.get("table_border_preset", "all")).lower().strip()
            visible = bool(CONFIG.get("table_border_visible", True))

            if visible and preset != "none":
                # Set border properties
                style = CONFIG.get("table_border_line_style", 1)  # 1 = wdLineStyleSingle
                color = int(CONFIG.get("table_border_color", 0))  # 0 = black
                width = CONFIG.get("table_border_line_width", 1)  # 1 = safe value

                borders.Enable = 1
                borders.OutsideLineStyle = style
                borders.OutsideColor = color
                
                if preset in ("all", "grid"):
                    borders.InsideLineStyle = style
                    borders.InsideColor = color
                else:  
                    borders.InsideLineStyle = 0  
                
                try:
                    borders.Shadow = 0
                except Exception:
                    pass
                    
            else:
                borders.Enable = 0
                borders.OutsideLineStyle = 0
                borders.InsideLineStyle = 0
                
        except Exception as e:
            print(f"Border configuration error: {e}")
            pass
    except Exception as e:
        print(f"Table setup error: {e}")
        pass

    current_row = 1
    if headers:
        for c, h in enumerate(headers, start=1):
            if c <= n_cols:
                cell = table.Cell(current_row, c)
                cell.Range.Text = str(h)
                cell.Range.ParagraphFormat.ReadingOrder = WD_READINGORDER_RTL
                cell.Range.ParagraphFormat.Alignment = WD_ALIGN_CENTER
                cell.Range.Bold = True
                try:
                    cell.Range.Font.Size = CONFIG["table_font_size"]
                    cell.Range.Font.Color = int(CONFIG.get("table_font_color", 0))
                    header_shade = CONFIG.get("table_header_shading_color")
                    if header_shade is not None:
                        cell.Shading.BackgroundPatternColor = int(header_shade)
                except Exception:
                    pass
        current_row += 1

    for row in rows:
        if current_row <= n_rows: 
            for c, val in enumerate(row[:n_cols], start=1):
                if c <= n_cols:
                    cell = table.Cell(current_row, c)
                    cell.Range.Text = str(val)
                    cell.Range.ParagraphFormat.ReadingOrder = WD_READINGORDER_RTL
                    cell.Range.ParagraphFormat.Alignment = WD_ALIGN_CENTER
                    try:
                        cell.Range.Font.Size = CONFIG["table_font_size"]
                        cell.Range.Font.Color = int(CONFIG.get("table_font_color", 0))
                        body_shade = CONFIG.get("table_body_shading_color")
                        if body_shade is not None:
                            cell.Shading.BackgroundPatternColor = int(body_shade)
                    except Exception:
                        pass
            current_row += 1

    try:
        table.AutoFitBehavior(2)  
    except Exception:
        pass

    tail = doc.Paragraphs.Add()
    rtl_paragraph(tail, align=WD_ALIGN_RIGHT)

def setup_header_footer(doc):
    """Set up header and footer before adding content."""
    try:
        if CONFIG.get("enable_header"):
            section = doc.Sections(1)
            header = section.Headers(1)  
            headerRange = header.Range
            headerRange.ParagraphFormat.ReadingOrder = WD_READINGORDER_RTL
            headerRange.ParagraphFormat.Alignment = WD_ALIGN_RIGHT

            headerTable = headerRange.Tables.Add(headerRange, 1, 2)
            try:
                headerTable.Rows.LeftIndent = 0
                page_width = doc.PageSetup.PageWidth - doc.PageSetup.LeftMargin - doc.PageSetup.RightMargin
                headerTable.PreferredWidth = page_width
                headerTable.PreferredWidthType = 1
                headerTable.Borders.Enable = 0
            except Exception:
                pass

            leftCell = headerTable.Cell(1, 1)
            company_text = CONFIG.get("company_name", "").strip()
            tagline = CONFIG.get("company_tagline", "").strip()
            if tagline:
                company_text += f"\n{tagline}"
            leftCell.Range.Text = company_text
            
            try:
                leftCell.Range.ParagraphFormat.ReadingOrder = WD_READINGORDER_RTL
                leftCell.Range.ParagraphFormat.Alignment = WD_ALIGN_LEFT
                leftCell.Range.Font.Bold = 1
                leftCell.Range.Font.Size = CONFIG.get("heading_font_size", 16)
            except Exception:
                pass

            rightCell = headerTable.Cell(1, 2)
            rc_range = rightCell.Range
            try:
                rc_range.ParagraphFormat.ReadingOrder = WD_READINGORDER_RTL
                rc_range.ParagraphFormat.Alignment = WD_ALIGN_RIGHT
                rc_range.ParagraphFormat.SpaceAfter = 0
            except Exception:
                pass

            logo_path = CONFIG.get("header_logo_path", "").strip()
            if logo_path and os.path.exists(logo_path):
                try:
                    rc_range.Collapse(1)

                    pic = rc_range.InlineShapes.AddPicture(
                        FileName=str(Path(logo_path).resolve()),
                        LinkToFile=False,
                        SaveWithDocument=True,
                    )
                    try:
                        pic.LockAspectRatio = True
                    except Exception:
                        pass
                    cur_w = float(pic.Width)
                    cur_h = float(pic.Height)
                    w = CONFIG.get("header_logo_width")
                    h = CONFIG.get("header_logo_height")
                    explicit_w = CONFIG.get("header_logo_width")
                    explicit_h = CONFIG.get("header_logo_height")
                    if explicit_w or explicit_h:
                        if explicit_w: pic.Width  = int(explicit_w)
                        if explicit_h: pic.Height = int(explicit_h)
                    else:
                        max_w = float(CONFIG.get("header_logo_max_width", 120))
                        max_h = float(CONFIG.get("header_logo_max_height", 60))
                        if cur_w > 0 and cur_h > 0:
                            scale = min(max_w / cur_w, max_h / cur_h, 1.0)
                            if scale < 1.0:
                                pic.Width  = int(cur_w * scale)
                                pic.Height = int(cur_h * scale)

                    rc_range.ParagraphFormat.Alignment = WD_ALIGN_RIGHT

                except Exception as e:
                    print(f"Logo insertion error: {e}")
            else:
                rc_range.Text = " "

        if CONFIG.get("enable_footer"):
            section = doc.Sections(1)
            footer = section.Footers(1)  
            fr = footer.Range
            fr.ParagraphFormat.ReadingOrder = WD_READINGORDER_RTL
            fr.ParagraphFormat.Alignment = WD_ALIGN_RIGHT

            ftable = fr.Tables.Add(fr, 1, 3)
            try:
                ftable.Rows.LeftIndent = 0
                page_width = doc.PageSetup.PageWidth - doc.PageSetup.LeftMargin - doc.PageSetup.RightMargin
                ftable.PreferredWidth = page_width
                ftable.PreferredWidthType = 1
                ftable.Borders.Enable = 0
            except Exception:
                pass

            try:
                ftable.Cell(1, 1).Range.Text = CONFIG.get("footer_left_text", "")
                ftable.Cell(1, 1).Range.ParagraphFormat.ReadingOrder = WD_READINGORDER_RTL
                ftable.Cell(1, 1).Range.ParagraphFormat.Alignment = WD_ALIGN_LEFT
            except Exception:
                pass

            try:
                centerRange = ftable.Cell(1, 2).Range
                centerRange.ParagraphFormat.ReadingOrder = WD_READINGORDER_RTL
                centerRange.ParagraphFormat.Alignment = WD_ALIGN_CENTER
                if CONFIG.get("footer_show_page_numbers", True):
                    centerRange.Fields.Add(centerRange, Type=33)  
                    centerRange.InsertAfter(" / ")
                    centerRange.Collapse(0) 
                    centerRange.Fields.Add(centerRange, Type=34)  
                elif CONFIG.get("footer_center_text"):
                    centerRange.Text = CONFIG.get("footer_center_text")
            except Exception:
                pass
            try:
                ftable.Cell(1, 3).Range.Text = CONFIG.get("footer_right_text", "")
                ftable.Cell(1, 3).Range.ParagraphFormat.ReadingOrder = WD_READINGORDER_RTL
                ftable.Cell(1, 3).Range.ParagraphFormat.Alignment = WD_ALIGN_RIGHT
            except Exception:
                pass

    except Exception as e:
        print(f"Header/Footer setup error: {e}")

