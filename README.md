# RFP Proposal Platform

Upload RFPs and supporting documents → AI‑generate a proposal → review, iterate with comments → export to Word and PowerPoint.

This repo contains everything needed for that flow:

- **Next.js frontend** with a single `UploadPage` that drives the entire workflow
- **FastAPI backend** that orchestrates OpenAI, Supabase, Word generation, and PPT generation
- **Local PPT template engine** with themed slide templates (e.g. `standard`, `arweqah`)
- **Word generator** that rebuilds `.docx` from saved markdown

---

## Architecture

- **Frontend – `apps/frontend`**
  - Next.js 15 (App Router) + React 19 + Tailwind CSS 4.
  - Main UI in `app/components/UploadPage.tsx`:
    - Uploads RFP and supporting files.
    - Streams proposal content from the backend over **Server‑Sent Events**.
    - Persists proposal history and comments in **Supabase**.
    - Triggers **Word** and **PowerPoint** generation and exposes download links.
  - Uses `app/nextapi/*` routes for:
    - Uploading files to Supabase Storage (`/nextapi/upload`).
    - Health checks (`/nextapi/check-supabase`, `/nextapi/check-onedrive`).
    - Conversions and comments (`/nextapi/convert`, `/nextapi/supabase-comments`).

- **API – `apps/main.py` + `apps/routes/rfp.py`**
  - Python 3.11 **FastAPI** app mounted at `/api`.
  - Core endpoints (all prefixed with `/api`):
    - `POST /initialgen/{uuid}` – stream proposal markdown from OpenAI (SSE).
    - `POST /regenerate` – regenerate proposal markdown with structured comments.
    - `POST /download/{uuid}` – rebuild `.docx` from the latest (or requested) markdown.
    - `POST /ppt-initialgen` – generate the first PPTX for a proposal from local templates.
    - `POST /ppt-regeneration` – regenerate PPTX using feedback comments.
    - `GET  /download` – return a Supabase URL for a generated PPTX.
    - `GET  /templates` – list locally available PPT templates.
  - Uses **Supabase** as source of truth for:
    - Uploaded RFP and supporting file URLs.
    - Proposal generations (`word_gen` table).
    - PPT generations (`ppt_gen` table).

- **PPT generator – `apps/app`**
  - PPT engine with:
    - Local JSON‑driven templates in `app/templates/*` (e.g. `standard`, `arweqah`).
    - Rich layout metadata for sections, charts, tables, images, and RTL/Arabic support.
  - Uses `OPENAI_API_KEY` + `OPENAI_MODEL` for slide content and **DALL‑E** for images.
  - Uploads generated PPTX files to Supabase (`proposal-ppts` bucket by default).

- **Word generator – `apps/wordgenAgent`**
  - Uses the OpenAI Responses API to generate a **markdown proposal** from RFP/supporting PDFs.
  - Streams chunks back to the API (and then the frontend) as SSE.
  - Persists markdown to Supabase and calls `generate_word_from_markdown` to build `.docx`.
  - Intended to run on a Windows environment with Microsoft Word installed for best fidelity.

- **Supabase integration – `apps/api/services/supabase_service.py` & frontend `app/supabase/*`**
  - Backend service for reading/writing Supabase tables and buckets.
  - Frontend clients for:
    - Public usage with anon key (`client.ts`).
    - Admin/server‑side usage with service role key (`admin.ts`).

- **Docker / infra**
  - `docker-compose.dev.yml` spins up:
    - `postgres` (RFP application DB).
    - `redis` (for future workers/queueing).
    - `api` (Python 3.11 container, FastAPI app – see notes below).
    - `frontend` (Next.js dev server).
  - `.github/workflows/deploy.yml` uses GitHub Actions to deploy to an Azure VM over SSH and restart PM2 processes.

> **Note**: The original OCR worker (`apps/workers/ocr`) is still referenced by `docker-compose.dev.yml` but is currently stubbed/not present in this repo.

---

## Data & Processing Flow

1. **Upload**
   - User drops RFP + supporting files on the Upload page.
   - Next.js `upload` route uploads them into Supabase Storage buckets (e.g. `rfp`, `supporting`) and records URLs in a Supabase table (`Data_Table`) under a generated `uuid`.

2. **Initial proposal generation**
   - UI calls `POST /api/initialgen/{uuid}` with user preferences and document configuration.
   - Backend looks up the latest Supabase row for that `uuid` and fetches RFP/supporting file URLs.
   - `WordGenAPI` uploads PDFs to OpenAI, streams markdown via SSE, and saves the full markdown into `word_gen` for that `uuid`/`gen_id`.
   - Backend triggers Word generation so a `.docx` is ready to download.

3. **Download Word**
   - UI calls `POST /api/download/{uuid}`.
   - Backend reloads the latest markdown and uses `generate_word_from_markdown` to (re)create the Word document if needed.
   - Response returns a Supabase URL (`proposal_word_url`) that the UI exposes as a download link.

