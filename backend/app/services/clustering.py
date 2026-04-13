"""KMeans-based clustering for session states."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib

import numpy as np
from sklearn.cluster import KMeans

from app.core.config import settings
from app.domain.dimensions import CORE_DIMENSION_KEYS
from app.domain.models import ClusterDescriptor, ClusterLabelOverride, ClusterMembership, ClusterOverview, ClusterVersionInfo, SessionRecord, SessionState
from app.services.storage import local_session_store


@dataclass(frozen=True)
class ClusterDescriptor:
    name: str
    narrative_label: str


CLUSTER_LABELS: tuple[ClusterDescriptor, ...] = (
    ClusterDescriptor("协同推进簇", "轨道修正式协作者"),
    ClusterDescriptor("抽象统筹簇", "高阶抽象操盘手"),
    ClusterDescriptor("稳态执行簇", "低波动推进者"),
    ClusterDescriptor("探索扩张簇", "远距校准型探索者"),
    ClusterDescriptor("强压决断簇", "低温高压思考核"),
    ClusterDescriptor("情境适配簇", "多场景切换型节点"),
)


class ClusteringService:
    def __init__(self) -> None:
        self._model: KMeans | None = None
        self._centers: np.ndarray | None = None
        self._training_matrix: np.ndarray | None = None
        self._training_labels: np.ndarray | None = None
        self._projection_mean: np.ndarray | None = None
        self._projection_components: np.ndarray | None = None
        self._core_projection_mean: np.ndarray | None = None
        self._core_projection_components: np.ndarray | None = None
        self._cluster_regions: list[dict[str, float | str | int]] = []
        self._cluster_count = settings.cluster_count
        self._current_signature: str | None = None
        self._current_version: str = "kmeans-v0"

    def feature_vector(self, state: SessionState) -> np.ndarray:
        latency_values = [answer.latency_ms for answer in state.answers if answer.latency_ms is not None]
        median_latency = float(np.median(latency_values)) if latency_values else 2500.0
        extreme_ratio = (
            sum(1 for answer in state.answers if abs(answer.mapped_score) >= 1.0) / len(state.answers)
            if state.answers
            else 0.0
        )
        vector = [
            *(state.core_mu[key] for key in CORE_DIMENSION_KEYS),
            state.zeta["consistency"],
            state.zeta["performative"],
            state.zeta["exploration"],
            state.zeta["fatigue"],
            extreme_ratio,
            median_latency / 5000.0,
            len(state.unlocked_subdimensions) / 10.0,
            len(state.active_modules) / 6.0,
        ]
        return np.array(vector, dtype=float)

    def refresh(self, sessions: list[SessionRecord]) -> None:
        dataset = [self.feature_vector(session.state) for session in sessions if session.state.question_count >= 5]
        dataset.extend(self._synthetic_reference_vectors())
        matrix = np.vstack(dataset)
        cluster_count = min(self._cluster_count, len(matrix))
        signature = self._build_signature(matrix, cluster_count)
        if signature == self._current_signature and self._model is not None:
            return
        self._model = KMeans(n_clusters=cluster_count, random_state=42, n_init=10)
        self._model.fit(matrix)
        self._centers = self._model.cluster_centers_
        self._training_matrix = matrix
        self._training_labels = self._model.labels_
        self._fit_projection(matrix)
        self._cluster_regions = self._build_cluster_regions(matrix, self._model.labels_)
        self._current_signature = signature
        self._persist_version(signature, len(dataset), cluster_count)

    def cluster_for_state(self, state: SessionState) -> tuple[str, str, float]:
        memberships = self.cluster_memberships_for_state(state)
        top = memberships[0]
        descriptor = self._descriptor_for(top.cluster_index)
        confidence = max(0.0, min(1.0, top.weight))
        return descriptor.name, descriptor.narrative_label, confidence

    def cluster_memberships_for_state(self, state: SessionState, top_k: int = 3) -> list[ClusterMembership]:
        if self._model is None or self._centers is None:
            self.refresh([])
        vector = self.feature_vector(state)
        assert self._centers is not None
        distances = np.linalg.norm(self._centers - vector, axis=1)
        logits = np.exp(-distances)
        weight_sum = float(logits.sum()) or 1.0
        ranked = np.argsort(distances)
        memberships: list[ClusterMembership] = []
        for index in ranked[:top_k]:
            descriptor = self._descriptor_for(int(index))
            memberships.append(
                ClusterMembership(
                    cluster_index=int(index),
                    cluster_name=descriptor.name,
                    narrative_label=descriptor.narrative_label,
                    weight=round(float(logits[index] / weight_sum), 4),
                    distance=round(float(distances[index]), 4),
                )
            )
        return memberships

    def project_state(self, state: SessionState, projection_mode: str = "auto") -> tuple[float, float]:
        return self._project_vector(self.feature_vector(state), projection_mode)

    def project_template_vector(
        self,
        weights: dict[str, float],
        mapped_score: float,
        projection_mode: str = "auto",
    ) -> tuple[float, float]:
        if projection_mode == "structure":
            return self._project_structure(weights, mapped_score)
        vector = np.array(
            [
                *(weights.get(key, 0.0) * mapped_score for key in CORE_DIMENSION_KEYS),
                0.0,
                0.0,
                0.0,
                0.0,
                abs(mapped_score),
                0.0,
                0.0,
                0.0,
            ],
            dtype=float,
        )
        return self._project_vector(vector, projection_mode)

    def overview(self, sessions: list[SessionRecord] | None = None) -> ClusterOverview:
        versions = local_session_store.list_cluster_versions()
        if not versions:
            self.refresh([])
            versions = local_session_store.list_cluster_versions()
        current = versions[0]
        scatter_points = self._scatter_points(sessions or [])
        return ClusterOverview(
            current_version=current.version,
            sample_size=current.sample_size,
            cluster_count=current.cluster_count,
            labels=[self._descriptor_for(index).name for index in range(current.cluster_count)],
            training_history=versions,
            scatter_points=scatter_points,
            label_overrides=local_session_store.list_cluster_label_overrides(current.version),
        )

    def save_label_override(self, version: str, cluster_index: int, name: str, narrative_label: str) -> ClusterLabelOverride:
        override = ClusterLabelOverride(
            version=version,
            cluster_index=cluster_index,
            name=name,
            narrative_label=narrative_label,
            updated_at=datetime.now(UTC),
        )
        local_session_store.save_cluster_label_override(override)
        return override

    def _synthetic_reference_vectors(self) -> list[np.ndarray]:
        references: list[np.ndarray] = []
        presets = [
            {"social_initiative": 1.2, "planning_preference": 1.0, "execution_drive": 1.3},
            {"abstraction_tendency": 1.4, "autonomous_judgment": 1.2, "risk_tolerance": 0.8},
            {"planning_preference": 1.1, "emotional_stability": 1.3, "execution_drive": 0.7},
            {"novelty_seeking": 1.4, "risk_tolerance": 1.1, "social_stimulation_tolerance": 0.9},
            {"autonomous_judgment": 1.3, "competition_cooperation": 0.8, "emotional_stability": 0.9},
            {"social_stimulation_tolerance": 1.0, "social_initiative": 0.8, "execution_drive": 0.7},
        ]
        for preset in presets:
            core_mu = {key: preset.get(key, 0.0) for key in CORE_DIMENSION_KEYS}
            state = SessionState(core_mu=core_mu, core_sigma={key: 1.0 for key in CORE_DIMENSION_KEYS})
            references.append(self.feature_vector(state))
        return references

    def _build_signature(self, matrix: np.ndarray, cluster_count: int) -> str:
        rounded = np.round(matrix.mean(axis=0), 3).tolist()
        payload = f"{cluster_count}|{len(matrix)}|{rounded}"
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]

    def _persist_version(self, signature: str, sample_size: int, cluster_count: int) -> None:
        versions = local_session_store.list_cluster_versions()
        if versions and versions[0].dataset_signature == signature:
            self._current_version = versions[0].version
            return

        version_number = len(versions) + 1
        version = ClusterVersionInfo(
            version=f"kmeans-v{version_number}",
            sample_size=sample_size,
            cluster_count=cluster_count,
            labels=[label.name for label in CLUSTER_LABELS[:cluster_count]],
            dataset_signature=signature,
            created_at=datetime.now(UTC),
        )
        local_session_store.save_cluster_version(version)
        self._current_version = version.version

    def _descriptor_for(self, cluster_index: int) -> ClusterDescriptor:
        base = CLUSTER_LABELS[cluster_index % len(CLUSTER_LABELS)]
        overrides = local_session_store.list_cluster_label_overrides(self._current_version)
        matched = next((item for item in overrides if item.cluster_index == cluster_index), None)
        if matched:
            return ClusterDescriptor(matched.name, matched.narrative_label)
        return base

    def center_points(self, projection_mode: str = "auto") -> list[dict[str, float | str | int]]:
        if self._model is None or self._centers is None:
            self.refresh([])
        assert self._centers is not None
        points: list[dict[str, float | str | int]] = []
        for index, center in enumerate(self._centers):
            dimensions = {key: float(center[position]) for position, key in enumerate(CORE_DIMENSION_KEYS)}
            x, y = self._project_vector(center, projection_mode)
            descriptor = self._descriptor_for(index)
            points.append(
                {
                    "cluster_index": index,
                    "cluster_name": descriptor.name,
                    "x": x,
                    "y": y,
                }
            )
        return points

    def cluster_regions(self, projection_mode: str = "auto") -> list[dict[str, float | str | int]]:
        if self._model is None or self._centers is None or self._training_matrix is None or self._training_labels is None:
            self.refresh([])
        if projection_mode == "auto":
            return self._cluster_regions
        assert self._training_matrix is not None
        assert self._training_labels is not None
        return self._build_cluster_regions(self._training_matrix, self._training_labels, projection_mode)

    def _scatter_points(self, sessions: list[SessionRecord]) -> list[dict[str, float | str | int]]:
        points: list[dict[str, float | str | int]] = []
        for session in sessions[-60:]:
            try:
                cluster_name, _, confidence = self.cluster_for_state(session.state)
            except Exception:
                continue
            points.append(
                {
                    "session_id": session.session_id,
                    "x": self.project_state(session.state)[0],
                    "y": self.project_state(session.state)[1],
                    "question_count": session.state.question_count,
                    "cluster_name": cluster_name,
                    "confidence": round(confidence, 3),
                }
            )
        return points

    def _fit_projection(self, matrix: np.ndarray) -> None:
        self._projection_mean = matrix.mean(axis=0)
        centered = matrix - self._projection_mean
        _u, _s, vt = np.linalg.svd(centered, full_matrices=False)
        if vt.shape[0] >= 2:
            self._projection_components = vt[:2]
        else:
            basis = np.zeros((2, matrix.shape[1]))
            basis[0, 0] = 1.0
            basis[1, 1 if matrix.shape[1] > 1 else 0] = 1.0
            self._projection_components = basis
        core_matrix = matrix[:, : len(CORE_DIMENSION_KEYS)]
        self._core_projection_mean = core_matrix.mean(axis=0)
        core_centered = core_matrix - self._core_projection_mean
        _core_u, _core_s, core_vt = np.linalg.svd(core_centered, full_matrices=False)
        if core_vt.shape[0] >= 2:
            self._core_projection_components = core_vt[:2]
        else:
            core_basis = np.zeros((2, core_matrix.shape[1]))
            core_basis[0, 0] = 1.0
            core_basis[1, 1 if core_matrix.shape[1] > 1 else 0] = 1.0
            self._core_projection_components = core_basis

    def _project_vector(self, vector: np.ndarray, projection_mode: str = "auto") -> tuple[float, float]:
        if projection_mode == "structure":
            return self._project_structure(
                {key: float(vector[position]) for position, key in enumerate(CORE_DIMENSION_KEYS)},
                1.0,
            )
        if self._projection_mean is None or self._projection_components is None or self._core_projection_mean is None or self._core_projection_components is None:
            self.refresh([])
        if projection_mode == "core":
            assert self._core_projection_mean is not None
            assert self._core_projection_components is not None
            core_vector = vector[: len(CORE_DIMENSION_KEYS)]
            centered = core_vector - self._core_projection_mean
            coords = self._core_projection_components @ centered
            return round(float(coords[0]), 3), round(float(coords[1]), 3)
        assert self._projection_mean is not None
        assert self._projection_components is not None
        centered = vector - self._projection_mean
        coords = self._projection_components @ centered
        return round(float(coords[0]), 3), round(float(coords[1]), 3)

    def _project_structure(self, weights: dict[str, float], mapped_score: float) -> tuple[float, float]:
        social_axis = (
            weights.get("social_initiative", 0.0)
            + 0.65 * weights.get("social_stimulation_tolerance", 0.0)
            + 0.45 * weights.get("competition_cooperation", 0.0)
        ) * mapped_score
        structure_axis = (
            weights.get("planning_preference", 0.0)
            + 0.7 * weights.get("execution_drive", 0.0)
            + 0.45 * weights.get("abstraction_tendency", 0.0)
        ) * mapped_score
        return round(float(social_axis), 3), round(float(structure_axis), 3)

    def _build_cluster_regions(
        self,
        matrix: np.ndarray,
        labels: np.ndarray,
        projection_mode: str = "auto",
    ) -> list[dict[str, float | str | int]]:
        projected = np.array([self._project_vector(vector, projection_mode) for vector in matrix], dtype=float)
        regions: list[dict[str, float | str | int]] = []
        assert self._centers is not None
        for index in range(len(self._centers)):
            cluster_points = projected[labels == index]
            descriptor = self._descriptor_for(index)
            if len(cluster_points) == 0:
                continue
            center_x = float(cluster_points[:, 0].mean())
            center_y = float(cluster_points[:, 1].mean())
            if len(cluster_points) >= 2:
                covariance = np.cov(cluster_points.T)
                eigenvalues, eigenvectors = np.linalg.eigh(covariance)
                order = np.argsort(eigenvalues)[::-1]
                eigenvalues = eigenvalues[order]
                eigenvectors = eigenvectors[:, order]
                angle = float(np.degrees(np.arctan2(eigenvectors[1, 0], eigenvectors[0, 0])))
                rx = max(0.28, float(np.sqrt(max(eigenvalues[0], 0.02))) * 1.9)
                ry = max(0.18, float(np.sqrt(max(eigenvalues[1], 0.01))) * 1.5)
            else:
                angle = 0.0
                rx = 0.36
                ry = 0.22
            regions.append(
                {
                    "cluster_index": index,
                    "cluster_name": descriptor.name,
                    "x": round(center_x, 3),
                    "y": round(center_y, 3),
                    "rx": round(rx, 3),
                    "ry": round(ry, 3),
                    "angle": round(angle, 2),
                }
            )
        return regions


clustering_service = ClusteringService()
