import io
import os
import uuid
import subprocess
import tempfile
from typing import Dict, Any, Tuple, List

import matplotlib.pyplot as plt
import seaborn as sns
from pptx import Presentation
from pptx.util import Inches

from core.logger import get_logger
from core.config import settings
from core.utils import short_kb

logger = get_logger("ppt")
sns.set_theme(style="whitegrid")
sns.set_palette("husl")
os.makedirs(settings.OUTPUT_CHARTS_DIR, exist_ok=True)


def analyze_template_layouts(template_bytes: bytes) -> Tuple[str, Dict[int, Dict[str, Any]]]:
    """
    Analyze the provided PPTX template bytes and return a short textual summary plus a
    dict with layout details {index: {name, title_idx, content_indices}}.
    """
    prs = Presentation(io.BytesIO(template_bytes))
    details: Dict[int, Dict[str, Any]] = {}

    for i, layout in enumerate(prs.slide_layouts):
        placeholders = getattr(layout, "placeholders", [])
        phs: List[Dict[str, Any]] = []
        for ph in placeholders:
            try:
                phs.append({
                    "idx": ph.placeholder_format.idx,
                    "type": ph.placeholder_format.type,
                    "name": getattr(ph, "name", "")
                })
            except Exception:
                continue

        title_idx = next((p["idx"] for p in phs if p["type"] == 1), None)
        content_indices = [p["idx"] for p in phs if p["type"] in (2, 4, 7, 14)]
        details[i] = {
            "name": getattr(layout, "name", f"Layout {i}"),
            "title_idx": title_idx,
            "content_indices": content_indices,
        }

    logger.info(f"template layouts detected: {len(prs.slide_layouts)}")
    return (f"Template layouts: {len(prs.slide_layouts)} found.", details)


def generate_chart_png(chart_spec: Dict[str, Any], cache) -> str:
    """
    Generate a PNG chart from a spec and return the file path.
    The file is registered with the cache for later cleanup.
    """
    title = chart_spec.get("title", "Chart")
    chart_type = str(chart_spec.get("chart_type", "bar")).lower()
    data = chart_spec.get("data", {}) or {}

    path = os.path.join(settings.OUTPUT_CHARTS_DIR, f"chart_{uuid.uuid4().hex[:8]}.png")
    labels = data.get("labels", []) or []

    fig, ax = plt.subplots(figsize=(10, 6))
    try:
        if chart_type in ("bar", "column"):
            values = data.get("values", []) or []
            ax.bar(labels, values)

        elif chart_type == "line":
            values = data.get("values", []) or []
            ax.plot(labels, values, marker="o")

        elif chart_type == "pie":
            values = data.get("values", []) or []
            if not labels or not values or len(labels) != len(values):
                labels = labels or [f"S{i+1}" for i in range(len(values))]
                labels = labels[:len(values)]
            ax.pie(values, labels=labels, autopct="%1.1f%%")

        else:
            ax.text(0.5, 0.5, f"Unsupported chart: {chart_type}", ha="center", va="center")

        ax.set_title(title)
        fig.tight_layout()
        fig.savefig(path, bbox_inches="tight", transparent=True)
        logger.info(f"chart generated '{title}' ({chart_type}) -> {path}")
    finally:
        plt.close(fig)

    try:
        cache.add_temp_file(path)
    except Exception:
        pass

    return path


def build_ppt_from_slides(slides: list, template_bytes: bytes, cache) -> bytes:
    """
    Build a PPTX in memory using the template bytes and slide JSON.
    Returns the PPTX as bytes.
    """
    prs = Presentation(io.BytesIO(template_bytes))
    xml_slides = getattr(prs.slides, "_sldIdLst", None)
    while xml_slides is not None and len(xml_slides):
        rId = xml_slides[0].rId
        prs.part.drop_rel(rId)
        del xml_slides[0]

    for idx, s in enumerate(slides, start=1):
        layout_idx = s.get("layout_index", 1)
        if not isinstance(layout_idx, int) or layout_idx < 0:
            layout_idx = 1
        if layout_idx >= len(prs.slide_layouts):
            layout_idx = len(prs.slide_layouts) - 1

        slide = prs.slides.add_slide(prs.slide_layouts[layout_idx])

        title = s.get("title", "") or ""
        try:
            if slide.shapes.title:
                slide.shapes.title.text = title
        except Exception:
            pass

        if str(s.get("layout_type", "")).upper() == "CHART" and "chart" in s:
            try:
                chart_path = generate_chart_png(s["chart"], cache)
                slide.shapes.add_picture(chart_path, Inches(1), Inches(1.5), width=Inches(8))
            except Exception as e:
                logger.warning(f"chart add failed on slide #{idx}: {e}")
        elif "content" in s:
            for pidx, content_list in enumerate(s.get("content", [])):
                try:
                    ph = slide.placeholders[pidx + 1]
                    ph.text = "\n".join(str(x) for x in (content_list or []))
                except Exception:
                    continue

        logger.info(f"slide added #{idx} (layout_index={layout_idx}, title='{title}')")

    out = io.BytesIO()
    prs.save(out)
    ppt_bytes = out.getvalue()
    logger.info(f"PowerPoint built (slides={len(slides)})")
    logger.info(f"PowerPoint ready in memory (size={short_kb(len(ppt_bytes))} KB)")
    return ppt_bytes


