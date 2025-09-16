import json
import logging
import os
from pathlib import Path


try:
    import win32com.client as win32
except Exception as e:
    raise RuntimeError("win32com is required. Install with: pip install pywin32") from e


CONFIG = {
    "visible_word": False,         # Show Word UI while generating?
    "output_path": "output/proposal.docx",

    # Language and text direction
    "language_lcid": 1025,         # Arabic (Saudi Arabia)
    "default_alignment": 2,        # WD_ALIGN_RIGHT
    "reading_order": 1,            # WD_READINGORDER_RTL

    # Paragraph spacing
    "space_before": 0,
    "space_after": 6,
    "line_spacing_rule": 0,        # WD_LINE_SPACE_SINGLE

    # Page setup
    "orientation": 0,              # WD_ORIENTATION_PORTRAIT
    "margin_top": 72,              # 1 inch = 72 points
    "margin_bottom": 72,
    "margin_left": 72,
    "margin_right": 72,

    # Table settings
    "table_autofit": True,
    "table_preferred_width": None, # None = auto (or set numeric points)

    # Styles
    "title_style": "Title",
    "heading_style": "Heading 1",
    "normal_style": "Normal",
    "font_size": 14,         # default body size (matches sample_config.txt)
    "heading_font_size": 16, # heading size (matches sample_config.txt)
    "title_font_size": 20,
    "points_font_size": 14,  # bullet points size (matches body text)
    "table_font_size": 12,   # table content size (slightly smaller than body)

    # Colors (WdColor integer). Default to black.
    "title_font_color": 0,
    "heading_font_color": 0,
    "content_font_color": 0,

    # Table style configuration - SAFE VALUES
    "table_font_color": 0,            # text color in table cells (WdColor)
    "table_border_visible": True,     # show borders
    "table_border_color": 0,          # 0 = black
    "table_border_line_style": 1,     # 1 = wdLineStyleSingle
    "table_border_line_width": 1,     # CHANGED: 1 = safe value (was 3)
    "table_border_preset": "all",     # one of: none | box | all | grid
    "table_header_shading_color": None, # e.g., 12632256 (light gray) or None
    "table_body_shading_color": None,   # None by default
    
    # Header/Footer controls
    "enable_header": False,
    "enable_footer": False,
    # Header content
    "company_name": "aXtrLabs",
    "company_tagline": "Your Trusted Partner in Hajj and Umrah Services",
    "header_logo_path": r"C:\Users\sanje_3wfdh8z\OneDrive\Desktop\RFP\RFP-Proposal-Platform\apps\wordgen-agent\app\asserts\download.png",   # absolute or relative to project root
    "header_logo_width": 5,    # points
    "header_logo_height": 2, # keep aspect if None
    "header_logo_max_width": 120,   # ~1.67 in
    "header_logo_max_height": 60, 
    "header_padding": 6,        # points of spacing after header
    # Footer content
    "footer_left_text": "",
    "footer_center_text": "",
    "footer_right_text": "",
    "footer_show_page_numbers": True,
    "footer_padding": 6,
}

# ---- Minimal Word constants (avoid makepy dependency) ----
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

WD_FORMAT_DOCX = 16  # wdFormatXMLDocument

# Common LCIDs: Arabic (Saudi Arabia) = 1025, Arabic (UAE) = 14337, Arabic (Egypt) = 3073
ARABIC_LCID = 1025


def is_valid_image_file(file_path):
    """Check if the file exists and is a valid image format for Word."""
    if not file_path or not os.path.exists(file_path):
        return False
    
    # Check file extension
    valid_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.tif', '.emf', '.wmf'}
    file_ext = Path(file_path).suffix.lower()
    
    if file_ext not in valid_extensions:
        return False
    
    # Check if file is readable and not empty
    try:
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            return False
        
        # Try to open the file to ensure it's accessible
        with open(file_path, 'rb') as f:
            f.read(1)  # Try to read first byte
        return True
    except Exception:
        return False

print(is_valid_image_file(CONFIG.get("header_logo_path")))


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


def add_bullet_list(doc, items):
    """Add a bullet list with RTL formatting."""
    if not items:
        return

    # Create the first paragraph then apply bullet format, then append the rest
    for it in items:
        p = doc.Paragraphs.Add()
        p.Range.Text = it
        rtl_paragraph(p, align=WD_ALIGN_RIGHT)
        
        # Apply font size to bullet points
        try:
            p.Range.Font.Size = CONFIG["points_font_size"]
        except Exception:
            pass

    # Add spacing after the list
    tail = doc.Paragraphs.Add()
    rtl_paragraph(tail, align=WD_ALIGN_RIGHT)



