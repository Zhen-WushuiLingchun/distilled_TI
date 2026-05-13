# Development Log

## 2026-05-13: Invite-Gated Email Registration

### Completed

- Converted invite redemption into real invite-gated registration:
  - `POST /api/invite/redeem` now requires both `invite_code` and `email`
  - email is normalized and hashed server-side
  - one normalized email can only create one anonymous user profile
  - API returns `email_already_registered` for duplicate registration
  - API returns `invalid_email` for malformed email
- Added `UserProfile.email_hash` and a SQLite unique index on `user_profiles.email_hash`.
- Kept public identity pseudonymous:
  - frontend still stores only `user_id / user_secret / handle`
  - profile/admin responses expose `email_registered`, not the raw email or email hash
- Updated landing and share entry UI:
  - new users must enter email plus invite code
  - existing local anonymous users can still claim share links without re-registering
- Removed duplicate invite-relationship creation in `redeem_invite`; invite edges are now written through one helper path.

### Validation

- Backend: `VECTOR_ENABLED=false GALGAME_AI_SCENE_ENABLED=false LOCAL_DB_PATH=<temp db> python -m compileall app tests; pytest -q` passed with `65 passed`.
- Frontend: `npm run lint` passed with the existing two dynamic `<img>` warnings in `StoryClient.tsx`; `npm run build` passed.
- Browser smoke using system Chrome:
  - landing invite + email registration saved a local anonymous profile.
  - share-page invite + email registration routed the new user to `/story`.
  - duplicate normalized email registration returned `email_already_registered`.
  - screenshots:
    - `C:\Users\hydro\AppData\Local\Temp\distilled-ti-email-registration-smoke\landing-email-registration.png`
    - `C:\Users\hydro\AppData\Local\Temp\distilled-ti-email-registration-smoke\share-email-registration-to-story.png`

## 2026-05-13: DeepSeek Story Provider Routing And Public Social Share Acceptance

### Completed

- Fixed live Story Scene generation for `deepseek-v4-pro` by adding provider-specific request controls:
  - default `thinking={"type":"disabled"}` for DeepSeek scene calls
  - optional `GALGAME_AI_SCENE_REASONING_EFFORT`
  - optional `GALGAME_AI_SCENE_OUTPUT_EFFORT`
  - retry variants that drop `response_format` and provider controls when an OpenAI-compatible endpoint rejects them
- Made Story Scene JSON parsing more tolerant:
  - empty final content retries the next variant instead of immediately falling back
  - `choice_texts` can now be returned as either an object or an array of `{option_key,text}`
  - invalid scene JSON still falls back safely and does not block play
- Changed invite-backed sharing from "entry code only" to "personal share invite":
  - every authenticated anonymous user is lazily assigned a personal invite code created by that user
  - new users who redeem another user's personal invite create an anonymous `invited` edge
  - existing users who open `/share?invite=...` now call `POST /api/user/invite/claim`
  - successful claims create an anonymous `invited` relationship edge without replacing the user's own share invite
- Promoted the hidden recommendation surface into the public `/profile` Social Lab while keeping user opt-in and report-readiness gates.
- Added visible share affordances:
  - `/profile` personal invite/share entry
  - `/evolution` copy invite entry and resume/report buttons for history rows
  - `/report` export JSON now includes `shared_by`, `invite_code`, and `share_url`
  - all public outward share links point to `/share` with the sharer's personal invite code

### Validation

- Backend targeted tests for DeepSeek request controls, retry variants, choice text normalization, and existing-user invite claims passed.
- Backend full regression: `VECTOR_ENABLED=false GALGAME_AI_SCENE_ENABLED=false LOCAL_DB_PATH=<temp db> pytest -q` passed with `64 passed`.
- Frontend: `npm run lint` passed with the existing two dynamic `<img>` warnings in `StoryClient.tsx`.
- Frontend: `npm run build` passed.
- Real DeepSeek/API smoke:
  - direct `AIService.generate_galgame_scene()` with `deepseek-v4-pro` returned a valid scene JSON.
  - public `/api/session/{id}/galgame/scene` returned `ai_generated=true`, 5 choices, and generated background asset.
