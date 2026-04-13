# Distilled TI 架构文档（v1）

> 副标题：一个基于固定核心坐标系、渐进分辨率提升、模块化投影与叙事标签生成的动态人格娱乐系统

---

## 0. 文档目的

本文档用于直接指导 **Distilled TI** 项目的设计与开发。它不是一份空泛的产品概念说明，而是一份兼顾：

- 产品定位
- 方法论边界
- 数学抽象
- 题库组织
- 评分更新
- 聚类与标签生成
- 前后端工程架构
- 数据库结构
- MVP 开发路线图

的实现草案。

本文档保留并整合了此前讨论中的核心思想：

1. **Distilled TI 不是分型系统，而是连续人格/行为倾向估计系统。**
2. **用户不是被判定为某一类，而是在一个相空间中被持续测绘。**
3. **标签只是解释层，而不是测量本体。**
4. **系统可以长期使用，但收敛的是估计，不是“人格真理”。**
5. **维度体系应采用固定主坐标系 + 渐进子维度 + 专题模块化投影，而不是底层无限乱增维。**
6. **整个系统可借鉴“纤维化的分层状态空间”直觉。**

---

## 1. 项目定位

### 1.1 一句话定义

**Distilled TI** 不是在判定用户“属于哪一类人”，而是在持续估计用户在 **行为倾向相空间** 中的位置，并把这个位置翻译成 **可读、可玩、可继续更新的叙事标签与动态报告**。

### 1.2 项目类型

Distilled TI 不是：

- 临床心理工具
- 标准化学术量表
- 招聘或筛选工具
- 精神诊断系统

Distilled TI 更像：

- 一个连续人格地图系统
- 一个可长期使用的互动画像产品
- 一个带有方法约束的娱乐型 personality engine
- 一个“你如何思考、互动、选择、推进”的动态投影系统

### 1.3 核心目标

系统要做到：

- 用户可随时开始
- 每次只做一题或几题
- 可以长期继续
- 每次都会更新状态估计
- 随着回答增加，画像逐步细化
- 输出不是僵硬的类型，而是：
  - 连续向量
  - 不确定性范围
  - 子维度细化
  - 模块化投影
  - 结构标签
  - 叙事标签
  - 动态报告

---

## 2. 方法论边界

### 2.1 不是“人格真理提取器”

系统估计的是：

- 某个时间窗口内的行为倾向
- 某些情境下的偏好与决策风格
- 随着回答逐步更新的后验状态

它不声称：

- 揭示用户本质
- 发现用户真实命运
- 给出不可改变的终极分类

### 2.2 不是 MBTI 换皮

Distilled TI 的关键区别不在于“换一个有趣标签”，而在于：

- **底层是连续向量，不是离散四字母。**
- **可以持续更新，不是一次性测完。**
- **允许不确定性存在。**
- **标签由后验结构生长出来，而不是先验强行贴上。**

### 2.3 娱乐优先，但不允许方法失控

本项目可以是娱乐型产品，但仍需明确约束：

- 题目生成不能完全失控
- 评分必须映射回同一底层坐标系
- 敏感内容必须受限
- 不允许将娱乐标签包装成临床判断

---

## 3. 总体理论框架

---

### 3.1 核心状态表示

用户在系统中的当前状态表示为：

\[
X_t = (\mu_t, \sigma_t, \zeta_t)
\]

其中：

- \(\mu_t\)：核心行为倾向向量的当前估计中心
- \(\sigma_t\)：各维度的不确定性
- \(\zeta_t\)：测量过程中的辅助交互信号

### 3.2 相空间视角

系统不是输出一个类别，而是在估计用户在相空间中的点：

\[
\theta \in \mathbb{R}^d
\]

但为了兼顾长期可比性与局部细化，系统采用三层维度架构：

- **Core Space**：固定的主坐标系
- **Subdimension Space**：在核心维度上逐步解锁的子维度
- **Projection Modules**：面向具体场景或玩法的专题投影空间

### 3.3 收敛含义

这里“收敛”的正确理解是：

