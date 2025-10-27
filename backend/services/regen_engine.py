import os
import re
from difflib import SequenceMatcher
from typing import List, Dict, Any, Tuple

from core.config import settings
from core.logger import get_logger
from core.utils import extract_json_array, short_kb, uuid_like
from core.cache_manager import CacheManager

from prompts.regen_prompt import (
    build_regen_system_prompt,
    build_regen_task_prompt,
    build_modification_summary,
)

from services.ppt_engine import (
    analyze_template_layouts,
    build_ppt_from_slides,
    export_pdf_from_ppt_bytes,  
)


class RegenerationEngine:
    """
    Orchestrates PPT regeneration workflow.
    """
    def __init__(self, supabase, openai_engine, cache: CacheManager, logger=None):
        self.supabase = supabase
        self.openai = openai_engine
        self.cache = cache
        self.logger = logger or get_logger("regen")
    
    def run_regeneration(
        self,
        uuid: str,
        previous_gen_id: str,
        regen_comments: List[Dict[str, str]],
        language: str = "english"
    ) -> Dict[str, Any]:
        """
        Main regeneration workflow.
        """
        try:
            self.logger.info(f"fetching previous generation (gen_id={previous_gen_id[:8]}...)")
            prev_record = self.supabase.fetch_record(uuid, previous_gen_id)
            if not prev_record:
                raise ValueError(f"Previous generation not found (uuid={uuid}, gen_id={previous_gen_id})")
            self.logger.info("previous record found")
            
            original_json = prev_record.get("generated_json")
            if not original_json:
                raise ValueError("Original JSON not stored in database (generated_json is null)")
            self.logger.info(f"original slides loaded (count={len(original_json)})")
            
            template_url = prev_record.get("ppt_template")
            if not template_url:
                raise ValueError("Template URL not found in previous record")
            
            template_key = template_url.split(f"{settings.PPT_TEMPLATE_BUCKET}/")[-1]
            template_bytes = self.supabase.download_file(settings.PPT_TEMPLATE_BUCKET, template_key)
            self.logger.info(f"template downloaded (size={short_kb(len(template_bytes))} KB)")
           
            template_analysis, layout_details = analyze_template_layouts(template_bytes)

            self.logger.info("validating modification requests...")
            validated_comments = self._validate_comments(original_json, regen_comments)
            if not validated_comments:
                raise ValueError("No valid modifications found - check slide numbers and content")
            self.logger.info(build_modification_summary(validated_comments))
            
            self.logger.info("applying modifications via OpenAI...")
            updated_slides = self._apply_modifications_via_openai(
                original_json,
                validated_comments,
                template_analysis,
                language
            )
            self.logger.info(f"modifications applied (output_slides={len(updated_slides)})")

            self.logger.info("building PowerPoint...")
            ppt_bytes = build_ppt_from_slides(updated_slides, template_bytes, self.cache)
            self.logger.info(f"PPT ready in memory (size={short_kb(len(ppt_bytes))} KB)")
            self.logger.info("exporting PDF...")
            pdf_bytes = export_pdf_from_ppt_bytes(ppt_bytes)
            if pdf_bytes:
                self.logger.info(f"PDF ready (size={short_kb(len(pdf_bytes))} KB)")
            else:
                self.logger.warning("PDF export skipped (converter not available)")

            new_gen_id = uuid_like("gen")
            self.logger.info("uploading regenerated files...")
            ppt_url = self.supabase.upload_bytes(
                settings.PPT_BUCKET,
                f"{new_gen_id}.pptx",
                ppt_bytes,
                "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            )
            pdf_url = None
            if pdf_bytes:
                pdf_url = self.supabase.upload_bytes(
                    settings.PDF_BUCKET,
                    f"{new_gen_id}.pdf",
                    pdf_bytes,
                    "application/pdf"
                )
            self.logger.info(f"uploads complete (ppt_url={ppt_url}, pdf_url={pdf_url})")

            self.logger.info("inserting new version...")
            self.supabase.insert_new_version(
                uuid=uuid,
                gen_id=new_gen_id,
                generated_json=updated_slides,
                regen_comments=regen_comments,
                generated_ppt=ppt_url,
                generated_pdf=pdf_url,
                rfp_file=prev_record["rfp_file"],
                supporting_file=prev_record["supporting_file"],
                ppt_template=prev_record["ppt_template"],
                general_preferences=prev_record.get("general_preferences", "")
            )
            self.logger.info(f"new version created (gen_id={new_gen_id})")

            return {
                "status": "completed",
                "gen_id": new_gen_id,
                "ppt_url": ppt_url,
                "pdf_url": pdf_url,
                "previous_gen_id": previous_gen_id,
                "modifications_applied": len(validated_comments)
            }
        finally:
            self.cache.cleanup()

    def _validate_comments(
        self,
        original_slides: List[Dict],
        regen_comments: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        """
        Validate modification requests. Uses fuzzy matching against title/content/chart.
        """
        validated = []
        for comment in regen_comments:
            slide_num = comment.get("slide")
            original_content = (comment.get("original_content") or "").strip()
            modification = (comment.get("modification") or "").strip()

            if not slide_num or not original_content or not modification:
                self.logger.warning(f"skipping invalid comment (missing fields): {comment}")
                continue
            if slide_num < 1 or slide_num > len(original_slides):
                self.logger.warning(f"skipping comment for slide {slide_num} (out of range 1-{len(original_slides)})")
                continue

            slide = original_slides[slide_num - 1]
            found, location = self._find_content_in_slide(slide, original_content)
            if not found:
                self.logger.warning(
                    f"skipping comment for slide {slide_num}: "
                    f"content not found: '{original_content[:60]}...'"
                )
                continue

            validated.append({**comment, "location": location})
            self.logger.info(f"validated: slide {slide_num}, location={location}")

        return validated

    @staticmethod
    def _norm_text(s: str) -> str:
        if not s:
            return ""
        s = s.lower()
        s = s.replace("—", "-").replace("–", "-")
        s = re.sub(r"[^\w\s\.-]", " ", s)  
        s = re.sub(r"\s+", " ", s).strip()
        return s

    @staticmethod
    def _token_overlap(a: str, b: str) -> float:
        ta = set(a.split())
        tb = set(b.split())
        if not ta or not tb:
            return 0.0
        return len(ta & tb) / float(len(ta))

    def _fuzzy_contains(self, hay: str, needle: str) -> bool:
        """
        Fuzzy containment: substring OR token-overlap OR similarity ratio.
        """
        h = self._norm_text(hay)
        n = self._norm_text(needle)
        if not h or not n:
            return False

        if n in h:
            return True
        if self._token_overlap(n, h) >= 0.6:
            return True
        if SequenceMatcher(None, n, h).ratio() >= 0.6:
            return True

        return False

    def _find_content_in_slide(
        self,
        slide: Dict,
        search_content: str
    ) -> Tuple[bool, str]:
        """
        Search title, nested/flat content, and chart fields with fuzzy logic.
        """
        title = slide.get("title", "") or ""
        if self._fuzzy_contains(title, search_content):
            return True, "title"

        content = slide.get("content", [])
        if isinstance(content, list):
            if content and all(isinstance(x, list) for x in content):
                for i, arr in enumerate(content):
                    for j, bullet in enumerate(arr or []):
                        btxt = str(bullet or "")
                        if self._fuzzy_contains(btxt, search_content):
                            return True, f"content[{i}][{j}]"
            else:
                for j, bullet in enumerate(content or []):
                    btxt = str(bullet or "")
                    if self._fuzzy_contains(btxt, search_content):
                        return True, f"content[0][{j}]"

        chart = slide.get("chart", {})
        if chart:
            try:
                parts = []
                parts.append(str(chart.get("title", "")))
                data = chart.get("data", {}) or {}
                labels = data.get("labels", []) or []
                parts.extend([str(x) for x in labels])
                if "values" in data:
                    parts.extend([str(v) for v in data.get("values", []) or []])
                for s in data.get("series", []) or []:
                    parts.append(str(s.get("name", "")))
                    parts.extend([str(v) for v in s.get("values", []) or []])
                chart_flat = " ".join(parts)
                if self._fuzzy_contains(chart_flat, search_content):
                    return True, "chart"
            except Exception:
                pass

        return False, ""

    def _apply_modifications_via_openai(
        self,
        original_slides: List[Dict],
        regen_comments: List[Dict[str, str]],
        template_info: str,
        language: str
    ) -> List[Dict]:
        """
        Call OpenAI to apply modifications. The prompts should enforced
        """
        system_prompt = build_regen_system_prompt()
        task_prompt = build_regen_task_prompt(
            original_slides,
            regen_comments,
            template_info,
            language
        )
        self.logger.info("calling OpenAI Chat Completion...")
        response = self.openai.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": task_prompt}
            ],
            temperature=0.3,
            max_tokens=settings.MAX_OUTPUT_TOKENS
        )
        raw_json = response.choices[0].message.content
        self.logger.info(f"OpenAI response received (chars={len(raw_json)})")

        updated_slides = extract_json_array(raw_json)
        if len(updated_slides) != len(original_slides):
            self.logger.warning(
                f"slide count mismatch: original={len(original_slides)}, updated={len(updated_slides)}"
            )
        return updated_slides
