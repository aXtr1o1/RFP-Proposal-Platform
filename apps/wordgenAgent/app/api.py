import os
from pathlib import Path
from typing import Optional, List
import logging
import json, re
from fastapi import FastAPI, HTTPException
import httpx
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential, RetryError
from dotenv import load_dotenv
from pymilvus import connections, Collection, MilvusException
from apps.wordgenAgent.app.proposal_clean import proposal_cleaner
from apps.wordgenAgent.app.wordcom import build_word_from_proposal
import time

try:
    from openai import OpenAI
except Exception:
    OpenAI = None  

load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env", override=False)
load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env", override=False)
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env", override=False)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("wordgen-agent")

class GenerateProposalRequest(BaseModel):
    uuid: str

class GenerateProposalResponse(BaseModel):
    status: str
    proposal_text: str
    detected_language: str

# ---------- Milvus utilities ----------

DEFAULT_CONSISTENCY = os.getenv("MILVUS_CONSISTENCY_LEVEL", "Bounded")

def _milvus_query_with_fallback(col: Collection, expr: str, output_fields: list, limit: int = 16384,
                                primary_consistency: str = DEFAULT_CONSISTENCY):
    try:
        return col.query(
            expr=expr,
            output_fields=output_fields,
            consistency_level=primary_consistency,
            limit=limit,
            timeout=60,  # seconds
        )
    except MilvusException as e:
        msg = str(e)
        if "Timestamp lag too large" in msg or "no available shard delegator" in msg:
            logger.warning(f"Milvus lag detected, retrying with Eventually + guarantee_timestamp=0: {msg}")
            try:
                return col.query(
                    expr=expr,
                    output_fields=output_fields,
                    consistency_level="Eventually",
                    limit=limit,
                    guarantee_timestamp=0, 
                    timeout=60,
                )
            except Exception as e2:
                logger.error(f"Fallback query also failed: {e2}")
                raise
        raise

def _connect_milvus() -> None:
    """Connect to Milvus using environment variables."""
    logger.info(f"milvus connection started")
    uri = os.getenv("MILVUS_URI")
    user = os.getenv("MILVUS_USER")
    password = os.getenv("MILVUS_PASSWORD")

    connect_kwargs = {"alias": "default"}

    if uri:
        connect_kwargs["uri"] = uri
        logger.info(f"milvus connected")

    if user and password:
        connect_kwargs["user"] = user
        connect_kwargs["password"] = password

    try:
        connections.connect(**connect_kwargs)  # type: ignore
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Milvus connection failed: {exc}")

def fetch_rfp_text_by_uuid(uuid: str) -> str:
    """Fetch concatenated text from rfp_files collection for a given folder_name (uuid)."""
    _connect_milvus()
    
    try:
        col = Collection("rfp_files")
        col.load()
        
        expr = f'folder_name == "{uuid}"'
        logger.info(f"Milvus query expr: {expr} on collection: rfp_files")
        
        results = _milvus_query_with_fallback(
            col,
            expr=expr,
            output_fields=["content", "chunk_index", "file_name"],
            limit=16384,
        )
        
        logger.info(f"Milvus query returned {len(results)} rows for uuid={uuid}")
        
        try:
            results.sort(key=lambda r: r.get("chunk_index", 0))
        except Exception as sort_exc:
            logger.warning(f"Sort warning: {sort_exc}")
        
        texts: List[str] = [r.get("content", "") for r in results if r.get("content")]
        return "\n\n".join(texts)
        
    except Exception as exc:
        logger.exception("Milvus query failed")
        raise HTTPException(status_code=500, detail=f"Milvus query failed: {exc}")

# def fetch_supportive_files_text_by_uuid(uuid: str) -> str:
#     """Fetch concatenated text from supportive_files collection for a given folder_name (uuid)."""
#     conn = _connect_milvus()
    
#     try:
#         col = Collection("supportive_files")
#         col.load()
        
#         expr = f'folder_name == "{uuid}"'
#         logger.info(f"Milvus query expr: {expr} on collection: supportive_files")
#         results = _milvus_query_with_fallback(
#             col,
#             expr=expr,
#             output_fields=["content", "chunk_index", "file_name"],
#             limit=16384,
#         )
        
