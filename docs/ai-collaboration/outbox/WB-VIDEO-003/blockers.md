# WB-VIDEO-003 · 未解决问题与下一步建议

## 1. P0 缺陷台账（本轮修复结果）

| 编号 | 描述 | 严重等级 | 责任模块 | 修复方案 | 修复结果 | 证据 |
|---|---|---|---|---|---|---|
| P0-1 | `static_material_expected=True` 全片豁免冻结检测，动态镜头冻结会误判 PASS | 高 | `qa.py` / `rework.py` | 删除全局豁免；改为经校验的明确时间区间白名单；逐区间判定；fail-closed | ✅ **FIXED**（8/8 测试通过） | `qa-fix-report.md` §1、`test-results.json` |
| P0-2 | D004 用「文件存在且非空」判定字幕修复完成 | 高 | `rework.py` / 字幕检查 | 新增 `subtitle_checks.py`：几何/安全区/字号/对比度/遮挡/烧录像素证据；人工项 `NEEDS_MANUAL_REVIEW`；FIXED 需自动证据 + 具名签核 | ✅ **FIXED**（9/9 测试通过） | `qa-fix-report.md` §2、`evidence/d004_reassessment.json` |

## 2. 由修复暴露出来的、尚未修复的真实缺陷

| 编号 | 时间码 / 位置 | 描述 | 严重等级 | 责任模块 | 修复方案（建议） | 修复结果 |
|---|---|---|---|---|---|---|
| D005（新） | 横屏/竖屏 v2 的 **5.5–8.5 s** | S002 静态彩条素材造成 3 s 冻结，旧质检漏报 | 中 | 素材 / Vidova | 换用真实动态素材；或在 manifest 中明确标为静态卡片并加入白名单（当前按素材处理，不豁免） | **OPEN**，停在 `REVIEW_REQUIRED` |
| D004（重判） | 竖屏字幕带 `[62,1179,950,26]`，中心 0.6208 H | 竖屏字幕仍在画面中部，字号 26 px < 32 px 下限；横屏字幕底边 0.947 H 略超 0.94 安全线 | 中 | 字幕模块 | 竖屏原生重排 + 字号 ≥32 px + 底部安全区重烧；重跑 P0-2 检查器 + 人工签核 | **STILL_FAILING**（原为虚假 `FIXED`） |
| D003 | 跨素材重复镜头 | WB-VIDEO-002 已修（`S003-A03`），本轮未复现 | — | Vidova | — | 保持 FIXED（历史） |

> 返工上限：**2/2 轮已用尽**，`third_cycle_allowed=false`，第 3 轮硬性停在 `REVIEW_REQUIRED`（`evidence/d004_reassessment.json` → `bounded_gate`）。本轮不自动修复 D004/D005。

## 3. 未打通的技术阻塞

| # | 阻塞 | 实际验证到哪一步 | 影响 | 建议下一步 | 状态 |
|---|---|---|---|---|---|
| B1 | **Vidova editor GUI 窗口门** | MCP 握手、18 工具、项目切换全部成功；新建/未打开项目上 `import_asset / timeline_edit / preview / asset list` 全部返回 `No open Vidova editor window is registered`；切回 GUI 已打开的原项目立即成功 | 无法用 MCP 导入素材或编排时间线 | 用 asar 中已确认的 `AppTrayCommandSchema` → `open-project` 托盘命令，经 GUI/UIA 打开项目窗口；然后用真实参数 `absolutePaths` 重跑 `import_asset` | **OPEN** |
| B2 | **Vidova 托管额度** | `generate_asset` 描述明确消耗 hosted quota；app.asar 发现 Free plan / lifetime allowance / 升级提示；18 个工具中无额度查询工具；剩余额度 UNVERIFIED | 无法生成任何真实 AI 素材 | 需用户批准「1 次最小额度 + 明确余量上限」；本轮 0 次调用 | **STOP（等审批）** |
| B3 | **Vidova 无导出/渲染工具** | 18 个工具中确认不存在 | 成片必须走剪映或外部渲染器 | 接受架构约束，用文件系统 + manifest 衔接 | **架构限制，非故障** |
| B4 | **剪映 CLI Host token 门** | 主程序已成功启动；本地 `127.0.0.1:20066` 服务返回 401；从外部调用 `query-content` 仍 `PERMISSION_DENIED: JIANYING_AGENT_RUNTIME_TOKEN is required` | 无法用原生 CLI 导入/编辑/导出 | 研究 Host 合法授权链路（只读，不伪造 token），或经授权做有限 UI Automation | **OPEN** |
| B5 | **剪映独立测试草稿未创建** | 未创建（CLI 写路径被 B4 阻断；GUI 窗口非独立草稿，按 §4 不操作其他窗口） | 无法验证导入/时间线/字幕/音轨/导出 | 先解 B4，再在独立草稿中验证 | **NOT_STARTED** |
| B6 | **真实 TTS 未打通** | 注册表确认 4 个中文 SAPI 语音；`Add-Type -AssemblyName System.Speech` 被环境安全策略拦截；Python 侧 pywin32/comtypes 及所有 TTS 包均缺失 | 无真实旁白音轨 | 批准使用 .NET 语音程序集或安装 pywin32；或核实其他免费方案价格后再定 | **OPEN** |
| B7 | **UI Automation 未执行** | 只确认系统存在 `UIAutomationClient.dll`；未枚举控件树、未点击 | Vidova/剪映 GUI 路径未验证 | 需用户授权「明确限定窗口内的桌面控制」 | **NOT_ATTEMPTED** |
| B8 | **竖屏非原生重排** | 模糊背景填充 + 字幕偏中部（D004 重判确认） | 竖屏交付质量不合格 | 见 D004 修复方案 | **OPEN（人工门内）** |
| B9 | **PAT 安全** | 45 个提交历史 + 99 个文件扫描 0 命中；本轮未读取/打印/提交明文 PAT | 曾以明文出现在对话中的 PAT 仍可能有效 | **用户应撤销并轮换**，后续用系统凭据管理器 | **待用户操作** |
| B10 | **空测试项目残留** | `893d1af1-…` 仍为空、无素材；MCP 无删除工具 | 轻微 | 任务书禁止擅自清理；需用户批准后处理 | **保留** |

