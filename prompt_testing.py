import os
from pathlib import Path
from typing import Optional, List
import logging
import json, re
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential, RetryError
from dotenv import load_dotenv
from pymilvus import connections, Collection, MilvusException
from openai import OpenAI
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("wordgen-agent")


load_dotenv(encoding="utf-8-sig", override=True)


def _normalize_sections(data: dict[str, any]) -> dict[str, any]:
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

def _json_only(text: str) -> dict[str, any]:
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
            cleaned = _sanitize_json_text(content)
            return cleaned

        except RetryError as re:
            logger.error(f"OpenAI request failed after retries: {re}")
            raise HTTPException(status_code=500, detail="OpenAI request failed after retries")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
def generate_proposal_with_openai(rfp_text: str, native_language: str,supporting_materials: str) -> str: # type: ignore
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

        Ensure each section contains:
        1. Detailed explanation of the topic
        2. Specific examples and practical cases
        3. Clear methodologies
        4. Specific timelines
        5. Performance measurement indicators

        The proposal must be comprehensive, detailed, and practically implementable."""
    

    proposal_template = """
        Proposal Title: `provide Proposal Title`
        Prepared by: `provide Company Name`

        1) Executive Summary
        2) Company Introduction
        3) Understanding of the RFP and Objectives
        4) Technical Approach and Methodology
            4.1 Framework Overview
            4.2 Phased Methodology
            4.3 Methodological Pillars
        5) Relevant Experience and Case Evidence
        6) Project Team and Roles
        7) Work Plan, Timeline, and Milestones
        8) Quality Assurance and Risk Management
        9) KPIs and Service Levels
        10) Data Privacy, Security, and IP
        11) Compliance with RFP Requirements
        12) Deliverables Summary
        13) Assumptions
        14) Pricing Approach (Summary)
        15) Why [Your Company]
        """
    
    
    messages = [
        {
            "role": "system", 
            "content": system_prompts
        },
        {
            "role": "user", 
            "content": (
                f"RFP DOCUMENT (Requirements & Specifications):\n" + (rfp_text or "")[:60000] + "\n\n"
                f"COMPANY BACKGROUND AND SUPPORTING MATERIALS:\n{supporting_materials}\n\n"
                f"\n\n{task_instructions}\n\n"
                f"IMPORTANT: The proposal must follow this structure exactly:\n"
                f"{proposal_template}\n\n"
                f"IMPORTANT: The entire proposal must be written in {native_language}. "
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
    print("Raw response:", raw)
    data = _json_only(raw)  
    return json.dumps(data, ensure_ascii=False)





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
        connections.connect(**connect_kwargs) # type: ignore
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Milvus connection failed: {exc}")
    
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
    


uuid = "7ad6986e-2ac1-46b1-a983-f22ace46ab1a"


def fetch_supportive_files_text_by_uuid(uuid: str) -> str:
    """Fetch concatenated text from supportive_files collection for a given folder_name (uuid)."""
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

rfp_text = fetch_rfp_text_by_uuid(str(uuid))
if not rfp_text:
    raise HTTPException(status_code=404, detail="No RFP knowledge found for provided uuid")

logger.info(f"Retrieved {len(rfp_text)} characters of RFP text for uuid {uuid}")

supporting_materials_json = fetch_supportive_files_text_by_uuid(str(uuid))
if not supporting_materials_json:
    logger.info(f"No supportive files found for uuid {uuid}")
    supporting_materials = ""

supporting_materials = generate_company_profile_json(supporting_materials_json)

final=generate_proposal_with_openai(rfp_text, "english", supporting_materials=supporting_materials)
print(final)
















