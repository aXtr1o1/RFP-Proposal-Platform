from typing import List, Dict, Any, Tuple
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

# Environment variables validation
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

# Import Milvus client
try:
    sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'vdb'))
    from milvus_client import get_milvus_client
    logger.info("Milvus client imported successfully")
except ImportError as e:
    logger.warning(f"Milvus client not found: {e}")
    get_milvus_client = None

# Import OCR Worker
try:
    workers_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'workers', 'ocr')
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
        """Authenticate with Microsoft Graph API"""
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
        """Make authenticated request to Microsoft Graph API"""
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
        """Get all available drives"""
        drives = []
        
        # Get shared drives
        result = self._make_request("/drives")
        if result:
            for drive in result.get("value", []):
                drives.append({
                    'id': drive['id'],
                    'name': drive['name'],
                    'type': drive.get('driveType', 'shared')
                })

        # Get user drives (limited to first 5)
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
        """Get folders in all drives"""
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
        """Recursively get all files in a folder"""
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
        """Get folder structure with nested folders and files"""
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
        """Download file from OneDrive"""
        try:
            response = requests.get(download_url)
            response.raise_for_status()
            return response.content
        except Exception as e:
            logger.error(f"Error downloading file: {e}")
            return None
    
    def determine_folder_type(self, file_info: Dict) -> str:
        """Determine collection name based on folder type"""
        folder_path = file_info.get('folder_path', '').lower()
        file_name = file_info.get('file_name', '').lower()
        
        # Check for supportive files indicators
        if ('supportive' in folder_path or 'support' in folder_path or 
            'supportive' in file_name or 'support' in file_name):
            return 'supportive_files'
        # Check for RFP files indicators
        elif ('rfp' in folder_path or 'rfp' in file_name):
            return 'rfp_files'
        else:
            # Default to RFP files
            return 'rfp_files'

    def process_file_with_enhanced_ocr(self, file_content: bytes, file_info: Dict) -> Tuple[List[Dict], List[Dict]]:
        """Process file with appropriate OCR based on folder type"""
        folder_type = self.determine_folder_type(file_info)
        file_name = file_info['file_name']
        
        if folder_type == 'supportive_files':
            # Use enhanced OCR for supportive files (text + images)
            try:
                sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'workers', 'ocr'))
                from image_ocr_service import get_image_ocr_service
                image_ocr_service = get_image_ocr_service()
                return image_ocr_service.extract_text_and_images_from_pdf(file_content, file_name)
            except ImportError:
                logger.warning("Image OCR service not available, using fallback OCR")
                text_results = self._process_with_fallback_ocr(file_content, file_name, "supportive")
                return text_results, []
        else:
            # Use text-only OCR for RFP files
            text_results = self._process_with_fallback_ocr(file_content, file_name, "RFP")
            return text_results, []
    
    def process_file_with_ocr(self, file_content, file_name, file_type="document"):
        """Process file with OCR using available worker"""
        if self.ocr_worker:
            return self.ocr_worker.process_file(file_content, file_name, file_type)
        else:
            return self._process_with_fallback_ocr(file_content, file_name, file_type)
    
    def _process_with_fallback_ocr(self, file_content, file_name, file_type="document"):
        """Fallback OCR processing using Azure Document Intelligence"""
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
    """Get or create OneDrive service instance"""
    global onedrive_service
    if onedrive_service is None:
        onedrive_service = OneDriveService()
    return onedrive_service

def determine_file_type(file_info: Dict) -> str:
    """Legacy function for backward compatibility"""
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

