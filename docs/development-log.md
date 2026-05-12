# Development Log

## 2026-05-12: Galgame UI, Pairwise Calibration, User Story Templates

### Completed

- Reviewed `Nova42x/paper2galgame` locally and borrowed the Web VN interaction pattern without copying code, assets, or API keys.
- Rebuilt `/story` into a fuller galgame-style window:
  - full-screen background stage
  - character silhouette
  - typewriter dialogue
  - choice overlay
  - free-line input inside the dialogue area
  - Log / Hide / Template / Workbench controls
  - classifier evidence drawer
- Added public invite-user story template APIs:
  - `GET /api/user/galgame/story-templates`
  - `POST /api/user/galgame/story-templates`
  - `PUT /api/user/galgame/story-templates/{template_id}`
  - `DELETE /api/user/galgame/story-templates/{template_id}`
- Added `owner_user_id` handling for `GalgameStoryTemplate`.
- Let user-owned templates participate in scene-template selection alongside system templates.
- Added pairwise free-text comparison scoring:
  - deterministic no-network pairwise classifier
  - fused with LLM and embedding distributions when available
  - persisted `pairwise_scores` into `GalgameTurn`
- Added offline calibration fixture set and script:
  - `backend/app/domain/galgame_calibration.py`
  - `backend/scripts/galgame_text_calibration.py`
- Added non-diagnostic `support_risk_flags` to `SessionReport`.
- Added report UI for support signals, explicitly marked as non-diagnostic and suitable only for support/triage workflows.
- Documented how the backend analysis layer can be reused in AI assistant/chat contexts for safer support escalation without making medical or psychological diagnoses.

### Validation

- Backend: `python -m compileall backend/app backend/tests` passed.
- Backend: `python backend/scripts/galgame_text_calibration.py` passed with `9/9`.
- Backend: `VECTOR_ENABLED=false pytest` passed with `56 passed`.
- Frontend: `npm run lint` passed.
- Frontend: `npm run build` passed.
- Browser acceptance:
  - `/story` loaded the VN frame with dialogue and 5 choices.
  - Template drawer created/listed a private `Mine` template for an invite-backed anonymous user.
  - Free-line submission advanced to Q2 and displayed classifier evidence with LLM / embedding / pairwise fields.
  - Console error capture was empty.
  - Screenshots:
    - `C:\Users\hydro\AppData\Local\Temp\distilled-ti-galgame-vn-acceptance\story-template-drawer.png`
    - `C:\Users\hydro\AppData\Local\Temp\distilled-ti-galgame-vn-acceptance\story-after-free-line.png`

### Not Completed Yet

- No generated image/sprite/audio asset pipeline yet.
- No public friend/recommendation UI; recommendation remains hidden/admin-side.
- No production crisis-support workflow, consent copy, audit trail, or human review queue.
- No true multi-character sprite asset library yet; current UI uses CSS silhouettes and provider-generated text.

### Next Step

- Continue toward share/export, report archive evolution, and optional hidden social graph visualization.
- If the story experience becomes the primary public mode, add real sprite/background asset generation or curated asset packs next.

## 2026-05-12: AI-GAL Story Generation And Free-Text Classifier

### Completed

- Reviewed AI-GAL and HOILAI references; chose to borrow AI-GAL's generative loop rather than vendoring Ren'Py/Unity runtimes.
- Relaxed Story Mode generation so the LLM writes playable galgame scenes from theme, characters, history, branch choice, and hidden measurement seed.
- Added Admin-managed story templates for theme, outline, location, speaker, character/background keys, and asset prompts.
- Added AI scene generation via OpenAI-compatible chat provider.
- Added free-text tendency classification:
  - LLM option distribution when configured
  - embedding similarity between player line and current choices when configured
  - rule fallback when AI/vector services are unavailable
  - fused `text_inference` with option-level scores and reason
- Let confident free-text inference map back to scoring option keys while preserving fallback to explicit selection.
- Added `galgame_turns` vector documents, indexing, reindex scope, and Admin similar story-turn search.
- Updated `/story` to show AI/fallback status, background/character keys, and free-text classification evidence.

### Validation

- Backend: `VECTOR_ENABLED=false pytest` passed with `53 passed`.
- Backend: `python -m compileall backend/app backend/tests` passed.
- Frontend: `npm run lint` passed.
- Frontend: `npm run build` passed.
- Browser acceptance:
  - `/story` loaded a playable scene with choices, custom free-line input, asset keys, and classifier panel after submission.
  - `/admin` loaded the Story Engine template panel and vector scope support for `galgame_turns`.
  - Screenshots:
    - `C:\Users\hydro\AppData\Local\Temp\distilled-ti-galgame-acceptance\story-galgame-classifier.png`
    - `C:\Users\hydro\AppData\Local\Temp\distilled-ti-galgame-acceptance\admin-story-engine.png`

### Not Completed Yet

- No generated image/sprite/audio asset pipeline yet.
- No offline calibration dataset or pairwise-comparison scorer for ambiguous free text yet.

### Next Step

