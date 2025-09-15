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

try:
    from openai import OpenAI
except Exception:
    OpenAI = None  # type: ignore




# Load environment variables from nearest .env up the tree
load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env", override=False)
load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env", override=False)
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env", override=False)


app = FastAPI(title="WordGen Agent API")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("wordgen-agent")


class GenerateProposalRequest(BaseModel):
    uuid: str


class GenerateProposalResponse(BaseModel):
    status: str
    proposal_text: str
    detected_language: str


# ---------- Milvus utilities ----------

DEFAULT_CONSISTENCY = os.getenv("MILVUS_CONSISTENCY_LEVEL", "Bounded")  # Strong|Session|Bounded|Eventually

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
        # Known transient/state error: timestamp lag on QueryNode
        if "Timestamp lag too large" in msg or "no available shard delegator" in msg:
            logger.warning(f"Milvus lag detected, retrying with Eventually + guarantee_timestamp=0: {msg}")
            try:
                return col.query(
                    expr=expr,
                    output_fields=output_fields,
                    consistency_level="Eventually",
                    limit=limit,
                    guarantee_timestamp=0,  # read whatever is available immediately
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
        
        # Sort by chunk_index if present for deterministic ordering
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
        # results = col.query(
        #     expr=expr, 
        #     output_fields=["content", "chunk_index", "file_name"], 
        #     consistency_level="Strong", 
        #     limit=16384
        # )
        
        logger.info(f"Milvus query returned {len(results)} rows for uuid={uuid}")
        
        # Sort by chunk_index if present for deterministic ordering
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
    
    # Create client
    import httpx
    http_client = httpx.Client()
    client = OpenAI(api_key=api_key, http_client=http_client)
    
    # Enhanced language detection prompt
    language_prompt = f"""Analyze this text and identify the primary language. Consider the following:
1. The main language used throughout the document
2. The language of technical terms and specifications
3. The language of legal and contractual language
4. The language of headings and structure

Text sample: {rfp_text[:2000]}

Respond with ONLY the language name in English (e.g., 'Arabic', 'English', 'Spanish', 'French', 'German', 'Chinese', 'Japanese', 'Korean', 'Portuguese', 'Italian', 'Russian', 'Turkish', 'Hindi', 'Urdu', 'Persian', 'Malay', 'Indonesian', 'Thai', 'Vietnamese')."""
    
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
    
    # Create client
    import httpx
    http_client = httpx.Client()

    client = OpenAI(api_key=api_key, http_client=http_client)
    
    # Create language-specific system prompt
    system_prompts = {
        "Arabic": "أنت كاتب مقترحات خبير. أنشئ مقترحاً شاملاً ومفصلاً للرد على طلب العروض باللغة العربية. يجب أن يتضمن البنية والمحتوى المفصل لكل قسم، وليس العناوين فقط.",
        "English": "You are an expert proposal writer. Create a comprehensive, detailed proposal response to the RFP in English. Include both structure AND detailed content for each section, not just headings.",
        "Spanish": "Eres un escritor de propuestas experto. Crea una propuesta integral y detallada para responder a la RFP en español. Incluye tanto la estructura como el contenido detallado para cada sección, no solo los encabezados.",
        "French": "Vous êtes un rédacteur de propositions expert. Créez une proposition complète et détaillée pour répondre à l'AAP en français. Incluez à la fois la structure ET le contenu détaillé pour chaque section, pas seulement les en-têtes.",
        "German": "Sie sind ein Experte für Vorschlagsschreiben. Erstellen Sie einen umfassenden, detaillierten Vorschlag zur Beantwortung der RFP auf Deutsch. Fügen Sie sowohl Struktur ALS AUCH detaillierte Inhalte für jeden Abschnitt hinzu, nicht nur Überschriften.",
        "Chinese": "您是一位专业的提案撰写专家。用中文创建一份全面、详细的提案来回应RFP。包括结构和每个部分的详细内容，而不仅仅是标题。",
        "Japanese": "あなたは専門的な提案書作成者です。RFPに対する包括的で詳細な提案を日本語で作成してください。構造と各セクションの詳細な内容を含めてください。見出しだけではありません。",
        "Korean": "당신은 전문적인 제안서 작성자입니다. RFP에 대한 포괄적이고 상세한 제안서를 한국어로 작성하세요. 구조와 각 섹션의 상세한 내용을 포함하되, 제목만이 아닙니다.",
        "Portuguese": "Você é um escritor de propostas especialista. Crie uma proposta abrangente e detalhada para responder ao RFP em português. Inclua tanto a estrutura quanto o conteúdo detalhado para cada seção, não apenas os cabeçalhos.",
        "Italian": "Sei uno scrittore di proposte esperto. Crea una proposta completa e dettagliata per rispondere all'RFP in italiano. Includi sia la struttura che il contenuto dettagliato per ogni sezione, non solo i titoli.",
        "Russian": "Вы эксперт по написанию предложений. Создайте всестороннее, подробное предложение для ответа на RFP на русском языке. Включите как структуру, так и подробное содержание для каждого раздела, а не только заголовки.",
        "Turkish": "Sen uzman bir teklif yazarısın. RFP'ye Türkçe olarak kapsamlı ve detaylı bir teklif yanıtı oluştur. Sadece başlıklar değil, hem yapıyı hem de her bölüm için detaylı içeriği dahil et.",
        "Hindi": "आप एक विशेषज्ञ प्रस्ताव लेखक हैं। RFP के लिए हिंदी में एक व्यापक, विस्तृत प्रस्ताव प्रतिक्रिया बनाएं। केवल शीर्षक नहीं, बल्कि संरचना और प्रत्येक अनुभाग के लिए विस्तृत सामग्री शामिल करें।",
        "Urdu": "آپ ایک ماہر تجاویز لکھنے والے ہیں۔ RFP کے لیے اردو میں ایک جامع، تفصیلی تجویز کا جواب بنائیں۔ صرف سرخیاں نہیں، بلکہ ساخت اور ہر سیکشن کے لیے تفصیلی مواد شامل کریں۔",
        "Persian": "شما یک نویسنده متخصص پیشنهاد هستید. یک پیشنهاد جامع و دقیق برای پاسخ به RFP به زبان فارسی ایجاد کنید. هم ساختار و هم محتوای دقیق برای هر بخش را شامل کنید، نه فقط عناوین.",
        "Malay": "Anda adalah penulis cadangan pakar. Cipta cadangan yang komprehensif dan terperinci untuk membalas RFP dalam bahasa Melayu. Sertakan kedua-dua struktur DAN kandungan terperinci untuk setiap bahagian, bukan hanya tajuk.",
        "Indonesian": "Anda adalah penulis proposal ahli. Buat proposal yang komprehensif dan detail untuk menanggapi RFP dalam bahasa Indonesia. Sertakan struktur DAN konten detail untuk setiap bagian, bukan hanya judul.",
        "Thai": "คุณเป็นนักเขียนข้อเสนอผู้เชี่ยวชาญ สร้างข้อเสนอที่ครอบคลุมและละเอียดเพื่อตอบสนอง RFP เป็นภาษาไทย รวมทั้งโครงสร้างและเนื้อหาที่ละเอียดสำหรับแต่ละส่วน ไม่ใช่แค่หัวข้อ",
        "Vietnamese": "Bạn là một chuyên gia viết đề xuất. Tạo một đề xuất toàn diện và chi tiết để phản hồi RFP bằng tiếng Việt. Bao gồm cả cấu trúc VÀ nội dung chi tiết cho từng phần, không chỉ tiêu đề."
    }
    
    system_prompt = system_prompts.get(native_language, f"You are an expert proposal writer. Create a comprehensive, detailed proposal response to the RFP in {native_language}. Include both structure AND detailed content for each section, not just headings.")
    
    # Create language-specific task instructions for detailed 10+ page proposals
    task_instructions = {
        "Arabic": f"المهمة: إنشاء مقترح شامل ومفصل باللغة العربية (على الأقل 10 صفحات) يتضمن:\n1. معالجة جميع متطلبات RFP ومعايير التقييم بتفاصيل محددة ومفصلة\n2. تضمين نهج تقني مفصل ومنهجية وجدول زمني مع تفسيرات شاملة\n3. تغطية الامتثال والشهادات والمؤهلات بأمثلة محددة ومفصلة\n4. أقسام للتسعير والشروط والأحكام مع تفسيرات مفصلة وواضحة\n5. تضمين النماذج المطلوبة والمصفوفات والملاحق مع محتوى كامل\n6. اتباع البنية واللغة الدقيقة لـ RFP\n7. تقديم محتوى كبير ومفصل تحت كل قسم (على الأقل 300-500 كلمة لكل قسم رئيسي)\n8. إظهار فهم متطلبات RFP من خلال ردود مفصلة ومفصلة\n9. تضمين منهجيات محددة وجداول زمنية وتسليمات مفصلة\n10. إظهار الخبرة المهنية والقدرة في المجال مع أمثلة محددة\n11. تضمين تحليل المخاطر واستراتيجيات التخفيف\n12. تقديم خطة إدارة المشروع المفصلة\n13. تضمين مقاييس الأداء ومؤشرات النجاح\n14. إظهار الابتكار والحلول المبتكرة\n15. تقديم ضمانات الجودة ومراقبة الأداء",
        "English": f"TASK: Create a comprehensive, detailed proposal in {native_language} (minimum 10 pages) that:\n1. Addresses ALL RFP requirements and evaluation criteria with extensive specific details\n2. Includes comprehensive technical approach, methodology, and timeline with detailed explanations\n3. Covers compliance, certifications, and qualifications with specific examples and evidence\n4. Has detailed sections for pricing, terms, and conditions with comprehensive explanations\n5. Includes all required forms, matrices, and appendices with complete content\n6. Follows the exact structure and language of the RFP\n7. Provides substantial, detailed content under each section (minimum 300-500 words per major section)\n8. Demonstrates deep understanding of RFP requirements through comprehensive responses\n9. Includes specific methodologies, detailed timelines, and comprehensive deliverables\n10. Shows professional expertise and capability with specific examples and case studies\n11. Includes comprehensive risk analysis and mitigation strategies\n12. Provides detailed project management approach and methodology\n13. Includes specific metrics, KPIs, and success measurement frameworks\n14. Demonstrates innovation and creative solutions\n15. Provides quality assurance and performance monitoring frameworks\n16. Each major section must be substantial and detailed to ensure 10+ pages of content"
    }
    
    task_instruction = task_instructions.get(native_language, f"TASK: Create a comprehensive, detailed proposal in {native_language} (minimum 10 pages) that addresses all RFP requirements with extensive detailed content, comprehensive technical approach, detailed methodology, comprehensive timeline, detailed compliance information, comprehensive pricing breakdown, and extensive professional expertise with specific examples.")
    
    messages = [
        {
            "role": "system", 
            "content": system_prompt
        },
        {
            "role": "user", 
            "content": (
                f"RFP DOCUMENT (Requirements & Specifications):\n" + (rfp_text or "")[:120000] +
                f"\n\n{task_instruction}\n\n"
                f"IMPORTANT: The entire proposal must be written in {native_language}. Use the same language style, terminology, and formatting conventions as the original RFP document."
            )
        }
		
    ]
    
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages, # type: ignore
        temperature=0.2,
        max_tokens=16000,  # Increased token limit for 10+ page detailed proposals
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
    Customize the generated proposal using supportive content (company details, expertise) via 4OMini.
    Returns a structured JSON object with labeled sections (heading, title, content, table, points, etc.).
    """


    if OpenAI is None:
        raise HTTPException(status_code=500, detail="openai package not available")
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not set")
    
    # Create client
    import httpx
    http_client = httpx.Client()

    client = OpenAI(api_key=api_key, http_client=http_client)

    try:
        # Build the prompt for JSON output
        prompt = f"""
You are a professional proposal writer. 
You are given an initial proposal draft and supportive company information.
Your task is to merge them into a professional, persuasive proposal.

- Use the supportive info to highlight expertise and offerings.
- Ensure logical flow and professional tone.
- Write in {native_language}.
- Output ONLY valid JSON. No extra text.

--- JSON FORMAT REQUIREMENTS ---
The final output must be a JSON object structured like this:
{{
  "title": "Main proposal title",
  "sections": [
    {{
      "heading": "Section heading",
      "content": "Full detailed content in paragraph form",
      "points": ["Point 1", "Point 2"],
      "table": {{
        "headers": ["Column1", "Column2"],
        "rows": [
          ["Row1-Col1", "Row1-Col2"],
          ["Row2-Col1", "Row2-Col2"]
        ]
      }}
    }}
  ]
}}

--- SUPPORTIVE COMPANY INFORMATION ---
{supportive_text}

--- INITIAL PROPOSAL DRAFT ---
{proposal_text}

Now generate the final proposal in the requested JSON format.
"""

        logger.info(f"Sending customization request to {model}")
    
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a senior proposal writer and JSON formatter."},
                {"role": "user", "content": prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens
        )

        # Parse JSON response
        raw_output = response.choices[0].message.content.strip() # type: ignore
        final_proposal_json = json.loads(raw_output)

        logger.info("Customized proposal generated successfully in JSON format")
        return final_proposal_json

    except Exception as exc:
        logger.exception("Error generating customized proposal via 4OMini")
        


# ---------- Text processing ----------



# ---------- API Endpoints ----------

@app.post("/generate-proposal", response_model=GenerateProposalResponse)
def generate_proposal(request: GenerateProposalRequest) -> GenerateProposalResponse:
    """Generate a detailed proposal text from RFP files in Milvus collection in the native language."""
    try:
        rfp_text = fetch_rfp_text_by_uuid(request.uuid)
        if not rfp_text:
            raise HTTPException(status_code=404, detail="No RFP knowledge found for provided uuid")
        
        logger.info(f"Retrieved {len(rfp_text)} characters of RFP text for uuid {request.uuid}")

        # 2) Retrieve supportive files text from Milvus supportive_files collection
        supportive_text = fetch_supportive_files_text_by_uuid(request.uuid)
        if not supportive_text:
            logger.warning("No supportive files found for the provided uuid. Proceeding without it.")
        
        logger.info(f"Retrieved {len(supportive_text)} characters of supportive files text for uuid {request.uuid}")
        
        native_language = detect_language(rfp_text)
        logger.info(f"Detected native language: {native_language}")
        proposal_text = generate_proposal_with_openai(rfp_text, native_language)
        final_proposal = customize_proposal_with_supportive_content_json(proposal_text, supportive_text, native_language)
        print("this is the final proposal", final_proposal)

        print("this is the proposal text", proposal_text + "\n...")

        
        return GenerateProposalResponse(
            status="ok",
            proposal_text=proposal_text,
            detected_language=native_language
        )
        
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


@app.get("/debug/rfp-data/{uuid}")
def debug_rfp_data(uuid: str):
    """Debug endpoint to see what RFP data will be used for proposal generation."""
    try:
        rfp_text = fetch_rfp_text_by_uuid(uuid)
        
        debug_info = {
            "uuid": uuid,
            "rfp_data": {
                "length": len(rfp_text),
                "preview": rfp_text[:1000] + "..." if len(rfp_text) > 1000 else rfp_text,
                "available": bool(rfp_text)
            },
            "recommendations": []
        }
        
        # Detect language if RFP text is available
        if rfp_text:
            try:
                detected_language = detect_language(rfp_text)
                debug_info["detected_language"] = detected_language
                debug_info["recommendations"].append(f"Proposal will be generated in {detected_language}")
            except Exception as lang_exc:
                debug_info["language_detection_error"] = str(lang_exc)
                debug_info["recommendations"].append("Language detection failed - proposal will use default language")
        
        # Add recommendations
        if not rfp_text:
            debug_info["recommendations"].append("No RFP data found - check if documents are uploaded correctly to rfp_files collection")
        if len(rfp_text) < 1000:
            debug_info["recommendations"].append("RFP data is very short - check if RFP document is complete")
            
        return debug_info
    except Exception as exc:
        logger.exception("Error in debug_rfp_data")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "message": "WordGen Agent API is running"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)



	