from __future__ import annotations

import pytest

from app.services.storage import local_session_store


@pytest.fixture(autouse=True)
def isolated_local_session_store(tmp_path):
    local_session_store.db_path = tmp_path / "distilled_ti_test.db"
    local_session_store._initialize()

