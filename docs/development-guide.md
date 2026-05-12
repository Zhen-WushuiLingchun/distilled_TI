# Distilled TI 开发指南

这份文档面向开发者，目标不是介绍“怎么使用产品”，而是解释这个项目目前是如何工作的：

- 核心对象和重要函数分别负责什么
- 连续答题如何逐步形成画像
- 聚类到底基于哪些特征
- AI 现在真实介入了哪些环节
- embedding / reranker / Qdrant 向量层现在如何接入
- 邀请制匿名用户和长期历史如何工作
- 题库、模板、实例题之间是什么关系
- 如何理解“收敛”“不确定性”“报告”
- 如何进一步做反作弊、识别瞎答题或伪造答题
- 接下来还有哪些值得开发的方向

## 1. 总体架构

当前系统可以分成 8 层：

1. `domain`
   - 定义核心维度、子维度、模块维度、题目模板、题目实例、会话状态、报告结构等数据模型
2. `item_bank`
   - 提供初始 seed 题库
3. `session_service`
   - 负责整个会话生命周期：启动、发题、收答案、生成报告、生成地图、管理模板
4. `scoring`
   - 把一次回答更新到 `SessionState`
5. `clustering`
   - 把当前会话状态映射到聚类空间，并提供 2D 投影
6. `ai_service`
   - 在配置 API provider 后，为改写题目、生成 probing 题、命名和总结报告提供增强
7. `vector layer`
   - 由 `embedding_service`、`vector_store`、`vector_indexer`、`reranker_service` 组成
   - 负责题目向量、会话快照向量、相似检索、rerank 精排和 best-effort 同步
8. `user_service`
   - 负责邀请码兑换、匿名用户档案、长期会话归属、邀请关系边和隐藏推荐候选
   - 不保存真实姓名、手机号、邮箱或学校身份

一个典型请求流大致如下：

1. 用户调用 `POST /api/session/start`
2. `SessionService.start_session()` 初始化 `SessionState`
3. `SessionService._generate_next_instance()` 选模板并生成本次展示题
4. 用户作答后调用 `POST /api/response/submit`
5. `ScoringEngine.apply_response()` 更新 `core_mu / core_sigma / sub_mu / module_scores / zeta`
6. 如果题数命中 `5 / 10 / 20 / 40` milestone，`VectorIndexer.index_session_snapshot()` best-effort 写入 `session_vectors`
7. 再由 `SessionService` 选择下一题
8. 达到最小题量后，`ScoringEngine.build_report()` + `ClusteringService` 输出结构化报告

如果用户先通过邀请码进入：

1. 用户调用 `POST /api/invite/redeem`
2. `UserService.redeem_invite()` 创建随机 `user_id`、随机 `handle` 和 `user_secret`
3. 前端把 `user_id / user_secret / handle` 保存到 localStorage
4. 后续 `POST /api/session/start` 会带上 `X-User-Id` 和 `X-User-Secret`
5. `SessionRecord.user_id` 被写入 SQLite，session TTL 从短期 TTL 切换为 `REGISTERED_SESSION_TTL_DAYS`
6. `/api/user/sessions` 可以列出该匿名用户的长期历史
7. `/api/user/session/{session_id}/access` 可以为用户自己的历史会话重新签发 session secret

所有向量写入都是辅助层：

- 主流程成功后才尝试写向量
- 向量失败只记录 `vector_sync_failures`
- 不阻塞新建模板、生成实例题、提交回答、改写预览

## 2. 核心数据结构

### 2.0 `UserProfile`、`InviteCode` 与 `UserRelationship`

邀请制用户层定义在 `backend/app/domain/models.py`，业务逻辑在 `backend/app/services/user_service.py`。

关键约束：

- `UserProfile.user_id` 是随机 ID。
- `UserProfile.handle` 是随机用户名，供 Public/Admin 展示。
- `user_secret_hash` 只保存哈希，不返回给前端。
- `InviteCode` 控制入口，支持 `max_uses / use_count / active / expires_at`。
- `UserRelationship` 当前只记录 `invited` 类型的邀请边。
- `SessionRecord.user_id` 用于把会话归属到匿名用户。

Public 侧只允许用户访问自己的档案和自己的 session。Admin 侧可以查看匿名用户、邀请、关系边和隐藏推荐候选。

