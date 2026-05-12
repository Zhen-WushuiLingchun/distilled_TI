# Plan: Galgame Story Mode

- Date: 2026-05-12
- Status: first slice implemented and locally validated
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

## Product Goal

The normal test loop is accurate but not fun. Story Mode changes the presentation:

- each item becomes a campus/relationship scenario
- options become in-scene choices
- user can also write a custom line
- the custom line is stored as additional context
- existing scoring still receives a normal `option_key`
- report, session vectors, clustering, and long-term archives continue to work

This gives users a game-like loop while still preserving measurement continuity.

## Implemented Backend

- Added `GalgameScene`, `GalgameChoice`, and `GalgameTurn`.
- Added SQLite `galgame_turns`.
- Added scene construction in `SessionService.build_galgame_scene()`.
- Added turn recording in `SessionService.record_galgame_turn()`.
- Added public endpoints:
  - `GET /api/session/{session_id}/galgame/scene`
  - `POST /api/session/{session_id}/galgame/respond`
- `respond` records the story turn, then calls the existing scoring path through `submit_answer()`.

## Implemented Frontend

- Added `/story`.
- Added `StoryClient`.
- Added Story Mode entry on the landing page.
- Story UI includes:
  - visual stage
  - character silhouette
  - narrator text
  - character line
  - in-scene choice buttons
  - custom free-line input
  - recent memory fragments
  - report readiness entry
- Story Mode reuses current active session if present, or starts a new one.
- If a user invite profile exists locally, Story Mode starts sessions under that user.

## Local Validation

- Backend: `VECTOR_ENABLED=false pytest` passed with `50 passed`.
- Frontend: `npm run lint` passed.
- Frontend: `npm run build` passed.
- Browser acceptance covered `/story` scene load, normal choice submission, custom free-line submission, memory fragment update, and the landing page Story Mode entry.

## Measurement Boundary

The first slice intentionally does not let free text directly determine psychometric score.

- The score still comes from the selected option.
- Free text is stored as additional context.
- Later phases can use embedding/LLM classification to infer option tendencies from free text, but that needs validation to avoid noisy scoring.

## Not Done Yet

- No AI-generated scenes yet.
- No image generation, character sprites, voice, or music.
- No embedding index for `galgame_turns` yet.
- No free-text scoring classifier yet.
- No authoring UI for user-written scenario templates yet.
- No branching story graph beyond the current item-by-item loop.

## Next Slices

1. Add `galgame_turn_vectors` or fold turns into session snapshot canonical text.
2. Add AI scene generation using current session profile, similar items, and recent turns.
3. Add admin/user scenario authoring.
4. Add free-text tendency classification with explicit confidence and fallback to manual option selection.
5. Add lightweight sprites/background presets without external game-engine dependency.
