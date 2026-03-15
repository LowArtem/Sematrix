# AGENTS.md

This file captures durable repository-level rules for autonomous agents working on **Sematrix**.

Use it to preserve stable project invariants.
Do **not** duplicate story-specific implementation details here.

If there is a conflict:

1. Follow direct user instructions.
2. Follow `CODEX.md` for execution workflow.
3. Follow this file for project-level constraints.
4. Use `./docs/full-specs.md` as the source of truth for details not repeated here.

---

## 1. Project Boundaries

- Sematrix is a **single-user local-first** notes application.
- There is **no auth, no roles, no registration**, and no password protection in MVP.
- Services exposed by Docker must bind to **localhost only** (`127.0.0.1`).
- The whole system must run locally through **Docker Compose**.
- All AI models must run **locally**. Do not introduce external LLM APIs for core product behavior.

---

## 2. Planning and Branch Model

- The PRD may be organized as **epics -> userStories**.
- A user story is the atomic executable work item.
- An epic is the planning, prioritization, and branch container for its nested stories.
- The PRD top-level `branchName` is the shared project/base integration branch.
- The PRD top-level `branchName` must not be a Git ref prefix of epic branch names (for example, avoid `foo` with epic branches like `foo/bar`), or Git cannot create both branches locally.
- In nested PRD mode, each epic must have its own `branchName`.
- All work for stories inside one epic must happen on that epic branch.
- Do not mix unfinished work from multiple epics on one branch.
- Do not create per-story branches unless the user explicitly changes the workflow.

---

## 3. Fixed Stack and Repo Shape

Keep the project aligned with the fixed stack:

- **Backend:** Python 3.12+, FastAPI, Pydantic, SQLAlchemy 2.x, Alembic
- **Workers:** Celery + Redis
- **Database:** PostgreSQL + pgvector
- **Frontend:** React + TypeScript (Vite)
- **Editor:** Tiptap
- **Local AI runtime:** Ollama
- **OCR:** PaddleOCR

Preferred repo shape:

- `backend/app/api` — HTTP layer only
- `backend/app/domain` — business logic
- `backend/app/infra` — DB models, repositories, external/local clients
- `backend/app/workers` — Celery entrypoints that call domain services
- `frontend/` — SPA

Backend foundation convention:

- Keep Celery tasks in dedicated modules under `backend/app/workers`; `celery_app.py` should register those modules and stay focused on Celery configuration.
- Keep worker task bodies thin and delegate business behavior to `backend/app/domain` services.
- Keep ENV parsing centralized in `backend/app/core/config.py` and have API/worker bootstrap code read shared settings from there instead of scattering `os.getenv(...)` calls across entrypoints.
- Keep public API error normalization centralized in `backend/app/api/errors.py` and register FastAPI exception handlers during app bootstrap instead of per-route try/except shaping.
- Keep structured logging context centralized in `backend/app/core/logging.py`, with API `X-Request-Id` binding registered from `backend/app/api/middleware.py` and Celery `task_id` binding registered from worker bootstrap instead of ad hoc per-handler logger setup.
- Keep request-scoped SQLAlchemy sessions in `backend/app/api/dependencies.py` and build repository-backed domain services from those dependencies instead of opening database sessions inside route handlers.
- Keep file-backed asset persistence in `backend/app/infra/assets.py`, and remove any just-written file on database rollback so `assets` / `note_assets` rows cannot drift from the filesystem.
- Keep local Ollama HTTP calls inside `backend/app/infra` adapters and inject those clients into note-save or pipeline services so tests can swap in fakes without moving title/summary/embedding logic into route handlers or worker tasks.
- Keep OCR calls inside `backend/app/infra/ocr.py`, and have OCR/caption stages update only their own fields plus stage-specific warnings on shared `asset_processing_results` rows so retries do not clobber sibling stage outputs.
- Keep SSRF-safe link fetching inside `backend/app/infra/link_fetcher.py`, and make every hop revalidate scheme, port, DNS-resolved IPs, redirect count, size limit, and timeout before any link-specific processing consumes the response.
- Keep YouTube Data API calls inside `backend/app/infra/youtube.py`, and have YouTube link stages persist both structured metadata and derived text/summary fields on `link_processing_results` so final indexing can consume the API result without scraping HTML in worker tasks.
- For `youtube_channel` links, keep the YouTube Data API as the primary path and only fall back to SSRF-safe web fetching on retryable API failures, storing the fallback as a warning-backed exception path instead of redefining the main design.
- Keep text-file link processing in `backend/app/infra/pipeline.py` on top of the shared SSRF-safe fetcher: enforce `MAX_TEXT_FILE_MB`, persist full extracted text on `link_processing_results`, and treat summary-generation failures as warning-backed fallbacks instead of discarding usable fetched text.
- Keep generic webpage link processing on top of the shared SSRF-safe fetcher, extract main text through `backend/app/infra/web_pages.py` with trafilatura first and readability-lxml fallback, and downgrade summary-generation failures to warning-backed heuristic summaries so usable page text still reaches indexing.
- Mirror per-object non-critical OCR/link/caption warnings onto `notes.processing_warnings` as soon as a stage persists its durable per-run result, so polled note detail can surface warnings before finalization while Ready-state finalization still deduplicates against the stage tables.

Preserve clean separation: **api -> domain -> infra**.
Do not move business logic into route handlers or UI code.

---

## 4. Core Product Invariants

### Notes