> 不是人格本体收敛，而是系统对用户当前行为倾向向量的后验估计逐步稳定，并在某个不确定性范围内波动。

因此，Distilled TI 是一个 **在线估计系统**，不是一次性判型器。

---

## 4. 纤维化直觉：分层人格空间的几何类比

### 4.1 为什么像纤维丛

Distilled TI 可以借鉴如下直觉：

- 先有一个相对稳定的核心空间
- 再在这个空间上附着更细的局部自由度
- 做题越多，不是底空间被推翻，而是在已有底空间上看见更多局部结构

这类似于一个映射：

\[
\pi : E \to B
\]

其中：

- \(B\)：底空间，对应固定核心人格/行为倾向空间
- \(E\)：总空间，对应“核心画像 + 子维度 + 模块投影”的总体状态空间
- \(\pi^{-1}(b)\)：某个核心点上附着的局部纤维结构

### 4.2 在项目中的解释

- **底空间 \(B\)**：固定核心维度构成的主骨架
- **纤维 \(F_b\)**：某个核心位置处可进一步展开的子维度、情境投影和解释结构
- **总空间 \(E\)**：用户完整画像可能落入的总体状态空间

### 4.3 为什么不能让底层无限乱增维

如果题量增加就直接改底空间：

- 前 20 题是 8 维
- 前 50 题变成 12 维
- 前 100 题又改成 19 维

则会导致：

- 前后状态不可比
- 收敛定义失效
- 聚类中心不断重算
- 标签规则不断重写
- 工程复杂度暴涨

因此更合理的方式是：

> **固定 base，逐步细化 fiber。**

### 4.4 更准确的说法

Distilled TI 不必严格宣称自己是数学定义下的纤维丛；更准确的表达是：

> 它采用一种“带纤维化直觉的分层状态空间”架构：固定核心坐标系作为底空间，在其上附着逐步解锁的子维度与情境模块作为局部纤维结构。

---

## 5. 三层维度架构

---

## 5.1 Level 1：Core Dimensions（固定核心维度）

这是系统长期稳定的主坐标系。建议 MVP 阶段固定 **10 个核心维度**。

记作：

\[
\theta_{\text{core}} = (\theta_1, \theta_2, \dots, \theta_{10})
\]

每个维度可先取区间：

\[
\theta_i \in [-3,3]
\]

其中 0 为中性。

### 核心维度列表

#### \(\theta_1\)：社交主动性
是否倾向主动开启互动、发起协作、先开口。

#### \(\theta_2\)：社交刺激耐受
是否能在高密度、多噪声、多互动环境中保持状态。

#### \(\theta_3\)：自主决断倾向
偏独立判断还是偏依赖权威、规范、群体共识。

#### \(\theta_4\)：规划结构偏好
偏计划、清单、结构化，还是偏即兴推进、边走边调。

#### \(\theta_5\)：风险容忍度
面对不确定性时，偏稳健还是愿意押注更高波动方案。

#### \(\theta_6\)：抽象化倾向
偏概念、模型、理论，还是偏实例、经验、操作。

#### \(\theta_7\)：新奇寻求
偏探索新方法、新环境、新体验，还是偏熟悉路径。

#### \(\theta_8\)：竞争—合作取向
默认驱动更偏差异化胜出，还是更偏协作共建。

#### \(\theta_9\)：情绪稳定性
受反馈、冲突、扰动影响的强弱与恢复速度。

#### \(\theta_{10}\)：推进执行力
是否擅长将判断转成实际推进，持续落地与收尾。

### 核心层的要求

- 不轻易修改定义
- 所有题目至少部分映射回核心层
- 所有历史状态都能在核心层比较
- 聚类和标签的主骨架建立在核心层之上

---

## 5.2 Level 2：Subdimensions（渐进解锁的子维度）

这层用于提升画像分辨率。它不是平地新增全新底层坐标，而是对核心维度做更细的局部分解。

### 例：社交簇的子维度

在核心层，系统可能只有一个粗粒度社交相关向量；但答题增加后，可以逐步解锁：