隐藏推荐由 `RELATIONSHIP_RECOMMENDATIONS_ENABLED` 控制，默认关闭。即使开启，也要求用户设置 `recommendation_opt_in=true`，并且只在 Admin 实验视图展示候选，不进入公开页面。

### 2.1 `SessionState`

`SessionState` 是整个系统最重要的对象，它定义在 `backend/app/domain/models.py`。

其中最关键的字段：

- `core_mu`
  - 10 个核心维度的当前估计值
  - 可以理解为“当前画像中心”
- `core_sigma`
  - 每个核心维度的不确定性
  - 值越低，说明这个维度在当前问答下越稳定
- `sub_mu / sub_sigma / sub_counts`
  - 子维度的估计值、不确定性、样本数
- `module_scores / module_counts`
  - 场景模块分数，例如 `study_style`、`team_mode`
- `zeta`
  - 一组状态信号
  - 当前包含：`consistency`、`performative`、`exploration`、`fatigue`
- `answers`
  - 每一道题的回答记录
- `question_count`
  - 当前总题数

### 2.2 `ItemTemplate` 与 `ItemInstance`

这两个概念必须分清：

- `ItemTemplate`
  - 模板题
  - 描述“测什么”
  - 包含维度载荷、子维度载荷、模块亲和度、区分度、难度、题面、选项
- `ItemInstance`
  - 会话中实际发给用户的一次题目实例
  - 描述“这次具体给用户看到什么”
  - 它可能是模板原文，也可能是 AI 改写版本，也可能是 probe 题

也就是说：

- 模板是测量骨架
- 实例是会话上下文中的一次具体呈现

## 3. 重要函数说明

下面按职责列出最关键的函数。

### 3.1 `SessionService`

`backend/app/services/session_service.py`

#### `start_session()`

职责：

- 创建新会话
- 初始化空状态
- 立即生成第一题
- 签发 `session_secret` 和 `delete_token`

这意味着会话一创建，就已经进入“可连续作答”的状态。

#### `_new_state()`

职责：

- 初始化一个零状态的 `SessionState`
- 设定核心维度、子维度、模块维度的默认值
- 用 `settings.default_sigma` 初始化不确定性

它决定了系统的“先验状态”。

#### `select_next_question()`

职责：

- 在当前题库里为某个会话计算“下一题最值得问什么”

它不是随机选题，而是综合多个因素打分：

- `uncertainty_gain`
  - 这题是否覆盖当前仍然不确定的维度
- `coverage_penalty`
  - 某些维度是否已经问太多了
- `novelty_bonus`
  - 场景是否有新鲜度
- `recency_penalty`
  - 最近是否问过太像的题
- `semantic_penalty`
  - 题面语义是否和近期题太相似
- `scenario_penalty`
  - 场景标签是否过度重复
- `phase_bonus`
  - 当前答题阶段更偏向 core、sub 还是 module
- `AI rewrite bonus`
  - 如果启用 AI 改写且最近改写占比偏低，会轻微提高可改写题优先级

这基本上就是当前系统的“主动测量策略”。

#### `_generate_next_instance()`

职责：

- 决定下一题到底是普通模板题，还是 probe 题
- 若是普通题，则走模板选择与实例化
- 若是 probe 题，则调用 AI 或 fallback 逻辑生成
- 实例题保存成功后，best-effort 写入 `item_vectors`

可以把它理解成整个问卷引擎的总调度器。

#### `_should_generate_probe()`

职责：

- 决定当前时点是否值得插入 probing 题

它考虑：

- 当前总题数是否达到阈值
- probe 题总数是否已达上限
- 最近题目里 probe 比例是否过高
- 最近是否刚问过 probe
- 是否已配置 AI

probe 题不是每次都出，而是“在合适的时机对模糊区域加压”。

#### `_generate_probe_instance()`

职责：

- 从候选 probe 维度里挑出最值得追问的方向
- 调用 `AIService.generate_probe_question()` 生成 probing 题
- 如 AI 不可用则回退到规则化 fallback
- 生成 `ItemInstance(layer="probe")`

#### `submit_answer()`

职责：

- 接收用户作答
- 调用 `ScoringEngine.apply_response()` 更新状态
- 如果题数达到 `SESSION_VECTOR_MILESTONES`，best-effort 写入一条 `session_vectors` 快照
- 再次生成下一题

这是会话持续推进的主入口。

#### `build_workbench_checkpoint()`

职责：