- Browser smoke using system Chrome:
  - `/share?invite=...` as an existing user claimed the inviter edge and routed to `/story`.
  - `/story` loaded a live generated scene; `session/start` and `galgame/scene` both returned 200; no console errors.
  - `/profile` showed personal invite, Social Lab enabled state, and result archive.
  - `/evolution` showed history shell and copy invite entry.
  - `/report` rendered Share / Export controls from a finalized local snapshot and showed the user's invite code.
  - screenshots:
    - `C:\Users\hydro\AppData\Local\Temp\distilled-ti-public-ui-smoke\share-before-claim.png`
    - `C:\Users\hydro\AppData\Local\Temp\distilled-ti-public-ui-smoke\story-live-scene.png`
    - `C:\Users\hydro\AppData\Local\Temp\distilled-ti-public-ui-smoke\profile-social-share.png`
    - `C:\Users\hydro\AppData\Local\Temp\distilled-ti-public-ui-smoke\evolution-history.png`
    - `C:\Users\hydro\AppData\Local\Temp\distilled-ti-public-ui-smoke\report-share-export.png`

### Not Completed Yet

- Character sprites can still fall back to local placeholder art when SD/Web image generation does not produce a usable transparent sprite.
- Public recommendations are visible as a Social Lab shell, but useful candidates still require both users to opt in and have report-ready sessions.
- There is no production moderation/abuse workflow for public invite sharing yet.
- ComfyUI generation remains a status probe only; generation still needs a workflow adapter.

### Next Step

- Improve the sprite/background asset quality path before adding more social surfaces.
- Add production controls for invite abuse, opt-in copy, and share-link throttling.
- Continue toward richer report history/evolution once there is enough long-lived user data.

## 2026-05-13: Natural Story Mode Boundary

### Completed

- Removed the last active path that could turn a raw `ItemInstance.prompt` into visible Story Mode dialogue.
- Changed scene generation payloads so the LLM receives natural branch text plus hidden `option_key`, not option scores or questionnaire labels.
- Added `choice_text` to the galgame response API so saved `galgame_turns.scene_text` preserves what the player actually saw or wrote.
- Tightened public scene sanitation:
  - rejects raw prompts, backend fields, questionnaire labels, and score-like option text
  - falls back to natural VN-style narration and choices
  - keeps classifier, embedding, pairwise, and asset evidence behind Debug/Workbench only
- Updated `/story` copy so the loading state, free-line placeholder, choice buttons, and backlog no longer describe the experience as a converted measurement question.
- Added a regression test that simulates a bad AI scene containing measurement leakage and verifies the public scene falls back to natural text.
- Added configurable Story Scene LLM budget:
  - `GALGAME_AI_SCENE_TIMEOUT_SECONDS`
  - `GALGAME_AI_SCENE_MAX_TOKENS`
  - JSON response format is attempted first, then retried without it for provider compatibility.

### Validation

- Backend targeted: `VECTOR_ENABLED=false pytest tests/test_session_api.py::test_galgame_scene_wraps_current_question_and_records_custom_text tests/test_session_api.py::test_galgame_scene_filters_ai_measurement_leaks -q` passed with `2 passed`.
- Backend compile: `python -m compileall app tests` passed.
- Backend full: `VECTOR_ENABLED=false GALGAME_AI_SCENE_ENABLED=false LOCAL_DB_PATH=<temp db> pytest -q` passed with `60 passed`.
- Frontend: `npm run lint` passed with the existing two dynamic `<img>` warnings in `StoryClient.tsx`.
- Frontend: `npm run build` passed.
- Browser `/story` smoke:
  - 5 natural branch choices rendered.
  - generated background and character assets rendered.
  - no console errors.
  - no visible `非常同意 / 非常不同意 / 当前映射 / option_key / prompt_shadow / score-like` leakage.
  - screenshot: `C:\Users\hydro\AppData\Local\Temp\distilled-ti-story-naturalized\story-naturalized-final.png`