- 陌生环境进入速度
- 熟人环境表达强度
- 群体存在感偏好
- 冲突场景开口阈值
- 高刺激环境中的社交衰减速度

### 例：执行簇的子维度

- 启动速度
- 中途切换倾向
- 收尾能力
- 长周期持续推进能力
- 阻力下推进能力

### 例：决策簇的子维度

- 信息不足下决断速度
- 权威依赖度
- 反悔倾向
- 风险—收益权衡方式
- 模糊情境容忍度

### 子维度层设计原则

- 子维度必须挂在某个核心簇下
- 只有在相关题量足够时才显示
- 可以局部显示、不必全局一次性全部开放
- 用户体验上表现为“画像越来越细”，而不是“系统换了一套规则”

---

## 5.3 Level 3：Projection Modules（专题投影模块）

这层面向产品玩法与场景解释。

它不应破坏核心坐标系，而应看作从总状态投影出的特定情境报告。

记作：

\[
P_k : E \to Y_k
\]

其中 \(P_k\) 是模块投影映射。

### 可能的模块示例

- 学习协作风格（Study Style）
- 项目组人格（Project Role）
- 冲突处理风格（Conflict Mode）
- 网聊人格（Chat Mode）
- 创作人格（Creative Mode）
- 旅行决策风格（Travel Style）
- 实验室人格（Lab Mode）
- 队友人格（Team Mode）

### 模块层特点

- 更有趣
- 更场景化
- 更适合分享与报告
- 稳定性可略低于核心层
- 主要用于叙事增强和玩法扩展

---

## 6. 辅助交互维度

除了核心人格/行为倾向坐标，还需要一组描述“用户如何与测量系统互动”的辅助指标：

\[
\zeta = (\zeta_1, \zeta_2, \zeta_3, \zeta_4)
\]

### \(\zeta_1\)：一致性
衡量重复题、改写题、锚点题上的稳定程度。

### \(\zeta_2\)：表演性
衡量用户是否有明显塑造形象、反向试探系统、玩梗式作答倾向。

### \(\zeta_3\)：探索欲
衡量用户是否愿意不断做新题、切换场景、试不同模块。

### \(\zeta_4\)：疲劳/漂移信号
衡量长时作答中是否出现乱答、机械化、稳定性骤降等迹象。

这些维度不是“人格本体”，但对系统调度、标签命名和报告解释非常有用。

---

## 7. 状态表示与总空间

可以将用户完整状态写作：

\[
x = (\theta_{\text{core}}, \xi_{\text{sub}}, \eta_{\text{module}}, \zeta)
\]

其中：

- \(\theta_{\text{core}}\)：核心向量
- \(\xi_{\text{sub}}\)：已解锁并已估计的子维度参数
- \(\eta_{\text{module}}\)：模块投影相关参数
- \(\zeta\)：交互辅助信号

在工程实现上，可以简化为：

\[
X_t = (\mu_t, \sigma_t, \zeta_t)
\]

其中 \(\mu_t\) 内部可拆成 core/sub/module 三部分。

---

## 8. 题库结构设计

题库不能只是文本列表，而应是 **结构化 item bank**。

每道题可以抽象成：

\[
q = (\text{text}, w_q, a_q, b_q, m_q, \tau_q, \phi_q)
\]

其中：

- `text`：题面文本
- `w_q`：作用维度载荷向量
- `a_q`：区分度/信息量
- `b_q`：阈值/偏置
- `m_q`：题型类型
- `tau_q`：情境标签
- `phi_q`：质量与校准信息

### 8.1 载荷向量 `w_q`

要求：

- 主作用维度 1–2 个
- 副作用维度最多 1 个
- 非零维度数量尽量不超过 3
- 所有题至少映射到某个核心维度簇

### 8.2 区分度 `a_q`

表示这道题提供信息的能力：

- 高区分度：更适合核心更新
- 中区分度：适合补充测量
- 低区分度：更适合娱乐投影或标签丰富

### 8.3 阈值 `b_q`