- 为用户端 Session Workbench 生成可解释 checkpoint 摘要
- 输出报告进度、session vector milestone、top core signals、不确定性队列、活跃模块、已解锁子维度
- 只做解释和展示，不参与评分、不参与选题

该字段会作为可选扩展出现在：

- `POST /api/session/start`
- `POST /api/response/submit`
- `GET /api/session/{session_id}/summary`

#### `build_workbench_evidence()`

职责：

- 为用户端 Session Workbench 生成按需加载的检索证据
- 复用 `VectorIndexer.build_rewrite_retrieval_context()` 和 `VectorIndexer.search_similar_sessions()`
- 输出相近模板、历史实例题、历史改写候选和匿名 session snapshot 的安全摘要
- 只暴露 `high / medium / low` confidence tier，不暴露 raw vector score 或 raw rerank score
- 如果向量层不可用，返回说明性 `notes`，不影响答题主链路

公开入口：

- `GET /api/session/{session_id}/workbench/evidence`

安全边界：

- 必须带 `X-Session-Secret`
- 不返回其他会话的原始 `session_id`
- 不返回 session snapshot canonical text
- 检索证据只能用于解释当前选题，不能作为最终人格结论

#### Session Workbench report preview

职责：

- 用户达到 `MIN_QUESTIONS_FOR_REPORT` 后，在 `/session` 内按需生成报告预览
- 预览调用现有 `POST /api/session/{session_id}/report`
- 不保存 final report snapshot
- 不跳转 `/report`
- 不阻止用户继续答题

预览内容：

- `narrative_label`
- `cluster_name`
- `ai_summary`
- `question_count`
- `cluster_confidence`
- `uncertainty_summary`
- top structural signals
- salient subdimensions / active modules

完整报告仍由“进入完整报告页”或“生成并查看报告”触发：

- 同时读取 `SessionReport`
- 同时读取 `SessionMap`
- 写入 frontend session storage 的 final report snapshot
- 跳转 `/report`

#### `build_report()`

职责：

- 检查题数是否达到可出报告阈值
- 刷新聚类模型
- 生成结构化报告

#### `build_map()`

职责：

- 生成当前画像点位
- 回放每一道题后的状态轨迹
- 计算轨迹点、答题点、簇中心和簇区域

这个函数把“抽象画像”投影成用户可视化轨迹。

### 3.2 `ScoringEngine`

`backend/app/services/scoring.py`

#### `predict_score()`

职责：

- 基于当前 `core_mu` 和题目的 `dimension_weights`
- 用 `tanh(discrimination * (dot - difficulty))`
- 预测用户对该题大概会作出的倾向性回答

它可以看作一个简化版项目反应 / 连续潜变量预测函数。

#### `apply_response()`

职责：

- 读取用户真实作答分值
- 与预测值比较，计算 `residual = observed - predicted`
- 根据残差更新会话状态

这是全系统最核心的更新方程。

它做了几件事：

1. 更新核心维度
   - `core_mu += eta * residual * weight`
2. 更新核心不确定性
   - `core_sigma` 会随着有效观测逐步收缩
3. 更新子维度
   - 只有父维度覆盖达到阈值后，子维度才真正解锁
4. 更新模块分数
   - 模块不是主轴，而是场景投影层
5. 记录答案历史
   - 包括预测分、残差、响应时长
6. 更新 `zeta`
   - `exploration` 随题数上升
   - 若残差极大，则 `consistency` 下降
   - 若残差较平稳，则 `consistency` 上升
   - 若延迟很短，`fatigue` 会升高

#### `build_report()`

职责：

- 根据当前状态生成正式报告
- 计算结构标签、聚类混合、核心条形图、子维度条形图、模块条形图
- 输出 `uncertainty_summary`
- 调用 AI 生成更有辨识度的命名与摘要

### 3.3 `ClusteringService`

`backend/app/services/clustering.py`

#### `feature_vector()`

职责：

- 把一个 `SessionState` 压成聚类向量

当前用到的特征包括：

- 10 个核心维度 `core_mu`
- `zeta.consistency`
- `zeta.performative`
- `zeta.exploration`
- `zeta.fatigue`
- 极端回答比例 `extreme_ratio`
- 中位响应时长 `median_latency / 5000`
- 解锁子维度数量
- 激活模块数量

这点很关键：

当前聚类并不只看“人格维度方向”，也把答题行为风格纳入特征。