#         logger.info(f"Milvus query returned {len(results)} rows for uuid={uuid}")
        
#         try:
#             results.sort(key=lambda r: r.get("chunk_index", 0))
#         except Exception as sort_exc:
#             logger.warning(f"Sort warning: {sort_exc}")
        
#         texts: List[str] = [r.get("content", "") for r in results if r.get("content")]
#         return "\n\n".join(texts)
        
#     except Exception as exc:
#         logger.exception("Milvus query failed")
#         raise HTTPException(status_code=500, detail=f"Milvus query failed: {exc}")


def fetch_supportive_files_text_by_uuid(uuid: str) -> str:
    """Fetch concatenated text from rfp_files collection for a given folder_name (uuid)."""
    _connect_milvus()
    
    try:
        col = Collection("supportive_files")
        col.load()
        
        expr = f'folder_name == "{uuid}"'
        logger.info(f"Milvus query expr: {expr} on collection: supportive_files")
        
        results = _milvus_query_with_fallback(
            col,
            expr=expr,
            output_fields=["content", "chunk_index", "file_name"],
            limit=16384,
        )
        
        logger.info(f"Milvus query returned {len(results)} rows for uuid={uuid}")
        
        try:
            results.sort(key=lambda r: r.get("chunk_index", 0))
        except Exception as sort_exc:
            logger.warning(f"Sort warning: {sort_exc}")
        
        texts: List[str] = [r.get("content", "") for r in results if r.get("content")]
        return "\n\n".join(texts)
        
    except Exception as exc:
        logger.exception("Milvus query failed")
        raise HTTPException(status_code=500, detail=f"Milvus query failed: {exc}")

#---------------------services-----------------------------


def _normalize_sections(data: dict[str, any]) -> dict[str, any]: # type: ignore
    """Ensure sections only contain allowed keys and have correct shapes."""
    allowed_section_keys = {"heading", "content", "points", "table"}
    if "sections" in data and isinstance(data["sections"], list):
        normalized = []
        for sec in data["sections"]:
            if not isinstance(sec, dict): 
                continue
            cleaned = {k: v for k, v in sec.items() if k in allowed_section_keys}
            # coerce types
            if "heading" in cleaned and not isinstance(cleaned["heading"], str):
                cleaned["heading"] = str(cleaned["heading"])
            if "content" in cleaned and not isinstance(cleaned["content"], str):
                cleaned["content"] = str(cleaned["content"])
            # points
            if "points" in cleaned:
                if not isinstance(cleaned["points"], list):
                    cleaned.pop("points", None)
                else:
                    cleaned["points"] = [str(p) for p in cleaned["points"] if isinstance(p, (str,int,float))]
                    if not cleaned["points"]:
                        cleaned.pop("points", None)
            # table
            if "table" in cleaned:
                tbl = cleaned["table"]
                if not isinstance(tbl, dict):
                    cleaned.pop("table", None)
                else:
                    headers = tbl.get("headers")
                    rows = tbl.get("rows")
                    if not (isinstance(headers, list) and all(isinstance(h, (str,int,float)) for h in headers)):
                        cleaned.pop("table", None)
                    elif not (isinstance(rows, list) and all(isinstance(r, list) for r in rows)):
                        cleaned.pop("table", None)
                    else:
                        cleaned["table"] = {
                            "headers": [str(h) for h in headers],
                            "rows": [[str(c) for c in r] for r in rows]
                        }
            # require heading & content
            if "heading" in cleaned and "content" in cleaned:
                normalized.append(cleaned)
        data["sections"] = normalized
    return data