表示该题的回答区间偏置，不是“难易”，而是该题更可能在什么倾向附近提供区分。

### 8.4 题型 `m_q`

MVP 建议支持以下几类：

1. Likert 五级题
2. 二选一 forced choice
3. 三选一行为偏好题
4. 情境决策题
5. 排序题（后续）
6. 微叙事反应题（后续）

### 8.5 情境标签 `tau_q`

示例：

- `study`
- `work`
- `friendship`
- `conflict`
- `leisure`
- `public`
- `online`
- `high_stakes`
- `low_stakes`
- `unknown_group`
- `close_group`

### 8.6 质量与校准信息 `phi_q`

包括：

- 是否核心题
- 是否锚点题
- 是否人工审核
- 是否允许改写
- 是否仅用于娱乐模块
- 是否存在关联锚点
- 使用次数与表现统计

---

## 9. 题库层级

建议题库按功能分为四层：

### 9.1 核心测量题

直接进入核心向量更新。

特点：

- 维度映射清晰
- 稳定性高
- 质量控制严格

### 9.2 锚点题

用于一致性检验、防漂移与重复测量。

形式：

- 原题重复
- 轻微改写
- 同维度替代表述

### 9.3 情境扩展题

用于让画像更接近真实生活情境，例如：

- 小组合作
- 公共场合
- 冲突沟通
- 网聊互动
- 项目推进

它们可以部分更新核心维度，也可以主要进入子维度或模块层。

### 9.4 娱乐投影题

例如热点题、梗题、世界观题、角色代入题等。

这些题的主要作用：

- 增强趣味性
- 丰富标签生成素材
- 增强用户粘性

但不建议高权重写入核心坐标。

---

## 10. 题目生成约束

这是 Distilled TI 成败的关键之一。

**原则：不要让模型自由出题。**

应该采用：

> 模板 + 检索 + 约束生成 + 规则校验

### 10.1 生成流程

#### Step 1：确定当前最需要测的部分
根据当前不确定性、近期覆盖情况、用户疲劳情况，决定下一题要测：

- 核心维度
- 某个子维度簇
- 某个模块投影
- 或某个锚点检验

#### Step 2：检索候选模板
从模板库中根据目标维度、情境标签、题型偏好找到候选模板。

#### Step 3：LLM 受限改写
模型只负责：

- 情境替换
- 文案润色
- 风格适配
- 选项语言优化

不允许它自由改变题目测量方向。

#### Step 4：规则校验器检查
检查：

- 维度数量是否越界
- 是否引导性过强
- 是否包含敏感内容
- 是否与近期题过于相似
- 是否进入道德审判或社会赞许陷阱

#### Step 5：展示并记录实例
每次展示的不是“模板本体”，而是一个 **题目实例**，应单独存档。

### 10.2 生成约束规则

#### 规则 1：一题最多主测 2 个维度
副测最多 1 个维度。

#### 规则 2：不得暗示“正确人格”
禁止措辞：

- 更成熟的人会……
- 真正优秀的人通常……
- 更聪明的人更倾向于……

#### 规则 3：避免高敏感主题进入核心测量
核心层尽量避开：

- 政治立场
- 宗教认同
- 创伤经历
- 医疗/精神诊断
- 性隐私
- 犯罪相关

#### 规则 4：同一核心维度必须跨情境采样
例如社交主动性不能只在聚会中测，还要在：

- 学习合作
- 线上互动
- 工作推进
- 熟人环境
- 陌生环境

中采样。

#### 规则 5：必须保留锚点题
每隔若干题插入重复题、改写题或同维度校验题。

### 10.3 示例生成输入结构

```json
{
  "target_layer": "core",
  "target_dimensions": ["social_initiative", "planning"],
  "primary_weights": [0.7, 0.3],
  "scenario_tags": ["study", "unknown_group", "medium_stakes"],
  "question_type": "situational_choice",
  "rewrite_mode": "template_preserving",
  "constraints": {
    "non_moralizing": true,
    "no_sensitive_topics": true,
    "max_dimensions": 2,
    "length_limit": 120
  }
}
```