#### `refresh()`

职责：

- 从历史会话里提取特征向量
- 追加一组 synthetic reference vectors
- 运行 `KMeans`
- 更新聚类中心、投影基础和版本签名

其中 synthetic reference vectors 的作用是：

- 在真实样本少时，给聚类空间一些基础骨架
- 避免模型在冷启动阶段完全塌到很小的局部区域

#### `cluster_memberships_for_state()`

职责：

- 计算当前状态到各簇中心的距离
- 用 `exp(-distance)` 转成 soft membership
- 返回前 `top_k` 个簇及其权重

这意味着系统输出的不是“你绝对属于某一类”，而是“你当前最接近哪些簇、接近程度多少”。

#### `project_state()` / `project_template_vector()`

职责：

- 把高维状态投到 2D 平面

其中有两套投影：

- `auto/core`
  - 基于 SVD 做数据驱动投影
- `structure`
  - 用规则定义的社交轴 / 结构轴做解释型投影

#### `_build_cluster_regions()`

职责：

- 用投影点的协方差估计每个簇的 2D 区域
- 输出一个近似椭圆区域

前端地图中的 cluster region 就来自这里。

### 3.4 `GenerationService`

`backend/app/services/generation.py`

#### `choose_template()`

职责：

- 从已经排序好的候选模板里再做一次轻量随机化选择

特点：

- 每 7 题左右会优先考虑 anchor 题
- 尽量避开最近问过的模板
- 在 top window 中做有约束的随机

这让系统不会死板地总是选同一路线。

#### `materialize_instance()`

职责：

- 把 `ItemTemplate` 变成一次真正发出的 `ItemInstance`
- 必要时先做 AI 改写
- 记录这次题目来自模板原文、AI 改写还是 anchor

#### `preview_rewrite()`

职责：

- 在调用 LLM 前先检索相近模板、相近实例题、历史改写候选
- 把检索证据压缩成 `retrieval_context`
- 生成多个候选改写
- 去重
- 结合规则分、embedding 分和 reranker 后的近邻证据评分
- 选出最优版本

#### `_score_candidate()`

职责：

- 给每个改写候选打分

当前考虑的因素：

- 是否通过约束校验
- 相对模板的措辞新颖度
- 长度是否接近目标区间
- 是否有明确场景锚点
- 与历史题面的相似度惩罚
- 与原模板的 embedding 安全距离
- 与现有题库近邻过近时的 duplicate penalty
- 同维度/同层近邻对齐时的 alignment bonus
- 是否来自 LLM 改写

这说明 AI 不是“生成啥就用啥”，而是被一个规则层再筛一遍。

### 3.5 `AIService`

`backend/app/services/ai_service.py`

当前 AI 真实参与 4 个环节：

#### `test_config()`

- 测试 provider 是否能通

#### `rewrite_template_candidates()`

- 基于模板和约束生成多个改写候选
- 输出 JSON
- 再由本地校验器过滤

#### `interpret_report_with_config()`

- 对结构化报告做更有辨识度的命名与总结
- 如果失败会回退到规则生成的文本

#### `generate_probe_question()`

- 让模型在若干候选 probe 维度里选最值得追问的一个
- 决定输出 statement 型还是 contrast 型 probing 题

### 3.6 Vector Layer

向量层由 4 个服务组成：

#### `EmbeddingService`

`backend/app/services/embedding_service.py`

- 调用 OpenAI-compatible `/embeddings`
- 当前本地联调使用 SiliconFlow `BAAI/bge-m3`
- 统一生成 canonical text，业务侧不直接拼 embedding 输入
- 支持模板、实例题、改写候选、会话 milestone 快照

#### `VectorStore`

`backend/app/services/vector_store.py`

- 封装 Qdrant collection 创建、upsert、search、delete
- 本地 Windows 开发优先使用 `QDRANT_LOCAL_PATH=.qdrant-local`
- Docker Qdrant 仍可通过 `QDRANT_URL=http://127.0.0.1:6333` 使用
- 业务 ID 会稳定映射成 UUID 写入 Qdrant，原始 ID 保留在 payload

#### `VectorIndexer`

`backend/app/services/vector_indexer.py`

- 负责 `index_template`
- 负责 `index_item_instance`
- 负责 `index_rewrite_candidate`
- 负责 `index_session_snapshot`
- 负责 `reindex(templates | instances | sessions | all)`
- 所有主链路调用都是 best-effort，失败只写 `vector_sync_failures`

