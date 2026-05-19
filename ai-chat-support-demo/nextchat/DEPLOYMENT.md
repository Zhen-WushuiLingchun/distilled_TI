# NextChat 心理支持信号 Demo 部署说明

这个目录是独立于 DSTI 主前端的聊天助手 demo。它的作用是证明外部 AI 助手可以用统一 API 接入 DSTI 的长期上下文分析、embedding/LLM/聚类支持信号系统。

## 架构

```text
用户在 NextChat 正常聊天
  -> NextChat 浏览器端采集最近聊天上下文
  -> NextChat server route /api/distilled/context
  -> DSTI Public API /api/context/analyze
  -> 管理员在 /support-admin 查看告警
```

浏览器不直接持有 `CONTEXT_ANALYSIS_API_KEY`。该 key 只放在 NextChat 服务端 `.env.local` 中。

## 服务器依赖

必须先部署并启动 DSTI Public API：

```text
https://你的域名/api/health
https://你的域名/api/context/analyze
https://你的域名/api/context/alerts
```

生产环境必须设置：

```env
CONTEXT_ANALYSIS_API_KEY=<你自己生成的服务端接入 key>
CONTEXT_ANALYSIS_ALLOW_UNAUTH_LOCAL=false
```

如果要启用真实 LLM、embedding、聚类增强，DSTI 后端还需要配置 DeepSeek、SiliconFlow、Qdrant/本地向量库等变量，见根目录 `README.md`。

## NextChat `.env.local`

从模板复制：

```powershell
cd ai-chat-support-demo\nextchat
Copy-Item .env.template .env.local
```

最小配置：

```env
DISTILLED_TI_API_BASE=https://dsti.hydrogenoxide18.com
DISTILLED_TI_CONTEXT_API_KEY=<与 DSTI 后端 CONTEXT_ANALYSIS_API_KEY 一致>
DISTILLED_TI_APPLICATION_ID=nextchat-support-demo
DISTILLED_TI_CONSENT_BASIS=user terms and local demo consent allow product safety support analysis
DISTILLED_TI_ADMIN_TOKEN=
NEXT_PUBLIC_DISTILLED_TI_SHOW_SIGNAL_BADGE=false
```

聊天模型配置示例：

```env
DEEPSEEK_API_KEY=<你的 DeepSeek key>
BASE_URL=https://api.deepseek.com
CUSTOM_MODELS=+deepseek-v4-pro
DEFAULT_MODEL=deepseek-v4-pro
CODE=<访问密码，可选>
HIDE_USER_API_KEY=1
```

如果你的 NextChat fork 使用 `DEEPSEEK_URL`，也可以同步设置：

```env
DEEPSEEK_URL=https://api.deepseek.com
```

## 启动

推荐从父目录启动：

```powershell
cd ai-chat-support-demo
.\start-nextchat-demo.ps1 -Port 3101 -Install
```

Linux：

```bash
cd ai-chat-support-demo
PORT=3101 INSTALL=auto ./start-nextchat-demo.sh
```

手动启动：

```powershell
cd ai-chat-support-demo\nextchat
npm install --ignore-scripts --legacy-peer-deps --package-lock=false
npm run dev
```

访问：

```text
http://127.0.0.1:3101
http://127.0.0.1:3101/support-admin
```

## 验收

类型检查：

```powershell
cd ai-chat-support-demo\nextchat
npx tsc --noEmit --pretty false
```

构建：

```powershell
npm run build
```

说明：当前 upstream NextChat 依赖组合下，`npm run lint` 可能触发 `unused-imports/no-unused-imports` 规则崩溃；以 `tsc` 和 `next build` 作为此 demo 的主要验收。

接口 smoke：

1. 打开普通聊天页，发送 3-5 轮日常对话。
2. 浏览器 Network 中应出现 `/api/distilled/context`。
3. 打开 `/support-admin`。
4. 如果后端有中高风险或支持信号，后台列表应显示对应记录。

服务器端 smoke：

```powershell
$env:DSTI_API_BASE_URL="https://dsti.hydrogenoxide18.com/api"
$env:DSTI_CONTEXT_API_KEY="<服务器 CONTEXT_ANALYSIS_API_KEY>"
python backend/scripts/check_public_api_deployment.py --api-base-url $env:DSTI_API_BASE_URL
```

关键 PASS：

- `context_requires_api_key`
- `context_authorized_analyze`

如果 `context_authorized_analyze` 失败：

- 检查 NextChat `.env.local` 的 `DISTILLED_TI_CONTEXT_API_KEY` 是否和后端一致。
- 检查 `DISTILLED_TI_API_BASE` 是否不带 `/api` 后缀；NextChat route 会自己拼 `/api/context/...`。
- 检查 DSTI 后端日志中的 LLM/embedding provider 错误。

## 安全边界

- 输出是非诊断支持信号，不是临床诊断。
- 企业或个人开发者必须有用户授权、隐私政策或合规依据。
- 浏览器端不展示心理分析细节，默认只在 `/support-admin` 后台查看。
- `crisis` 级别必须进入人工复核流程，不能由模型自动做高风险决策。
