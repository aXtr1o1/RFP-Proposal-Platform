from fastapi import FastAPI, HTTPException, Path, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import os
from datetime import datetime
from typing import List, Dict, Optional
from dotenv import load_dotenv
import sys
import uuid
from apps.wordgenAgent.app.api import generate_proposal
from fastapi import Body
from pydantic import BaseModel
from typing import Optional, Dict, Any

load_dotenv()

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="RFP Proposal Platform API",
    description="RFP document processing with enhanced OCR text extraction and proposal generation",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class OCRRequest(BaseModel):
    config: Optional[str] = None
    docConfig: Optional[Dict[str, Any]] = None
    timestamp: Optional[str] = None
    language: Optional[str] = "arabic"


sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'vdb'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'workers', 'ocr'))

from apps.api.routes.rfp import get_onedrive_service
from apps.vdb.milvus_client import get_milvus_client
from apps.workers.ocr.worker import get_ocr_worker
from apps.supabase.supabase_service import upload_and_save_pdf

try:
    from apps.workers.ocr.text_ocr_service import get_text_ocr_service
    TEXT_OCR_AVAILABLE = True
    logger.info("Enhanced Text OCR service available")
except ImportError as e:
    logger.warning(f"Enhanced Text OCR service not available: {e}")
    TEXT_OCR_AVAILABLE = False
    get_text_ocr_service = None

@app.get("/")
async def root():
    """Root endpoint with service status"""
    return {
        "message": "RFP Proposal Platform - Enhanced API with OCR Text Processing and Proposal Generation",
        "version": "1.0.0",
        "endpoints": {
            "/files": "GET - List available RFP folders",
            "/ocr/{folder_name}": "POST - Process folder with OCR text extraction and generate comprehensive proposal",
            "/milvus": "GET - View/Search documents (shows processed text data)",
        },
        "services_status": {
            "onedrive": "✅ Available",
            "milvus": "✅ Available",
            "ocr_text_processing": "✅ Available", 
            "enhanced_text_ocr": "✅ Available" if TEXT_OCR_AVAILABLE else "❌ Basic OCR Only",
            "proposal_generation": "✅ Available with architecture diagrams",
            "collections": ["rfp_files", "supportive_files"]
        },
        "features": {
            "ocr_text_extraction": "Azure Document Intelligence for high-quality text extraction",
            "comprehensive_proposals": "6-7 page detailed proposals with diagrams",
            "multi_language_support": "Arabic, English languages",
            "enhanced_content_generation": "Detailed technical content with specific examples"
        },
        "timestamp": datetime.now().isoformat()
    }

