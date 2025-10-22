from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import uuid
import os
from routes.config import *
from routes.logging import logger
from routes import utils
from supabase_db.supabase_service import supabase_service
from ppt_generation import openai_service, ppt_service
from prompt import prompt

router = APIRouter()

class InitialGenRequest(BaseModel):
    """Request schema for /initialgen endpoint"""
    uuid: str                   
    template: str                
    user_preference: str        
    language: str               

@router.get("/ppt_templates")
async def get_templates():
    try:
        logger.info("📋 Fetching PPT templates...")
        
        templates = supabase_service.get_all_templates()
        
        logger.info(f"✅ Retrieved {len(templates)} templates")
        
        return {
            "status": "success",
            "templates": templates
        }
        
    except Exception as e:
        logger.error(f"❌ Error fetching templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/initialgen")
async def initialize_generation(request: InitialGenRequest):
    try:
        logger.info("=" * 80)
        logger.info("🚀 STARTING PROPOSAL GENERATION")
        logger.info("=" * 80)
        gen_id = f"gen_{uuid.uuid4().hex[:12]}"
        logger.info(f"📝 Generated gen_id: {gen_id}")
        
        template_file_path = f"{request.template}/Template.pptx"
        template_url = supabase_service.client.storage.from_(PPT_TEMPLATE_BUCKET).get_public_url(template_file_path)
        logger.info(f"🎨 Template URL: {template_url}")
        
        logger.info(f"📥 Fetching record for uuid: {request.uuid}")
        record = supabase_service.fetch_generation_data_by_uuid(request.uuid)
        
        if not record:
            logger.error(f"❌ Record not found for uuid: {request.uuid}")
            raise HTTPException(status_code=404, detail="Record not found")
        
        rfp_file_url = record["rfp_file"]
        supporting_file_url = record["supporting_file"]
        logger.info(f"✅ Record fetched successfully")
        
        logger.info("📦 Downloading files from Supabase...")
        
        temp_rfp_path = os.path.join(TEMP_DIR, f"{gen_id}_rfp.pdf")
        temp_supporting_path = os.path.join(TEMP_DIR, f"{gen_id}_supporting.pdf")
        temp_template_path = os.path.join(TEMP_DIR, f"{gen_id}_template.pptx")
        
        rfp_file_path = rfp_file_url.split(f"{RFP_BUCKET}/")[-1]
        supporting_file_path = supporting_file_url.split(f"{SUPPORTING_BUCKET}/")[-1]
        
        supabase_service.download_file_from_bucket(RFP_BUCKET, rfp_file_path, temp_rfp_path)
        supabase_service.download_file_from_bucket(SUPPORTING_BUCKET, supporting_file_path, temp_supporting_path)
        supabase_service.download_file_from_bucket(PPT_TEMPLATE_BUCKET, template_file_path, temp_template_path)
        
        logger.info("✅ All files downloaded successfully")
        
        logger.info("☁️  Uploading PDFs to OpenAI...")
        rfp_id = openai_service.upload_pdf_to_openai(temp_rfp_path)
        supporting_id = openai_service.upload_pdf_to_openai(temp_supporting_path)
        logger.info(f"✅ Files uploaded: rfp_id={rfp_id}, supporting_id={supporting_id}")
        
        logger.info("🔍 Analyzing template layouts...")
        template_analysis, layout_details = ppt_service.analyze_template_layouts(temp_template_path)
        
        logger.info(f"📝 Building prompts (language: {request.language})...")
        system_prompt = prompt.build_system_prompt(request.language, template_analysis, layout_details)
        task_prompt = prompt.build_task_prompt(request.user_preference, layout_details)
        logger.info("✅ Prompts built successfully")
        
        logger.info("🤖 Calling OpenAI Responses API...")
        raw_json = openai_service.generate_proposal_content(system_prompt, task_prompt, rfp_id, supporting_id)
        logger.info(f"✅ Received response from OpenAI ({len(raw_json)} characters)")
        
        logger.info("🔧 Parsing JSON slides...")
        slides = utils.parse_slides_json(raw_json)
        logger.info(f"✅ Parsed {len(slides)} slides")
        
        logger.info("📊 Creating PowerPoint presentation...")
        temp_ppt_path = os.path.join(TEMP_DIR, f"{gen_id}_generated.pptx")
        ppt_service.create_ppt_from_json(slides, temp_template_path, temp_ppt_path)
        logger.info(f"✅ PPT created: {temp_ppt_path}")
        
        logger.info("Converting PPT to PDF...")
        temp_pdf_path = os.path.join(TEMP_DIR, f"{gen_id}_generated.pdf")
        pdf_result = ppt_service.convert_ppt_to_pdf(temp_ppt_path, temp_pdf_path)
        
        if pdf_result:
            logger.info(f"[OK] PDF created: {temp_pdf_path}")
        else:
            logger.warning("[WARN] PDF conversion skipped - no tool available")
        
        logger.info("Uploading generated files to Supabase...")
        
        ppt_filename = f"{gen_id}_ppt.pptx"
        ppt_url = supabase_service.upload_file_to_bucket(PPT_BUCKET, temp_ppt_path, ppt_filename)
        logger.info(f"[OK] PPT URL: {ppt_url}")
        
        if pdf_result:
            pdf_filename = f"{gen_id}_pdf.pdf"
            pdf_url = supabase_service.upload_file_to_bucket(PDF_BUCKET, temp_pdf_path, pdf_filename)
            logger.info(f"[OK] PDF URL: {pdf_url}")
        else:
            pdf_url = None
            logger.warning("[WARN] PDF upload skipped - only PPTX available")
        
        logger.info("Updating database...")
        
        updates = {
            "gen_id": gen_id,
            "ppt_template": template_url,
            "general_preference": request.user_preference,
            "generated_ppt": ppt_url,
            "generated_pdf": pdf_url  
        }
        
        supabase_service.update_record_by_uuid(request.uuid, updates)
        logger.info("[OK] Database updated successfully")
        
        logger.info("Cleaning up temp files...")
        
        files_to_cleanup = [
            temp_rfp_path,
            temp_supporting_path,
            temp_template_path,
            temp_ppt_path
        ]
        
        if pdf_result:
            files_to_cleanup.append(temp_pdf_path)
        
        utils.cleanup_temp_files(*files_to_cleanup)
        
        logger.info("=" * 80)
        logger.info("[SUCCESS] PROPOSAL GENERATION COMPLETED")
        logger.info("=" * 80)
        
        response = {
            "status": "completed",
            "gen_id": gen_id,
            "ppt_url": ppt_url
        }
        
        if pdf_url:
            response["pdf_url"] = pdf_url
        else:
            response["pdf_url"] = None
            response["note"] = "PDF conversion not available - install LibreOffice to enable"
        
        return response
        
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"❌ Error in initialize_generation: {e}")
        logger.error(f"Error type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download")
async def download_proposal(uuid: str, gen_id: str):
    try:
        logger.info(f"📥 Fetching download URLs for uuid={uuid}, gen_id={gen_id}")
        record = supabase_service.fetch_generation_data(uuid, gen_id)
        
        if not record:
            logger.error(f"❌ Record not found for uuid={uuid}, gen_id={gen_id}")
            raise HTTPException(status_code=404, detail="Record not found")
        
        ppt_url = record.get("generated_ppt")
        pdf_url = record.get("generated_pdf")
        
        if not ppt_url or not pdf_url:
            logger.warning(f"⚠️  Files not generated yet for uuid={uuid}, gen_id={gen_id}")
            raise HTTPException(
                status_code=404,
                detail="Files not generated yet. Please call /initialgen first."
            )
        
        logger.info(f"✅ URLs retrieved successfully")
        logger.info(f"   PPT: {ppt_url}")
        logger.info(f"   PDF: {pdf_url}")
        
        return {
            "status": "completed",
            "ppt_url": ppt_url,
            "pdf_url": pdf_url
        }
        
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"❌ Error in download_proposal: {e}")
        raise HTTPException(status_code=500, detail=str(e))
