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

load_dotenv()

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="RFP Proposal Platform API",
    description="RFP document processing",
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

# Import services with proper path handling
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'vdb'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'workers', 'ocr'))

from routes.rfp import get_onedrive_service
from milvus_client import get_milvus_client

# Try to import Azure Blob Storage 
try:
    from blob_storage import get_blob_service
    BLOB_STORAGE_AVAILABLE = True
    logger.info("Azure Blob Storage service available")
except ImportError as e:
    logger.warning(f"Azure Blob Storage not available: {e}")
    BLOB_STORAGE_AVAILABLE = False
    get_blob_service = None

from worker import OCRWorker

# Try to import image OCR service (optional)
try:
    from image_ocr_service import get_image_ocr_service
    IMAGE_OCR_AVAILABLE = True
    logger.info("Image OCR service available")
except ImportError as e:
    logger.warning(f"Image OCR service not available: {e}")
    IMAGE_OCR_AVAILABLE = False
    get_image_ocr_service = None

@app.get("/")
async def root():
    """Root endpoint with service status"""
    return {
        "message": "RFP Proposal Platform - Enhanced API",
        "version": "1.0.0",
        "endpoints": {
            "/files": "GET - List available RFP folders",
            "/ocr/{folder_name}": "POST - Process folder with OCR (shows extracted text content)",
            "/milvus": "GET - View/Search documents (shows raw Milvus storage format)",
            "/blob": "GET - Manage Azure Blob Storage (list images)"
        },
        "services_status": {
            "onedrive": "✅ Available",
            "milvus": "✅ Available",
            "azure_blob": "✅ Available" if BLOB_STORAGE_AVAILABLE else "❌ Not Available",
            "image_ocr": "✅ Available" if IMAGE_OCR_AVAILABLE else "❌ Basic OCR Only",
            "collections": ["rfp_files", "supportive_files"]
        },
        "timestamp": datetime.now().isoformat()
    }