def _json_only(text: str) -> dict[str, any]: # type: ignore
    """Parse JSON strictly; raise if invalid."""
    try:
        obj = json.loads(text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Model did not return valid JSON: {e}")
    if not isinstance(obj, dict) or "title" not in obj or "sections" not in obj:
        raise HTTPException(status_code=500, detail="JSON missing required keys: 'title' and 'sections'.")
    if not isinstance(obj["title"], str):
        obj["title"] = str(obj["title"])
    obj = _normalize_sections(obj)
    return obj


# ---------- LLM utilities ----------


def generate_company_profile_json(supporting_materials: str) -> str:
    """Generate a detailed company profile JSON from supporting materials."""
    if OpenAI is None:
        raise HTTPException(status_code=500, detail="openai package not available")
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not set")

    MAX_SUPPORTING_LEN = 80_000  # ~80k chars as a soft cap
    sm = supporting_materials.strip()
    if len(sm) > MAX_SUPPORTING_LEN:
        sm = sm[:MAX_SUPPORTING_LEN] + "\n\n[TRUNCATED]\n"

    company_digest_system = """You are an expert proposal analyst.
            Extract a structured, comprehensive CompanyDigest (JSON) from the provided 'supporting_text'.
            Rules:
            - Use ONLY information in supporting_text; no external facts.
            - Translate Arabic to English for the digest, but preserve proper nouns (institutions, programs) in Arabic with an English gloss if known.
            - If a field is missing, use "Not specified".
            - Keep it concise but complete; don't exceed ~1200 tokens.
            - Include 'source_attribution' with brief quotes/section labels from supporting_text for key claims.
            """

    company_digest_user = f"""
    supporting_text (verbatim):
    ---
    {supporting_materials}
    ---

    Produce JSON with this exact schema:

    {{
    "company_profile": {{
        "legal_name": "...",
        "brand_name": "...",
        "hq_location": "...",
        "founded_year": "...",
        "mission": "...",
        "vision": "...",
        "values": ["..."]
    }},
    "capabilities": {{
        "domains": ["..."],                 # e.g., الحج والعمرة experience mgmt, PMO, training
        "services": ["..."],                # consulting, program design, CX, PMO, pricing studies, etc.
        "methodologies": ["..."],           # e.g., best practices tailoring, impact measurement
        "differentiators": ["..."],         # deep sector expertise, network, etc.
        "partners": ["..."]                 # notable local/international partners
    }},
    "track_record": [
        {{
        "project_title": "...",
        "client": "...",
        "year_or_period": "...",
        "scope_summary": "...",
        "outcomes_kpis": ["...","..."]
        }}
    ],
    "sector_context": {{
        "rationale": "...",                 # Vision 2030 alignment; scale figures
        "key_figures": ["..."]              # e.g., 30M target, 22.5M in 2019, etc. (only if present in text)
    }},
    "resources": {{
        "team_overview": "...",             # experts, national+intl blend
        "tooling_platforms": ["..."],       # if any
        "languages": ["Arabic","English", "..."]
    }},
    "compliance_and_qa": {{
        "standards": ["..."],
        "qa_approach": ["..."],
        "data_privacy_security": ["..."]
    }},
    "contact": {{
        "website": "...",
        "email": "...",
        "phone": "...",
        "address": "..."
    }},
    "source_attribution": [
        {{"claim":"deep sector expertise","evidence":"<short quote or section label>"}},
        {{"claim":"partners list","evidence":"<short quote or section label>"}}
    ]
    }}
    """


    messages = [
        {
            "role": "system", 
            "content": company_digest_system
        },
        {
            "role": "user", 
            "content": company_digest_user
        }
    ]

    def _sanitize_json_text(txt: str) -> str:
        # Strip common wrappers like ```json ... ```
        t = txt.strip()
        if t.startswith("```"):
            t = t.strip("`")
            # remove potential leading 'json'
            if t.lower().startswith("json"):
                t = t[4:].lstrip()
        # Trim anything before first '{' and after last '}'
        l = t.find("{")
        r = t.rfind("}")
        if l != -1 and r != -1 and r > l:
            t = t[l:r+1]
        return t.strip()

    import httpx
    timeout = httpx.Timeout(20.0, connect=10.0, read=30.0, write=30.0)
    with httpx.Client(timeout=timeout) as http_client:
        client = OpenAI(api_key=api_key, http_client=http_client)

        messages = [
            {"role": "system", "content": company_digest_system},
            {"role": "user", "content": company_digest_user},
        ]

        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,  # type: ignore
                temperature=0.25,
                max_tokens=2200,
                response_format={"type": "json_object"},  # <- key line
            )
            logger.info("OpenAI response received for company profile generation")
            content = resp.choices[0].message.content if resp and resp.choices else ""

            # Sanitize & parse
            cleaned = _sanitize_json_text(content) #type:ignore
            return cleaned

        except RetryError as re:
            logger.error(f"OpenAI request failed after retries: {re}")
            raise HTTPException(status_code=500, detail="OpenAI request failed after retries")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
