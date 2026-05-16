"""Qdrant-backed vector store helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from qdrant_client import QdrantClient
from qdrant_client.http import models

from app.core.config import settings


class VectorStoreError(RuntimeError):
    """Raised when vector storage is unavailable."""


class VectorStore:
    def __init__(self) -> None:
        self._client: QdrantClient | None = None
        self._collection_ready: set[str] = set()

    def is_enabled(self) -> bool:
        return bool(
            settings.vector_enabled
            and (settings.qdrant_local_path.strip() or settings.qdrant_url.strip())
        )

    def upsert(
        self,
        point_id: str,
        vector: list[float],
        payload: dict[str, Any],
        *,
        collection_name: str | None = None,
    ) -> None:
        if not vector:
            raise VectorStoreError("empty_vector")
        client = self._client_or_raise()
        resolved_collection = self._resolve_collection_name(collection_name)
        self._ensure_collection(client, resolved_collection, len(vector))
        client.upsert(
            collection_name=resolved_collection,
            points=[models.PointStruct(id=self._point_id(point_id), vector=vector, payload=payload)],
            wait=True,
        )

    def delete_point(self, point_id: str, *, collection_name: str | None = None) -> None:
        client = self._client_or_raise()
        resolved_collection = self._resolve_collection_name(collection_name)
        if not client.collection_exists(resolved_collection):
            return
        client.delete(
            collection_name=resolved_collection,
            points_selector=models.PointIdsList(points=[self._point_id(point_id)]),
            wait=True,
        )

    def delete_by_filter(self, query_filter: models.Filter, *, collection_name: str | None = None) -> None:
        client = self._client_or_raise()
        resolved_collection = self._resolve_collection_name(collection_name)
        if not client.collection_exists(resolved_collection):
            return
        client.delete(
            collection_name=resolved_collection,
            points_selector=models.FilterSelector(filter=query_filter),
            wait=True,
        )

    def search(
        self,
        vector: list[float],
        *,
        limit: int,
        score_threshold: float | None = None,
        query_filter: models.Filter | None = None,
        collection_name: str | None = None,
    ) -> list[models.ScoredPoint]:
        try:
            client = self._client_or_raise()
            resolved_collection = self._resolve_collection_name(collection_name)
            if not client.collection_exists(resolved_collection):
                return []
            response = client.query_points(
                collection_name=resolved_collection,
                query=vector,
                limit=limit,
                with_payload=True,
                score_threshold=score_threshold,
                query_filter=query_filter,
            )
            return list(response.points)
        except VectorStoreError:
            raise
        except Exception as exc:  # pragma: no cover - defensive wrapper for qdrant client internals
            raise VectorStoreError(str(exc)) from exc

    def close(self) -> None:
        if self._client is None:
            return
        self._client.close()
        self._client = None
        self._collection_ready.clear()

    def _client_or_raise(self) -> QdrantClient:
        if not self.is_enabled():
            raise VectorStoreError("qdrant_not_configured")
        if self._client is None:
            try:
                if settings.qdrant_local_path.strip():
                    local_path = Path(settings.qdrant_local_path).expanduser()
                    local_path.mkdir(parents=True, exist_ok=True)
                    self._client = QdrantClient(
                        path=str(local_path),
                        force_disable_check_same_thread=True,
                    )
                else:
                    self._client = QdrantClient(
                        url=settings.qdrant_url,
                        api_key=settings.qdrant_api_key or None,
                        timeout=int(max(settings.embedding_timeout_seconds, 1)),
                    )
            except Exception as exc:  # pragma: no cover - qdrant local can raise plain RuntimeError on lock conflicts
                raise VectorStoreError(str(exc)) from exc
        return self._client

    def _ensure_collection(self, client: QdrantClient, collection_name: str, vector_size: int) -> None:
        if not isinstance(self._collection_ready, set):
            self._collection_ready = set()
        if collection_name in self._collection_ready and client.collection_exists(collection_name):
            return
        if not client.collection_exists(collection_name):
            client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=vector_size,
                    distance=models.Distance.COSINE,
                ),
            )
        self._collection_ready.add(collection_name)

    def _resolve_collection_name(self, collection_name: str | None) -> str:
        return collection_name or settings.qdrant_collection_item_vectors

    def _point_id(self, point_id: str) -> str:
        try:
            return str(UUID(point_id))
        except ValueError:
            return str(uuid5(NAMESPACE_URL, point_id))


vector_store = VectorStore()
