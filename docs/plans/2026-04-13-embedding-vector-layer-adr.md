# ADR: 引入 Embedding 向量层

- 日期：2026-04-13
- 状态：Proposed
- 决策类型：Architecture Decision Record
- 目标形态：线上扩展优先

## 1. 背景

Distilled TI 当前已经具备以下核心能力：

- 结构化测量主链路
  - 基于 `SessionState` 的 `mu / sigma` 更新
- 主动选题
  - 基于不确定性、覆盖度、重复惩罚、场景多样性选择下一题
- AI 增强
  - 题目改写、probe 题生成、报告命名和摘要
- 聚类与地图
  - 基于结构化和行为特征的 `KMeans` 聚类、软成员关系、二维投影

但当前系统仍存在几个明显瓶颈：

1. 题目相似度主要依赖词面和字符 n-gram 近似
   - 对“语义相近但措辞不同”的题识别不稳定
2. AI 改写时缺少检索增强上下文
   - 难以稳定避免“过近改写”或“偏离测量方向的改写”
3. 聚类命名仍以人工预设为主
   - 适应性有限，难随着样本增长自动演化
4. 当前用户表征几乎完全依赖结构化状态
   - 没有统一的语义检索层可供后续分析和近邻解释

因此，需要引入一层独立的 embedding 向量架构，用来承载：

- 题目语义向量
- 会话 / 用户语义-行为混合向量
- 簇表示向量
- 检索增强上下文
- 自动簇解释与标签候选生成

## 2. 决策目标

本次 ADR 的目标不是替换现有评分体系，而是新增一个“向量增强层”，满足以下需求：

### 功能目标

- 让 AI 出题 / 改写前可检索最相近题目和历史改写案例
- 更稳定地判断题目是否与原模板保持一致测量方向
- 支持跨题库去重、覆盖分析、语义聚类
- 支持生成会话 / 用户的向量表征，辅助聚类和异常检测
- 支持对簇自动生成候选名称、候选叙事标签和摘要

### 非功能目标

- 支持独立服务化部署
- 可通过标准 API 接入，不强绑某个单体数据库
- 支持后续多用户 / 多环境扩展
- 保持当前主评分链路可独立运行
- 避免 AI 和 embedding 直接接管心理测量主逻辑

## 3. 决策

我们决定引入一层独立的 Embedding Vector Layer，采用“主测量层 + 向量增强层 + AI 生成解释层”的三层架构。

### 核心原则

1. 结构化测量层继续作为主判断层
   - `ScoringEngine`
   - `SessionState`
   - `mu / sigma`
   - 不被 embedding 替代
2. 向量层作为检索、增强和表征层
   - 用于题目、会话、簇的语义 / 混合向量表示
3. AI 层基于结构化数据和检索结果做生成与解释
   - 不直接负责最终评分

## 4. 方案选择

### 方案 A：继续使用当前字符级相似度和规则检索

优点：

- 实现最简单
- 成本低
- 无额外基础设施

缺点：

- 无法稳定识别语义相近题
- 无法支撑后续自动簇解释
- 无法为 AI 提供足够强的检索上下文

结论：

- 不满足后续演进目标

### 方案 B：直接把 embedding 融入现有 SQLite 模型

优点：

- 本地易接入
- 改动小

缺点：

- 不利于线上扩展
- 向量检索能力受限
- 后续多环境、多模型、多租户扩展困难

结论：

- 不适合作为线上扩展优先方案

### 方案 C：引入独立向量层，通过 API 调用

优点：

- 解耦现有后端
- 便于后续服务化、扩展和替换 embedding 模型
- 支持题目、会话、簇三类对象统一检索
- 更适合演进到多用户线上环境

缺点：

- 架构复杂度上升
- 需要维护额外存储和同步逻辑

结论：

- 选择此方案

## 5. 高层架构

```text
Frontend
   |
   v
FastAPI Backend
   |
   +--> Scoring / Session / Reporting / Clustering
   |
   +--> Embedding Orchestrator
           |
           +--> Embedding Provider API
           |
           +--> Vector Store API
           |
           +--> Metadata Store (existing DB / future relational store)
```

其中：

- `Embedding Provider API`
  - 负责生成文本 embedding
  - 可以是 OpenAI-compatible embedding 接口，或本地模型服务
- `Vector Store API`
  - 负责 upsert / search / delete
  - 推荐可替换，避免写死实现
- `Embedding Orchestrator`
  - 负责对象规范化、向量生成、向量同步、检索、结果融合

## 6. 向量对象模型

建议至少引入 3 大类 collection。

### 6.1 `item_vectors`

对象：

- 题目模板
- 改写候选
- 已发出的题目实例

建议 metadata：