def add_table_rtl(doc, headers, rows):
    """Add an RTL table with a header row aligned to the right margin."""
    n_rows = max(1, len(rows) + (1 if headers else 0))
    n_cols = max(1, len(headers) if headers else (len(rows[0]) if rows else 1))

    # Insert an empty paragraph as insertion point
    anchor = doc.Paragraphs.Add()
    rng = anchor.Range

    table = doc.Tables.Add(rng, n_rows, n_cols)

    try:
        # Remove table.Direction - this property doesn't exist
        table.Rows.LeftIndent = 0
        page_width = doc.PageSetup.PageWidth - doc.PageSetup.LeftMargin - doc.PageSetup.RightMargin
        table.PreferredWidth = page_width
        table.PreferredWidthType = 1  

        # Apply border configuration - FIXED VERSION
        try:
            borders = table.Borders
            preset = str(CONFIG.get("table_border_preset", "all")).lower().strip()
            visible = bool(CONFIG.get("table_border_visible", True))

            if visible and preset != "none":
                # Set border properties
                style = CONFIG.get("table_border_line_style", 1)  # 1 = wdLineStyleSingle
                color = int(CONFIG.get("table_border_color", 0))  # 0 = black (changed from -16777216)
                width = CONFIG.get("table_border_line_width", 3)  # 3 = wdLineWidth050pt

                # Enable borders first
                borders.Enable = 1
                
                # Set outline properties (applies to all outer borders)
                borders.OutsideLineStyle = style
                borders.OutsideColor = color
                
                # Set inside properties based on preset
                if preset in ("all", "grid"):
                    borders.InsideLineStyle = style
                    borders.InsideColor = color
                else:  # "box" - no inside borders
                    borders.InsideLineStyle = 0  # No inside borders
                
                # Disable shadow
                try:
                    borders.Shadow = 0
                except Exception:
                    pass
                    
            else:
                # No borders
                borders.Enable = 0
                borders.OutsideLineStyle = 0
                borders.InsideLineStyle = 0
                
        except Exception as e:
            print(f"Border configuration error: {e}")
            pass
    except Exception as e:
        print(f"Table setup error: {e}")
        pass

    # Fill header
    current_row = 1
    if headers:
        for c, h in enumerate(headers, start=1):
            cell = table.Cell(current_row, c)
            cell.Range.Text = str(h)
            cell.Range.ParagraphFormat.ReadingOrder = WD_READINGORDER_RTL
            cell.Range.ParagraphFormat.Alignment = WD_ALIGN_CENTER
            cell.Range.Bold = True
            # Apply font size to table headers
            try:
                cell.Range.Font.Size = CONFIG["table_font_size"]
                # Text color
                cell.Range.Font.Color = int(CONFIG.get("table_font_color", 0))
                # Header shading if configured
                header_shade = CONFIG.get("table_header_shading_color")
                if header_shade is not None:
                    cell.Shading.BackgroundPatternColor = int(header_shade)
            except Exception:
                pass
        current_row += 1

    # Fill body
    for row in rows:
        for c, val in enumerate(row[:n_cols], start=1):
            cell = table.Cell(current_row, c)
            cell.Range.Text = str(val)
            cell.Range.ParagraphFormat.ReadingOrder = WD_READINGORDER_RTL
            cell.Range.ParagraphFormat.Alignment = WD_ALIGN_RIGHT
            # Apply font size to table content
            try:
                cell.Range.Font.Size = CONFIG["table_font_size"]
                # Text color
                cell.Range.Font.Color = int(CONFIG.get("table_font_color", 0))
                # Body shading if configured
                body_shade = CONFIG.get("table_body_shading_color")
                if body_shade is not None:
                    cell.Shading.BackgroundPatternColor = int(body_shade)
            except Exception:
                pass
        current_row += 1

    # Autofit but keep width
    try:
        table.AutoFitBehavior(2)  # wdAutoFitWindow
    except Exception:
        pass

    # Space after table
    tail = doc.Paragraphs.Add()
    rtl_paragraph(tail, align=WD_ALIGN_RIGHT)



