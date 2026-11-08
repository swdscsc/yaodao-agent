# WB-VIDEO-003 阶段报告 — 质检漏洞修复、真实工具链验证与制作准入准备

| 项 | 值 |
|---|---|
| Task ID | WB-VIDEO-003 |
| Status | `partial`（P0 修复完成；真实工具链仍有阻塞） |
| **最终结论** | **B · `CONDITIONAL PASS`** — 详见 §10 |
| Start / End | 2026-11-08 15:43 / 16:05 +0800（Asia/Shanghai, UTC+8） |
| 基准提交 | `08ffda5199cffccf762e810f139ab8bf1522fe2b`（远端 `main`，fetch 后与本地一致，工作区干净） |
| 分支 | `main` |
| 报告路径 | `docs/ai-collaboration/outbox/WB-VIDEO-003/report.md` |
| 交付目录 | `docs/ai-collaboration/outbox/WB-VIDEO-003/` |

---

## 0. 一句话结论

**两个 P0 质检漏洞已真实修复并有 17/17 自动化测试与修复前后对比证据；但 Vidova 真实生成、剪映真实导入/导出、真实旁白均未打通，因此不具备正式宣传片制作准入条件。** 本轮零付费额度消耗、零工程改动、零凭据提交。

---

## 1. 开工前状态核对（避免重复劳动）

- `git fetch` + `ls-remote origin refs/heads/main` → `08ffda5…`，本地 HEAD 相同，工作区干净。
- `inbox/` 仍只有 `WB-VIDEO-001-bootstrap-pipeline.md`；**无 WB-VIDEO-003 任务文件**（本轮任务书由用户在会话中下达，已按协议记录）。
- 已读：`README.md`、`WB-VIDEO-002-report.md`、`status/pipeline-status.json`、`WB-VIDEO-002/{core.py,qa.py,run_e2e.py,rework.py,shotlist.json}` 及 `evidence/*.json`。
- 因此本轮**不重复搭建框架**：复用已验证的 `core.py` 状态机/重试/manifest，只替换有缺陷的质检与判定逻辑，并把 WB-VIDEO-002 原文件完整保留为「修复前」证据。

## 2. 机器与软件版本

| 项 | 值 |
|---|---|
| OS | Windows 11 家庭中文版 10.0.22631.6199 |
| Python / Node | 3.13.14 / v22.22.2 |
| FFmpeg | 7.1-essentials（`freezedetect / freezeframes / blackdetect / silencedetect / volumedetect / subtitles / gblur / concat` 均可用） |
| ffprobe | 剪映内置 `1.0.0-401a53202a` |
| 图像库 | PIL 13.0.0 / cv2 5.0.0 / numpy 2.5.4 |
| Vidova | 1.0.66.0，`127.0.0.1:17373`，MCP 18 工具 |
| 剪映专业版 | 11.7.0.14652，`jianying-agent-cli.exe`，hubcli 47 契约 |
| git / 网络 | 2.55.0.windows.3；GitHub 需本机 `127.0.0.1:7897` 代理（按命令临时指定，未改全局配置） |

## 3. 实际测试过的工具 / 接口与执行动作（凭据已脱敏）

| 类别 | 实际动作 |
|---|---|
| GitHub | `fetch`、`ls-remote`、`git log --all` 历史密钥扫描、工作树 99 文件扫描 |
| Vidova MCP | `initialize`、`tools/list`（18 工具 + inputSchema）、`list_projects`、`get_active_project`、`set_active_project`、`timeline_get_state`、`asset list`、`import_asset`、`preview` |
| Vidova 静态 | 分块扫描 `app.asar`（317,396,315 B）定位 `AppTrayCommandSchema` / `open-project` / `AssetStoreImportPathsInputSchema` / 额度错误串；**未修改安装目录** |
| 剪映 | `Get-Process` / 端口 / `--help` / `draft --help` / `query-content --input <json文件> --output <json文件>` / 草稿 SHA-256 前后对比 / 启动主程序（§4 授权，PID 21424）/ 只读 GET 本地端口 |
| TTS | 注册表只读枚举 SAPI 语音、Python 包可用性检查、hubcli TTS 契约解析 |
| 本地测试 | FFmpeg 生成 4 段测试视频（`testsrc2 / color / freezeframes / sine`）+ PIL 生成 6 组字幕帧；`run_tests.py` 17 项；`rework.py` 严格重质检 + D004 重判 |

