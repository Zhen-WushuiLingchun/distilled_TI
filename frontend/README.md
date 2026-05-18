# Distilled TI Frontend

当前前端提供三段体验：

- 首页：项目说明 + 邀请注册 + 模式入口
- 会话页：连续答题，20 题后可随时拿报告，也可继续作答
- Story 页：Web Galgame / VN 模式
- Senren 页：本地游戏 / Senren 模式入口
- 报告页：AI 摘要、雷达图、细节百分比条、模块投影
- 历史页：查看注册用户长期会话和本地会话
- 管理页：查看模板库、实例题、改写预览、向量、资产、用户、邀请、聚类

## 本地运行

```powershell
npm install
Copy-Item .env.local.example .env.local
npm run dev
```

默认访问：

- `http://127.0.0.1:3000`

## 环境变量

可选设置：

```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000/api
NEXT_PUBLIC_ADMIN_API_BASE_URL=http://127.0.0.1:8001/api
```

如果不设置，默认也会请求上面的本地后端地址。

不要在 `frontend/.env.local` 放 DeepSeek、SiliconFlow、Resend、Volcengine、Context API 等密钥；前端只保存可公开的 API 地址。

## 说明

- 报告页依赖后端 `20` 题门槛。
- AI provider 通过 Admin 或后端 `scripts\ai_acceptance.py --save` 配置，不再由普通首页持久化。
- 若要联调，请先启动 backend，再启动 frontend。
- 完整配置和智能体验收流程见仓库根目录 `README.md`。
