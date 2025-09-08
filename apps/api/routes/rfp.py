from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import List
from pydantic import BaseModel
import os
import requests

router = APIRouter(prefix="/rfp", tags=["rfp"])
@router.post("/ingest")
async def ingest(files: List[UploadFile]):
    # TODO: store files, create job in DB, enqueue OCR
    return {"status": "queued", "files": [f.filename for f in files]}


class OCRRequest(BaseModel):
    uuid: str


GRAPH_BASE = "https://graph.microsoft.com/v1.0"
VISION_ENDPOINT = os.getenv("AZURE_VISION_ENDPOINT", "").rstrip("/")
VISION_KEY = os.getenv("AZURE_VISION_KEY")
ONEDRIVE_CLIENT_ID = os.getenv("ONEDRIVE_CLIENT_ID")
ONEDRIVE_CLIENT_SECRET = os.getenv("ONEDRIVE_CLIENT_SECRET")
ONEDRIVE_TENANT_ID = os.getenv("ONEDRIVE_TENANT_ID")

def get_graph_access_token():
    if not all([ONEDRIVE_CLIENT_ID, ONEDRIVE_CLIENT_SECRET, ONEDRIVE_TENANT_ID]):
        raise HTTPException(status_code=500, detail="OneDrive credentials not configured in .env")
    
    url = f"https://login.microsoftonline.com/{ONEDRIVE_TENANT_ID}/oauth2/v2.0/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": ONEDRIVE_CLIENT_ID,
        "client_secret": ONEDRIVE_CLIENT_SECRET,
        "scope": "https://graph.microsoft.com/.default"
    }
    
    try:
        response = requests.post(url, data=data)
        response.raise_for_status()
        return response.json()["access_token"]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get Graph token: {str(e)}")

def _graph_request(url, stream=False):
    token = get_graph_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers, stream=stream)
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=f"Graph API error: {response.text}")
    return response

def find_uuid_folder(uuid: str):
    try:
        response = _graph_request(f"{GRAPH_BASE}/me/drive/root:/{uuid}")
        if response.status_code == 200:
            return response.json()
    except:
        pass

    response = _graph_request(f"{GRAPH_BASE}/me/drive/root/search(q='{uuid}')")
    results = response.json().get("value", [])
    for item in results:
        if item.get("name") == uuid and "folder" in item:
            return item
    raise HTTPException(status_code=404, detail=f"UUID folder '{uuid}' not found in OneDrive")

def get_folder_children(folder_id: str):
    response = _graph_request(f"{GRAPH_BASE}/me/drive/items/{folder_id}/children")
    return response.json().get("value", [])

def download_file_content(item_id: str):
    response = _graph_request(f"{GRAPH_BASE}/me/drive/items/{item_id}/content", stream=True)
    return response.content

def send_to_vision_ocr(file_bytes: bytes):
    if not (VISION_ENDPOINT and VISION_KEY):
        raise HTTPException(status_code=500, detail="Azure Vision OCR not configured in .env")
    
    url = f"{VISION_ENDPOINT}/vision/v3.2/read/analyze"
    headers = {
        "Ocp-Apim-Subscription-Key": VISION_KEY,
        "Content-Type": "application/octet-stream"
    }
    
    response = requests.post(url, headers=headers, data=file_bytes)
    if response.status_code >= 300:
        raise HTTPException(status_code=response.status_code, detail=f"Vision OCR failed: {response.text}")
    
    operation_location = response.headers.get("Operation-Location")
    if not operation_location:
        raise HTTPException(status_code=502, detail="No Operation-Location header from Vision")
    
    return operation_location

@router.post("/ocr")
async def ocr_uuid_folder(request: OCRRequest):
    """
    Find OneDrive folder by UUID, get supporting_files and RFP subfolders,
    download all files and send to Azure Vision OCR.
    
    Exactly as requested by team lead:
    - Get UUID from request body
    - Search OneDrive for folder matching UUID
    - Get supporting_files and RFP subfolders
    - Push files to Azure Vision OCR
    """
    try:
        base_folder = find_uuid_folder(request.uuid)
        print(f"Found UUID folder: {base_folder['name']}")
        children = get_folder_children(base_folder["id"])
        supporting_files_folder = None
        rfp_folder = None
        
        for child in children:
            if child.get("name") == "supporting_files" and "folder" in child:
                supporting_files_folder = child
            elif child.get("name") == "RFP" and "folder" in child:
                rfp_folder = child
        
        if not supporting_files_folder:
            raise HTTPException(status_code=404, detail="supporting_files subfolder not found")
        if not rfp_folder:
            raise HTTPException(status_code=404, detail="RFP subfolder not found")
        supporting_files = [f for f in get_folder_children(supporting_files_folder["id"]) if "file" in f]
        rfp_files = [f for f in get_folder_children(rfp_folder["id"]) if "file" in f]
        
        print(f"Found {len(supporting_files)} supporting files, {len(rfp_files)} RFP files")
        def process_files(files, folder_type):
            results = []
            for file_item in files:
                print(f"Processing {folder_type} file: {file_item['name']}")
                file_bytes = download_file_content(file_item["id"])
                operation_location = send_to_vision_ocr(file_bytes)
                results.append({
                    "name": file_item["name"],
                    "itemId": file_item["id"],
                    "operationLocation": operation_location
                })
            return results
        
        supporting_results = process_files(supporting_files, "supporting_files")
        rfp_results = process_files(rfp_files, "RFP")
        
        return {
            "uuid": request.uuid,
            "supporting_files": supporting_results,
            "rfp": rfp_results,
            "message": f"Successfully processed {len(supporting_results)} supporting files and {len(rfp_results)} RFP files"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
