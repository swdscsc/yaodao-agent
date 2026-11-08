# WB-VIDEO-003 · 环境调查审计（Vidova / 剪映 / 凭据 / TTS）

调查时间：2026-11-08 15:43–15:50 +0800。基准：远端 `main` = `08ffda5199cffccf762e810f139ab8bf1522fe2b`。
机器可读原始记录：`evidence/environment_probe.json`（已脱敏，无绝对路径 / 账号 / 密钥）。

> 状态口径严格区分：**接口存在** ≠ **接口可调用** ≠ **调用成功** ≠ **实际生成了有效视频**。本轮**没有任何一步达到第 4 级**。

---

## 1. Vidova 1.0.66.0

| 项 | 实测 |
|---|---|
| 安装 / 版本 | 已安装，`Vidova.exe` ProductVersion `1.0.66.0`（`%LOCALAPPDATA%/Programs/Vidova/`） |
| 进程 | 主进程 PID 9196 + 6 个子进程，运行中（启动于 2026-11-07 22:12） |
| 端口 | `127.0.0.1:17373` **LISTEN**，属主 PID 9196 |
| MCP 端点 | `POST /mcp`，JSON-RPC 2.0，streamable HTTP；`initialize` 成功（protocolVersion `2025-06-18`，serverInfo `vidova-desktop 1.0.0`） |
| `tools/list` | **18 个真实工具**，与 WB-VIDEO-002 一致，无新增导出/渲染工具 |

### 1.1 能力分级

| 能力 | 接口存在 | 可调用 | 调用成功 | 生成有效视频 |
|---|:---:|:---:|:---:|:---:|
| `initialize` / `tools/list` | ✅ | ✅ | ✅ | — |
| `list_projects` / `get_active_project` | ✅ | ✅ | ✅ | — |
| `set_active_project` / `create_project` | ✅ | ✅ | ✅ | — |
| `import_asset` | ✅ | ✅ | ❌ 窗口门阻断 | ❌ |
| `timeline_get_state` / `timeline_edit` / `preview` | ✅ | ✅ | ❌（新建项目）/ ✅（GUI 已打开的原项目） | ❌ |
| `generate_asset` | ✅ | 未调用（额度红线） | ❌ | ❌ |
| 导出 / 渲染 | ❌ 不存在 | — | — | — |

### 1.2 窗口门 `No open Vidova editor window is registered`（重点排查）

在 WB-VIDEO-002 遗留的空测试项目 `893d1af1-0d6e-42a9-9489-a996307faeb7` 上重新复现（**未新建项目、未导入任何素材**）：

```
set_active_project -> OK
timeline_get_state  -> No open Vidova editor window is registered for projectId 893d1af1-...
asset list          -> 同样错误
import_asset local  -> 同样错误
preview captureFrame-> 同样错误
```

**正确对照组**：切回 GUI 已打开的原项目 `042ac827-fe6c-4e1e-8305-7cadf2b143fd` 后，`timeline_get_state` 立即成功（1 layer / 1 clip / 58.33 s / 608×1080），`asset list` 返回 26 个素材。→ 结论：editor 类工具绑定的是**已在 GUI 打开的编辑器窗口**，MCP 自身无法打开窗口。测试结束后已把 active project 恢复为原项目并验证。

### 1.3 `app.asar` 静态分析（只读，未修改安装目录）

- `No open Vidova editor window is registered` 与 `MCP dispatch failed; project editor is not registered` 定位在主包中。
- `AppTrayCommandSchema` 是 zod `discriminatedUnion("type", [...])`，包含 `open-project` + `projectId`、`new-project`、`start-recording`、`import-video`、`open-settings`、`open-shortcuts`、`upload-diagnostics`；`AppTrayCommandEventSchema = { command: ... }` 经 `electron.ipcRenderer.on(IPC_CHANNELS.appTrayCommand, ...)` 投递。
  → **`open-project` 是渲染进程内部托盘 IPC 事件，不是外部可调用 API / MCP 工具**。要打开项目窗口，只能走 GUI 托盘菜单或 UI Automation；本轮未获得对 Vidova 桌面做 UI Automation 的授权（WB-VIDEO-003 §4 的 UI Automation 授权仅限剪映独立测试草稿），因此**未执行**。
- **新增真实参数契约**：`AssetStoreImportPathsInputSchema = zod.object({ projectId: string.min(1), absolutePaths: array(string.min(1)) }).strict()`。即 `import_asset action=local` 的参数是 **`absolutePaths`**，不是 WB-VIDEO-002 猜过的 `paths / files / filePaths / path`。`tools/list` 的 `inputSchema` 只声明 `action / resultStart / resultEnd`，真实参数藏在 description 与内部 schema 里。这是下一阶段可直接使用的证据，但**本轮仍未实调成功**（被窗口门挡住）。

