# Distilled TI Unified Assessment Core Architecture

> Status: proposed architecture baseline
>
> Scope: backend, frontend, Story/Galgame, Senren, and AI Chat support-signal integration
>
> Principle: one assessment core, multiple input adapters, multiple product experiences, one report/evolution system.

## 1. Purpose

Distilled TI should not evolve into three separate personality systems. The product goal is to offer three assessment experiences while keeping one shared personality assessment core:

- Standard question assessment.
- Story / Galgame hidden-choice assessment.
- AI Chat context support-signal assessment.

The correct architecture is:

```text
User interaction
  -> Mode Adapter
  -> AssessmentSignal
  -> Assessment Core
  -> SessionState / UserState / Evidence
  -> Report / Map / History / Evolution / Support Signals
```

The user-facing modes can look very different. The measurement kernel must remain shared.

## 2. Product Boundary

Distilled TI is a continuous behavior-tendency mapping system. It is not:

- a clinical diagnosis tool
- a hiring or screening tool
- a one-shot immutable personality classifier
- an automated high-stakes decision system

The system estimates behavior tendencies in a fixed coordinate space, tracks uncertainty, preserves evidence, and translates state into readable labels and reports.

The labels are explanation, not measurement itself.

## 3. Current Repository Map

### Main Product

```text
backend/
  FastAPI backend for assessment, users, reports, admin, story, vectors, and context signals.

frontend/
  Main Next.js frontend for standard assessment, Story, Senren, reports, history, evolution, profile, and admin.
```

### External Demo

```text
ai-chat-support-demo/
  External integration demo for chat-context support-signal APIs.

ai-chat-support-demo/nextchat/
  Upstream NextChat-based demo. This is not the main product frontend.
```

### Product Knowledge And Planning

```text
docs/
  Development guide, logs, API notes, plans, and architecture records.

Distilled_TI_Architecture_v1.md
  Existing theory and early implementation architecture.

item_bank_rewrite_v1.md
  Item-bank and rewrite design notes.

skills/
  Character/persona skill content used by Senren/story enrichment.
```

## 4. Target Logical Layers

### 4.1 Assessment Core

The Assessment Core is the only layer that owns personality-state updates.

Responsibilities:

- Own the fixed core coordinate system.
- Maintain `SessionState` and future long-lived `UserState`.
- Update core dimensions, subdimensions, module scores, uncertainty, and zeta signals.
- Preserve evidence and confidence.
- Produce report-ready state.
- Stay usable when LLM, embedding, reranker, vector search, or image generation is unavailable.

Current implementation anchors:

- `backend/app/domain/dimensions.py`
- `backend/app/domain/models.py`
- `backend/app/services/scoring.py`
- `backend/app/services/reporting.py`
- `backend/app/services/clustering.py`
- `backend/app/services/storage.py`

The core should not know whether a signal came from a standard item, a visual novel choice, a Senren game choice, or a chat transcript.

### 4.2 Input Adapters

Adapters translate mode-specific user behavior into a shared assessment signal.

Adapters do not own personality rules. They only normalize input and attach confidence/evidence.

Required adapters:

```text
standard_question_adapter
story_choice_adapter
story_free_text_adapter
senren_choice_adapter
chat_context_adapter
```

Current implementation anchors:

- Standard question: `session_service.py`, `scoring.py`
- Story/Galgame: `session_service.py`, `generation.py`, `ai_service.py`, `galgame_asset_service.py`
- Senren: `senren_monitor_service.py`, `senren_choice_tree.py`, `senren_dimension_mapping.py`
- AI Chat context: `context_analysis_service.py`

### 4.3 Application Services

Application services orchestrate sessions, users, persistence, AI provider settings, vectors, assets, and admin actions.

Responsibilities:

- Start/resume/delete sessions.
- Issue and validate access tokens.
- Manage users, invites, history, and evolution.
- Store evidence, reports, turns, templates, and context-analysis records.
- Call the Assessment Core through adapter outputs.
- Keep optional services optional.

Current implementation anchors:

- `backend/app/services/session_service.py`
- `backend/app/services/user_service.py`
- `backend/app/services/ai_service.py`
- `backend/app/services/vector_indexer.py`
- `backend/app/services/embedding_service.py`
- `backend/app/services/reranker_service.py`
- `backend/app/services/galgame_asset_service.py`
- `backend/app/services/context_analysis_service.py`