#### `RerankerService`

`backend/app/services/reranker_service.py`

- 调用 OpenAI-compatible `/rerank`
- 当前本地联调使用 SiliconFlow `BAAI/bge-reranker-v2-m3`
- 只用于 embedding 召回后的 top-k 精排
- 不接管评分、选题、聚类或报告结论

必须强调：

- AI 当前不是评分器
- AI 不直接决定最终人格结论
- AI 更像“语言生成增强层”和“局部提问策略增强层”

## 4. 题库、模板与测量层级

### 4.1 题库结构

seed 题库定义在 `backend/app/domain/item_bank.py`。

当前题库大致分成几层：

- `core`
  - 直接测 10 个核心维度
- `sub`
  - 测更细的子维度
- `module`
  - 测不同场景中的投影模块
- `probe`
  - AI 或 fallback 生成的追问题
- `anchor`
  - 用于周期性校准的一类题

### 4.2 模板里的关键字段

每个模板通常有这些关键参数：

- `dimension_weights`
  - 主测哪些核心维度
- `subdimension_weights`
  - 若该题也用于子维度细化，则在这里表达
- `module_affinities`
  - 这题更容易激活哪个场景模块
- `discrimination`
  - 区分度
- `difficulty`
  - 难度 / 门槛
- `scenario_tags`
  - 场景标签，用于避免重复和增强情境覆盖
- `is_anchor`
  - 是否为锚题
- `allow_rewrite`
  - 是否允许 AI 改写

### 4.3 模板校验

模板写入时会经过 `validators.py`。

当前硬约束包括：

- 一题至少测一个核心维度
- 最多映射 3 个维度
- 主测维度不能超过 2 个
- 题面长度限制
- 不允许明显价值判断式措辞
- 不允许敏感主题

probe 题和 likert 题还分别有额外校验逻辑。

## 5. 连续作答如何“收敛”

这是你最关心的问题之一。

### 5.1 收敛的含义

这里的“收敛”不是指用户会被收敛到一个固定 MBTI 类别，而是：

- `core_mu` 逐渐稳定
- `core_sigma` 逐渐下降
- 高层维度先成形
- 子维度和模块逐步展开
- 聚类归属从模糊混合，逐渐变成更清晰的簇权重分布

### 5.2 为什么连续答题会收敛

因为系统每次回答后都在做 3 件事：

1. 更新状态中心
   - 用残差修正 `mu`
2. 收缩不确定性
   - 被有效测量过的维度 `sigma` 会下降
3. 主动追问不确定区域
   - 下一题优先覆盖高不确定、低覆盖的地方

换句话说：

- 不是“题做得越多越多”
- 而是“系统越来越把题问到刀口上”

### 5.3 好处是什么

连续作答相对一次性分型的优势：

- 可以先给出早期报告，再继续细化
- 不必一开始就把所有细节问完
- 更适合区分“核心骨架”与“场景投影”
- 可以用锚题和 probe 题反复校准
- 对不确定性更诚实，不强迫输出假的确定感

### 5.4 收敛到什么状态

理想上，一个成熟会话会出现：

- 多个核心维度 `sigma` 下降到较稳定水平
- 若干关键子维度被解锁并形成方向
- 模块分数里出现少量活跃模块
- 聚类 membership 头部权重提升
- 报告的 narrative label 不再频繁剧烈变化

## 6. 聚类是怎么做的

### 6.1 当前方法

当前聚类是：

- 特征构造：`feature_vector()`
- 算法：`KMeans`
- soft 输出：用到簇中心的距离做 `exp(-distance)` 归一化

所以严格说：

- 当前训练是 hard clustering
- 但展示层是 soft membership

### 6.2 为什么不直接按核心维度硬分类型

因为当前系统的目标不是发固定人格证书，而是：

- 给出“结构相近的人在空间里的聚集区域”
- 让报告能表达混合态与边界态

所以它更适合作为“状态空间 + 近邻解释器”，而不是绝对分型器。

### 6.3 当前聚类的不足

也要诚实讲，目前聚类仍然很早期：

- 样本量还不大
- synthetic reference vectors 带有明显人工先验
- `KMeans` 对球状簇更友好，未必适合所有真实人格结构
- `zeta.performative` 已进入特征向量，但当前几乎还没被正式更新

