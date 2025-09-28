import os
from typing import Optional

MODEL = os.getenv("OPENAI_MODEL", "gpt-5")

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

COMPANY_DIGEST_SCHEMA =r"""
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
    return "Analyze SUPPORTING_FILE and produce one JSON object matching schema above, using only the file."

system_prompts = """You are an expert in technical and development proposal writing both (Arabic and English).
                    Your task is to create a comprehensive, detailed proposal in English (minimum 6-7 pages, 1000 - 1500 words) that:
                    1. Addresses ALL RFP requirements and evaluation criteria with extensive specific details
                    2. Includes comprehensive technical approach, clear methodology, and detailed timeline with complete explanations
                    3. Covers compliance, certifications, and qualifications comprehensively with specific examples
                    4. Has detailed sections for pricing, terms, and conditions with clear explanations
                    5. Includes all required forms, matrices, and appendices with complete content
                    6. Follows the exact structure and language required by the RFP
                    7. Provides substantial, detailed content under each section (minimum 100 - 150 words per major section)
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

JSON_SCHEMA_TEXT =  r"""
                      Return ONLY a JSON object with this exact structure and keys (no extra keys, no prose, no extra wordings expect the JSON object):

                      {
                      "title": "Professional proposal title reflecting company name and project scope",
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
                    TASK: Write detailed proposal (6–7 pages, 1000-1500 words) using RFP, Supporting file, User Config, and CompanyDigest.
                    - Each section: 100 - 150 words (elaborate if short in RFP).
                    - Populate company-specific sections with supporting materials.
                    - Use rich paragraphs in 'content'; points/tables only if relevant.
                    - DO NOT invent partners/facts.

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
                    """

PROPOSAL_TEMPLATE = """
                    Here is the Headings and the sub-heading I wanted in the proposal,
                    [Professional Proposal Title reflecting RFP and company solution alongwith Prepared By]

                    Executive Summary
                    Company Introduction
                    Understanding of the RFP and Objectives
                    Technical Approach and Methodology
                        - Framework Overview
                        - Phased Methodology
                        - Methodological Pillars
                    Project Architecture
                        - System Components
                        - Data Flow & Integration
                        - Technology Stack
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
    
    company_digest_block = f"\nCompanyDigest:\n{company_digest_json}\n" if company_digest_json else "\nCompanyDigest: null\n"
    
    notes_block = f'\nUserNotes: "{(user_config_notes or "").strip()}"\n'
    
    arabic_addendum = ""
    if (language or "").lower() == "arabic":
        arabic_addendum = f"""
                          ARABIC Instructions:
                          - Generate the proposal in Modern Standard Arabic about 1000 - 1500 words.
                          - Output the entire proposal in Arabic (Modern Standard Arabic): titles, headings, sub-headings and content.
                          - Ensure the Arabic content is correct, coherent, and of high quality, strictly based on the RFP files, Supporting files (Company Digest), and User Configuration.
                          - Do not include filler or unnecessary text; generate only high-quality content.
                          - The proposal must be entirely in Arabic, with no English words unless absolutely necessary.
                          - Use only information from the RFP, Supporting files, and User Configuration.
                          - Each section must contain at least 200 words.
                          - Tables and bullet points must be right-to-left (RTL) aligned.
                          - Try to use this template while generating the proposal: {PROPOSAL_TEMPLATE}
                          - Follow the strict {JSON_SCHEMA_TEXT}. Do not add any content before or after the JSON schema. Do not include labels like 'Generated Proposal' or 'Draft'—only return the JSON schema as it is.
                          - Return ONLY one JSON object, with no wrappers or extra text.
                          """


    return (
        f"- Target language: {language}\n"
        f"RFP_FILE:\n{rfp_label} Contains the project details.\n"
        f"SUPPORTING_FILE:\n{supporting_label} Contains the company details.\n"
        f"About the company:\n{company_digest_block}\n"
        f"UserConfig:\n{user_config_json or 'null'}\n"
        f"{notes_block}\n"
        "Do not write phrases such as 'the RFP mentions this, but based on the user config we updated that.' Instead, directly update and adapt the proposal accordingly. The proposal must be fully revised based on the RFP, Supporting File, and User Configuration—without explicitly stating these sources."
        "Based on the UserConfiguration change the entire proposal"
        f"{PROPOSAL_TEMPLATE} — analyze this template and maintain its structure while generating the proposal.\n"
        "- Keep this proposal template structure exactly as is, with all headings and sub-headings.\n"
        f"{JSON_SCHEMA_TEXT}\n"
        "- The title must include the company name and scope.\n"
        "- Each section must contain at least 100–200 words (e.g., methods, KPIs, timelines).\n"
        "- Apply UserNotes preferences to the corresponding sections.\n"
        "- The RFP takes precedence over user preferences.\n"
        "- Do not invent or add external facts.\n"
        "- Bind CompanyDigest: Use fields from BEGIN_COMPANY_DIGEST_JSON for the “Company Introduction,” “Relevant Experience and Case Evidence,” and “Why [Your Company]” sections. Replace any placeholders like “[Your Company]” or “[Year]” with values from company_profile.brand_name / founded_year, if available.\n"
        "- Bind UserConfigurationNotes: Apply each directive to the appropriate section (e.g., timeline → Work Plan/Timeline, emphasis → Company Introduction/Why Us). Do not create new sections or keys.\n"
        "- Do not terminate early; continue elaborating until the token limit is reached.\n"
        "- Output must contain only one JSON object.\n"
        f"{arabic_addendum}"
    )
