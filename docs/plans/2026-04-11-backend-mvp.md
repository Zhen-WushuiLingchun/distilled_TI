# Distilled TI Backend MVP Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 搭建 Distilled TI 的后端 MVP，跑通会话启动、选题、答题更新、报告与地图查询的 API 闭环。

**Architecture:** 采用单体 FastAPI 后端，先以内存题库与 SQLite 持久化建立稳定闭环，把核心维度、评分引擎、会话状态和 API 契约固定下来。实现上保持模块化分层，后续可替换为 PostgreSQL、LLM 改写与聚类服务而不破坏接口。

**Tech Stack:** Python 3.13, FastAPI, Pydantic, SQLModel, pytest

---

### Task 1: 项目骨架与依赖

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/core/config.py`
- Create: `backend/app/api/routes.py`
- Create: `backend/tests/test_health.py`

**Step 1: 写失败测试**

```python
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
```

**Step 2: 运行测试确认失败**

Run: `pytest backend/tests/test_health.py -v`
Expected: FAIL，因为应用尚未创建。

**Step 3: 写最小实现**

```python
app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}
```

**Step 4: 再跑测试**

Run: `pytest backend/tests/test_health.py -v`
Expected: PASS

### Task 2: 领域模型与维度定义

**Files:**
- Create: `docs/dimensions.md`
- Create: `backend/app/domain/dimensions.py`
- Create: `backend/app/domain/models.py`
- Create: `backend/app/domain/item_bank.py`
- Test: `backend/tests/test_item_bank.py`

**Step 1: 写失败测试**

```python
def test_seed_item_bank_has_core_questions():
    bank = build_seed_item_bank()
    assert len(bank) >= 10
```

**Step 2: 运行测试确认失败**

Run: `pytest backend/tests/test_item_bank.py -v`
Expected: FAIL，因为题库构建器不存在。

**Step 3: 写最小实现**

```python
CORE_DIMENSIONS = [...]

def build_seed_item_bank():
    return [...]
```

**Step 4: 再跑测试**

Run: `pytest backend/tests/test_item_bank.py -v`
Expected: PASS

### Task 3: 评分引擎

**Files:**
- Create: `backend/app/services/scoring.py`
- Test: `backend/tests/test_scoring.py`

**Step 1: 写失败测试**

```python
def test_submit_response_updates_mu_and_sigma():
    engine = ScoringEngine()
    next_state = engine.apply_response(state, item, 1.0)
    assert next_state.core_mu != state.core_mu
```

**Step 2: 运行测试确认失败**

Run: `pytest backend/tests/test_scoring.py -v`
Expected: FAIL，因为评分引擎未实现。

**Step 3: 写最小实现**

```python
class ScoringEngine:
    def apply_response(...):
        ...
```

**Step 4: 再跑测试**

Run: `pytest backend/tests/test_scoring.py -v`
Expected: PASS

### Task 4: 会话服务与 API

**Files:**
- Create: `backend/app/services/session_service.py`
- Create: `backend/app/api/schemas.py`
- Modify: `backend/app/api/routes.py`
- Test: `backend/tests/test_session_api.py`

**Step 1: 写失败测试**

```python
def test_start_submit_and_fetch_report():
    ...
```

**Step 2: 运行测试确认失败**

Run: `pytest backend/tests/test_session_api.py -v`
Expected: FAIL，因为 API 尚未接通。

**Step 3: 写最小实现**

```python
@router.post("/api/session/start")
def start_session():
    ...
```

**Step 4: 再跑测试**

Run: `pytest backend/tests/test_session_api.py -v`
Expected: PASS

### Task 5: 验证与清理

**Files:**
- Modify: `backend/README.md`
- Test: `backend/tests/...`

**Step 1: 运行测试集**

Run: `pytest backend/tests -v`
Expected: PASS

**Step 2: 检查诊断**

Run: VS Code diagnostics on edited Python files
Expected: 无新增错误

**Step 3: 记录运行方式**

```bash
uvicorn app.main:app --reload
```
