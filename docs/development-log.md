# Development Log

## 2026-05-06: Session Workbench Slice 1

### Completed

- Reworked the public session page from a question-only layout into a first-pass Session Workbench.
- Kept the existing session API and answer submission flow unchanged.
- Added a live profile panel derived from `SessionState`.
- Added top core signal bars with confidence estimates from `core_sigma`.
- Added an uncertainty queue based on highest `core_sigma`.
- Added a question rationale panel derived from question layer, generation mode, scenario tags, and current uncertainty.
- Added a report readiness panel.
- Added milestone progress for `5 / 10 / 20 / 40` session vector snapshots.
- Added recent answer trajectory cards from `state.answers`.
- Added unlocked subdimension and active module context display.
- Added workbench-specific background, panel, option, and page-load motion styles.

### Validation

- `npm run lint`: passed.
- `npm run build`: passed.

### Not Completed Yet

- No backend API changes were made for richer "why this question" evidence.
- User-facing vector evidence is not displayed yet.
- Session checkpoint summary cards are still derived locally; there is not yet a dedicated public checkpoint API.
- No browser screenshot/manual visual pass has been recorded yet.

### Next Step

- Run a manual browser pass on `/session`.
- Then build Workbench slice 2:
  - expose stronger checkpoint summaries from backend if needed
  - add better milestone cards
  - decide which retrieval evidence can be safely shown to users
  - keep raw vector scores hidden from public judgment

## 2026-04-27: Embedding Vector Layer, Reranker, Session Vectors, Local Acceptance

### Completed

- Implemented Phase 1 `item_vectors`.
- Indexed item templates, generated item instances, and rewrite candidates.
- Implemented canonical text builders for templates, instances, rewrite candidates, and session snapshots.
- Implemented Qdrant-backed vector storage behind `VectorStore`.
- Implemented best-effort vector writes behind `VectorIndexer`.
- Added SQLite `vector_sync_failures` for vector write failures.
- Integrated vector indexing into template mutations and generated item persistence.
- Added retrieval context to rewrite preview before LLM candidate generation.
- Added embedding-based scoring signals to rewrite candidate scoring.
- Implemented reranker support as retrieval top-k reranking.
- Implemented Phase 2 `session_vectors`.
- Indexed session snapshots only at `5 / 10 / 20 / 40` question milestones.
- Added similar session search for admin diagnostics.
- Added Admin APIs for vector reindex, similar templates, similar sessions, and sync failures.
- Added Admin UI vector panel and rewrite retrieval evidence display.
- Added Windows-friendly local Qdrant mode through `QDRANT_LOCAL_PATH`.
- Added live acceptance scripts:
  - `backend/scripts/vector_acceptance.py`
  - `backend/scripts/ai_acceptance.py`
- Added `.env.example` placeholders for SiliconFlow, DeepSeek, Qdrant, and vector settings.
- Updated `.gitignore` so local secret files, `.env`, local Qdrant storage, and local SQLite state are not committed.

### Live Acceptance Results

- DeepSeek chat provider:
  - model: `deepseek-v4-pro`
  - result: connection test passed
  - local provider config saved into local SQLite
- SiliconFlow embedding:
  - model: `BAAI/bge-m3`
  - embedding dimension: `1024`
  - result: connection test passed
- SiliconFlow reranker:
  - model: `BAAI/bge-reranker-v2-m3`
  - result: connection test passed
- Vector reindex:
  - templates: `123` indexed, `0` failed
  - instances: `8` indexed, `0` failed
  - sessions: `0` indexed, `0` failed because there were no local milestone session snapshots
- Similar template search:
  - returned meaningful hits
  - returned rerank scores
- Vector sync failures:
  - `0` after the final acceptance run

### Issues Found And Fixed

- Qdrant local mode rejects arbitrary string point IDs.
- Fix: map business IDs to stable UUIDs before Qdrant writes.
- Original business IDs remain in payload metadata.
- DeepSeek `deepseek-v4-pro` can spend small `max_tokens` on reasoning output and return empty final content.
- Fix: AI provider health check now uses an English minimal prompt and larger `max_tokens`.
- PowerShell can write `.env` with UTF-8 BOM, causing the first key to be misread.
- Local fix: rewrite `backend/.env` as UTF-8 without BOM.

### Validation

- `python scripts/ai_acceptance.py --save`: passed locally with DeepSeek.
- `python scripts/vector_acceptance.py`: passed locally with SiliconFlow and Qdrant local mode.
- `VECTOR_ENABLED=false pytest`: `46 passed`.
- Previous frontend checks on this branch:
  - `npm run lint`: passed
  - `npm run build`: passed

### Not Completed Yet

- Public Session Workbench UI is not implemented yet.
- Admin rewrite preview still needs a manual quality check with real retrieval context.
- No `cluster_vectors` collection yet.
- No automatic vector retry worker yet.
- No production secrets manager yet.
- No CI pipeline update yet.
- No automatic anomaly or cheating label based on session vectors.

### Current Operating Model

- Local secrets live only in ignored files:
  - `backend/.env`
  - `backend/local-secrets.md`
- Local Qdrant state lives in ignored path:
  - `backend/.qdrant-local/`
- Local SQLite state is ignored:
  - `backend/distilled_ti_local.db`
- Real vector acceptance should use:
  - `cd backend`
  - `python scripts/vector_acceptance.py`
- Real chat provider acceptance should use:
  - `cd backend`
  - `python scripts/ai_acceptance.py --save`
- Unit tests should normally disable the live vector layer:
  - PowerShell: `$env:VECTOR_ENABLED='false'; pytest`

### Next Step

- Build Session Workbench slice 1.
- The user-facing session page should stop feeling like a single-question form.
- Keep the existing answer flow, but add:
  - live profile panel
  - question rationale panel
  - recent trajectory panel
  - report readiness panel
  - milestone checkpoint display
- Do this before `cluster_vectors`, because the backend already has enough vector evidence and session state to make the frontend more explanatory.
