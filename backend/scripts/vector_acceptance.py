"""Run a live vector-layer acceptance smoke test.

This script reads backend settings from environment variables or backend/.env.
It does not print API keys.
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.domain.item_bank import build_seed_item_bank
from app.core.config import settings
from app.services.embedding_service import embedding_service
from app.services.reranker_service import reranker_service
from app.services.storage import local_session_store
from app.services.vector_indexer import vector_indexer
from app.services.vector_store import vector_store


def _has_real_key(value: str) -> bool:
    normalized = value.strip()
    return bool(normalized and normalized != "your_siliconflow_key")


def _is_siliconflow_url(value: str) -> bool:
    return "siliconflow" in value.lower()


def _print_summary(name: str, payload: object) -> None:
    print(f"{name}: {payload}")


def main() -> int:
    _print_summary("vector_enabled", vector_indexer.is_enabled())
    if not vector_indexer.is_enabled():
        print("vector layer is not enabled; check backend/.env")
        return 2

    embedding_key_configured = _has_real_key(settings.embedding_api_key)
    _print_summary("embedding_api_key_configured", embedding_key_configured)
    if _is_siliconflow_url(settings.embedding_base_url) and not embedding_key_configured:
        print("SiliconFlow embedding requires a real EMBEDDING_API_KEY in backend/.env")
        return 2

    reranker_key = settings.reranker_api_key or settings.embedding_api_key
    reranker_key_configured = _has_real_key(reranker_key)
    _print_summary("reranker_api_key_configured", reranker_key_configured)
    if _is_siliconflow_url(settings.reranker_base_url or settings.embedding_base_url) and not reranker_key_configured:
        print("SiliconFlow reranker requires a real RERANKER_API_KEY or EMBEDDING_API_KEY in backend/.env")
        return 2

    vectors = embedding_service.embed_texts(["Distilled TI vector acceptance smoke test"])
    _print_summary("embedding_dimension", len(vectors[0]) if vectors else 0)

    _print_summary("reranker_enabled", reranker_service.is_enabled())
    if reranker_service.is_enabled():
        reranked = reranker_service.rerank(
            "measurement-preserving rewrite",
            [
                "A candidate that keeps the same measurement direction.",
                "A candidate that changes the construct completely.",
            ],
            top_n=2,
        )
        _print_summary("reranker_top_index", reranked[0].index if reranked else None)

    for scope in ("templates", "instances", "sessions"):
        summary = vector_indexer.reindex(scope)  # type: ignore[arg-type]
        _print_summary(
            f"reindex_{scope}",
            {
                "enabled": summary.enabled,
                "indexed": summary.indexed_count,
                "failed": summary.failed_count,
                "failure_ids": summary.failure_ids[:3],
            },
        )

    template = build_seed_item_bank()[0]
    hits = vector_indexer.search_similar_templates(template=template, top_k=3)
    _print_summary(
        "similar_templates",
        [
            {
                "object_id": hit.object_id,
                "score": hit.score,
                "rerank_score": hit.rerank_score,
            }
            for hit in hits
        ],
    )

    sessions = local_session_store.list_session_records(limit=1)
    if sessions:
        session_hits = vector_indexer.search_similar_sessions(sessions[0], top_k=3)
        _print_summary(
            "similar_sessions",
            [
                {
                    "session_id": hit.session_id,
                    "milestone": hit.snapshot_milestone,
                    "score": hit.score,
                    "rerank_score": hit.rerank_score,
                }
                for hit in session_hits
            ],
        )
    else:
        _print_summary("similar_sessions", "skipped_no_sessions")

    failures = local_session_store.list_vector_sync_failures(limit=5)
    _print_summary("recent_failures", len(failures))
    for failure in failures[:3]:
        _print_summary(
            "failure",
            {
                "object_type": failure.object_type,
                "operation": failure.operation,
                "object_id": failure.object_id,
                "error": failure.error_message[:160],
            },
        )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        vector_store.close()
