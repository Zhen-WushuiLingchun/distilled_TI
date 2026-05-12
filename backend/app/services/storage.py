"""Local SQLite persistence for ephemeral sessions."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.core.config import settings
from app.domain.models import (
    ClusterLabelOverride,
    ClusterVersionInfo,
    InviteCode,
    ItemInstance,
    ItemTemplate,
    SessionHistoryEntry,
    SessionRecord,
    UserProfile,
    UserRelationship,
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
            if "user_id" not in columns:
                connection.execute("ALTER TABLE sessions ADD COLUMN user_id TEXT")
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
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS user_profiles (
                    user_id TEXT PRIMARY KEY,
                    handle TEXT NOT NULL UNIQUE,
                    invite_code TEXT NOT NULL,
                    invited_by_user_id TEXT,
                    user_secret_hash TEXT NOT NULL,
                    relationship_opt_in INTEGER NOT NULL DEFAULT 0,
                    recommendation_opt_in INTEGER NOT NULL DEFAULT 0,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS invite_codes (
                    code TEXT PRIMARY KEY,
                    created_by_user_id TEXT,
                    label TEXT NOT NULL,
                    max_uses INTEGER NOT NULL,
                    use_count INTEGER NOT NULL,
                    active INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS user_relationships (
                    relationship_id TEXT PRIMARY KEY,
                    source_user_id TEXT NOT NULL,
                    target_user_id TEXT NOT NULL,
                    relationship_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            self._ensure_bootstrap_invite(connection)
            connection.commit()

    def _ensure_bootstrap_invite(self, connection: sqlite3.Connection) -> None:
        if not settings.invite_bootstrap_code:
            return
        row = connection.execute(
            "SELECT code FROM invite_codes WHERE code = ?",
            (settings.invite_bootstrap_code,),
        ).fetchone()
        if row is not None:
            return
        now = datetime.now(UTC)
        invite = InviteCode(
            code=settings.invite_bootstrap_code,
            label="Local bootstrap invite",
            max_uses=settings.invite_default_max_uses,
            created_at=now,
        )
        connection.execute(
            """
            INSERT INTO invite_codes (
                code,
                created_by_user_id,
                label,
                max_uses,
                use_count,
                active,
                payload_json,
                created_at,
                expires_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                invite.code,
                invite.created_by_user_id,
                invite.label,
                invite.max_uses,
                invite.use_count,
                int(invite.active),
                invite.model_dump_json(),
                invite.created_at.isoformat(),
                invite.expires_at.isoformat() if invite.expires_at else None,
            ),
        )

    def save_session(self, record: SessionRecord) -> None:
        now = datetime.now(UTC)
        if record.user_id:
            expires_at = now + timedelta(days=settings.registered_session_ttl_days)
        else:
            expires_at = now + timedelta(hours=settings.session_ttl_hours)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO sessions (session_id, status, user_id, payload_json, created_at, updated_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    status = excluded.status,
                    user_id = excluded.user_id,
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at,
                    expires_at = excluded.expires_at
                """,
                (
                    record.session_id,
                    record.status,
                    record.user_id,
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

    def list_sessions(self, user_id: str | None = None) -> list[SessionHistoryEntry]:
        with self._connect() as connection:
            if user_id:
                rows = connection.execute(
                    """
                    SELECT s.session_id, s.payload_json, s.status, s.created_at, s.updated_at, u.handle
                    FROM sessions s
                    LEFT JOIN user_profiles u ON s.user_id = u.user_id
                    WHERE s.user_id = ?
                    ORDER BY s.updated_at DESC
                    LIMIT 100
                    """,
                    (user_id,),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT s.session_id, s.payload_json, s.status, s.created_at, s.updated_at, u.handle
                    FROM sessions s
                    LEFT JOIN user_profiles u ON s.user_id = u.user_id
                    ORDER BY s.updated_at DESC
                    LIMIT 100
                    """
                ).fetchall()
        entries: list[SessionHistoryEntry] = []
        for session_id, payload_json, status, created_at, updated_at, user_handle in rows:
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
                    user_id=record.user_id,
                    user_handle=user_handle,
                    status=status,
                    question_count=record.state.question_count,
                    can_generate_report=record.state.question_count >= settings.min_questions_for_report,
                    created_at=resolved_created_at,
                    updated_at=resolved_updated_at,
                )
            )
        return entries

    def list_session_records(self, limit: int | None = 100, user_id: str | None = None) -> list[SessionRecord]:
        query = "SELECT payload_json FROM sessions ORDER BY updated_at DESC"
        params: tuple[object, ...] = ()
        if user_id is not None:
            query = "SELECT payload_json FROM sessions WHERE user_id = ? ORDER BY updated_at DESC"
            params = (user_id,)
        if limit is not None:
            query += " LIMIT ?"
            params = (*params, limit)
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

    def save_user_profile(self, profile: UserProfile) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO user_profiles (
                    user_id,
                    handle,
                    invite_code,
                    invited_by_user_id,
                    user_secret_hash,
                    relationship_opt_in,
                    recommendation_opt_in,
                    payload_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    handle = excluded.handle,
                    invite_code = excluded.invite_code,
                    invited_by_user_id = excluded.invited_by_user_id,
                    user_secret_hash = excluded.user_secret_hash,
                    relationship_opt_in = excluded.relationship_opt_in,
                    recommendation_opt_in = excluded.recommendation_opt_in,
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (
                    profile.user_id,
                    profile.handle,
                    profile.invite_code,
                    profile.invited_by_user_id,
                    profile.user_secret_hash,
                    int(profile.relationship_opt_in),
                    int(profile.recommendation_opt_in),
                    profile.model_dump_json(),
                    profile.created_at.isoformat(),
                    profile.updated_at.isoformat(),
                ),
            )
            connection.commit()

    def load_user_profile(self, user_id: str) -> UserProfile | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM user_profiles WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        if row is None:
            return None
        return UserProfile.model_validate_json(row[0])

    def load_user_by_handle(self, handle: str) -> UserProfile | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM user_profiles WHERE handle = ?",
                (handle,),
            ).fetchone()
        if row is None:
            return None
        return UserProfile.model_validate_json(row[0])

    def list_user_profiles(self, limit: int = 100) -> list[UserProfile]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT payload_json FROM user_profiles
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [UserProfile.model_validate_json(row[0]) for row in rows]

    def save_invite_code(self, invite: InviteCode) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO invite_codes (
                    code,
                    created_by_user_id,
                    label,
                    max_uses,
                    use_count,
                    active,
                    payload_json,
                    created_at,
                    expires_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(code) DO UPDATE SET
                    created_by_user_id = excluded.created_by_user_id,
                    label = excluded.label,
                    max_uses = excluded.max_uses,
                    use_count = excluded.use_count,
                    active = excluded.active,
                    payload_json = excluded.payload_json,
                    expires_at = excluded.expires_at
                """,
                (
                    invite.code,
                    invite.created_by_user_id,
                    invite.label,
                    invite.max_uses,
                    invite.use_count,
                    int(invite.active),
                    invite.model_dump_json(),
                    invite.created_at.isoformat(),
                    invite.expires_at.isoformat() if invite.expires_at else None,
                ),
            )
            connection.commit()

    def load_invite_code(self, code: str) -> InviteCode | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM invite_codes WHERE code = ?",
                (code,),
            ).fetchone()
        if row is None:
            return None
        return InviteCode.model_validate_json(row[0])

    def list_invite_codes(self, limit: int = 100) -> list[InviteCode]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT payload_json FROM invite_codes
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [InviteCode.model_validate_json(row[0]) for row in rows]

    def save_user_relationship(self, relationship: UserRelationship) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO user_relationships (
                    relationship_id,
                    source_user_id,
                    target_user_id,
                    relationship_type,
                    payload_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(relationship_id) DO UPDATE SET
                    payload_json = excluded.payload_json
                """,
                (
                    relationship.relationship_id,
                    relationship.source_user_id,
                    relationship.target_user_id,
                    relationship.relationship_type,
                    relationship.model_dump_json(),
                    relationship.created_at.isoformat(),
                ),
            )
            connection.commit()

    def list_user_relationships(self, user_id: str | None = None, limit: int = 200) -> list[UserRelationship]:
        with self._connect() as connection:
            if user_id:
                rows = connection.execute(
                    """
                    SELECT payload_json FROM user_relationships
                    WHERE source_user_id = ? OR target_user_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (user_id, user_id, limit),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT payload_json FROM user_relationships
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        return [UserRelationship.model_validate_json(row[0]) for row in rows]

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
