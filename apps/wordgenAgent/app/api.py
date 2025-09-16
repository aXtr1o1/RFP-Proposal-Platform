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

from apps.wordgenAgent.app.proposal_clean import proposal_cleaner
from apps.wordgenAgent.app.wordcom import build_word_from_proposal

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
    host = os.getenv("MILVUS_HOST", "localhost")
    port = int(os.getenv("MILVUS_PORT", "19530"))
    secure_env = os.getenv("MILVUS_SECURE", "false").strip().lower()
    secure = secure_env in ("1", "true", "yes", "on")
    user = os.getenv("MILVUS_USER")
    password = os.getenv("MILVUS_PASSWORD")

    connect_kwargs = {
        "alias": "default",
        "host": host,
        "port": str(port),
        "secure": secure,
    }
    if user and password:
        connect_kwargs["user"] = user
        connect_kwargs["password"] = password
    
    try:
        connections.connect(**connect_kwargs)
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

# ---------- LLM utilities ----------

def _extract_chat_content(resp) -> str:
    """Extract text content from OpenAI chat response robustly."""
    try:
        choice = resp.choices[0]
        msg = getattr(choice, "message", None) or {}
        content = getattr(msg, "content", None)
        if isinstance(content, str) and content.strip():
            return content
        raise ValueError("No content returned from model")
    except Exception as exc:
        logger.exception("Failed to extract content from OpenAI response")
        raise

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
def detect_language(rfp_text: str) -> str:
    """Detect the primary language of the RFP text."""
    if OpenAI is None:
        raise HTTPException(status_code=500, detail="openai package not available")
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not set")
    
    import httpx
    http_client = httpx.Client()
    client = OpenAI(api_key=api_key, http_client=http_client)
    
    language_prompt = f"""Analyze this text and identify the primary language. Consider the following:
1. The main language used throughout the document
2. The language of technical terms and specifications
3. The language of legal and contractual language
4. The language of headings and structure

Text sample: {rfp_text[:2000]}

Respond with ONLY the language name in English (e.g., 'Arabic', 'English')."""
    
    lang_resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": language_prompt}],
        temperature=0.1,
        max_tokens=50,
    )
    detected_language = _extract_chat_content(lang_resp).strip()
    logger.info(f"Detected native language: {detected_language}")
    return detected_language

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
def generate_proposal_with_openai(rfp_text: str, native_language: str) -> str:
    """Generate a comprehensive proposal from RFP text in the native language."""
    if OpenAI is None:
        raise HTTPException(status_code=500, detail="openai package not available")
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not set")
    
    import httpx
    http_client = httpx.Client()
    client = OpenAI(api_key=api_key, http_client=http_client)
    
    system_prompts = {
        "Arabic": """أنت خبير في كتابة المقترحات التقنية والتنموية. 
مهمتك إنشاء مقترح شامل ومفصل باللغة العربية (6-7 صفحات على الأقل) يتضمن:
1. معالجة شاملة لجميع متطلبات RFP ومعايير التقييم بتفاصيل محددة ومفصلة
2. محتوى تقني مفصل ومنهجية واضحة وجدول زمني شامل مع تفسيرات كاملة
3. تغطية شاملة للامتثال والشهادات والمؤهلات بأمثلة محددة ومفصلة
4. أقسام مفصلة للتسعير والشروط والأحكام مع شروحات واضحة
5. تضمين النماذج المطلوبة والجداول والملاحق مع محتوى كامل
6. اتباع البنية واللغة الدقيقة المطلوبة في RFP
7. تقديم محتوى مفصل وشامل تحت كل قسم (على الأقل 200-400 كلمة لكل قسم رئيسي)
8. إظهار فهم عميق لمتطلبات RFP من خلال ردود مفصلة ومحددة
9. تضمين منهجيات محددة وجداول زمنية مفصلة وتسليمات واضحة
10. إظهار الخبرة المهنية والقدرة التقنية مع أمثلة محددة
11. تضمين تحليل شامل للمخاطر واستراتيجيات التخفيف
12. تقديم خطة إدارة مشروع مفصلة
13. تضمين مقاييس الأداء ومؤشرات النجاح المحددة
14. إظهار الابتكار والحلول الإبداعية
15. تقديم ضمانات الجودة ومراقبة الأداء""",
        
        "English": """You are an expert in technical and development proposal writing.
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
15. Provides quality assurance and performance monitoring frameworks"""
    }
    
    system_prompt = system_prompts.get(native_language, system_prompts["Arabic"])
    
    task_instructions = {
        "Arabic": f"""المهمة: إنشاء مقترح شامل ومفصل باللغة العربية (على الأقل 6-7 صفحات) يتضمن:

لكل قسم، قدم:
- محتوى مفصل وشامل (200-400 كلمة)
- نقاط رئيسية محددة (3-5 نقاط لكل قسم)
- جداول توضيحية مع بيانات مفصلة حيثما كان مناسباً

تأكد من أن كل قسم يحتوي على:
1. شرح مفصل للموضوع
2. أمثلة محددة وحالات عملية
3. منهجيات واضحة
4. جداول زمنية محددة
5. مؤشرات قياس الأداء

يجب أن يكون المقترح شاملاً ومفصلاً وقابلاً للتطبيق العملي.""",
        
        "English": f"""TASK: Create a comprehensive, detailed proposal in {native_language} (minimum 6-7 pages) that includes:

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
    }
    
    task_instruction = task_instructions.get(native_language, task_instructions["Arabic"])
    
    messages = [
        {
            "role": "system", 
            "content": system_prompt
        },
        {
            "role": "user", 
            "content": (
                f"RFP DOCUMENT (Requirements & Specifications):\n" + (rfp_text or "")[:60000] +
                f"\n\n{task_instruction}\n\n"
                f"IMPORTANT: The entire proposal must be written in {native_language}. "
                f"Each section must have detailed content, specific bullet points, and relevant tables. "
                f"Avoid placeholder text like 'سيتم توضيح' - instead provide actual detailed content."
            )
        }
    ]
    
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.5, 
        max_tokens=16000,  
    )
    return _extract_chat_content(resp).strip()

# ---------- Supportive content ----------

def customize_proposal_with_supportive_content_json(
    proposal_text: str, 
    supportive_text: str, 
    native_language: str = "en",
    model="gpt-4o-mini",
    temperature: float = 0.7,
    max_tokens: int = 16000
) -> dict:
    """
    generated proposal using supportive content with enhanced detail and robust JSON parsing.
    """
    if OpenAI is None:
        raise HTTPException(status_code=500, detail="openai package not available")
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not set")
    
    import httpx
    http_client = httpx.Client()
    client = OpenAI(api_key=api_key, http_client=http_client)

    try:
        prompt = f"""
أنت كاتب مقترحات خبير. لديك مسودة مقترح أولية ومعلومات شركة داعمة.
مهمتك دمجها في مقترح احترافي ومقنع ومفصل.

- استخدم المعلومات الداعمة لإبراز الخبرة والعروض
- اضمن التدفق المنطقي والنبرة المهنية
- اكتب باللغة {native_language}
- قدم محتوى مفصل وشامل لكل قسم (200-400 كلمة)
- تجنب النصوص الشكلية مثل "سيتم توضيح" - قدم محتوى فعلي
- اخرج JSON صالح فقط. لا نصوص إضافية
- استخدم علامات اقتباس مزدوجة فقط وتجنب الفواصل المنقوطة في النصوص

--- متطلبات صيغة JSON ---
يجب أن يكون الناتج النهائي كائن JSON منظم كالتالي:
{{
  "title": "عنوان المقترح الرئيسي",
  "sections": [
    {{
      "heading": "عنوان القسم",
      "content": "محتوى مفصل وشامل في شكل فقرة",
      "points": ["النقطة 1", "النقطة 2", "النقطة 3"],
      "table": {{
        "headers": ["العمود الأول", "العمود الثاني"],
        "rows": [
          ["الصف الأول - العمود الأول", "الصف الأول - العمود الثاني"],
          ["الصف الثاني - العمود الأول", "الصف الثاني - العمود الثاني"]
        ]
      }}
    }}
  ]
}}

--- معلومات الشركة الداعمة ---
{supportive_text[:3000]}

--- مسودة المقترح الأولية ---
{proposal_text[:8000]}

الآن أنشئ المقترح النهائي في صيغة JSON المطلوبة بمحتوى مفصل وشامل.
تأكد من أن JSON صالح بدون أخطاء في علامات الاقتباس أو الفواصل.
"""

        logger.info(f"Sending enhanced customization request to {model}")
    
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "أنت كاتب مقترحات خبير ومنسق JSON. أنتج JSON صالح فقط بمحتوى مفصل. استخدم علامات اقتباس مزدوجة فقط وتجنب الأحرف الخاصة."},
                {"role": "user", "content": prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens
        )

        raw_output = response.choices[0].message.content.strip()
        logger.info(f"Raw OpenAI response length: {len(raw_output)}")
        logger.info(f"Raw OpenAI response first 200 chars: {raw_output[:200]}...")
        
        final_proposal_json = _parse_json_with_fallbacks(raw_output)

        logger.info("Enhanced customized proposal generated successfully in JSON format")
        return final_proposal_json

    except Exception as exc:
        logger.exception("Error generating proposal")
        return _create_fallback_proposal(proposal_text, supportive_text, native_language)

def _parse_json_with_fallbacks(raw_output: str) -> dict:
    """
    Parse JSON with multiple fallback strategies to handle malformed responses.
    """
    logger.info("Attempting JSON parsing with fallback strategies...")
    
    try:
        if raw_output.startswith("```"):
            raw_output = raw_output.replace("```json", "").replace("```")
        
        final_proposal_json = json.loads(raw_output)
        logger.info("✅ Strategy 1: Direct JSON parsing successful")
        return final_proposal_json
    except json.JSONDecodeError as e:
        logger.warning(f"❌ Strategy 1 failed: {e}")
    
    try:
        cleaned_output = _clean_json_response(raw_output)
        final_proposal_json = json.loads(cleaned_output)
        logger.info("✅ Strategy 2: Cleaned JSON parsing successful")
        return final_proposal_json
    except json.JSONDecodeError as e:
        logger.warning(f"❌ Strategy 2 failed: {e}")
    
    try:
        json_block = _extract_json_block(raw_output)
        final_proposal_json = json.loads(json_block)
        logger.info("✅ Strategy 3: JSON block extraction successful")
        return final_proposal_json
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"❌ Strategy 3 failed: {e}")
    
    try:
        fixed_output = _fix_json_delimiters(raw_output)
        final_proposal_json = json.loads(fixed_output)
        logger.info("✅ Strategy 4: JSON delimiter fix successful")
        return fixed_output
    except json.JSONDecodeError as e:
        logger.warning(f"❌ Strategy 4 failed: {e}")
    
    try:
        if raw_output.strip().startswith('{') and 'title' in raw_output:
            import ast
            final_proposal_json = ast.literal_eval(raw_output)
            if isinstance(final_proposal_json, dict):
                logger.info("✅ Strategy 5: AST literal_eval successful")
                return final_proposal_json
    except (ValueError, SyntaxError) as e:
        logger.warning(f"❌ Strategy 5 failed: {e}")
    
    logger.error("All JSON parsing strategies failed, creating fallback proposal")
    raise ValueError(f"Could not parse JSON response after all fallback strategies. Raw response: {raw_output[:500]}...")

def _clean_json_response(raw_output: str) -> str:
    """
    Clean common JSON formatting issues.
    """
    cleaned = raw_output.replace("```json", "").replace("```")
    cleaned = cleaned.replace("'", '"')  
    cleaned = re.sub(r',(\s*[}$$])', r'\1', cleaned)
    cleaned = re.sub(r'"\s*\n\s*"', '",\n    "', cleaned)
    cleaned = re.sub(r'(?<!\$$"([^"]*)"([^"]*)"', r'"\1\\"\\"\2"', cleaned)
    
    return cleaned

def _extract_json_block(raw_output: str) -> str:
    """
    Extract the main JSON block from response.
    """
    start = raw_output.find('{')
    if start == -1:
        raise ValueError("No opening brace found")
    brace_count = 0
    for i in range(start, len(raw_output)):
        if raw_output[i] == '{':
            brace_count += 1
        elif raw_output[i] == '}':
            brace_count -= 1
            if brace_count == 0:
                return raw_output[start:i+1]
    
    raise ValueError("No matching closing brace found")

def _fix_json_delimiters(raw_output: str) -> str:
    """
    Fix common delimiter issues in JSON.
    """
    lines = raw_output.split('\n')
    fixed_lines = []
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        if line.endswith(('}', ']')) and i < len(lines) - 1:
            next_line = lines[i + 1].strip()
            if next_line and not next_line.startswith(('}', ']')) and not line.endswith(','):
                if not (line.endswith('}') and next_line.startswith(']')):
                    line += ','
        
        fixed_lines.append(line)
    
    return '\n'.join(fixed_lines)

def _create_fallback_proposal(proposal_text: str, supportive_text: str, native_language: str) -> dict:
    """
    Create a basic fallback proposal structure when JSON parsing fails.
    """
    logger.info("Creating fallback proposal structure")
    title_match = re.search(r'title["\s]*:[\s]*["\']([^"\']+)["\']', proposal_text, re.IGNORECASE)
    title = title_match.group(1) if title_match else "مقترح شامل للرد على طلب العروض (RFP)"
    sections = []
    text_parts = re.split(r'\n\s*\n', proposal_text)
    
    for i, part in enumerate(text_parts[:8]): 
        if len(part.strip()) > 50:  
            sections.append({
                "heading": f"القسم {i+1}" if native_language == "Arabic" else f"Section {i+1}",
                "content": part.strip()[:800],  
                "points": [],
                "table": {"headers": [], "rows": []}
            })
    if not sections:
        sections = [
            {
                "heading": "مقدمة" if native_language == "Arabic" else "Introduction",
                "content": proposal_text[:500] if proposal_text else "محتوى المقترح الأساسي",
                "points": ["نقطة أساسية 1", "نقطة أساسية 2"] if native_language == "Arabic" else ["Basic point 1", "Basic point 2"],
                "table": {"headers": [], "rows": []}
            },
            {
                "heading": "التفاصيل التقنية" if native_language == "Arabic" else "Technical Details", 
                "content": supportive_text[:500] if supportive_text else "التفاصيل التقنية للمقترح",
                "points": [],
                "table": {"headers": [], "rows": []}
            }
        ]
    
    return {
        "title": title,
        "sections": sections
    }

# ---------- API Endpoints ----------

def generate_proposal(uuid):
    """Generate a detailed proposal text from RFP files in Milvus collection in the native language."""
    try:
        rfp_text = fetch_rfp_text_by_uuid(str(uuid))
        if not rfp_text:
            raise HTTPException(status_code=404, detail="No RFP knowledge found for provided uuid")
        
        logger.info(f"Retrieved {len(rfp_text)} characters of RFP text for uuid {uuid}")
        supportive_text = fetch_supportive_files_text_by_uuid(uuid)
        if not supportive_text:
            logger.warning("No supportive files found for the provided uuid. Proceeding without it.")
            supportive_text = ""  
        
        logger.info(f"Retrieved {len(supportive_text)} characters of supportive files text for uuid {uuid}")
        
        native_language = detect_language(rfp_text)
        logger.info(f"Detected native language: {native_language}")
        
        proposal_text = generate_proposal_with_openai(rfp_text, native_language)
        

        try:
            final_proposal = customize_proposal_with_supportive_content_json(proposal_text, supportive_text, native_language)
        except Exception as customization_error:
            logger.error(f"Proposal customization failed: {customization_error}")
            final_proposal = {
                "title": "مقترح شامل للرد على طلب العروض (RFP)" if native_language == "Arabic" else "Comprehensive RFP Response Proposal",
                "sections": [
                    {
                        "heading": "المحتوى الأساسي" if native_language == "Arabic" else "Main Content",
                        "content": proposal_text[:1000],  
                        "points": [],
                        "table": {"headers": [], "rows": []}
                    }
                ]
            }
        
        try:
            final_proposal_str = json.dumps(final_proposal, ensure_ascii=False, indent=2)
            cleaned_proposal = proposal_cleaner(input_text=final_proposal_str)
            
            if isinstance(cleaned_proposal, str):
                try:
                    proposal_dict = json.loads(cleaned_proposal)
                except json.JSONDecodeError:
                    logger.warning("Cleaned proposal is not valid JSON, using original")
                    proposal_dict = final_proposal
            else:
                proposal_dict = cleaned_proposal
        except Exception as cleaning_error:
            logger.error(f"Proposal cleaning failed: {cleaning_error}")
            proposal_dict = final_proposal

        # === ARCHITECTURE DIAGRAM INTEGRATION ===
        try:
            logger.info("Starting architecture diagram integration")
            enhanced_proposal_dict = generate_and_integrate_architecture_diagram(
                proposal_dict, rfp_text, native_language
            )
            proposal_dict = enhanced_proposal_dict
            logger.info("Architecture diagram successfully integrated into proposal")
            
        except Exception as e:
            logger.error(f"Architecture diagram integration failed: {e}")
            logger.info("Continuing with original proposal without architecture diagrams")

        try:
            output_path = build_word_from_proposal(proposal_dict, output_path="output/proposal69.docx", visible=False)
            logger.info(f"Word document generated successfully: {output_path}")
        except Exception as word_error:
            logger.error(f"Word document generation failed: {word_error}")
        
        print("this is the final proposal", json.dumps(proposal_dict, ensure_ascii=False, indent=2))
        
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

def generate_and_integrate_architecture_diagram(proposal_dict: dict, rfp_text: str, native_language: str) -> dict:
    """
    Generate architecture diagram and integrate it into the proposal.
    """
    try:
        from apps.wordgenAgent.app.architecture_diagram import ProposalArchitectureDiagramGenerator
        
        logger.info("Starting architecture diagram generation")
        diagram_generator = ProposalArchitectureDiagramGenerator()
        diagram_result = diagram_generator.generate_architecture_diagram_from_proposal(
            proposal_dict, rfp_text, native_language
        )
        
        if not diagram_result.get("success"):
            logger.warning(f"Architecture diagram generation failed: {diagram_result.get('error')}")
            return proposal_dict  
        diagram_section = diagram_result.get("diagram_section")
        if not diagram_section:
            logger.warning("No diagram section returned")
            return proposal_dict
        enhanced_proposal = integrate_diagram_section_with_openai(
            proposal_dict, diagram_section, native_language
        )
        
        logger.info("✅ Architecture diagram successfully integrated into proposal")
        return enhanced_proposal
        
    except Exception as e:
        logger.error(f"Error in architecture diagram integration: {e}")
        return proposal_dict  

def integrate_diagram_section_with_openai(proposal_dict: dict, diagram_section: dict, native_language: str) -> dict:
    """
    Use OpenAI to intelligently place the architecture diagram section in the proposal.
    """
    if OpenAI is None:
        logger.warning("OpenAI not available, using fallback placement")
        return _fallback_diagram_placement(proposal_dict, diagram_section)
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("OpenAI API key not available, using fallback placement")
        return _fallback_diagram_placement(proposal_dict, diagram_section)
    
    try:
        import httpx
        http_client = httpx.Client()
        client = OpenAI(api_key=api_key, http_client=http_client)
        
        placement_prompts = {
            "Arabic": """
            أنت خبير في كتابة المقترحات التقنية. لديك مقترح كامل وقسم جديد للهندسة التقنية.
            
            مهمتك: تحديد أفضل مكان لإدراج قسم الهندسة التقنية في المقترح.
            
            المقترح الحالي (العناوين فقط):
            {section_headings}
            
            قسم الهندسة التقنية الجديد:
            العنوان: {diagram_heading}
            
            أعد ترتيب أقسام المقترح مع إدراج قسم الهندسة التقنية في المكان المناسب.
            أعد قائمة بترتيب العناوين الجديد فقط.
            """,
            
            "English": """
            You are an expert technical proposal writer. You have a complete proposal and a new technical architecture section.
            
            Your task: Determine the best placement for the technical architecture section within the proposal.
            
            Current proposal (headings only):
            {section_headings}
            
            New technical architecture section:
            Heading: {diagram_heading}
            
            Reorder the proposal sections with the technical architecture section in the most appropriate location.
            Return only the new ordering of headings.
            """
        }
        current_sections = proposal_dict.get("sections", [])
        section_headings = [section.get("heading", "") for section in current_sections]
        
        prompt_template = placement_prompts.get(native_language, placement_prompts["Arabic"])
        placement_prompt = prompt_template.format(
            section_headings="\n".join([f"{i+1}. {heading}" for i, heading in enumerate(section_headings)]),
            diagram_heading=diagram_section.get("heading", "")
        )
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a proposal structure expert. Provide optimal section ordering."},
                {"role": "user", "content": placement_prompt}
            ],
            temperature=0.2,
            max_tokens=500
        )
        ai_response = response.choices.message.content.strip()
        logger.info(f"AI placement suggestion received: {ai_response[:100]}...")
        return _smart_diagram_placement(proposal_dict, diagram_section, ai_response)
        
    except Exception as e:
        logger.error(f"Error in AI-powered diagram placement: {e}")
        return _fallback_diagram_placement(proposal_dict, diagram_section)

def _smart_diagram_placement(proposal_dict: dict, diagram_section: dict, ai_suggestion: str) -> dict:
    """
    Smart placement of diagram section based on AI suggestion and proposal structure.
    """
    sections = proposal_dict.get("sections", [])
    
    technical_keywords = ["technical", "تقني", "scope", "نطاق", "requirements", "متطلبات", "solution", "حل"]
    
    best_position = len(sections) // 2  
    
    for i, section in enumerate(sections):
        heading = section.get("heading", "").lower()
        if any(keyword in heading for keyword in technical_keywords):
            best_position = i + 1
            break
    best_position = min(best_position, len(sections))
    sections.insert(best_position, diagram_section)
    proposal_dict["sections"] = sections
    
    logger.info(f"Architecture diagram placed at position {best_position + 1}")
    return proposal_dict

def _fallback_diagram_placement(proposal_dict: dict, diagram_section: dict) -> dict:
    """
    Fallback method to place diagram section (after first 2 sections).
    """
    sections = proposal_dict.get("sections", [])
    insert_position = min(2, len(sections))
    sections.insert(insert_position, diagram_section)
    
    proposal_dict["sections"] = sections
    logger.info(f"Architecture diagram placed at fallback position {insert_position + 1}")
    return proposal_dict
