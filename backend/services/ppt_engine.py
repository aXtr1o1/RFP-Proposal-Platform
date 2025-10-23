import io, os, uuid
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from pptx import Presentation
from pptx.util import Inches
from core.logger import get_logger
from core.config import settings

logger = get_logger("ppt")

sns.set_theme(style="whitegrid")
sns.set_palette("husl")

def analyze_template_layouts(template_bytes: bytes):
    prs = Presentation(io.BytesIO(template_bytes))
    details = {}
    report = f"Template layouts: {len(prs.slide_layouts)} found.\n"
    for i, layout in enumerate(prs.slide_layouts):
        phs = [{"idx": ph.placeholder_format.idx, "type": ph.placeholder_format.type, "name": ph.name} for ph in layout.placeholders]
        title_idx = next((ph["idx"] for ph in phs if ph["type"] == 1), None)
        content_indices = [ph["idx"] for ph in phs if ph["type"] in (2,4,7,14)]
        details[i] = {"name": layout.name, "title_idx": title_idx, "content_indices": content_indices}
        report += f"Layout {i}: {layout.name} | title={title_idx}, contents={content_indices}\n"
    return report, details

def generate_chart_png(chart_spec: dict, cache) -> str:
    title = chart_spec.get("title", "Chart")
    chart_type = chart_spec.get("chart_type", "bar").lower()
    data = chart_spec.get("data", {})
    path = os.path.join(settings.OUTPUT_CHARTS_DIR, f"chart_{uuid.uuid4().hex[:8]}.png")
    fig, ax = plt.subplots(figsize=(10,6))
    if chart_type in ["bar", "column"]:
        labels = data.get("labels", [])
        values = data.get("values", [])
        sns.barplot(x=labels, y=values, ax=ax)
    elif chart_type == "line":
        labels = data.get("labels", [])
        values = data.get("values", [])
        ax.plot(labels, values, marker='o')
    elif chart_type == "pie":
        labels = data.get("labels", [])
        values = data.get("values", [])
        ax.pie(values, labels=labels, autopct='%1.1f%%')
    ax.set_title(title)
    plt.tight_layout()
    plt.savefig(path, bbox_inches="tight", transparent=True)
    plt.close()
    cache.add_temp_file(path)
    return path

def build_ppt_from_slides(slides, template_bytes, cache):
    prs = Presentation(io.BytesIO(template_bytes))
    while prs.slides._sldIdLst:
        rId = prs.slides._sldIdLst[0].rId
        prs.part.drop_rel(rId)
        del prs.slides._sldIdLst[0]
    for i, s in enumerate(slides, start=1):
        layout = prs.slide_layouts[min(s.get("layout_index",1), len(prs.slide_layouts)-1)]
        slide = prs.slides.add_slide(layout)
        title = s.get("title","")
        if slide.shapes.title:
            slide.shapes.title.text = title
        if s.get("layout_type") == "CHART" and "chart" in s:
            chart_path = generate_chart_png(s["chart"], cache)
            slide.shapes.add_picture(chart_path, Inches(1), Inches(1.5), width=Inches(8))
        elif "content" in s:
            for idx, content_list in enumerate(s["content"]):
                if idx < len(slide.placeholders):
                    try:
                        ph = slide.placeholders[idx+1]
                        ph.text = "\n".join(content_list)
                    except Exception:
                        pass
    out = io.BytesIO()
    prs.save(out)
    return out.getvalue()

def export_pdf_from_ppt(ppt_bytes: bytes) -> bytes | None:
    import tempfile, subprocess
    with tempfile.TemporaryDirectory() as tmpdir:
        ppt_path = os.path.join(tmpdir, "temp.pptx")
        pdf_path = os.path.join(tmpdir, "temp.pdf")
        with open(ppt_path,"wb") as f: f.write(ppt_bytes)
        try:
            subprocess.run(["soffice","--headless","--convert-to","pdf",ppt_path,"--outdir",tmpdir],check=True)
            with open(pdf_path,"rb") as f:
                return f.read()
        except Exception:
            return None
