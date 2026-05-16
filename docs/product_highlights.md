# ✨ Distilled TI 心理检测软件核心亮点

基于代码深度分析，Distilled TI 是一款创新的心理测评平台，融合了 Galgame 沉浸式体验与 AI 智能分析。

---

## 🎮 双模式心理分析系统

### 模式一：本地 Galgame 行为分析 + Skill 蒸馏

#### 1. 角色人设深度建模（Layer 0-5 六维人格）

每个角色拥有完整的六层人格定义：

| Layer | 层级名称 | 内容 | 作用 |
|-------|----------|------|------|
| **Layer 0** | 核心性格 | 不可违背的核心原则 | 最高优先级行为准则 |
| **Layer 1** | 身份描述 | 角色背景、路线故事 | 建立角色认知基础 |
| **Layer 2** | 表达风格 | 语气、口头禅、语速 | 对话风格生成 |
| **Layer 3** | 决策框架 | 优先级、如何说不、面对质疑 | AI 判断逻辑 |
| **Layer 4** | 人际行为 | 对上级/下级/平级的态度 | 社交互动规则 |
| **Layer 5** | 边界雷区 | 喜欢/拒绝/回避的话题 | 内容过滤保护 |

**代码实现**：
- [backend/app/domain/senren_skills_loader.py](file:///g:/trae galgame/distilled_TI/backend/app/domain/senren_skills_loader.py) - 人设加载器
- [skills/yoshino/persona.md](file:///g:/trae galgame/distilled_TI/skills/yoshino/persona.md) - 角色人设示例

#### 2. 千恋万花角色 Skill 系统

9个角色完整配置：

| 角色 | 定位 | 核心特质 |
|------|------|----------|
| **芳乃** | 巫女姬 | 责任感、忠诚、内心柔软 |
| **丛雨** | 付丧神 | 毒舌、孤独、好奇心旺盛 |
| **茉子** | 女忍者 | 轻浮外表、细腻内心 |
| **蕾娜** | 留学生 | 天真、热情、文化桥梁 |
| **小春** | 弓道少女 | 完美主义、坚强独立 |
| **芦花** | 看板娘 | 照顾者、温暖开朗 |
| **将臣** | 男主角 | 温和可靠、责任感 |
| **廉太郎** | 损友 | 热血笨蛋、讲义气 |
| **隆文** | 神主 | 严肃古板、深沉父爱 |

**人格特质量化**：每个角色拥有 10 维心理画像（社交主动性、情绪稳定性、规划偏好等）

**代码实现**：[plugins/colleague-skill/scripts/build_senren_skills.py](file:///g:/trae galgame/distilled_TI/plugins/colleague-skill/scripts/build_senren_skills.py)

#### 3. Skill 蒸馏机制

将专家数字痕迹转化为可调用的 AI Skill：

```
数据采集 → Persona 分析 → Skill 生成 → 增量进化
```

**支持的数据来源**：
- 飞书/钉钉/Slack 自动采集
- 微信聊天记录（SQLite）
- 邮件/PDF/图片/Markdown 导入

---

### 模式二：AI 智能对话场景行为分析

#### 1. 多分类器融合推理

五种推理方式融合：

| 分类器 | 原理 | 应用场景 |
|--------|------|----------|
| **规则引擎** | 预设规则匹配 | 简单明确的场景 |
| **向量检索** | Embedding 相似度匹配 | 语义理解 |
| **成对比较** | Pairwise 模型 | 精细判断 |
| **LLM 推理** | 大语言模型分析 | 深度理解 |
| **混合模式** | 综合以上所有 | 复杂场景 |

**代码实现**：[backend/app/domain/models.py](file:///g:/trae galgame/distilled_TI/backend/app/domain/models.py#L85-91)

#### 2. 动态题目生成与改写

AI 根据用户状态动态生成个性化题目，保持测量方向不变，只改写措辞。

**核心优势**：
- **个性化措辞**：根据用户特质定制提问方式
- **去重机制**：向量相似度检测避免重复
- **场景适配**：选择最匹配的测试场景

**代码实现**：[backend/app/services/ai_service.py](file:///g:/trae galgame/distilled_TI/backend/app/services/ai_service.py#L108-199)

#### 3. 自由文本输入推理

支持用户自由输入，AI 推断其心理倾向：

```python
class GalgameTextInference(BaseModel):
    inferred_option_key: str | None  # 推断的选项
    confidence: float                # 置信度
    reason: str                      # 推理原因
    source: Literal["rule", "embedding", "pairwise", "llm", "hybrid"]
```

---

## 📊 实时更新心理图谱

### 1. 贝叶斯渐进评估

每回答一题实时更新心理画像：

```python
class SessionState(BaseModel):
    core_mu: dict[str, float]      # 各维度均值（当前心理状态）
    core_sigma: dict[str, float]   # 各维度标准差（不确定性）
    zeta: dict[str, float] = {     # 元认知指标
        "consistency": 0.5,        # 回答一致性
        "performative": 0.0,       # 表演倾向
        "exploration": 0.5,        # 探索程度
        "fatigue": 0.0             # 疲劳度
    }
```

**核心优势**：
- **动态更新**：实时反映用户状态变化
- **不确定性量化**：sigma 值表示测量置信度
- **元认知监测**：识别回答质量

**代码实现**：[backend/app/domain/models.py](file:///g:/trae galgame/distilled_TI/backend/app/domain/models.py#L93-115)

### 2. 工作进度看板

可视化展示测试进度和关键信号：

```python
class WorkbenchCheckpoint(BaseModel):
    question_count: int                          # 当前答题数
    report_ready: bool                           # 报告是否就绪
    top_core_signals: list[WorkbenchSignal]     # 核心维度信号
    uncertainty_queue: list[WorkbenchSignal]    # 待解决的不确定性
    narrative: str                              # 当前叙事描述
```

**用户体验**：
- **进度可视化**：清晰展示测试进度
- **即时反馈**：每个里程碑提供阶段性总结
- **智能引导**：提示需要更多数据的维度

**代码实现**：[backend/app/domain/models.py](file:///g:/trae galgame/distilled_TI/backend/app/domain/models.py#L252-268)

### 3. 聚类分析与人格标签

KMeans 聚类将用户分为 6 种类型：

| 簇名称 | 叙事标签 | 核心特征 |
|--------|----------|----------|
| 协同推进簇 | 轨道修正式协作者 | 善于协作、推进执行 |
| 抽象统筹簇 | 高阶抽象操盘手 | 抽象思维、全局视角 |
| 稳态执行簇 | 低波动推进者 | 稳定可靠、执行力强 |
| 探索扩张簇 | 远距校准型探索者 | 好奇心强、勇于探索 |
| 强压决断簇 | 低温高压思考核 | 冷静理智、善于决策 |
| 情境适配簇 | 多场景切换型节点 | 灵活适应、多面能力 |

**代码实现**：[backend/app/services/clustering.py](file:///g:/trae galgame/distilled_TI/backend/app/services/clustering.py)

---

## 🧠 十维人格模型

| 维度 | 描述 | 应用场景 |
|------|------|----------|
| **社交主动性** | 主动开启互动、发起协作的倾向 | 团队协作、社交场合 |
| **社交刺激耐受** | 在高密度互动下维持状态的能力 | 社交活动、公开演讲 |
| **自主决断倾向** | 独立判断 vs 依赖权威 | 决策场景、领导力评估 |
| **规划结构偏好** | 对清单、结构化的偏好 | 项目管理、学习规划 |
| **风险容忍度** | 面对不确定性的承受能力 | 创业、投资决策 |
| **抽象化倾向** | 偏好概念模型 vs 实例经验 | 学术研究、创新工作 |
| **新奇寻求** | 对新方法、新体验的追求 | 职业发展、兴趣探索 |
| **竞争合作取向** | 竞争领先 vs 合作共建 | 团队角色定位 |
| **情绪稳定性** | 受反馈影响的强弱和恢复速度 | 压力管理、冲突处理 |
| **推进执行力** | 把判断转化为行动的能力 | 项目推进、任务完成 |

**代码实现**：[backend/app/domain/dimensions.py](file:///g:/trae galgame/distilled_TI/backend/app/domain/dimensions.py#L26-41)

---

## 🔄 双模式协同工作流程

```
┌─────────────────────────────────────────────────────────────────┐
│                    Distilled TI 心理分析系统                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   🎮 模式一：Galgame 行为分析              🤖 模式二：AI 对话分析    │
│   ┌──────────────────────┐            ┌──────────────────────┐   │
│   │ 角色人设 Layer 0-5   │            │ 多分类器融合推理     │   │
│   │ 场景化互动选择       │            │ 动态题目生成         │   │
│   │ 记忆碎片系统         │            │ 自由文本推断         │   │
│   │ Skill 蒸馏机制       │            │ 实时语义分析         │   │
│   └──────────┬───────────┘            └──────────┬───────────┘   │
│              │                                   │                │
│              └────────────────┬──────────────────┘                │
│                               ▼                                  │
│              ┌──────────────────────────────────┐                │
│              │        实时心理图谱更新            │                │
│              │  贝叶斯评估 | 进度看板 | 聚类分析  │                │
│              └──────────────────────────────────┘                │
│                               ▼                                  │
│              ┌──────────────────────────────────┐                │
│              │         最终心理报告输出          │                │
│              │  10维人格画像 + 模块分析 + 建议   │                │
│              └──────────────────────────────────┘                │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🎯 产品价值总结

| 维度 | 价值描述 |
|------|----------|
| **沉浸体验** | Galgame 场景化互动，高代入感 |
| **精准分析** | 10维人格模型 + 聚类分析 |
| **动态生成** | AI 个性化题目与对话 |
| **实时反馈** | 渐进式心理图谱更新 |
| **多模态输入** | 选择题 + 自由文本 |
| **Skill 蒸馏** | 将专家知识转化为可调用技能 |

> **"在互动叙事中发现真实自我"**

通过 **场景化沉浸** + **智能分析** + **行为驱动叙事** 的三重优势，Distilled TI 重新定义了心理测评体验！

---

*Generated from code analysis of Distilled TI project*
