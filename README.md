# Distilled TI 中文开发与使用手册

> Not a type. A structure.

Distilled TI 是一个本地优先的连续心理测量、行为倾向估计与交互式叙事实验系统。它不是传统的一次性“人格类型测试”，而是把答题、自由文本、视觉小说选择、长期会话上下文、embedding 检索、LLM 解释和聚类分析组合成一条可扩展的画像引擎。

当前仓库已经包含三类可运行产品形态：

- 标准测量模式：用户按题作答，系统连续更新核心维度、子维度、模块倾向、聚类与报告。
- Story / Galgame 模式：把测量题隐藏在视觉小说剧情中，用户通过自然选择或自由文本推进故事。
- AI Chat 支持信号 demo：基于 NextChat 的独立聊天前端，把任意聊天上下文接入后端的非诊断支持/风险信号 API。

本项目不提供医学诊断，不替代临床评估，不应作为高风险自动决策依据。所有“心理问题”“风险”“支持信号”相关输出都应理解为产品安全、人工复核、长期趋势观察和研究原型中的非诊断信号。

## 目录

- [系统总览](#系统总览)
- [核心原理](#核心原理)
- [测量系统如何工作](#测量系统如何工作)
- [LLM、embedding、reranker 与聚类分别做什么](#llmembeddingreranker-与聚类分别做什么)
- [开箱配置路线图](#开箱配置路线图)
- [快速启动](#快速启动)
- [后端服务与端口](#后端服务与端口)
- [环境变量配置](#环境变量配置)
- [公开用户流程](#公开用户流程)
- [Story / Galgame 模式](#story--galgame-模式)
- [图像资产生成：火山 Ark、SD WebUI 与缓存](#图像资产生成火山-arksd-webui-与缓存)
- [AI Chat 支持信号 demo](#ai-chat-支持信号-demo)
- [API 总览](#api-总览)
- [数据、隐私与邀请关系](#数据隐私与邀请关系)
- [开发指南](#开发指南)
- [测试与验收](#测试与验收)
- [给智能体/CC/Codex 的安装验收清单](#给智能体cccodex-的安装验收清单)
- [已知限制](#已知限制)

## 系统总览

![Distilled TI Visual](figure/1.png)

Distilled TI 的核心目标是：不要把用户压缩成固定标签，而是维护一个会随交互不断更新的状态空间。

系统会记录和估计：

- 核心心理/行为维度：例如社交主动性、风险承受、抽象倾向、执行驱动等。
- 不确定性：每个核心维度都有 `mu` 和 `sigma`，报告会展示当前稳定程度。
- 子维度：当某个核心维度样本足够时，解锁更细的子维度。
- 模块倾向：例如学习风格、项目角色、冲突模式、聊天模式、创造模式、团队模式。
- 行为统计：题数、延迟、极端选择比例、一致性、探索度、疲劳信号等。
- 聚类位置：通过 KMeans 与二维投影展示用户当前状态在群体空间里的位置。
- 长期演化：注册用户可以保留会话和报告历史，观察自己的变化轨迹。
- 关系网络：邀请码建立匿名邀请边，用于后续社交推荐和关系网络分析。

## 核心原理

```text
用户输入
  ├─ 标准选择题
  ├─ Story Mode 剧情选择
  ├─ Story Mode 自由文本
  └─ AI Chat 长上下文

后端分析层
  ├─ ScoringEngine: 连续维度更新
  ├─ EmbeddingService: 标准化文本向量化
  ├─ VectorIndexer: Qdrant / 本地向量库检索
  ├─ RerankerService: SiliconFlow rerank 二次排序
  ├─ AIService: LLM 解释、剧情生成、自由文本倾向分类
  ├─ ClusteringService: KMeans 聚类、二维投影
  └─ ContextAnalysisService: 通用支持/风险信号 API

输出
  ├─ 当前题目 / 当前剧情幕
  ├─ 用户状态向量
  ├─ 报告与解释
  ├─ 聚类与投影地图
  ├─ 相似题 / 相似会话 / 相似剧情 turn
  └─ AI Chat 后台支持信号
```

这里最重要的设计原则是：向量层、LLM 层、SD 资产层都只是增强层。它们失败时，标准答题、Story Mode、报告生成和提交答案仍应可用。

## 测量系统如何工作

### 1. 题目不是孤立文本，而是带权重的测量对象

每个 `ItemTemplate` 或 `ItemInstance` 都包含：

- `prompt`: 用户看到的题目或隐藏测量种子。
- `options`: 选项及其映射分数，通常是 `-1.0` 到 `+1.0`。
- `dimension_weights`: 对核心维度的影响权重。
- `subdimension_weights`: 对子维度的影响权重。
- `module_affinities`: 对场景模块的影响。
- `layer`: `core | sub | module | probe | entertainment`。
- `scenario_tags`: 情景标签，用于去重、检索和生成。

### 2. 每次回答都会更新连续状态

后端使用 `ScoringEngine` 做状态更新：

```text
predicted_score = tanh(discrimination * (core_mu · weights - difficulty))
residual = observed_score - predicted_score
eta = eta0 / sqrt(1 + question_count / eta_decay)
core_mu += eta * residual * dimension_weight
core_sigma = shrink(core_sigma) + drift
```

直观解释：

- 如果用户的选择比模型预期更“正向”，对应维度会向正方向更新。
- 如果用户的选择比模型预期更“负向”，对应维度会向负方向更新。
- 题数越多，单题影响越小。
- `sigma` 会随有效观测逐渐收缩，但保留最小不确定性。
- 子维度只有在父维度样本足够后才解锁，避免早期过度解释。

### 3. 系统同时维护 zeta 行为指标

`zeta` 不是人格维度，而是回答过程信号：

- `consistency`: 近期回答和模型预期的稳定程度。
- `performative`: 预留给表演性/策略性作答特征。
- `exploration`: 交互展开程度。
- `fatigue`: 过快作答或疲劳信号。

这些指标会进入报告、聚类特征和支持信号，但不会被当成诊断结论。

### 4. 报告不是固定模板，而是结构化状态摘要

报告包含：

- 核心维度条形图。
- 子维度洞察。
- 模块倾向。
- 聚类名称、混合权重和置信度。
- 不确定性摘要。
- 支持/风险提示。
- 可选 LLM 解释文案。

如果 LLM 未配置或调用失败，后端会回退到 deterministic 文案。

## LLM、embedding、reranker 与聚类分别做什么

### LLM

LLM 目前用于：

- 报告解释：把结构化状态转换成可读叙事。
- 题目改写：管理端预览候选改写，不直接覆盖题库。
- Story Mode 剧情生成：把隐藏测量 seed、角色设定、地点和历史 turn 转成自然 VN 剧情。
- Story Mode 自由文本倾向分类：把玩家自己写的话映射到当前剧情选项的 `option_key`。
- 通用 Context API：作为可选 JSON evaluator 补充规则和 embedding 信号。

默认可接 OpenAI-compatible API。DeepSeek 示例配置见 [环境变量配置](#环境变量配置)。

### Embedding

Embedding 用于把题目、实例、会话快照、Story turn 和外部聊天上下文变成语义向量。

当前索引对象包括：

- `item_vectors`: 模板题、生成实例题、改写候选、Galgame turn。
- `session_vectors`: 会话 milestone 快照。

典型用途：

- 相似题检索，防止题库重复。
- 改写预览 retrieval evidence。
- 改写候选 embedding 评分。
- 相似会话检索。
- 相似 Galgame turn 检索。
- 自由文本与剧情选项的语义相似度计算。
- Context API 中的支持/风险语义 anchor 匹配。

### Reranker

Reranker 已接入向量检索的二次排序链路。启用后，`VectorIndexer` 会先用 embedding 召回更多候选，再调用 reranker 按自然查询和候选文本重新排序。

默认推荐：

```env
RERANKER_BASE_URL=https://api.siliconflow.cn/v1
RERANKER_MODEL=BAAI/bge-reranker-v2-m3
```

Reranker 失败不会阻塞主业务，只会退回 embedding 排序。

### 聚类

聚类由 `ClusteringService` 完成，核心方法是 KMeans。

聚类特征包括：

- 10 个核心维度的 `core_mu`。
- `zeta` 四项行为指标。
- 极端选择比例。
- 中位作答延迟。
- 解锁子维度数量。
- 激活模块数量。

样本不足时，系统会混入 synthetic reference vectors，保证本地 demo 也能稳定出簇。聚类结果会用于报告、地图、管理端概览和长期演化展示。

## 开箱配置路线图

这套仓库可以按两种强度启动。先选路线，再复制对应模板。

### 路线 A：零外部 key，本地烟测

适合第一次 clone、CI、或者只想确认页面/后端能跑起来。

需要配置的外部 API：`0` 个。

使用模板：

```powershell
Copy-Item backend\.env.minimal.example backend\.env
Copy-Item frontend\.env.local.example frontend\.env.local
```

能力边界：

- 标准测量、报告 fallback、历史档案、邀请注册、Senren/Story fallback 都能跑。
- 登录验证码会直接返回到页面，便于本地调试；不要用于公开部署。
- embedding/reranker、云端生图、邮件发送、真实 LLM 文案都不会调用。
- Context API 允许本机无 key 调用，只用于本地 demo。

### 路线 B：完整本地联调

适合展示真实能力、给别人验收、或者让智能体继续开发。

建议配置的外部 API：`4` 个。

| 用途 | 推荐服务/模型 | 环境变量 |
| --- | --- | --- |
| LLM 文本、报告、剧情、自由文本分类 | DeepSeek `deepseek-v4-pro` | `AI_API_KEY`，再运行 `backend/scripts/ai_acceptance.py --save` |
| embedding 与 reranker | SiliconFlow `BAAI/bge-m3`、`BAAI/bge-reranker-v2-m3` | `EMBEDDING_API_KEY`、`RERANKER_API_KEY` |
| 邮箱验证码 | Resend | `RESEND_API_KEY`、`EMAIL_FROM` |
| GPU-free 云端生图 | Volcengine Ark `doubao-seedream-5-0-260128` | `GALGAME_ASSET_API_KEY` |

使用模板：

```powershell
Copy-Item backend\.env.example backend\.env
Copy-Item frontend\.env.local.example frontend\.env.local
```

需要手动替换的 placeholder：

- `your_deepseek_key`
- `your_siliconflow_key`
- `your_resend_key`
- `your_volcengine_ark_api_key`
- `your_context_api_key`
- `EMAIL_FROM` 里的发信域名邮箱

本地服务数量：

- 必需：Public API `8000`、Admin API `8001`、主前端 `3000`。
- 可选：Qdrant HTTP `6333`；Windows 推荐先用 `QDRANT_LOCAL_PATH=.qdrant-local`，不必启动 Docker。
- 可选：SD WebUI `7860`；只有把 `GALGAME_ASSET_BACKEND=sdwebui` 时才需要。
- 可选：AI Chat static demo `3100` 或 NextChat demo `3101`。

### 哪些密钥不能进仓库

只能写入本地文件：

- `backend/.env`
- `frontend/.env.local`
- `ai-chat-support-demo/.env`
- `ai-chat-support-demo/nextchat/.env.local`

仓库模板只允许 placeholder。`.gitignore` 已忽略真实 `.env`、本地数据库、Qdrant 状态、生成图片、Next build 输出和 `node_modules`。

## 快速启动

### 环境要求

- Windows PowerShell。
- Python `>=3.13`。
- Node.js `>=20`。
- npm `>=10`。
- 可选：本地 SD WebUI，默认 `http://127.0.0.1:7860`。
- 可选：Qdrant Docker 或 Qdrant local path。

### 安装后端

```powershell
cd "F:\学习和研究\新鲜玩意\distilled TI-codex-795e\backend"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e .[dev]
```

### 安装前端

```powershell
cd "F:\学习和研究\新鲜玩意\distilled TI-codex-795e\frontend"
npm install
```

### 配置环境变量

复制后端配置模板：

```powershell
cd "F:\学习和研究\新鲜玩意\distilled TI-codex-795e"
Copy-Item backend\.env.example backend\.env
Copy-Item frontend\.env.local.example frontend\.env.local
```

然后在 `backend/.env` 中填入本地 key。不要把真实 key 写入 README、源码或提交记录。第一次只做无 key 烟测时，改用：

```powershell
cd "F:\学习和研究\新鲜玩意\distilled TI-codex-795e"
Copy-Item backend\.env.minimal.example backend\.env
Copy-Item frontend\.env.local.example frontend\.env.local
```

完整联调前建议先跑：

```powershell
cd backend
python scripts\ai_acceptance.py --save
python scripts\vector_acceptance.py
```

### 一键启动主应用

在仓库根目录执行：

```powershell
.\start-dev.bat
```

它会启动：

- Public API: `http://127.0.0.1:8000`
- Admin API: `http://127.0.0.1:8001`
- Main Frontend: `http://127.0.0.1:3000`

### 手动启动主应用

Public API：

```powershell
cd backend
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Admin API：

```powershell
cd backend
python -m uvicorn app.admin_main:app --reload --host 127.0.0.1 --port 8001
```

Main Frontend：

```powershell
cd frontend
npm run dev
```

## 后端服务与端口

最小运行只需要三项：

| 服务 | 必需 | 默认端口 | 说明 |
| --- | --- | --- | --- |
| Public FastAPI | 是 | `8000` | 用户注册、会话、答题、报告、Story、Context API |
| Admin FastAPI | 是 | `8001` | 模板、AI 配置、向量、资产、用户关系、聚类管理 |
| Main Next.js Frontend | 是 | `3000` | 主用户端和管理端页面 |

增强能力按需启动：

| 服务 | 必需 | 默认端口/路径 | 说明 |
| --- | --- | --- | --- |
| Qdrant local path | 否 | `.qdrant-local` | Windows 推荐方式，不需要 Docker，设置 `QDRANT_LOCAL_PATH` |
| Qdrant Docker | 否 | `6333` | 设置 `QDRANT_URL=http://127.0.0.1:6333` |
| SD WebUI | 否 | `7860` | 仅在 `GALGAME_ASSET_BACKEND=sdwebui` 时需要，需启动 API |
| AI Chat static demo | 否 | `3100` | 轻量外部聊天接入样例 |
| NextChat demo | 否 | `3000` 或自定义 | 独立聊天助手 demo，建议和主前端错开端口 |

如果主前端已经占用 `3000`，NextChat demo 可以这样启动：

```powershell
cd ai-chat-support-demo\nextchat
npm run mask
npx next dev -p 3101
```

## 环境变量配置

后端使用 `pydantic-settings` 读取 `backend/.env`。前端只读取公开 API 地址，绝不能放模型或邮件密钥。

### 配置文件清单

| 文件 | 是否提交 | 用途 |
| --- | --- | --- |
| [backend/.env.example](backend/.env.example) | 是 | 完整联调模板，包含 DeepSeek、SiliconFlow、Resend、Volcengine placeholder |
| [backend/.env.minimal.example](backend/.env.minimal.example) | 是 | 零外部 key 烟测模板 |
| `backend/.env` | 否 | 后端真实本地配置和所有密钥 |
| [frontend/.env.local.example](frontend/.env.local.example) | 是 | 主前端 API 地址模板 |
| `frontend/.env.local` | 否 | 主前端本地 API 地址 |
| [ai-chat-support-demo/.env.example](ai-chat-support-demo/.env.example) | 是 | 轻量 AI Chat demo 模板 |
| [ai-chat-support-demo/nextchat/.env.template](ai-chat-support-demo/nextchat/.env.template) | 是 | NextChat demo 模板 |
| `ai-chat-support-demo/nextchat/.env.local` | 否 | NextChat demo 真实配置 |

### 后端最关键变量

| 模块 | 变量 | 必需性 | 说明 |
| --- | --- | --- | --- |
| SQLite | `LOCAL_DB_PATH` | 必需 | 默认 `distilled_ti_local.db`；删除它会清空本地用户、会话、AI 配置、邀请、分析记录 |
| 注册/会话 | `MIN_QUESTIONS_FOR_REPORT` | 必需 | 默认 `20`；Story/Senren report 另有 `SENREN_MIN_CHOICES_FOR_REPORT=8` |
| LLM 验收脚本 | `AI_PROVIDER`、`AI_BASE_URL`、`AI_API_KEY`、`AI_MODEL` | 完整联调必需 | 这些变量供 `python scripts\ai_acceptance.py --save` 使用；运行成功后写入 SQLite，后端运行时从 SQLite 读取 |
| 向量层 | `VECTOR_ENABLED` | 完整联调必需 | `false` 时所有向量检索/写入自动降级 |
| Embedding | `EMBEDDING_BASE_URL`、`EMBEDDING_API_KEY`、`EMBEDDING_MODEL` | 向量必需 | 推荐 SiliconFlow `BAAI/bge-m3` |
| Reranker | `RERANKER_BASE_URL`、`RERANKER_API_KEY`、`RERANKER_MODEL` | 建议 | 推荐 SiliconFlow `BAAI/bge-reranker-v2-m3`；失败会退回 embedding 排序 |
| Qdrant | `QDRANT_LOCAL_PATH` 或 `QDRANT_URL` | 向量必需 | Windows 推荐 `QDRANT_LOCAL_PATH=.qdrant-local`，不需要 Docker |
| 剧情文本 | `GALGAME_AI_SCENE_ENABLED` | 建议 | 开启后调用保存的 LLM provider，失败走自然 fallback |
| 图像生成 | `GALGAME_ASSET_GENERATION_ENABLED`、`GALGAME_ASSET_BACKEND`、`GALGAME_ASSET_API_KEY` | 可选 | 默认模板使用 Volcengine Ark；本地 SD WebUI 不需要 API key |
| 邮箱登录 | `EMAIL_PROVIDER`、`RESEND_API_KEY`、`EMAIL_FROM` | 公开测试必需 | 本地最小模板用 `EMAIL_PROVIDER=none` 和页面返回 dev code |
| Context API | `CONTEXT_ANALYSIS_API_KEY` | 共享 demo 必需 | 调用方通过 `X-Context-API-Key` 传入 |

### LLM provider：为什么要跑 `--save`

当前运行时 LLM provider 不直接从 `.env` 自动加载，而是由 Admin API 持久化到 SQLite。这样做的原因是前端 Admin 可以测试并切换 provider，同时不会把 API key 返回给浏览器。

推荐配置：

```env
AI_PROVIDER=deepseek
AI_BASE_URL=https://api.deepseek.com
AI_API_KEY=your_deepseek_key
AI_MODEL=deepseek-v4-pro
```

保存到本地 SQLite：

```powershell
cd backend
python scripts\ai_acceptance.py --save
```

也可以打开 `http://127.0.0.1:3000/admin`，在 AI 配置面板里填同样信息。DeepSeek Story Scene 默认会发送 `thinking={"type":"disabled"}`，避免 reasoning-only 输出破坏实时剧情 JSON；如果 provider 不支持扩展字段，后端会自动降级重试。

### Embedding、reranker、Qdrant

推荐配置：

```env
VECTOR_ENABLED=true
EMBEDDING_BASE_URL=https://api.siliconflow.cn/v1
EMBEDDING_API_KEY=your_siliconflow_key
EMBEDDING_MODEL=BAAI/bge-m3

RERANKER_BASE_URL=https://api.siliconflow.cn/v1
RERANKER_API_KEY=your_siliconflow_key
RERANKER_MODEL=BAAI/bge-reranker-v2-m3
```

Windows 本地优先：

```env
QDRANT_LOCAL_PATH=.qdrant-local
QDRANT_URL=
```

Docker Qdrant：

```powershell
docker run -p 6333:6333 -v ${PWD}\.qdrant-local:/qdrant/storage qdrant/qdrant
```

```env
QDRANT_LOCAL_PATH=
QDRANT_URL=http://127.0.0.1:6333
QDRANT_COLLECTION_ITEM_VECTORS=item_vectors
QDRANT_COLLECTION_SESSION_VECTORS=session_vectors
```

验收：

```powershell
cd backend
python scripts\vector_acceptance.py
```

如果 `vector_sync_failures` 不为空，先修配置或模型调用问题，再继续开发 Phase 2/3。向量失败不会阻塞用户答题，但会影响相似题、改写证据、自由文本 embedding 辅助和 Workbench 证据。

### 图像生成 provider

默认完整模板使用火山 Ark Seedream：

```env
GALGAME_ASSET_GENERATION_ENABLED=true
GALGAME_ASSET_BACKEND=volcengine_seedream
GALGAME_ASSET_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
GALGAME_ASSET_API_KEY=your_volcengine_ark_api_key
GALGAME_ASSET_MODEL=doubao-seedream-5-0-260128
GALGAME_ASSET_RESPONSE_FORMAT=url
GALGAME_ASSET_SIZE_BACKGROUND=2K
GALGAME_ASSET_SIZE_CHARACTER=2K
```

切到本地 SD WebUI：

```env
GALGAME_ASSET_BACKEND=sdwebui
GALGAME_ASSET_BASE_URL=http://127.0.0.1:7860
GALGAME_ASSET_API_KEY=
GALGAME_ASSET_MODEL=
```

关闭自动生图：

```env
GALGAME_ASSET_GENERATION_ENABLED=false
```

关闭后仍会显示 fallback/static 图或已缓存图片，不阻塞剧情。

### 邀请制、邮箱和社交推荐

公开测试建议：

```env
INVITE_BOOTSTRAP_CODE=
INVITE_BOOTSTRAP_MAX_USES=1
INVITE_DEFAULT_MAX_USES=1
USER_INVITE_MAX_USES=1
RELATIONSHIP_RECOMMENDATIONS_ENABLED=false

EMAIL_PROVIDER=resend
EMAIL_FROM="Distilled TI <no-reply@your-domain.example>"
RESEND_API_KEY=your_resend_key
AUTH_LOGIN_CODE_RETURN_IN_RESPONSE=false
```

本地烟测可以用 [backend/.env.minimal.example](backend/.env.minimal.example)，它会把 `AUTH_LOGIN_CODE_RETURN_IN_RESPONSE=true`，验证码直接显示在页面上，避免必须先配邮件。

重要坑点：

- `INVITE_BOOTSTRAP_CODE` 不应在公开页面提示用户长期使用；公开测试应在 Admin 里生成一次性邀请码。
- `USER_INVITE_MAX_USES=1` 表示每个用户生成的邀请码只能邀请一个人，用完后需要用户重新生成。
- 邮箱只用于去重和登录验证码，不在 Public/Admin 响应里展示明文邮箱。
- `RELATIONSHIP_RECOMMENDATIONS_ENABLED=false` 时 Social Lab 入口可以存在，但不会返回推荐候选。

### Context API 配置

```env
CONTEXT_ANALYSIS_API_KEY=your_context_api_key
CONTEXT_ANALYSIS_ALLOW_UNAUTH_LOCAL=false
CONTEXT_ANALYSIS_RECENT_MESSAGE_LIMIT=30
CONTEXT_ANALYSIS_STORE_RAW_MESSAGES=false
```

`CONTEXT_ANALYSIS_API_KEY` 是你自己生成的服务端接入密钥，不是第三方平台 key。外部 AI 助手调用 `/api/context/analyze` 时必须带：

```http
X-Context-API-Key: your_context_api_key
```

`CONTEXT_ANALYSIS_STORE_RAW_MESSAGES=false` 时，后端只保存证据窗口和分析结果，不保存完整原始聊天消息。

## 公开用户流程

### 邀请注册

系统默认是邀请制：

1. 管理员在 `/admin` 创建邀请码。
2. 用户在首页或 `/share?invite=...` 输入邮箱和邀请码。
3. 邮箱只存 hash，用于“一邮箱一用户”限制。
4. 注册后生成匿名 `user_id`、`user_secret`、随机 handle。
5. 用户可以生成自己的单次邀请码邀请别人。
6. 邀请关系写入匿名关系边，不暴露真实邮箱。

### 标准测量流程

1. 打开 `http://127.0.0.1:3000`。
2. 输入邀请码和邮箱，或使用已保存的本地身份。
3. 进入 `/session` 或 `/story`。
4. 满 `20` 题后生成报告。
5. 在 `/report` 查看当前报告。
6. 在 `/history` 查看历史会话。
7. 在 `/evolution` 查看长期报告演化。
8. 在 `/profile` 管理邀请、社交推荐 opt-in 和个人档案。

### 分享与导出

分享页会携带分享者的邀请码，以便建立匿名关系网络。报告分享、Profile 分享和 Evolution 入口都应优先使用当前用户的一次性邀请码。

## Story / Galgame 模式

入口：`http://127.0.0.1:3000/story`

Story Mode 的目标是让测量过程不再像问卷。用户看到的是视觉小说场景，而不是“非常同意/非常不同意”的心理题。

当前 Story Mode 已按 `gal指南.txt` 改成 Unit/Event harness：每个会话先生成 `galgame_story_plan_v2`，包含 `character_config`、20 个 `Unit`、`Narration`/`Dialogue` 事件、`WaitForPlayerInput` 和 `EndCondition`。LLM 和 fallback 都必须围绕当前 Unit 续写，不能随意跳 tag、跳地点或复读上一句角色台词。自由文本会通过 “发送自由台词” 按钮提交，同时仍保留显式选项作为低置信度回退。

进入 `/story` 后会先显示配置页，不会立刻开始答题。用户可以选择：

- `随机 Skill 角色`：从 `skills/*/persona.md` 和 `meta.json` 留存角色库中随机抽取一个角色，适合更稳定的人设和语气。
- `指定 Skill 角色`：手动选择一个角色，用于测试同一角色下的长期一致性。
- `原创自由生成`：使用项目内置原创 profile 池，不绑定既有角色，更适合每局不同的体验。

后端接口是 `GET /api/galgame/character-profiles` 和 `POST /api/session/start` 的 `story_character_mode/story_character_slug` 字段。Senren 本地模式已恢复为 `/senren`，用于本地千恋万花目录验证、启动监视、VN 场景、路线历史和报告；Web Story 继续复用角色 skill 数据，两条路径互不覆盖。

### Story Mode 怎么用

1. 启动主前端和后端。
2. 打开 `/story`。
3. 系统会复用当前活跃会话，或者自动开始新会话。
4. 每一幕显示背景、角色、旁白、台词和自然选择。
5. 用户可以点选项，也可以自己写一句台词。
6. 后端把选择或自由文本映射回测量 `option_key`。
7. 后续仍能生成标准报告、地图、聚类、历史档案。

### Story Mode 原理

每一幕背后仍有一个标准题目或实例题，但前端不展示问卷措辞。后端会构造剧情输入：

- 当前隐藏测量 seed。
- 当前角色、地点、主题。
- 最近 story turn 历史。
- 可映射的选项 key。
- 用户上一轮选择或自由文本。

LLM 生成自然 VN JSON：

- `title`
- `location`
- `narrator_text`
- `speaker`
- `dialogue`
- `choices`
- `choice_texts`
- `background_key`
- `character_key`
- `mood`

如果 LLM 失败，后端返回自然 fallback 场景，不阻塞游玩。

### 自由文本如何参与测量

用户写自己的台词后，后端会尝试三层映射：

- LLM：判断文本更接近哪个当前剧情选项。
- Embedding：比较玩家文本与各选项 anchor 的语义相似度。
- Pairwise：用成对比较器和词面信号得到分布。

融合权重当前为：

- LLM 可用时权重约 `0.56`。
- Embedding 可用时权重约 `0.24`。
- Pairwise 可用时权重约 `0.20`。

如果融合置信度低于 `GALGAME_FREE_TEXT_INFERENCE_MIN_CONFIDENCE`，就回退到用户显式选择的选项，避免强行解释自由文本。

### Story 模板后台

Admin 支持创建和管理 Story template：

- 管理端：`/admin`
- API: `/api/admin/galgame/story-templates`
- 可配置主题、故事大纲、地点、角色 key、背景 key、prompt、是否启用。
- 可手动预生成背景和角色资产。
- 可检索相似 Galgame turn。

## 图像资产生成：火山 Ark、SD WebUI 与缓存

当前资产生成方式参考 AI-GAL 的产品模式：

```text
LLM 生成剧情、地点、角色 key
  -> 后端根据场景写出 background / character prompt
  -> 图像 provider 生成图片
  -> 图片保存到 frontend/public/generated/galgame
  -> 前端按 /generated/galgame/... 或签名 backend asset URL 显示
```

### 默认：火山 Ark Seedream

完整模板默认走 GPU-free 云端生图，适合部署到没有显卡的服务器：

```env
GALGAME_ASSET_BACKEND=volcengine_seedream
GALGAME_ASSET_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
GALGAME_ASSET_MODEL=doubao-seedream-5-0-260128
GALGAME_ASSET_RESPONSE_FORMAT=url
GALGAME_ASSET_SIZE_BACKGROUND=2K
GALGAME_ASSET_SIZE_CHARACTER=2K
GALGAME_ASSET_SEQUENTIAL_IMAGE_GENERATION=disabled
GALGAME_ASSET_STREAM=false
```

后端调用：

```text
POST /api/v3/images/generations
Authorization: Bearer <GALGAME_ASSET_API_KEY>
```

坑点：

- Seedream 5.0 lite 对像素面积有下限，`1024x576` 会失败；模板使用 `2K`。
- 生成结果以 URL 返回后，后端会下载到本地 public cache，而不是把临时远端 URL 直接暴露给前端。
- 没有配置 `GALGAME_ASSET_API_KEY` 时，资产生成会失败并回退，不阻塞剧情。

### 可选：本地 SD WebUI

如果本机有 GPU 或已经启动 SD WebUI，可切换为：

```env
GALGAME_ASSET_BACKEND=sdwebui
GALGAME_ASSET_BASE_URL=http://127.0.0.1:7860
GALGAME_ASSET_API_KEY=
GALGAME_ASSET_MODEL=
```

默认端口：

```text
http://127.0.0.1:7860
```

后端会调用：

```text
GET  /sdapi/v1/sd-models
POST /sdapi/v1/txt2img
```

启动 SD WebUI 时要打开 API，例如 AUTOMATIC1111 通常需要：

```powershell
webui-user.bat --api --listen
```

本机只用本地访问时也可以不加 `--listen`，但必须有 `--api`。

### 角色、背景、缓存与用户隔离

生成文件默认写入：

```text
frontend/public/generated/galgame
```

该目录已在 `.gitignore` 中忽略，不会提交到仓库。

缓存控制：

- `GALGAME_ASSET_CACHE_MAX_FILES=300`
- `GALGAME_ASSET_CACHE_MAX_AGE_DAYS=14`
- `GALGAME_ASSET_CLEANUP_ENABLED=true`

当前策略：

- 背景可以按地点/章节/剧情阶段生成，多一点变化能提升体验。
- 角色图不应该每一幕都重生；当前按 `character_key` 复用缓存，降低费用和等待时间。
- 角色一致性更高的长期方案是 img2img、ControlNet、IP-Adapter 或 ComfyUI workflow；当前 ComfyUI 只做可用性探测，还没有 workflow adapter。
- 生成资产目前是项目级 cache，不是强用户隔离。生产化时应把路径改成 `generated/galgame/{user_id_or_session_id}/...`，并配合 TTL 清理和 per-user quota。

清理方式：

```powershell
# 通过 Admin UI 清理，或直接调用：
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8001/api/admin/galgame/assets/cleanup `
  -ContentType "application/json" `
  -Body '{"max_files":300,"max_age_days":14}'
```

### 资产相关 API

- `GET /api/admin/galgame/assets/status`
- `POST /api/admin/galgame/assets/generate`
- `POST /api/admin/galgame/assets/cleanup`
- `POST /api/admin/galgame/story-templates/{template_id}/assets`

## AI Chat 支持信号 demo

目录：[ai-chat-support-demo](ai-chat-support-demo/README.md)

这个 demo 用来证明 Distilled TI 后端不是只能处理“答题”，也能处理外部 AI 助手的长上下文。前台用户正常聊天，后台把最近聊天窗口发送到 `/api/context/analyze`，管理员在独立页面查看非诊断支持/风险信号。

### 轻量静态 demo

```powershell
cd ai-chat-support-demo
python -m uvicorn server:app --host 127.0.0.1 --port 3100 --reload
```

打开：

```text
http://127.0.0.1:3100
```

### NextChat demo

目录：[ai-chat-support-demo/nextchat](ai-chat-support-demo/nextchat/README_DISTILLED_TI.md)

推荐启动：

```powershell
cd ai-chat-support-demo
.\start-nextchat-demo.ps1 -Port 3101 -Install
```

Ubuntu / Linux：

```bash
cd ai-chat-support-demo
PORT=3101 INSTALL=auto ./start-nextchat-demo.sh
```

安装：

```powershell
cd ai-chat-support-demo\nextchat
npm install --ignore-scripts --legacy-peer-deps --package-lock=false
```

配置 `.env.local`：

```env
DISTILLED_TI_API_BASE=http://127.0.0.1:8000
DISTILLED_TI_CONTEXT_API_KEY=
DISTILLED_TI_APPLICATION_ID=nextchat-support-demo
DISTILLED_TI_ADMIN_TOKEN=
```

运行：

```powershell
npm run dev
```

如果主前端已经占用 `3000`：

```powershell
npm run mask
npx next dev -p 3101
```

后台告警页：

```text
http://127.0.0.1:3000/support-admin
```

如果使用推荐脚本的 `-Port 3101`，后台页是 `http://127.0.0.1:3101/support-admin`。

### Context API 的输出边界

Context API 输出的是：

- `risk_level`: `none | low | medium | high | crisis`
- `risk_score`
- `cluster`
- `signals`
- `immediate_actions`
- `human_review_recommended`
- `evidence_window`

它不是诊断结果。`crisis` 级别应进入人工复核和当地危机资源流程，而不是自动惩罚、封号或贴标签。

## API 总览

所有主后端 API 默认带 `/api` 前缀。

### Public API

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/api/health` | 健康检查 |
| `POST` | `/api/invite/redeem` | 邀请码 + 邮箱注册 |
| `GET` | `/api/user/me` | 当前用户档案 |
| `PATCH` | `/api/user/me` | 更新用户配置 |
| `POST` | `/api/user/invite/claim` | 领取别人分享的邀请码关系 |
| `POST` | `/api/user/invite/generate` | 生成当前用户的一次性邀请码 |
| `GET` | `/api/user/sessions` | 用户历史会话 |
| `GET` | `/api/user/evolution` | 用户长期演化 |
| `GET` | `/api/user/recommendations` | 用户推荐候选 |
| `POST` | `/api/user/session/{session_id}/access` | 为历史会话重新签发访问凭证 |
| `GET` | `/api/user/galgame/story-templates` | 用户自定义 Story 模板列表 |
| `POST` | `/api/user/galgame/story-templates` | 创建用户 Story 模板 |
| `PUT` | `/api/user/galgame/story-templates/{template_id}` | 更新用户 Story 模板 |
| `DELETE` | `/api/user/galgame/story-templates/{template_id}` | 删除用户 Story 模板 |
| `GET` | `/api/galgame/character-profiles` | Web Story 可选角色 profile / skill 列表 |
| `POST` | `/api/session/start` | 开始测量会话 |
| `POST` | `/api/question/next` | 获取下一题 |
| `POST` | `/api/response/submit` | 提交选择题回答 |
| `GET` | `/api/session/{session_id}/summary` | 当前会话摘要 |
| `GET` | `/api/session/{session_id}/workbench/evidence` | Workbench 证据 |
| `GET` | `/api/session/{session_id}/galgame/scene` | 获取 Story 当前幕 |
| `POST` | `/api/session/{session_id}/galgame/respond` | 提交 Story 选择或自由文本 |
| `GET` | `/api/session/{session_id}/report` | 获取报告 |
| `POST` | `/api/session/{session_id}/report` | 生成报告 |
| `GET` | `/api/session/{session_id}/map` | 获取地图投影 |
| `DELETE` | `/api/session/{session_id}` | 丢弃会话 |

### Context API

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `POST` | `/api/context/analyze` | 分析外部聊天上下文 |
| `GET` | `/api/context/analyses` | 查询某用户/会话分析历史 |
| `GET` | `/api/context/alerts` | 查询中高风险支持信号列表 |

最小请求示例：

```json
{
  "application_id": "acme-chat",
  "external_user_id": "anon-user-001",
  "conversation_id": "thread-001",
  "consent_basis": "user accepted product safety support policy",
  "messages": [
    { "role": "assistant", "content": "我在，你想先说哪部分？" },
    { "role": "user", "content": "最近真的撑不住了，感觉没有出路。" }
  ],
  "persist": true,
  "persist_messages": false
}
```

### Admin API

Admin API 默认只允许本机访问。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/api/health` | Admin 健康检查 |
| `POST` | `/api/session/{session_id}/access` | 管理端签发会话访问凭证 |
| `POST` | `/api/ai/config` | 配置 LLM provider |
| `GET` | `/api/ai/config` | 查看 LLM 配置状态 |
| `POST` | `/api/ai/rewrite-question` | 题目改写预览 |
| `POST` | `/api/admin/invites` | 创建邀请码 |
| `GET` | `/api/admin/invites` | 邀请码列表 |
| `GET` | `/api/admin/users` | 用户列表 |
| `GET` | `/api/admin/users/relationships` | 匿名关系边列表 |
| `GET` | `/api/admin/users/{user_id}/recommendations` | 指定用户推荐候选 |
| `POST` | `/api/admin/vector/reindex` | 重建向量索引 |
| `GET` | `/api/admin/vector/templates/similar` | 相似题检索 |
| `GET` | `/api/admin/vector/sessions/similar` | 相似会话检索 |
| `GET` | `/api/admin/vector/galgame-turns/similar` | 相似 Story turn 检索 |
| `GET` | `/api/admin/vector/sync-failures` | 向量同步失败记录 |
| `GET` | `/api/admin/galgame/story-templates` | 管理 Story 模板 |
| `POST` | `/api/admin/galgame/story-templates` | 创建 Story 模板 |
| `PUT` | `/api/admin/galgame/story-templates/{template_id}` | 更新 Story 模板 |
| `DELETE` | `/api/admin/galgame/story-templates/{template_id}` | 删除 Story 模板 |
| `GET` | `/api/admin/galgame/assets/status` | 查看 Galgame 资产状态 |
| `POST` | `/api/admin/galgame/assets/generate` | 手动生成背景/角色 |
| `POST` | `/api/admin/galgame/assets/cleanup` | 清理生成资产 |
| `POST` | `/api/admin/galgame/story-templates/{template_id}/assets` | 为模板预生成资产 |
| `GET` | `/api/admin/templates` | 题库模板列表 |
| `POST` | `/api/admin/item-template/create` | 创建题目模板 |
| `PUT` | `/api/admin/item-template/{template_id}` | 更新题目模板 |
| `POST` | `/api/admin/item-template/{template_id}/archive` | 归档题目模板 |
| `DELETE` | `/api/admin/item-template/{template_id}` | 删除题目模板 |
| `GET` | `/api/admin/item-instances` | 生成实例题列表 |
| `GET` | `/api/admin/sessions` | 会话列表 |
| `POST` | `/api/admin/cleanup` | 清理过期会话 |
| `GET` | `/api/admin/clusters/overview` | 聚类概览 |
| `POST` | `/api/admin/clusters/label-override` | 覆盖聚类标签 |

### Vector reindex scope

`POST /api/admin/vector/reindex` 支持：

```json
{ "scope": "templates" }
{ "scope": "instances" }
{ "scope": "sessions" }
{ "scope": "galgame_turns" }
{ "scope": "all" }
```

## 数据、隐私与邀请关系

### SQLite

默认数据库：

```text
distilled_ti_local.db
```

存储内容包括：

- 会话状态。
- 题目实例。
- 用户 profile。
- 邮箱 hash。
- 邀请码。
- 匿名关系边。
- Story turn。
- 向量同步失败记录。
- Context API 分析记录。

### 向量数据

向量数据存储在：

- Qdrant local path，例如 `.qdrant-local`。
- 或 Qdrant server，例如 `http://127.0.0.1:6333`。

集合：

- `item_vectors`
- `session_vectors`

### 不要提交的内容

以下内容已在 `.gitignore` 中忽略：

- 真实 `.env` 和 `.env.*`；模板 `.env.example`、`.env.minimal.example`、`.env.local.example` 例外。
- 本地数据库。
- Qdrant 本地目录。
- 生成的 Galgame 图片。
- `node_modules`
- `.next`
- local secret 文件。

真实 API key 只应保存在本地 `.env` 或本机 secret 文件中。

## 开发指南

### 项目结构

```text
distilled TI/
├─ backend/
│  ├─ app/
│  │  ├─ api/                    # public/admin routes 与 API schemas
│  │  ├─ core/                   # Settings 与环境变量
│  │  ├─ domain/                 # 维度、题库、领域模型
│  │  ├─ services/               # 会话、评分、聚类、LLM、向量、资产、存储
│  │  ├─ main.py                 # Public API 入口
│  │  └─ admin_main.py           # Admin API 入口
│  ├─ scripts/                   # acceptance scripts
│  ├─ tests/                     # pytest
│  └─ pyproject.toml
├─ frontend/
│  ├─ app/                       # Next.js App Router 页面
│  ├─ components/                # 主前端组件
│  └─ lib/                       # API 封装和本地状态
├─ ai-chat-support-demo/
│  ├─ static/                    # 轻量聊天 demo
│  └─ nextchat/                  # NextChat 改造版
├─ docs/
│  ├─ context-support-api.md
│  ├─ development-guide.md
│  ├─ development-log.md
│  ├─ dimensions.md
│  └─ plans/
├─ figure/
├─ start-dev.bat
└─ start-dev.ps1
```

### 主前端页面

| 路由 | 用途 |
| --- | --- |
| `/` | Landing、注册、入口选择 |
| `/session` | 标准答题 |
| `/story` | Galgame / VN 模式 |
| `/senren` | Senren 本地游戏入口，验证本地游戏目录并启动监视会话 |
| `/senren/monitor` | Senren 本地游戏 VN 监视视图 |
| `/senren/history` | Senren 路线历史 |
| `/report` | 当前报告 |
| `/report/[sessionId]` | 历史报告 |
| `/history` | 历史会话恢复 |
| `/evolution` | 长期演化 |
| `/profile` | 用户档案、邀请、推荐 opt-in |
| `/share` | 分享和邀请码入口 |
| `/admin` | 本地管理台 |

### 开发新测量题

建议只通过 Admin UI 或 `ItemTemplateCreate` 写入：

- 必须给出清晰 `dimension_weights`。
- 尽量给 `scenario_tags`，便于去重和 Story 化。
- 不要让单题同时强影响过多维度。
- 允许 `allow_rewrite=true` 的题可以进入 AI 改写预览。
- 修改题库后可执行 vector reindex。

### 开发新 Story 模板

Story 模板应描述“场景和角色”，不要写成心理测评题：

- `theme`
- `outline`
- `location`
- `speaker`
- `background_key`
- `character_key`
- `background_prompt`
- `character_prompt`

测量目的保留在后端隐藏 seed，不要进入主画面。

### 开发新向量对象

当前原则：

- 业务侧不要自己拼 embedding 输入。
- 所有对象通过 `EmbeddingService` 构造 canonical text。
- 向量写入通过 `VectorIndexer`。
- 失败走 `vector_sync_failures`，不阻塞用户操作。

## 测试与验收

### 后端测试

```powershell
cd backend
$env:VECTOR_ENABLED='false'
$env:GALGAME_AI_SCENE_ENABLED='false'
$env:GALGAME_ASSET_GENERATION_ENABLED='false'
pytest -q
```

### 前端测试

```powershell
cd frontend
npm run lint
npm run build
```

### NextChat demo 验证

```powershell
cd ai-chat-support-demo\nextchat
npm install --ignore-scripts --legacy-peer-deps --package-lock=false
npx tsc --noEmit --pretty false
npm run build
```

已知 upstream NextChat 的 `npm run lint` 在当前依赖组合下可能触发 `unused-imports/no-unused-imports` 规则崩溃；这不阻断 `next build`。

### 真实联调建议顺序

1. 启动 Public API、Admin API、主前端。
2. 配置 DeepSeek LLM provider。
3. 配置 SiliconFlow embedding/reranker。
4. 选择 Qdrant local path 或 Docker Qdrant。
5. 在 Admin 执行 `templates` reindex。
6. 执行 `instances`、`sessions`、`galgame_turns` reindex。
7. 用相似题、相似会话、相似 Story turn 检索做 smoke。
8. 如果使用火山 Ark，确认 `GALGAME_ASSET_API_KEY` 已填；如果使用 SD WebUI，启动 `7860` 并打开 API。
9. 在 Admin 检查 Galgame asset status，云端模式应显示 `cloud_configured=true`。
10. 打开 `/story` 验证剧情、选择、自由文本和生成图片。
11. 启动 NextChat demo，打开 `/support-admin` 验证 Context API 告警。

## 给智能体/CC/Codex 的安装验收清单

这一段给自动化 agent 使用，目标是“下载仓库后按步骤配置、启动、验收，不要猜”。

### 0. 初始约束

- 不要把任何用户提供的真实 API key 写入 git。
- 不要提交 `backend/.env`、`frontend/.env.local`、生成图片、SQLite DB、Qdrant 本地目录。
- 如果只做文档/前端改动，不要启动外部付费 API。
- Windows PowerShell 下不要使用 Bash here-doc；用原生命令或脚本。
- 当前分支如已有用户改动，先 `git status --short --branch`，不要 reset 或 checkout 覆盖。

### 1. 依赖安装

```powershell
cd "F:\学习和研究\新鲜玩意\distilled TI-codex-795e"

cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e .[dev]

cd ..\frontend
npm install
```

### 2. 选择配置档

无 key 烟测：

```powershell
cd "F:\学习和研究\新鲜玩意\distilled TI-codex-795e"
Copy-Item backend\.env.minimal.example backend\.env -Force
Copy-Item frontend\.env.local.example frontend\.env.local -Force
```

完整联调：

```powershell
cd "F:\学习和研究\新鲜玩意\distilled TI-codex-795e"
Copy-Item backend\.env.example backend\.env -Force
Copy-Item frontend\.env.local.example frontend\.env.local -Force
```

完整联调至少要替换：

- `AI_API_KEY`
- `EMBEDDING_API_KEY`
- `RERANKER_API_KEY`
- `RESEND_API_KEY`
- `GALGAME_ASSET_API_KEY`
- `CONTEXT_ANALYSIS_API_KEY`
- `EMAIL_FROM`

### 3. 保存 LLM provider

`.env` 里的 `AI_*` 只供验收脚本读取。必须执行：

```powershell
cd backend
python scripts\ai_acceptance.py --save
```

看到 `ai_test_ok: True` 和 `saved_to_local_store: True` 后，Story Scene、报告、rewrite、probe 才会使用该 provider。

### 4. 向量验收

```powershell
cd backend
python scripts\vector_acceptance.py
```

期望：

- `vector_enabled: True`
- `embedding_dimension` 大于 `0`
- `reranker_enabled: True`
- `recent_failures: 0`

如果使用 `QDRANT_LOCAL_PATH=.qdrant-local`，不需要 Docker。如果改成 `QDRANT_URL=http://127.0.0.1:6333`，先启动 Qdrant。

### 5. 启动主应用

```powershell
cd "F:\学习和研究\新鲜玩意\distilled TI-codex-795e"
.\start-dev.ps1
```

确认：

- Public API: `http://127.0.0.1:8000/docs`
- Admin API: `http://127.0.0.1:8001/docs`
- Frontend: `http://127.0.0.1:3000`

首页入口：

- `/session`：标准答题。
- `/story`：Web Galgame Story Mode。
- `/senren`：Senren 本地游戏模式；用于本地目录验证、启动游戏、选择监视和路线报告。
- `/history`、`/evolution`、`/profile`：长期历史、演化、用户邀请。
- `/admin`：本机管理端。

### 6. 手工 smoke

最少验收：

1. 打开 `/admin`，创建一次性 invite。
2. 打开 `/`，用 invite + 邮箱注册。
3. 打开 `/session`，答 2-3 题，确认能继续出题。
4. 打开 `/story`，确认剧情不是问卷措辞，选项可推进。
5. 打开 `/senren`，输入本地千恋万花目录，确认验证、启动监视、`/senren/monitor` 和 `/senren/report` 可用。
6. Admin 执行 vector reindex：`templates`、`instances`、`sessions`、`galgame_turns`。
7. Admin 查看 similar templates/sessions/galgame turns。
8. Admin 查看 `vector_sync_failures`，期望为空。
9. Admin 查看 Galgame asset status，若开启云端生图，应显示 `cloud_configured=true`。
10. 用 Story 或 Admin 手动生成一张背景，确认保存到 `frontend/public/generated/galgame`。

### 7. 回归命令

```powershell
cd backend
pytest -q

cd ..\frontend
npm run lint
npm run build
```

当前允许存在的已知前端 lint 警告：`StoryClient.tsx` 的两个 `<img>` 性能警告。新增错误或构建失败必须修。

### 8. 常见故障

| 现象 | 常见原因 | 处理 |
| --- | --- | --- |
| Story Scene 一直 fallback | 没执行 `ai_acceptance.py --save`，或 provider 返回非 JSON | 先跑脚本；必要时在 Admin 重新保存 provider |
| 有云端生图 key 但不生成图 | `GALGAME_ASSET_GENERATION_ENABLED=false` 或 backend 没重启 | 改 `.env` 后重启 Public/Admin API |
| 火山返回尺寸错误 | 使用了 `1024x576` 这类低像素尺寸 | 用 `GALGAME_ASSET_SIZE_BACKGROUND=2K` |
| SD WebUI 不通 | 没用 `--api` 启动，或端口不是 `7860` | 检查 `http://127.0.0.1:7860/sdapi/v1/sd-models` |
| Context API 401 | 没带 `X-Context-API-Key` | 配置同一个 `CONTEXT_ANALYSIS_API_KEY` 到 demo |
| 登录收不到邮件 | Resend 域名未验证、`EMAIL_FROM` 域名不匹配、key 错 | 先用 minimal 模板 dev code；再修 Resend |
| 新用户不知道邀请码 | Admin 未创建 invite，或 bootstrap code 为空 | 在 `/admin` 创建一次性 invite |
| 邀请码被多人共用 | `max_uses` 太大 | `INVITE_DEFAULT_MAX_USES=1`、`USER_INVITE_MAX_USES=1` |
| 生成图片占空间 | cache 未清理 | 调 Admin cleanup，或降低 `GALGAME_ASSET_CACHE_MAX_FILES/MAX_AGE_DAYS` |
| 前端请求错端口 | 没有复制 `frontend/.env.local` | 用 `frontend/.env.local.example` 重新复制 |

## 已知限制

- 本项目仍是本地优先原型，不是生产 SaaS。
- Context API 是非诊断支持信号，不是医疗诊断。
- `relationship_recommendations_enabled` 默认应谨慎开启，公开推荐/社交功能需要隐私文案和滥用控制。
- Qdrant local path 适合 Windows 本地开发，但多进程同时写入时仍需注意锁。
- SD WebUI 生成质量取决于本地模型、prompt、采样器和显存。
- 角色一致性目前主要依赖 `character_key` 缓存复用，尚未实现完整 img2img / ControlNet 工作流。
- ComfyUI adapter 尚未实现生成 workflow。
- 音频目前是 fallback/static 路径，未接真实音频生成。
- NextChat demo 保留 upstream NextChat 大量文件，后续可裁剪成更小的企业接入 SDK 示例。

## 文档入口

- [docs/development-guide.md](docs/development-guide.md)
- [docs/development-log.md](docs/development-log.md)
- [docs/context-support-api.md](docs/context-support-api.md)
- [docs/dimensions.md](docs/dimensions.md)
- [docs/plans/2026-04-13-embedding-vector-layer-adr.md](docs/plans/2026-04-13-embedding-vector-layer-adr.md)
- [docs/plans/2026-05-12-galgame-story-mode.md](docs/plans/2026-05-12-galgame-story-mode.md)
- [ai-chat-support-demo/README.md](ai-chat-support-demo/README.md)
- [ai-chat-support-demo/nextchat/README_DISTILLED_TI.md](ai-chat-support-demo/nextchat/README_DISTILLED_TI.md)

## 免责声明

Distilled TI 当前用于本地实验、交互体验、结构化自测、产品安全研究和后端架构验证。它不构成临床诊断、医疗建议、心理治疗、危机干预自动系统或高风险决策系统。涉及自伤、自杀、暴力风险、未成年人保护、就业、教育、金融、保险等高风险场景时，必须由合规流程和受训人员人工复核。
