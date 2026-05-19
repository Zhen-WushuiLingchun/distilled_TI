# Senren Local Companion 部署说明

这个程序不是服务器组件。它运行在玩家自己的 Windows 电脑上，只通过 HTTPS API 连接 DSTI 服务器。

## 架构边界

- 用户本机：读取本地游戏目录、启动真实游戏、剪贴板/OCR 捕获、手动选择同步、保存用户登录凭证。
- DSTI 服务器：账号、邮箱验证码、会话、事件接收、选择记录、LLM/embedding/聚类分析、报告归档。
- 云端永远不读取用户游戏目录，不解包 `data.xp3`，不保存截图，不保存正版游戏资源。

数据链路：

```text
真实游戏/文本 hook/OCR
  -> http://127.0.0.1:17877 本机 companion
  -> https://你的域名/api/senren/companion/{session_id}/event
  -> DSTI Context Analysis / Senren report
```

## 用户本机安装

要求：

- Windows 10/11。
- Python 3.10+。
- 已有 DSTI 网站账号。
- 已安装真实千恋万花游戏。

可选 OCR：

- Tesseract OCR。
- Python 包 `Pillow`、`pytesseract`。如果只用剪贴板模式，不需要这些包。

启动：

```powershell
cd senren-local-companion
Copy-Item .env.example .env
.\start-companion.ps1
```

打开：

```text
http://127.0.0.1:17877
```

## 本机 `.env`

`.env` 只在用户本机使用，不提交仓库。

```env
DSTI_SITE_URL=https://dsti.hydrogenoxide18.com
DSTI_API_BASE_URL=https://dsti.hydrogenoxide18.com/api
SENREN_COMPANION_PORT=17877
TESSERACT_CMD=
SENREN_OCR_LANG=jpn+chi_sim+eng
SENREN_OCR_REGION=
```

OCR 区域示例：

```env
SENREN_OCR_REGION=120,650,1680,320
```

含义是 `x,y,width,height`，用于只识别游戏文本框区域。

## 使用流程

1. 在 DSTI 网站用邀请码注册并验证邮箱。
2. 运行 companion，填写网站地址和 API 地址。
3. 输入邮箱，获取验证码，完成登录。
4. 填写本地游戏目录并校验。
5. 点击“启动真实游戏”。
6. 点击“开始服务器记录”。
7. 如果手动同步：真实游戏遇到选择时，在 companion 选择对应节点并提交。
8. 如果自动捕获：选择 `clipboard` 或 `ocr`，点击“开始自动捕获”。
9. 达到报告阈值后生成报告，网站账号历史中可查看 Senren 测量记录。

## 自动捕获验收

剪贴板模式：

```powershell
Set-Clipboard "测试台词：我先把当前文本复制到剪贴板。"
Invoke-RestMethod http://127.0.0.1:17877/api/local/capture/probe `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"mode":"clipboard","send":false}'
```

期望：

- `ok=true`。
- `text_excerpt` 包含测试台词。

登录并开始服务器记录后：

```powershell
Invoke-RestMethod http://127.0.0.1:17877/api/local/capture/probe `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"mode":"clipboard","send":true}'
```

期望：

- 返回 `sent`。
- 服务器 companion session 的 `events` 数量增加。

OCR 模式：

```powershell
Invoke-RestMethod http://127.0.0.1:17877/api/local/capture/probe `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"mode":"ocr","send":false}'
```

如果失败：

- `Pillow/ImageGrab 未安装`：安装 `pip install Pillow`。
- `pytesseract 未安装`：安装 `pip install pytesseract`。
- `tesseract is not installed`：安装 Tesseract 并设置 `TESSERACT_CMD`。
- 识别慢或误识别：设置 `SENREN_OCR_REGION` 只覆盖游戏文本框。

## 服务器验收

服务器或公网可访问机器上运行：

```powershell
$env:DSTI_API_BASE_URL="https://dsti.hydrogenoxide18.com/api"
$env:DSTI_CONTEXT_API_KEY="<服务器 CONTEXT_ANALYSIS_API_KEY>"
$env:DSTI_USER_ID="<用户 user_id>"
$env:DSTI_USER_SECRET="<用户 user_secret>"
python backend/scripts/check_public_api_deployment.py --api-base-url $env:DSTI_API_BASE_URL
```

关键 PASS：

- `api_health`
- `context_authorized_analyze`
- `senren_companion_sessions_requires_user`
- `senren_companion_start_authorized`
- `senren_companion_event_authorized`

## Cloudflare / 网关配置

本机 companion 访问的是 JSON API，不是网页浏览器。Cloudflare 如果对 `/api/*` 触发 Managed Challenge、Bot Fight、Browser Integrity Check 或类似 JS challenge，本机程序只会收到 `Just a moment...` HTML，无法继续登录、刷新选择树或同步事件。

生产环境必须保证以下路径直接返回 JSON：

- `GET /api/health`
- `POST /api/auth/login`
- `POST /api/auth/login/verify`
- `GET /api/user/me`
- `GET /api/senren/roadmap`
- `GET/POST /api/senren/companion/*`

Cloudflare 推荐规则：

```text
When: URI Path starts with "/api/"
Then: Skip/Allow security features that issue browser challenges
Scope: at least Managed Challenge, Super Bot Fight/Bot Fight, Browser Integrity Check
```

如果不想放行整个 `/api/*`，至少放行上面列出的账号和 Senren companion 路由。也可以把 API 放到单独子域名，例如 `api.example.com`，该子域名不启用浏览器挑战，只保留必要的限流、鉴权和服务器侧日志。

本机 companion 已内置诊断：

```powershell
Invoke-RestMethod http://127.0.0.1:17877/api/local/remote-health
```

正常结果：

```json
{"ok":true,"remote":{"status":"ok"}}
```

如果看到：

```json
{
  "error": "cloudflare_challenge",
  "message": "远端 API 被 Cloudflare 浏览器挑战页拦截。"
}
```

说明不是 companion 登录逻辑问题，而是网关把 API 请求挡成了网页挑战；先修 Cloudflare/反代规则。

## 常见问题

- `no_active_session`：先登录并点击“开始服务器记录”。
- `cloudflare_challenge`：Cloudflare/反代对 API 路由发了浏览器挑战，按上一节放行 API JSON 路由。
- `remote_http_401`：用户凭证缺失或过期，重新邮箱登录。
- `remote_http_403`：session secret 不匹配，重新开始服务器记录。
- 事件有了但没有推进路线：正常，`event` 只用于上下文归档和分析；只有 `choice` 会推进 Senren 测量路线。
- 服务器看不到记录：确认 companion API 地址是 `https://域名/api`，不是前端站点根路径。