这意味着：

- 当前聚类更适合“原型解释”和“地图可视化”
- 还不适合被当作严格科学分类结论

## 7. AI 是怎么用的

### 7.1 当前已经在用的地方

AI 目前主要用于：

- 改写题面
- 生成 probing 题
- 生成报告命名和摘要

### 7.2 当前没有交给 AI 的地方

目前没有交给 AI 的核心决策：

- 核心评分更新
- 聚类训练
- 题目合法性最终判断
- 会话访问控制

这是一个很好的边界：

- 数值部分由规则和模型负责
- 语言部分由 AI 增强

### 7.3 为什么这样设计

这样设计有几个优点：

- 更稳定，可复现
- 更容易调试
- 不会因为一次模型波动就把整个画像逻辑带偏
- 可以在没有 AI 的情况下继续跑完整闭环

### 7.4 embedding / reranker 现在怎么划边界

向量层已经接入，当前默认联调组合是：

- DeepSeek `deepseek-v4-pro`
  - 用作通用 chat / rewrite / report / probe provider
- SiliconFlow `BAAI/bge-m3`
  - 用作 embedding provider
- SiliconFlow `BAAI/bge-reranker-v2-m3`
  - 用作 reranker provider
- Qdrant local mode
  - Windows 本地优先使用 `QDRANT_LOCAL_PATH=.qdrant-local`

当前已经落地的能力：

- `item_vectors`
  - 模板
  - 已生成实例题
  - 改写候选
- `session_vectors`
  - 只在 `5 / 10 / 20 / 40` 题时写会话快照
- 管理端 reindex
  - `templates`
  - `instances`
  - `sessions`
  - `all`
- 管理端相似检索
  - similar templates
  - similar sessions
- 改写预览检索证据
  - 相近模板
  - 相近实例题
  - 历史改写候选

其中：

- embedding 负责“召回候选”
- reranker 负责“在当前语境下做精排”
- 规则层负责“是否可用、是否安全、是否保持测量方向”

必须强调的边界没有变：

- 语义相近，不等于测量构念完全等价
- 向量层是检索增强层，不是心理测量主判定层
- reranker 是证据排序器，不是评分器

因此当前 embedding / reranker 的角色是：

- 检索助手
- 改写约束器
- 近邻证据排序器
- 管理端诊断工具

而不是：

- 主评分器
- 构念判定器
- 自动题库裁决器
- 自动异常判定器

### 7.5 如何处理“语义相近不等于测量等价”

这是后续实现里最容易踩坑的点。

建议把题目判断拆成两层：

#### 第一层：语义相关性

由 embedding + reranker 负责回答：

- 这题和哪些题文本上最接近
- 改写版本与原题是否仍然足够相关
- 某个簇附近最值得拿来解释的题目和会话有哪些

#### 第二层：测量等价性

由结构化规则和人工审核负责回答：

- 维度载荷是否保持一致
- 子维度 / 模块意图是否发生漂移
- 场景标签是否从一个语境滑到另一个语境
- 题型是否仍然适配原本的作答方式
- 校验器是否通过

换句话说：

- embedding 只能证明“像不像”
- 不能单独证明“是不是同一个测量构念”

### 7.6 建议的治理规则

为了避免向量层被误用，建议后续实现时加这些规则：

1. 改写候选必须先过规则校验，再看 embedding / reranker 分数
2. 不能仅凭 embedding 相似度自动合并或删除题目
3. 不能仅凭语义相似度认定两题可互为 anchor 或镜像题
4. 对高风险改写保留人工审核
5. 聚类主向量仍以结构化向量为主，语义向量只做辅助
6. 簇表达层默认走 `RAG + LLM 候选 + 人工审核`

当前已完成：

1. `item_vectors`
2. `session_vectors`
3. embedding 召回
4. reranker 精排
5. 改写检索证据
6. 管理端 reindex / similar / sync failures

当前还没做：

1. `cluster_vectors`
2. 用户端 Session Workbench
3. 自动异常判定
4. 后台任务队列和自动重试
5. 生产级密钥管理

## 8. 能不能识别瞎答题、伪造答题

可以，而且当前代码里已经有一些基础信号，但还没有形成完整的“反作弊判别器”。

### 8.1 当前已经存在的可用信号

#### 1. 残差异常

当前系统记录了：