def setup_header_footer(doc):
    """Set up header and footer before adding content."""
    try:
        if CONFIG.get("enable_header"):
            section = doc.Sections(1)
            header = section.Headers(1)  # wdHeaderFooterPrimary
            headerRange = header.Range
            headerRange.ParagraphFormat.ReadingOrder = WD_READINGORDER_RTL
            headerRange.ParagraphFormat.Alignment = WD_ALIGN_RIGHT

            # Create header table
            headerTable = headerRange.Tables.Add(headerRange, 1, 2)
            try:
                headerTable.Rows.LeftIndent = 0
                page_width = doc.PageSetup.PageWidth - doc.PageSetup.LeftMargin - doc.PageSetup.RightMargin
                headerTable.PreferredWidth = page_width
                headerTable.PreferredWidthType = 1
                headerTable.Borders.Enable = 0
            except Exception:
                pass

            # Company name/tagline
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

            # # Logo
            # rightCell = headerTable.Cell(1, 2)
            # rightCell.Range.ParagraphFormat.ReadingOrder = WD_READINGORDER_RTL
            # rightCell.Range.ParagraphFormat.Alignment = WD_ALIGN_RIGHT
            # logo_path = CONFIG.get("header_logo_path", "").strip()
            # if logo_path and os.path.exists(logo_path):
            #     try:
            #         img_shape = rightCell.Range.InlineShapes.AddPicture(
            #             FileName=str(Path(logo_path).resolve()), 
            #             LinkToFile=False, 
            #             SaveWithDocument=True
            #         )
            #         if CONFIG.get("header_logo_width"):
            #             img_shape.Width = CONFIG.get("header_logo_width")
            #         if CONFIG.get("header_logo_height"):
            #             img_shape.Height = CONFIG.get("header_logo_height")
            #     except Exception as e:
            #         print(f"Logo insertion error: {e}")


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
                    # Collapse range before inserting the picture
                    # 1 = wdCollapseStart (we're not importing makepy constants, so use literal)
                    rc_range.Collapse(1)

                    pic = rc_range.InlineShapes.AddPicture(
                        FileName=str(Path(logo_path).resolve()),
                        LinkToFile=False,
                        SaveWithDocument=True,
                    )

                    # Optional, safer sizing AFTER insertion
                    try:
                        # Lock aspect if you plan to set only one dimension
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
                # Ensure cell isn't empty (Word sometimes dislikes truly empty ranges)
                rc_range.Text = " "


        # Footer
        if CONFIG.get("enable_footer"):
            section = doc.Sections(1)
            footer = section.Footers(1)  # wdHeaderFooterPrimary
            fr = footer.Range
            fr.ParagraphFormat.ReadingOrder = WD_READINGORDER_RTL
            fr.ParagraphFormat.Alignment = WD_ALIGN_RIGHT

            # Footer table
            ftable = fr.Tables.Add(fr, 1, 3)
            try:
                ftable.Rows.LeftIndent = 0
                page_width = doc.PageSetup.PageWidth - doc.PageSetup.LeftMargin - doc.PageSetup.RightMargin
                ftable.PreferredWidth = page_width
                ftable.PreferredWidthType = 1
                ftable.Borders.Enable = 0
            except Exception:
                pass

            # Left footer text
            try:
                ftable.Cell(1, 1).Range.Text = CONFIG.get("footer_left_text", "")
                ftable.Cell(1, 1).Range.ParagraphFormat.ReadingOrder = WD_READINGORDER_RTL
                ftable.Cell(1, 1).Range.ParagraphFormat.Alignment = WD_ALIGN_LEFT
            except Exception:
                pass

            # Center - page numbers or text
            try:
                centerRange = ftable.Cell(1, 2).Range
                centerRange.ParagraphFormat.ReadingOrder = WD_READINGORDER_RTL
                centerRange.ParagraphFormat.Alignment = WD_ALIGN_CENTER
                if CONFIG.get("footer_show_page_numbers", True):
                    centerRange.Fields.Add(centerRange, Type=33)  # wdFieldPage
                    centerRange.InsertAfter(" / ")
                    centerRange.Collapse(0)  # wdCollapseEnd
                    centerRange.Fields.Add(centerRange, Type=34)  # wdFieldNumPages
                elif CONFIG.get("footer_center_text"):
                    centerRange.Text = CONFIG.get("footer_center_text")
            except Exception:
                pass

            # Right footer text
            try:
                ftable.Cell(1, 3).Range.Text = CONFIG.get("footer_right_text", "")
                ftable.Cell(1, 3).Range.ParagraphFormat.ReadingOrder = WD_READINGORDER_RTL
                ftable.Cell(1, 3).Range.ParagraphFormat.Alignment = WD_ALIGN_RIGHT
            except Exception:
                pass

    except Exception as e:
        print(f"Header/Footer setup error: {e}")