def generate_proposal_with_openai(rfp_text: str, native_language: str,supporting_materials: str, user_config: str) ->dict: # type: ignore
    """Generate a comprehensive proposal from RFP text in the native language."""
    if OpenAI is None:
        raise HTTPException(status_code=500, detail="openai package not available")
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not set")
    
    http_client = httpx.Client()
    client = OpenAI(api_key=api_key, http_client=http_client)
    
    system_prompts ="""You are an expert in technical and development proposal writing.
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
    
    JSON_SCHEMA_TEXT = """
        Return ONLY a JSON object with this exact structure and keys (no extra keys, no prose):

        {
        "title": "Professional proposal title reflecting client name and project scope"
        "title": "string",
        "sections": [
            {
            "heading": "string",
            "content": "string",
            "points": ["string", "..."]    // include ONLY if bullet points exist; otherwise omit this key
            ,
            "table": {                      // include ONLY if this section has a table; otherwise omit this key
                "headers": ["string", "..."],
                "rows": [["string","..."], ["string","..."]]
            }
            }
        ]
        }
        """

    task_instructions = f"""TASK: Create a comprehensive, detailed proposal in {native_language} (minimum 6-7 pages) that includes:
                following the exact outline below. Populate company-specific parts from the supporting materials.
        For every major section, include rich paragraphs in "content", add "points" only if there are bullet items,
        and include a "table" only if a table is relevant (with headers and rows). Do NOT invent partners or facts not present.
        {JSON_SCHEMA_TEXT}
        For each section, provide:
        - Detailed, comprehensive content (200-400 words)
        - Specific key points (3-5 points per section)
        - Explanatory tables with detailed data where appropriate

        Instruction for Generating Proposal Title and Prepared By Line:
        Proposal Title:
            - Create a concise, professional title that clearly reflects the RFP subject and the company’s solution or offering.
            - Include the client name or project name if specified in the RFP.
            - Ensure the title is specific, relevant, and aligned with the proposal content.
            - Use professional language; avoid generic terms like “proposal,” “submission,” or “offer.”
            - Keep it engaging, clear, and suitable for formal business documents.
            - Include a “Prepared by” in the title itself naturally.
            - Reflect understanding of the RFP and supporting materials.
            - Include the name(s) of the individual(s) or company preparing the proposal in the prepared by.


        Ensure each section contains:
        1. Detailed explanation of the topic
        2. Specific examples and practical cases
        3. Clear methodologies
        4. Specific timelines
        5. Performance measurement indicators

        The proposal must be comprehensive, detailed, and practically implementable.

        --- USER CUSTOM CONFIGURATION ---
        {user_config}
        use this to add tone, structure, and specific requirements to the proposal.
        [NON-NEGOTIABLE DIRECTIVES]
        • Treat USER_CONFIG as binding contract requirements.
        • For each directive in USER_CONFIG, add a dedicated section in "sections" with a precise heading.

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
    
    
    messages = [
        {
            "role": "system", 
            "content": system_prompts
        },
        {
            "role": "user", 
            "content": (
                f"RFP DOCUMENT (Requirements & Specifications):\n" + (rfp_text or "") + "\n\n"
                f"COMPANY BACKGROUND AND SUPPORTING MATERIALS:\n{supporting_materials}\n\n"
                f"\n\n{task_instructions}\n\n"
                f"IMPORTANT: The proposal must follow this structure exactly:\n"
                f"{proposal_template}\n\n"
                f"IMPORTANT: The entire proposal must be written in {native_language}.(including headings).\n"
                f"Each section must have detailed content (200-400 words), bullet points, and tables where relevant. "
                f"No placeholder text—provide actual detailed content."
            )
        }
    ]

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,  # type: ignore
        temperature=0.5, 
        max_tokens=16000,
        response_format={"type": "json_object"},  
    )

    raw = resp.choices[0].message.content if resp and resp.choices else ""
    raw_prased=json.loads(str(raw))
    # print(raw_prased)
    return raw_prased





