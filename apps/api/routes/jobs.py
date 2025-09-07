from fastapi import APIRouter

router = APIRouter(prefix="/jobs", tags=["jobs"])

@router.get("/{job_id}")
def get_job(job_id: str):
    # TODO: fetch job status from DB
    return {"job_id": job_id, "status": "QUEUED"}

@router.get("/wordgen/next")
def next_word_job():
    # TODO: return next approved job for Word agent
    return {"job_id": None}
