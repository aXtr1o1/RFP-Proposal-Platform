import json
import os
from pathlib import Path

# --- Word COM (requires Windows + MS Word installed) ---
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


def rtl_paragraph(paragraph, align=WD_ALIGN_RIGHT):
    """Apply RTL defaults to a paragraph."""
    pf = paragraph.Format
    pf.ReadingOrder = WD_READINGORDER_RTL
    pf.Alignment = align
    pf.SpaceBefore = 0
    pf.SpaceAfter = 6
    pf.LineSpacingRule = WD_LINE_SPACE_SINGLE


def add_rtl_paragraph(doc, text, style_name=None, align=WD_ALIGN_RIGHT, font_size=None):
    """Insert a paragraph with RTL formatting and an optional style."""
    para = doc.Paragraphs.Add()
    if style_name:
        try:
            para.Style = style_name
        except Exception:
            # Fallback if style not found
            pass
    para.Range.Text = text
    rtl_paragraph(para, align=align)
    
    # Apply font size if specified
    if font_size:
        try:
            para.Range.Font.Size = font_size
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
        table.Direction = WD_TABLE_DIRECTION_RTL
        table.Rows.LeftIndent = 0
        page_width = doc.PageSetup.PageWidth - doc.PageSetup.LeftMargin - doc.PageSetup.RightMargin
        table.PreferredWidth = page_width
        table.PreferredWidthType = 1  
    except Exception:
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



def build_word_from_proposal(proposal_dict, output_path="proposal.docx", visible=False):
    

    
    """Create a Word docx from the labeled Arabic proposal JSON via Word COM."""
    title = proposal_dict.get("title", "").strip()
    sections = proposal_dict.get("sections", [])

    word = win32.Dispatch("Word.Application")
    word.Visible = bool(visible)
    doc = word.Documents.Add()

    # Page setup (portrait, normal margins)
    ps = doc.PageSetup
    ps.Orientation = CONFIG["orientation"]
    ps.TopMargin = CONFIG["margin_top"]
    ps.BottomMargin = CONFIG["margin_bottom"]
    ps.LeftMargin = CONFIG["margin_left"]
    ps.RightMargin = CONFIG["margin_right"]

    # Optional: set proofing language for the whole doc (if available)
    try:
        doc.Content.LanguageID = CONFIG["language_lcid"]
    except Exception:
        pass

    # Title (use built-in Title style if present; align right, RTL)
    if title:
        add_rtl_paragraph(doc, title, style_name="Title", align=WD_ALIGN_RIGHT, font_size=CONFIG["title_font_size"])

    # Thin separator after title
    sep = doc.Paragraphs.Add()
    rtl_paragraph(sep, align=WD_ALIGN_RIGHT)

    # Sections
    for sec in sections:
        heading = (sec.get("heading") or "").strip()
        content = (sec.get("content") or "").strip()
        points = sec.get("points") or []
        table = sec.get("table") or {}
        headers = table.get("headers") or []
        rows = table.get("rows") or []

        # Heading (use Heading 1)
        if heading:
            add_rtl_paragraph(doc, heading, style_name="Heading 1", align=WD_ALIGN_RIGHT, font_size=CONFIG["heading_font_size"])

        # Content
        if content:
            # Split to short paragraphs for better layout
            for para_text in content.split("\n"):
                if para_text.strip():
                    add_rtl_paragraph(doc, para_text.strip(), style_name="Normal", align=WD_ALIGN_RIGHT, font_size=CONFIG["font_size"])

        # Bullets
        if points:
            add_bullet_list(doc, points)
            print("points:", points)

        # Table
        if headers or rows:
            add_table_rtl(doc, headers, rows)

    # Save
    output_path = str(Path(output_path).resolve())
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc.SaveAs(output_path, FileFormat=WD_FORMAT_DOCX)
    doc.Close(SaveChanges=False)
    word.Quit()

    return output_path


