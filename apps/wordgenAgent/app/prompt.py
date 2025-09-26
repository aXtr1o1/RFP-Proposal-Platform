import os
from typing import Optional

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.3"))
MAX_OUTPUT_TOKENS = int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "16000"))

COMPANY_DIGEST_SYSTEM = """You are an expert proposal analyst.
Extract a structured, comprehensive CompanyDigest (JSON) from the provided 'supporting_text'.
Rules:
- Use ONLY information in supporting_text; no external facts.
- Translate Arabic to English for the digest, but preserve proper nouns (institutions, programs) in Arabic with an English gloss if known.
- If a field is missing, use "Not specified".
- Keep it concise but complete; don't exceed ~1200 tokens.
- Include 'source_attribution' with brief quotes/section labels from supporting_text for key claims.
Return ONLY valid JSON. No commentary, no markdown fences.
"""

# ------------------------------------------------------
# 2) Company profile JSON schema — the exact JSON format
# ------------------------------------------------------
COMPANY_DIGEST_SCHEMA = r"""
Produce JSON with this exact schema:

{
  "company_profile": {
    "legal_name": "...",
    "brand_name": "...",
    "hq_location": "...",
    "founded_year": "...",
    "mission": "...",
    "vision": "...",
    "values": ["..."]
  },
  "capabilities": {
    "domains": ["..."],
    "services": ["..."],
    "methodologies": ["..."],
    "differentiators": ["..."],
    "partners": ["..."]
  },
  "track_record": [
    {
      "project_title": "...",
      "client": "...",
      "year_or_period": "...",
      "scope_summary": "...",
      "outcomes_kpis": ["...", "..."]
    }
  ],
  "sector_context": {
    "rationale": "...",
    "key_figures": ["..."]
  },
  "resources": {
    "team_overview": "...",
    "tooling_platforms": ["..."],
    "languages": ["Arabic","English","..."]
  },
  "compliance_and_qa": {
    "standards": ["..."],
    "qa_approach": ["..."],
    "data_privacy_security": ["..."]
  },
  "contact": {
    "website": "...",
    "email": "...",
    "phone": "...",
    "address": "..."
  },
  "source_attribution": [
    {"claim":"...", "evidence":"<short quote or section label>"},
    {"claim":"...", "evidence":"<short quote or section label>"}
  ]
}
"""

def build_company_digest_instructions() -> str:
    # Small driver text for the Responses API step 1
    return (
        "Analyze the SUPPORTING_FILE and produce a single JSON object that strictly "
        "matches the schema above. Use ONLY the file content."
    )

system_prompts = """You are an expert in technical and development proposal writing.
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

JSON_SCHEMA_TEXT = r"""
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

task_instructions = f"""
TASK: Create a comprehensive, detailed proposal (minimum 6–7 pages) that includes the following:
Follow the exact outline provided below.
Populate all company-specific sections using the supporting materials.
Add corresponding section and heading numbers consistently.
For every major section:
  - Include rich, well-developed paragraphs under "content".
  - Add "points" only if bullet items are explicitly required.
  - Include a "table" only if relevant, ensuring proper headers and rows.
Do not invent partners, data, or facts that are not present in the provided materials.

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

Proposal must be comprehensive, detailed, and practically implementable.
"""