# ---------- API Endpoints ----------

def generate_proposal(uuid , doc_config, language , user_config):
    """Generate a detailed proposal text from RFP files in Milvus collection in the native language."""
    try:
        logger.info("SLEEPING FOR 2 SECONDS")
        time.sleep(2)
        rfp_text = fetch_rfp_text_by_uuid(str(uuid).strip())
        if not rfp_text:
            raise HTTPException(status_code=404, detail="No RFP knowledge found for provided uuid")
        
        logger.info(f"Retrieved {len(rfp_text)} characters of RFP text for uuid {uuid}")
        supportive_text = fetch_supportive_files_text_by_uuid(str(uuid).strip())
        if not supportive_text:
            logger.warning(f"No supportive files found for the provided uuid {uuid}. Proceeding without it.")
            supportive_text = ""  
        
        logger.info(f"Retrieved {len(supportive_text)} characters of supportive files text for uuid {uuid}")
        native_language = language
        logger.info(f"Detected native language: {native_language}")
        supportive_materials = generate_company_profile_json(supportive_text)
        proposal_dict = generate_proposal_with_openai(rfp_text, native_language, supportive_materials, user_config)
        logger.info(f"Generated proposal JSON with {proposal_dict} characters")
        # print('this is the type paathukoo',{type(proposal_dict)})
        

        try:

            output_path = build_word_from_proposal(proposal_dict, output_path=f"output/{uuid}.docx", visible=False , user_config=doc_config, language=native_language)
            return output_path
        except Exception as word_error:
            logger.error(f"Word document generation failed: {word_error}")
        
        
    except RetryError as rex:
        cause = getattr(rex, "last_attempt", None)
        root_exc = None
        try:
            if cause is not None:
                exc_attr = getattr(cause, "exception", None)
                if callable(exc_attr):
                    root_exc = exc_attr()
                else:
                    root_exc = exc_attr
        except Exception:
            root_exc = None
        msg = f"OpenAI retry failed: {type(root_exc).__name__ if root_exc else type(rex).__name__}: {root_exc or rex}"
        logger.exception(msg)
        raise HTTPException(status_code=502, detail=msg)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unhandled error in generate_proposal")
        raise HTTPException(status_code=500, detail=str(exc))
    






# ---------- Architecture Diagram Integration ----------



# def generate_and_integrate_architecture_diagram(proposal_dict: dict, rfp_text: str, native_language: str) -> dict:
#     """
#     Generate architecture diagram and integrate it into the proposal.
#     """
#     try:
#         from apps.wordgenAgent.app.architecture_diagram import ProposalArchitectureDiagramGenerator
        
#         logger.info("Starting architecture diagram generation")
#         diagram_generator = ProposalArchitectureDiagramGenerator()
#         diagram_result = diagram_generator.generate_architecture_diagram_from_proposal(
#             proposal_dict, rfp_text, native_language
#         )
        
#         if not diagram_result.get("success"):
#             logger.warning(f"Architecture diagram generation failed: {diagram_result.get('error')}")
#             return proposal_dict  
#         diagram_section = diagram_result.get("diagram_section")
#         if not diagram_section:
#             logger.warning("No diagram section returned")
#             return proposal_dict
#         enhanced_proposal = integrate_diagram_section_with_openai(
#             proposal_dict, diagram_section, native_language
#         )
        
#         logger.info("✅ Architecture diagram successfully integrated into proposal")
#         return enhanced_proposal
        
#     except Exception as e:
#         logger.error(f"Error in architecture diagram integration: {e}")
#         return proposal_dict  

# def integrate_diagram_section_with_openai(proposal_dict: dict, diagram_section: dict, native_language: str) -> dict:
#     """
#     Use OpenAI to intelligently place the architecture diagram section in the proposal.
#     """
#     if OpenAI is None:
#         logger.warning("OpenAI not available, using fallback placement")
#         return _fallback_diagram_placement(proposal_dict, diagram_section)
    