@app.get("/files")
async def get_files():
    """Get available folders in RFP-Uploads"""
    try:
        service = get_onedrive_service()
        folders = service.get_folders_in_drives()
        rfp_folder = None
        for folder in folders:
            if folder['folder_name'] == 'RFP-Uploads':
                rfp_folder = folder
                break
        
        if not rfp_folder:
            raise HTTPException(status_code=404, detail="RFP-Uploads folder not found")
        structure = service.get_folder_structure(rfp_folder['drive_id'], 'RFP-Uploads', max_depth=2)
        
        available_folders = []
        for folder in structure['folders']:
            available_folders.append({
                'folder_name': folder['folder_name'],
                'file_count': len(folder.get('files', [])),
                'subfolder_count': len(folder.get('subfolders', [])),
                'created_datetime': folder.get('created_datetime'),
                'modified_datetime': folder.get('modified_datetime')
            })
        
        return {
            "available_folders": available_folders,
            "total_folders": len(available_folders),
            "rfp_uploads_info": {
                "drive_id": rfp_folder['drive_id'],
                "folder_structure": "Found"
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting files: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ocr/{folder_name}")
async def process_ocr(folder_name: str = Path(..., description="Folder name to process"), request: OCRRequest = Body(...)):
    """Process folder with enhanced OCR text extraction and save to Milvus collections + Generate comprehensive proposal"""
    try:
        start_time = datetime.now()
        logger.info(f"Processing folder: {folder_name}")

        user_config = request.config
        doc_config = request.docConfig
        timestamp = request.timestamp
        language = request.language

        logger.info(f"Received config: {user_config}")
        logger.info(f"Received docConfig: {doc_config}")
        logger.info(f"Timestamp: {timestamp}")
        logger.info(f"laguage received: {language}")
        logger.info(f"laguage received: {language}")
        print(doc_config)
        onedrive_service = get_onedrive_service()
        
        folders = onedrive_service.get_folders_in_drives()
        rfp_folder = None
        for folder in folders:
            if folder['folder_name'] == 'RFP-Uploads':
                rfp_folder = folder
                break

        if not rfp_folder:
            raise HTTPException(status_code=404, detail="RFP-Uploads folder not found")
        search_path = f"RFP-Uploads/{folder_name}"
        all_files = onedrive_service.get_all_files_recursively(rfp_folder['drive_id'], search_path, max_depth=3)
        if not all_files:
            raise HTTPException(status_code=404, detail=f"No files found in folder '{folder_name}'")
        pdf_files = [f for f in all_files if f['mime_type'] == 'application/pdf' or f['file_name'].lower().endswith('.pdf')]
        if not pdf_files:
            raise HTTPException(status_code=404, detail="No PDF files found for processing")
        
        logger.info(f"Found {len(pdf_files)} PDF files to process")
        
        all_ocr_results = []
        processed_files = []
        failed_files = []
        extracted_content = {} 
        ocr_worker = get_ocr_worker()
        for pdf_file in pdf_files:
            try:
                logger.info(f"Processing: {pdf_file['file_name']}")
                file_content = onedrive_service.download_file(pdf_file.get('download_url'))
                if not file_content:
                    failed_files.append({"file_name": pdf_file['file_name'], "reason": "Download failed"})
                    continue
                folder_type = onedrive_service.determine_folder_type(pdf_file)
                logger.info(f"File {pdf_file['file_name']} detected as: {folder_type}")
                text_results = onedrive_service.process_file_with_text_ocr(file_content, pdf_file)
                
                if text_results:
                    extracted_content[pdf_file['file_name']] = {
                        'file_type': folder_type,
                        'total_pages': len(text_results),
                        'total_words': sum([r.get('word_count', 0) for r in text_results]),
                        'pages_content': []
                    }
                    
                    for result in text_results:
                        result['file_path'] = pdf_file.get('file_path', pdf_file['file_name'])
                        result['folder_path'] = pdf_file.get('folder_path', 'unknown')
                        page_content = result.get('content', '')
                        extracted_content[pdf_file['file_name']]['pages_content'].append({
                            'page_number': result.get('page', 1),
                            'content': page_content,
                            'word_count': result.get('word_count', 0),
                            'content_preview': page_content[:300] + ('...' if len(page_content) > 300 else ''),
                            'content_length': len(page_content)
                        })
                    
                    all_ocr_results.extend(text_results)
                    
                    processed_files.append({
                        "file_name": pdf_file['file_name'],
                        "folder_type": folder_type,
                        "pages_processed": len(text_results),
                        "total_words": sum([r.get('word_count', 0) for r in text_results])
                    })
                    
                    logger.info(f"Successfully processed: {pdf_file['file_name']} ({len(text_results)} pages)")
                else:
                    failed_files.append({"file_name": pdf_file['file_name'], "reason": "OCR failed - no text extracted"})
                    logger.error(f"OCR failed for: {pdf_file['file_name']}")
                    
            except Exception as e:
                logger.error(f"Error processing {pdf_file['file_name']}: {e}")
                failed_files.append({"file_name": pdf_file['file_name'], "reason": str(e)})
        
        if not all_ocr_results:
            raise HTTPException(status_code=400, detail="No documents processed successfully")
        try:
            rfp_results = [r for r in all_ocr_results if r.get('file_type') == 'rfp_files']
            supportive_results = [r for r in all_ocr_results if r.get('file_type') == 'supportive_files']
            
            vector_result = {
                "vector_stored": True,
                "collections": {},
                "total_documents_saved": 0
            }
            
            if rfp_results:
                logger.info(f"Saving {len(rfp_results)} RFP results to rfp_files collection")
                rfp_client = get_milvus_client("rfp_files")
                if rfp_client.is_available():
                    rfp_ids = rfp_client.save_documents(rfp_results, folder_name)
                    vector_result["collections"]["rfp_files"] = {
                        "documents_stored": len(rfp_ids),
                        "collection_name": "rfp_files",
                        "document_ids_sample": rfp_ids[:3],  
                        "status": "success"
                    }
                    vector_result["total_documents_saved"] += len(rfp_ids)
                    logger.info(f"Saved {len(rfp_ids)} RFP documents to Milvus")
                else:
                    vector_result["collections"]["rfp_files"] = {"status": "failed", "reason": "Milvus client not available"}
            
            if supportive_results:
                logger.info(f"Saving {len(supportive_results)} supportive results to supportive_files collection")
                supportive_client = get_milvus_client("supportive_files")
                if supportive_client.is_available():
                    supportive_ids = supportive_client.save_documents(supportive_results, folder_name)
                    
                    vector_result["collections"]["supportive_files"] = {
                        "documents_stored": len(supportive_ids),
                        "collection_name": "supportive_files",
                        "document_ids_sample": supportive_ids[:3],  
                        "status": "success"
                    }
                    vector_result["total_documents_saved"] += len(supportive_ids)
                    logger.info(f"Saved {len(supportive_ids)} supportive documents to Milvus")
                else:
                    vector_result["collections"]["supportive_files"] = {"status": "failed", "reason": "Milvus client not available"}
            
        except Exception as e:
            logger.error(f"Milvus storage error: {e}")
            vector_result = {"vector_stored": False, "error": str(e)}
        
        processing_time = str(datetime.now() - start_time)
        logger.info(f"Processing completed in {processing_time}")
        proposal_generation_result = {}
        try:
            
            logger.info(f"Starting comprehensive proposal generation for folder: {folder_name}")
            output_path = generate_proposal(uuid=folder_name, user_config=doc_config, language=language)
            logger.info(f"Comprehensive proposal PATH is here............: {output_path}")
            local_docx = os.path.join("output", f"{folder_name}.docx")
            local_pdf = os.path.join("output", f"{folder_name}.pdf")
            try:
                convert(local_docx, local_pdf)
                logger.info(f"Converted DOCX to PDF: {local_pdf}")
            except Exception as e:
                logger.error(f"PDF conversion failed: {e}")
                local_pdf = None


            onedrive_info = {}


            # Upload the generated document back to OneDrive

            try:
                onedrive_service.ensure_folder_path(rfp_folder['drive_id'], search_path)
                dest_rel_path = f"{search_path}/{folder_name}.docx"
                uploaded_item = onedrive_service.upload_small_file(
                    rfp_folder['drive_id'],
                    dest_rel_path,
                    local_docx
                )
                web_url_docx = uploaded_item.get("webUrl")



                # upload the PDF file (if conversion succeeded)

                web_url_pdf = None
                if local_pdf:
                    dest_pdf_path = f"{search_path}/{folder_name}.pdf"
                    uploaded_pdf = onedrive_service.upload_small_file(
                        rfp_folder['drive_id'],
                        dest_pdf_path,
                        local_pdf
                    )
                    web_url_pdf = uploaded_pdf.get("webUrl")

                # optional: create a view-only share link for easy embedding
                share_docx = onedrive_service.create_share_link(
                    rfp_folder['drive_id'],
                    uploaded_item.get("id"),
                    scope="anonymous",  
                    link_type="view"
                )

                share_pdf = None
                if local_pdf and uploaded_pdf:
                    share_pdf = onedrive_service.create_share_link(
                        rfp_folder['drive_id'],
                        uploaded_pdf.get("id"),
                        scope="anonymous",
                        link_type="view"
                    )


                onedrive_info = {
                    "uploaded_docx": True,
                    "docx_webUrl": web_url_docx,
                    "docx_shareUrl": share_docx,
                    "uploaded_pdf": bool(local_pdf),
                    "pdf_webUrl": web_url_pdf,
                    "pdf_shareUrl": share_pdf
                }



                logger.info(f"Uploaded proposal (DOCX + PDF) to OneDrive")
                logger.info(f"Uploaded proposal to OneDrive: {web_url_docx}")
                logger.info(f"Share link (DOCX): {share_docx}")
                pdf_supabase_url = upload_and_save_pdf(local_pdf, f"{folder_name}.pdf", uuid=folder_name, pdf_share_url=share_pdf)
                if local_pdf:  
                    logger.info(f"Uploaded PDF to OneDrive: {web_url_pdf}")
                    logger.info(f"Share link (PDF): {share_pdf}")

            except Exception as e:
                logger.warning(f"OneDrive upload failed: {e}")
                onedrive_info = {"uploaded": False, "error": str(e)}
            
        except Exception as e:
            logger.error(f"Comprehensive proposal generation failed for folder {folder_name}: {e}")
            
        return {
            "folder_name": folder_name,
            "onedrive": onedrive_info,
            "supabase_url" : pdf_supabase_url,
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OCR processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
from fastapi.responses import FileResponse

@app.get("/download/{filename}")
def download_file(filename: str):
    file_path = os.path.join("output", filename)
    if not os.path.exists(file_path):
        return {"error": "File not found"}
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

import pythoncom
from docx2pdf import convert
@app.get("/download-pdf/{filename}")
def download_pdf(filename: str):
    if not filename.endswith(".docx"):
        filename += ".docx"

    docx_path = os.path.join("output", filename)
    if not os.path.exists(docx_path):
        return {"error": "File not found"}

    pdf_filename = filename.replace(".docx", ".pdf")
    pdf_path = os.path.join("output", pdf_filename)

    if not os.path.exists(pdf_path):
        # Manually init COM
        pythoncom.CoInitialize()
        try:
            convert(docx_path, pdf_path)
        finally:
            pythoncom.CoUninitialize()

    return FileResponse(
        path=pdf_path,
        filename=pdf_filename,
        media_type="application/pdf"
    )

@app.get("/milvus")
async def get_milvus(
    search: str = Query(None, description="Search query for documents"),
    limit: int = Query(10, description="Number of results to return"),
    collection: str = Query("both", description="Collection to query: rfp, supportive, or both"),
    format: str = Query("formatted", description="Response format: formatted or raw")
):
    """View Milvus data or search documents across collections"""
    try:
        logger.info(f"Milvus query: search='{search}', collection='{collection}', format='{format}'")
        results = {}
        
        if collection in ["rfp", "both"]:
            try:
                rfp_client = get_milvus_client("rfp_files")
                if search:
                    rfp_results = rfp_client.search_similar_documents(search, limit)
                    results["rfp_files"] = {
                        "results": rfp_results,
                        "count": len(rfp_results),
                        "type": "search_results",
                        "collection_info": {
                            "name": "rfp_files",
                            "description": "RFP documents (OCR text processing)"
                        }
                    }
                else:
                    rfp_docs = rfp_client.get_all_documents(limit)
                    rfp_stats = rfp_client.get_stats()
                    raw_data = []
                    if format == "raw" and rfp_client.client and rfp_client.client.has_collection("rfp_files"):
                        try:
                            rfp_client.client.load_collection("rfp_files")
                            raw_query_result = rfp_client.client.query(
                                collection_name="rfp_files",
                                filter="",
                                output_fields=["*"],
                                limit=5
                            )
                            raw_data = raw_query_result
                            logger.info(f"Retrieved {len(raw_data)} raw RFP entries")
                        except Exception as e:
                            logger.warning(f"Could not get RFP raw data: {e}")
                    
                    results["rfp_files"] = {
                        "documents": rfp_docs,
                        "stats": rfp_stats,
                        "count": len(rfp_docs),
                        "type": "document_list",
                        "collection_info": {
                            "name": "rfp_files",
                            "description": "RFP documents (OCR text processing)"
                        },
                        "raw_milvus_data": raw_data if format == "raw" else f"Use ?format=raw to see raw Milvus storage format"
                    }
            except Exception as e:
                logger.error(f"RFP collection error: {e}")
                results["rfp_files"] = {"error": str(e), "collection": "rfp_files"}
        if collection in ["supportive", "both"]:
            try:
                supportive_client = get_milvus_client("supportive_files")
                if search:
                    supportive_results = supportive_client.search_similar_documents(search, limit)
                    results["supportive_files"] = {
                        "results": supportive_results,
                        "count": len(supportive_results),
                        "type": "search_results",
                        "collection_info": {
                            "name": "supportive_files",
                            "description": "Supportive documents (OCR text processing)"
                        }
                    }
                else:
                    supportive_docs = supportive_client.get_all_documents(limit)
                    supportive_stats = supportive_client.get_stats()
                    raw_data = []
                    if format == "raw" and supportive_client.client and supportive_client.client.has_collection("supportive_files"):
                        try:
                            supportive_client.client.load_collection("supportive_files")
                            raw_query_result = supportive_client.client.query(
                                collection_name="supportive_files",
                                filter="",
                                output_fields=["*"],
                                limit=5
                            )
                            raw_data = raw_query_result
                            logger.info(f"Retrieved {len(raw_data)} raw supportive entries")
                        except Exception as e:
                            logger.warning(f"Could not get supportive raw data: {e}")
                    
                    results["supportive_files"] = {
                        "documents": supportive_docs,
                        "stats": supportive_stats,
                        "count": len(supportive_docs),
                        "type": "document_list",
                        "collection_info": {
                            "name": "supportive_files",
                            "description": "Supportive documents (OCR text processing)"
                        },
                        "raw_milvus_data": raw_data if format == "raw" else f"Use ?format=raw to see raw Milvus storage format"
                    }
            except Exception as e:
                logger.error(f"Supportive collection error: {e}")
                results["supportive_files"] = {"error": str(e), "collection": "supportive_files"}
        
        total_docs = 0
        for coll_name, coll_data in results.items():
            if not isinstance(coll_data, dict) or "error" in coll_data:
                continue
            total_docs += coll_data.get("count", 0)
        
        return {
            "query_info": {
                "type": "search" if search else "list",
                "search_query": search,
                "response_format": format,
                "collection_filter": collection,
                "limit": limit
            },
            "summary": {
                "total_documents": total_docs,
                "collections_queried": list(results.keys()),
                "available_collections": ["rfp_files", "supportive_files"]
            },
            "collections": results,
            "usage_info": {
                "search_example": "/milvus?search=contract&collection=both&limit=5",
                "raw_data_example": "/milvus?format=raw&collection=rfp&limit=3",
                "collection_specific": "/milvus?collection=supportive&format=formatted"
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Milvus query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