def convert_ppt_to_pdf(ppt_path: str, pdf_path: str) -> str:
    """
    Convert a PPTX file on disk to PDF on disk using LibreOffice soffice (PATH or common locations).
    Returns the actual PDF path on success, "" on failure.

    NOTE: LibreOffice writes <input_basename>.pdf into --outdir (ignores the given pdf file name),
    so we compute expected path and rename if the caller requested a different filename.
    """
    try:
        from pathlib import Path

        logger.info(f"Converting PPT to PDF: {ppt_path}")

        ppt_path = os.path.abspath(ppt_path)
        desired_pdf_path = os.path.abspath(pdf_path)
        outdir = str(Path(desired_pdf_path).parent)
        os.makedirs(outdir, exist_ok=True)
        expected_pdf = str(Path(outdir) / (Path(ppt_path).stem + ".pdf"))

        soffice_paths = [
            "soffice",
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
            "/usr/bin/soffice",
            "/usr/local/bin/soffice",
        ]

        for soffice_path in soffice_paths:
            try:
                result = subprocess.run(
                    [
                        soffice_path,
                        "--headless",
                        "--convert-to", "pdf",
                        "--outdir", outdir,
                        ppt_path,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )

                if result.returncode == 0 and os.path.exists(expected_pdf):
                    final_pdf = expected_pdf
                    if os.path.abspath(expected_pdf) != desired_pdf_path:
                        try:
                            os.replace(expected_pdf, desired_pdf_path)
                            final_pdf = desired_pdf_path
                        except Exception:
                            pass
                    logger.info(f"[OK] PDF converted using LibreOffice: {final_pdf}")
                    return final_pdf

                if result.returncode != 0:
                    logger.warning(
                        "LibreOffice returned non-zero exit code: "
                        f"{result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
                    )

                if result.returncode == 0 and not os.path.exists(expected_pdf):
                    logger.warning(
                        "LibreOffice reported success but PDF not found.\n"
                        f"Expected at: {expected_pdf}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
                    )

            except FileNotFoundError:
                continue
            except Exception as e:
                logger.debug(f"LibreOffice attempt failed at {soffice_path}: {e}")
                continue

        logger.warning("LibreOffice not found in PATH or standard locations; trying PowerPoint COM fallback...")
        if os.name == "nt":
            try:
                import comtypes.client

                logger.info("Attempting PDF conversion using Microsoft PowerPoint (COM)...")

                powerpoint = comtypes.client.CreateObject("PowerPoint.Application")
                powerpoint.Visible = 1

                ppt_abs = os.path.abspath(ppt_path)
                pdf_abs = os.path.abspath(desired_pdf_path)

                deck = powerpoint.Presentations.Open(ppt_abs, WithWindow=False)
                deck.SaveAs(pdf_abs, 32)  
                deck.Close()
                powerpoint.Quit()

                if os.path.exists(pdf_abs):
                    logger.info(f"[OK] PDF converted using PowerPoint COM: {pdf_abs}")
                    return pdf_abs
                else:
                    logger.warning("PowerPoint COM reported success but PDF not found")

            except ImportError:
                logger.debug("comtypes not installed for PowerPoint COM fallback")
            except Exception as e:
                logger.debug(f"PowerPoint COM automation failed: {e}")

        logger.warning("=" * 60)
        logger.warning("NO PDF CONVERSION TOOL AVAILABLE")
        logger.warning("PDF generation skipped - PPTX file is available")
        logger.warning("")
        logger.warning("To enable PDF conversion:")
        logger.warning("  Windows: Install LibreOffice and add to PATH")
        logger.warning("  Linux:   sudo apt install libreoffice -y")
        logger.warning("  macOS:   brew install libreoffice")
        logger.warning("=" * 60)

        return ""

    except Exception as e:
        logger.error(f"[ERROR] Error converting PPT to PDF: {e}")
        return ""


def export_pdf_from_ppt_bytes(ppt_bytes: bytes) -> bytes | None:
    """
    Convert PPTX bytes to PDF bytes using LibreOffice via a temp folder.
    Returns PDF bytes or None on failure.
    """
    with tempfile.TemporaryDirectory() as tdir:
        ppt_path = os.path.join(tdir, "input.pptx")
        pdf_path = os.path.join(tdir, "output.pdf")
        with open(ppt_path, "wb") as f:
            f.write(ppt_bytes)

        final_pdf_path = convert_ppt_to_pdf(ppt_path, pdf_path)
        if final_pdf_path and os.path.exists(final_pdf_path):
            with open(final_pdf_path, "rb") as f:
                data = f.read()
            logger.info("PDF bytes ready in memory")
            return data
        return None
