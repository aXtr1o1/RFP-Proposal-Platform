# Contributing to RFP Proposal Platform

Thank you for contributing to the RFP Proposal Platform. This document outlines our development workflow, coding standards, and how to get your changes merged.

---

## Table of Contents

- [Team & Roles](#team--roles)
- [Branching](#branching)
- [Pull Request Process](#pull-request-process)
- [Coding Standards](#coding-standards)
- [Quality Gates (CI)](#quality-gates-ci)
- [Bug Tracking (Issues)](#bug-tracking-issues)
- [PR Hygiene](#pr-hygiene)
- [Getting Started](#getting-started)

---

## Team & Roles

| Role        | Name                  | Branch        |
|------------|------------------------|---------------|
| Team Lead  | Dharani Eswaramurthi   | `dharani-dev` |
| CTO        | Pragadeswaran          | —             |
| Developer  | Hariprasanth S         | `hari-dev`    |
| Developer  | Sakthivel M            | `sakthi-dev`  |
| Developer  | Pugalarasan L          | `puagl-dev`   |

**Code Owners:** Dharani Eswaramurthi and Pragadeswaran (CTO) — all PRs require their review/approval where CODEOWNERS applies.

---

## Branching

- Each developer works on their **own feature branch** (e.g. `hari-dev`, `sakthi-dev`, `puagl-dev`).
- **No direct commits to `main`.** All changes must go via Pull Request.
- Branch naming: `<firstname>-dev` (lowercase, hyphen-separated).

### Branch Flow

```
main
 └── Testing          ← PR target for dev branches (EOD on dev days)
       ├── dharani-dev
       ├── hari-dev
       ├── sakthi-dev
       └── puagl-dev
```

---

## Pull Request Process

1. **Work on your branch**  
   Create a feature branch from `Testing` (or `main` if `Testing` doesn’t exist yet) and push to your dev branch (`hari-dev`, `sakthi-dev`, etc.).

2. **Run checks locally**  
   Before pushing, ensure lint and format pass:
   - **Python:** `ruff check . && ruff format --check .`
   - **TS/TSX:** `eslint . && prettier --check .` (from `apps/frontend`)

3. **GitHub Actions**  
   On push, GitHub Actions runs lint and format. Fix any failing checks before opening a PR.

4. **Open a PR to `Testing`**  
   On development days, raise a PR **before EOD** to merge your branch into `Testing`. Prefer small, focused PRs.

5. **Review**  
   Reviewers review PRs daily. At least one approval from a Code Owner is required where CODEOWNERS applies.

6. **Merge**  
   Merge is allowed only when:
   - GitHub Actions (lint, format, tests) are green
   - Required reviews are completed
   - No merge conflicts

7. **Merge cadence**  
   Each developer must merge at least one PR to `Testing` on development days.

---

## Coding Standards

### General

- **No single-file projects.** Split code into modules/components/functions and import from the main entry point.
- **UI:** Next.js/React with `.tsx` files (no `.js` for UI).
- **Python:** Use Pydantic models for request/response and data validation — avoid passing raw dicts.
- **Python projects:** Add a `.gitignore` at the start; never commit `venv`, caches, local configs, or secrets.

### UI Assets

Place UI assets in **lowercase** folders, for example:

- `assets/logos/`
- `assets/icons/`
- `assets/images/`
- `assets/profiles/`

### Commit Conventions

- Use clear, descriptive commit messages.
- Prefer present tense: e.g. `Add user authentication` instead of `Added user authentication`.
- Reference issues when applicable: e.g. `Fix #42: Resolve upload timeout`.

---

## Quality Gates (CI)

- **Lint and format** run on every push and PR via GitHub Actions.
- Merges to `main` and `Testing` are allowed only when CI checks pass.

### Tools

| Stack      | Lint            | Format               |
|-----------|------------------|----------------------|
| Python    | `ruff check`     | `ruff format --check`|
| TS/TSX    | `eslint`         | `prettier --check`   |

### Tests

- Core logic must have tests.
- PRs that change logic should include tests or justify why they are not needed.

---

## Bug Tracking (Issues)

- Anyone can raise a GitHub Issue (including small bugs).
- If a bug is part of your active work, fix it in your branch without creating a separate issue.
- If a bug is **not** part of your work, create or update a GitHub Issue.

### Required Issue Fields

Every issue must include:

- **Steps to reproduce**
- **Expected vs actual result**
- **Environment details** (branch, build, browser, device)
- **Screenshot/video evidence** (where applicable)
- **@mention** the relevant person or Code Owner

### Closing Issues

- Only the responsible person may close an issue.
- Before closing:
  - Confirm the fix is merged into the appropriate branch
  - Attach evidence (screenshot, video, logs) if relevant

---

## PR Hygiene

- Keep PRs **small and frequent**.
- PR description must include:
  - **What** changed
  - **Why** it changed
  - **How** it was tested
  - **UI screenshots** (if applicable)

---

## Getting Started

1. **Clone and set up**

   ```bash
   git clone <repo-url>
   cd RFP-Proposal-Platform
   ```

2. **Create your branch**

   ```bash
   git checkout -b <yourname>-dev
   ```

3. **Install dependencies**

   - Backend: `pip install -r apps/requirements.txt`
   - Frontend: `cd apps/frontend && npm install`

4. **Run locally**

   - Backend: `uvicorn apps.main:app --reload --host 0.0.0.0 --port 8000`
   - Frontend: `cd apps/frontend && npm run dev`

5. **See [README.md](README.md)** for full setup, environment variables, and architecture.

---

## Security

- **Never commit secrets** in code, docs, screenshots, or logs.
- Use `.env.example` for variable names and placeholders only.
- Store real secrets in a secret manager (e.g. GitHub Secrets), not in git.

---

## Questions?

Reach out to **Dharani Eswaramurthi** (Team Lead) or **Pragadeswaran** (CTO) for process or technical questions.
