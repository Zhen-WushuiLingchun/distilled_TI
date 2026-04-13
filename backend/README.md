# Distilled TI Backend

当前后端提供一条可跑的单会话闭环：

- 会话启动：`POST /api/session/start`
- 下一题调度：`POST /api/question/next`
- 提交回答：`POST /api/response/submit`
- 获取会话摘要：`GET /api/session/{id}/summary`
- 获取报告：`GET /api/session/{id}/report`
- 获取二维地图：`GET /api/session/{id}/map`
- 删除当前会话：`DELETE /api/session/{id}`
- 配置 AI Provider：`POST /api/ai/config`
- 读取 AI 配置状态：`GET /api/ai/config`
- 题目改写预览：`POST /api/ai/rewrite-question`
- 新增自定义题目：`POST /api/admin/item-template/create`
- 模板列表：`GET /api/admin/templates`
- 实例题列表：`GET /api/admin/item-instances`
- 本地会话列表：`GET /api/admin/sessions`
- 过期清理：`POST /api/admin/cleanup`

## 本地运行

```bash
python -m pip install -e .[dev]
uvicorn app.main:app --reload
```

默认地址：

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

## AI 接口说明

- 当前版本不会把 API Key 返回给前端。
- 通过 `/api/ai/config` 可动态设置：
  - `provider`
  - `model`
  - `base_url`
  - `api_key`
- 报告接口会优先调用已配置模型生成中文摘要。
- 如果未配置模型或调用失败，会自动降级为后端生成的 deterministic 文案。

## 会话规则

- 默认答到 `20` 题后开放正式报告。
- 会话可继续一直答题，当前上限是 `10000`。
- 用户可以在前端主动结束并删除会话，不做长期保存。
- 活跃会话会同步写入本地 SQLite：`distilled_ti_local.db`

## 题库与约束

- 题库已包含 core / sub / module / anchor 的基础模板。
- `/api/admin/item-template/create` 支持提交自定义题目模板。
- `/api/ai/rewrite-question` 会基于模板 + 会话状态给出受限改写预览，默认优先走真实模型。
- 新题目会经过约束校验：
  - 维度数量限制
  - moralizing 文案拦截
  - 敏感主题拦截
  - 选项数量检查

## 聚类与历史

- 报告聚类已切换为 `scikit-learn KMeans` 方案。
- 会话与实例会写入本地 SQLite，并附带过期时间。
- 历史页展示的是 TTL 生命周期内的本地会话，不是永久存档。