### 4.4 API Layer

The API layer should only translate HTTP requests/responses and enforce authentication/authorization.

It should not contain measurement logic.

Current API groups:

- Public API: `backend/app/api/routes.py`
- Admin API: `backend/app/api/admin_routes.py`
- Senren API: `backend/app/api/senren_routes.py`
- Shared schemas: `backend/app/api/schemas.py`

### 4.5 Frontend Experiences

The frontend is a set of product experiences over the same backend state.

Expected experiences:

```text
/
  Product entry and mode selection.

/session
  Standard question assessment.

/story
  Generic Story / Galgame assessment.

/senren
  Senren-specific assessment experience.

/report
  Unified report entry.

/history
  Session history.

/evolution
  Long-term evolution.

/profile
  User profile, invites, and social/recommendation controls.

/admin
  Admin configuration, item bank, AI provider, vectors, templates, assets.
```

Frontend pages and components should not implement assessment rules. They should call typed API clients and render returned state.

## 5. AssessmentSignal

The missing architectural concept is a shared signal object.

All assessment modes should eventually produce `AssessmentSignal` before any state update.

Proposed shape:

```text
AssessmentSignal
  signal_id: string
  session_id: string
  user_id?: string

  source_mode:
    standard_question
    story_choice
    story_free_text
    senren_choice
    chat_context

  source_id: string
    item_id / scene_id / choice_id / conversation_id / message_window_id

  source_ref?: object
    template_id, story_template_id, turn_id, route_id, external app id, etc.

  observed_score?: number
    normalized behavior score consumed by the core.

  core_dimension_weights: Record<string, number>
  subdimension_weights: Record<string, number>
  module_affinities: Record<string, number>

  confidence: number
    0.0 to 1.0 confidence in the adapter mapping.

  evidence:
    visible_text?: string
    hidden_prompt_ref?: string
    selected_option_key?: string
    selected_option_text?: string
    custom_text_excerpt?: string
    chat_excerpt_window?: string[]
    inference_reason?: string

  timing:
    latency_ms?: number
    created_at: datetime

  safety_flags:
    non-diagnostic support/risk signal references.

  adapter_version: string
  diagnostic: false
```

The initial implementation can be smaller, but the architecture should assume this model.

## 6. Mode-Specific Rules

### 6.1 Standard Question Assessment

Role:

- Primary structured assessment path.
- Highest default confidence.
- Best source for early baseline estimation.

Input:

- item instance
- option key
- latency
- item weights and option scores

Adapter output:

- `source_mode = standard_question`
- high confidence, typically `0.85` to `1.0`
- direct `observed_score`
- direct dimension weights

Core behavior:

- Updates `SessionState.core_mu`, `core_sigma`, subdimensions, modules, zeta, answer history.

### 6.2 Story / Galgame Assessment

Role:

- Natural, lower-friction assessment experience.
- Hides measurement scaffolding behind story choices.
- Preserves visible narrative evidence.

Input:

- current hidden item instance
- generated or fallback scene
- story choices
- optional custom player text
- classifier output for free text

Adapter output:

- `source_mode = story_choice` or `story_free_text`
- medium confidence
- selected/inferred option key
- visible scene and choice evidence
- inference reason for free text

Core behavior:

- Uses the same state update path as standard questions.
- Applies confidence-aware update once supported.
- Stores `GalgameTurn` as experience evidence, not as a separate personality state.

### 6.3 Senren Assessment

Role:

- A specific product experience built on top of the same core.
- Maps game choices and route context into Distilled TI dimensions.

Input:

- Senren choice id
- selected option
- route context
- optional local game asset state

Adapter output:

- `source_mode = senren_choice`
- medium confidence
- mapped item-like weights
- game-specific evidence and route metadata

Core behavior:

- Should use Assessment Core state updates.
- Senren-specific narrative labels are presentation overrides, not separate measurement logic.

### 6.4 AI Chat Context Assessment

Role:

- External or internal chat context analysis.
- Product safety and support-signal layer.
- Longitudinal auxiliary evidence.

Input:

- authorized chat messages
- external user id
- conversation id
- consent basis
- metadata

Adapter output:

- `source_mode = chat_context`
- support/risk signals
- evidence window
- optional long-term tendency signals

Core behavior:

