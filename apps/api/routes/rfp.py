from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import msal
import requests
import time
from datetime import datetime
import os
import logging
from dotenv import load_dotenv
import uuid
import urllib.parse

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)
router = APIRouter()

# Configuration from environment
TENANT_ID = os.getenv("TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
OCR_KEY = os.getenv("OCR_KEY")
OCR_ENDPOINT = os.getenv("OCR_ENDPOINT")

# Validate required environment variables
if not all([TENANT_ID, CLIENT_ID, CLIENT_SECRET, OCR_KEY, OCR_ENDPOINT]):
    missing_vars = []
    if not TENANT_ID: missing_vars.append("TENANT_ID")
    if not CLIENT_ID: missing_vars.append("CLIENT_ID")
    if not CLIENT_SECRET: missing_vars.append("CLIENT_SECRET")
    if not OCR_KEY: missing_vars.append("OCR_KEY")
    if not OCR_ENDPOINT: missing_vars.append("OCR_ENDPOINT")
    
    logger.error(f"Missing required environment variables: {missing_vars}")
    raise ValueError(f"Missing required environment variables: {missing_vars}")

# Import OCR worker
try:
    import sys
    import os
    workers_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'workers', 'ocr')
    sys.path.append(workers_path)
    from worker import OCRWorker
    logger.info("OCR Worker imported successfully")
except ImportError as e:
    logger.warning(f"OCR Worker not found: {e}, using fallback implementation")
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
            logger.info("OCR Worker initialized successfully")
        else:
            self.ocr_worker = None
            logger.warning("Using fallback OCR implementation")
            
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
        
        # Get shared drives
        result = self._make_request("/drives")
        if result:
            shared_drives = result.get("value", [])
            for drive in shared_drives:
                drives.append({
                    'id': drive['id'],
                    'name': drive['name'],
                    'type': drive.get('driveType', 'shared'),
                    'url': drive.get('webUrl', 'No URL')
                })
        
        # Get user drives  
        users_result = self._make_request("/users")
        if users_result:
            users = users_result.get("value", [])
            for user in users[:5]:
                user_id = user.get("id")
                display_name = user.get("displayName", "Unknown")
                
                drive_result = self._make_request(f"/users/{user_id}/drive")
                if drive_result:
                    drives.append({
                        'id': drive_result['id'],
                        'name': f"{display_name}'s OneDrive",
                        'type': 'personal',
                        'url': drive_result.get('webUrl', 'No URL')
                    })
        
        return drives
    
    def get_folders_in_drives(self):
        drives = self.get_all_drives()
        all_folders = []
        
        for drive in drives:
            drive_id = drive['id']
            items_result = self._make_request(f"/drives/{drive_id}/root/children")
            
            if items_result:
                items = items_result.get("value", [])
                for item in items:
                    if 'folder' in item:
                        all_folders.append({
                            'drive_id': drive_id,
                            'drive_name': drive['name'],
                            'folder_id': item['id'],
                            'folder_name': item['name'],
                            'folder_path': item['name'],
                            'web_url': item.get('webUrl', 'No URL'),
                            'created_datetime': item.get('createdDateTime'),
                            'modified_datetime': item.get('lastModifiedDateTime')
                        })
        
        return all_folders
    
    def get_all_files_recursively(self, drive_id, base_path, max_depth=3, current_depth=0):
        """FIXED: Recursively get all files from nested folder structure"""
        if current_depth >= max_depth:
            return []
        
        all_files = []
        encoded_path = urllib.parse.quote(base_path)
        endpoint = f"/drives/{drive_id}/root:/{encoded_path}:/children"
        result = self._make_request(endpoint)
        
        if not result:
            return []
        
        items = result.get("value", [])
        
        for item in items:
            if 'file' in item:
                # It's a file - FIXED the variable name bug
                file_info = {
                    'file_id': item['id'],
                    'file_name': item['name'],
                    'file_path': f"{base_path}/{item['name']}",
                    'folder_path': base_path,
                    'file_size': item.get('size', 0),
                    'mime_type': item.get('file', {}).get('mimeType', 'unknown'),
                    'web_url': item.get('webUrl', 'No URL'),
                    'download_url': item.get('@microsoft.graph.downloadUrl'),
                    'created_datetime': item.get('createdDateTime'),
                    'modified_datetime': item.get('lastModifiedDateTime')
                }
                all_files.append(file_info)  # FIXED: append to all_files
            elif 'folder' in item:
                # It's a folder, recurse into it
                subfolder_path = f"{base_path}/{item['name']}"
                subfolder_files = self.get_all_files_recursively(
                    drive_id, 
                    subfolder_path, 
                    max_depth, 
                    current_depth + 1
                )
                all_files.extend(subfolder_files)
        
        return all_files
    
    def get_folder_structure(self, drive_id, base_path, max_depth=3, current_depth=0):
        """Get complete folder structure with files"""
        if current_depth >= max_depth:
            return {"folders": [], "files": []}
        
        encoded_path = urllib.parse.quote(base_path)
        endpoint = f"/drives/{drive_id}/root:/{encoded_path}:/children"
        result = self._make_request(endpoint)
        
        if not result:
            return {"folders": [], "files": []}
        
        folders = []
        files = []
        items = result.get("value", [])
        
        for item in items:
            if 'folder' in item:
                folder_info = {
                    'folder_id': item['id'],
                    'folder_name': item['name'],
                    'folder_path': f"{base_path}/{item['name']}",
                    'parent_path': base_path,
                    'child_count': item.get('folder', {}).get('childCount', 0),
                    'web_url': item.get('webUrl', 'No URL'),
                    'created_datetime': item.get('createdDateTime'),
                    'modified_datetime': item.get('lastModifiedDateTime')
                }
                
                # Get nested structure
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
                    'file_id': item['id'],
                    'file_name': item['name'],
                    'file_path': f"{base_path}/{item['name']}",
                    'folder_path': base_path,
                    'file_size': item.get('size', 0),
                    'mime_type': item.get('file', {}).get('mimeType', 'unknown'),
                    'web_url': item.get('webUrl', 'No URL'),
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