- DeepSeek local config was switched to `deepseek-v4-pro` and Admin connection test passed. Real scene generation still fell back to natural local fallback because the model did not return valid final scene JSON in `message.content` during the browser/API smoke.

### Not Completed Yet

- Story quality still depends on the configured LLM and SD model; this patch prevents measurement leakage but does not guarantee high literary quality.
- `deepseek-v4-pro` scene generation needs provider-specific follow-up if it keeps returning reasoning-only or invalid final JSON. Current runtime remains safe because it falls back to natural VN text.

### Next Step

- If the rendered scene is still weak, tune only the story prompt/template/asset prompts, not the measurement scaffolding.
- Decide whether Story Mode should use a non-reasoning chat model for live scene text while reserving `deepseek-v4-pro` for slower analysis/report tasks.

## 2026-05-12: VN Asset Pipeline, Share Links, Evolution, Public Social UI

### Completed

- Added a real Story Mode asset pipeline:
  - backend `galgame_asset_service.py`
  - `GalgameAssetReference` fields on `GalgameScene`
  - local fallback background SVGs, character sprite SVGs, and ambient WAV
  - optional SD WebUI or OpenAI-compatible image generation through env config
  - Admin asset status, manual generate, and story-template pre-generation APIs
  - conservative connected-background alpha post-processing for generated character sprites
  - generated assets ignored under `frontend/public/generated/`
- Updated AI scene generation to return image-model-friendly English prompts for background and character assets.
- Reworked `/story` away from the analysis-heavy side panel:
  - full-screen visual novel background image
  - character sprite image
  - bottom dialogue box
  - Log / Hide / Template / Debug / Report controls
  - classifier/asset evidence hidden behind Debug
- Added public user evolution API and `/evolution` page for long-term report/history trajectory.
- Added public opt-in recommendation UI on `/profile`, still gated by `RELATIONSHIP_RECOMMENDATIONS_ENABLED` and user opt-in.
- Added `/share` landing page and report share/export controls.
- Share links generated from reports include the sharer's invite code, so incoming users preserve invite graph attribution.

### Validation

- Backend: `VECTOR_ENABLED=false pytest` passed with `59 passed`.
- Frontend: `npm run lint` passed with two existing `<img>` optimization warnings for dynamic local asset URLs.
- Frontend: `npm run build` passed.
- Real SD WebUI acceptance:
  - local SD WebUI at `http://127.0.0.1:7860` responded through `/sdapi/v1/sd-models`.
  - model detected: `anything-v5-PrtRE.safetensors`.
  - Admin asset API generated 4 backgrounds and 4 character sprites under `frontend/public/generated/galgame`.
  - Public `/api/session/{id}/galgame/scene` returned `background_asset.source=generated` and `character_asset.source=generated`.
  - Browser smoke on `/story` rendered generated background/sprite, 5 choices, no console errors, and Debug showed `generated / generated`.
  - Screenshot evidence:
    - `C:\Users\hydro\AppData\Local\Temp\distilled-ti-vn-browser\story-vn-generated-v2.png`
    - `C:\Users\hydro\AppData\Local\Temp\distilled-ti-vn-browser\story-vn-debug-v2.png`

### Not Completed Yet

- Browser acceptance for share/evolution/profile is still pending; `/story` asset UI is smoke-tested.
- ComfyUI is only probed in status; generation still needs a workflow adapter file before it can run.
- Audio generation is not implemented yet; Story Mode has fallback/static ambient audio only.
- Recommendation remains disabled by default until the operator explicitly enables `RELATIONSHIP_RECOMMENDATIONS_ENABLED`.

### Next Step

- Run local browser smoke against `/`, `/share`, `/profile`, and `/evolution`.
- Tune SD prompt templates and add a ComfyUI workflow adapter or cloud image backend only if SD WebUI quality is insufficient.

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