未执行：`generate_asset`（额度红线）、任何付费/充值、删除或覆盖用户文件、伪造 token 或工程文件、UI Automation 桌面控制、公开发布。

## 4. P0-1 修复结论：**已修复**

- **漏洞**：`WB-VIDEO-002/rework.py` 在最终成片上用 `qa_media(..., static_material_expected=True)` 关掉整条视频的冻结检测。
- **修复**：`WB-VIDEO-003/qa.py` 删除该参数（传入即 `ValueError`），改为 `static_intervals` 明确区间白名单；白名单经 fail-closed 校验（数值、顺序、reason、不重叠、不越界、覆盖率 ≤50%）；每个冻结区间单独判定，白名单外 → `FAIL` + 具体区间 + 原因 + `needs_manual_review`。`rework.py` 只白名单化 3 张已确认的静态卡片 `[0,1.5] / [4.5,5.5] / [10.5,12.0]`。
- **测试证据**（8/8 通过，`test-results.json` / `qa-fix-report.md` §1）：正常动态 PASS；中间冻结检出 `1.500–3.533 s` 且 FAIL；合法静态片头 `PASS_ALLOWED_STATIC`；片头之后动态冻结 FAIL；4 类白名单配置错误全部 fail-closed 且豁免次数 0；越界 `end=999` 报 `OUT_OF_RANGE`；旧参数被拒绝。
- **修复前后对比**（`evidence/before_after.json`）：同一文件，修复前 `EXPECTED_STATIC / PASS`，修复后 `FAIL` 并给出 `1.500–3.533 s`。
- **真实漏报被抓出**：用修复后 QA 重跑 WB-VIDEO-002 宣称「9 项全 PASS」的 v2 成片，横屏/竖屏均 **FAIL**，精确指出 **5.5–8.5 s（静态彩条素材 S002）白名单外冻结**；3 张静态卡片区间被正确放行。

## 5. P0-2 修复结论：**已修复**

- **漏洞**：`WB-VIDEO-002/rework.py` 用 `bool(v2.exists() and v2.stat().st_size > 0)` 把 D004 标 `FIXED`。
- **修复**：`WB-VIDEO-003/subtitle_checks.py` 增加 SRT 解析、越界、横/竖屏安全区、字号、对比度、主体/UI 重叠 IoU、与**无字幕参考帧**的烧录像素差证据、以及从像素差实测字幕带几何；`artifact_exists` 权重显式置 0。程序不可判定的 3 项一律 `NEEDS_MANUAL_REVIEW`；`FIXED` 需自动无 FAIL + 具名人工 `APPROVED` + 证据 + 烧录像素通过；自动与人工证据分字段存储。
- **测试证据**（9/9 通过）：正常字幕自动 PASS 但无签核仍 `NEEDS_MANUAL_REVIEW`；具名签核后才 `FIXED`；越界、贴底边、与主体重叠、竖屏中部、SRT 存在但画面无字幕、文件存在不等于 FIXED、自动/人工分离 —— 全部按预期判定。
- **历史 D004 重判**（`evidence/d004_reassessment.json`）：用真实关键帧与无字幕参考帧像素差定位字幕带 —— 竖屏 `[62,1179,950,26]` 中心 **0.6208 H（画面中部）**、字号 26 px < 32 px；横屏底边 0.947 H 略超 0.94 安全线。旧 `FIXED` → **新 `STILL_FAILING`**，3 项人工复核 `NOT_PERFORMED`。**证明旧判定是虚假的。**

## 6. 逐项回答任务书 §10 的十个问题

