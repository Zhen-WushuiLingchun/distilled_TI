# Distilled TI Backend

当前后端提供一条可跑的单会话闭环：

- 会话启动：`POST /api/session/start`
- 下一题调度：`POST /api/question/next`
- 提交回答：`POST /api/response/submit`
- 获取会话摘要：`GET /api/session/{id}/summary`
- 获取报告：`GET /api/session/{id}/report`
- 获取二维地图：`GET /api/session/{id}/map`
- 删除当前会话：`DELETE /api/session/{id}`
- 配置 AI Provider：`POST /api/ai/config`
- 读取 AI 配置状态：`GET /api/ai/config`
- 题目改写预览：`POST /api/ai/rewrite-question`
- 新增自定义题目：`POST /api/admin/item-template/create`
- 模板列表：`GET /api/admin/templates`
- 实例题列表：`GET /api/admin/item-instances`
- 本地会话列表：`GET /api/admin/sessions`
- 过期清理：`POST /api/admin/cleanup`

## 用户认证

- 邀请码注册：`POST /api/invite/redeem`，邀请码 + 邮箱注册匿名档案。
- 邮箱登录：`POST /api/auth/login`，已注册用户通过邮箱验证码找回设备凭证。
- 用户信息：`GET /api/user/me`
- 更新偏好：`PATCH /api/user/me`
- 生成邀请码：`POST /api/user/invite/generate`
- 绑定邀请码：`POST /api/user/invite/claim`

## Context API（安全信号测量）

对任意对话上下文进行非诊断性安全/支持信号分析，结合规则、embedding 和 LLM 三层：

- 分析上下文：`POST /api/context/analyze`
- 查询分析历史：`GET /api/context/analyses`
- 查询中高风险信号：`GET /api/context/alerts`

## 千恋万花人格监视器（Senren API）

> **重要声明：Senren 是独立的用户端本地流程。**
> 服务端提供 REST API 接收来自用户本地浏览器的 HTTP 请求；游戏启动、路径验证、Context API 测量等逻辑在本地部署时执行，不要求服务端共享用户文件系统。

### 监视会话

- 启动监视会话：`POST /api/senren/monitor/start`
- 获取实时人格状态：`GET /api/senren/monitor/{session_id}/live-state`
- 提交游戏选择：`POST /api/senren/monitor/choice`，每次选择会 best-effort 调用 Context API 做测量
- 获取路线图：`GET /api/senren/monitor/{session_id}/roadmap`
- 获取 VN 场景：`GET /api/senren/monitor/{session_id}/vn-scene`

### 本地游戏

- 验证游戏目录：`POST /api/senren/local-game/validate`，检测 `scenario.pck` / `Script.pck` / exe
- 启动游戏并监视：`POST /api/senren/local-game/launch`，验证路径 -> `subprocess` 启动游戏 exe -> 创建监视会话
- 获取本地游戏信息：`GET /api/senren/local-game/{session_id}/info`

### 报告与分析

- 获取报告：`GET /api/senren/monitor/{session_id}/report`
- 角色契合度：`GET /api/senren/monitor/{session_id}/character-affinity`
- 角色人设库：`GET /api/senren/skills/personas`

## 本地运行

先从仓库根目录复制配置模板：

```powershell
Copy-Item backend\.env.example backend\.env
# 或零外部 key 烟测：
# Copy-Item backend\.env.minimal.example backend\.env
```

安装依赖：

```powershell
python -m pip install -e .[dev]
```

启动 Public API：

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

启动 Admin API：

```powershell
python -m uvicorn app.admin_main:app --reload --host 127.0.0.1 --port 8001
```

默认地址：

- Public Swagger UI: `http://127.0.0.1:8000/docs`
- Admin Swagger UI: `http://127.0.0.1:8001/docs`

完整配置、密钥数量、Qdrant、火山 Ark、SD WebUI、Resend 和智能体验收流程见仓库根目录 [README.md](../README.md)。

## AI 接口说明

- 当前版本不会把 API Key 返回给前端。
- 通过 `/api/ai/config` 可动态设置：
  - `provider`
  - `model`
  - `base_url`
  - `api_key`
- 也可以把 `AI_*` 写到 `backend/.env` 后运行 `python scripts\ai_acceptance.py --save`，脚本会测试并保存到 SQLite。
- 报告接口会优先调用已配置模型生成中文摘要。
- 如果未配置模型或调用失败，会自动降级为后端生成的 deterministic 文案。

## 会话规则

- 默认答到 `20` 题后开放正式报告。
- 会话可继续一直答题，当前上限是 `10000`。
- 注册用户会话会绑定匿名 `user_id` 并按 `REGISTERED_SESSION_TTL_DAYS` 长期保留；未注册会话仍按短 TTL 清理。
- 活跃会话会同步写入本地 SQLite：`distilled_ti_local.db`

## 题库与约束

- 题库已包含 core / sub / module / anchor 的基础模板。
- `/api/admin/item-template/create` 支持提交自定义题目模板。
- `/api/ai/rewrite-question` 会基于模板 + 会话状态给出受限改写预览，默认优先走真实模型。
- 新题目会经过约束校验：
  - 维度数量限制
  - moralizing 文案拦截
  - 敏感主题拦截
  - 选项数量检查

## 聚类与历史

- 报告聚类已切换为 `scikit-learn KMeans` 方案。
- 会话与实例会写入本地 SQLite，并附带过期时间。
- 历史页展示的是 TTL 生命周期内的本地会话，不是永久存档。
