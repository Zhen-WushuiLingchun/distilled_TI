# Plan: Galgame Story Mode

- Date: 2026-05-12
- Status: AI-GAL style generation, free-text classifier, SD WebUI asset generation, share/evolution/social UI slice implemented; 2026-05-13 DeepSeek scene routing and browser smoke passed
- Scope: make Distilled TI playable by wrapping measurement questions in a visual-novel style scenario loop.

## Reference Review

Two reference projects were downloaded into a temporary local directory for review:

- `Empty-ZZJ/HOILAI-Galgame-Framework`
  - Unity/C# galgame framework
  - Apache-2.0
  - Strong for standalone Unity games, XML-style scripts, hot update, character animation, and nested branches
  - Not selected for direct integration because this repo is a Web/FastAPI/Next product
- `tamikip/AI-GAL`
  - Python/Ren'Py based AI galgame
  - main project MIT, with Ren'Py/LGPL/Zlib related distribution considerations
  - Strong for AI-generated story setup, branch choices, snapshots, and user custom input
  - Not selected for direct integration because Ren'Py/desktop launcher/image/audio dependencies would create a separate runtime

Decision: borrow the AI-GAL product pattern, not its runtime or code. Implement Story Mode natively in the existing Web stack.

Follow-up after inspecting AI-GAL more closely: the useful part is not a fixed questionnaire wrapper, but the loop of `theme + character setting + story history + branch choice + optional player custom input -> next generated scene`. The current implementation therefore keeps the measurement prompt as a hidden seed and lets the LLM write a playable scene with only two hard constraints: keep option keys mappable, and do not present direct psychological diagnosis.

2026-05-13 correction: the public Story Mode must not feel like a converted test item. The visible scene, choices, backlog, and custom-input placeholder must be natural visual-novel content. Measurement anchors remain only as backend `option_key` values and hidden analysis seeds; option scores and questionnaire labels are not sent to the story LLM and are not rendered in the main UI.

## Product Goal

The normal test loop is accurate but not fun. Story Mode changes the presentation:

- each item becomes a hidden analysis seed for a campus/relationship scenario
- options become natural in-scene choices, not agreement labels
- user can also write a custom line
- the custom line is stored as additional context
- existing scoring still receives a normal `option_key`
- report, session vectors, clustering, and long-term archives continue to work

This gives users a game-like loop while still preserving measurement continuity.

## Implemented Backend

- Added `GalgameScene`, `GalgameChoice`, and `GalgameTurn`.
- Added SQLite `galgame_turns`.
- Added AI-GAL style scene construction in `SessionService.build_galgame_scene()`.
- Added public text sanitation so raw prompts, backend fields, score-like labels, and questionnaire wording fall back to natural VN text.
- Added `AIService.generate_galgame_scene()` for OpenAI-compatible story generation.
- Added turn recording in `SessionService.record_galgame_turn()`.
- Added free-text tendency inference:
  - LLM produces option-level probability distribution when configured.
  - embedding compares the player line against current scene choices when embedding is configured.
  - a fusion layer returns `source`, `confidence`, `option_scores`, and explanation.
  - if free text confidence is above `GALGAME_FREE_TEXT_INFERENCE_MIN_CONFIDENCE`, scoring uses the inferred option.
  - if AI/vector services fail, rule fallback preserves the story flow.
- Added `EmbeddingService.build_galgame_turn_document()`.
- Added `VectorIndexer.index_galgame_turn()`, `search_similar_galgame_turns()`, and `galgame_turns` reindex scope.
- Added Admin story-template APIs and story-turn similar-search API.
- Added public endpoints:
  - `GET /api/session/{session_id}/galgame/scene`
  - `POST /api/session/{session_id}/galgame/respond`
- Added Story Mode asset resolution:
  - `GalgameAssetReference` on scene responses
  - local fallback background/sprite/audio assets
  - optional SD WebUI-compatible and OpenAI-compatible image generation controlled by env vars
  - Admin asset status/manual generation/story-template pre-generation APIs
  - conservative generated-character alpha post-processing for sprite-like PNGs
  - generated assets written under ignored `frontend/public/generated/galgame`
- `respond` records the story turn, resolves free-text tendency when available, then calls the existing scoring path through `submit_answer()`.
- `respond` accepts `choice_text` so `galgame_turns.scene_text` records the visible player branch or custom line instead of an internal option label.
- DeepSeek live Story Scene routing now sends `thinking={"type":"disabled"}` by default for `deepseek-v4-pro` and retries without optional provider controls if the endpoint rejects them.
- Scene JSON parsing now accepts `choice_texts` as either an object or an array of `{option_key,text}`.