| 问题 | 回答 |
|---|---|
| P0-1 是否修复？证据？ | **是**。`qa.py` 删除全片豁免、改为区间白名单；8/8 测试通过；修复前后同文件 `EXPECTED_STATIC/PASS` → `FAIL(1.500–3.533s)`；历史成片重判由 PASS 变 FAIL 并定位 5.5–8.5 s 漏报。 |
| P0-2 是否修复？证据？ | **是**。`subtitle_checks.py` + `rework.py` 禁止文件存在判定；9/9 测试通过；历史 D004 用真实帧像素证据由虚假 `FIXED` 重判为 `STILL_FAILING`。 |
| Vidova 当前是否可用？验证到哪一步？ | **接口层可用，编辑/生成链路不可用**。版本/进程/端口/MCP 握手/18 工具/项目切换/只读工具全部实测成功；`import_asset / timeline_edit / preview` 被 GUI 窗口门阻断（对照组证明切回 GUI 已打开项目即恢复）；`generate_asset` 因额度红线 0 调用；无导出工具。详 `environment-audit.md` §1。 |
| 剪映当前是否可用？验证到哪一步？ | **主程序可启动（本轮新验证），原生编辑不可用**。启动后主窗口 `JianyingPro`、本地 `127.0.0.1:20066` 服务存在但返回 401；CLI 5 个子命令存在，但 `query-content` 仍 `PERMISSION_DENIED: JIANYING_AGENT_RUNTIME_TOKEN is required`；用户 2 个草稿 SHA-256 前后完全一致。详 §2。 |
| 是否完成真实素材生成？ | **否**。0 次 `generate_asset`，0 额度消耗；本轮所有媒体都是 FFmpeg 合成测试信号，明确不冒充真实素材。 |
| 是否完成真实剪映导入和导出？ | **否**。未创建独立测试草稿，未导入、未编辑、未导出；CLI 写路径被 token 门阻断，UI Automation 未获授权执行。 |
| 是否完成真实旁白？ | **否**。仅调查：注册表确认 4 个中文 SAPI 语音、剪映 4 条 TTS 契约；`Add-Type System.Speech` 被环境安全策略拦截，Python TTS 包全缺失，**本轮未合成任何音频**，未把占位音频标成旁白。 |
| 当前还有哪些阻塞？ | 10 项，见 `blockers.md`：Vidova GUI 窗口门 / 额度 / 无导出、剪映 Host token / 独立草稿 / TTS / UIA、竖屏非原生重排、PAT 轮换、空测试项目残留；另有 D004 重判与新增 D005 两条未修复缺陷。 |
| 下一阶段还需用户批准什么？ | 7 项集中清单（`blockers.md` §5）：1 次最小额度生成 + 余量上限、剪映 GUI 独立草稿操作、限定窗口 UI Automation、本地 TTS 依赖、清理空测试项目、撤销轮换 PAT、是否进入第 3 轮返工。 |
| 当前是否达到正式宣传片制作准入标准？ | **否**。见 §10 结论 B。 |

## 7. 交付清单（相对路径）

| 路径 | 内容 |
|---|---|
| `report.md` | 本报告（唯一主报告） |
| `environment-audit.md` | Vidova / 剪映 / 凭据 / TTS 环境审计 |
| `qa-fix-report.md` | 两个 P0 漏洞修复记录与前后对比 |
| `test-results.json` | 17 项自动化测试完整结果（含每项的期望/实际/证据） |
| `e2e-plan.md` | 15–20 s 最小真实 E2E 方案与逐环节状态 |
| `blockers.md` | 未解决问题、缺陷台账、审批清单 |
| `qa.py` / `subtitle_checks.py` / `rework.py` / `run_tests.py` | 修复后源码与测试源码 |
| `evidence/before_after.json` | P0-1 / P0-2 修复前后对比 |
| `evidence/freeze_intervals.json` | 具体冻结区间与判定原因 |
| `evidence/d004_reassessment.json` | 历史成片严格重质检 + D004 重判 |
| `evidence/environment_probe.json` | 脱敏环境审计原始数据 |
| `evidence/shot_manifest.json` | 12 字段镜头登记表（计划态，`asset_path=null`） |
| `evidence/subtitle_contact_sheet.jpg` | 6 格字幕测试帧视觉证据 |
| `status/pipeline-status.json` | 更新后的机器可读流水线状态 |

大媒体（测试 MP4、成片、全部中间帧）只存本机 `pipeline/` 与 `pipeline/qa003/`，**未提交**；本机绝对路径只存仓库外 `config.local.json`。

## 8. 验证与合规检查

| 检查 | 结果 |
|---|---|
| 全部自动化测试 | **17 / 17 PASS**，退出码 0（`test-results.json.summary`） |
| Python 编译 | `qa.py / subtitle_checks.py / rework.py / run_tests.py` 全部通过 |
| JSON 校验 | 交付目录内全部 JSON 解析通过 |
| Git 历史密钥扫描 | 45 个提交，0 命中 |
| 工作区敏感扫描 | 99 个文本文件，0 命中（PAT / 私钥 / runtime token 值 / 绝对路径 / 用户名路径） |
| 本轮明文 PAT 读取/打印/提交 | **0 次** |
| 用户原有工程 | 2 个剪映草稿 `draft_content.json` 前后 SHA-256 完全一致；Vidova 原 active project 已恢复并验证；空测试项目保留未删 |
| 付费 / 额度 | `generate_asset` 0 次、TTS 0 次、无购买、无充值 |
| 证据可验证性 | `evidence/manifest.sha256.json` 列出所有证据文件的 SHA-256 |