---

## 11. 评分更新机制

这里给出一个能直接工程实现的 MVP 版本。它不追求严格 psychometrics，但逻辑闭合且便于扩展。

### 11.1 回答映射

- 五级题映射为：

\[
r_t \in \{-1,-0.5,0,0.5,1\}
\]

- 二选一题映射为：

\[
r_t \in \{-1,1\}
\]

- 三选一题可映射为：

\[
-1,0,1
\]

### 11.2 预测回答

系统根据当前状态预测用户对题 \(q_t\) 的反应：

\[
\hat r_t = \tanh(\gamma (w_t \cdot \mu_t - b_t))
\]

其中：

- \(w_t\)：题目载荷向量
- \(\mu_t\)：当前估计状态
- \(b_t\)：题目偏置
- \(\gamma\)：缩放参数

### 11.3 残差

\[
e_t = r_t - \hat r_t
\]

若残差较大，说明这道题对系统是有信息量的。

### 11.4 核心向量更新

\[
\mu_{t+1} = \mathrm{clip}\big(\mu_t + \eta_t \, c_t \, e_t \, w_t, -3, 3\big)
\]

其中：

- \(\eta_t\)：步长，随答题数逐渐减小
- \(c_t\)：题目置信权重

可设：

\[
\eta_t = \frac{\eta_0}{\sqrt{1 + t/T}}
\]

例如：

- \(\eta_0 = 0.35\)
- \(T = 20\)

### 11.5 不确定性更新

对每个维度维护：

\[
\sigma_t = (\sigma_{t,1},\dots,\sigma_{t,d})
\]

更新规则可取：

\[
\sigma_{t+1,i} = \max\big(\sigma_{\min},\, \sigma_{t,i}(1-\rho c_t |w_{t,i}|) + \delta_t\big)
\]

其中：

- \(\rho\)：收缩率
- \(\delta_t\)：漂移补偿项

若锚点题出现明显矛盾，可适度提高对应维度的不确定性。

### 11.6 子维度与模块更新

- 当某个簇相关题量不足时，只更新其父核心维度
- 当某个簇相关题量足够时，开始更新其子维度向量
- 当某个模块题量足够时，激活对应投影评分

这可以理解为：

- **前期更新 base**
- **中期开始细化 fiber**
- **后期增加模块投影质量**

### 11.7 辅助信号更新

#### 一致性
根据锚点题差值更新。

#### 表演性
可由如下启发式指标综合：

- 极端选项比例过高
- 前后矛盾但语气/模式明显带表演性
- 明显试探系统输出风格

#### 探索欲
由继续答题意愿、场景切换频率、模块尝试度估计。

#### 疲劳
由以下信号综合：

- 极短作答时间
- 直线型作答
- 一致性骤降

---

## 12. 选题策略

下一个题目不应随机，而应根据当前状态选择最有价值的题。

可定义：

\[
\mathrm{Need}(q) = \lambda_1 \cdot \mathrm{uncertainty\ gain} + \lambda_2 \cdot \mathrm{coverage\ gain} + \lambda_3 \cdot \mathrm{novelty\ gain} - \lambda_4 \cdot \mathrm{repetition\ penalty}
\]

直观解释：

- 优先测最不确定的维度
- 保持覆盖均匀
- 给用户一点新鲜感
- 避免连续出现太像的题

### 12.1 前中后期选题逻辑

#### 前期（前 20 题）
- 快速定位核心空间
- 不必细分过多
- 高区分度核心题优先

#### 中期（20–60 题）
- 开始插入子维度题
- 加强锚点校验
- 提升跨情境覆盖

#### 后期（60+ 题）
- 开始专题模块投影
- 重点缩小不确定性
- 更重视细化，而非大幅移动核心中心点

---

## 13. 聚类与标签生成

Distilled TI 的标签分为两层：

- **结构层标签**
- **叙事层标签**

### 13.1 聚类输入

用于聚类的特征向量可设置为：

\[
v = [\mu \parallel \zeta \parallel h]
\]