import pythoncom
from win32com.client import gencache
import logging


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("wordcom")


def build_word_from_proposal(proposal_dict, output_path="proposal69.docx", visible=False):
    """Create a Word docx from the labeled Arabic proposal JSON via Word COM."""
    import json

    # Handle case where proposal_dict is accidentally a string
    if isinstance(proposal_dict, str):
        try:
            proposal_dict = json.loads(proposal_dict)
            logger.log(logging.WARNING, "⚠️ proposal_dict was str, parsed as JSON")
        except Exception as e:
            logger.error(f"❌ proposal_dict is str and not valid JSON: {e}")
            raise

    title = proposal_dict.get("title", "").strip()
    sections = proposal_dict.get("sections", [])
    logger.info(f"Generating Word doc with title: {title} and {len(sections)} sections")
    
    pythoncom.CoInitialize()  # <-- important
    word = gencache.EnsureDispatch("Word.Application")  # <-- safer than Dispatch
    word.Visible = bool(visible)
    word.DisplayAlerts = 0  # <-- avoid UI prompts that can break COM ops
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

        # Setup header and footer BEFORE adding content
        setup_header_footer(doc)
        logger.debug("🔖 Header and footer applied")

        # Title
        if title:
            add_rtl_paragraph(
                doc,
                title,
                style_name="Title",
                align=WD_ALIGN_RIGHT,
                font_size=CONFIG["title_font_size"],
                font_color=CONFIG.get("title_font_color", 0),
                bold=True,
            )
            logger.debug("🏷️ Title added")

        # Separator after title
        sep = doc.Paragraphs.Add()
        rtl_paragraph(sep, align=WD_ALIGN_RIGHT)

        # Process sections
        for sec in sections:
            heading = (sec.get("heading") or "").strip()
            content = (sec.get("content") or "").strip()
            points = sec.get("points") or []
            table = sec.get("table") or {}
            headers = table.get("headers") or []
            rows = table.get("rows") or []

            # Heading
            if heading:
                add_rtl_paragraph(
                    doc,
                    heading,
                    style_name="Heading 1",
                    align=WD_ALIGN_RIGHT,
                    font_size=CONFIG["heading_font_size"],
                    font_color=CONFIG.get("heading_font_color", 0),
                    bold=True,
                )

            # Content
            if content:
                for para_text in content.split("\n"):
                    if para_text.strip():
                        add_rtl_paragraph(
                            doc,
                            para_text.strip(),
                            style_name="Normal",
                            align=WD_ALIGN_RIGHT,
                            font_size=CONFIG["font_size"],
                            font_color=CONFIG.get("content_font_color", 0),
                            bold=False,
                        )

            # Bullet points
            if points:
                add_bullet_list(doc, points)

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
            # Try with different filename
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
        # Always clean up
        if doc:
            try:
                doc.Close(SaveChanges=False)
            except:
                pass
        try:
            word.Quit()
        except:
            pass











# if __name__ == "__main__":

