# Distilled TI Fullstack Slice Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 构建一条可用的全链路体验：用户可连续答题、20 题后可随时获取报告、也可继续答题细化画像，报告文案由 AI 生成并展示核心可视化。

**Architecture:** 先把后端从“纯骨架”提升为“可支撑会话产品”的状态机，补充答题上限、最小报告门槛、本地临时会话生命周期、子维度与模块占位、AI 报告生成接口。然后初始化最小 Next.js 前端，对接会话 API，提供单会话答题页和报告页。

**Tech Stack:** Python 3.13, FastAPI, Pydantic, pytest, Next.js, React, TypeScript, Tailwind CSS

---

### Task 1: 后端会话规则

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/domain/models.py`
- Modify: `backend/app/services/session_service.py`
- Modify: `backend/app/api/schemas.py`
- Modify: `backend/app/api/routes.py`
- Test: `backend/tests/test_session_api.py`

**Step 1: 写失败测试**
- 报告少于 20 题时返回受控提示
- 答题数达到上限时停止继续出题
- 会话可随时退出并拉取当前进度摘要

**Step 2: 跑测试确认失败**

Run: `pytest backend/tests/test_session_api.py -v`
Expected: FAIL

**Step 3: 实现最小规则**
- 增加 `min_questions_for_report`
- 增加 `max_questions_per_session`
- 增加会话状态字段与摘要接口

**Step 4: 再跑测试**

Run: `pytest backend/tests/test_session_api.py -v`
Expected: PASS

### Task 2: 纤维化状态与题库约束

**Files:**
- Modify: `backend/app/domain/models.py`
- Modify: `backend/app/domain/item_bank.py`
- Create: `backend/app/services/validators.py`
- Modify: `backend/app/services/scoring.py`
- Modify: `backend/app/services/session_service.py`
- Test: `backend/tests/test_scoring.py`
- Test: `backend/tests/test_item_bank.py`

**Step 1: 写失败测试**
- 子维度题量达阈值后解锁
- 模块投影在足够题量后出现
- 新增题目违反约束时被拒绝

**Step 2: 跑测试确认失败**

Run: `pytest backend/tests/test_scoring.py backend/tests/test_item_bank.py -v`
Expected: FAIL

**Step 3: 实现最小能力**
- 在状态里加入 `sub_mu/sub_sigma/module_scores`
- 维护子维度解锁阈值
- 增加模板约束校验器

**Step 4: 再跑测试**

Run: `pytest backend/tests/test_scoring.py backend/tests/test_item_bank.py -v`
Expected: PASS

### Task 3: AI 报告与后端报告接口

**Files:**
- Modify: `backend/app/services/ai_service.py`
- Modify: `backend/app/services/scoring.py`
- Modify: `backend/app/api/schemas.py`
- Modify: `backend/app/api/routes.py`
- Test: `backend/tests/test_session_api.py`

**Step 1: 写失败测试**
- 20 题后报告返回 AI 摘要字段
- 未配置 AI 时降级返回 deterministic 文案

**Step 2: 跑测试确认失败**

Run: `pytest backend/tests/test_session_api.py -v`
Expected: FAIL

**Step 3: 实现最小能力**
- AI 服务增加“总结报告”能力
- 报告接口返回结构标签、叙事标签、AI 摘要、二维投影、百分比条数据

**Step 4: 再跑测试**

Run: `pytest backend/tests/test_session_api.py -v`
Expected: PASS

### Task 4: 前端会话与报告页

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/next.config.js`
- Create: `frontend/app/page.tsx`
- Create: `frontend/app/session/page.tsx`
- Create: `frontend/app/report/[sessionId]/page.tsx`
- Create: `frontend/app/globals.css`
- Create: `frontend/lib/api.ts`
- Create: `frontend/components/...`

**Step 1: 初始化项目**

Run: `npm create next@latest frontend -- --ts --tailwind --eslint --app --src-dir false --import-alias "@/*"`
Expected: 项目生成成功

**Step 2: 实现最小页面**
- Landing Page
- Session Page
- Report Page

**Step 3: 接通 API**
- 启动会话
- 提交答案
- 连续作答
- 达到 20 题后展示“查看报告”

**Step 4: 本地验证**

Run: `npm run lint`
Expected: PASS

### Task 5: 联调与体验修整

**Files:**
- Modify: `backend/README.md`
- Create: `frontend/README.md`
- Test: `backend/tests/...`

**Step 1: 运行后端测试**

Run: `pytest backend/tests -v`
Expected: PASS

**Step 2: 运行前端静态检查**

Run: `npm run lint`
Expected: PASS

**Step 3: 记录本地启动方法**

```bash
uvicorn app.main:app --reload
npm run dev
```