4. **Regeneration with comments**
   - User leaves structured comments on the proposal.
   - UI calls `POST /api/regenerate` with `uuid`, base `gen_id`, and comment payload.
   - Backend writes a new row in `word_gen` with a new `gen_id`, runs the regeneration prompt against the previous markdown, saves updated markdown, and returns the new Word link + content.

5. **PPT generation & regeneration**
   - UI calls `POST /api/ppt-initialgen` with `uuid`, `gen_id`, language (English/Arabic), and selected template id.
   - Backend checks that template exists in `apps/app/templates/*`, generates PPT content, applies the template, and uploads PPTX to Supabase.
   - For feedback‑based changes, UI calls `POST /api/ppt-regeneration` with comments; backend regenerates PPTX and stores a new `ppt_genid` and URL.

---

## Environment Variables (overview)

### Shared / backend

These are loaded from `.env` by the Python services:

- **OpenAI**
  - `OPENAI_API_KEY` – secret key used by Word generator and PPT engine.
  - `OPENAI_MODEL` – model name for proposal and slide content.
  - `DALL_E_MODEL`, `DALL_E_SIZE`, `DALL_E_QUALITY`, `DALL_E_STYLE` – DALL‑E configuration (optional, see `apps/app/config.py`).

- **Supabase**
  - `SUPABASE_URL`
  - `SUPABASE_KEY` – backend service key.
  - `SUPABASE_BUCKET` – PPT bucket name (defaults to `proposal-ppts`).
  - Optional tuning:
    - `SUPABASE_WORD_GEN_TABLE` (default `word_gen`)
    - `SUPABASE_PPT_GEN_TABLE` (default `ppt_gen`)
    - `SUPABASE_WORD_BUCKET` (default `word`)

- **FastAPI / general**
  - `LOG_LEVEL` – e.g. `INFO`, `DEBUG`.

### Frontend (`apps/frontend`)

These are read at build/runtime by Next.js:

- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY` (server‑side only, used in `supabaseAdmin`).
- **Backend URL configuration** (used in `UploadPage.tsx`):
  - `NEXT_PUBLIC_API_HOST` – hostname for the FastAPI service (used to build `http://HOST:8000/api` by default), or
  - `NEXT_PUBLIC_API_BASE_URL` – full base URL for the API; if set, the frontend appends `/api` as needed.

There is usually a `.env.example` at the repo root; copy and customize it as needed:

```bash
cp .env.example .env
# edit .env with your keys/secrets
```

> **Never commit real secrets** – keep `.env` out of version control.

---

## Local Development

### Option 1 – Docker Compose (all services)

Prerequisites: Docker, Docker Compose, `.env` with the required variables.

```bash
cp .env.example .env   # fill in all required keys
docker compose -f docker-compose.dev.yml up --build
```

- Frontend: `http://localhost:3000`
- API (FastAPI): `http://localhost:8000/api` (FastAPI docs at `/api/docs` when running directly)

> The OCR worker referenced in `docker-compose.dev.yml` is currently stubbed and may not run; it is not required for the proposal flow described above.

### Option 2 – Run backend & frontend directly

**Backend (FastAPI):**

```bash
python -m venv .venv
.\.venv\Scripts\activate  # Windows
pip install -r apps/requirements.txt

uvicorn apps.main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend (Next.js):**

```bash
cd apps/frontend
npm install
npm run dev
```

Then open `http://localhost:3000` and ensure `NEXT_PUBLIC_API_HOST` or `NEXT_PUBLIC_API_BASE_URL` points at your running FastAPI instance.

---

## Deployment

CI/CD is handled via GitHub Actions (`.github/workflows/deploy.yml`):

- On push to `master`, GitHub Actions:
  - SSHes into an Azure VM.
  - Pulls the latest code into `/home/azureuser/RFP-Proposal-Platform`.
  - Installs backend dependencies (`apps/requirements.txt`).
  - Installs and builds the frontend (`apps/frontend`).
  - Restarts PM2 processes defined in `ecosystem.config.js` (backend + frontend).

The Word/PPT generation pieces assume:

- A Python 3.11 environment with the same dependencies as in `apps/requirements.txt`.
- Access to OpenAI and Supabase using the configured keys.
- For full Word fidelity, a Windows host with Microsoft Word installed for the Word agent.

---

## Where to Look Next

- **Frontend UX:** `apps/frontend/app/components/UploadPage.tsx`
- **API entrypoint:** `apps/main.py`
- **Proposal & PPT endpoints:** `apps/routes/rfp.py`
- **PPT engine & templates:** `apps/app/*`
- **Word generation & prompts:** `apps/wordgenAgent/app/*`
- **Supabase integration:** `apps/api/services/supabase_service.py`, `apps/frontend/app/supabase/*`
