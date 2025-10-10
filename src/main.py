from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.routes.api import router as api_router

app = FastAPI()
app.add_middleware(
    CORSMiddleware, 
    allow_origins=["*"], 
    allow_methods=["*"], 
    allow_headers=["*"])

app.include_router(api_router)

@app.get("/health")
def health(): return {"ok": True}
