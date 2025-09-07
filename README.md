# RFP Proposal Platform (MVP Boilerplate)

Upload RFP → OCR → Summarize → Review → Word draft (.docx).

## Apps
- **apps/api**: FastAPI (Python 3.11)
- **apps/frontend**: Next.js 14 (App Router) + Tailwind
- **apps/wordgen-agent**: Windows Word COM agent (Python) – generates `.docx` from `.dotx`
- **apps/workers/ocr**: OCR worker (Azure Vision + Tesseract fallback, stubbed)

## Quick start (dev)
```bash
cp .env.example .env   # fill keys
docker compose -f docker-compose.dev.yml up --build
# FE: http://localhost:3000
# API: http://localhost:8000/healthz
```
## Deploy
- CI/CD via GitHub Actions → Azure Container Apps (API + FE)
- Self-hosted Windows runner for Word agent

See `.github/workflows/` for pipelines.
