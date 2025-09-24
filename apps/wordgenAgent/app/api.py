import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Tuple
from pathlib import Path
import requests
import pythoncom
from docx2pdf import convert
from openai import OpenAI
from apps.wordgenAgent.app.wordcom import build_word_from_proposal
from apps.wordgenAgent.app.proposal_clean import proposal_cleaner
from apps.api.services.supabase_service import (
    get_pdf_urls_by_uuid,
    upload_file_to_storage,
    update_proposal_in_data_table,
)

logger = logging.getLogger("wordgen_api")

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "pdf")  

system_prompts_en = """You are an expert in technical and development proposal writing.
Your task is to create a comprehensive, detailed proposal in English (minimum 6-7 pages) that:
1. Addresses ALL RFP requirements and evaluation criteria with extensive specific details
2. Includes comprehensive technical approach, clear methodology, and detailed timeline with complete explanations
3. Covers compliance, certifications, and qualifications comprehensively with specific examples
4. Has detailed sections for pricing, terms, and conditions with clear explanations
5. Includes all required forms, matrices, and appendices with complete content
6. Follows the exact structure and language required by the RFP
7. Provides substantial, detailed content under each section (minimum 200-400 words per major section)
8. Demonstrates deep understanding of RFP requirements through detailed, specific responses
9. Includes specific methodologies, detailed timelines, and clear deliverables
10. Shows professional expertise and technical capability with specific examples
11. Includes comprehensive risk analysis and mitigation strategies
12. Provides detailed project management approach
13. Includes specific performance metrics and success indicators
14. Demonstrates innovation and creative solutions
15. Provides quality assurance and performance monitoring frameworks
16. Merge the RFP with the company's supporting materials for company-specific sections.
17. Output MUST be valid JSON only (no markdown fences, no commentary)."""

system_prompts_ar = """أنت خبير في كتابة المقترحات التقنية ومقترحات التطوير.
مهمتك إنشاء مقترح شامل ومفصل باللغة العربية (لا يقل عن 6–7 صفحات) بحيث:
1) يغطي جميع متطلبات كراسة الشروط ومعايير التقييم بالتفاصيل الدقيقة.
2) يتضمن منهجية تقنية شاملة، وإطار عمل واضح، وخطة زمنية مفصلة مع الشرح الكامل.
3) يغطي الامتثال والاعتمادات والمؤهلات بشكل شامل مع أمثلة محددة.
4) يتضمن أقسامًا مفصلة للتسعير والشروط والأحكام مع تفسيرات واضحة.
5) يشتمل على جميع النماذج والمصفوفات والملاحق المطلوبة بمحتوى مكتمل.
6) يلتزم تمامًا بالهيكل واللغة المطلوبة في كراسة الشروط.
7) يقدم محتوى غنيًا تحت كل قسم (200–400 كلمة على الأقل لكل قسم رئيسي).
8) يُظهر فهمًا عميقًا لمتطلبات كراسة الشروط عبر ردود محددة ومفصلة.
9) يتضمن منهجيات محددة وخططًا زمنية واضحة ومخرجات قابلة للقياس.
10) يوضح خبرة مهنية وقدرة تقنية مع أمثلة محددة.
11) يتضمن تحليلًا شاملًا للمخاطر واستراتيجيات التخفيف.
12) يقدم منهجية إدارة مشروع مفصلة.
13) يضم مؤشرات أداء محددة ومعايير نجاح واضحة.
14) يُظهر الابتكار والحلول الإبداعية.
15) يقدم إطار ضمان الجودة ومتابعة الأداء.
16) يدمج كراسة الشروط مع المواد التعريفية للشركة للأقسام الخاصة بالشركة.
17) يجب أن يكون الإخراج JSON صالحًا فقط (بدون علامات تنسيق أو تعليقات خارج JSON)."""

JSON_SCHEMA_TEXT = """
Return ONLY a JSON object with this exact structure and keys (no extra keys, no prose):

{
"title": "Professional proposal title reflecting client name and project scope",
"sections": [
    {
    "heading": "string",
    "content": "string",
    "points": ["string", "..."],
    "table": {
        "headers": ["string", "..."],
        "rows": [["string","..."], ["string","..."]]
    }
    }
]
}
"""

JSON_SCHEMA_TEXT_AR = """
أعد فقط كائن JSON بهذا الهيكل الدقيق والمفاتيح التالية (بدون مفاتيح إضافية، بدون نص خارج JSON):

{
"title": "عنوان مقترح احترافي يعكس اسم العميل ونطاق المشروع",
"sections": [
    {
    "heading": "string",
    "content": "string",
    "points": ["string", "..."],
    "table": {
        "headers": ["string", "..."],
        "rows": [["string","..."], ["string","..."]]
    }
    }
]
}
"""

