# WB-VIDEO-001 执行报告 — 阶段一：接口调查

- **Task ID**：WB-VIDEO-001
- **Status**：`partial`
- **Status 说明**：只读发现 + 极小非破坏性能力测试已全部完成；另有 2 项能力验证**主动停在审批边界未执行**（生成任务消耗额度、剪映 CLI 编辑需运行时 token）。这是按任务书设计停止，不是测试失败。**本报告不代表整条流水线已经打通。**
- **Start**：2026-11-08 14:21 +0800（Asia/Shanghai, UTC+8）
- **End**：2026-11-08 14:38 +0800（取证结束）；报告定稿 14:43 +0800
- **Source commit**：`ca4afb732b951241266a82358c10b9afe49a1414`
- **Branch**：`main`
- **Repository**：`swdscsc/yaodao-agent`
- **本报告路径**：`docs/ai-collaboration/outbox/WB-VIDEO-001-report.md`

---

## 0. 一句话结论

Vidova 的本地 MCP 是**真实可用**的（18 个工具，含项目/时间线/素材操作），但**没有导出工具**、且生成能力消耗托管额度；剪映专业版 11.7.0 **内置官方 `jianying-agent-cli.exe` 与 47 条 hubcli 契约**（覆盖素材导入、时间线、音频、文本、导出），但实调用被 `JIANYING_AGENT_RUNTIME_TOKEN` 权限门槛挡住，且主程序当前未运行。**两款软件之间未发现任何官方直接接口**，只能靠文件系统 + manifest 衔接。

---

## 1. Status

`partial`。理由见上。五类结论严格区分见 §7.4；未验证项没有被写成"成功"。

---

## 2. 起止时间与时区

| 项 | 值 |
|---|---|
| 开始 | 2026-11-08 14:21:00 +0800 |
| 取证结束 | 2026-11-08 14:38:00 +0800 |
| 报告定稿 | 2026-11-08 14:43:00 +0800 |
| 时区 | Asia/Shanghai (UTC+08:00) |

---

## 3. 机器与应用版本

| 项 | 实测值 |
|---|---|
| OS | Microsoft Windows 11 家庭中文版，build 10.0.22631.6199 |
| git | 2.55.0.windows.3（PortableGit，`credential.helper=manager`） |
| curl | 8.13.0 (Windows, Schannel) |
| Python | 3.13.14 |
| Node | v22.22.2 |
| FFmpeg | 7.1-essentials_build-www.gyan.dev（在 PATH） |
| ffprobe | **不在 PATH**；剪映内置 `ffprobe.exe` 1.0.0-401a53202a 可用 |
| UIAutomation | `UIAutomationClient.dll` 存在（174,136 bytes）；未做窗口枚举 |
| GitHub 网络 | 直连 `github.com:443` 间歇性失败（connection reset / 超时）；本机 `127.0.0.1:7897` 代理可用 |

**Vidova**

| 项 | 实测值 |
|---|---|
| ProductVersion / FileVersion | 1.0.66.0 / 1.0.66 |
| 安装路径 | `%LOCALAPPDATA%/Programs/Vidova/Vidova.exe` |
| 主进程 | 运行中，Electron main + 6 个子进程；`--app-path=.../resources/app.asar`，`--user-data-dir=%APPDATA%/Vidova` |
| 用户数据 | `%APPDATA%/Vidova` 是符号链接，指向本机另一盘符目录（真实路径仅存本地 config，不公开） |
| 监听 | `127.0.0.1:17373` LISTEN，属主为主进程 |
| MCP | `POST http://127.0.0.1:17373/mcp`，protocolVersion `2025-06-18`，serverInfo `vidova-desktop 1.0.0` |

**剪映专业版**

| 项 | 实测值 |
|---|---|
| 注册表 DisplayName / Version | 剪映专业版 / **11.7.0.14652** |
| `JianyingPro.exe` 版本 | 11.7.0.c55059b72a0 |
| `agent_runtime_env` | 1.0.0，build 20261028-200301，git_hash c55059b72a0… |
| 安装路径 | `%LOCALAPPDATA%/JianyingPro/Apps/11.7.0.14652/` |
| 主进程 | **未运行**；仅 `VEDetector.exe` 辅助进程存在，且无监听端口 |
| 草稿目录 | `%LOCALAPPDATA%/JianyingPro/User Data/Projects/com.lveditor.draft/` |