def generate_files_summary(ocr_results: List[Dict]) -> Dict:
    if not ocr_results:
        return {
            "files_processed": 0,
            "total_pages": 0,
            "total_words": 0,
            "files_summary": []
        }
    
    files_summary = {}
    for result in ocr_results:
        file_name = result['file_name']
        if file_name not in files_summary:
            files_summary[file_name] = {
                'file_name': file_name,
                'file_type': result['file_type'],
                'pages': [],
                'total_words': 0,
                'page_count': 0
            }
        
        files_summary[file_name]['pages'].append({
            'page': result['page'],
            'content': result['content'],
            'word_count': result['word_count']
        })
        files_summary[file_name]['total_words'] += result['word_count']
        files_summary[file_name]['page_count'] += 1
    
    return {
        "files_processed": len(files_summary),
        "total_pages": len(ocr_results),
        "total_words": sum([r['word_count'] for r in ocr_results]),
        "files_summary": list(files_summary.values())
    }

# === MERGED ENDPOINT 1 LOGIC ===
async def get_rfp_uploads_files():
    """Get complete nested folder structure from RFP-Uploads"""
    try:
        start_time = datetime.now()
        logger.info("Fetching complete folder structure from RFP-Uploads")
        
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
        
        # Get complete folder structure with nested folders and files
        structure = service.get_folder_structure(rfp_folder['drive_id'], 'RFP-Uploads', max_depth=3)
        
        # Flatten all files for easy access
        all_files = []
        
        def collect_files(folders_list, files_list):
            all_files.extend(files_list)
            for folder in folders_list:
                if 'files' in folder:
                    all_files.extend(folder['files'])
                if 'subfolders' in folder:
                    collect_files(folder['subfolders'], folder.get('files', []))
        
        collect_files(structure['folders'], structure['files'])
        
        processing_time = str(datetime.now() - start_time)
        
        return {
            "folder_name": "RFP-Uploads",
            "folder_info": rfp_folder,
            "folder_structure": structure,
            "all_files_flattened": all_files,
            "total_nested_folders": len(structure['folders']),
            "total_files": len(all_files),
            "processing_time": processing_time,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching RFP-Uploads structure: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching structure: {str(e)}")

# === FIXED MERGED ENDPOINT 2 LOGIC ===
async def process_folder_with_ocr(folder_name: str, background_tasks: BackgroundTasks = None):
    """FIXED: Process folder with recursive file search for nested structure"""
    try:
        start_time = datetime.now()
        logger.info(f"Processing folder '{folder_name}' with OCR (recursive search)")
        
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
        
        # Determine the search path
        if folder_name == 'RFP-Uploads':
            # Process all files in RFP-Uploads recursively
            search_path = 'RFP-Uploads'
            processing_path = "RFP-Uploads (All Files Recursively)"
        else:
            # Process specific subfolder recursively
            subfolder_name = folder_name.replace('RFP-Uploads/', '').replace('RFP-Uploads%2F', '')
            search_path = f"RFP-Uploads/{subfolder_name}"
            processing_path = f"RFP-Uploads/{subfolder_name} (Recursive)"
        
        logger.info(f"Searching recursively in path: {search_path}")
        
        # Get all files recursively from the specified path
        all_files = service.get_all_files_recursively(rfp_folder['drive_id'], search_path, max_depth=3)
        
        if not all_files:
            return {
                "folder_name": folder_name,
                "processing_path": processing_path,
                "search_path": search_path,
                "folder_info": rfp_folder,
                "message": "No files found in the specified path (searched recursively)",
                "total_files": 0,
                "ocr_results": None,
                "timestamp": datetime.now().isoformat()
            }
        
        # Filter PDF files for OCR processing
        pdf_files = [
            f for f in all_files 
            if f['mime_type'] == 'application/pdf' or f['file_name'].lower().endswith('.pdf')
        ]
        
        if not pdf_files:
            return {
                "folder_name": folder_name,
                "processing_path": processing_path,
                "search_path": search_path,
                "folder_info": rfp_folder,
                "message": "No PDF files found for OCR processing (searched recursively)",
                "total_files": len(all_files),
                "pdf_files": 0,
                "all_files": all_files,
                "timestamp": datetime.now().isoformat()
            }
        
        # Process PDF files with OCR
        all_ocr_results = []
        processed_files = 0
        failed_files = []
        
        for pdf_file in pdf_files:
            try:
                if not pdf_file.get('download_url'):
                    failed_files.append({
                        "file_name": pdf_file['file_name'], 
                        "reason": "No download URL available",
                        "file_path": pdf_file.get('file_path', 'unknown')
                    })
                    continue
                
                logger.info(f"Processing file: {pdf_file['file_name']} from path: {pdf_file.get('file_path', 'unknown')}")
                file_content = service.download_file(pdf_file['download_url'])
                
                if not file_content:
                    failed_files.append({
                        "file_name": pdf_file['file_name'], 
                        "reason": "Failed to download file",
                        "file_path": pdf_file.get('file_path', 'unknown')
                    })
                    continue
                
                file_type = determine_file_type(pdf_file)
                
                ocr_results = service.process_file_with_ocr(
                    file_content, 
                    pdf_file['file_name'], 
                    file_type
                )
                
                if ocr_results:
                    # Add path info to OCR results
                    for result in ocr_results:
                        result['file_path'] = pdf_file.get('file_path', pdf_file['file_name'])
                        result['folder_path'] = pdf_file.get('folder_path', 'unknown')
                    
                    all_ocr_results.extend(ocr_results)
                    processed_files += 1
                    logger.info(f"Successfully processed {pdf_file['file_name']} - {len(ocr_results)} pages")
                else:
                    failed_files.append({
                        "file_name": pdf_file['file_name'], 
                        "reason": "OCR processing failed",
                        "file_path": pdf_file.get('file_path', 'unknown')
                    })
                    
            except Exception as e:
                logger.error(f"Error processing file {pdf_file['file_name']}: {str(e)}")
                failed_files.append({
                    "file_name": pdf_file['file_name'], 
                    "reason": str(e),
                    "file_path": pdf_file.get('file_path', 'unknown')
                })
        
        # Generate summary
        summary = generate_files_summary(all_ocr_results)
        processing_time = str(datetime.now() - start_time)
        
        return {
            "folder_name": folder_name,
            "processing_path": processing_path,
            "search_path": search_path,
            "folder_info": rfp_folder,
            "total_files": len(all_files),
            "pdf_files_found": len(pdf_files),
            "processed_files": processed_files,
            "failed_files": failed_files,
            "ocr_results": {
                "total_pages": summary["total_pages"],
                "total_words": summary["total_words"],
                "files_summary": summary["files_summary"]
            },
            "processing_time": processing_time,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing folder '{folder_name}' with OCR: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing folder: {str(e)}")

# NEW: Get files from a specific nested path
async def get_specific_subfolder_files(subfolder_name: str):
    """Get files from a specific nested path within RFP-Uploads"""
    try:
        start_time = datetime.now()
        logger.info(f"Fetching files from RFP-Uploads/{subfolder_name} (recursive)")
        
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
        
        # Get folder structure for the specific subfolder
        search_path = f"RFP-Uploads/{subfolder_name}"
        structure = service.get_folder_structure(rfp_folder['drive_id'], search_path, max_depth=2)
        
        # Get all files recursively
        all_files = service.get_all_files_recursively(rfp_folder['drive_id'], search_path, max_depth=2)
        
        processing_time = str(datetime.now() - start_time)
        
        return {
            "parent_folder": "RFP-Uploads",
            "subfolder_name": subfolder_name,
            "search_path": search_path,
            "folder_structure": structure,
            "all_files": all_files,
            "total_files": len(all_files),
            "processing_time": processing_time,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching files from nested path: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching nested path: {str(e)}")