## Implemented Frontend

- Added `/story`.
- Added `StoryClient`.
- Added Story Mode entry on the landing page.
- Story UI includes:
  - visual stage
  - generated/fallback background image
  - generated/fallback character sprite
  - narrator text
  - character line
  - in-scene choice buttons
  - custom free-line input
- recent memory fragments hidden in Debug
- AI/fallback scene evidence hidden in Debug
  - background/character asset keys
  - free-text tendency distribution after custom input
  - report readiness entry
- Story Mode reuses current active session if present, or starts a new one.
- If a user invite profile exists locally, Story Mode starts sessions under that user.
- Added `/share` so report shares carry the sharer's invite code.
- Added `/evolution` so invite-backed users can see long-term report/session trajectory.
- Added public `/profile` recommendation UI, still gated by environment flag and opt-in.
- Existing users who enter through `/share?invite=...` now claim the inviter edge before routing to `/story`, preserving the invite relationship graph.
- New users who enter through `/share?invite=...` must register with email plus invite code; the email is stored only as a uniqueness hash.
- Profile, report, and evolution share links all use the current user's personal invite code.

- Added Admin Story Engine panel:
  - create/update/delete story templates
  - configure theme, outline, location, speaker, character/background keys and prompts
  - reindex/search `galgame_turns`

## Local Validation

- Backend: `VECTOR_ENABLED=false GALGAME_AI_SCENE_ENABLED=false LOCAL_DB_PATH=<temp db> pytest -q` passed with `64 passed`.
- Frontend: `npm run lint` passed after the current slice, with only the expected dynamic `<img>` warnings.
- Frontend: `npm run build` passed after the current slice.
- Real DeepSeek scene smoke:
  - direct `AIService.generate_galgame_scene()` returned valid final scene JSON.
  - public `/api/session/{id}/galgame/scene` returned `ai_generated=true`.
- Browser acceptance covered:
  - `/share` existing-user invite claim to `/story`
  - `/story` live generated scene with no console errors
  - `/profile` personal invite and Social Lab shell
  - `/evolution` history shell and invite copy action
  - `/report` Share / Export controls from a finalized snapshot

## Measurement Boundary

The first slice used manual option selection only. Current slice upgrades this:

- Free text is now classified into option tendencies.
- Classification is not a psychological diagnosis; it only maps the line to the closest current scene option.
- The mapping is explainable through LLM score, embedding score, and fused score.
- Low-confidence or unavailable classification falls back to the selected option/rule path.
- Every turn is saved for later `galgame_turns` vector search.

Research calibration used in this slice:

- Human-preference learning work treats preferences as signals that can come in multiple feedback formats, not only closed choices.
- open-ended survey scaling work suggests pairwise/comparative judgments can be more stable than raw zero-shot numeric ratings.
- value-consistency work warns that open-ended and multiple-choice mappings need consistency checks.
- embedding work supports using contextual text embeddings as a semantic similarity layer rather than exact lexical matching.

References checked:

- <https://arxiv.org/abs/2406.11191>
- <https://arxiv.org/pdf/2401.00368>
- <https://aclanthology.org/2024.findings-emnlp.891.pdf>
- <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5112677>

## Not Done Yet

- ComfyUI generation adapter is not implemented yet; status probing exists, but generation needs a workflow adapter.
- Audio generation is not implemented yet; current audio path is fallback/static only.
- Branching remains item-by-item rather than a persistent Ren'Py-style graph.
- Character sprites can still fall back to local placeholder art when local generation is unavailable or not suitable.
- Public Social Lab can render, but useful candidates still require opt-in and report-ready sessions.

## Next Slices

1. Improve real sprite/background quality and generation prompts before expanding the social surface further.
2. Add a ComfyUI workflow adapter if local SD WebUI quality is not enough.
3. Add a cloud image provider adapter if local generation is too heavy for deployment.
4. Add deeper branch memory once story quality is stable.
5. Add public invite abuse controls and clearer opt-in copy before broader social/recommendation exposure.

## 2026-05-12 SD WebUI Acceptance

- Local SD WebUI: `http://127.0.0.1:7860`
- Detected model: `anything-v5-PrtRE.safetensors`
- Admin generated assets: 4 backgrounds and 4 character sprites.
- Public scene API returned generated background and generated character asset URLs.
- Browser `/story` smoke rendered generated PNG assets with no console errors; Debug panel reported `generated / generated`.