proposal_template = """
[Professional Proposal Title reflecting RFP and company solution alongwith Prepared By]

Executive Summary
Company Introduction
Understanding of the RFP and Objectives
Technical Approach and Methodology
    *Framework Overview
    *Phased Methodology
    *Methodological Pillars
Project Architecture
    *System Components
    *Data Flow & Integration
    *Technology Stack
Relevant Experience and Case Evidence
Project Team and Roles
Work Plan, Timeline, and Milestones
Quality Assurance and Risk Management
KPIs and Service Levels
Data Privacy, Security, and IP
Compliance with RFP Requirements
Deliverables Summary
Assumptions
Pricing Approach (Summary)
Why [Your Company]
"""

proposal_template_ar = """
[عنوان مهني للمقترح يعكس كراسة الشروط وحل الشركة مع عبارة "إعداد: ..."]

الملخص التنفيذي
التعريف بالشركة
فهم كراسة الشروط والأهداف
المنهجية الفنية ومنهجية التنفيذ
    *نظرة عامة على الإطار
    *منهجية على مراحل
    *الركائز المنهجية
هندسة المشروع
    *مكونات النظام
    *تدفق البيانات والتكامل
    *حزمة التقنيات
الخبرة ذات الصلة والأدلة المرجعية
فريق العمل والأدوار
خطة العمل والجدول الزمني والمعالم
ضمان الجودة وإدارة المخاطر
مؤشرات الأداء ومستويات الخدمة
الخصوصية والأمن وحقوق الملكية الفكرية
الامتثال لمتطلبات كراسة الشروط
ملخص المخرجات
الافتراضات
منهجية التسعير (مختصر)
لماذا [اسم شركتك]
"""

task_instructions_en_base = f"""
TASK: Create a comprehensive, detailed proposal (minimum 6-7 pages) that includes:
Follow the exact outline below. Populate company-specific parts from the supporting materials.
For every major section, include rich paragraphs in "content", add "points" only if there are bullet items,
and include a "table" only if a table is relevant (with headers and rows). Do NOT invent partners or facts not present.

{JSON_SCHEMA_TEXT}

For each section, provide:
- Detailed explanation of the topic
- Specific examples and practical cases
- Clear methodologies
- Specific timelines
- Performance measurement indicators

Proposal Title Instructions:
- Create a concise, professional title reflecting the RFP and solution.
- Include the client or project name if specified.
- Avoid generic terms.
- Keep it formal and professional.
- Add “Prepared by [Your Company]”.

IMPORTANT: The proposal must follow this structure:
{{OUTLINE}}

Proposal must be comprehensive, detailed, and practically implementable.
"""

task_instructions_ar_base = f"""
المهمة: أنشئ مقترحًا شاملاً ومفصلاً (لا يقل عن 6–7 صفحات) يتضمن:
اتبع المخطط أدناه حرفيًا. املأ الأجزاء الخاصة بالشركة من المواد الداعمة.
في كل قسم رئيسي، ضع فقرات غنية في "content"، وأضف "points" فقط عند وجود عناصر نقطية،
وأضف "table" فقط عند الحاجة (مع رؤوس وصفوف). لا تخترع شركاء أو حقائق غير موجودة.

{JSON_SCHEMA_TEXT_AR}

لكل قسم قدم:
- شرحًا تفصيليًا للموضوع
- أمثلة محددة وحالات عملية
- منهجيات واضحة
- جداول زمنية محددة
- مؤشرات قياس أداء

تعليمات عنوان المقترح:
- أنشئ عنوانًا موجزًا واحترافيًا يعكس كراسة الشروط والحل.
- ضمّن اسم العميل أو المشروع إن وُجد.
- تجنب المصطلحات العامة.
- حافظ على الطابع الرسمي والمهني.
- أضف: "إعداد: [اسم شركتك]".

مهم: يجب أن يتبع المقترح هذا الهيكل:
{{OUTLINE}}

يجب أن يكون المقترح شاملًا ومفصلًا وقابلًا للتنفيذ عمليًا.
"""

