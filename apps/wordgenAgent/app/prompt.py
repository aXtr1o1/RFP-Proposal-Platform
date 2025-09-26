import os
from typing import Optional

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.2"))
MAX_OUTPUT_TOKENS = int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "12000"))

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

Proposal must be comprehensive, detailed, and practically implementable.
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

def build_task_instructions_with_config(
    language: str,
    user_config_json: str,
    rfp_label: str,
    supporting_label: str,
    company_digest_json: str | None = None,
) -> str:
    company_digest_block = (
        f"\nCompanyDigest (JSON, derived strictly from SUPPORTING_FILE):\n{company_digest_json}\n"
        if company_digest_json else "\nCompanyDigest: null\n"
    )

    arabic_addendum = ""
    if (language or "").strip().lower() == "arabic":
        arabic_addendum = """
ARABIC OUTPUT ADDENDUM (bilingual guidance):
- Produce the entire proposal content in Arabic (Modern Standard Arabic), with the SAME depth and detail as the English standard.
- For each major section, write approximately 450-650 words of substantive, grounded content (not filler), unless the RFP section is inherently brief.
- Keep the same structure and section headings as specified; do not add or remove sections.
- Content must be fully grounded ONLY in RFP_FILE, SUPPORTING_FILE, and CompanyDigest, and consistent with UserConfiguration. Do NOT introduce external facts.
- Prefer paragraphs for narrative content; include 'points' ONLY for true lists.
- If a fact is missing, OMIT it rather than stating "Not specified".
- Use right-to-left layout and correct Arabic punctuation like full stop and commas. Tables must be RTL. Bullet points must be right-aligned.
"""

    return (
        "\n\n--- Additional generation constraints ---\n"
        f"- Target language for the proposal: {language}\n"
        f"- RFP_FILE role: {rfp_label}\n"
        f"- SUPPORTING_FILE role: {supporting_label}\n"
        f"{company_digest_block}"
        "UserConfiguration (JSON; if provided, respect these preferences while writing):\n"
        f"{(user_config_json or 'null')}\n"
        "Notes:\n"
        "- If any CompanyDigest field has value \"Not specified\", OMIT that detail—do not explicitly write that it is missing.\n"
        "- Prefer paragraphs; use 'points' ONLY for actual lists.\n"
        "- English bullets must be left-aligned; Arabic bullets must be right-aligned.\n"
        f"{arabic_addendum}"
    )
