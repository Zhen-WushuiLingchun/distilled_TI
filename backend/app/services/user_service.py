"""Invite-only anonymous user profiles and relationship graph helpers."""

from __future__ import annotations

import hashlib
import math
import re
import secrets
from datetime import UTC, datetime
from uuid import uuid4

from app.core.config import settings
from app.domain.models import (
    InviteCode,
    SessionRecord,
    UserAccessGrant,
    UserProfile,
    UserRecommendation,
    UserRelationship,
)
from app.services.clustering import clustering_service
from app.services.storage import local_session_store


class UserService:
    _EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

    def _hash_token(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _normalize_email(self, email: str) -> str:
        normalized = email.strip().lower()
        if not normalized or not self._EMAIL_PATTERN.match(normalized):
            raise ValueError("invalid_email")
        return normalized

    def _hash_email(self, email: str) -> str:
        return hashlib.sha256(f"email:{email}".encode("utf-8")).hexdigest()

    def _new_handle(self) -> str:
        adjectives = ("ash", "cedar", "mint", "paper", "river", "field", "orbit", "lumen")
        nouns = ("atlas", "signal", "keel", "thread", "marker", "vector", "grain", "node")
        for _ in range(20):
            handle = f"{secrets.choice(adjectives)}-{secrets.choice(nouns)}-{secrets.token_hex(2)}"
            if local_session_store.load_user_by_handle(handle) is None:
                return handle
        return f"anon-{secrets.token_hex(5)}"

    def redeem_invite(self, code: str, email: str) -> UserAccessGrant:
        invite_code = code.strip()
        normalized_email = self._normalize_email(email)
        email_hash = self._hash_email(normalized_email)
        invite = local_session_store.load_invite_code(invite_code)
        now = datetime.now(UTC)
        if invite is None:
            raise ValueError("invite_not_found")
        if not invite.active:
            raise ValueError("invite_inactive")
        if invite.expires_at and invite.expires_at <= now:
            raise ValueError("invite_expired")
        if invite.use_count >= invite.max_uses:
            raise ValueError("invite_exhausted")
        if local_session_store.load_user_by_email_hash(email_hash):
            raise ValueError("email_already_registered")

        user_secret = secrets.token_urlsafe(32)
        profile = UserProfile(
            user_id=f"user-{uuid4()}",
            handle=self._new_handle(),
            invite_code=invite.code,
            invited_by_user_id=invite.created_by_user_id,
            email_hash=email_hash,
            user_secret_hash=self._hash_token(user_secret),
            created_at=now,
            updated_at=now,
        )
        local_session_store.save_user_profile(profile)
        self._create_invite_relationship(invite.created_by_user_id, profile.user_id, now)
        profile = self._ensure_share_invite(profile)

        updated_use_count = invite.use_count + 1
        updated_invite = invite.model_copy(
            update={
                "use_count": updated_use_count,
                "active": invite.active and updated_use_count < invite.max_uses,
            }
        )
        local_session_store.save_invite_code(updated_invite)

        return UserAccessGrant(
            user_id=profile.user_id,
            user_secret=user_secret,
            handle=profile.handle,
            relationship_opt_in=profile.relationship_opt_in,
            recommendation_opt_in=profile.recommendation_opt_in,
        )

    def login(self, email: str) -> UserAccessGrant:
        """通过邮箱登录，返回新 user_secret（旧 secret 作废）。"""
        normalized_email = self._normalize_email(email)
        email_hash = self._hash_email(normalized_email)
        profile = local_session_store.load_user_by_email_hash(email_hash)
        if profile is None:
            raise KeyError("email_not_found")
        user_secret = secrets.token_urlsafe(32)
        updated = profile.model_copy(
            update={
                "user_secret_hash": self._hash_token(user_secret),
                "updated_at": datetime.now(UTC),
            }
        )
        local_session_store.save_user_profile(updated)
        return UserAccessGrant(
            user_id=updated.user_id,
            user_secret=user_secret,
            handle=updated.handle,
            relationship_opt_in=updated.relationship_opt_in,
            recommendation_opt_in=updated.recommendation_opt_in,
        )

    def authenticate(self, user_id: str, user_secret: str | None) -> UserProfile:
        if not user_secret:
            raise PermissionError("user_secret_required")
        profile = local_session_store.load_user_profile(user_id)
        if profile is None:
            raise KeyError("user_not_found")
        if not secrets.compare_digest(profile.user_secret_hash, self._hash_token(user_secret)):
            raise PermissionError("invalid_user_secret")
        return self._ensure_share_invite(profile)

    def create_invite(
        self,
        created_by_user_id: str | None = None,
        label: str = "",
        max_uses: int = 1,
    ) -> InviteCode:
        code = f"DTI-{secrets.token_urlsafe(6).upper().replace('-', '').replace('_', '')[:8]}"
        invite = InviteCode(
            code=code,
            created_by_user_id=created_by_user_id,
            label=label or "Admin invite",
            max_uses=max(1, max_uses),
            created_at=datetime.now(UTC),
        )
        local_session_store.save_invite_code(invite)
        return invite

    def update_profile_flags(
        self,
        profile: UserProfile,
        relationship_opt_in: bool | None = None,
        recommendation_opt_in: bool | None = None,
    ) -> UserProfile:
        updated = profile.model_copy(
            update={
                "relationship_opt_in": profile.relationship_opt_in if relationship_opt_in is None else relationship_opt_in,
                "recommendation_opt_in": profile.recommendation_opt_in
                if recommendation_opt_in is None
                else recommendation_opt_in,
                "updated_at": datetime.now(UTC),
            }
        )
        local_session_store.save_user_profile(updated)
        return updated

    def claim_invite(self, profile: UserProfile, code: str) -> UserProfile:
        invite_code = code.strip()
        invite = local_session_store.load_invite_code(invite_code)
        now = datetime.now(UTC)
        if invite is None:
            raise ValueError("invite_not_found")
        if not invite.active:
            raise ValueError("invite_inactive")
        if invite.expires_at and invite.expires_at <= now:
            raise ValueError("invite_expired")

        source_user_id = invite.created_by_user_id
        if not source_user_id or source_user_id == profile.user_id:
            return self._ensure_share_invite(profile)

        existing = local_session_store.list_user_relationships(user_id=profile.user_id, limit=1000)
        if any(
            item.source_user_id == source_user_id
            and item.target_user_id == profile.user_id
            and item.relationship_type == "invited"
            for item in existing
        ):
            return self._ensure_share_invite(profile)

        if invite.use_count >= invite.max_uses:
            raise ValueError("invite_exhausted")

        self._create_invite_relationship(source_user_id, profile.user_id, now)
        updated_use_count = invite.use_count + 1
        local_session_store.save_invite_code(
            invite.model_copy(
                update={
                    "use_count": updated_use_count,
                    "active": invite.active and updated_use_count < invite.max_uses,
                }
            )
        )
        return self._ensure_share_invite(profile)

    def issue_share_invite(self, profile: UserProfile) -> UserProfile:
        existing_invite = local_session_store.load_invite_code(profile.invite_code)
        if existing_invite and existing_invite.created_by_user_id == profile.user_id and existing_invite.active:
            local_session_store.save_invite_code(existing_invite.model_copy(update={"active": False}))
        return self._create_share_invite(profile)

    def list_users(self, limit: int = 100) -> list[UserProfile]:
        return local_session_store.list_user_profiles(limit)

    def list_invites(self, limit: int = 100) -> list[InviteCode]:
        return local_session_store.list_invite_codes(limit)

    def list_relationships(self, user_id: str | None = None, limit: int = 200) -> list[UserRelationship]:
        return local_session_store.list_user_relationships(user_id, limit)

    def user_sessions(self, user_id: str):
        return local_session_store.list_sessions(user_id=user_id)

    def recommend_candidates(self, subject_user_id: str, limit: int = 5) -> list[UserRecommendation]:
        if not settings.relationship_recommendations_enabled:
            return []

        subject = local_session_store.load_user_profile(subject_user_id)
        if subject is None or not subject.recommendation_opt_in:
            return []

        subject_session = self._latest_report_ready_session(subject_user_id)
        if subject_session is None:
            return []

        connected = self._connected_user_ids(subject_user_id)
        subject_cluster, _label, _confidence = clustering_service.cluster_for_state(subject_session.state)
        candidates: list[UserRecommendation] = []

        for profile in local_session_store.list_user_profiles(500):
            if profile.user_id == subject_user_id:
                continue
            if profile.user_id in connected:
                continue
            if not profile.recommendation_opt_in:
                continue
            candidate_session = self._latest_report_ready_session(profile.user_id)
            if candidate_session is None:
                continue
            candidate_cluster, _candidate_label, _candidate_confidence = clustering_service.cluster_for_state(candidate_session.state)
            similarity = self._core_similarity(subject_session, candidate_session)
            cluster_bonus = 0.08 if candidate_cluster == subject_cluster else 0.0
            score = round(min(1.0, similarity + cluster_bonus), 3)
            candidates.append(
                UserRecommendation(
                    subject_user_id=subject_user_id,
                    candidate_user_id=profile.user_id,
                    candidate_handle=profile.handle,
                    score=score,
                    reason="画像距离接近，且不属于当前邀请关系链的直接连接。",
                    shared_cluster_name=candidate_cluster if candidate_cluster == subject_cluster else None,
                )
            )

        return sorted(candidates, key=lambda item: item.score, reverse=True)[:limit]

    def _latest_report_ready_session(self, user_id: str) -> SessionRecord | None:
        records = local_session_store.list_session_records(limit=50, user_id=user_id)
        report_ready = [
            record
            for record in records
            if record.state.question_count >= settings.min_questions_for_report
        ]
        return report_ready[0] if report_ready else None

    def _connected_user_ids(self, user_id: str) -> set[str]:
        connected = {user_id}
        for relationship in local_session_store.list_user_relationships(user_id=user_id, limit=500):
            connected.add(relationship.source_user_id)
            connected.add(relationship.target_user_id)
        return connected

    def _ensure_share_invite(self, profile: UserProfile) -> UserProfile:
        existing_invite = local_session_store.load_invite_code(profile.invite_code)
        if (
            existing_invite
            and existing_invite.created_by_user_id == profile.user_id
            and existing_invite.active
            and existing_invite.use_count < existing_invite.max_uses
        ):
            return profile
        if existing_invite and existing_invite.created_by_user_id == profile.user_id:
            return profile

        return self._create_share_invite(profile)

    def _create_share_invite(self, profile: UserProfile) -> UserProfile:
        invite = self.create_invite(
            created_by_user_id=profile.user_id,
            label=f"Share invite for {profile.handle}",
            max_uses=settings.user_invite_max_uses,
        )
        updated = profile.model_copy(update={"invite_code": invite.code, "updated_at": datetime.now(UTC)})
        local_session_store.save_user_profile(updated)
        return updated

    def _create_invite_relationship(
        self,
        source_user_id: str | None,
        target_user_id: str,
        created_at: datetime,
    ) -> None:
        if not source_user_id or source_user_id == target_user_id:
            return
        local_session_store.save_user_relationship(
            UserRelationship(
                relationship_id=f"rel-{uuid4()}",
                source_user_id=source_user_id,
                target_user_id=target_user_id,
                relationship_type="invited",
                created_at=created_at,
            )
        )

    def _core_similarity(self, left: SessionRecord, right: SessionRecord) -> float:
        keys = sorted(set(left.state.core_mu) | set(right.state.core_mu))
        if not keys:
            return 0.0
        distance = math.sqrt(
            sum((left.state.core_mu.get(key, 0.0) - right.state.core_mu.get(key, 0.0)) ** 2 for key in keys)
        )
        return max(0.0, 1.0 - distance / max(math.sqrt(len(keys)) * 2.0, 0.01))


user_service = UserService()