### 1.4 额度与收费风险（未付费、未生成）

| 问题 | 结论 |
|---|---|
| 单次生成是否消耗额度 | **是**。`generate_asset` 描述：「Uses hosted quota. This runs a Vidova cloud service.」「Image generation uses your image-generation allowance. Speech is included with a usage quota.」 |
| 是否有免费额度 | **存在 Free plan 线索**（app.asar 错误串 `Verify your account to use AI on the Free plan.`），但**未验证账户实际状态** |
| 剩余免费额度 | **UNVERIFIED**：18 个 MCP 工具中没有额度查询工具；查询余额需认证托管调用，本轮授权不含此项 |
| 自动续费 / 收费风险 | **UNVERIFIED**：未在 asar 发现自动续费证据；但存在 `Upgrade your plan to continue.`、`Your usage limit has been reached.`、`You have reached the lifetime allowance for this feature.`、`Provide a valid credential to continue.`，说明有付费墙与终身上限 |
| 能否零额度测试项目创建/素材导入 | 项目创建 ✅ 已实测零额度；素材导入接口标注零额度，但**当前被窗口门阻断**，未调用成功 |
| 本轮 `generate_asset` 调用数 | **0** |

→ **按任务书要求立即停在付费红线前**：需用户明确批准「1 次最小额度生成 + 明确的额度余量上限」后才可进入 WB-VIDEO-004。未使用任何来源不明的账号或密钥。

### 1.5 空测试项目 `893d1af1-…` 状态

`list_projects` 返回 2 个项目：空的 `WB-E2E-20261108-TEST`（893d1af1…）与用户的 `Recording 2026-11-07 13-32-19`（042ac827…）。前者**仍为空、未导入任何素材**；MCP 无 `delete_project` 工具。按任务书「擅自清理之前的测试项目」属禁止项 → **保留，不删除**，仅报告状态。

---

## 2. 剪映专业版 11.7.0.14652

| 项 | 实测 |
|---|---|
| 安装 / 版本 | 已安装，`%LOCALAPPDATA%/JianyingPro/Apps/11.7.0.14652/`，`JianyingPro.exe` 版本 `11.7.0.c55059b72a0` |
| 启动前 | 主程序**未运行**，仅 `VEDetector.exe` 辅助进程 |
| **启动主程序**（§4 明确授权） | ✅ `Start-Process` 返回 PID 21424；随后出现主窗口 PID 22220，标题 `JianyingPro`，共 8 个 JianyingPro 进程 + 1 个 Tray |
| CLI | ✅ 存在，`jianying-agent-cli.exe draft <fetch-feishu-doc｜query-content｜plan-patch｜validate-patch｜apply-patch> --input <json文件> [--output <json文件>]` |
| hubcli 契约 | 47 条，`custom-agent.hub-cli.v1`；TTS 相关 4 条：`canvas.audio.add / setSubType / setTtsVoice / setSpeechRate`（effect=`write`） |

### 2.1 本轮新增关键发现：Host Runtime 本地服务

主程序启动后监听 3 个端口：

- `127.0.0.1:20066` → **HTTP 401 Unauthorized**，`Content-Type: application/json`、`Cache-Control: no-store`（GET `/`、`/health`、`/status` 均 401）
- `127.0.0.1:7264` → 无 HTTP 响应
- `192.168.204.1:25713` → 非回环地址，未探测

→ Host Runtime 服务**存在但需鉴权**。这是一个比 WB-VIDEO-002 更进一步的证据：token 很可能由该本地鉴权链路颁发，但**本轮没有、也不会伪造或提取 token**。

### 2.2 CLI 授权状态

即使主程序已启动，从外部进程调用：

```
jianying-agent-cli draft query-content --input {} --output <file>
=> {"code":"PERMISSION_DENIED","message":"JIANYING_AGENT_RUNTIME_TOKEN is required","ok":false, ...}
```

- 当前 shell 进程中无 `JIANYING_* / AGENT_RUNTIME_*` 环境变量（只查了变量名，未打印任何值）。
- `hubcli/cli.mjs` 明写「业务身份、授权和交付由 Host 持有」→ 外部直接启动的 CLI 拿不到合法注入的 token。
- 因此 `plan-patch / validate-patch / apply-patch` 以及素材导入、时间线、字幕、音轨、导出**全部未验证**。

### 2.3 用户工程完整性（前后 SHA-256 对比）

| 草稿 | 启动前 | 启动后 | 结论 |
|---|---|---|---|
| `11月7日/draft_content.json` | 4,928 B，`75E07786574BF6D9…`，2026-11-07 18:12:11 | 完全相同 | 未修改 |
| `yaodao_yaodao_ep/draft_content.json` | 29,205 B，`0792B2C4E809A6B6…`，2026-11-07 18:45:12 | 完全相同 | 未修改 |

