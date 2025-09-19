from typing import List, Dict, Any, Tuple,Optional
import msal
import requests
from datetime import datetime
import os
import logging
from dotenv import load_dotenv
import urllib.parse
import sys
import pathlib
import json

load_dotenv()

logger = logging.getLogger(__name__)

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
    from apps.vdb.milvus_client import get_milvus_client
    logger.info("Milvus client imported successfully")
except ImportError as e:
    logger.warning(f"Milvus client not found: {e}")
    get_milvus_client = None

# Import OCR Worker 
try:
    workers_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'workers', 'ocr')
    sys.path.append(workers_path)
    from apps.workers.ocr.worker import get_ocr_worker
    logger.info("OCR Worker imported successfully")
except ImportError as e:
    logger.warning(f"OCR Worker not found: {e}")
    get_ocr_worker = None

try:
    from apps.workers.ocr.text_ocr_service import get_text_ocr_service
    logger.info("Text OCR Service imported successfully")
except ImportError as e:
    logger.warning(f"Text OCR Service not found: {e}")
    get_text_ocr_service = None

class OneDriveService:
    def __init__(self):
        self.tenant_id = TENANT_ID
        self.client_id = CLIENT_ID
        self.client_secret = CLIENT_SECRET
        self.access_token = None
        self.base_url = "https://graph.microsoft.com/v1.0"
        if get_ocr_worker:
            try:
                self.ocr_worker = get_ocr_worker()
            except Exception as e:
                logger.warning(f"OCR Worker initialization failed: {e}")
                self.ocr_worker = None
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
    def _auth_headers(self, extra=None):
        h = {"Authorization": f"Bearer {self.access_token}"}
        if extra: h.update(extra)
        return h

    def ensure_folder_path(self, drive_id: str, path: str) -> Dict:
        """
        Ensure 'path' exists under the given drive. Creates it if missing.
        Returns the folder item JSON.
        """
        # Try to GET the folder
        url = f"{self.base_url}/drives/{drive_id}/root:/{urllib.parse.quote(path)}"
        r = requests.get(url, headers=self._auth_headers())
        if r.status_code == 200:
            return r.json()
        if r.status_code != 404:
            r.raise_for_status()

        # Create the chain of subfolders step by step
        segments = [p for p in pathlib.PurePosixPath(path).parts if p not in ("/", "")]
        parent_url = f"{self.base_url}/drives/{drive_id}/root/children"
        parent_path = ""
        for seg in segments:
            parent_path = f"{parent_path}/{seg}" if parent_path else seg
            get_url = f"{self.base_url}/drives/{drive_id}/root:/{urllib.parse.quote(parent_path)}"
            g = requests.get(get_url, headers=self._auth_headers())
            if g.status_code == 200:
                continue
            if g.status_code != 404:
                g.raise_for_status()
            # create this segment
            payload = {"name": seg, "folder": {}, "@microsoft.graph.conflictBehavior": "fail"}
            c = requests.post(
                f"{self.base_url}/drives/{drive_id}/root:/{urllib.parse.quote(parent_path.rsplit('/',1)[0]) or ''}:/children",
                headers=self._auth_headers({"Content-Type":"application/json"}),
                data=json.dumps(payload)
            )
            if c.status_code not in (200, 201):
                c.raise_for_status()
        # Return final folder
        rf = requests.get(url, headers=self._auth_headers())
        rf.raise_for_status()
        return rf.json()

    def upload_small_file(self, drive_id: str, dest_path: str, local_file_path: str) -> Dict:
        """
        PUT /content for files up to ~4MB (docx usually OK). Overwrites if exists.
        dest_path like: 'RFP-Uploads/{folder_name}/{filename}.docx'
        """
        up_url = f"{self.base_url}/drives/{drive_id}/root:/{urllib.parse.quote(dest_path)}:/content"
        with open(local_file_path, "rb") as f:
            r = requests.put(up_url, headers=self._auth_headers(), data=f)
        r.raise_for_status()
        return r.json()

    def create_share_link(self, drive_id: str, item_id: str, scope: str = "anonymous", link_type: str = "view") -> Optional[str]:
        """
        Returns a shareable URL (view-only by default). Requires Files.ReadWrite.All (App) permissions.
        """
        url = f"{self.base_url}/drives/{drive_id}/items/{item_id}/createLink"
        payload = {"type": link_type, "scope": scope}
        r = requests.post(url, headers=self._auth_headers({"Content-Type":"application/json"}), data=json.dumps(payload))
        if r.status_code in (200, 201):
            data = r.json()
            return data.get("link", {}).get("webUrl")
        # If createLink is disabled by policy, just return None (frontend can use webUrl)
        return None
    
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
        if ('supportive' in folder_path or 'support' in folder_path or 
            'supportive' in file_name or 'support' in file_name):
            return 'supportive_files'
        elif ('rfp' in folder_path or 'rfp' in file_name):
            return 'rfp_files'
        else:
            return 'rfp_files'

    def process_file_with_text_ocr(self, file_content: bytes, file_info: Dict) -> List[Dict]:
        """Process file with text-only OCR based on folder type"""
        folder_type = self.determine_folder_type(file_info)
        file_name = file_info['file_name']
        
        if get_text_ocr_service:
            try:
                text_ocr_service = get_text_ocr_service()
                return text_ocr_service.extract_text_from_pdf(file_content, file_name, folder_type)
            except Exception as e:
                logger.warning(f"Text OCR service failed, using basic OCR: {e}")
        
        if self.ocr_worker:
            return self.ocr_worker.process_file(file_content, file_name, folder_type)
        else:
            logger.error("No OCR service available")
            return []
    
    def process_text_file(self, file_content: bytes, file_info: Dict) -> List[Dict]:
        """Process text files without OCR - extract text content directly"""
        try:
            text_content = file_content.decode('utf-8')
            file_name = file_info['file_name']
            file_type = self.determine_folder_type(file_info)
            max_chunk_size = 2000  # characters
            chunks = []
            
            if len(text_content) <= max_chunk_size:
                chunks = [text_content]
            else:
                words = text_content.split()
                current_chunk = []
                current_length = 0
                
                for word in words:
                    if current_length + len(word) > max_chunk_size and current_chunk:
                        chunks.append(' '.join(current_chunk))
                        current_chunk = [word]
                        current_length = len(word)
                    else:
                        current_chunk.append(word)
                        current_length += len(word) + 1
                
                if current_chunk:
                    chunks.append(' '.join(current_chunk))
            processed_data = []
            for i, chunk in enumerate(chunks):
                if chunk.strip():
                    processed_data.append({
                        "file_name": file_name,
                        "file_type": file_type,
                        "chunk": i + 1,
                        "content": chunk.strip(),
                        "word_count": len(chunk.split()),
                        "timestamp": datetime.now().isoformat()
                    })
            
            return processed_data
            
        except UnicodeDecodeError:
            logger.warning(f"Cannot process {file_info['file_name']} as text file - binary format")
            return []
        except Exception as e:
            logger.error(f"Error processing text file {file_info['file_name']}: {e}")
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