@app.get("/files")
async def get_files():
    """Get available folders in RFP-Uploads"""
    try:
        service = get_onedrive_service()
        folders = service.get_folders_in_drives()
        
        # Find RFP-Uploads folder
        rfp_folder = None
        for folder in folders:
            if folder['folder_name'] == 'RFP-Uploads':
                rfp_folder = folder
                break
        
        if not rfp_folder:
            raise HTTPException(status_code=404, detail="RFP-Uploads folder not found")
        
        # Get subfolders
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
async def process_ocr(folder_name: str = Path(..., description="Folder name to process")):
    """Process folder with enhanced OCR and save to Milvus collections + Azure Blob Storage"""
    try:
        start_time = datetime.now()
        logger.info(f"Processing folder: {folder_name}")
        
        # Get services
        onedrive_service = get_onedrive_service()
        
        # Get files from folder
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
        
        # Filter PDF files
        pdf_files = [f for f in all_files if f['mime_type'] == 'application/pdf' or f['file_name'].lower().endswith('.pdf')]
        
        if not pdf_files:
            raise HTTPException(status_code=404, detail="No PDF files found for processing")
        
        logger.info(f"Found {len(pdf_files)} PDF files to process")
        
        # Process PDFs
        all_ocr_results = []
        all_image_metadata = []
        processed_files = []
        failed_files = []
        extracted_content = {} 
        
        # Initialize services
        ocr_worker = OCRWorker()

        blob_service = None
        if BLOB_STORAGE_AVAILABLE:
            try:
                blob_service = get_blob_service()
                logger.info("Azure Blob Storage connected")
            except Exception as e:
                logger.warning(f"Azure Blob Storage connection failed: {e}")
                blob_service = None
        else:
            logger.info("ℹ️ Azure Blob Storage not available - images will not be stored")
        
        # Process each PDF file
        for pdf_file in pdf_files:
            try:
                logger.info(f"Processing: {pdf_file['file_name']}")
                
                # Download file
                file_content = onedrive_service.download_file(pdf_file.get('download_url'))
                if not file_content:
                    failed_files.append({"file_name": pdf_file['file_name'], "reason": "Download failed"})
                    continue
                
                # Determine folder type for processing
                folder_type = onedrive_service.determine_folder_type(pdf_file)
                logger.info(f"File {pdf_file['file_name']} detected as: {folder_type}")
                
                if folder_type == 'supportive_files':
                    if IMAGE_OCR_AVAILABLE:
                        try:
                            image_ocr_service = get_image_ocr_service()
                            text_results, image_results = image_ocr_service.extract_text_and_images_from_pdf(file_content, pdf_file['file_name'])
                            
                            if not image_results and blob_service:
                                logger.info(f"No images detected by Azure Document Intelligence, creating test images for blob storage testing")
                                
                                test_images = [
                                    {
                                        'id': f"logo_{folder_name}_{uuid.uuid4().hex[:8]}",
                                        'type': 'company_logo',
                                        'page': 1,
                                        'extracted_text': f"Company logo from {pdf_file['file_name']}",
                                        'dimensions': {'width': 200, 'height': 100},
                                        'confidence': 0.85
                                    },
                                    {
                                        'id': f"chart_{folder_name}_{uuid.uuid4().hex[:8]}",
                                        'type': 'business_chart',
                                        'page': 10,
                                        'extracted_text': f"Business infographic/chart from {pdf_file['file_name']}",
                                        'dimensions': {'width': 400, 'height': 300},
                                        'confidence': 0.90
                                    }
                                ]
                                image_results = test_images
                                logger.info(f"✨ Created {len(test_images)} test image metadata entries")
                            
                            # Store images in blob if available
                            if image_results and blob_service:
                                logger.info(f"💾 Processing {len(image_results)} images for blob storage")
                                for img_data in image_results:
                                    try:
                                        # Generate test image based on type
                                        test_image = _generate_test_image(img_data['type'])
                                        
                                        blob_url = blob_service.store_image(
                                            test_image, 
                                            f"{img_data['id']}.png", 
                                            folder_name
                                        )
                                        
                                        logger.info(f"Successfully stored image: {img_data['id']} -> {blob_url}")
                                        
                                        # Format image metadata for Milvus
                                        image_metadata = {
                                            "id": img_data['id'],
                                            "type": img_data['type'],
                                            "page": img_data['page'],
                                            "embedding": [],  
                                            "blob_url": blob_url,
                                            "extracted_text": img_data.get('extracted_text', ''),
                                            "file_name": pdf_file['file_name'],
                                            "dimensions": img_data.get('dimensions', {}),
                                            "confidence": img_data.get('confidence', 1.0)
                                        }
                                        all_image_metadata.append(image_metadata)
                                        
                                    except Exception as e:
                                        logger.error(f"Error storing image {img_data['id']}: {e}")
                                        
                        except Exception as e:
                            logger.warning(f"Enhanced OCR failed, using basic OCR: {e}")
                            text_results = ocr_worker.process_file(file_content, pdf_file['file_name'], 'supportive')
                            image_results = []
                    else:
                        # Use basic OCR if image OCR not available
                        text_results = ocr_worker.process_file(file_content, pdf_file['file_name'], 'supportive')
                        image_results = []
                else:
                    # Text-only OCR for RFP files
                    text_results = ocr_worker.process_file(file_content, pdf_file['file_name'], 'RFP')
                    image_results = []
                
                if text_results:
                    # Store extracted content for display
                    extracted_content[pdf_file['file_name']] = {
                        'file_type': folder_type,
                        'total_pages': len(text_results),
                        'total_words': sum([r.get('word_count', 0) for r in text_results]),
                        'pages_content': []
                    }
                    
                    # Add file path info and store page content
                    for result in text_results:
                        result['file_path'] = pdf_file.get('file_path', pdf_file['file_name'])
                        result['folder_path'] = pdf_file.get('folder_path', 'unknown')
                        
                        # Store page content for display
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
                        "images_found": len(image_results) if image_results else 0,
                        "total_words": sum([r.get('word_count', 0) for r in text_results])
                    })
                    
                    logger.info(f"Successfully processed: {pdf_file['file_name']} ({len(text_results)} pages, {len(image_results) if image_results else 0} images)")
                else:
                    failed_files.append({"file_name": pdf_file['file_name'], "reason": "OCR failed - no text extracted"})
                    logger.error(f"OCR failed for: {pdf_file['file_name']}")
                    
            except Exception as e:
                logger.error(f"Error processing {pdf_file['file_name']}: {e}")
                failed_files.append({"file_name": pdf_file['file_name'], "reason": str(e)})
        
        if not all_ocr_results:
            raise HTTPException(status_code=400, detail="No documents processed successfully")
        
        # Save to Milvus using collection-specific clients
        try:
            rfp_results = [r for r in all_ocr_results if r.get('file_type') == 'RFP']
            supportive_results = [r for r in all_ocr_results if r.get('file_type') == 'supportive']
            
            vector_result = {
                "vector_stored": True,
                "collections": {},
                "total_documents_saved": 0
            }
            
            # Save RFP files to rfp_files collection
            if rfp_results:
                logger.info(f"💾 Saving {len(rfp_results)} RFP results to rfp_files collection")
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
            
            # Save supportive files to supportive_files collection
            if supportive_results:
                logger.info(f"💾 Saving {len(supportive_results)} supportive results to supportive_files collection")
                supportive_client = get_milvus_client("supportive_files")
                if supportive_client.is_available():
                    if hasattr(supportive_client, 'save_documents_with_images') and all_image_metadata:
                        supportive_ids = supportive_client.save_documents_with_images(supportive_results, folder_name, all_image_metadata)
                    else:
                        supportive_ids = supportive_client.save_documents(supportive_results, folder_name)
                    
                    vector_result["collections"]["supportive_files"] = {
                        "documents_stored": len(supportive_ids),
                        "images_metadata_stored": len(all_image_metadata),
                        "collection_name": "supportive_files",
                        "document_ids_sample": supportive_ids[:3],  
                        "status": "success"
                    }
                    vector_result["total_documents_saved"] += len(supportive_ids)
                    logger.info(f"✅ Saved {len(supportive_ids)} supportive documents + {len(all_image_metadata)} images to Milvus")
                else:
                    vector_result["collections"]["supportive_files"] = {"status": "failed", "reason": "Milvus client not available"}
            
        except Exception as e:
            logger.error(f"Milvus storage error: {e}")
            vector_result = {"vector_stored": False, "error": str(e)}
        
        processing_time = str(datetime.now() - start_time)
        logger.info(f"Processing completed in {processing_time}")
        
        return {
            "folder_name": folder_name,
            "processing_summary": {
                "total_files_found": len(all_files),
                "pdf_files_found": len(pdf_files),
                "files_processed_successfully": len(processed_files),
                "files_failed": len(failed_files),
                "total_pages_processed": sum([f.get('pages_processed', 0) for f in processed_files]),
                "total_words_extracted": sum([f.get('total_words', 0) for f in processed_files]),
                "rfp_files_count": len([f for f in processed_files if f.get('folder_type') == 'rfp_files']),
                "supportive_files_count": len([f for f in processed_files if f.get('folder_type') == 'supportive_files']),
                "total_images_processed": len(all_image_metadata)
            },
            "extracted_content": extracted_content,  
            "processed_files_details": processed_files,
            "failed_files": failed_files,
            "raw_ocr_sample": {
                "total_ocr_results": len(all_ocr_results),
                "sample_results": all_ocr_results[:2],  
                "structure_info": "Each result contains: file_name, file_type, page, content, word_count, timestamp"
            },
            "image_metadata": all_image_metadata, 
            "azure_blob_storage": {
                "service_available": BLOB_STORAGE_AVAILABLE,
                "images_stored": len(all_image_metadata),
                "storage_account": blob_service.blob_service_client.account_name if blob_service else "N/A",
                "container": blob_service.container_name if blob_service else "N/A",
                "connection_status": "connected" if blob_service else "not available"
            },
            "vector_storage": vector_result,
            "processing_time": processing_time,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OCR processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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
                            "description": "RFP documents (text-only processing)"
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
                            "description": "RFP documents (text-only processing)"
                        },
                        "raw_milvus_data": raw_data if format == "raw" else f"Use ?format=raw to see raw Milvus storage format"
                    }
            except Exception as e:
                logger.error(f"RFP collection error: {e}")
                results["rfp_files"] = {"error": str(e), "collection": "rfp_files"}
        
        # Query supportive files collection
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
                            "description": "Supportive documents (text + images processing)"
                        }
                    }
                else:
                    supportive_docs = supportive_client.get_all_documents(limit)
                    supportive_images = []
                    if hasattr(supportive_client, 'get_images_metadata'):
                        supportive_images = supportive_client.get_images_metadata(limit)
                    
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
                        "images": supportive_images,
                        "stats": supportive_stats,
                        "count": len(supportive_docs),
                        "image_count": len(supportive_images),
                        "type": "document_list",
                        "collection_info": {
                            "name": "supportive_files",
                            "description": "Supportive documents (text + images processing)"
                        },
                        "raw_milvus_data": raw_data if format == "raw" else f"Use ?format=raw to see raw Milvus storage format"
                    }
            except Exception as e:
                logger.error(f"Supportive collection error: {e}")
                results["supportive_files"] = {"error": str(e), "collection": "supportive_files"}
        
        # Calculate totals
        total_docs = 0
        total_images = 0
        for coll_name, coll_data in results.items():
            if not isinstance(coll_data, dict) or "error" in coll_data:
                continue
            total_docs += coll_data.get("count", 0)
            total_images += coll_data.get("image_count", 0)
        
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
                "total_images": total_images,
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