#     api_key = os.getenv("OPENAI_API_KEY")
#     if not api_key:
#         logger.warning("OpenAI API key not available, using fallback placement")
#         return _fallback_diagram_placement(proposal_dict, diagram_section)
    
#     try:
#         import httpx
#         http_client = httpx.Client()
#         client = OpenAI(api_key=api_key, http_client=http_client)
        
#         placement_prompts = {
#             "Arabic": """
#             أنت خبير في كتابة المقترحات التقنية. لديك مقترح كامل وقسم جديد للهندسة التقنية.
            
#             مهمتك: تحديد أفضل مكان لإدراج قسم الهندسة التقنية في المقترح.
            
#             المقترح الحالي (العناوين فقط):
#             {section_headings}
            
#             قسم الهندسة التقنية الجديد:
#             العنوان: {diagram_heading}
            
#             أعد ترتيب أقسام المقترح مع إدراج قسم الهندسة التقنية في المكان المناسب.
#             أعد قائمة بترتيب العناوين الجديد فقط.
#             """,
            
#             "English": """
#             You are an expert technical proposal writer. You have a complete proposal and a new technical architecture section.
            
#             Your task: Determine the best placement for the technical architecture section within the proposal.
            
#             Current proposal (headings only):
#             {section_headings}
            
#             New technical architecture section:
#             Heading: {diagram_heading}
            
#             Reorder the proposal sections with the technical architecture section in the most appropriate location.
#             Return only the new ordering of headings.
#             """
#         }
#         current_sections = proposal_dict.get("sections", [])
#         section_headings = [section.get("heading", "") for section in current_sections]
        
#         prompt_template = placement_prompts.get(native_language, placement_prompts["Arabic"])
#         placement_prompt = prompt_template.format(
#             section_headings="\n".join([f"{i+1}. {heading}" for i, heading in enumerate(section_headings)]),
#             diagram_heading=diagram_section.get("heading", "")
#         )
        
#         response = client.chat.completions.create(
#             model="gpt-4o-mini",
#             messages=[
#                 {"role": "system", "content": "You are a proposal structure expert. Provide optimal section ordering."},
#                 {"role": "user", "content": placement_prompt}
#             ],
#             temperature=0.2,
#             max_tokens=500
#         )
#         ai_response = response.choices.message.content.strip() # type: ignore
#         logger.info(f"AI placement suggestion received: {ai_response[:100]}...")
#         return _smart_diagram_placement(proposal_dict, diagram_section, ai_response)
        
#     except Exception as e:
#         logger.error(f"Error in AI-powered diagram placement: {e}")
#         return _fallback_diagram_placement(proposal_dict, diagram_section)

# def _smart_diagram_placement(proposal_dict: dict, diagram_section: dict, ai_suggestion: str) -> dict:
#     """
#     Smart placement of diagram section based on AI suggestion and proposal structure.
#     """
#     sections = proposal_dict.get("sections", [])
    
#     technical_keywords = ["technical", "تقني", "scope", "نطاق", "requirements", "متطلبات", "solution", "حل"]
    
#     best_position = len(sections) // 2  
    
#     for i, section in enumerate(sections):
#         heading = section.get("heading", "").lower()
#         if any(keyword in heading for keyword in technical_keywords):
#             best_position = i + 1
#             break
#     best_position = min(best_position, len(sections))
#     sections.insert(best_position, diagram_section)
#     proposal_dict["sections"] = sections
    
#     logger.info(f"Architecture diagram placed at position {best_position + 1}")
#     return proposal_dict

# def _fallback_diagram_placement(proposal_dict: dict, diagram_section: dict) -> dict:
#     """
#     Fallback method to place diagram section (after first 2 sections).
#     """
#     sections = proposal_dict.get("sections", [])
#     insert_position = min(2, len(sections))
#     sections.insert(insert_position, diagram_section)
    
#     proposal_dict["sections"] = sections
#     logger.info(f"Architecture diagram placed at fallback position {insert_position + 1}")
#     return proposal_dict