- By default, chat context should not strongly update personality core dimensions.
- Chat signals should first feed support/risk evidence and longitudinal trend records.
- Any future personality-state update from chat must be explicit, confidence-gated, and auditable.

## 7. Confidence Policy

Different modes should not have equal measurement weight.

Recommended defaults:

```text
standard_question: 0.85 - 1.00
story_choice:      0.55 - 0.80
story_free_text:   0.35 - 0.75
senren_choice:     0.50 - 0.80
chat_context:      0.20 - 0.65 for trend evidence, not direct core updates by default
```

The scoring engine should eventually accept signal confidence and use it to scale update strength.

Until then, adapter confidence should still be persisted as evidence so future reports can explain why some conclusions are stronger than others.

## 8. Evidence Model

Every state update should be explainable.

Evidence should answer:

- What did the user see?
- What did the user do?
- How was it mapped?
- What confidence did the adapter assign?
- Which dimensions were affected?
- Was any safety/support signal detected?
- Which adapter version produced the mapping?

Evidence is not only for debugging. It is needed for:

- report transparency
- user trust
- regression testing
- future recalibration
- safety review

Existing evidence carriers:

- `AnswerRecord`
- `GalgameTurn`
- `ContextAnalysisRecord`
- item instances
- vector sync records

Future direction:

- Introduce a unified `AssessmentSignalRecord` table/model.
- Keep mode-specific records as richer source evidence.

## 9. Reporting Architecture

Reports should be mode-agnostic.

A report should read from:

- current state
- uncertainty
- subdimension unlocks
- module scores
- cluster memberships
- evidence summary
- support/risk flags
- optional AI interpretation

Reports should not ask:

- Did this come from `/session` or `/story`?
- Was this a Senren scene or a generic scene?
- Was this a NextChat conversation?

Instead, reports can show evidence provenance:

```text
Evidence mix:
  70% structured question evidence
  20% story choice evidence
  10% chat support trend evidence
```

This helps users understand confidence without splitting the product into separate reports.

## 10. API Architecture

### Current Operational Ports

```text
Public backend: http://127.0.0.1:8000
Admin backend:  http://127.0.0.1:8001
Frontend:       http://127.0.0.1:3000
```

### Current API Groups

```text
/api/session/*
/api/question/*
/api/response/*
/api/user/*
/api/context/*
/api/admin/*
/api/senren/*
```

### Target Conceptual Groups

The URL structure does not have to change immediately, but the conceptual ownership should be:

```text
Assessment APIs
  start session, next item, submit signal/answer, summary, report, map

Story Adapter APIs
  scene generation, story response, story templates

Chat Context Adapter APIs
  context analyze, context history, context alerts

Senren Adapter APIs
  monitor start, choice, live state, route, VN scene, report

User APIs
  invite, profile, sessions, evolution, recommendations

Admin APIs
  AI config, templates, vectors, clusters, assets, cleanup
```

### API Rule

API handlers should:

- validate request payloads
- enforce access tokens
- call services
- return schema responses

API handlers should not:

- update personality dimensions directly
- parse LLM output directly
- duplicate scoring logic
- duplicate adapter mapping rules

## 11. Frontend Architecture

### Current Main Frontend

The main frontend already has a central API client:

- `frontend/lib/api.ts`
- `frontend/lib/runtime-store.ts`

This should become the only normal path for backend access.

### Required Frontend Direction

Rules:

- Pages own routing and layout.
- Components own interaction and rendering.
- `lib/api.ts` or a sibling API module owns HTTP calls.
- `runtime-store.ts` owns local access bundles.
- No page should hardcode backend URLs when a shared API client can be used.
- No component should implement assessment mapping logic.

### Senren Frontend Note

Senren pages currently contain direct `fetch` calls and separate session storage usage.

Target:

- Move Senren HTTP calls into a typed API client.
- Keep Senren experience-specific UI in Senren components.
- Keep tokens and session access handling consistent with the rest of the app.

## 12. AI, Embedding, Vector, And Asset Layers

These are enhancement layers, not the core.

### AI Service

Used for:

- report interpretation
- story scene generation
- question rewriting
- free-text classification
- context analysis

Rule:

- AI output must be validated.
- AI failure must fall back safely.
- AI must not become the only source of measurement truth.

### Embedding And Vector Indexing

Used for:

