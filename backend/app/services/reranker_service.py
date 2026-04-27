"""SiliconFlow-compatible reranker helpers."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.core.config import settings


class RerankerServiceError(RuntimeError):
    """Raised when the reranker provider is unavailable."""


@dataclass(slots=True)
class RerankResult:
    index: int
    relevance_score: float


class RerankerService:
    def is_enabled(self) -> bool:
        return bool(
            settings.vector_enabled
            and self._base_url().strip()
            and settings.reranker_model.strip()
        )

    def rerank(self, query: str, documents: list[str], top_n: int | None = None) -> list[RerankResult]:
        normalized_query = query.strip()
        normalized_documents = [document.strip() for document in documents if document.strip()]
        if not normalized_query or not normalized_documents:
            return []
        if not self.is_enabled():
            raise RerankerServiceError("reranker_not_configured")

        headers = {"Content-Type": "application/json"}
        api_key = self._api_key()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload: dict[str, object] = {
            "model": settings.reranker_model,
            "query": normalized_query,
            "documents": normalized_documents,
            "top_n": min(top_n or len(normalized_documents), len(normalized_documents)),
            "return_documents": False,
        }

        try:
            with httpx.Client(timeout=settings.reranker_timeout_seconds, follow_redirects=False) as client:
                response = client.post(
                    f"{self._base_url().rstrip('/')}/rerank",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                body = response.json()
        except Exception as exc:  # pragma: no cover - exercised by tests via mocks
            raise RerankerServiceError(f"reranker_request_failed:{exc}") from exc

        results = body.get("results")
        if not isinstance(results, list):
            raise RerankerServiceError("reranker_response_missing_results")

        ranked: list[RerankResult] = []
        for item in results:
            try:
                ranked.append(
                    RerankResult(
                        index=int(item["index"]),
                        relevance_score=float(item["relevance_score"]),
                    )
                )
            except Exception as exc:  # pragma: no cover - defensive parsing
                raise RerankerServiceError(f"reranker_response_invalid_result:{exc}") from exc
        return ranked

    def _base_url(self) -> str:
        return settings.reranker_base_url or settings.embedding_base_url

    def _api_key(self) -> str:
        return settings.reranker_api_key or settings.embedding_api_key


reranker_service = RerankerService()