---

## 4. 实际测试过的工具 / 接口

1. GitHub：`git clone` / `git ls-remote` / `git fetch`（经代理）、`git push --dry-run`、凭据可用性探测（脱敏）。
2. Vidova MCP：`GET` 路由探测、`initialize`、`tools/list`、5 次 `tools/call` 只读调用、1 次故意使用不存在 jobId 的 `kind=status` 探测。
3. Vidova 本地资产：进程/端口/版本信息、日志目录、`assets/` 目录实体文件核对。
4. 剪映：`jianying-agent-cli.exe --help`、`draft query-content --input <空 JSON 文件> --output <文件>`、`contracts.json` 及 4 份契约文件解析、注册表与目录/草稿结构只读枚举。
5. 工具链：`python --version`、`ffmpeg -version`、剪映内置 `ffprobe -version`、`node --version`。

**未做任何 UI 点击、未启动任何应用、未创建/修改任何工程或素材。**

---

## 5. 实际执行的命令与动作（脱敏，可复现）

```bash
# GitHub（代理仅按命令临时指定，未修改全局 git config）
git clone https://github.com/swdscsc/yaodao-agent.git
git -c http.proxy=http://127.0.0.1:7897 -c https.proxy=http://127.0.0.1:7897 ls-remote origin HEAD

# Vidova MCP 端点探测
curl -s -i http://127.0.0.1:17373/
curl -s -i http://127.0.0.1:17373/mcp          # GET -> 405

# MCP 握手（只读）
curl -s -X POST http://127.0.0.1:17373/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"wb-discovery","version":"1.0.0"}}}'

# 只读 tools/call 模板
curl -s -X POST http://127.0.0.1:17373/mcp -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":10,"method":"tools/call","params":{"name":"list_projects","arguments":{}}}'

# 剪映官方 CLI（只读探测，输入文件放在仓库外的临时目录）
"%LOCALAPPDATA%/JianyingPro/Apps/11.7.0.14652/jianying-agent-cli.exe" --help
"%LOCALAPPDATA%/JianyingPro/Apps/11.7.0.14652/jianying-agent-cli.exe" \
  draft query-content --input probe/input-empty.json --output probe/out-query.json
```

PowerShell 侧只读使用了 `Get-NetTCPConnection`、`Get-Process` / `Get-CimInstance Win32_Process`、注册表 Uninstall 项、`Get-Item().VersionInfo`、`Get-Content`（仅 `root_meta_info.json` / 契约 JSON）。**任何 token、密码、PAT 的值均未被打印、写入仓库或上传。**

---

## 6. 创建 / 修改的文件

### 提交到仓库（仅这两个新增文件）

| 相对路径 | 大小 | SHA-256 |
|---|---|---|
| `docs/ai-collaboration/outbox/WB-VIDEO-001-report.md` | 本文件（自引用，不计算） | — |
| `docs/ai-collaboration/status/pipeline-status.json` | 10,556 bytes | `62c2779dbb4b91111e2fd7be7d518eaa834ebdeb79d8bc3b6766d92112577dd0` |

`pipeline-status.json` 已通过 `json.load` 校验。若后续任务更新该文件，校验和以仓库 Git 历史中的最新版为准。

### 仅本机、不提交（仓库外 `probe/`）

| 文件 | 用途 |
|---|---|
| `probe/input-empty.json` | 剪映 CLI 参数契约探测输入（`{}`） |
| `probe/out-query.json` | 剪映 CLI 返回的 `PERMISSION_DENIED` 结构化结果 |
| `probe/pipeline-local.config.json` | **机器相关绝对路径本地配置**（遵循 Step 3：公开文件不放绝对路径） |

**未修改**：仓库原有任何源码、`README.md`、`listenai.toml`、协作协议 README、inbox 任务文件、Vidova 现有项目与 26 个素材、剪映 2 个现有草稿工程。

---

## 7. 验证与精确结果

### 7.1 GitHub handoff