- `object_type`: `template | rewrite_candidate | item_instance`
- `template_id`
- `instance_id`
- `layer`
- `dimension_weights`
- `subdimension_weights`
- `module_affinities`
- `scenario_tags`
- `allow_rewrite`
- `generation_mode`
- `created_at`

主要用途：

- 题目去重
- 改写前后相似度判定
- 语义覆盖分析
- AI 出题 RAG

### 6.2 `session_vectors`

对象：

- 会话快照
- 会话阶段性状态

建议 metadata：

- `session_id`
- `question_count`
- `core_mu`
- `core_sigma`
- `zeta`
- `extreme_ratio`
- `median_latency`
- `active_modules`
- `unlocked_subdimensions`
- `response_quality_score`（未来）
- `created_at`

主要用途：

- 近邻会话检索
- 异常检测
- 辅助聚类
- 簇代表样本检索

### 6.3 `cluster_vectors`

对象：

- 簇中心表征
- 簇代表样本摘要

建议 metadata：

- `cluster_version`
- `cluster_index`
- `keyword_cloud`
- `metaphor_candidates`
- `cluster_summary`
- `evidence_bundle`
- `sample_size`
- `top_dimensions`
- `top_subdimensions`
- `top_modules`

主要用途：

- 基于 RAG 的簇表达生成
- 簇近邻搜索
- 簇漂移对比

## 7. 向量来源设计

### 7.1 题目向量

建议对以下内容做 embedding：

- 原题 `prompt`
- 题目所属维度标签文本
- 场景标签文本
- 题目说明性摘要

推荐做法不是只 embed 原题文本，而是构造一个标准化文本：

```text
layer=core
dimensions=planning_preference:1.0, execution_drive:0.2
scenarios=project, work
prompt=事情一开动之前，我会先想把步骤、顺序和节奏理顺。
```

这样 embedding 会同时感知：

- 题面语义
- 测量语境
- 维度意图

### 7.2 会话向量

会话向量不建议只来自用户文本，因为当前项目主要是选择题系统。

建议使用两类向量并存：

- `session_struct_vector`
  - 基于 `core_mu`、`core_sigma`、`zeta`、行为统计拼接成数值向量
- `session_semantic_vector`
  - 基于会话摘要文本做 embedding
  - 摘要可由规则层自动生成，也可由 AI 补充

推荐先用：

- 结构向量主导
- 语义向量辅助

### 7.3 簇向量

簇向量建议由两部分组成：

- 聚类中心的结构向量
- 簇代表样本的语义摘要 embedding

这样便于同时支持：

- 数值近邻
- 语义解释

这里的 `cluster_version + cluster_index` 只应被理解为：

- 当前一次聚类结果里的内部锚点
- 便于系统缓存代表样本、簇证据、簇区域和解释产物

它不应被理解为：

- 预设的人格类型
- 跨版本天然稳定的簇身份
- 面向用户展示的固定标签

## 8. 与现有功能的集成方式

### 8.1 AI 改写

当前改写流程位于：

- `GenerationService.preview_rewrite()`
- `AIService.rewrite_template_candidates()`

建议新增流程：

1. 读取模板原题向量
2. 检索：
   - 最相近模板题
   - 最相近历史改写候选
   - 已判失败 / 不通过的改写样本
3. 将这些上下文一并传给 LLM
4. 对改写结果重新做 embedding
5. 计算：
   - 与原题距离
   - 与其他题最近距离
   - 与目标维度语义中心的距离
6. 作为改写评分的额外项

新增收益：

- 避免改写过近
- 避免改写跑偏
- 避免与题库其他题过度重复

### 8.2 出题选择

当前 `select_next_question()` 已有：

- 不确定性收益
- 覆盖惩罚
- 语义重复惩罚

未来可加入 embedding 信号：

- `semantic_novelty_bonus`
  - 与近期题目向量距离较大则加分
- `measurement_alignment_score`
  - 与目标维度语义中心对齐程度
- `coverage_gap_score`
  - 某类语义题型是否长期缺失

注意：

- embedding 信号应是附加项
- 不应覆盖 `sigma` 驱动的结构化主动测量逻辑

### 8.3 聚类

当前聚类使用的是手工构造的 `feature_vector()`。

未来建议升级为双层聚类输入：

- 主向量：结构化特征
- 辅向量：会话语义向量

两种可选做法：

1. 向量拼接后统一聚类
2. 双空间分别聚类，再做 late fusion

推荐：

- 先离线实验 `late fusion`
- 不要立刻改线上主聚类逻辑

### 8.4 基于 RAG 的簇表达生成

未来建议不要把目标收窄为“固定 tag”，而是升级为“无固定簇标签的簇表达生成层”。

推荐流程：

