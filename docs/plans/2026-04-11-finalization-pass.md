# Distilled TI Finalization Pass Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将当前原型推进到更接近最终版：接入真实 LLM 受限改写和题目实例链路、替换 prototype 聚类为真实聚类服务，并补齐历史页、管理页和题库编辑能力。

**Architecture:** 保持 FastAPI + Next.js 双端结构不变，在后端新增模板检索、实例存档、锚点调度、聚类训练/推断和 TTL 清理；在前端新增管理视图与历史视图，统一走现有 API。报告层同步展示更细的 sub/module 结果，并升级 AI 文案风格。

**Tech Stack:** Python 3.13, FastAPI, Pydantic, sqlite3, scikit-learn, httpx, pytest, Next.js, React, TypeScript

---

### Task 1: 题目实例化与改写链路

**Files:**
- Modify: `backend/app/services/ai_service.py`
- Create: `backend/app/services/generation.py`
- Modify: `backend/app/services/session_service.py`
- Modify: `backend/app/api/routes.py`
- Modify: `backend/app/api/schemas.py`
- Test: `backend/tests/test_generation.py`

### Task 2: 锚点调度与 TTL 清理

**Files:**
- Modify: `backend/app/services/session_service.py`
- Modify: `backend/app/services/storage.py`
- Modify: `backend/app/core/config.py`
- Test: `backend/tests/test_session_api.py`

### Task 3: 真实聚类服务

**Files:**
- Replace: `backend/app/services/clustering.py`
- Create: `backend/app/services/analytics.py`
- Modify: `backend/app/services/scoring.py`
- Test: `backend/tests/test_clustering.py`

### Task 4: 管理与历史 API

**Files:**
- Modify: `backend/app/api/routes.py`
- Modify: `backend/app/api/schemas.py`
- Create: `backend/tests/test_admin_api.py`

### Task 5: 历史页、管理页、题库编辑器

**Files:**
- Create: `frontend/app/history/page.tsx`
- Create: `frontend/app/admin/page.tsx`
- Create: `frontend/components/AdminClient.tsx`
- Create: `frontend/components/HistoryClient.tsx`
- Modify: `frontend/lib/api.ts`
- Run: `npm run lint`
- Run: `npm run build`
