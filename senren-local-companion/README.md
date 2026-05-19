# Senren Local Companion

这是给千恋万花本地游戏准备的独立 companion 程序。它运行在用户自己的电脑上，负责读取本机游戏目录、启动真实游戏，并把用户在真实游戏中遇到的选择同步到 Distilled TI 服务器。

## 当前能力

- 本机校验游戏目录，确认存在 `SenrenBanka.exe`、`千恋＊万花.exe`、`data.xp3`、`scenario.xp3`、`scenario.pck` 或 `Script.pck` 等关键文件。
- 本机只读扫描 Kirikiri/XP3 布局，识别主剧情包候选，例如 `data.xp3`，并给出 hook 入口建议。
- 本机启动真实游戏 exe，不要求服务器能访问用户电脑文件。
- 填写网站/API 地址，支持连接自部署服务器。
- 使用网站账号的邮箱验证码登录，凭证只保存在用户本机。
- 拉取服务器端 Senren 选择树，用户在真实游戏中遇到选择后，在 companion 面板里选择对应分支并同步。
- 在选择发生前，也可以只同步当前剧情上下文；本机 hook 可以调用 `http://127.0.0.1:17877/api/local/hook/event` 上传当前台词、可见选项和 route marker。
- 内置本机自动捕获入口：
  - `clipboard`：剪贴板桥接，适合游戏/翻译工具/文本 hook 已经能复制当前台词的情况。
  - `ocr`：屏幕 OCR fallback，需要本机安装 Tesseract，不保存截图，只上传识别到的文本摘要。
- 服务端按登录用户持久化本地游戏测量记录，网页端可通过账号查看历史。

## 不做什么

- 不修改、重打包或覆盖正版游戏文件，尤其不写入 `data.xp3`。
- 不把进程注入、内存读取或游戏包解析放到云端服务器。
- 不上传 `data.xp3`、存档、截图或原始游戏资源。
- 不生成伪剧情冒充真实千恋万花内容。

当前版本已经具备可验证的本机自动捕获最小链路：剪贴板桥接和 OCR。更深的文本层 hook、存档解析或日志解析应继续放在本机 companion 内扩展，并复用同一个本地事件 API。

## `data.xp3` 和 hook 边界

`data.xp3` 通常是 Kirikiri/XP3 游戏的核心数据包，可能包含剧情脚本、索引或资源。当前 companion 只做文件名、大小、相对路径和角色判断，不解包、不上传、不解析正文。

推荐 hook 顺序：

1. 本机文本层或剪贴板桥接：捕获当前显示台词、可见选项和 route marker。
2. OCR fallback：文本层不可用时，从屏幕识别当前台词和选项。
3. 存档/日志解析：只有格式稳定且不需要上传原始文件时才做。
4. 手动同步：始终保留，作为最稳 fallback。

服务端只负责账号、会话、测量分析、报告和归档。它不应该也不能直接判断用户本机 `data.xp3` 的内容。自动 hook 捕获到的数据应先发给本机 companion，再由 companion 带用户凭证和 session secret 调用服务器 API。

## 自动捕获模式

### 剪贴板桥接

这是默认推荐模式。它不依赖额外 Python 包。只要真实游戏、翻译器、文本 hook 工具或用户手动复制了当前台词，companion 就会检测剪贴板变化并去重上报。

使用流程：

1. 登录 companion。
2. 点击“开始服务器记录”。
3. 捕获模式选择“剪贴板桥接”。
4. 点击“开始自动捕获”。
5. 在游戏/文本工具中复制当前台词或选项文本。
6. `captureStatus.sent_count` 增加，服务器记录中会出现 `source=clipboard` 的事件。

### OCR fallback

OCR 模式适合没有稳定文本 hook 的环境，但对识别质量和性能更敏感。

Windows 推荐安装 Tesseract 后创建 `.env`：

```env
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
SENREN_OCR_LANG=jpn+chi_sim+eng
SENREN_OCR_REGION=
```

如果 OCR 整屏太慢，可以把 `SENREN_OCR_REGION` 设置为文本框区域，例如：

```env
SENREN_OCR_REGION=120,650,1680,320
```

格式是 `x,y,width,height`。companion 只在内存中截图识别，不保存图片。

本机 hook 事件入口示例：

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:17877/api/local/hook/event `
  -ContentType 'application/json' `
  -Body '{
    "event_type": "choice_snapshot",
    "scene_title": "共通线 · 神社前",
    "dialogue_text": "屏幕上当前显示的一句台词",
    "visible_choices": ["选项 A", "选项 B"],
    "route_marker": "common_ch1_choice_03",
    "source": "hook"
  }'
```

## 启动

Windows PowerShell:

```powershell
cd senren-local-companion
.\start-companion.ps1
```

或直接：

```powershell
python companion.py
```

启动后打开：

```text
http://127.0.0.1:17877
```

## 配置项

- 网站地址：例如 `https://dsti.hydrogenoxide18.com`
- API 地址：例如 `https://dsti.hydrogenoxide18.com/api`
- 游戏目录：例如 `D:\Games\SenrenBanka`
- 登录邮箱：必须是已通过邀请码注册的网站账号

配置会保存在用户本机：

```text
%APPDATA%\DistilledTI\senren-companion\config.json
```

## 推荐使用流程

1. 在网站用邀请码注册账号。
2. 本机运行 companion。
3. 填写网站地址和 API 地址。
4. 用邮箱验证码登录。
5. 填写真实千恋万花安装目录并校验。
6. 点击“启动真实游戏”。
7. 游戏里遇到选择时，在 companion 选择对应章节/选项并同步。
8. 达到报告阈值后，点击“生成/刷新报告”。
9. 回到网站账号查看本地游戏测量历史。

## 验收

最小本机验收：

```powershell
python -m py_compile companion.py
.\start-companion.ps1
```

打开 `http://127.0.0.1:17877` 后验证：

- `/api/local/capture/status` 返回 `running=false`。
- 点击“探测”可以读取当前剪贴板文本。
- 登录并开始服务器记录后，点击“探测并发送”能在服务器 `GET /api/senren/companion/sessions` 中看到 `events` 增加。
- 真实游戏选择同步后，`choices_count` 增加，达到服务器阈值后可以生成报告。