1. 每次聚类完成后，取每个簇的代表会话
2. 汇总代表会话的：
   - top core dimensions
   - top subdimensions
   - active modules
   - 行为统计
   - 代表题目
3. 检索：
   - 最接近的历史簇摘要
   - 最接近的代表题目
   - 最接近的会话样本摘要
   - 相关本地辅助知识 / 相似信息数据库
4. 将这些结构化摘要和检索结果作为 RAG 上下文交给 LLM
5. 由 LLM 生成：
   - `keyword_cloud`
   - `cluster_summary`
   - `metaphor_candidates`
   - `evidence_points`
   - `user_specific_explanation`
6. 后台管理端审核后生效，默认不生成固定簇标签

这样可以做到：

- 更符合项目“连续状态、非硬分型”的理念
- 输出直接围绕证据、关键词云和解释生成，而不是先造一个固定名字
- 更适合边界簇、混合簇和过渡簇
- 在保留自适应能力的同时，不完全失去可控性

进一步建议：

- `cluster_summary + keyword_cloud + evidence_points + user_specific_explanation` 才是主表达层
- 若未来确实需要短名称，也应被视为可选派生物，而不是系统基石
- 用户侧不直接暴露 `cluster_index`
- `cluster_version + cluster_index` 仅用于系统内部引用和缓存

## 9. 推荐技术选型

### 9.1 Embedding Provider

要求：

- 支持标准 API
- 可替换
- 可兼容 OpenAI 风格接口

建议抽象成接口：

- `EmbeddingProvider.embed_texts(texts: list[str]) -> list[list[float]]`
- `RerankerProvider.rerank(query: str, documents: list[str]) -> list[RerankHit]`

默认首选实现：

- 远端 API：
  - `SiliconFlow`
  - embedding model: `BAAI/bge-m3`
  - reranker model: `BAAI/bge-reranker-v2-m3`
- 本地模式：
  - 本地部署 `BAAI/bge-m3`
  - 本地部署 `BAAI/bge-reranker-v2-m3`

推荐原因：

- 更适合中文与中英混合场景
- 对题目检索、改写约束、簇表达 RAG 都比较契合
- `embedding + rerank` 比仅做向量召回更稳
- 可以在开发期先用远端 API 验证，后续再平滑切到本地

保留的抽象要求：

- provider 仍应保持可替换
- 不把业务代码直接写死在 SiliconFlow SDK 或某个本地运行时上
- 业务层只依赖统一的 provider 接口

为什么要加入 reranker：

- 向量召回适合找“可能相关”的候选
- reranker 更适合判断“在当前测量上下文里到底哪个最相关”
- 对题目改写、代表样本抽取、簇表达生成尤其有价值

### 9.2 Vector Store

线上扩展优先时，建议优先考虑独立向量库。

推荐首选：

- `Qdrant`

理由：

- API 友好
- 支持 metadata filter
- 适合题目 / 会话 / 簇多 collection 管理
- 本地开发和线上部署都比较顺

可选：

- `Weaviate`
- `Milvus`
- `Postgres + pgvector`

不推荐作为本 ADR 主路径的：

- 继续完全依赖 SQLite 自制检索

### 9.3 后端集成模块

建议新增：

- `backend/app/services/embedding_service.py`
  - 负责文本规范化、向量生成和缓存
- `backend/app/services/reranker_service.py`
  - 负责召回后的精排和相关性打分
- `backend/app/services/vector_store.py`
  - 负责 collection upsert / search / delete
- `backend/app/services/vector_indexer.py`
  - 负责模板、实例、会话、簇的同步
- `backend/app/services/cluster_naming.py`
  - 负责代表样本检索与候选命名生成

## 10. API 设计建议

建议后端内部先封装，再决定是否对管理端开放。

### 10.1 内部服务接口

- `index_template(template: ItemTemplate) -> None`
- `index_item_instance(instance: ItemInstance) -> None`
- `index_session_snapshot(session: SessionRecord) -> None`
- `search_similar_templates(prompt: str, top_k: int) -> list[SearchHit]`
- `search_similar_sessions(session_id: str, top_k: int) -> list[SearchHit]`
- `rerank_templates(query: str, candidates: list[str]) -> list[RerankHit]`
- `rerank_cluster_evidence(query: str, candidates: list[str]) -> list[RerankHit]`
- `build_cluster_label_candidates(version: str) -> list[ClusterLabelCandidate]`

### 10.2 管理端 API

建议未来新增：

- `POST /api/admin/vector/reindex`
- `GET /api/admin/vector/templates/similar`
- `GET /api/admin/vector/sessions/similar`
- `POST /api/admin/clusters/auto-label-preview`

## 11. 数据一致性策略