| 项 | 结果 |
|---|---|
| remote | `https://github.com/swdscsc/yaodao-agent.git` (fetch/push) |
| 分支 | `main`，基线 `ca4afb73` |
| 读取任务 | ✅ `clone` 成功，已读 `docs/ai-collaboration/README.md` 与 `inbox/WB-VIDEO-001-bootstrap-pipeline.md` |
| 直连网络 | ❌ `git fetch` 报 `Recv failure: Connection was reset`；`curl https://github.com` 超时 |
| 经代理读取 | ✅ `127.0.0.1:7897` → `ls-remote` 返回 `ca4afb73…`；`git fetch` 走通 |
| **推送认证** | ⚠️ **受阻**：`credential.helper=manager`；`git credential fill` 在非交互模式返回空、交互模式挂起；`push --dry-run` 报 `could not read Username for 'https://github.com'`。Windows 凭据管理器存在 `git:https://github.com` 与 `git:https://swdscsc@github.com` 两条目标，但本会话无法用它完成认证。**未请求、未伪造、未提交任何 token/PAT。** 报告已本地提交；推送在提交后发起，结果以仓库 commit 历史与本次会话回报为准。 |

### 7.2 Vidova

**端口与端点（confirmed working）**

```
GET /      -> 404 {"error":"Unknown local Vidova MCP route: /"}
GET /mcp   -> 405 {"jsonrpc":"2.0","error":{"code":-32000,
              "message":"Method not allowed. The local Vidova MCP endpoint accepts POST requests."},"id":null}
GET /sse, /health, /api, /status, /tools, /json/version -> 404 同上风格
POST /mcp initialize -> 200 {"result":{"protocolVersion":"2025-06-18",
              "capabilities":{"tools":{"listChanged":true}},
              "serverInfo":{"name":"vidova-desktop","version":"1.0.0"}}...}
```

即：**有效端点只有 `POST /mcp`**，不是 `/sse`。响应 `content-type: application/json`（非 SSE）。

**`tools/list` 结果（confirmed working，18 个工具，`content-length: 20940`）**

| # | 工具 | 额度属性 | 本轮是否调用 |
|---|---|---|---|
| 1 | `list_projects` | 本地，不消耗额度 | ✅ |
| 2 | `get_active_project` | 本地 | ✅ |
| 3 | `create_project` | 本地 | ❌ 未调用 |
| 4 | `set_active_project` | 本地 | ❌ |
| 5 | `timeline_get_state` | 本地 | ✅ |
| 6 | `timeline_edit` | 本地 | ❌ |
| 7 | `clip_enhance` | 本地 | ❌ |
| 8 | `asset` | 本地（`action=transcribe` 为托管任务） | ✅ `list` / `metadata` |
| 9 | `inspect_media` | 本地 | ❌ |
| 10 | `import_asset` | 本地 | ❌ |
| 11 | `preview` | 本地 | ❌ |
| 12 | `generate_asset` | **消耗托管额度** | ⚠️ 仅测 `kind=status` + 假 jobId |
| 13 | `sfx` | 本地 | ❌ |
| 14 | `component` | 本地 | ❌ |
| 15 | `branch_action` | 本地 | ❌ |
| 16 | `project_history` | 本地 | ❌ |
| 17 | `recipe` | 本地 | ❌ |
| 18 | `sleep` | 本地 | ❌ |

补充事实：所有工具 `execution.taskSupport = "forbidden"` → **调度器不能依赖 MCP Task 原语，必须自己按 `jobId` 轮询**。`generate_asset` 的 `inputSchema` 只声明了 `kind / resultStart / resultEnd`，而 `prompt / durationSeconds / aspectRatio / resolution / jobId / voice` 等只出现在 description 里，**参数契约尚未验证，不可凭猜测构造调用**。

**只读 `tools/call` 精确结果**

| 调用 | 返回（摘要） |
|---|---|
| `list_projects` | 1 个项目：`Recording 2026-11-07 13-32-19`，id `042ac827-…` |
| `get_active_project` | 同上 |
| `timeline_get_state` | 608×1080 / 60 fps / 1 layer / 1 clip / 58.33 s |
| `asset(action=list)` | 26 个素材，逐条含类型、大小、时长、分辨率，并附 JSON（含 `storagePath`） |
| `asset(action=metadata, assetId=62023b6c…)` | `Metadata for '26-Tahoe-Beach-Day.jpg'` / `Extract metadata: 1600x900` |
| `generate_asset(kind=status, jobId=WB-VIDEO-001-NO-SUCH-JOB)` | `isError:true` — `The requested resource was not found. (ref: 7f72668d-…)`；**未创建任何任务** |

