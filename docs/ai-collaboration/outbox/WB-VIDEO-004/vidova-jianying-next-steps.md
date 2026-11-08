# WB-VIDEO-004 · Vidova / 剪映链路的下一步（只读研究）

| 项 | 值 |
|---|---|
| 本轮性质 | **研究与方案**，不是打通；未打开任何 GUI 窗口、未导入素材、未消耗额度、未提取/伪造 token |
| 证据 | `evidence/vidova_window_research.json`、`evidence/vidova_deeplink_research.json`、`evidence/jianying_host_research.json` |
| 结论 | Vidova 窗口门**发现一条合法线索但未验证**；剪映**尚未找到合法自动化路径** |

---

## 1. Vidova：窗口门的合法解决方案研究

### 1.1 本轮重新确认的事实

| 项 | 实测 |
|---|---|
| MCP 服务 | `127.0.0.1:17373` 监听，`initialize` 200 |
| 工具 | **18 个**（`list_projects / get_active_project / create_project / set_active_project / timeline_get_state / timeline_edit / clip_enhance / asset / inspect_media / import_asset / preview / generate_asset / sfx / component / branch_action / project_history / recipe / sleep`） |
| `generate_asset` 调用 | **0 次**（额度红线） |
| 项目切换 / GUI 控制 / 素材导入 | **未执行** |
| 导出工具 | 18 个里**仍不存在** |

### 1.2 静态分析的新发现（本轮新增证据）

对 `%LOCALAPPDATA%/Programs/Vidova/resources/app.asar`（317,396,315 B）做只读分块扫描：

| 关键词 | 命中 | 解读 |
|---|---|---|
| `setAsDefaultProtocolClient` | 1 | 应用注册了自定义协议 |
| `vidova://` | 1 | **唯一实例是 `vidova://auth/callback`**（登录回调） |
| `second-instance` | 1 | 存在单实例 / 二次启动处理逻辑 |
| `open-project` | 4 | 托盘命令 schema 的一部分 |
| `appTrayCommand` | 4 | renderer 内部 IPC 通道 |
| `showMainWindow` | 2 | 托盘命令上下文含主窗口显示逻辑 |
| `OpenExternalProject` | 8 | 内部命令类型枚举，非外部 API |
| `openExternalProject` | 22 | 同上 |
| `openProjectId` | 2 | 字符串表中存在，但**未找到可调用的 URL 或 CLI 参数** |
| `projectId=` | 0 / `deeplink` 0 / `--open-project` 0 | **没有发现项目打开的 deep link 或命令行参数** |

Windows 注册表只读确认 `HKCU\Software\Classes\vidova` 存在，`shell\open\command` 形如 `<VIDOVA_EXE> "%1"`（**值已脱敏，只记录形状**），即协议会接收 URL 参数。

### 1.3 结论与边界

- **已确认**：MCP 的 18 个工具里**没有任何一个能打开编辑器窗口**（`any_mcp_tool_can_open_editor_window = false`）；`create_project` 成功也不会注册 GUI editor；`open-project` 是 `AppTrayCommandSchema` 的 renderer 内部托盘 IPC。
- **新线索**：注册了 `vidova://` 协议且有单实例处理，但包内**只找到 auth 回调 URL**，没有文档化/可确认的"打开项目" URL。因此这**只是下一阶段的调查线索，绝不能写成"窗口门已解决"**。
- **合法候选路径（按优先级）**：
  1. 真实 GUI 托盘菜单点击「打开项目」（人工或经授权的限定窗口 UI Automation）→ 让 editor 窗口注册 → 再调用 MCP `import_asset`（真实参数 `projectId` + `absolutePaths`）；
  2. 在**明确授权**前提下，验证 `vidova://` 是否支持项目类 URL（只做协议行为观察，不触发登录/账号操作、不传任何凭据）；
  3. 若以上都不行，接受架构约束：Vidova 只做素材生成/管理，编排与导出交给剪映或外部渲染器（B3 限制）。
- **明确不做**：修改 app.asar / 安装目录；伪造 IPC 调用；注入代码；读取或绕过账户凭据；未经授权控制桌面。

### 1.4 零额度可完成的测试清单（合法、可立即执行）

| # | 测试 | 预期证据 |
|---|---|---|
| 1 | `initialize` / `tools/list` | 工具清单 + inputSchema 原文 |
| 2 | `list_projects` / `get_active_project` | 项目列表与当前 active project（**不切换**） |
| 3 | `inspect_media` 指向本机已有本地文件 | 媒体元数据回执（只读） |
| 4 | 静态 asar 扫描 | 关键词命中与上下文（已做） |
| 5 | `create_project` 空测试项目 | WB-VIDEO-002 已验证零额度，本轮**不重复创建** |
| 6 | 额度相关只读检查 | app.asar 错误串（Free plan / lifetime allowance / upgrade），**账户余额仍 UNVERIFIED** |

> `generate_asset` 描述明确「Uses hosted quota… Image generation uses your image-generation allowance」；18 个工具无额度查询工具。任何生成调用必须先取得「1 次最小额度 + 明确余量上限」的批准。

---

## 2. 剪映：合法 Host 授权链路研究

### 2.1 本轮实测状态