if __name__ == "__main__":

    example_json = {
  "title": "مقترح شامل للرد على طلب العروض (RFP)",
  "sections": [
    {
      "heading": "مقدمة",
      "content": "يسر [اسم الشركة] أن تقدم هذا المقترح استجابة لطلب العروض المقدم من الجهة الحكومية بشأن مشروع تطوير معايير وظيفية للعاملين في مجال خدمة ضيوف الرحمن. يهدف هذا المقترح إلى توضيح النهج المتبع وآليات التنفيذ والقدرات الفنية والإدارية التي تمتلكها الشركة لضمان نجاح المشروع.",
      "points": [
        "تعريف المنافسة وأهدافها",
        "المواعيد الرئيسية للتقديم والتنفيذ",
        "شروط أهلية مقدمي العروض"
      ],
      "table": {
        "headers": ["المصطلح", "التعريف"],
        "rows": [
          ["الجهة الحكومية", "الجهة المسؤولة عن طرح المنافسة ومتابعة التنفيذ"],
          ["مقدم العرض", "الشركة أو الكيان المتقدم للمنافسة"],
          ["المنافسة", "العملية التنافسية التي يتم عبرها تقديم وتقييم العروض"],
          ["الخدمات", "النطاق المطلوب تنفيذه وفقًا لشروط RFP"]
        ]
      }
    },
    {
      "heading": "الأحكام العامة",
      "content": "تلتزم [اسم الشركة] بأعلى معايير النزاهة والشفافية في جميع مراحل المنافسة والتنفيذ، بما يضمن مبدأ تكافؤ الفرص لجميع الأطراف المشاركة.",
      "points": [
        "ضمان المساواة والشفافية",
        "الإفصاح عن أي تعارض محتمل في المصالح",
        "التقيد بالسلوكيات والأخلاقيات المهنية"
      ],
      "table": {
        "headers": ["المبدأ", "التفاصيل"],
        "rows": [
          ["المساواة", "المعاملة العادلة لجميع المتنافسين دون استثناء"],
          ["الشفافية", "توفير المعلومات الكاملة والدقيقة للجهة الحكومية"],
          ["تعارض المصالح", "الإفصاح المبكر عن أي مواقف قد تؤثر على الحياد"],
          ["الأخلاقيات", "اتباع معايير أخلاقية ومهنية في جميع مراحل المشروع"]
        ]
      }
    },
    {
      "heading": "إعداد العروض",
      "content": "يتم إعداد العروض وفق منهجية تضمن وضوح البيانات ودقتها بما يحقق أهداف المنافسة. تم تحديد مدة صلاحية العرض بـ 90 يومًا من تاريخ فتح المظاريف لضمان الالتزام الكامل.",
      "points": [
        "تأكيد نية المشاركة في المنافسة",
        "اللغة المعتمدة لتقديم العرض",
        "وثائق العرض الفني والمالي"
      ],
      "table": {
        "headers": ["البند", "التفاصيل"],
        "rows": [
          ["اللغة", "العرض مقدم باللغة العربية مع إمكانية توفير نسخة باللغة الإنجليزية إذا طلبت"],
          ["مدة الصلاحية", "90 يومًا من تاريخ فتح المظاريف"],
          ["الوثائق الفنية", "منهجية التنفيذ وخطة العمل والهيكل التنظيمي للفريق"],
          ["الوثائق المالية", "جداول التكاليف التفصيلية وخطط الدفع"]
        ]
      }
    },
    {
      "heading": "تقديم العروض",
      "content": "سيتم تقديم العروض عبر المنصة الإلكترونية الرسمية (اعتماد)، مع الالتزام بتسليم الضمان الابتدائي المنصوص عليه ضمن شروط المنافسة.",
      "points": [
        "آلية تقديم العروض عبر المنصة",
        "آلية فتح المظاريف بحضور ممثلين"
      ],
      "table": {
        "headers": ["الإجراء", "التفاصيل"],
        "rows": [
          ["تقديم العروض", "رفع جميع الملفات المطلوبة عبر منصة اعتماد"],
          ["الضمان الابتدائي", "تقديم ضمان بنكي بنسبة محددة حسب شروط المنافسة"],
          ["فتح العروض", "إجراء فتح المظاريف بحضور لجنة مختصة وممثلين عن الجهة الحكومية"]
        ]
      }
    },
    {
      "heading": "تقييم العروض",
      "content": "تعتمد عملية التقييم على معايير فنية ومالية واضحة، بما يضمن اختيار أفضل عرض يحقق الجودة والتكلفة المثلى.",
      "points": [
        "آلية التقييم الفني",
        "معايير التقييم المالي",
        "آلية تصحيح الأخطاء في العروض"
      ],
      "table": {
        "headers": ["المعيار", "التفاصيل"],
        "rows": [
          ["المعيار الفني", "يشمل الخبرة السابقة، الكفاءات البشرية، ومنهجية التنفيذ"],
          ["المعيار المالي", "يشمل ملاءمة الأسعار ومطابقتها للتكلفة التقديرية"],
          ["آلية التصحيح", "مراجعة أي أخطاء حسابية وإبلاغ مقدم العرض بها"]
        ]
      }
    },
    {
      "heading": "متطلبات التعاقد",
      "content": "عند إرساء العقد، ستقوم الجهة الحكومية بإخطار الفائز رسميًا عبر البوابة الإلكترونية، مع تحديد النطاق الزمني والمالي بدقة.",
      "points": [
        "إشعار الترسية عبر المنصة",
        "تقديم الضمان النهائي",
        "بدء التنفيذ وفق الجدول"
      ],
      "table": {
        "headers": ["البند", "التفاصيل"],
        "rows": [
          ["إشعار الترسية", "إرسال خطاب رسمي عبر البوابة الإلكترونية"],
          ["الضمان النهائي", "5% من قيمة العقد الإجمالية"],
          ["بداية التنفيذ", "بعد اعتماد العقد وتوقيعه من جميع الأطراف"]
        ]
      }
    },
    {
      "heading": "نطاق العمل المفصل",
      "content": "يتضمن نطاق العمل مراحل متتابعة تبدأ بالتخطيط وتنتهي بالتنفيذ والتقييم، لضمان إنجاز المشروع بكفاءة وجودة عالية.",
      "points": [
        "مرحلة التخطيط",
        "مرحلة التحليل",
        "مرحلة التنفيذ",
        "مرحلة التقييم"
      ],
      "table": {
        "headers": ["المرحلة", "التفاصيل"],
        "rows": [
          ["التخطيط", "تحديد الأهداف، تشكيل الفريق، ووضع الجدول الزمني"],
          ["التحليل", "دراسة الوظائف والمهام الحالية وتحليل الاحتياجات"],
          ["التنفيذ", "إعداد الوصف الوظيفي، تطوير البرامج التدريبية"],
          ["التقييم", "قياس الأداء وفق مؤشرات محددة وإصدار تقارير شاملة"]
        ]
      }
    },
    {
      "heading": "المواصفات",
      "content": "سيتم توفير فريق متكامل من الخبراء والمستشارين ذوي الكفاءة العالية، لضمان تطبيق أفضل الممارسات العالمية.",
      "points": [
        "فريق عمل متعدد التخصصات",
        "المنهجية المعتمدة في التنفيذ"
      ],
      "table": {
        "headers": ["البند", "التفاصيل"],
        "rows": [
          ["فريق العمل", "يشمل خبراء في إدارة المشاريع، التدريب، والتطوير المؤسسي"],
          ["منهجية التنفيذ", "تعتمد على خطوات منظمة (تخطيط – تنفيذ – متابعة – تقييم)"]
        ]
      }
    },
    {
      "heading": "الشروط الخاصة",
      "content": "تلتزم الشركة بتقديم جميع المخرجات في المواعيد المحددة مع ضمان الجودة العالية.",
      "points": [
        "الالتزام بالجدول الزمني",
        "تقديم تقارير دورية",
        "جودة المخرجات"
      ],
      "table": {
        "headers": ["البند", "التفاصيل"],
        "rows": [
          ["المخرجات", "إعداد وتسليم الوثائق وفق الجدول المتفق عليه"],
          ["التقارير", "تقارير شهرية وربع سنوية ترفع للجهة الحكومية"],
          ["الجودة", "تطبيق معايير ضبط الجودة ISO 9001"]
        ]
      }
    },
    {
      "heading": "خطة إدارة المشروع",
      "content": "تعتمد خطة إدارة المشروع على نظام متكامل لإدارة المخاطر، وضمان الالتزام بمؤشرات الأداء الرئيسية لتحقيق النجاح.",
      "points": [
        "تحليل المخاطر المحتملة",
        "إجراءات التخفيف من المخاطر",
        "مؤشرات الأداء الرئيسية"
      ],
      "table": {
        "headers": ["البند", "التفاصيل"],
        "rows": [
          ["تحليل المخاطر", "تحديد المخاطر المتعلقة بالوقت والميزانية والجودة"],
          ["إجراءات التخفيف", "خطة بديلة للتنفيذ في حال حدوث تأخير أو عوائق"],
          ["مؤشرات الأداء", "KPIs تشمل الإنجاز الزمني، جودة المخرجات، ورضا المستفيدين"]
        ]
      }
    }
  ]
}


    json_path = Path("input.json")
    if json_path.exists():
        with open(json_path, "r", encoding="utf-8") as f:
            proposal = json.load(f)
    else:
        proposal = example_json  # fallback to inline

    out = build_word_from_proposal(proposal, output_path="output/proposal_ar3.docx", visible=False)
    print(f"✅ Word document created: {out}")