- `predicted_score`
- `mapped_score`
- `residual`

如果用户连续多题都表现出异常大的残差，就说明：

- 当前回答和历史状态严重不一致
- 可能是瞎答
- 也可能是用户刻意反向作答
- 也可能说明前面画像还不稳定

#### 2. 一致性信号 `zeta.consistency`

当前规则里：

- `abs(residual) > 1.1` 时，一致性下降
- 否则，一致性缓慢回升

虽然这是一个简单规则，但已经是最初的“行为一致性评分”。

#### 3. 响应时长

每个答案都记录了 `latency_ms`。

当前已有使用：

- 极短延迟会拉高 `fatigue`
- 聚类特征向量也吃进了 `median_latency`

这意味着极快乱点、极端稳定的固定节奏，其实已经能部分被行为特征捕捉到。

#### 4. 极端选项比例

聚类特征里已经包含：

- `extreme_ratio`

如果一个用户持续选择最左 / 最右，可能代表：

- 真实人格很鲜明
- 或者应付式作答

单独看不能下结论，但与残差、时长结合后会更有意义。

#### 5. Anchor 题复核

系统会周期性插入 anchor 题。

这类题天然适合做：

- 时间间隔内的重复测量一致性检查
- 前后状态漂移检查

### 8.2 现在还没正式实现，但非常值得加的统计方法

下面这些是最值得下一步做成正式能力的。

#### A. 人员拟合度 `person-fit`

可以借鉴 IRT 里的思路，为每个会话计算：

- 某人给定当前 `theta` 时，观测回答序列的似然
- 明显低似然的序列判为“拟合差”

这会比单看极端比例更稳。

#### B. 长串同答 / 机械模式检测

比如检测：

- 连续 10 题都同一选项
- 选项模式呈周期性摆动
- 极短时间内完成大量题目

这是最基础也最有效的反乱填规则。

#### C. 锚题前后漂移统计

对同维度 anchor 题做：

- 前后差值
- 标准化漂移分数
- drift curve

若漂移过大，可能是：

- 用户状态真的在变
- 也可能是后期疲劳、随意答题或刻意伪装

#### D. 语义自相矛盾检测

可利用模板元信息做：

- 正反项一致性检查
- 相近场景题的方向冲突检查
- 互斥子维度的矛盾回答检查

这部分 AI 也能参与，但规则层应先定义冲突图谱。

#### E. 马氏距离 / 异常向量检测

基于全体会话的特征向量，检测：

- 是否偏离正常答题群体过远
- 是否同时出现极低时长、高极端率、低一致性、异常轨迹震荡

这比单点规则更像一个真正的异常检测器。

#### F. 轨迹振荡指数

在当前系统里可以直接从 `trajectory_points` 推出：

- 状态更新方向是否频繁大幅反转
- 是否出现“锯齿型画像路径”

如果某用户轨迹非常不稳定，而 `sigma` 又不合理地不降，就很可能是乱答或伪装。

### 8.3 AI 能不能参与识别伪装答题

可以，但不建议让 AI 独立做最终判决。

更合理的方式是：

- 先由规则 / 统计模型生成一组可解释信号
- 再让 AI 做“审阅解释器”

例如输入：

- 残差摘要
- 响应时长分布
- anchor 漂移
- 矛盾题对列表
- 聚类归属震荡情况

然后让 AI 输出：

- “疑似疲劳”
- “疑似机械答题”
- “疑似刻意形象管理”
- “证据不足，不建议判定”

也就是说：

- AI 适合解释
- 不适合做唯一裁判

## 9. 一个更完整的反作弊方案可以怎么设计

建议未来引入 `response_quality_score`，由以下子分数组成：

- `latency_score`
  - 是否存在异常快答、整段固定节奏
- `consistency_score`
  - 残差和拟合度是否异常
- `anchor_stability_score`
  - 锚题前后是否大幅漂移
- `pattern_score`
  - 是否出现机械同答、极端值刷屏
- `semantic_coherence_score`
  - 是否出现明显语义矛盾
- `trajectory_stability_score`
  - 状态轨迹是否无意义震荡

然后把总分分成：

- `可信`
- `需谨慎解释`
- `可能低质量作答`

这会比“直接判作弊”更符合当前产品定位。

## 10. 接下来还能怎么开发

下面是我认为最值得推进的路线。

### 10.1 第一优先级：把用户端从问答页升级成 Session Workbench