#     example_json = {
#   "title": "مقترح شامل للرد على طلب العروض (RFP)",
#   "sections": [
#     {
#       "heading": "مقدمة",
#       "content": "يسر [اسم الشركة] أن تقدم هذا المقترح استجابة لطلب العروض المقدم من الجهة الحكومية بشأن مشروع تطوير معايير وظيفية للعاملين في مجال خدمة ضيوف الرحمن. يهدف هذا المقترح إلى توضيح النهج المتبع وآليات التنفيذ والقدرات الفنية والإدارية التي تمتلكها الشركة لضمان نجاح المشروع.",
#       "points": [
#         "تعريف المنافسة وأهدافها",
#         "المواعيد الرئيسية للتقديم والتنفيذ",
#         "شروط أهلية مقدمي العروض"
#       ],
#       "table": {
#         "headers": ["المصطلح", "التعريف"],
#         "rows": [
#           ["الجهة الحكومية", "الجهة المسؤولة عن طرح المنافسة ومتابعة التنفيذ"],
#           ["مقدم العرض", "الشركة أو الكيان المتقدم للمنافسة"],
#           ["المنافسة", "العملية التنافسية التي يتم عبرها تقديم وتقييم العروض"],
#           ["الخدمات", "النطاق المطلوب تنفيذه وفقًا لشروط RFP"]
#         ]
#       }
#     },
#     {
#       "heading": "الأحكام العامة",
#       "content": "تلتزم [اسم الشركة] بأعلى معايير النزاهة والشفافية في جميع مراحل المنافسة والتنفيذ، بما يضمن مبدأ تكافؤ الفرص لجميع الأطراف المشاركة.",
#       "points": [
#         "ضمان المساواة والشفافية",
#         "الإفصاح عن أي تعارض محتمل في المصالح",
#         "التقيد بالسلوكيات والأخلاقيات المهنية"
#       ],
#       "table": {
#         "headers": ["المبدأ", "التفاصيل"],
#         "rows": [
#           ["المساواة", "المعاملة العادلة لجميع المتنافسين دون استثناء"],
#           ["الشفافية", "توفير المعلومات الكاملة والدقيقة للجهة الحكومية"],
#           ["تعارض المصالح", "الإفصاح المبكر عن أي مواقف قد تؤثر على الحياد"],
#           ["الأخلاقيات", "اتباع معايير أخلاقية ومهنية في جميع مراحل المشروع"]
#         ]
#       }
#     },
#     {
#       "heading": "إعداد العروض",
#       "content": "يتم إعداد العروض وفق منهجية تضمن وضوح البيانات ودقتها بما يحقق أهداف المنافسة. تم تحديد مدة صلاحية العرض بـ 90 يومًا من تاريخ فتح المظاريف لضمان الالتزام الكامل.",
#       "points": [
#         "تأكيد نية المشاركة في المنافسة",
#         "اللغة المعتمدة لتقديم العرض",
#         "وثائق العرض الفني والمالي"
#       ],
#       "table": {
#         "headers": ["البند", "التفاصيل"],
#         "rows": [
#           ["اللغة", "العرض مقدم باللغة العربية مع إمكانية توفير نسخة باللغة الإنجليزية إذا طلبت"],
#           ["مدة الصلاحية", "90 يومًا من تاريخ فتح المظاريف"],
#           ["الوثائق الفنية", "منهجية التنفيذ وخطة العمل والهيكل التنظيمي للفريق"],
#           ["الوثائق المالية", "جداول التكاليف التفصيلية وخطط الدفع"]
#         ]
#       }
#     },
#     {
#       "heading": "تقديم العروض",
#       "content": "سيتم تقديم العروض عبر المنصة الإلكترونية الرسمية (اعتماد)، مع الالتزام بتسليم الضمان الابتدائي المنصوص عليه ضمن شروط المنافسة.",
#       "points": [
#         "آلية تقديم العروض عبر المنصة",
#         "آلية فتح المظاريف بحضور ممثلين"
#       ],
#       "table": {
#         "headers": ["الإجراء", "التفاصيل"],
#         "rows": [
#           ["تقديم العروض", "رفع جميع الملفات المطلوبة عبر منصة اعتماد"],
#           ["الضمان الابتدائي", "تقديم ضمان بنكي بنسبة محددة حسب شروط المنافسة"],
#           ["فتح العروض", "إجراء فتح المظاريف بحضور لجنة مختصة وممثلين عن الجهة الحكومية"]
#         ]
#       }
#     },
#     {
#       "heading": "تقييم العروض",
#       "content": "تعتمد عملية التقييم على معايير فنية ومالية واضحة، بما يضمن اختيار أفضل عرض يحقق الجودة والتكلفة المثلى.",
#       "points": [
#         "آلية التقييم الفني",
#         "معايير التقييم المالي",
#         "آلية تصحيح الأخطاء في العروض"
#       ],
#       "table": {
#         "headers": ["المعيار", "التفاصيل"],
#         "rows": [
#           ["المعيار الفني", "يشمل الخبرة السابقة، الكفاءات البشرية، ومنهجية التنفيذ"],
#           ["المعيار المالي", "يشمل ملاءمة الأسعار ومطابقتها للتكلفة التقديرية"],
#           ["آلية التصحيح", "مراجعة أي أخطاء حسابية وإبلاغ مقدم العرض بها"]
#         ]
#       }
#     },
#     {
#       "heading": "متطلبات التعاقد",
#       "content": "عند إرساء العقد، ستقوم الجهة الحكومية بإخطار الفائز رسميًا عبر البوابة الإلكترونية، مع تحديد النطاق الزمني والمالي بدقة.",
#       "points": [
#         "إشعار الترسية عبر المنصة",
#         "تقديم الضمان النهائي",
#         "بدء التنفيذ وفق الجدول"
#       ],
#       "table": {
#         "headers": ["البند", "التفاصيل"],
#         "rows": [
#           ["إشعار الترسية", "إرسال خطاب رسمي عبر البوابة الإلكترونية"],
#           ["الضمان النهائي", "5% من قيمة العقد الإجمالية"],
#           ["بداية التنفيذ", "بعد اعتماد العقد وتوقيعه من جميع الأطراف"]
#         ]
#       }
#     },
#     {
#       "heading": "نطاق العمل المفصل",
#       "content": "يتضمن نطاق العمل مراحل متتابعة تبدأ بالتخطيط وتنتهي بالتنفيذ والتقييم، لضمان إنجاز المشروع بكفاءة وجودة عالية.",
#       "points": [
#         "مرحلة التخطيط",
#         "مرحلة التحليل",
#         "مرحلة التنفيذ",
#         "مرحلة التقييم"
#       ],
#       "table": {
#         "headers": ["المرحلة", "التفاصيل"],
#         "rows": [
#           ["التخطيط", "تحديد الأهداف، تشكيل الفريق، ووضع الجدول الزمني"],
#           ["التحليل", "دراسة الوظائف والمهام الحالية وتحليل الاحتياجات"],
#           ["التنفيذ", "إعداد الوصف الوظيفي، تطوير البرامج التدريبية"],
#           ["التقييم", "قياس الأداء وفق مؤشرات محددة وإصدار تقارير شاملة"]
#         ]
#       }
#     },
#     {
#       "heading": "المواصفات",
#       "content": "سيتم توفير فريق متكامل من الخبراء والمستشارين ذوي الكفاءة العالية، لضمان تطبيق أفضل الممارسات العالمية.",
#       "points": [
#         "فريق عمل متعدد التخصصات",
#         "المنهجية المعتمدة في التنفيذ"
#       ],
#       "table": {
#         "headers": ["البند", "التفاصيل"],
#         "rows": [
#           ["فريق العمل", "يشمل خبراء في إدارة المشاريع، التدريب، والتطوير المؤسسي"],
#           ["منهجية التنفيذ", "تعتمد على خطوات منظمة (تخطيط – تنفيذ – متابعة – تقييم)"]
#         ]
#       }
#     },
#     {
#       "heading": "الشروط الخاصة",
#       "content": "تلتزم الشركة بتقديم جميع المخرجات في المواعيد المحددة مع ضمان الجودة العالية.",
#       "points": [
#         "الالتزام بالجدول الزمني",
#         "تقديم تقارير دورية",
#         "جودة المخرجات"
#       ],
#       "table": {
#         "headers": ["البند", "التفاصيل"],
#         "rows": [
#           ["المخرجات", "إعداد وتسليم الوثائق وفق الجدول المتفق عليه"],
#           ["التقارير", "تقارير شهرية وربع سنوية ترفع للجهة الحكومية"],
#           ["الجودة", "تطبيق معايير ضبط الجودة ISO 9001"]
#         ]
#       }
#     },
#     {
#       "heading": "خطة إدارة المشروع",
#       "content": "تعتمد خطة إدارة المشروع على نظام متكامل لإدارة المخاطر، وضمان الالتزام بمؤشرات الأداء الرئيسية لتحقيق النجاح.",
#       "points": [
#         "تحليل المخاطر المحتملة",
#         "إجراءات التخفيف من المخاطر",
#         "مؤشرات الأداء الرئيسية"
#       ],
#       "table": {
#         "headers": ["البند", "التفاصيل"],
#         "rows": [
#           ["تحليل المخاطر", "تحديد المخاطر المتعلقة بالوقت والميزانية والجودة"],
#           ["إجراءات التخفيف", "خطة بديلة للتنفيذ في حال حدوث تأخير أو عوائق"],
#           ["مؤشرات الأداء", "KPIs تشمل الإنجاز الزمني، جودة المخرجات، ورضا المستفيدين"]
#         ]
#       }
#     }
#   ]
# }


#     json_path = Path("input.json")
#     if json_path.exists():
#         with open(json_path, "r", encoding="utf-8") as f:
#             proposal = json.load(f)
#     else:
#         proposal = example_json  # fallback to inline

#     out = build_word_from_proposal(proposal, output_path="output/proposal69.docx", visible=False)
#     print(f"✅ Word document created: {out}")