**本地素材路径（confirmed working）**：`storagePath = assets/<projectId>/<assetId>/` 已核对为真实目录，内含 `source`（245,332 bytes）与 `thumbnail.jpg`（46,438 bytes）。这证明「取得生成结果 → 落到本地素材路径」的落地形式存在，但**尚未用新生成任务端到端验证**。

**额度边界（关键，blocked by approval）**：`generate_asset` 描述原文包含 `Image generation uses your image-generation allowance. Speech is included with a usage quota.`；`asset(action=transcribe)` 描述为 `starts a hosted transcription job`。按任务书 "Do not spend paid credits; if unclear whether a test consumes credits, ask first"，**本轮未创建任何生成任务、未调用 transcribe、未消耗任何额度、未购买任何服务**。

**日志摘录（脱敏）**：`vidova-2026-11-08.log` 中出现
`{"level":"error","scope":"Failed to synchronize generation jobs","message":"Something went wrong. Try again later."}`
→ 托管生成任务同步依赖外部服务且曾失败，调度器必须做容错与超时处理。

**导出能力（unavailable）**：18 个工具中**没有 export / render / 导出成片工具**。Vidova 侧无法直接产出可交付成片；导出必须另寻路径（例如剪映或外部 FFmpeg）。

### 7.3 剪映专业版

**原生 CLI（confirmed working 调用 / blocked by permissions 实调用）**

```
$ jianying-agent-cli.exe --help
usage: jianying-agent-cli draft <fetch-feishu-doc|query-content|plan-patch|validate-patch|apply-patch> --input <json> [--output <json>]

# --input 传内联 '{}'  -> {"code":"INVALID_ARGUMENT","command":"draft query-content",
#                          "message":"系统找不到指定的文件。","ok":false,...}
# --input 传真实 JSON 文件 + --output 文件：
{"code":"PERMISSION_DENIED","command":"draft query-content",
 "message":"JIANYING_AGENT_RUNTIME_TOKEN is required","ok":false,
 "output":"...","result":{},"runId":"local-run"}
```

→ CLI 可正常解析命令、写出结构化输出文件，但**实际读取/编辑草稿需要运行时 token**；该 token 预期由剪映主程序运行时注入。当前主进程未运行，本会话也没有该变量。**没有提取、伪造、存储或提交任何 token。**

**`hubcli` 契约（静态读取，detected but not tested）**：`Resources/agent_runtime_env/cli/hubcli/contracts.json` → protocol `custom-agent.hub-cli.v1`、`maxInputBytes 1048576`、**47 条命令**，包含 `asset.list / asset.get / asset.import / asset.export`、`canvas.video.add / canvas.audio.add / canvas.text.add / canvas.image.add`、`canvas.batch / canvas.check / canvas.nodes.move / canvas.storyboard.create`、`canvas.audio.setTtsVoice / setSpeechRate / setSubType`、`canvas.generation.get / resubmit` 等。

单份契约带 `effect` 与 `permission.risk` 字段，实测：

| 契约 | effect | required | risk |
|---|---|---|---|
| `canvas.help` | `read` | `[]` | `readonly` |
| `asset.import` | — | `request_id`, `source` | — |
| `asset.export` | `write` | `request_id`, `asset_id`, `relative_path` | `confirm_before_write` |
| `canvas.batch` | `write` | `request_id`, `input` | `confirm_before_write` |
| `canvas.audio.add` | `write` | — | `confirm_before_write` |

→ 原生契约在能力上覆盖「导入素材 / 时间线编排 / 旁白与音频 / 字幕文本 / 导出」，**但这些只是随包资源的 schema，不等于已经验证可调用**。

**工程文件与导入导出（detected but not tested）**：草稿根目录含 `root_meta_info.json` 及 2 个现有工程目录（`11月7日`、`yaodao_yaodao_ep`），每个工程含 `draft_content.json`、`draft_meta_info.json`、`draft_cover.jpg` 等。工程是**文件化 JSON**，理论上可复制/导入；但**未验证 UI 导入导出功能，也绝未伪造或改写任何工程文件**（遵守用户「不得通过伪造项目文件宣称完成」）。这两个现有工程一个字节都没动。

