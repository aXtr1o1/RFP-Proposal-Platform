# Architecture Overview

This document describes the architecture of the RFP Proposal Platform: system components, data flow, integrations, and key design decisions. It serves as a reference for developers and should be updated whenever the architecture changes.

---

## Table of Contents

1. [Project Structure](#1-project-structure)
2. [High-Level System Diagram](#2-high-level-system-diagram)
3. [Core Components](#3-core-components)
4. [Data Stores](#4-data-stores)
5. [External Integrations](#5-external-integrations)
6. [Data & Processing Flow](#6-data--processing-flow)
7. [Deployment & Infrastructure](#7-deployment--infrastructure)
8. [Security Considerations](#8-security-considerations)
9. [Development & Testing](#9-development--testing)
10. [Key Design Decisions](#10-key-design-decisions)
11. [Future Considerations](#11-future-considerations)
12. [Glossary](#12-glossary)

---

## 1. Project Structure

```
RFP-Proposal-Platform/
├── .github/
│   ├── CODEOWNERS
│   └── workflows/
│       ├── ci.yml          # Lint, format, repo standards checks
│       └── deploy.yml      # Deploy to Azure VM on push to master
├── apps/
│   ├── main.py             # FastAPI app entrypoint
│   ├── requirements.txt    # Python dependencies
│   ├── routes/
│   │   └── rfp.py          # Proposal & PPT API endpoints
│   ├── api/
│   │   └── services/
│   │       └── supabase_service.py  # Backend Supabase client
│   ├── app/                # PPT generator engine
│   │   ├── config.py
│   │   ├── core/           # ppt_generation, ppt_regeneration, supabase
│   │   ├── models/         # Pydantic models (presentation, template)
│   │   ├── services/       # chart, content_mapper, icon, image, openai, pptx_generator, table, template
│   │   ├── templates/      # standard, arweqah (JSON-driven slide themes)
│   │   └── utils/          # content_validator, markdown_parser, svg_converter, text_formatter
│   ├── frontend/           # Next.js 15 App Router app
│   │   ├── app/
│   │   │   ├── components/  # UploadPage, MarkdownRenderer, PdfAnnotator
│   │   │   ├── nextapi/    # upload, check-supabase, check-onedrive, convert, supabase-comments
│   │   │   ├── supabase/   # client.ts, admin.ts
│   │   │   └── page.tsx
│   │   └── public/         # Static assets
│   ├── regen_services/     # Regeneration prompt logic
│   └── wordgenAgent/       # Word proposal generator
│       └── app/
│           ├── api.py      # WordGenAPI (OpenAI integration)
│           ├── document.py # generate_word_from_markdown
│           └── ...
├── docker-compose.dev.yml  # postgres, redis, api, frontend (dev)
├── ruff.toml               # Python lint/format config
├── ARCHITECTURE.md         # This document
├── CONTRIBUTING.md
└── README.md
```

---

## 2. High-Level System Diagram

```
┌─────────────┐     ┌──────────────────────────────────────────────────────────┐
│   User      │     │                    Next.js Frontend                       │
│  (Browser)  │◄───►│  UploadPage.tsx  │  nextapi/* routes  │  Supabase client  │
└─────────────┘     └────────────┬──────────────────────────────┬──────────────┘
                                 │                              │
                                 │ HTTP / SSE                   │ Direct
                                 ▼                              ▼
┌────────────────────────────────────────────────────┐    ┌─────────────────┐
│              FastAPI Backend (apps/main.py)         │    │    Supabase     │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────┐ │    │  • Storage      │
│  │ rfp routes  │  │ Word generator│  │ PPT engine │ │    │  • word_gen     │
│  │ /initialgen │  │ wordgenAgent  │  │ apps/app   │ │    │  • ppt_gen      │
│  │ /regenerate │  │              │  │            │ │    │  • Data_Table   │
│  │ /download   │  └──────┬───────┘  └─────┬──────┘ │    └────────┬────────┘
│  │ /ppt-*      │         │                │        │             │
│  └──────┬──────┘         │                │        └──────┬──────┘
│         │                │                │               │
│         └────────────────┼────────────────┘               │
└──────────────────────────┼────────────────────────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   OpenAI    │  (Responses API, DALL-E)
                    └─────────────┘
```

**Data flow summary:** User uploads RFP + supporting files → stored in Supabase Storage → backend fetches URLs → OpenAI generates markdown (streamed via SSE) → markdown saved to `word_gen` → Word/PPT generated → outputs stored in Supabase → user downloads.

---

## 3. Core Components

### 3.1. Frontend

| Attribute | Details |
|-----------|---------|
| **Name** | RFP Proposal Web App |
| **Description** | Single-page workflow for uploading RFPs, streaming AI-generated proposals, reviewing with comments, and exporting to Word and PowerPoint. |
| **Technologies** | Next.js 15 (App Router), React 19, Tailwind CSS 4, TypeScript |
| **Key files** | `apps/frontend/app/components/UploadPage.tsx`, `app/nextapi/*` |
| **Deployment** | Served via PM2 on Azure VM (or Docker in dev) |

### 3.2. API (FastAPI)

| Attribute | Details |
|-----------|---------|
| **Name** | RFP Proposal API |
| **Description** | Orchestrates proposal generation, regeneration, Word/PPT creation, and Supabase reads/writes. Exposes REST + SSE endpoints. |
| **Technologies** | Python 3.11, FastAPI, Uvicorn |
| **Entrypoint** | `apps/main.py`, routes in `apps/routes/rfp.py` |
| **Deployment** | PM2 on Azure VM (port 8000) |

### 3.3. Word Generator

| Attribute | Details |
|-----------|---------|
| **Name** | Word Proposal Generator |
| **Description** | Uses OpenAI Responses API to generate markdown from RFP/supporting PDFs, streams via SSE, persists to Supabase, and builds `.docx` via `generate_word_from_markdown`. |
| **Technologies** | Python, OpenAI SDK, python-docx |
| **Location** | `apps/wordgenAgent/` |
| **Note** | Best Word fidelity on Windows with Microsoft Word installed |

### 3.4. PPT Generator

| Attribute | Details |
|-----------|---------|
| **Name** | PowerPoint Template Engine |
| **Description** | JSON-driven slide templates (`standard`, `arweqah`), generates slide content via OpenAI, DALL-E for images, applies themes, uploads PPTX to Supabase. |
| **Technologies** | Python, python-pptx, OpenAI (chat + DALL-E) |
| **Location** | `apps/app/` |
| **Templates** | `apps/app/templates/*/` (config.json, layouts.json, theme.json, etc.) |

---

## 4. Data Stores

### 4.1. Supabase (Primary)

| Attribute | Details |
|-----------|---------|
| **Type** | PostgreSQL (Supabase), Storage buckets |
| **Purpose** | Source of truth for RFP/supporting file URLs, proposal generations, PPT generations, and generated artifacts. |
| **Key tables** | `Data_Table` (upload metadata), `word_gen` (proposal markdown, gen_id, rfp_files, supporting_files), `ppt_gen` (PPT generations, URLs) |
| **Buckets** | `rfp`, `supporting`, `word`, `proposal-ppts` (default names configurable via env) |
| **Clients** | Backend: `apps/api/services/supabase_service.py`, `apps/app/core/supabase_service.py`; Frontend: `apps/frontend/app/supabase/client.ts`, `admin.ts` |

### 4.2. PostgreSQL (Local Dev)

| Attribute | Details |
|-----------|---------|
| **Type** | PostgreSQL 16 |
| **Purpose** | RFP application database in local Docker setup. |
| **Config** | `docker-compose.dev.yml` (postgres service) |

### 4.3. Redis

| Attribute | Details |
|-----------|---------|
| **Type** | Redis 7 |
| **Purpose** | Reserved for future workers/queueing. |
| **Config** | `docker-compose.dev.yml` (redis service) |

---

## 5. External Integrations

| Service | Purpose | Integration method |
|---------|---------|--------------------|
| **OpenAI** | Proposal markdown generation, slide content, DALL-E images | REST API (Responses API, Chat Completions, Images API) |
| **Supabase** | Database, storage, auth (if used) | Official SDK (Python, JavaScript) |
| **OneDrive** (optional) | Referenced in health check route | `nextapi/check-onedrive` |

---

## 6. Data & Processing Flow

1. **Upload**  
   User drops RFP + supporting files → Next.js `upload` route → Supabase Storage buckets → URLs stored in `Data_Table` under a generated `uuid`.

2. **Initial proposal generation**  
   UI → `POST /api/initialgen/{uuid}` → Backend fetches RFP/supporting URLs → WordGenAPI uploads PDFs to OpenAI → streams markdown via SSE → saves to `word_gen` → triggers Word generation.

3. **Download Word**  
   UI → `POST /api/download/{uuid}` → Backend loads latest markdown → `generate_word_from_markdown` → returns Supabase URL for `.docx`.

4. **Regeneration with comments**  
   User adds structured comments → UI → `POST /api/regenerate` with `uuid`, `gen_id`, comments → new row in `word_gen` with new `gen_id` → regeneration prompt → updated markdown and Word URL.

5. **PPT generation & regeneration**  
   UI → `POST /api/ppt-initialgen` or `POST /api/ppt-regeneration` → Backend uses template engine → OpenAI for content, DALL-E for images → uploads PPTX to Supabase → returns download URL.

---

## 7. Deployment & Infrastructure

| Attribute | Details |
|-----------|---------|
| **Cloud** | Azure (VM) |
| **CI/CD** | GitHub Actions (`.github/workflows/deploy.yml`) — on push to `master`, SSH to Azure VM, pull, install deps, rebuild, restart PM2 |
| **Process manager** | PM2 (`ecosystem.config.js`) |
| **Local dev** | Docker Compose (`docker-compose.dev.yml`): postgres, redis, api, frontend |

---

## 8. Security Considerations

| Area | Implementation |
|------|----------------|
| **Secrets** | No secrets in code; use `.env` (gitignored) and secret managers. `.env.example` for variable names only. |
| **Supabase keys** | `SUPABASE_KEY` (service role) for backend; `NEXT_PUBLIC_SUPABASE_ANON_KEY` for frontend; `SUPABASE_SERVICE_ROLE_KEY` server-side only. |
| **CORS** | `CORSMiddleware` allows all origins in current config; restrict in production as needed. |
| **Data in transit** | TLS for HTTP traffic (handled by reverse proxy / hosting). |
| **Storage** | Supabase Storage for uploaded and generated files; access controlled via Supabase policies. |

---

## 9. Development & Testing

| Aspect | Details |
|--------|---------|
| **Setup** | See [README.md](README.md) and [CONTRIBUTING.md](CONTRIBUTING.md). |
| **Linting / formatting** | Python: `ruff check .`, `ruff format --check .`; TS/TSX: `eslint`, `prettier --check`. Enforced via `.github/workflows/ci.yml`. |
| **Testing** | pytest for Python; tests required for core logic per CONTRIBUTING. |
| **Branching** | Per-developer branches (`dharani-dev`, `hari-dev`, etc.) → PR to `Testing` → merge when CI passes. |

---

## 10. Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Supabase as source of truth** | Centralized storage and DB, real-time capabilities, simple SDK. |
| **SSE for proposal streaming** | Better UX; user sees content as it’s generated. |
| **Markdown as intermediate format** | Easy to edit, store, and convert to Word/PPT. |
| **JSON-driven PPT templates** | Flexible themes and layouts without code changes. |
| **Separate Word and PPT engines** | Different flows and dependencies; clear separation of concerns. |

---

## 11. Future Considerations

- OCR worker (`apps/workers/ocr`) is referenced in `docker-compose.dev.yml` but currently stubbed.
- Redis reserved for future background jobs/queues.
- Consider restricting CORS in production.
- Word generation: Windows + Microsoft Word recommended for best fidelity.

---

## 12. Glossary

| Term | Definition |
|------|------------|
| **RFP** | Request for Proposal — document describing requirements for a project or service. |
| **gen_id** | Generation ID — unique identifier for a proposal generation (stored in `word_gen`). |
| **uuid** | Session/use-case identifier for an upload and its associated generations. |
| **SSE** | Server-Sent Events — HTTP streaming used for real-time proposal content. |
| **PPT/PPTX** | Microsoft PowerPoint presentation format. |

---

**Document maintained by:** Development team  
**Last updated:** 2025-02-05