- Add a small free-text calibration fixture set before changing classifier weights.
- Then consider pairwise comparison for ambiguous free-text turns.

## 2026-05-06: Session Workbench Slice 4

### Completed

- Added a report preview panel inside the public `/session` Workbench.
- Kept preview generation on demand; normal answer submission still does not generate reports.
- Before the report threshold, the panel explains how many questions remain.
- After `min_questions_for_report`, users can generate a preview without leaving the session.
- Preview shows:
  - narrative label and cluster name
  - AI/fallback summary
  - question count, cluster confidence, average sigma, stable dimension count
  - top structural signals
  - salient subdimensions and active modules
- Users can still continue answering after preview, or enter the full `/report` flow.
- Fixed duplicate React keys for repeated scenario tags in the session page and evidence cards.

### Browser Acceptance

- Ran a real Chrome DevTools Protocol pass against local `/session`.
- Evidence drawer acceptance:
  - loaded `/session`
  - clicked retrieval evidence
  - confirmed `vector offline`, `reranker not applied`, no raw vector score text, and no console errors
  - screenshot: `C:\Users\hydro\AppData\Local\Temp\distilled-ti-acceptance\session-workbench-evidence.png`
- Report preview acceptance:
  - cleared browser session storage
  - submitted 20 answers through real UI buttons
  - generated report preview
  - confirmed `Report Preview`, `Structural Signals`, `进入完整报告页`, and no console errors
  - screenshot: `C:\Users\hydro\AppData\Local\Temp\distilled-ti-acceptance\session-report-preview.png`

### Validation

- Frontend: `npm run lint` passed.
- Frontend: `npm run build` passed.
- Browser acceptance passed after restarting frontend dev server to clear stale HMR state.

### Not Completed Yet

- Broader browser pass on `/report`, `/history`, and `/admin` is still pending.
- Slice 5 visual polish and mobile refinement are not implemented yet.
- Admin rewrite preview still needs manual quality validation with real vector retrieval.
- No `cluster_vectors` work yet.

### Next Step

- Run broader browser acceptance across the remaining pages.
- Then do Slice 5: polish layout hierarchy, mobile density, and final workbench UX details.

## 2026-05-06: Session Workbench Slice 3

### Completed

- Added a public, session-secret-protected evidence endpoint:
  - `GET /api/session/{session_id}/workbench/evidence`
- Added safe `WorkbenchEvidence` and `WorkbenchEvidenceItem` response models.
- Reused existing vector retrieval instead of introducing another vector path:
  - item evidence from template / historical item instance / rewrite candidate retrieval context
  - session evidence from `session_vectors` similar-session snapshots
- Kept evidence loading out of the main answer submission path.
- Hid raw vector scores and raw rerank scores from the public response.
- Converted retrieval strength into `high / medium / low` confidence tiers.
- Sanitized session snapshot evidence so anonymous session canonical text is not exposed.
- Added an on-demand retrieval evidence drawer in `/session`.
- Documented that retrieval evidence is explanation support only, not a final personality conclusion.

### Validation

- Backend targeted test: `VECTOR_ENABLED=false pytest backend/tests/test_session_api.py -q` passed with `4 passed`.
- Full backend: `VECTOR_ENABLED=false pytest` passed with `47 passed`.
- Frontend: `npm run lint` passed.
- Frontend: `npm run build` passed.
- Tracked secret scan passed with no `sk-...` values found in tracked files.

### Not Completed Yet

- Manual browser visual pass on `/session` is still pending.
- Slice 4 report preview and user-facing narrative summary are not implemented yet.
- No `cluster_vectors` work yet.

### Next Step

- Do a browser pass on `/session`.
- Next feature slice: report preview / narrative summary after the report threshold.

## 2026-05-06: Session Workbench Slice 2

### Completed

- Added backend `WorkbenchCheckpoint` payloads as optional public API fields.
- Added checkpoint data to:
  - `POST /api/session/start`
  - `POST /api/response/submit`
  - `GET /api/session/{session_id}/summary`
- Kept existing public API fields compatible.
- Added backend-derived milestone status for `5 / 10 / 20 / 40` session vector snapshots.
- Added backend-derived report progress, snapshot readiness, top core signals, uncertainty queue, active modules, unlocked subdimensions, and a short workbench narrative.
- Updated the frontend API types for `WorkbenchCheckpoint`, `WorkbenchSignal`, and `WorkbenchMilestone`.
- Updated `/session` to prefer backend checkpoint data and fall back to local derivation if the field is absent.
- Replaced the simple milestone progress block with explicit milestone cards.
- Kept raw vector scores hidden from the public user experience.

### Validation

- Backend: `VECTOR_ENABLED=false pytest` passed with `46 passed`.
- Frontend: `npm run lint` passed.
- Frontend: `npm run build` passed.

### Not Completed Yet

- Manual browser visual pass on `/session` is still pending.
- No user-facing retrieval evidence drawer yet.
- No dedicated public similar-session explanation yet.
- No `cluster_vectors` work yet.

### Next Step