| 项 | 实测 |
|---|---|
| 主程序 | **当前未运行**（与 WB-VIDEO-003 结束时不同，进程已退出） |
| 本地 runtime 端口 | `127.0.0.1:20066` **未监听**（本轮无法复现 401） |
| `JIANYING_AGENT_RUNTIME_TOKEN` | 当前 shell 环境**不存在**（只记录布尔值，未读取/打印任何值） |
| 任何 `JIANYING*` 环境变量 | 无 |
| CLI 文件 | `<JY_APP_DIR>/jianying-agent-cli.exe`、`jianying-agent-cli-tests.exe` 存在 |
| 外部直接调用 `--help` / `draft --help` | **退出码 `3221226505`（0xC0000409），stdout/stderr 均为空** —— 外部直接调用未得到帮助输出；与 WB-VIDEO-003 记录的「5 个 draft 子命令」不矛盾，后者来自另一路径，本轮如实记录差异 |
| hubcli 契约文件 | `Resources/agent_runtime_env/bin/hubcli`、`hubcli.cmd`、`cli/hubcli/` 存在 |
| 用户 2 个草稿 | `11月7日` sha256 前缀 `75e07786574bf6d9`、`yaodao_yaodao_ep` `0792b2c4e809a6b6`，**与 WB-VIDEO-003 完全一致，未被修改** |

### 2.2 新发现：Host 提供的运行时契约（只读，无密钥）

`hubcli` 启动脚本原文（已脱敏检查，**不含任何长密钥**）：

```
hubcli requires an absolute CUSTOM_AGENT_BUN_EXECUTABLE supplied by Host.
HUBCLI_ENTRY="$HUBCLI_BIN_DIR/../cli/hubcli/cli.mjs"
exec "$CUSTOM_AGENT_BUN_EXECUTABLE" "$HUBCLI_ENTRY" "$@"
```

即：**hubcli 依赖 Host 注入的绝对 Bun 可执行文件路径**，Windows 版 `.cmd` 同样强制校验该变量为绝对路径。这解释了为什么外部 shell 直接调用 CLI / hubcli 会失败：运行环境不是剪映 Host 启动的受控进程。

WB-VIDEO-003 已记录 47 条 `custom-agent.hub-cli.v1` 契约（含 `canvas.audio.add / setSubType / setTtsVoice / setSpeechRate` 等 write 类），以及 `query-content` 返回 `PERMISSION_DENIED: JIANYING_AGENT_RUNTIME_TOKEN is required`。本轮**没有**再调用任何写命令，也**没有**提取、伪造或绕过 token。

### 2.3 合法路径评估

| 路径 | 合法性 | 状态 |
|---|---|---|
| 由剪映 Host 正常启动 agent runtime，并在该受控进程内获得授权 | ✅ 合法 | **未打通**；需要官方/Host 提供的启动方式，本轮未发现公开文档 |
| 从外部 shell 设置 token 后调用 CLI | ❌ | token 由 Host 持有；不提取、不伪造、不绕过 |
| 逆向 `127.0.0.1:20066` 鉴权 | ❌ | 明确不做 |
| 修改加密草稿 / 伪造工程文件 | ❌ | 明确禁止（草稿格式不统一，含加密/base64 风格文本） |
| 在**独立空白测试草稿**中经授权的 GUI / UI Automation | ✅ 有条件合法 | 需用户批准；本轮**未创建草稿、未执行 UIA** |

→ **结论：剪映尚未找到合法的自动化路径。** 现有两个用户工程保持只读。

### 2.4 下一阶段可执行步骤（须先批准）

1. 批准「启动剪映 GUI + 创建独立空白测试草稿」后，先记录两个现有工程的 SHA-256（只读基线）；
2. 在独立草稿内导入**明确标记为测试素材**的本地文件，验证素材导入；
3. 依次验证时间线、字幕、音轨、导出，每步记录回执与文件路径；
4. 若 Host runtime 由官方方式启动，观察其合法授权链（不提取 token 值），确认 `query-content / apply-patch` 是否可用；
5. 全程不得触碰现有 2 个工程、不得覆盖草稿、不得删除缓存、不得公开发布、不得消耗会员/云额度。

---

## 3. 费用边界（本轮遵守）

| 项 | 本轮 |
|---|---|
| 购买 / 充值 / 自动续费 | **0** |
| `generate_asset` 调用 | **0** |
| 剪映可能的会员/云 TTS 调用 | **0** |
| 在线 TTS 服务调用 | **0** |
| 发现免费额度 | 仅见 app.asar 中 Free plan / lifetime allowance 字符串，**剩余额度 UNVERIFIED** |

若后续发现免费额度，仍须先确认：剩余额度、单次成本、收费条件、是否自动续费，再请示批准；**不自行试用可能收费的功能**。

---

## 4. 汇总回答

| 问题 | 回答 |
|---|---|
| Vidova 窗口门是否有合法解决方案？ | **有候选线索，未验证**。托盘 GUI / 限定 UIA 是最现实路径；`vidova://` 协议存在但只有 auth 回调，无项目打开证据；MCP 自身无法开窗口。 |
| 剪映是否找到合法自动化路径？ | **否**。Host 注入 `CUSTOM_AGENT_BUN_EXECUTABLE` 与 `JIANYING_AGENT_RUNTIME_TOKEN` 的受控运行环境是唯一合法方向，外部调用失败；GUI 独立草稿需批准。 |
| 本轮是否真实导入/编辑/导出？ | **否，0 次**。 |
| 是否修改了用户工程？ | **否**，两个草稿 SHA-256 前后完全一致。 |
| 是否消耗额度或付费？ | **否，0**。 |