class WordGenAPI:
    def __init__(self) -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required")
        self.client = OpenAI(api_key=api_key)

    @staticmethod
    def _clean_url(url: str) -> str:
        return (url or "").split("?")[0]

    def _upload_pdf_urls_to_openai(self, rfp_url: str, supporting_url: str) -> Tuple[str, str]:
        """Download both PDFs and upload as user_data files; returns (rfp_id, sup_id)."""
        rfp_u = self._clean_url(rfp_url)
        sup_u = self._clean_url(supporting_url)

        logger.info(f"Downloading RFP: {rfp_u}")
        rfp_bytes = requests.get(rfp_u, timeout=60).content

        logger.info(f"Downloading Supporting: {sup_u}")
        sup_bytes = requests.get(sup_u, timeout=60).content

        rfpf = self.client.files.create(file=("RFP.pdf", rfp_bytes, "application/pdf"), purpose="user_data")
        supf = self.client.files.create(file=("Supporting.pdf", sup_bytes, "application/pdf"), purpose="user_data")
        logger.info(f"OpenAI files uploaded: rfp={rfpf.id}, supporting={supf.id}")
        return rfpf.id, supf.id

    def _convert_docx_to_pdf(self, docx_path: str) -> str:
        """Convert DOCX -> PDF using docx2pdf (Word COM) with proper COM init."""
        pdf_path = os.path.splitext(docx_path)[0] + ".pdf"
        pythoncom.CoInitialize()
        try:
            convert(docx_path, pdf_path)
            logger.info(f"Converted to PDF: {pdf_path}")
        finally:
            pythoncom.CoUninitialize()
        return pdf_path

    def _select_prompts(self, language: str, outline: str | None) -> tuple[str, str]:
        """
        Choose EN/AR prompts and inject the outline (if provided).
        If outline is None/empty, fall back to the built-in template in that language.
        """
        is_ar = (language or "").strip().lower() == "arabic"

        base = task_instructions_ar_base if is_ar else task_instructions_en_base
        default_outline = proposal_template_ar if is_ar else proposal_template
        effective_outline = outline.strip() if outline and outline.strip() else default_outline
        task = base.replace("{OUTLINE}", effective_outline)

        system = system_prompts_ar if is_ar else system_prompts_en
        return system, task

    def generate_complete_proposal(
        self,
        uuid: str,
        rfp_url: str,
        supporting_url: str,
        user_config: str = "",
        doc_config: Dict[str, Any] | None = None,
        language: str = "english",
        outline: str | None = None,   
    ) -> Dict[str, Any]:

        start = datetime.now()
        logger.info(f"[initialgen] START for uuid={uuid}")
        rfp_id, sup_id = self._upload_pdf_urls_to_openai(rfp_url, supporting_url)
        system_prompts, task_instructions = self._select_prompts(language, outline)
        logger.info("Calling OpenAI Responses API…")
        completion = self.client.responses.create(
            model=OPENAI_MODEL,
            input=[{
                "role": "user",
                "content": [
                    {"type": "input_file", "file_id": rfp_id},
                    {"type": "input_file", "file_id": sup_id},
                    {"type": "input_text", "text": system_prompts},
                    {"type": "input_text", "text": task_instructions},
                ],
            }],
        )
        raw = completion.output_text or ""
        logger.info(f"OpenAI response chars: {len(raw)}")

        if "{" not in raw or '"sections"' not in raw:
            logger.warning("Model returned non-JSON; retrying with strict guardrail")
            strict_guard = (
                "Return ONLY a single valid JSON object matching the schema. "
                "Start with '{' and end with '}'. No explanations, no markdown, no extra text."
            )
            completion = self.client.responses.create(
                model=OPENAI_MODEL,
                input=[{
                    "role": "user",
                    "content": [
                        {"type": "input_file", "file_id": rfp_id},
                        {"type": "input_file", "file_id": sup_id},
                        {"type": "input_text", "text": system_prompts},
                        {"type": "input_text", "text": task_instructions},
                        {"type": "input_text", "text": strict_guard},
                    ],
                }],
            )
            raw = completion.output_text or ""
            logger.info(f"[retry] OpenAI response chars: {len(raw)}")

        cleaned = proposal_cleaner(raw)
        out_dir = Path("output")
        out_dir.mkdir(parents=True, exist_ok=True)
        docx_path = out_dir / f"{uuid}.docx"

        effective_cfg = {}
        if isinstance(user_config, str) and user_config.strip().startswith("{"):
            try:
                effective_cfg = json.loads(user_config)
            except Exception:
                effective_cfg = doc_config or {}
        else:
            effective_cfg = doc_config or {}

        docx_abs = build_word_from_proposal(
            proposal_dict=cleaned,
            user_config=effective_cfg,
            output_path=str(docx_path),
            language=language,
            visible=False,
        )

        pdf_path = ""
        try:
            pdf_path = self._convert_docx_to_pdf(docx_abs)
        except Exception as e:
            logger.warning(f"PDF conversion failed: {e}")

        word_url = ""
        pdf_url = ""
        try:
            with open(docx_abs, "rb") as f:
                word_bytes = f.read()
            word_url = upload_file_to_storage(
                word_bytes, f"{uuid}/proposal.docx", "proposal.docx", bucket_name=SUPABASE_BUCKET
            )
        except Exception as e:
            logger.error(f"Upload DOCX failed: {e}")

        if pdf_path and os.path.exists(pdf_path):
            try:
                with open(pdf_path, "rb") as f:
                    pdf_bytes = f.read()
                pdf_url = upload_file_to_storage(
                    pdf_bytes, f"{uuid}/proposal.pdf", "proposal.pdf", bucket_name=SUPABASE_BUCKET
                )
            except Exception as e:
                logger.error(f"Upload PDF failed: {e}")

        updated = update_proposal_in_data_table(
            uuid,
            json.dumps(cleaned, ensure_ascii=False),
            pdf_url,
            word_url
        )

        elapsed = (datetime.now() - start).total_seconds()
        logger.info(f"[initialgen] DONE uuid={uuid} in {elapsed:.2f}s")

        return {
            "status": "success",
            "uuid": uuid,
            "proposal_content": cleaned,
            "word_file_path": docx_abs,
            "proposal_word_url": word_url,
            "proposal_pdf_url": pdf_url,
            "data_table_updated": updated,
            "processing_time": f"{elapsed:.2f}s",
            "model_used": OPENAI_MODEL,
            "language": language,
        }
wordgen_api = WordGenAPI()