- `content_json` is the **source of truth** for note content.
- `content_text_flat` is derived text used for search/indexing.
- Note status lifecycle is fixed: **Draft -> Processing -> Ready / Error**.
- Save is **explicit only** in MVP. Do not add autosave unless the spec is changed.
- A note should enter `Processing` only after a **meaningful save**.
- If a note returns to `Draft`, derived indexing data must stop affecting search/results.

### Folders and Tags

- Folders are **flat**. No nesting in MVP.
- Deleting a folder moves notes to **no folder** (`folder_id = null`).
- Tags must be normalized to **lowercase**.
- Tags cannot contain spaces; only allowed characters from the spec are valid.

### Assets

- Images are stored on disk under `./data/assets`.
- Tiptap image nodes must reference **`assetId`**, not data URLs.
- Asset usage must be tracked through `note_assets`.
- Unused files should only be removed when they are no longer referenced anywhere.
- Image upload must always be tied to a **real `note_id`**.

---

## 5. Indexing and Pipeline Rules

- `index_version` is mandatory protection against stale background writes.
- Every Save/Reindex that triggers processing must create a new pipeline run for the current version.
- Background processing must use a **snapshot** of note assets/links for that run.
- Stale results must never overwrite newer note state.

### Pipeline ownership

- The only pipeline entrypoint is `start_pipeline(note_id, index_version, request_id)`.
- Individual OCR/link/caption stages must not be launched ad hoc from API routes.
- Only `finalize_pipeline(...)` or `pipeline_failed(...)` may set the final note state to `Ready` or `Error`.
- `finalize_pipeline(...)` must read durable current-run stage outputs from PostgreSQL and rebuild `search_text`, `embedding`, and final `summary` from that stored state, not from large Celery callback payloads.

### Worker granularity

- Worker stages should be **coarse-grained**: process all links of a note, or all images of a note.
- Do not explode work into one Celery task per single asset/link unless the spec changes.
- Do not pass large payloads through Celery/Redis. Pass identifiers only.
- Intermediate results belong in persistent storage, and finalization must read them from there.

### Error policy

- OCR failure for one image, caption failure for one image, or failure for one link is normally **non-critical**.
- Non-critical enrichment failures should produce warnings, not automatically fail the whole note.
- `Error` is reserved for failures that block finalization or make the indexed note state invalid.
- Celery retry policy is fixed: link-processing gets **3 total attempts** with exponential backoff; OCR and image-caption stages get **2 total attempts**.

---

## 6. Search and Model Rules

- Search is **hybrid**: lexical + semantic.
- Lexical search must use stored/indexed PostgreSQL FTS data, not ad hoc `to_tsvector(...)` per request.
- The FTS strategy is fixed to **RU + EN**, using explicit Russian and English configurations.
- Semantic search uses the note embedding stored in pgvector.
- Hybrid ranking uses **RRF**, not page-local score normalization.
- `search_text` is the canonical search document.
- `note.summary` must **not** be fed back into `search_text`.
- Final summary is generated **from** `search_text`, not the other way around.
- Summary generation must use the configured Qwen model in **non-thinking mode**.

---

## 7. Frontend / Backend Boundary

- Frontend is a client of the backend API.
- Backend owns:
  - note persistence
  - tag normalization
  - asset/link synchronization
  - title generation
  - summary generation
  - OCR / caption / link extraction
  - search document construction
  - embeddings
  - ranking / score calculation
- Frontend must not implement backend indexing logic locally.
- Keep the Tiptap extension set centralized in the note-editor UI and derive outgoing `content_json` from `editor.getJSON()` there, so later note actions reuse one frontend source of truth instead of hand-building document payloads.
- Keep note-editor image insertion behind one frontend upload helper that posts to `/api/assets/image` and always inserts assetId-backed Tiptap image nodes, so toolbar upload, drag-drop, and paste flows cannot drift into data-URL storage.
- MVP status updates are **REST-based only**. Do not add SSE/WebSocket status streaming unless explicitly requested.

---

## 8. Link Processing and Safety

When handling links:

- Only `http` / `https` are allowed.
- Normalize saved note URLs before snapshotting them by removing fragments/default ports, lowercasing scheme + host, and sorting query params so duplicate links inside one note collapse to one `normalized_url`.
- Only public resources are allowed.
- Requests to localhost, loopback, private, link-local, or otherwise internal IP ranges must be blocked.
- DNS resolution and redirect validation must be part of the safety model.
- Timeouts, redirect limits, and response-size limits are mandatory.

YouTube-specific rule:

- Prefer the official **YouTube Data API v3**.
- Do not treat raw HTML scraping as the main YouTube integration path.

---

## 9. Draft Cleanup and Operations

- Empty/abandoned Draft notes are expected and must be cleaned up by a scheduled TTL job.
- Draft cleanup belongs to the worker layer and must be scheduled via **celery beat**, not the API process.
- Draft cleanup emptiness should follow the same meaningful-content rule as Save, using the current `content_json` state rather than lingering pre-save `note_assets` rows alone, so abandoned Draft uploads remain TTL-cleanable.
- Persistent runtime data lives under `./data`.
- Configuration should come from **ENV** with sensible defaults.
- The repo should remain reproducible from a fresh checkout with Docker-based startup.

---

## 10. What to Store Here

Keep this file short and durable.
Add only repository truths that future tasks will need repeatedly, such as:

- architectural boundaries
- lifecycle invariants
- branch/workflow invariants
- search/indexing invariants
- security constraints
- fixed product assumptions

Do **not** store here:

- story-by-story notes
- temporary debugging context
- one-off migration details
- task-specific implementation plans

Those belong in `progress.txt`, PRD notes, or the current task context.
