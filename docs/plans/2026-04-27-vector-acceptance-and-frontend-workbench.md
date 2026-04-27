# Plan: Vector Acceptance And Frontend Workbench

- Date: 2026-04-27
- Status: Phase 1/2 live acceptance complete; frontend workbench pending
- Scope: close Phase 1/2 vector acceptance first, then upgrade the user-facing session frontend from a question loop into a workbench.

## Current Status

- Phase 1 `item_vectors` is implemented and live-tested for templates, generated item instances, and rewrite candidates.
- Phase 2 `session_vectors` is implemented and live-tested for milestone session snapshots.
- Reranker is implemented and live-tested in the retrieval layer as a second-stage rerank step for similar templates, rewrite evidence, and similar sessions.
- Admin APIs and Admin UI expose reindex, similar templates, similar sessions, sync failures, and rewrite retrieval evidence.
- DeepSeek provider acceptance is implemented and live-tested with `deepseek-v4-pro`.
- SiliconFlow vector acceptance is implemented and live-tested with `BAAI/bge-m3` and `BAAI/bge-reranker-v2-m3`.
- The SiliconFlow API key must stay in local environment files only and must not be committed.

## Live Acceptance Record

- Date: 2026-04-27
- DeepSeek model: `deepseek-v4-pro`
- Embedding model: `BAAI/bge-m3`
- Embedding dimension: `1024`
- Reranker model: `BAAI/bge-reranker-v2-m3`
- Qdrant mode: local embedded storage through `QDRANT_LOCAL_PATH=.qdrant-local`
- `templates` reindex: `123` indexed, `0` failed
- `instances` reindex: `8` indexed, `0` failed
- `sessions` reindex: `0` indexed, `0` failed because no milestone session snapshots existed locally
- Similar template query returned stable hits with both embedding scores and rerank scores
- `vector_sync_failures`: `0` after fixing Qdrant point id handling

Fix discovered during live acceptance:

- Qdrant local mode requires UUID-compatible point IDs.
- Business IDs are now mapped to stable UUIDs before Qdrant write.
- Original business IDs remain in payload metadata.

## Qdrant Decision

- Qdrant gives us a real ANN vector index, payload filtering, collection separation, upsert/delete semantics, and inspectable local state.
- The concrete value is not just storing vectors; it is stable nearest-neighbor retrieval with metadata filters such as object type, layer, dimensions, milestones, and archived status.
- Windows does not require Docker for this repo now. Local dev can use embedded Qdrant storage through `QDRANT_LOCAL_PATH=.qdrant-local`.
- Docker Qdrant remains a valid option when we want behavior closer to deployment, HTTP inspection on `6333`, or shared state across processes.
- Replacements are possible, but each has tradeoffs. SQLite vector extensions reduce infrastructure but add native extension packaging risk on Windows. FAISS is fast but does not give us first-class payload filtering and service-style operations. Postgres/pgvector is a good production alternative if the app later moves to Postgres.
- Current decision: keep Qdrant as the vector store abstraction target, use `QDRANT_LOCAL_PATH` for Windows local acceptance, and keep the service wrapper thin enough to swap later if needed.

## Reranker Scope

- Reranker is now used after embedding retrieval, not as a replacement for embedding search.
- Reranker improves hit ordering for small top-k evidence sets where embedding similarity alone can return semantically adjacent but measurement-wrong neighbors.
- Reranker does not take over core scoring, item selection, cluster assignment, or report logic.
- This keeps the measurement model deterministic while still improving retrieval evidence quality.

## Phase 1/2 Acceptance Steps

- Create `backend/.env` from `backend/.env.example`.
- Set `EMBEDDING_API_KEY` and `RERANKER_API_KEY` locally.
- Use `EMBEDDING_MODEL=BAAI/bge-m3`.
- Use `RERANKER_MODEL=BAAI/bge-reranker-v2-m3`.
- Prefer `QDRANT_LOCAL_PATH=.qdrant-local` on Windows if Docker is not already running.
- Run `cd backend`.
- Run `python scripts/vector_acceptance.py`.
- Confirm `vector_enabled: True`.
- Confirm embedding dimension is non-zero.
- Confirm reranker is enabled and returns a top index.
- Confirm `templates`, `instances`, and `sessions` reindex complete without failures.
- Confirm similar templates return meaningful hits.
- Confirm similar sessions returns hits when local sessions exist.
- Confirm recent vector sync failures are empty.

## Acceptance Gates Before More Feature Work

- Done: Reindex returned `enabled=true` and `failed=0` for templates.
- Done: Reindex returned `enabled=true` and `failed=0` for instances.
- Done: Reindex returned `enabled=true` and `failed=0` for sessions, with no local milestone sessions present.
- Done: Similar templates returned meaningful hits and rerank scores.
- Done: `vector_sync_failures` was empty after the final acceptance run.
- Pending manual UI check: rewrite preview retrieval context in Admin UI.
- Pending manual quality check: selected rewrite candidates should not show obvious near-duplicates or measurement-direction drift.

## Frontend Workbench Timing

- The frontend should be upgraded now that vector acceptance has passed, and before `cluster_vectors`.
- Reason: the next frontend version should consume retrieval evidence, session milestones, and similar-session context that now exist in the backend.
- This is more valuable than adding another vector collection first, because the current user experience still hides most of the system intelligence.

## Frontend Workbench Target

- Replace the current public question-only loop with a session workbench.
- Keep the current answer flow fast, but add context around it instead of making the user stare at one isolated question.
- Show a "why this question" panel based on active dimension, uncertainty, coverage, scenario, and retrieval evidence.
- Show a live profile panel with top changing dimensions, uncertainty, active modules, and unlocked subdimensions.
- Show a trajectory panel with recent answers, direction changes, and milestone markers.
- Show a checkpoint panel at 5, 10, 20, and 40 questions with a short state summary.
- Show a report preview once enough evidence exists, without forcing the user to finish a long questionnaire first.
- Keep the admin vector panel separate from the user-facing session workbench.

## Frontend Workbench Implementation Slices

- Slice 1: restructure the session page into question, live profile, trajectory, and evidence panels without changing scoring behavior.
- Slice 2: add checkpoint cards at session vector milestones and expose the snapshot summary to the UI.
- Slice 3: add "similar sessions" and "similar evidence" as an optional insight drawer for internal/admin-facing validation first.
- Slice 4: add report preview and user-facing narrative summary after the minimum report threshold.
- Slice 5: revisit visual design so the product feels like an adaptive assessment cockpit, not a form wizard.

## Not In This Step

- Do not add `cluster_vectors` yet.
- Do not make reranker control scoring or item selection.
- Do not expose raw vector scores as user-facing truth.
- Do not write SiliconFlow keys into repo files.
- Do not add a background worker until manual reindex and best-effort writes prove insufficient.

## Immediate Next Step

- Build Session Workbench slice 1.
- Keep the public answer flow compatible with existing session APIs.
- Add UI panels for live profile, question rationale, trajectory, and report readiness.
- Use existing backend fields first; only add API fields where the UI cannot derive the state safely.
- Keep vector evidence user-facing only as explanation support, not as a final judgment.
