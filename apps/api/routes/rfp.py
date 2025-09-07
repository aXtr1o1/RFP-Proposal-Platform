from fastapi import APIRouter, UploadFile, File
from typing import List

router = APIRouter(prefix="/rfp", tags=["rfp"])

@router.post("/ingest")
async def ingest(files: List[UploadFile]):
    # TODO: store files, create job in DB, enqueue OCR
    return {"status": "queued", "files": [f.filename for f in files]}