- Do a real browser pass on `/session` with backend and frontend running.
- Then build Workbench Slice 3:
  - decide whether retrieval evidence should be user-facing or admin/internal only
  - add an insight drawer if safe
  - avoid exposing raw vector scores as personality conclusions

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

## 2026-05-12: Invite-Backed Anonymous Users, Long-Term Archives, Hidden Recommendations Foundation

### Completed

- Added invite-backed anonymous user profiles.
- Added local bootstrap invite support through `INVITE_BOOTSTRAP_CODE`.
- Added `user_profiles`, `invite_codes`, and `user_relationships` SQLite tables.
- Added `sessions.user_id` and long retention for registered anonymous users through `REGISTERED_SESSION_TTL_DAYS`.
- Added public user APIs:
  - `POST /api/invite/redeem`
  - `GET /api/user/me`
  - `PATCH /api/user/me`
  - `GET /api/user/sessions`
  - `POST /api/user/session/{session_id}/access`
- Added admin user/invite APIs:
  - `POST /api/admin/invites`
  - `GET /api/admin/invites`
  - `GET /api/admin/users`
  - `GET /api/admin/users/relationships`
  - `GET /api/admin/users/{user_id}/recommendations`
- Added hidden recommendation candidate service:
  - disabled by default through `RELATIONSHIP_RECOMMENDATIONS_ENABLED=false`
  - requires user recommendation opt-in
  - excludes directly connected invite relationships
  - uses report-ready sessions and core profile similarity
- Added frontend invite entry on the landing page.
- Added persistent anonymous user credentials in localStorage.
- Added `/profile` for anonymous handle, privacy opt-ins, long-term session archive, resume, and report entry.
- Updated History to use user-owned long-term sessions when a user credential exists.
- Added Admin UI panels for invites, users, relationship edges, and hidden recommendation probing.
- Added `files.zip` to `.gitignore` so Claude handoff archives are not accidentally committed.

### Validation

- Backend: `VECTOR_ENABLED=false pytest` passed with `49 passed`.
- Frontend: `npm run lint` passed.
- Frontend: `npm run build` passed.

### Not Completed Yet

- No real login, email, phone, OAuth, or campus SSO.
- No public friend/recommendation UI.
- No graph visualization yet.
- No share/export implementation yet.
- No long-term evolution timeline across multiple reports yet.
- No production moderation/abuse controls for invite creation.
- No privacy policy or consent copy beyond concise in-product warnings.

### Next Step

- Build export/share and report archive polish.
- Add Admin graph visualization for invite tree and opt-in/recommendation readiness.
- Add user-facing evolution timeline comparing latest report with previous report.
- Keep recommendation UI hidden until privacy and product constraints are reviewed.

## 2026-05-12: Galgame Story Mode First Slice

### Completed

- Reviewed two AI/galgame references:
  - `Empty-ZZJ/HOILAI-Galgame-Framework`: Unity/C# framework, useful design reference but not selected for direct Web integration.
  - `tamikip/AI-GAL`: Python/Ren'Py AI galgame, useful for AI story/branch/custom-input pattern but not selected for direct runtime integration.
- Decision: implement a native Web Story Mode instead of vendoring Unity/Ren'Py code.
- Added backend models:
  - `GalgameScene`
  - `GalgameChoice`
  - `GalgameTurn`
- Added SQLite `galgame_turns` table.
- Added `SessionService.build_galgame_scene()`.
- Added `SessionService.record_galgame_turn()`.
- Added public endpoints:
  - `GET /api/session/{session_id}/galgame/scene`
  - `POST /api/session/{session_id}/galgame/respond`
- Added frontend `/story`.
- Added `StoryClient` with visual novel style stage, narrator, character line, choices, custom text input, memory fragments, and report readiness.
- Added Story Mode entry on the landing page.
- Story Mode reuses current session or starts a new invite-backed session when a local anonymous user exists.

### Validation

- Backend: `VECTOR_ENABLED=false pytest` passed with `50 passed`.
- Frontend: `npm run lint` passed.
- Frontend: `npm run build` passed.
- Browser acceptance passed on `/story`:
  - loaded the visual-novel scene
  - submitted a normal choice
  - submitted a custom free-line with a selected tendency option
  - confirmed the next scene and memory fragment update
  - confirmed the landing page exposes Story Mode and Workbench Mode entries
  - screenshots: `C:\Users\hydro\AppData\Local\Temp\distilled-ti-story-acceptance\story-after-custom.png`, `C:\Users\hydro\AppData\Local\Temp\distilled-ti-story-acceptance\landing-story-cta.png`

### Not Completed Yet

- Scenes are deterministic wrappers around existing items, not LLM-generated yet.
- Free text is stored as context but does not directly score the user.
- No image generation, voice, music, or external game engine integration.
- No vector indexing of `galgame_turns` yet.
- No authoring UI for user-written scenario/dialogue templates yet.

### Next Step

- Use embedding/LLM to classify free-text custom lines with confidence.
- Add `galgame_turns` to session canonical text or a dedicated vector collection.
- Add AI-generated scene text from current profile, current item, and recent story memory.