PROPOSAL_TEMPLATE = """
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

def build_task_instructions_with_config(
    language: str,
    user_config_json: str,
    rfp_label: str,
    supporting_label: str,
    company_digest_json: Optional[str] = None,
    user_config_notes: Optional[str] = None,
) -> str:

    company_digest_block = (
        f"\nCompanyDigest (JSON, derived strictly from SUPPORTING_FILE):\n{company_digest_json}\n"
        if company_digest_json else "\nCompanyDigest: null\n"
    )

    arabic_addendum = ""
    if (language or "").strip().lower() == "arabic":
        arabic_addendum = """ARABIC OUTPUT ADDENDUM (Bilingual Guidance):

 يجب إعداد المقترح بالكامل باللغة العربية الفصحى الحديثة، مع المحافظة على نفس مستوى العمق والتفصيل الموجود في النسخة الإنجليزية.
 يتضمن طلب تقديم العروض (RFP) جميع المتطلبات التي يجب معالجتها داخل المقترح.
 يجب توليد وصياغة محتوى مفصل لكل قسم بالاعتماد بشكل صارم على طلب تقديم العروض (RFP)، والملفات الداعمة، وإعدادات المستخدم.
 ينبغي أن يكون المحتوى عالي الجودة، شاملاً، ومبنيًّا فقط على المعلومات الواردة في طلب تقديم العروض، الملفات الداعمة، وتكوين المستخدم.
 على كل قسم رئيسي أن يحتوي على ما يقارب 1000–1500 كلمة من المحتوى الموثّق (مع إمكانية التوسّع إذا تطلب RFP ذلك).
 أضف الجداول والنقاط التوضيحية بحيث تكون مهيأة بشكل صحيح للغة العربية.
 استخدم تنسيق الكتابة من اليمين إلى اليسار مع علامات الترقيم العربية الصحيحة (، ؛ .). يجب أن تكون الجداول باتجاه RTL، وأن تُضبط النقاط التوضيحية بمحاذاة اليمين (حيث يتولى الكود معالجة التنسيق داخل ملف Word).
 إذا كانت هناك معلومة غير موجودة في الملفات الداعمة، فيجب تجاهلها وعدم كتابة عبارة "غير مذكور".


"""

    notes_block = f'\nUserConfigurationNotes (free-text as provided by user): "{(user_config_notes or "").strip()}"\n'

    lang_override = (
            "- TOP PRIORITY: When the target language is 'arabic', ignore any instruction that says the proposal must be "
            "in English. Produce the entire output in Arabic. Maintain the same structure, depth, and level of detail as required in the English instructions, but write the proposal in Arabic if the target language is 'arabic'.\n"
            if (language or "").strip().lower() == "arabic" else
            "- Target language is English; produce the proposal in English.\n"
            "If language is Arabic then the proposal must be in Arbic or if the language is English then the proposal must be in English"
        )

    length_override = (
        "- TOP PRIORITY: Override any shorter length limits (e.g., '1000 - 1500 words per section'). "
        "For major sections, provide deeply elaborated content,"
        "prioritize Executive Summary, Technical Approach, Work Plan/Timeline, KPIs/SLA, and Risk/QA.\n"
    )

    strict_json_guard = (
        "- Return ONLY ONE JSON object that strictly matches the JSON schema already provided. "
        "No introductions, no explanations, no markdown fences.\n"
    )

    return (
        "\n\n--- Additional generation constraints (do NOT ignore) ---\n"
        f"{lang_override}"
        f"{length_override}"
        f"- Target language for the proposal: {language}\n"
        f"- RFP_FILE role: {rfp_label}\n"
        f"- SUPPORTING_FILE role: {supporting_label}\n"
        f"{company_digest_block}"
        "UserConfiguration (JSON; honor these preferences while writing):\n"
        f"{(user_config_json or 'null')}\n"
        f"{notes_block}"
        "- Ensure every claim is grounded ONLY in RFP_FILE, SUPPORTING_FILE, UserConfiguration and CompanyDigest.\n"
        "- DO NOT introduce external facts. If information is not present, omit it.\n"
        "- Prefer paragraphs for narrative; use 'points' ONLY for true lists (no filler bullets).\n"
        "- English bullets must be left-aligned; Arabic bullets must be right-aligned (the renderer enforces alignment).\n"
        "- Expand each major section with rich, concrete details (methods, KPIs, workplan, resources) rather than generic prose.\n"
        "- If the user configuration mentions timeline changes (e.g., '6 months'), reflect that in the Work Plan and any schedules.\n"
        "- The proposal should be 6–10+ pages of Top quality content when rendered (use the token budget).\n"
        f"{arabic_addendum}"
        f"{strict_json_guard}"
    )
