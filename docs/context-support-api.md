# Context Support Signal API

本接口把 Distilled TI 的聚类、LLM、embedding 和规则分析能力抽象成一个通用后端能力：外部应用提交授权上下文，后端返回标准化的非诊断支持/风险信号。它适合接入 AI 助手、客服、社区、陪伴产品、学习产品或内部员工支持工具。

## 设计边界

- 这是 `support-signal API`，不是医学诊断 API。
- 输出只能用于产品安全、人工复核、支持入口、危机资源提示和长期趋势观察。
- 外部应用必须具备用户授权、隐私政策或企业合规依据；不要把它用于隐蔽监控。
- 如果返回 `risk_level=crisis`，应触发人工复核和当地危机资源。美国场景可提示用户拨打或短信 988，参考 [988 Lifeline](https://988lifeline.org/get-help/)。
- 风险信号的规则锚点参考 NIMH 对自杀警示信号的公开说明，例如想死、绝望、被困、成为负担、计划/方法、告别、退缩和睡眠/物质使用变化等，参考 [NIMH warning signs](https://www.nimh.nih.gov/health/publications/warning-signs-of-suicide)。

## 认证

后端配置：

```env
CONTEXT_ANALYSIS_API_KEY=your-server-side-key
CONTEXT_ANALYSIS_RECENT_MESSAGE_LIMIT=30
CONTEXT_ANALYSIS_STORE_RAW_MESSAGES=false
```

请求头：

```http
X-Context-API-Key: your-server-side-key
```

如果 `CONTEXT_ANALYSIS_API_KEY` 为空，本地开发会放行；生产环境应设置。

## Analyze Context

```http
POST /api/context/analyze
Content-Type: application/json
X-Context-API-Key: your-server-side-key
```

### Request

```json
{
  "application_id": "acme-chat",
  "external_user_id": "sha256-or-random-user-id",
  "conversation_id": "thread-2026-05-16-001",
  "consent_basis": "user accepted product safety and support analysis policy",
  "channel": "ai_chat",
  "locale": "zh-CN",
  "metadata": {
    "plan": "free",
    "surface": "assistant"
  },
  "messages": [
    {
      "role": "assistant",
      "content": "我在。你想先说哪一部分？"
    },
    {
      "role": "user",
      "content": "我最近真的撑不住了，感觉没有任何出路。"
    }
  ],
  "persist": true,
  "persist_messages": false,
  "include_debug": false
}
```

字段说明：

- `application_id`: 外部应用 ID，用于多租户或多产品区分。
- `external_user_id`: 外部系统的匿名用户 ID。建议传 hash 或随机 ID，不传真实邮箱/手机号。
- `conversation_id`: 外部聊天线程 ID。
- `consent_basis`: 授权或合规依据。空值会被拒绝。
- `messages`: 最近上下文。建议传最近 10-30 轮，同时保留外部系统自己的长期上下文摘要。
- `persist`: 是否保存本次分析记录。
- `persist_messages`: 是否请求保存原始消息。只有后端同时设置 `CONTEXT_ANALYSIS_STORE_RAW_MESSAGES=true` 才会保存原文；默认只保存证据窗口和分析结果。
- `include_debug`: 是否返回 embedding/LLM 调试信息。生产用户侧不建议开启。

### Response

```json
{
  "analysis_id": "5b20f2d1-7998-49f7-bae2-d2bb7b7b8b6a",
  "application_id": "acme-chat",
  "external_user_id": "sha256-or-random-user-id",
  "conversation_id": "thread-2026-05-16-001",
  "risk_level": "high",
  "risk_score": 0.68,
  "cluster": "distress_escalation_watch",
  "confidence": 0.78,
  "signals": [
    {
      "key": "hopeless_trapped_burden_language",
      "label": "绝望、被困或成为负担的表达",
      "severity": "high",
      "confidence": 0.78,
      "source": "rule",
      "evidence": ["感觉没有任何出路"],
      "suggested_action": "提供支持性回应、降低任务压力，并建议人工复核最近上下文。",
      "diagnostic": false
    }
  ],
  "immediate_actions": [
    "建议人工复核最近上下文，并提供危机/心理支持资源入口。",
    "降低模型回复的任务压力，优先采用陪伴、澄清和安全计划式回应。"
  ],
  "escalation_required": false,
  "human_review_recommended": true,
  "evidence_window": [
    "assistant: 我在。你想先说哪一部分？",
    "user: 我最近真的撑不住了，感觉没有任何出路。"
  ],
  "model_usage": {
    "rule": { "enabled": true, "signal_count": 1 },
    "embedding": { "enabled": false },
    "llm": { "enabled": false },
    "channel": "ai_chat",
    "locale": "zh-CN"
  },
  "method_version": "context_support_signals_v1",
  "diagnostic": false,
  "created_at": "2026-05-16T12:00:00Z"
}
```

## Risk Levels

- `none`: 当前窗口没有明显支持/风险信号。
- `low`: 弱支持信号，适合长期趋势记录。
- `medium`: 建议持续观察，提供支持入口。
- `high`: 建议人工复核，助手回复应转为支持和安全导向。
- `crisis`: 可能存在即时自伤/自杀风险，必须走危机升级和人工复核流程。

## 分析链路

- `rule`: 快速命中高风险语言、绝望/被困、告别/计划、退缩和功能变化等信号。
- `embedding`: 如果配置了 embedding，会把用户上下文与支持信号 anchor 做语义相似度比较，覆盖不完全词面匹配的表达。
- `LLM`: 如果配置了管理端 AI provider，会做结构化 JSON 判断，补充语义解释和建议动作。
- `cluster`: 后端把信号聚合成可接入业务流程的簇，例如 `acute_safety_escalation`、`distress_escalation_watch`、`longitudinal_support_watch`。

## 查询历史

```http
GET /api/context/analyses?application_id=acme-chat&external_user_id=user-1&conversation_id=thread-1&limit=20
X-Context-API-Key: your-server-side-key
```

返回最近分析记录。外部系统可以把它和自己的长期用户画像、工单系统或人工复核队列关联。

## 查询告警

```http
GET /api/context/alerts?application_id=acme-chat&min_risk=medium&limit=50
X-Context-API-Key: your-server-side-key
```

返回最近达到 `min_risk` 的分析记录，默认用于后台人工复核列表。`min_risk` 可取 `low | medium | high | crisis`。

## 独立 Demo

见 [ai-chat-support-demo/README.md](../ai-chat-support-demo/README.md)。其中包含两个样例：

- `ai-chat-support-demo/`: 轻量 FastAPI BFF + 静态聊天页，便于快速 smoke。
- `ai-chat-support-demo/nextchat/`: 基于 NextChat 的真实聊天前端改造版。前台聊天页通过 `app/components/support-signal-probe.tsx` 无感上报上下文，服务端路由 `app/api/distilled/context/route.ts` 转发到主后端；管理页 `/support-admin` 通过 `app/api/distilled/alerts/route.ts` 查看需要人工复核的支持信号。