其中：

- \(\mu\)：核心与已稳定子维度
- \(\zeta\)：辅助交互信号
- \(h\)：若干统计特征，例如：
  - 极端回答率
  - 回答时长中位数
  - 场景偏好分布
  - 稳定期长度

### 13.2 聚类方法

MVP 可用：

- KMeans
- Gaussian Mixture

初步设置 12–24 个簇即可。

后续可升级为：

- HDBSCAN
- 谱聚类
- Prototype-based clustering

### 13.3 结构层标签

由规则生成，尽量可解释。

例如根据绝对值最大的 3–4 个轴输出：

- 高抽象 · 高自主 · 低噪声耐受
- 高推进 · 中高竞争 · 中低规划
- 低风险 · 高规划 · 高稳定

### 13.4 叙事层标签

在结构层标签基础上，由模型生成更有记忆点的命名，例如：

- 延迟点火推进器
- 低温高压思考核
- 远距校准型协作者
- 轨道修正型操盘手
- 噪声屏蔽式策动者

### 13.5 标签约束

叙事标签必须：

- 不侮辱
- 不病理化
- 不假装临床诊断
- 不制造宿命感
- 不做绝对化人格裁决

---

## 14. 报告生成逻辑

最终报告建议至少包括五部分：

### A. 当前相空间位置
展示核心画像、已解锁子维度、当前不确定性。

### B. 稳定性说明
说明哪些维度比较稳，哪些还在波动区间内。

### C. 行为风格摘要
用自然语言解释用户更可能如何思考、互动、决策与推进。

### D. 情境投影
在不同模块中给出投影，例如：

- 学习合作时
- 冲突处理中
- 陌生群体中
- 项目推进中

### E. 标签与原型邻近
给出结构标签、叙事标签、邻近原型簇。

文案风格应避免“你就是……”，而更倾向于：

- 当前数据表明你更倾向于……
- 在这些场景下，你更可能……
- 目前系统对这些结论较有把握；对另一些部分仍存在不确定性

---

## 15. 前后端 MVP 架构

### 15.1 总体架构

```text
[ Next.js Frontend ]
        |
        v
[ FastAPI Backend ]
   |      |      |
   |      |      +--> [ LLM Gateway ]
   |      |
   |      +--> [ Scoring Engine ]
   |
   +--> [ PostgreSQL + pgvector ]
   |
   +--> [ Redis / Job Queue ]
```

### 15.2 前端模块

建议技术栈：

- Next.js
- TypeScript
- Tailwind CSS
- Zustand 或 Redux
- ECharts / Recharts

#### 页面建议

1. Landing Page
2. Session Page
3. Live Map Page
4. Report Page
5. History Page
6. Admin/Curator Page

#### 核心组件

- `QuestionCard`
- `OptionSelector`
- `ContinueBar`
- `TraitRadar`
- `UncertaintyMeter`
- `ClusterTagPanel`
- `SessionProgressMiniMap`
- `AnswerHistoryDrawer`

### 15.3 后端模块

建议技术栈：

- FastAPI
- SQLAlchemy / SQLModel
- Pydantic
- scikit-learn
- pgvector
- Redis + RQ/Celery

#### 服务拆分

1. Session Service
2. Item Service
3. Generator Service
4. Scoring Service
5. Clustering & Tag Service
6. Report Service
7. Analytics Service

### 15.4 API 建议

#### 启动会话
`POST /api/session/start`

返回：

- `session_id`
- 初始状态
- 第一题

#### 获取下一题
`POST /api/question/next`

#### 提交回答
`POST /api/response/submit`

#### 获取当前报告
`GET /api/session/{id}/report`

#### 获取相空间投影
`GET /api/session/{id}/map`

#### 管理模板
`POST /api/admin/template/create`

---

## 16. 数据库表设计

建议使用 PostgreSQL + pgvector。

### 16.1 `users`

```sql
users (
  id UUID PK,
  anonymous_id TEXT UNIQUE,
  created_at TIMESTAMP,
  locale TEXT,
  consent_version TEXT,
  settings JSONB
)
```