向量层引入后，必须考虑同步问题。

### 建议策略

- 结构化数据库仍是 source of truth
- 向量库是派生索引
- 所有向量对象都带 `object_id + version + updated_at`
- 后台支持全量重建索引

### 同步触发点

- 模板创建 / 更新 / 归档后
- 题目实例生成后
- 会话进入关键里程碑后
  - 例如题数达到 5、10、20、40
- 聚类版本刷新后

### 失败处理

- 主业务成功，向量写入失败时记录异步补偿任务
- 向量层失败不应阻塞主测量链路

## 12. 风险与限制

### 风险 1：语义相似不等于测量等价

embedding 可以帮助判断“像不像”，但不能单独判断“测的是不是同一个心理构念”。

因此：

- embedding 只做辅助
- 最终仍要保留维度载荷和校验规则
- 必须把“语义相关性”和“测量等价性”分开建模

进一步建议：

- 不要仅凭 embedding 相似度就认定两题可以互相替代
- 题目改写通过前，仍应同时检查：
  - 核心维度载荷是否一致
  - 子维度 / 模块意图是否一致
  - 场景语境是否发生偏移
  - 规则校验是否通过
- reranker 的任务也应定义为“测量语境下的相关性排序”，而不是“心理构念自动判定器”
- 对高风险改写和高风险合并仍应保留人工审核

### 风险 2：AI / embedding 污染主评分

如果让向量层直接决定核心评分或最终人格标签，会显著降低可解释性。

因此：

- 主评分继续由结构化规则负责
- 向量层只参与检索、候选生成、解释增强

### 风险 3：线上复杂度上升

引入独立向量层后，需要额外处理：

- 服务可用性
- 数据同步
- 成本控制
- 模型版本管理
- 远端 / 本地双模式切换的一致性

### 风险 4：簇表达生成早期不稳定

在样本不够大时，簇本身可能不稳定，关键词云、解释和证据摘要也会一起漂移。

因此：

- 早期应采用“RAG + LLM 候选 + 人工审核”的机制
- 不应把内部 `cluster_index` 直接当作用户可见标签
- 不应默认生成固定簇名称并长期缓存给用户使用

## 13. 分阶段实施路线

### Phase 1：题目向量层

目标：

- 建立 `item_vectors`
- 用于改写筛选、题目去重、题目检索

产出：

- 模板和改写候选向量索引
- 相似题检索接口
- 改写评分新增 embedding 约束项

### Phase 2：会话向量层

目标：

- 建立 `session_vectors`
- 支持近邻会话检索和异常会话检索

产出：

- 会话向量索引
- 相似会话搜索
- 向量辅助的异常检测实验

### Phase 3：簇向量与簇表达层

目标：

- 建立 `cluster_vectors`
- 生成基于 RAG 的簇表达候选

产出：

- 代表样本提取
- `keyword_cloud / cluster_summary / metaphor_candidates / evidence_points / user_specific_explanation`
- 后台审核流程

### Phase 4：聚类增强

目标：

- 评估结构向量 + 语义向量的混合聚类

产出：

- 离线对比实验
- 簇稳定性指标
- 是否纳入正式聚类主链路的决策依据

## 14. 决策结果

我们决定：

1. 引入独立 Embedding Vector Layer
2. 通过 API 方式接入 embedding provider 和 vector store
3. 优先采用 `Qdrant + 可替换 Embedding/Reranker Provider` 方案
4. 先服务于题目检索、AI 改写约束、会话近邻检索、簇表达生成
5. 不直接替代当前 `ScoringEngine` 和 `SessionState` 主测量逻辑
6. 默认首选 `SiliconFlow / 本地 BAAI-bge-m3 + BAAI-bge-reranker-v2-m3` 双模式实现
7. `cluster_version + cluster_index` 仅作为内部聚类锚点，不作为用户侧固定簇标签

## 15. 对现有项目的影响

短期影响：

- 增加服务模块和同步逻辑
- 增加向量基础设施运维成本
- 改进 AI 改写和题目去重质量

中期影响：

- 聚类解释更有弹性
- 从固定簇标签转向证据驱动的实时解释
- 支持近邻检索和更强的研究辅助能力

长期影响：

- 为多用户线上环境打基础
- 为异常检测、会话质量分析、自动知识发现提供统一语义层

## 16. 当前建议

如果进入实施阶段，建议第一步不是直接“把 embedding 接进聚类”，而是：

1. 先完成 `item_vectors`
2. 再完成 `session_vectors`
3. 最后才做 `cluster_vectors` 和基于 RAG 的簇表达生成

原因：

- 题目向量层最容易验证价值
- 会话向量层次之
- 簇表达生成最依赖样本规模、检索质量和摘要稳定性，适合后置