## 4. 本轮明确「未验证」的事项（不得推测为通过）

- 真实 AI 素材生成、真实 jobId 轮询、生成结果落盘路径与 ffprobe 校验。
- `import_asset` 的 `absolutePaths` 参数契约**只从 asar 静态 schema 得到，未实调成功**。
- 剪映素材导入、时间线编辑、字幕、音轨、导出，以及任何 `apply-patch` 回执。
- 剪映 UI Automation 控件树与可操作性。
- 本地 TTS 的实际中文音质、情绪控制、与剪映的集成。
- 免费额度剩余量、自动续费/收费风险。
- 字幕文字内容是否与 SRT 一致（需 OCR/人工）、语义可读性、未声明主体遮挡 —— 全部 `NEEDS_MANUAL_REVIEW`。
- 语义一致性 / 人物物体畸形 AI 视觉检查（本轮无真实素材，不适用）。

## 5. 下一阶段所需用户批准（集中清单，不逐条打断）

| # | 事项 | 类别 |
|---|---|---|
| 1 | 允许 **1 次最小额度** `generate_asset` 测试，并给出明确的额度余量上限；确认不购买、不开通自动续费 | 付费 / 额度 |
| 2 | 允许**启动并操作剪映 GUI**，在独立空白测试草稿中完成导入/编辑/导出（现有 2 个工程只读） | 应用操作 |
| 3 | 允许在**明确限定的窗口内**使用 UI Automation（含 Vidova 托盘 `open-project` 与剪映测试草稿），不触碰其他窗口或账号设置 | 桌面控制 |
| 4 | 允许使用本地 .NET SAPI 或安装 `pywin32` 以生成中文旁白（本地免费，需先确认无付费依赖） | 本地依赖 |
| 5 | 是否清理空 Vidova 测试项目 `893d1af1-…`（本轮已保留） | 删除 |
| 6 | 撤销并轮换此前明文出现的 GitHub PAT；后续统一使用系统凭据管理器 | 凭据 |
| 7 | 竖屏 D004 残余缺陷是否进入第 3 轮返工（当前被有界策略硬停止在 `REVIEW_REQUIRED`） | 人工审核节点 |

## 6. 建议的下一任务书（WB-VIDEO-004）

- **Goal**：解除 B1 / B2 / B4 / B6，跑通 `e2e-plan.md` 的 13 环节最小真实链路。
- **Scope**：1 个真实素材 + 1 个独立剪映草稿 + 1 次真实导出；不制作正式宣传片。
- **Inputs**：本目录全部文件、`WB-VIDEO-002/`、`status/pipeline-status.json`、本机 `pipeline/`（仓库外）。
- **Acceptance criteria**：见 `e2e-plan.md` §5。
- **Safety limits**：不购买额度、不删改现有工程与素材、不公开发布、不上传隐私、不提交任何凭据。
- **Expected report**：`docs/ai-collaboration/outbox/WB-VIDEO-004-report.md`。