## 9. 已知问题与未验证假设

- 修复后的 QA 把 WB-VIDEO-002 的 v2 成片判为 FAIL（含新增 D005 冻结缺陷与 D004 字幕缺陷）；**本轮没有修复这些成片本身**，只修复判定逻辑并如实重判。
- 返工已 2/2 轮，`third_cycle_allowed=false`，第 3 轮硬停在 `REVIEW_REQUIRED`。
- OCR 文字内容比对、语义可读性、未声明主体遮挡：程序未验证，全部 `NEEDS_MANUAL_REVIEW`。
- `font_px` 在历史重判中取自渲染参数 `FontSize=26/30`，非帧内测量。
- `import_asset` 的 `absolutePaths` 契约来自 `app.asar` 静态 zod schema，**未实调成功**（窗口门）。
- 剪映 `127.0.0.1:20066` 服务的鉴权机制未逆向、未绕过；token 未提取、未伪造。
- 免费额度剩余量、自动续费风险：UNVERIFIED。
- 语义一致性 / 人物物体畸形 AI 视觉检查：本轮无真实素材，不适用，未宣称完成。
- 此前对话中明文出现的 GitHub PAT 仍可能有效，**建议用户撤销并轮换**。

## 10. 最终结论：**B · CONDITIONAL PASS**

| 判定 | 依据 |
|---|---|
| 为什么不是 A `PASS` | 关键真实链路无证据：Vidova 真实生成 0 次、剪映真实导入/导出 0 次、真实旁白 0 段、独立剪映草稿 0 个。 |
| 为什么不是 C `FAIL` | 两个 P0 关键质检问题**确已修复**，17/17 自动化测试通过，且有修复前后对比、具体冻结区间、真实帧像素证据与可复算的 SHA-256 清单；不属于「关键质检问题仍存在」。 |
| 为什么是 B | 符合定义「质检修复通过，但部分真实工具链仍有阻塞，只允许继续已验证的环节」。 |

**准入含义**：
- ✅ 允许继续：已验证的本地质检、manifest、状态机、有界返工、参考渲染（仅作占位）、只读环境调查、本次新增的自动字幕检查与冻结白名单机制。
- ❌ 不允许：进入正式宣传片制作；不允把 FFmpeg 参考渲染当作剪映成片交付；不允把合成图案当作 AI 素材；不允把文本/占位音频当作配音完成；不允把未验证的导出标成质量合格。
- 下一阶段必须先解决 B1/B2/B4/B6 并取得 §5 的批准，再按 `e2e-plan.md` 逐环节补齐真实证据。

**本轮到此停止，等待 ChatGPT 审核 WB-VIDEO-003 的报告与证据，再决定下一阶段工作。**

---

## 11. 提交与 GitHub 链接

| 项 | 值 |
|---|---|
| 仓库 / 分支 | `swdscsc/yaodao-agent` / `main` |
| 基准提交 | `08ffda5199cffccf762e810f139ab8bf1522fe2b` |
| 主体交付 commit SHA | 见推送完成后的补记（`status/pipeline-status.json` 与会话回报） |
| 报告 | https://github.com/swdscsc/yaodao-agent/blob/main/docs/ai-collaboration/outbox/WB-VIDEO-003/report.md |
| 交付目录 | https://github.com/swdscsc/yaodao-agent/tree/main/docs/ai-collaboration/outbox/WB-VIDEO-003 |
| 证据目录 | https://github.com/swdscsc/yaodao-agent/tree/main/docs/ai-collaboration/outbox/WB-VIDEO-003/evidence |
| 状态文件 | https://github.com/swdscsc/yaodao-agent/blob/main/docs/ai-collaboration/status/pipeline-status.json |
| 推送方式 | 优先使用系统凭据管理器（GCM / wincred）等受保护存储；不读取、不打印、不提交明文 PAT；无 force-push |
