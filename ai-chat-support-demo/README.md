# AI Chat Support Signal Demo

这个目录是独立 demo，不接入主前端路由。它展示任意 AI 助手如何把授权聊天上下文发到 Distilled TI 后端的通用 `context/analyze` API，并获得非诊断的支持/风险信号。

当前包含两个入口：

- 根目录静态 demo：最小 FastAPI BFF，方便快速 smoke。
- `nextchat/`：基于 upstream NextChat 的真实聊天前端改造版，聊天页无感上报上下文，`/support-admin` 查看后台告警。

## 运行

1. 先启动主后端：

```powershell
cd ..\backend
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

2. 启动本 demo：

```powershell
cd ..\ai-chat-support-demo
python -m uvicorn server:app --host 127.0.0.1 --port 3100 --reload
```

3. 打开 `http://127.0.0.1:3100`。

## 可选模型

如果设置了 OpenAI-compatible 聊天模型，demo 会调用真实助手；否则使用本地 fallback 文案。

```powershell
$env:DEMO_CHAT_BASE_URL="https://api.example.com/v1"
$env:DEMO_CHAT_API_KEY="..."
$env:DEMO_CHAT_MODEL="your-chat-model"
```

如果主后端设置了 `CONTEXT_ANALYSIS_API_KEY`，demo 也要设置同名转发 key：

```powershell
$env:DISTILLED_TI_CONTEXT_API_KEY="..."
```

## 接入点

demo 每轮聊天后调用：

```http
POST http://127.0.0.1:8000/api/context/analyze
```

它只把结果显示在右侧 Developer / Safety Console；真实产品可以把这个面板隐藏到后台，仅供安全支持、人工复核或企业风控流程使用。

## NextChat 入口

```powershell
cd .\nextchat
npm install --ignore-scripts --legacy-peer-deps --package-lock=false
npm run dev
```

配置见 [nextchat/README_DISTILLED_TI.md](nextchat/README_DISTILLED_TI.md)。聊天页本身不展示心理分析，后台查看地址为 `http://127.0.0.1:3000/support-admin`。

## 边界

- 返回的是 `support_signals`，不是心理疾病诊断。
- 外部产品必须有用户授权、隐私政策或企业合规依据，不能把该接口用于隐蔽监控。
- `crisis` 级别应触发人工复核和当地危机支持资源；在美国可提示 988。