**UI Automation（detected but not tested）**：系统存在 `UIAutomationClient.dll`；但当前无剪映主窗口可枚举，且运行时加载 .NET 程序集被本执行环境安全策略拦截，因此未做窗口自动化实测。

**未发现**：剪映与 Vidova 之间的任何官方直接接口；两软件间未发现本地 HTTP/MCP 直通。

### 7.4 五类结论汇总

| 类别 | 项目 |
|---|---|
| **confirmed working** | GitHub 读取/抓取；Vidova 进程与 17373 端口；`POST /mcp` 端点；`initialize`；`tools/list`（18 工具）；Vidova 5 组本地只读调用；素材真实本地路径解析；`kind=status` 状态通道与错误格式；剪映版本/安装/进程事实；剪映 CLI 可调用且返回结构化结果；47 条契约解析；草稿 JSON 格式；FFmpeg / Python / 剪映内置 ffprobe |
| **detected but not tested** | Vidova `create_project` / `timeline_edit` / `import_asset` / `preview` / `component`（均标注不消耗额度但未写操作）；剪映 47 条写契约；剪映工程 UI 导入导出；UI Automation 窗口自动化 |
| **unavailable** | Vidova MCP 的导出/渲染工具（工具列表中不存在）；Vidova ↔ 剪映官方直接桥接接口 |
| **blocked by permissions** | 剪映 `jianying-agent-cli.exe` 实际编辑调用（缺运行时 token）；GitHub push 认证（非交互环境无法完成 GCM 授权） |
| **blocked by approval（额度）** | `generate_asset` 创建真实生成任务、`asset action=transcribe` |
| **not attempted** | 真实 jobId 的「生成→轮询→结果落盘」链路；创建无害空测试项目；剪映导入/剪辑/导出；FFmpeg 自动质检；AI 视觉质检；返工闭环（均为后续阶段） |

---

## 8. 证据材料

- 本报告中的 HTTP 响应片段、MCP JSON 结果、CLI 输出、契约字段均为本次实测原样摘录（仅做了脱敏与截断）。
- 未提交任何截图、视频或大体积媒体（遵守 README「不提交大原始媒体」）。可复现证据为本报告 §5 命令 + §7 返回值。
- 机器相关绝对路径保存在仓库外本地 config，公开文件统一用 `%LOCALAPPDATA%` / 占位符。

---

## 9. 已知问题与未验证假设

1. **不能把端口开放当成接口可用**：本轮对每个能力单独调用了 `tools/call` 才下结论。
2. **Vidova 无导出工具**：若最终成片由剪映导出，则 Vidova 产物只能是中间素材；若走 FFmpeg 合成，需要另建时间线渲染器。这是架构级缺口，需 ChatGPT 决策。
3. **`generate_asset` 参数契约不完整**：schema 未声明 prompt / durationSeconds / jobId 等字段，不能凭 description 猜测构造调用，下阶段必须用受控单测确认。
4. **托管生成依赖外部服务**：日志出现 `Failed to synchronize generation jobs`，需要超时、幂等与重试设计。
5. **剪映 token 机制未知**：不清楚是否由主程序启动自动注入、是否需要登录/会员、是否随版本变化；`canvas_agent/package-manifest.json` 标注 `platform: darwin-arm64` 与 Windows 安装并存，说明资源包跨平台复用，不能推断 Windows 原生路径完全一致。
6. **剪映契约是随包资源，不等于公开稳定 API**：版本升级可能变更；`confirm_before_write` 意味着写操作需要确认流程。
7. **GitHub 推送认证**：本会话无可用非交互凭据；网络还需经本机 7897 代理（未改全局配置）。
8. **未验证 UI Automation 实际效果**：Qt/CEF 混合界面常出现控件树不可见，不能预设可行。
9. **没有验证任何"两个软件直连"**：目前唯一可信衔接方式是文件系统 + manifest，且尚未实现。

---

## 10. 给 ChatGPT 的下一步建议（WB-VIDEO-002 提案）

**先请用户回答 3 个审批问题**，再执行任何写操作：

1. 是否允许消耗 **1 次最小额度**做单张图片或最短语音生成测试（明确额度来源与上限）？
2. 是否允许**启动剪映主程序**并创建一个不触碰现有 2 个工程的空测试草稿？
3. 剪映导出是否需要登录/会员；若原生 CLI 的 token 始终不可用，是否接受 UI Automation 备选路线？