def save_to_milvus_by_collection(processed_data: List[Dict], collection_name: str, folder_name: str) -> Dict:
    """Save data to specific Milvus collection - text processing only"""
    try:
        if not get_milvus_client:
            return {"vector_stored": False, "reason": "Milvus client not available"}
        
        milvus_client = get_milvus_client(collection_name)
        
        if milvus_client.is_available():
            vector_ids = milvus_client.save_documents(processed_data, folder_name)
            
            return {
                "vector_stored": True,
                "collection_name": collection_name,
                "documents_stored": len(vector_ids),
                "vector_ids_sample": vector_ids[:3],  
                "embedding_model": "MiniLM-L6-v2",
                "processing_mode": "text_only"
            }
        else:
            return {"vector_stored": False, "reason": "Milvus client not available"}
            
    except Exception as e:
        logger.error(f"Vector storage error for collection {collection_name}: {e}")
        return {"vector_stored": False, "collection_name": collection_name, "error": str(e)}

def get_milvus_data_by_collections() -> Dict:
    """Get data from both RFP and supportive collections - text processing only"""
    try:
        if not get_milvus_client:
            return {"error": "Milvus client not available"}
        
        collections_data = {}
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
        try:
            supportive_client = get_milvus_client("supportive_files")
            supportive_documents = supportive_client.get_all_documents(limit=50)
            supportive_stats = supportive_client.get_stats()
            
            collections_data['supportive_files'] = {
                "documents": supportive_documents,
                "stats": supportive_stats,
                "document_count": len(supportive_documents)
            }
        except Exception as e:
            logger.warning(f"Error getting supportive files data: {e}")
            collections_data['supportive_files'] = {"error": str(e), "document_count": 0}
        
        return {
            "collections": collections_data,
            "total_rfp_documents": collections_data.get('rfp_files', {}).get('document_count', 0),
            "total_supportive_documents": collections_data.get('supportive_files', {}).get('document_count', 0),
            "processing_mode": "text_only",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting collections data: {e}")
        return {"error": str(e)}

def search_across_collections(query: str, limit: int = 10) -> Dict:
    """Search across both RFP and supportive collections - text processing only"""
    try:
        if not get_milvus_client:
            return {"error": "Milvus client not available"}
        
        search_results = {}
        try:
            rfp_client = get_milvus_client("rfp_files")
            rfp_results = rfp_client.search_similar_documents(query, limit)
            search_results['rfp_files'] = {
                "results": rfp_results,
                "count": len(rfp_results),
                "collection_type": "RFP Files (Text Processing)"
            }
        except Exception as e:
            logger.warning(f"Error searching RFP files: {e}")
            search_results['rfp_files'] = {"error": str(e), "count": 0}
        try:
            supportive_client = get_milvus_client("supportive_files")
            supportive_results = supportive_client.search_similar_documents(query, limit)
            search_results['supportive_files'] = {
                "results": supportive_results,
                "count": len(supportive_results),
                "collection_type": "Supportive Files (Text Processing)"
            }
        except Exception as e:
            logger.warning(f"Error searching supportive files: {e}")
            search_results['supportive_files'] = {"error": str(e), "count": 0}
        
        return {
            "search_query": query,
            "collections": search_results,
            "total_rfp_results": search_results.get('rfp_files', {}).get('count', 0),
            "total_supportive_results": search_results.get('supportive_files', {}).get('count', 0),
            "processing_mode": "text_only",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error searching collections: {e}")
        return {"error": str(e)}
