import os
from typing import Optional

MODEL = os.getenv("OPENAI_MODEL", "gpt-5")

PROPOSAL_TEMPLATE_EN = """
- Executive Summary
- Company Introduction
- Understanding of the RFP and Objectives
- Technical Approach and Methodology
  - Framework Overview
  - Phased Methodology
  - Methodological Pillars
- Project Architecture
  - System Components
  - Data Flow & Integration
  - Technology Stack
- Relevant Experience and Case Evidence
- Project Team and Roles
- Work Plan, Timeline, and Milestones
- Quality Assurance and Risk Management
- KPIs and Service Levels
- Data Privacy, Security, and IP
- Compliance with RFP Requirements
- Deliverables Summary
- Assumptions
- Pricing Approach (Summary)
- Why [Your Company]
"""

PROPOSAL_TEMPLATE_AR = """
- الملخص التنفيذي
- مقدمة عن الشركة
- فهم طلب تقديم العروض والأهداف
- المنهجية والأسلوب التقني
  - نظرة عامة على الإطار
  - منهجية متعددة المراحل
  - ركائز المنهجية
- هيكلية المشروع
  - مكونات النظام
  - تدفق البيانات والتكامل
  - حزمة التقنيات
- الخبرات ذات الصلة والدراسات المرجعية
- فريق المشروع والأدوار
- خطة العمل والجدول الزمني والمراحل الرئيسية
- ضمان الجودة وإدارة المخاطر
- مؤشرات الأداء الرئيسية ومستويات الخدمة
- خصوصية البيانات والأمن والملكية الفكرية
- الالتزام بمتطلبات طلب تقديم العروض
- ملخص المخرجات
- الافتراضات
- منهجية التسعير (ملخص)
- لماذا [اسم شركتك]
"""

system_prompts = """You are an expert technical proposal writer for English or Modern Standard Arabic. Follow only the specified sections and produce the output entirely in GitHub Markdown. Do not include JSON, extra prose, or formatting instructions outside the required markdown.

Rules:
1. Scope: Mirror ONLY the requested sections from the RFP outline; do not invent additional sections or mention section numbers explicitly.
2. Sources: Use only the provided RFP/BRD, Supporting File, CompanyDigest, and User Configuration. Do not invent partners, facts, certifications, or clients.
3. Company mapping: Map CompanyDigest into Company Introduction, Relevant Experience, and Why [Company]; replace placeholders (e.g., [Your Company], founded year) with digest values where available.
4. User Configuration: Apply timelines and directives exactly where relevant (Work Plan/Timeline, tone requirements, emphases, etc.).
5. Language: Output everything in the requested language (title, headings, body, tables, bullets). For Arabic, write in Modern Standard Arabic; proper nouns may keep an English gloss if absolutely necessary. Layout/RTL is handled by the renderer—do not output layout instructions.
6. Style: Prefer rich paragraphs for main content; only use points or tables when the content genuinely benefits from structured formatting.
7. Template fidelity: When task instructions provide a "Proposal Template," copy the headings verbatim, in the language they appear, without adding/removing nodes.
8. Output: Return GitHub Markdown only, suitable for immediate rendering.

Proposal Title Instructions:
- Create a concise, professional title reflecting the RFP and solution.
- Include the client or project name if specified.
- Avoid generic terms.
- Keep it formal and professional.
- Append "Prepared by [Your Company]".

IMPORTANT:
- Keep all headings, sub-headings, content, tables, and bullet points entirely in the requested language, with no English words unless absolutely necessary.
- Never wrap the response in JSON or add explanatory prose outside the markdown.
"""


def build_task_instructions_with_config(
    language: str,
    user_config_json: str,
    rfp_label: str,
    supporting_label: str,
    user_config_notes: Optional[str] = None,
) -> str:

    normalized_language = (language or "").strip().lower()
    notes_block = f'\nUserNotes: "{(user_config_notes or "").strip()}"\n'
    template_block = (PROPOSAL_TEMPLATE_AR if normalized_language == "arabic" else PROPOSAL_TEMPLATE_EN).strip()

    arabic_addendum = ""
    if normalized_language == "arabic":
        arabic_addendum = """
                          ARABIC Instructions:
                          - Output the entire proposal in Modern Standard Arabic.
                          - Keep all titles, headings, sub-headings, content, tables, and bullets fully Arabic except for unavoidable proper nouns.
                          - Ensure the Arabic content is precise, coherent, and grounded strictly in the RFP, Supporting File (CompanyDigest), and User Configuration.
                          - Do not mention layout directions (RTL is handled automatically); simply provide Arabic text.
                          - Return ONLY the markdown; no wrappers, JSON, or commentary.
                          """

    return (
        f"- Target language: {language}\n"
        f"RFP_FILE:\n{rfp_label}\n"
        f"SUPPORTING_FILE:\n{supporting_label}\n"
        f"UserConfig:\n{user_config_json or 'null'}\n"
        f"{notes_block}\n"
        "Proposal Template (mirror exactly; headings already shown in the required language):\n"
        f"{template_block}\n"
        "Constraints:\n"
        "- Apply all User Configuration directives to the relevant sections.\n"
        "- Do not invent or add external facts.\n"
        f"{arabic_addendum}"
    )
