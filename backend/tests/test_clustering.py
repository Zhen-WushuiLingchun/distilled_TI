from app.domain.dimensions import make_zero_vector
from app.domain.models import SessionState
from app.services.clustering import clustering_service


def test_clustering_returns_cluster_and_confidence():
    state = SessionState(
        core_mu=make_zero_vector(0.0) | {
            "abstraction_tendency": 1.2,
            "autonomous_judgment": 1.0,
            "risk_tolerance": 0.6,
        },
        core_sigma=make_zero_vector(1.0),
    )
    clustering_service.refresh([])
    cluster_name, narrative_label, confidence = clustering_service.cluster_for_state(state)

    assert cluster_name
    assert narrative_label
    assert 0.0 <= confidence <= 1.0
    overview = clustering_service.overview()
    assert overview.current_version.startswith("kmeans-v")
    assert overview.training_history


def test_cluster_regions_available_after_refresh():
    clustering_service.refresh([])

    regions = clustering_service.cluster_regions()

    assert regions
    assert "rx" in regions[0]
    assert "ry" in regions[0]


def test_projection_modes_return_coordinates():
    state = SessionState(
        core_mu=make_zero_vector(0.0) | {
            "social_initiative": 0.9,
            "planning_preference": 0.8,
            "execution_drive": 0.7,
            "abstraction_tendency": 1.1,
        },
        core_sigma=make_zero_vector(1.0),
    )
    clustering_service.refresh([])

    auto_point = clustering_service.project_state(state, "auto")
    structure_point = clustering_service.project_state(state, "structure")
    core_point = clustering_service.project_state(state, "core")

    assert len(auto_point) == 2
    assert len(structure_point) == 2
    assert len(core_point) == 2
    assert auto_point != structure_point or auto_point != core_point
