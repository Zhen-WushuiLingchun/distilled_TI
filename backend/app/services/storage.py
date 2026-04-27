"""Local SQLite persistence for ephemeral sessions."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.core.config import settings
from app.domain.models import (
    ClusterLabelOverride,
    ClusterVersionInfo,
    ItemInstance,
    ItemTemplate,
    SessionHistoryEntry,
    SessionRecord,
    VectorSyncFailure,
)


class LocalSessionStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                )
                """
            )
            columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(sessions)").fetchall()
            }
            if "created_at" not in columns:
                connection.execute("ALTER TABLE sessions ADD COLUMN created_at TEXT")
            if "updated_at" not in columns:
                connection.execute("ALTER TABLE sessions ADD COLUMN updated_at TEXT")
            if "expires_at" not in columns:
                connection.execute("ALTER TABLE sessions ADD COLUMN expires_at TEXT")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS item_instances (
                    instance_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    template_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS item_templates (
                    template_id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS cluster_versions (
                    version TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS cluster_label_overrides (
                    version TEXT NOT NULL,
                    cluster_index INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (version, cluster_index)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS ai_provider_config (
                    config_key TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS vector_sync_failures (
                    failure_id TEXT PRIMARY KEY,
                    object_type TEXT NOT NULL,
                    object_id TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    error_message TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.commit()

    def save_session(self, record: SessionRecord) -> None:
        now = datetime.now(UTC)
        expires_at = now + timedelta(hours=settings.session_ttl_hours)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO sessions (session_id, status, payload_json, created_at, updated_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    status = excluded.status,
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at,
                    expires_at = excluded.expires_at
                """,
                (
                    record.session_id,
                    record.status,
                    record.model_dump_json(),
                    record.created_at.isoformat(),
                    now.isoformat(),
                    expires_at.isoformat(),
                ),
            )
            connection.commit()

    def load_session(self, session_id: str) -> SessionRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        return SessionRecord.model_validate_json(row[0])

    def save_item_instance(self, instance: ItemInstance) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO item_instances (instance_id, session_id, template_id, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(instance_id) DO UPDATE SET
                    payload_json = excluded.payload_json
                """,
                (
                    instance.id,
                    instance.session_id,
                    instance.template_id,
                    instance.model_dump_json(),
                    instance.created_at.isoformat(),
                ),
            )
            connection.commit()

    def load_item_instance(self, instance_id: str) -> ItemInstance | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM item_instances WHERE instance_id = ?",
                (instance_id,),
            ).fetchone()
        if row is None:
            return None
        return ItemInstance.model_validate_json(row[0])

    def save_template(self, template: ItemTemplate) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO item_templates (template_id, payload_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(template_id) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (template.id, template.model_dump_json(), datetime.now(UTC).isoformat()),
            )
            connection.commit()

    def load_templates(self) -> list[ItemTemplate]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload_json FROM item_templates ORDER BY updated_at DESC",
            ).fetchall()
        return [ItemTemplate.model_validate_json(row[0]) for row in rows]

    def delete_template(self, template_id: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM item_templates WHERE template_id = ?", (template_id,))
            connection.commit()

    def list_item_instances(self, session_id: str | None = None, limit: int | None = 100) -> list[ItemInstance]:
        with self._connect() as connection:
            if session_id:
                query = "SELECT payload_json FROM item_instances WHERE session_id = ? ORDER BY created_at DESC"
                params: tuple[object, ...] = (session_id,)
                if limit is not None:
                    query += " LIMIT ?"
                    params = (session_id, limit)
                rows = connection.execute(query, params).fetchall()
            else:
                query = "SELECT payload_json FROM item_instances ORDER BY created_at DESC"
                params = ()
                if limit is not None:
                    query += " LIMIT ?"
                    params = (limit,)
                rows = connection.execute(query, params).fetchall()
        return [ItemInstance.model_validate_json(row[0]) for row in rows]

    def list_sessions(self) -> list[SessionHistoryEntry]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT session_id, payload_json, status, created_at, updated_at
                FROM sessions
                ORDER BY updated_at DESC
                LIMIT 100
                """
            ).fetchall()
        entries: list[SessionHistoryEntry] = []
        for session_id, payload_json, status, created_at, updated_at in rows:
            record = SessionRecord.model_validate_json(payload_json)
            resolved_created_at = (
                datetime.fromisoformat(created_at)
                if isinstance(created_at, str) and created_at
                else record.created_at
            )
            resolved_updated_at = (
                datetime.fromisoformat(updated_at)
                if isinstance(updated_at, str) and updated_at
                else record.updated_at
            )
            entries.append(
                SessionHistoryEntry(
                    session_id=session_id,
                    status=status,
                    question_count=record.state.question_count,
                    can_generate_report=record.state.question_count >= settings.min_questions_for_report,
                    created_at=resolved_created_at,
                    updated_at=resolved_updated_at,
                )
            )
        return entries

    def list_session_records(self, limit: int | None = 100) -> list[SessionRecord]:
        query = "SELECT payload_json FROM sessions ORDER BY updated_at DESC"
        params: tuple[object, ...] = ()
        if limit is not None:
            query += " LIMIT ?"
            params = (limit,)
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [SessionRecord.model_validate_json(row[0]) for row in rows]

    def cleanup_expired(self) -> int:
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            expired_session_ids = [
                row[0]
                for row in connection.execute(
                    "SELECT session_id FROM sessions WHERE expires_at <= ?",
                    (now,),
                ).fetchall()
            ]
            if expired_session_ids:
                placeholders = ",".join("?" for _ in expired_session_ids)
                connection.execute(
                    f"DELETE FROM item_instances WHERE session_id IN ({placeholders})",
                    expired_session_ids,
                )
                connection.execute(
                    f"DELETE FROM sessions WHERE session_id IN ({placeholders})",
                    expired_session_ids,
                )
            connection.commit()
        return len(expired_session_ids)

    def delete_session(self, session_id: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM item_instances WHERE session_id = ?", (session_id,))
            connection.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            connection.commit()

    def save_cluster_version(self, version: ClusterVersionInfo) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO cluster_versions (version, payload_json, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(version) DO UPDATE SET
                    payload_json = excluded.payload_json
                """,
                (version.version, version.model_dump_json(), version.created_at.isoformat()),
            )
            connection.commit()

    def list_cluster_versions(self) -> list[ClusterVersionInfo]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload_json FROM cluster_versions ORDER BY created_at DESC LIMIT 30",
            ).fetchall()
        return [ClusterVersionInfo.model_validate_json(row[0]) for row in rows]

    def save_cluster_label_override(self, override: ClusterLabelOverride) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO cluster_label_overrides (version, cluster_index, payload_json, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(version, cluster_index) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (
                    override.version,
                    override.cluster_index,
                    override.model_dump_json(),
                    override.updated_at.isoformat(),
                ),
            )
            connection.commit()

    def list_cluster_label_overrides(self, version: str | None = None) -> list[ClusterLabelOverride]:
        with self._connect() as connection:
            if version:
                rows = connection.execute(
                    "SELECT payload_json FROM cluster_label_overrides WHERE version = ? ORDER BY cluster_index ASC",
                    (version,),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT payload_json FROM cluster_label_overrides ORDER BY updated_at DESC",
                ).fetchall()
        return [ClusterLabelOverride.model_validate_json(row[0]) for row in rows]

    def save_ai_provider_config(self, payload_json: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO ai_provider_config (config_key, payload_json, updated_at)
                VALUES ('default', ?, ?)
                ON CONFLICT(config_key) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (payload_json, datetime.now(UTC).isoformat()),
            )
            connection.commit()

    def load_ai_provider_config(self) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM ai_provider_config WHERE config_key = 'default'",
            ).fetchone()
        if row is None:
            return None
        return str(row[0])

    def save_vector_sync_failure(self, failure: VectorSyncFailure) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO vector_sync_failures (
                    failure_id,
                    object_type,
                    object_id,
                    operation,
                    error_message,
                    payload_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    failure.failure_id,
                    failure.object_type,
                    failure.object_id,
                    failure.operation,
                    failure.error_message,
                    failure.model_dump_json(),
                    failure.created_at.isoformat(),
                ),
            )
            connection.commit()

    def list_vector_sync_failures(self, limit: int = 25) -> list[VectorSyncFailure]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT failure_id, object_type, object_id, operation, error_message, payload_json, created_at
                FROM vector_sync_failures
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        failures: list[VectorSyncFailure] = []
        for failure_id, object_type, object_id, operation, error_message, payload_json, created_at in rows:
            try:
                failures.append(VectorSyncFailure.model_validate_json(payload_json))
            except Exception:
                failures.append(
                    VectorSyncFailure(
                        failure_id=str(failure_id),
                        object_type=str(object_type),
                        object_id=str(object_id),
                        operation=str(operation),
                        error_message=str(error_message),
                        payload_json=str(payload_json),
                        created_at=datetime.fromisoformat(created_at),
                    )
                )
        return failures


local_session_store = LocalSessionStore(settings.local_db_path)