### 16.2 `sessions`

```sql
sessions (
  id UUID PK,
  user_id UUID FK,
  started_at TIMESTAMP,
  ended_at TIMESTAMP,
  status TEXT,
  mode TEXT,
  question_count INT,
  stable_score FLOAT,
  current_cluster_id UUID,
  current_tag_id UUID
)
```

### 16.3 `state_snapshots`

```sql
state_snapshots (
  id UUID PK,
  session_id UUID FK,
  step_index INT,
  core_mu JSONB,
  core_sigma JSONB,
  sub_mu JSONB,
  sub_sigma JSONB,
  module_state JSONB,
  zeta JSONB,
  created_at TIMESTAMP
)
```

### 16.4 `item_templates`

```sql
item_templates (
  id UUID PK,
  name TEXT,
  template_text TEXT,
  question_type TEXT,
  layer TEXT,              -- core / sub / module / entertainment
  dimension_weights JSONB,
  discrimination FLOAT,
  difficulty FLOAT,
  scenario_tags TEXT[],
  quality_score FLOAT,
  is_anchor BOOLEAN,
  allow_rewrite BOOLEAN,
  status TEXT,
  embedding VECTOR(1536),
  metadata JSONB,
  created_at TIMESTAMP
)
```

### 16.5 `item_instances`

```sql
item_instances (
  id UUID PK,
  template_id UUID FK,
  session_id UUID FK,
  generated_text TEXT,
  options JSONB,
  generation_mode TEXT,
  llm_model TEXT,
  validator_passed BOOLEAN,
  scenario_tags TEXT[],
  effective_weights JSONB,
  created_at TIMESTAMP
)
```

### 16.6 `responses`

```sql
responses (
  id UUID PK,
  session_id UUID FK,
  item_instance_id UUID FK,
  raw_answer JSONB,
  mapped_score FLOAT,
  latency_ms INT,
  confidence_self_report FLOAT,
  created_at TIMESTAMP
)
```

### 16.7 `anchor_links`

```sql
anchor_links (
  id UUID PK,
  item_template_a UUID FK,
  item_template_b UUID FK,
  relation_type TEXT,
  expected_similarity FLOAT
)
```

### 16.8 `clusters`

```sql
clusters (
  id UUID PK,
  name TEXT,
  version TEXT,
  centroid JSONB,
  covariance JSONB,
  summary_rules JSONB,
  created_at TIMESTAMP
)
```

### 16.9 `tags`

```sql
tags (
  id UUID PK,
  cluster_id UUID FK,
  structural_label TEXT,
  narrative_label TEXT,
  description TEXT,
  style TEXT,
  version TEXT,
  created_at TIMESTAMP
)
```

### 16.10 `session_tags`

```sql
session_tags (
  id UUID PK,
  session_id UUID FK,
  tag_id UUID FK,
  score FLOAT,
  reason JSONB,
  created_at TIMESTAMP
)
```

### 16.11 `generation_logs`

```sql
generation_logs (
  id UUID PK,
  session_id UUID FK,
  template_id UUID FK,
  prompt JSONB,
  raw_output TEXT,
  validation_result JSONB,
  created_at TIMESTAMP
)
```

---

## 17. 题库构建策略

### 17.1 MVP 建议规模

第一版建议：

- 核心题：200–300 道
- 锚点题：50–80 道
- 情境扩展题：80–120 道
- 娱乐投影题：按需逐步添加

总量在 350–450 道模板题左右，足以做第一版。

### 17.2 题库来源

#### A. 手工设计
最适合作为骨架。

#### B. LLM 受限扩写
在模板约束与审核规则下扩写。

#### C. 数据反哺
根据题目表现与用户流失点迭代题库。

### 17.3 审核流程

进入核心题库前，建议每题经过：

- 维度标注
- 语言审核
- 敏感性审核
- 引导性审核
- 歧义审核

---

## 18. 可视化设计

### 18.1 推荐展示方式

#### A. 核心雷达图
适合快速展示核心画像。