- 保留当前快速作答主流程
- 增加“为什么问这题”面板
- 增加实时画像面板
- 增加最近答题轨迹和 milestone checkpoint
- 在满足报告阈值前提前展示报告预览
- 不把 raw vector score 当作用户侧结论

原因：

- 后端现在已经有 `item_vectors`、`session_vectors` 和 retrieval evidence
- 当前用户端仍主要像单题问卷，隐藏了系统真正的主动测量能力
- 先做 Workbench，比继续加 `cluster_vectors` 更能提升产品可理解性

### 10.2 第二优先级：把现有原型打磨稳

- 给 `zeta.performative` 真正定义更新规则
- 做统一的 `response_quality_score`
- 给 anchor 题增加稳定性诊断
- 把题目冲突图谱显式建模
- 增加会话质量摘要写入报告

### 10.3 第三优先级：把测量层做厚

- 扩充子维度题库
- 给不同场景模块增加更多模板
- 引入更明确的反向题、镜像题、复核题
- 引入题目曝光控制和模板使用统计

### 10.4 第四优先级：把聚类做得更像研究工具

- 存更多历史样本，不只使用内存中的活动会话
- 支持对比 `KMeans / GMM / HDBSCAN`
- 引入聚类质量指标
  - `silhouette score`
  - `Davies-Bouldin`
  - cluster stability over bootstraps
- 把“固定簇标签”降级为可选物，改做基于 RAG 的簇解释层

### 10.5 关于 cluster id / cluster label 的建议

如果后续继续沿这条线开发，我建议把下面几个概念彻底分开：

- `cluster_version + cluster_index`
  - 只作为系统内部锚点
  - 用来指向当前聚类版本里的某个簇
- `cluster evidence bundle`
  - 该簇的代表会话、代表题目、top dimensions、top subdimensions、top modules、行为统计
- `user-facing explanation`
  - 面向用户的实时解释结果

也就是说：

- 系统内部仍然需要 `cluster_index`
- 但用户侧未必需要看到“簇标签”
- 更符合项目宗旨的做法，是让用户看到：
  - `keyword_cloud`
  - `cluster_summary`
  - `evidence_points`
  - `user_specific_explanation`

这样做的好处是：

- 避免把动态聚类误读成固定人格类型
- 更适合边界态、混合态和过渡态
- 让解释层可以根据实时行为和检索上下文动态生成
- 让 cluster 成为内部分析骨架，而不是外部标签容器

### 10.6 第五优先级：把 AI 从“语言增强”推进到“研究辅助”

- 用 AI 审核题面重复与语义冲突
- 用 AI 辅助生成候选题，但必须保留规则校验
- 用 AI 解释可疑作答信号
- 用 AI 生成面向研究者的“会话摘要”

### 10.7 第六优先级：工程化

- 增加 CI 中对后端测试和前端构建的强约束
- 把配置进一步环境变量化
- 支持可替换数据库
- 为会话历史、模板版本、聚类版本建立更清晰的数据迁移策略
- 为模型实验增加离线评估脚本

## 11. 推荐的下一步开发顺序

如果只允许选一条最现实的路线，我建议：

1. 先做 Session Workbench 第一版
2. 再做 `response_quality_score`
3. 再做 anchor / 镜像题一致性检测
4. 再把聚类样本池从“当前会话”扩到“持久化历史”
5. 最后再做 `cluster_vectors` 和更复杂的 AI 审阅器

原因是：

- Workbench 会立刻暴露主动测量、向量证据和 milestone 价值
- 质量诊断会立刻提高系统可信度
- 一致性检测能直接帮助识别瞎答题与伪装答题
- 聚类质量提升后，地图和报告解释才更稳
- AI 放在最后做解释层，会更安全，也更容易评估

## 12. 一句话总结

Distilled TI 当前已经不是一个静态问卷，而是一个：

- 基于连续潜在状态更新的测量原型
- 带主动选题策略的会话引擎
- 用聚类做空间解释的报告系统
- 用 AI 做语言增强与 probing 增强的混合系统
- 用 embedding / reranker 做检索证据和近邻诊断的向量增强系统

下一阶段最值得做的，不是“堆更多炫的 AI”，而是：

- 把测量质量
- 一致性诊断
- 题目统计
- 聚类稳定性

这几件真正决定系统可信度的基础设施补齐。