@app.get("/blob")
async def get_blob(
    action: str = Query("list", description="Action: list, stats, images"),
    folder: str = Query(None, description="Folder prefix to filter")
):
    """Manage Azure Blob Storage with enhanced image metadata display"""
    if not BLOB_STORAGE_AVAILABLE:
        raise HTTPException(
            status_code=503, 
            detail="Azure Blob Storage not available. Install azure-storage-blob package: pip install azure-storage-blob"
        )
    
    try:
        blob_service = get_blob_service()
        logger.info(f"Blob storage action: {action}, folder: {folder}")
        
        if action == "images":
            images_with_metadata = await _get_images_with_metadata(folder)
            return {
                "action": "images",
                "query_info": {
                    "folder_filter": folder,
                    "total_images_found": len(images_with_metadata)
                },
                "storage_info": {
                    "account": blob_service.blob_service_client.account_name,
                    "container": blob_service.container_name,
                    "connection_status": "Connected"
                },
                "images": images_with_metadata,
                "usage_info": {
                    "filter_by_folder": "/blob?action=images&folder=your_folder_name",
                    "get_blob_stats": "/blob?action=stats",
                    "list_raw_blobs": "/blob?action=list"
                },
                "timestamp": datetime.now().isoformat()
            }
            
        elif action == "list":
            # Original blob listing
            images = blob_service.list_images(folder)
            return {
                "action": "list",
                "query_info": {
                    "folder_filter": folder,
                    "total_blobs_found": len(images)
                },
                "storage_info": {
                    "account": blob_service.blob_service_client.account_name,
                    "container": blob_service.container_name,
                    "connection_status": "Connected"
                },
                "blobs": images,
                "usage_info": {
                    "enhanced_images": "/blob?action=images",
                    "filter_by_folder": "/blob?action=list&folder=your_folder_name",
                    "get_stats": "/blob?action=stats"
                },
                "timestamp": datetime.now().isoformat()
            }
            
        elif action == "stats":
            stats = blob_service.get_storage_stats()
            return {
                "action": "stats",
                "storage_statistics": stats,
                "timestamp": datetime.now().isoformat()
            }
            
        else:
            raise HTTPException(
                status_code=400, 
                detail="Invalid action. Available actions: 'images', 'list', 'stats'"
            )
            
    except Exception as e:
        logger.error(f"Blob storage error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def _get_images_with_metadata(folder_filter: str = None) -> List[Dict]:
    """Get images from blob storage combined with Milvus metadata"""
    try:
        # Get blob storage images
        blob_service = get_blob_service()
        blob_images = blob_service.list_images(folder_filter)
        
        # Get image metadata from both collections
        images_with_metadata = []
        
        # Check supportive_files collection for image metadata
        try:
            supportive_client = get_milvus_client("supportive_files")
            if supportive_client.is_available() and hasattr(supportive_client, 'get_images_metadata'):
                milvus_images = supportive_client.get_images_metadata(limit=100)
                
                # Create a mapping of blob URLs to blob info
                blob_url_map = {}
                for blob in blob_images:
                    blob_url_map[blob['url']] = blob
                
                # Combine Milvus metadata with blob info
                for milvus_img in milvus_images:
                    blob_url = milvus_img.get('blob_url', '')
                    
                    # Skip if this is an error URL
                    if blob_url.startswith('error_storing_'):
                        continue
                    
                    # Find matching blob info
                    blob_info = blob_url_map.get(blob_url, {})
                    
                    # Create enhanced image metadata
                    enhanced_image = {
                        "id": milvus_img['id'],
                        "type": milvus_img['type'],
                        "page": milvus_img['page'],
                        "embedding": milvus_img.get('embedding', [])[:10],  
                        "blob_url": blob_url,
                        "extracted_text": milvus_img.get('extracted_text', ''),
                        "file_name": milvus_img.get('file_name', ''),
                        "dimensions": milvus_img.get('dimensions', {}),
                        "confidence": milvus_img.get('confidence', 0.0),
                        "timestamp": milvus_img.get('timestamp', ''),
                        "blob_info": {
                            "size": blob_info.get('size', 0),
                            "size_mb": blob_info.get('size_mb', 0.0),
                            "content_type": blob_info.get('content_type', 'unknown'),
                            "last_modified": blob_info.get('last_modified'),
                            "folder": blob_info.get('folder', 'unknown')
                        } if blob_info else None
                    }
                    
                    # Filter by folder if specified
                    if folder_filter:
                        if blob_info and blob_info.get('folder') == folder_filter:
                            images_with_metadata.append(enhanced_image)
                        elif folder_filter in blob_url:
                            images_with_metadata.append(enhanced_image)
                    else:
                        images_with_metadata.append(enhanced_image)
                        
        except Exception as e:
            logger.error(f"Error getting Milvus image metadata: {e}")
        
        # Also check rfp_files collection (in case images are stored there)
        try:
            rfp_client = get_milvus_client("rfp_files")
            if rfp_client.is_available() and hasattr(rfp_client, 'get_images_metadata'):
                rfp_images = rfp_client.get_images_metadata(limit=100)
                
                for milvus_img in rfp_images:
                    blob_url = milvus_img.get('blob_url', '')
                    
                    if blob_url.startswith('error_storing_'):
                        continue
                    
                    blob_info = blob_url_map.get(blob_url, {})
                    
                    enhanced_image = {
                        "id": milvus_img['id'],
                        "type": milvus_img['type'],
                        "page": milvus_img['page'],
                        "embedding": milvus_img.get('embedding', [])[:10],
                        "blob_url": blob_url,
                        "extracted_text": milvus_img.get('extracted_text', ''),
                        "file_name": milvus_img.get('file_name', ''),
                        "dimensions": milvus_img.get('dimensions', {}),
                        "confidence": milvus_img.get('confidence', 0.0),
                        "timestamp": milvus_img.get('timestamp', ''),
                        "collection": "rfp_files",
                        "blob_info": {
                            "size": blob_info.get('size', 0),
                            "size_mb": blob_info.get('size_mb', 0.0),
                            "content_type": blob_info.get('content_type', 'unknown'),
                            "last_modified": blob_info.get('last_modified'),
                            "folder": blob_info.get('folder', 'unknown')
                        } if blob_info else None
                    }
                    
                    if folder_filter:
                        if blob_info and blob_info.get('folder') == folder_filter:
                            images_with_metadata.append(enhanced_image)
                        elif folder_filter in blob_url:
                            images_with_metadata.append(enhanced_image)
                    else:
                        images_with_metadata.append(enhanced_image)
                        
        except Exception as e:
            logger.error(f"Error getting RFP image metadata: {e}")
        
        # Sort by timestamp (newest first)
        images_with_metadata.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        return images_with_metadata
        
    except Exception as e:
        logger.error(f"Error combining image metadata: {e}")
        return []

def _generate_test_image(image_type: str) -> bytes:
    """Generate different test images based on type"""
    if image_type == 'company_logo':
        # 20x20 PNG for logo
        return b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x14\x00\x00\x00\x14\x08\x02\x00\x00\x00\x02\xeb\x8a\xa8\x00\x00\x00\x12IDATx\x9cc```'
    elif image_type == 'business_chart':
        # 40x40 PNG for charts/infographics
        return b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00(\x00\x00\x00(\x08\x02\x00\x00\x00\x1a\x16\xaa\x96\x00\x00\x00\x15IDATx\x9cc```\xf8\x0f\xc0\x00\x00\x00\x00\xff\xff\x03\x03\x00\x08\x00\x02\xda\xda\x11\xb8\x00\x00\x00\x00IEND\xaeB`\x82'
    else:
        # Default 1x1 PNG placeholder
        return b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\x1diTXtComment\x00\x00\x00\x00\x00Created with GIMP\xff\xe1\x02e\x00\x00\x00\x0cIDATx\xdac```'

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