def save_to_milvus_by_collection(ocr_results: List[Dict], image_metadata: List[Dict], collection_name: str, folder_name: str) -> Dict:
    """Save data to specific Milvus collection"""
    try:
        if not get_milvus_client:
            return {"vector_stored": False, "reason": "Milvus client not available"}
        
        # Get collection-specific client
        milvus_client = get_milvus_client(collection_name)
        
        if milvus_client.is_available():
            # Save documents with images if available and supported
            if hasattr(milvus_client, 'save_documents_with_images') and image_metadata:
                vector_ids = milvus_client.save_documents_with_images(ocr_results, folder_name, image_metadata)
            else:
                vector_ids = milvus_client.save_documents(ocr_results, folder_name)
            
            return {
                "vector_stored": True,
                "collection_name": collection_name,
                "documents_stored": len(vector_ids),
                "images_metadata_stored": len(image_metadata),
                "vector_ids_sample": vector_ids[:3],  # Show first 3 IDs
                "embedding_model": "MiniLM-L6-v2"
            }
        else:
            return {"vector_stored": False, "reason": "Milvus client not available"}
            
    except Exception as e:
        logger.error(f"Vector storage error for collection {collection_name}: {e}")
        return {"vector_stored": False, "collection_name": collection_name, "error": str(e)}

def get_milvus_data_by_collections() -> Dict:
    """Get data from both RFP and supportive collections"""
    try:
        if not get_milvus_client:
            return {"error": "Milvus client not available"}
        
        collections_data = {}
        
        # Get data from RFP files collection
        try:
            rfp_client = get_milvus_client("rfp_files")
            rfp_documents = rfp_client.get_all_documents(limit=50)
            rfp_stats = rfp_client.get_stats()
            
            collections_data['rfp_files'] = {
                "documents": rfp_documents,
                "stats": rfp_stats,
                "document_count": len(rfp_documents)
            }
        except Exception as e:
            logger.warning(f"Error getting RFP files data: {e}")
            collections_data['rfp_files'] = {"error": str(e), "document_count": 0}
        
        # Get data from supportive files collection
        try:
            supportive_client = get_milvus_client("supportive_files")
            supportive_documents = supportive_client.get_all_documents(limit=50)
            
            # Get image metadata if method exists
            images = []
            if hasattr(supportive_client, 'get_images_metadata'):
                images = supportive_client.get_images_metadata(limit=50)
            
            supportive_stats = supportive_client.get_stats()
            
            collections_data['supportive_files'] = {
                "documents": supportive_documents,
                "images": images,
                "stats": supportive_stats,
                "document_count": len(supportive_documents),
                "image_count": len(images)
            }
        except Exception as e:
            logger.warning(f"Error getting supportive files data: {e}")
            collections_data['supportive_files'] = {"error": str(e), "document_count": 0, "image_count": 0}
        
        return {
            "collections": collections_data,
            "total_rfp_documents": collections_data.get('rfp_files', {}).get('document_count', 0),
            "total_supportive_documents": collections_data.get('supportive_files', {}).get('document_count', 0),
            "total_images": collections_data.get('supportive_files', {}).get('image_count', 0),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting collections data: {e}")
        return {"error": str(e)}

def search_across_collections(query: str, limit: int = 10) -> Dict:
    """Search across both RFP and supportive collections"""
    try:
        if not get_milvus_client:
            return {"error": "Milvus client not available"}
        
        search_results = {}
        
        # Search RFP files collection
        try:
            rfp_client = get_milvus_client("rfp_files")
            rfp_results = rfp_client.search_similar_documents(query, limit)
            search_results['rfp_files'] = {
                "results": rfp_results,
                "count": len(rfp_results),
                "collection_type": "RFP Files (Text Only)"
            }
        except Exception as e:
            logger.warning(f"Error searching RFP files: {e}")
            search_results['rfp_files'] = {"error": str(e), "count": 0}
        
        # Search supportive files collection
        try:
            supportive_client = get_milvus_client("supportive_files")
            supportive_results = supportive_client.search_similar_documents(query, limit)
            search_results['supportive_files'] = {
                "results": supportive_results,
                "count": len(supportive_results),
                "collection_type": "Supportive Files (Text + Images)"
            }
        except Exception as e:
            logger.warning(f"Error searching supportive files: {e}")
            search_results['supportive_files'] = {"error": str(e), "count": 0}
        
        return {
            "search_query": query,
            "collections": search_results,
            "total_rfp_results": search_results.get('rfp_files', {}).get('count', 0),
            "total_supportive_results": search_results.get('supportive_files', {}).get('count', 0),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error searching collections: {e}")
        return {"error": str(e)}