**建议的 WB-VIDEO-002 范围**：
- Vidova：在授权下跑 1 次 `generate_asset`，记录**真实 jobId → `kind=status` 轮询 → 完成 → 结果落盘绝对路径 → ffprobe 校验**的完整证据链，并补齐真实参数契约。
- 剪映：启动主程序后确认 `JIANYING_AGENT_RUNTIME_TOKEN` 是否自动注入；若可用，先测 `draft query-content` 只读，再测 `plan-patch` / `validate-patch` 与一个空草稿的 `apply-patch`；全程只在新工程上操作。
- 若剪映原生接口不可用，再评估 UI Automation（先做窗口枚举可行性验证，不直接写工程）。

**本阶段严格停在审批边界，等待审核后再进入下一阶段。**

---

## 附录 A：Step 3 handoff 契约提案（仅设计，未落地）

### A.1 每镜头 manifest 条目（唯一编号，禁止重复导入）

```json
{
  "asset_id": "S001-A01",
  "shot_id": "S001",
  "purpose": "开场：老人独自坐在餐桌前",
  "prompt": "generation prompt",
  "file_path": "assets/generated/S001-A01.mp4",
  "file_type": "video/mp4",
  "duration_seconds": 5.0,
  "width": 1920,
  "height": 1080,
  "fps": 30,
  "source_type": "vidova",
  "source": "vidova|local|stock|manual",
  "is_ai_generated": true,
  "is_real_footage": false,
  "job_id": null,
  "checksum_sha256": null,
  "generation_status": "pending",
  "qa_status": "not_checked",
  "quality_checks": ["decode", "black_frame", "silence", "freeze", "peak", "av_sync"],
  "allow_edit": false,
  "retry_count": 0,
  "notes": []
}
```

- `asset_id = S<shot###>-A<seq>` 全局唯一；去重键 `(shot_id, source, checksum_sha256)`。
- `allow_edit` 仅在 `qa_status == passed` **且** SHA-256 校验通过 **且** 素材未标记异常时为 `true`。
- `file_path` 一律相对路径；**机器绝对路径只存仓库外本地 config**。

### A.2 任务状态机

```
PENDING → GENERATING → COMPLETED → VALIDATING → APPROVED → EDITING → EXPORTED → QA_CHECKING → DELIVERED
                ↓            ↓            ↓
             FAILED   REVIEW_REQUIRED  ESCALATED
             (重试)     (人工审核硬节点)  (超限/需人工)
```

用户要求的 `PENDING / GENERATING / COMPLETED / FAILED / REVIEW_REQUIRED` 全部包含；`VALIDATING / APPROVED / EDITING / EXPORTED / QA_CHECKING / DELIVERED / ESCALATED` 为流水线后续环节补充。

### A.3 有界重试与返工

| 参数 | 值 |
|---|---|
| 单镜头最大生成尝试次数 | 3（首次 + 2 次重试） |
| 退避 | 5s / 15s / 45s |
| 生成任务轮询上限 | 10 分钟，超时 → `FAILED` |
| 成片返工闭环最大轮次 | 2；超过 → `REVIEW_REQUIRED` 人工审核 |
| 缺陷路由 | 素材问题 → Vidova；剪辑 → 剪映；音频 → 音频模块；字幕 → 字幕模块 |
| 硬停止点 | `REVIEW_REQUIRED` / `ESCALATED` 必须人工确认，禁止自动继续 |

---

## 附录 B：验收标准核对

| # | 标准 | 结果 |
|---|---|---|
| 1 | WorkBuddy 能从 GitHub 读到任务 | ✅ |
| 2 | WorkBuddy 能提交并推送报告 | ⚠️ 本地提交完成；推送认证见 §7.1，结果以仓库 commit 历史与会话回报为准 |
| 3 | Vidova 与剪映能力分别有证据记录 | ✅（§7.2 / §7.3 / §7.4） |
| 4 | 未修改任何现有工程或源素材 | ✅ |
| 5 | 未使用付费服务或额度 | ✅（`generate_asset` / `transcribe` 调用数 = 0；无购买；无 token 提交） |

**声明**：以上均为实测观察结果；任何未被实际调用的 capability 均未被标记为成功。阶段一调查完成 ≠ 整条流水线打通。