- similar item retrieval
- duplicate avoidance
- session similarity
- story turn retrieval
- context semantic anchors

Rule:

- Vector search improves quality and evidence.
- It must not be required for basic assessment flow.

### Galgame Assets

Used for:

- background and character visuals
- generated or fallback assets
- Senren local asset integration

Rule:

- Asset generation is presentation, not measurement.
- Asset failure should not block assessment.

## 13. NextChat Demo Boundary

`ai-chat-support-demo/nextchat` is an external integration demo.

It should not be treated as the main product frontend.

Purpose:

- show how a chat product can call Distilled TI context APIs
- keep context API key server-side
- show support-admin alert review

Not its purpose:

- define the main product architecture
- block main frontend releases
- own personality-state updates

Quality gates for the main product should not depend on upstream NextChat lint/test health.

Quality gates for the demo can be separate:

- install
- build
- context route smoke
- support-admin smoke

## 14. Testing And Quality Gates

### Main Backend

Required:

```powershell
cd backend
python -m pytest
```

Recommended:

- tests should use isolated local SQLite databases
- no test should depend on `backend/distilled_ti_local.db`
- adapter tests should assert produced signal shape and confidence
- core tests should assert state update behavior independently from UI modes

### Main Frontend

Required:

```powershell
cd frontend
npm run lint
npm run build
npm audit
```

### Demo

Recommended separately:

```powershell
cd ai-chat-support-demo
python -m py_compile server.py

cd nextchat
npm install --ignore-scripts --legacy-peer-deps --package-lock=false
npm run build
```

Known demo tooling should not block main product work unless the current task explicitly targets the demo.

## 15. Migration Plan

### Phase 1: Document And Freeze Boundaries

Goals:

- Adopt this architecture as the baseline.
- Mark main product and demo boundaries.
- Document current API groups.
- Add development-log entries for every architecture or implementation pass.

No large code movement.

### Phase 2: Introduce AssessmentSignal Internally

Goals:

- Add a domain model for assessment signals.
- Convert standard question submission into a signal before scoring.
- Persist enough signal evidence for reports and debugging.

External API can remain unchanged.

Current status:

- `AssessmentSignal` has been introduced as an internal domain model.
- `ScoringEngine.apply_signal()` is the shared scoring-core entrypoint.
- `ScoringEngine.apply_response()` remains as a compatibility wrapper that builds a signal before applying it.
- Standard question submission, Story/Galgame response submission, and Senren choice submission now carry source-mode metadata into the scoring core.
- Signal confidence is recorded on the internal signal, but update strength is not confidence-scaled yet.

### Phase 3: Route Story And Senren Through Signals

Goals:

- Convert story choices and free text into signals.
- Convert Senren game choices into signals.
- Keep mode-specific evidence records.
- Ensure all state updates use Assessment Core.

### Phase 4: Confidence-Aware Scoring

Goals:

- Update scoring to accept signal confidence.
- Scale update strength by confidence.
- Preserve existing behavior for high-confidence standard questions.

### Phase 5: Unified Evidence-Aware Reports

Goals:

- Add evidence provenance to reports.
- Show mode mix and confidence summary.
- Keep report output unified across all experiences.

### Phase 6: Frontend API Consolidation

Goals:

- Move direct fetch calls into typed API modules.
- Normalize token handling.
- Normalize error handling.
- Keep pages as experiences only.

### Phase 7: Demo Hardening

Goals:

- Treat NextChat as an external integration.
- Fix demo-specific lint/test/build issues only when demo work is in scope.
- Avoid letting demo dependency churn affect the main app.

## 16. Development Rules Going Forward

Every new feature should answer:

- Which layer owns this?
- Is this core logic, adapter logic, service orchestration, API transport, or UI experience?
- Does it create or consume `AssessmentSignal`?
- Does it preserve evidence and confidence?
- Does it affect main product, demo, or both?
- Which documentation and development-log entry must be updated?

Default rule:

```text
No new assessment path may update personality state without going through the Assessment Core.
```

## 17. Summary

The correct architecture is not to remove the three assessment modes. The correct architecture is to make them input adapters over one shared core.

Distilled TI should evolve toward:

```text
One core coordinate system
One assessment state model
One signal pipeline
Three input adapters
Multiple product experiences
One report/history/evolution system
```

This preserves the product vision while preventing the codebase from becoming three unrelated products in one repository.