#### B. 二维投影地图
用 PCA/UMAP 将高维状态投影到二维平面，显示当前位置与邻近簇。

#### C. 不确定性条形图
展示系统对各维度的信心程度。

#### D. 漂移轨迹图
展示多个 session 中状态随时间的变化。

#### E. 模块投影卡片
展示“实验室人格”“队友人格”等子报告。

### 18.2 文案建议

避免写：

- 你就是这样的人
- 你的本质是……

更建议写：

- 当前数据表明你更倾向于……
- 在这些场景下，你更可能……
- 这些结论比较稳定；这些结论还需要更多题目支持

---

## 19. 路线图

### Phase 0：定理论骨架（3–5 天）

交付物：

- 核心维度定义文档
- 子维度体系初稿
- 模块列表初稿
- 评分更新规则 v0
- 标签生成规范 v0

### Phase 1：题库骨架 + 后端闭环（5–7 天）

任务：

- 建库
- 写 session API
- 写 scoring engine
- 手工录入首批 80–120 道题
- 实现最小答题—更新—存档闭环

### Phase 2：前端单会话版本（5–7 天）

任务：

- Landing Page
- Session Page
- 当前状态可视化
- 简单标签显示

### Phase 3：动态改写 + 锚点机制（7–10 天）

任务：

- 模板检索
- LLM 改写
- 规则校验器
- 锚点调度
- 一致性指标

### Phase 4：聚类 + 报告 + 标签系统（5–7 天）

任务：

- 初步聚类
- 结构标签
- 叙事标签
- 报告页

### Phase 5：内测与调参（持续）

重点观测：

- 哪些题流失高
- 哪些题引导性强
- 哪些维度长期漂移
- 哪些模块用户最爱玩
- 哪些标签空泛或重复

---

## 20. 开发优先级建议

### 最先做的三件事

#### 第一件：写 `dimensions.md`
把：

- 10 个核心维度
- 每个核心簇下的子维度
- 计划开放的模块列表

全部明确写出来。

#### 第二件：手工做首批题库骨架
先不要依赖模型自动出题。先做：

- 核心题 120 道左右
- 锚点题 20–30 道
- 情境扩展题若干

#### 第三件：写 scoring engine
让系统先能：

- 选题
- 更新核心向量
- 更新不确定性
- 输出结构标签

只要这一步跑起来，项目就已经真正成立了。

---

## 21. 风险与边界

### 21.1 不做临床判断
禁止输出：

- 某种心理障碍
- 某种病理人格
- 某种诊断倾向

### 21.2 不做高风险筛选
禁止直接用于：

- 招聘筛选
- 学校筛选
- 恋爱操控判断
- 风险人群评估

### 21.3 不伪装为权威学术认证
可以自称：

- 动态人格娱乐系统
- 行为倾向地图
- 自我探索型互动产品

但不应声称：

- 官方人格真相
- 权威心理测试结论
- 临床意义上的人格诊断

---

## 22. 最终定义总结

### 工程定义

> Distilled TI 是一个基于固定核心坐标系、渐进子维度解锁、模块化情境投影、受约束题目生成、连续向量更新与后验聚类解释的动态人格娱乐系统。

### 产品定义

> 它不是在告诉用户“你是哪一类人”，而是在持续描绘用户更可能如何思考、互动、选择与推进，并将这种动态状态翻译成可读、可玩的叙事标签。

### 几何定义（类比式）

> Distilled TI 可以被理解为一个带纤维化直觉的分层状态空间：固定核心人格空间作为底空间，在其上附着逐步解锁的子维度与情境模块作为局部纤维结构。

---

## 23. 下一步建议

开发顺序建议如下：

1. 先定维度，不先定 fancy tag
2. 先写题库，不先上自由生成
3. 先把评分引擎跑起来
4. 再接动态题目改写
5. 再做聚类和叙事标签
6. 最后再做复杂模块和长期轨迹

如果只看一条原则，那么就是：

> **先把 base 立稳，再逐步展开 fiber。**