两个 `draft_content.json` 格式仍不统一：一个是加密/base64 风格文本，一个是明文 JSON。**未把加密草稿当文本改、未伪造工程文件、未创建独立测试草稿**。

未创建独立测试草稿的原因：CLI 写路径被 token 门阻断；GUI 路径需要 UI Automation 控制桌面，而启动后的窗口并非「独立测试草稿」窗口，按 §4「不得操作其他窗口或账号设置」的限制，本轮选择不做 GUI 自动化，如实记录阻塞。

### 2.4 剪映能力分级

| 能力 | 接口存在 | 可调用 | 调用成功 | 实际导出有效视频 |
|---|:---:|:---:|:---:|:---:|
| 启动主程序 | — | — | ✅ | — |
| CLI `--help` / 5 个子命令 | ✅ | ✅ | ✅ | — |
| `query-content` | ✅ | ✅ | ❌ `PERMISSION_DENIED` | ❌ |
| `plan/apply-patch`、导入、时间线、字幕、音轨、导出 | ✅（契约） | ❌ 未授权 | ❌ | ❌ |
| UI Automation | 系统有 `UIAutomationClient.dll` | 未执行 | ❌ | ❌ |

---

## 3. 凭据与仓库安全

| 检查 | 结果 |
|---|---|
| 本轮是否读取 / 复制 / 打印 / 提交明文 PAT | **否**（一次都没有） |
| Git 历史（45 个提交）密钥扫描 | 0 命中（GitHub 经典 PAT 前缀 / 细粒度 PAT 前缀 / 私钥 / OpenAI 风格 key） |
| 工作区（99 个文本文件）扫描 | 0 命中（PAT / 私钥 / runtime token 值 / 本机绝对路径 / 用户名路径） |
| 被跟踪的 token/secret/credential 类文件名 | 无 |
| remote URL 是否内嵌凭据 | 否 |
| 是否已提醒轮换 | **是**：此前在对话中以明文出现过的 GitHub PAT 应尽快**撤销并轮换**；后续推送优先使用系统凭据管理器 / GCM 等受保护存储 |

本轮所有日志与证据均已脱敏：绝对路径用 `<LOCAL>` / `<PIPELINE>` / `<QA003>` / `%LOCALAPPDATA%` 占位。凭据存放文件位于仓库外，**未提交**。

---

## 4. TTS 与声音方案（只调查，零付费消费）

| 方案 | 本地运行 | 中文普通话 | 情绪/语速 | 免费额度 | 输出格式 | 剪映集成 | 本轮状态 |
|---|---|---|---|---|---|---|---|
| **Windows SAPI（System.Speech）** | ✅ | 4 个中文语音：Huihui Desktop、Huihui/Kangkang/Yaoyao OneCore；可懂但机械 | ❌ 情绪 / ✅ 语速（Rate） | ✅ 系统内置、无额度 | PCM WAV（FFmpeg 可转 AAC / MP3） | 需先生成 WAV 再导入 | **识别到，但未实际合成** |
| 剪映 hubcli TTS 契约 | ❌ 依赖 Host | 未知 | `setTtsVoice` / `setSpeechRate` 契约存在 | 未知，可能涉及会员/云端额度 | 未知 | 原生，但需 token | 契约只读，参数 schema 未验证 |
| edge-tts / pyttsx3 / gTTS / piper / ChatTTS / Kokoro / pywin32 / comtypes | — | — | — | — | — | — | **均未安装**，未联网、未下载模型、未核实价格，不宣称可用 |

**未实际合成的原因**（真实阻塞，非偷懒）：`Add-Type -AssemblyName System.Speech` 被执行环境安全策略拦截（`Add-Type compiles and loads .NET code at runtime`）；Python 侧 `win32com / comtypes / pythoncom` 均缺失。因此本轮**没有任何真实旁白音频产出**，也没有把占位音频标成正式旁白。

**优先级建议**：① 打通 SAPI（本地免费，需用户批准使用 .NET 语音程序集或安装 pywin32）；② 若要求更自然的中文与情绪，再评估有免费额度且无需绑定的在线服务并**先核实实际价格与条款**；③ 剪映内置 TTS 需先解决 Host 授权，且必须确认是否消耗会员/云端额度。

---

## 5. 环境结论

- **Vidova**：接口层可用，但 editor 写入被 GUI 窗口门挡住；真实生成因额度红线**未执行**；无导出能力。
- **剪映**：主程序能正常启动（本轮新验证），Host Runtime 本地鉴权服务存在，但 CLI 写路径仍被 Host token 门阻断；用户工程零改动；**没有任何真实导入 / 编辑 / 导出**。
- **两者之间**：仍无官方直连接口，只能靠文件系统 + manifest 衔接。
- **未产生任何付费消费、未删改任何用户工程或素材、未伪造任何接口或 token**。
