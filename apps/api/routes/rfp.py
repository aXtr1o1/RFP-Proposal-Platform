from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List, Dict, Any
import msal
import requests
import time
from datetime import datetime
import os
import logging
from dotenv import load_dotenv
import urllib.parse
import sys

load_dotenv()

logger = logging.getLogger(__name__)
router = APIRouter()

TENANT_ID = os.getenv("TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
OCR_KEY = os.getenv("OCR_KEY")
OCR_ENDPOINT = os.getenv("OCR_ENDPOINT")

if not all([TENANT_ID, CLIENT_ID, CLIENT_SECRET, OCR_KEY, OCR_ENDPOINT]):
    missing_vars = []
    if not TENANT_ID: missing_vars.append("TENANT_ID")
    if not CLIENT_ID: missing_vars.append("CLIENT_ID")
    if not CLIENT_SECRET: missing_vars.append("CLIENT_SECRET")
    if not OCR_KEY: missing_vars.append("OCR_KEY")
    if not OCR_ENDPOINT: missing_vars.append("OCR_ENDPOINT")
    
    logger.error(f"Missing required environment variables: {missing_vars}")
    raise ValueError(f"Missing required environment variables: {missing_vars}")

try:
    sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', 'vdb'))
    from milvus_client import get_milvus_client
    logger.info("Milvus client imported successfully")
except ImportError as e:
    logger.warning(f"Milvus client not found: {e}")
    get_milvus_client = None

try:
    workers_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', 'workers', 'ocr')
    sys.path.append(workers_path)
    from worker import OCRWorker
    logger.info("OCR Worker imported successfully")
except ImportError as e:
    logger.warning(f"OCR Worker not found: {e}")
    OCRWorker = None

class OneDriveService:
    def __init__(self):
        self.tenant_id = TENANT_ID
        self.client_id = CLIENT_ID
        self.client_secret = CLIENT_SECRET
        self.access_token = None
        self.base_url = "https://graph.microsoft.com/v1.0"
        
        if OCRWorker:
            self.ocr_worker = OCRWorker()
        else:
            self.ocr_worker = None
            
        self._authenticate()
    
    def _authenticate(self):
        try:
            authority = f"https://login.microsoftonline.com/{self.tenant_id}"
            app = msal.ConfidentialClientApplication(
                client_id=self.client_id,
                client_credential=self.client_secret,
                authority=authority
            )
            
            scopes = ["https://graph.microsoft.com/.default"]
            result = app.acquire_token_for_client(scopes=scopes)
            
            if "access_token" in result:
                self.access_token = result["access_token"]
                logger.info("OneDrive authentication successful")
            else:
                raise Exception(f"Authentication failed: {result.get('error_description')}")
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            raise
    
    def _make_request(self, endpoint):
        headers = {"Authorization": f"Bearer {self.access_token}"}
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed for {endpoint}: {str(e)}")
            return None
    
    def get_all_drives(self):
        drives = []
        result = self._make_request("/drives")
        if result:
            for drive in result.get("value", []):
                drives.append({
                    'id': drive['id'],
                    'name': drive['name'],
                    'type': drive.get('driveType', 'shared')
                })

        users_result = self._make_request("/users")
        if users_result:
            for user in users_result.get("value", [])[:5]:
                user_id = user.get("id")
                display_name = user.get("displayName", "Unknown")
                
                drive_result = self._make_request(f"/users/{user_id}/drive")
                if drive_result:
                    drives.append({
                        'id': drive_result['id'],
                        'name': f"{display_name}'s OneDrive",
                        'type': 'personal'
                    })
        
        return drives
    
    def get_folders_in_drives(self):
        drives = self.get_all_drives()
        all_folders = []
        
        for drive in drives:
            drive_id = drive['id']
            items_result = self._make_request(f"/drives/{drive_id}/root/children")
            
            if items_result:
                for item in items_result.get("value", []):
                    if 'folder' in item:
                        all_folders.append({
                            'drive_id': drive_id,
                            'folder_name': item['name'],
                            'created_datetime': item.get('createdDateTime'),
                            'modified_datetime': item.get('lastModifiedDateTime')
                        })
        
        return all_folders
    
    def get_all_files_recursively(self, drive_id, base_path, max_depth=3, current_depth=0):
        if current_depth >= max_depth:
            return []
        
        all_files = []
        encoded_path = urllib.parse.quote(base_path)
        endpoint = f"/drives/{drive_id}/root:/{encoded_path}:/children"
        result = self._make_request(endpoint)
        
        if not result:
            return []
        
        for item in result.get("value", []):
            if 'file' in item:
                file_info = {
                    'file_id': item['id'],
                    'file_name': item['name'],
                    'file_path': f"{base_path}/{item['name']}",
                    'folder_path': base_path,
                    'file_size': item.get('size', 0),
                    'mime_type': item.get('file', {}).get('mimeType', 'unknown'),
                    'download_url': item.get('@microsoft.graph.downloadUrl'),
                    'created_datetime': item.get('createdDateTime'),
                    'modified_datetime': item.get('lastModifiedDateTime')
                }
                all_files.append(file_info)
            elif 'folder' in item:
                subfolder_path = f"{base_path}/{item['name']}"
                subfolder_files = self.get_all_files_recursively(
                    drive_id, 
                    subfolder_path, 
                    max_depth, 
                    current_depth + 1
                )
                all_files.extend(subfolder_files)
        
        return all_files
    
    def get_folder_structure(self, drive_id, base_path, max_depth=2, current_depth=0):
        if current_depth >= max_depth:
            return {"folders": [], "files": []}
        
        encoded_path = urllib.parse.quote(base_path)
        endpoint = f"/drives/{drive_id}/root:/{encoded_path}:/children"
        result = self._make_request(endpoint)
        
        if not result:
            return {"folders": [], "files": []}
        
        folders = []
        files = []
        
        for item in result.get("value", []):
            if 'folder' in item:
                folder_info = {
                    'folder_name': item['name'],
                    'folder_path': f"{base_path}/{item['name']}",
                    'child_count': item.get('folder', {}).get('childCount', 0),
                    'created_datetime': item.get('createdDateTime'),
                    'modified_datetime': item.get('lastModifiedDateTime')
                }
                
                if current_depth < max_depth - 1:
                    nested_structure = self.get_folder_structure(
                        drive_id, 
                        f"{base_path}/{item['name']}", 
                        max_depth, 
                        current_depth + 1
                    )
                    folder_info['subfolders'] = nested_structure['folders']
                    folder_info['files'] = nested_structure['files']
                
                folders.append(folder_info)
                
            elif 'file' in item:
                file_info = {
                    'file_name': item['name'],
                    'file_path': f"{base_path}/{item['name']}",
                    'file_size': item.get('size', 0),
                    'mime_type': item.get('file', {}).get('mimeType', 'unknown'),
                    'download_url': item.get('@microsoft.graph.downloadUrl'),
                    'created_datetime': item.get('createdDateTime'),
                    'modified_datetime': item.get('lastModifiedDateTime')
                }
                files.append(file_info)
        
        return {"folders": folders, "files": files}
    
    def download_file(self, download_url):
        try:
            response = requests.get(download_url)
            response.raise_for_status()
            return response.content
        except Exception as e:
            logger.error(f"Error downloading file: {e}")
            return None
    
    def process_file_with_ocr(self, file_content, file_name, file_type="document"):
        if self.ocr_worker:
            return self.ocr_worker.process_file(file_content, file_name, file_type)
        else:
            return self._fallback_ocr_processing(file_content, file_name, file_type)
    
    def _fallback_ocr_processing(self, file_content, file_name, file_type="document"):
        url = f"{OCR_ENDPOINT}/formrecognizer/documentModels/prebuilt-layout:analyze?api-version=2023-07-31"
        
        headers = {
            'Ocp-Apim-Subscription-Key': OCR_KEY,
            'Content-Type': 'application/octet-stream'
        }
        
        try:
            response = requests.post(url, headers=headers, data=file_content)
            
            if response.status_code == 202:
                operation_url = response.headers['Operation-Location']
                poll_headers = {'Ocp-Apim-Subscription-Key': OCR_KEY}
                
                max_attempts = 30
                attempt = 0
                
                while attempt < max_attempts:
                    result = requests.get(operation_url, headers=poll_headers)
                    data = result.json()
                    
                    if data['status'] == 'succeeded':
                        pages_data = []
                        if 'analyzeResult' in data and 'pages' in data['analyzeResult']:
                            for page_idx, page in enumerate(data['analyzeResult']['pages']):
                                if 'lines' in page:
                                    content = ' '.join([line['content'] for line in page['lines']])
                                    if content.strip():
                                        pages_data.append({
                                            "file_name": file_name,
                                            "file_type": file_type,
                                            "page": page_idx + 1,
                                            "content": content,
                                            "word_count": len(content.split()),
                                            "timestamp": datetime.now().isoformat()
                                        })
                        
                        return pages_data
                        
                    elif data['status'] == 'failed':
                        logger.error(f"OCR failed for {file_name}: {data}")
                        return []
                    else:
                        time.sleep(2)
                        attempt += 1
                
                return []
            else:
                logger.error(f"OCR request failed for {file_name}: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"OCR Error for {file_name}: {e}")
            return []

# Global service instance
onedrive_service = None

def get_onedrive_service():
    global onedrive_service
    if onedrive_service is None:
        onedrive_service = OneDriveService()
    return onedrive_service

def determine_file_type(file_info: Dict) -> str:
    file_name = file_info['file_name'].lower()
    folder_path = file_info.get('folder_path', '').lower()
    
    if 'rfp' in file_name or 'rfp' in folder_path:
        return "RFP"
    elif 'support' in file_name or 'support' in folder_path:
        return "supportiveFile"
    elif 'proposal' in file_name:
        return "proposal"
    else:
        return "document"

async def get_available_folders():
    """Get available folders inside RFP-Uploads (not RFP-Uploads itself)"""
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
        
        # Get folders inside RFP-Uploads
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
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching folders: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def process_folder_with_ocr_and_vectors(folder_name: str, background_tasks=None):
    """Process folder with OCR and automatically save to Milvus"""
    try:
        start_time = datetime.now()
        logger.info(f"Processing folder '{folder_name}' with OCR and vector storage")
        
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
        
        # Get files from specified folder
        search_path = f"RFP-Uploads/{folder_name}"
        all_files = service.get_all_files_recursively(rfp_folder['drive_id'], search_path, max_depth=3)
        
        if not all_files:
            raise HTTPException(status_code=404, detail=f"No files found in folder '{folder_name}'")
        
        # Filter PDF files
        pdf_files = [f for f in all_files if f['mime_type'] == 'application/pdf' or f['file_name'].lower().endswith('.pdf')]
        
        if not pdf_files:
            raise HTTPException(status_code=404, detail="No PDF files found for OCR processing")
        
        # Process PDFs with OCR
        all_ocr_results = []
        processed_files = []
        failed_files = []
        
        for pdf_file in pdf_files:
            try:
                if not pdf_file.get('download_url'):
                    failed_files.append({"file_name": pdf_file['file_name'], "reason": "No download URL"})
                    continue
                
                logger.info(f"Processing file: {pdf_file['file_name']}")
                file_content = service.download_file(pdf_file['download_url'])
                
                if not file_content:
                    failed_files.append({"file_name": pdf_file['file_name'], "reason": "Download failed"})
                    continue
                
                file_type = determine_file_type(pdf_file)
                ocr_results = service.process_file_with_ocr(file_content, pdf_file['file_name'], file_type)
                
                if ocr_results:
                    # Add path info to OCR results
                    for result in ocr_results:
                        result['file_path'] = pdf_file.get('file_path', pdf_file['file_name'])
                        result['folder_path'] = pdf_file.get('folder_path', 'unknown')
                    
                    all_ocr_results.extend(ocr_results)
                    processed_files.append({
                        "file_name": pdf_file['file_name'],
                        "pages_processed": len(ocr_results),
                        "total_words": sum([r.get('word_count', 0) for r in ocr_results])
                    })
                else:
                    failed_files.append({"file_name": pdf_file['file_name'], "reason": "OCR failed"})
                    
            except Exception as e:
                logger.error(f"Error processing {pdf_file['file_name']}: {e}")
                failed_files.append({"file_name": pdf_file['file_name'], "reason": str(e)})
        
        if not all_ocr_results:
            raise HTTPException(status_code=400, detail="No documents processed successfully")
        
        # Group OCR results by document for response
        documents = {}
        for result in all_ocr_results:
            file_name = result.get('file_name', 'unknown')
            if file_name not in documents:
                documents[file_name] = {
                    'file_name': file_name,
                    'file_type': result.get('file_type'),
                    'file_path': result.get('file_path'),
                    'pages': []
                }
            documents[file_name]['pages'].append({
                'page_number': result.get('page', 1),
                'content': result.get('content', ''),
                'word_count': result.get('word_count', 0)
            })
        
        # Calculate totals for each document
        for doc in documents.values():
            doc['total_pages'] = len(doc['pages'])
            doc['total_words'] = sum([p['word_count'] for p in doc['pages']])
            doc['combined_content'] = ' '.join([p['content'] for p in doc['pages']])
        
        # Auto save to Milvus
        vector_result = {}
        try:
            if get_milvus_client:
                milvus_client = get_milvus_client()
                if milvus_client.is_available():
                    vector_ids = milvus_client.save_documents(all_ocr_results, folder_name)
                    vector_result = {
                        "vector_stored": True,
                        "documents_stored": len(vector_ids),
                        "vector_ids": vector_ids,
                        "embedding_model": "MiniLM-L6-v2"
                    }
                    logger.info(f"Saved {len(vector_ids)} documents to Milvus")
                else:
                    vector_result = {"vector_stored": False, "reason": "Milvus not available"}
            else:
                vector_result = {"vector_stored": False, "reason": "Milvus client not imported"}
        except Exception as e:
            logger.error(f"Vector storage error: {e}")
            vector_result = {"vector_stored": False, "error": str(e)}
        
        processing_time = str(datetime.now() - start_time)
        
        return {
            "folder_name": folder_name,
            "total_files": len(all_files),
            "pdf_files": len(pdf_files),
            "processed_files": len(processed_files),
            "failed_files": len(failed_files),
            "ocr_results": {
                "documents": list(documents.values()),
                "total_documents": len(documents),
                "total_pages": sum([doc['total_pages'] for doc in documents.values()]),
                "total_words": sum([doc['total_words'] for doc in documents.values()])
            },
            "vector_storage": vector_result,
            "processing_time": processing_time,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing folder: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def get_milvus_data():
    """View stored vector documents"""
    try:
        if not get_milvus_client:
            raise HTTPException(status_code=503, detail="Milvus client not available")
        
        milvus_client = get_milvus_client()
        
        if not milvus_client.is_available():
            raise HTTPException(status_code=503, detail="Milvus database not available")
        
        documents = milvus_client.get_all_documents(limit=100)
        stats = milvus_client.get_stats()
        
        return {
            "database_info": {
                "total_documents": stats.get("total_documents", 0),
                "embedding_model": stats.get("embedding_model", "unknown"),
                "collection_name": stats.get("collection_name", "unknown"),
                "file_types": stats.get("file_types", {}),
                "folders": stats.get("folders", {})
            },
            "documents_returned": len(documents),
            "documents": documents,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting Milvus data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def get_rfp_uploads_files():
    """Legacy: Get complete folder structure from RFP-Uploads"""
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
        
        structure = service.get_folder_structure(rfp_folder['drive_id'], 'RFP-Uploads', max_depth=3)
        
        # Flatten all files
        all_files = []
        def collect_files(folders_list, files_list):
            all_files.extend(files_list)
            for folder in folders_list:
                if 'files' in folder:
                    all_files.extend(folder['files'])
                if 'subfolders' in folder:
                    collect_files(folder['subfolders'], folder.get('files', []))
        
        collect_files(structure['folders'], structure['files'])
        
        return {
            "folder_name": "RFP-Uploads",
            "folder_info": rfp_folder,
            "folder_structure": structure,
            "all_files_flattened": all_files,
            "total_nested_folders": len(structure['folders']),
            "total_files": len(all_files),
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching RFP-Uploads structure: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def process_folder_with_ocr(folder_name: str, background_tasks=None):
    """Legacy: Process folder with OCR (without vector storage)"""
    return await process_folder_with_ocr_and_vectors(folder_name, background_tasks)
