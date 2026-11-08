# WB-VIDEO-004 阶段报告 — 质检签核补强、AI 产品广告导演研究与免费真实剪辑链路准备

| 项 | 值 |
|---|---|
| Task ID | WB-VIDEO-004 |
| Status | `partial`（P0 修复与规范完成；真实工具链仍有阻塞） |
| **最终结论** | **B · `CONDITIONAL PASS`** — 详见 §11 |
| Start / End | 2026-11-08 16:30 / 17:06 +0800（Asia/Shanghai, UTC+8） |
| 基准提交 | `addca7883c59f8aeb490376d71478095799e5d97`（远端 `main`，fetch 后与本地一致，工作区干净） |
| 报告路径 | `docs/ai-collaboration/outbox/WB-VIDEO-004/report.md` |
| 交付目录 | `docs/ai-collaboration/outbox/WB-VIDEO-004/` |

---

## 0. 一句话结论

**字幕人工签核已改为逐项独立审核并有 26/26 自动化测试与修复前后对比；17 个 GitHub 项目做了真实只读代码/许可证检查；六角色广告导演工作流、产品广告剪辑规范与推荐架构已成文；但中文 TTS 仍 0 段语音 WAV、Vidova 窗口门与剪映 Host 授权仍只有研究线索、没有任何真实素材生成/剪映导入导出。因此不具备进入正式宣传片制作的条件。本轮 0 付费、0 额度消耗、0 依赖安装、0 工程改动。**

---

## 1. 开工前状态核对（避免重复劳动）

- `git fetch` + `ls-remote origin refs/heads/main` → `addca788…`，本地 HEAD 相同，工作区干净。
- `inbox/` 仍只有 `WB-VIDEO-001-bootstrap-pipeline.md`；本轮任务书由会话下达（按协议记录）。
- 已读：`README.md`、`WB-VIDEO-003/subtitle_checks.py`、`run_tests.py`、`report.md`、`environment-audit.md`、`status/pipeline-status.json`（schema 1.2）。
- **不重复**：不重建框架、不重跑 WB-VIDEO-003 的 17 项测试、不重新生成额度/工程证据；只在本目录新增修复、研究与规范，WB-VIDEO-003 文件完整保留为修复前基线。

## 2. 机器与软件版本

| 项 | 值 |
|---|---|
| OS | Windows 11 家庭中文版 10.0.22631.6199（Intel 核显，无独立 NVIDIA GPU） |
| Python / Node | 3.13.14 / v22.22.2 |
| FFmpeg / ffprobe | 7.1-essentials / 剪映内置 1.0.0-401a53202a |
| 图像库 | PIL 13.0.0 / cv2 5.0.0 / numpy 2.5.4 |
| Vidova | 1.0.66.0，`127.0.0.1:17373`，MCP 18 工具（本轮重新握手确认） |
| 剪映专业版 | 11.7.0.14652，`jianying-agent-cli.exe` + hubcli 契约 |
| 网络 / 凭据 | GitHub 需本机代理；推送使用系统凭据管理器（未读取/打印明文 PAT） |
| 已装 TTS 相关 | **无**（whisper / torch / edge_tts / TTS / pyttsx3 / win32com / comtypes 全部缺失） |

## 3. 实际执行过的动作（凭据已脱敏）

| 类别 | 实际动作 |
|---|---|
| GitHub | `fetch` / `ls-remote` / `git log` / 新增文件 diff 检查；17 个第三方仓库的 HTML、commits Atom、README、LICENSE、依赖文件、入口源码 **真实 GET**（逐 URL 记录状态、bytes、SHA-256） |
| P0 修复 | 新建 `subtitle_checks.py`（逐项签核 + 字号三态 + 文字对比度 + 多指标遮挡）、`run_signoff_tests.py`；PIL 本地生成测试帧与 SRT；运行 26 项测试 |
| 环境只读 | Vidova MCP `initialize` / `tools/list`；端口探测；`app.asar` 317 MB 分块静态扫描；注册表 URL scheme 只读；剪映 CLI 帮助、hubcli 启动脚本、环境变量**布尔存在性**、草稿 SHA-256 前后对比 |
| TTS | 注册表语音 token 只读；三条合法调用路径尝试（均被安全策略拒绝，未绕过）；FFmpeg 生成 440 Hz 合成测试音 WAV + `ffprobe` / `volumedetect` / `silencedetect` 验证音频 QA 链路 |
| 文档 | 11 份规定交付文档 + 源码 + 测试 + 证据；`pipeline-status.json` 升级到 schema 1.3 |

**未执行**：`generate_asset`（0 次）、任何付费/充值、剪映 GUI/草稿/导入/导出、UI Automation、任何 `pip install` 或模型下载、删除或覆盖用户文件、公开发布、token 提取/伪造、安全策略绕过。

## 4. P0：字幕人工签核逐项审核（已完成）

- **缺陷**：WB-VIDEO-003 第 319–320 行只要一个顶层 `APPROVED` 对象即视为签核，三个 `MANUAL_ITEMS` 从未逐项检查。
- **修复**：每项独立 `reviewer / reviewed_at / item_id / verdict / evidence / notes` + 强制绑定 `frame_ref / time_range / video_version / subtitle_version`；拒绝空值、占位证据、未来时间、错误版本/帧/时间段、重复记录、模拟审核人；自动与人工两个独立结构；`FIXED` 需 7 个先决条件全满足；生产台账二次校验。
- **额外三项改进**：字号区分渲染参数 / 帧内实测 / 人工确认（渲染参数权重 0）；对比度改为文字掩膜 vs 邻近背景环的真实测量（旧整带分布降级为诊断字段）；遮挡改为 IoU + intersection/subject + intersection/subtitle 多指标。
- **证据**：`subtitle-signoff-tests.json` **26/26 PASS**；`evidence/signoff_before_after.json` 同一输入旧门 `signed_off=true`、新门 0/3 项通过；`evidence/signoff_sample_contact_sheet.jpg` 三格测试帧；`subtitle-signoff-fix.md` 含全部实测数值（低对比样例 band spread 145 但文字对比 ratio 1.177 → FAIL；小遮挡 IoU 0.0025 旧逻辑 PASS、新 `intersection/subject=1.0` → FAIL）。
- D004 仍 `STILL_FAILING`，本轮**未伪造任何人工审核**，未批准第 3 轮返工。

## 5. 核心研究结论摘要

| 主题 | 结论 |
|---|---|
| GitHub 项目 | 17 个真实仓库，覆盖 10 方向；许可证按**原文**核对并纠正 6 处自动识别错误（edge-tts 实为 LGPL-3.0 为主、vmaf 为 BSD-2-Clause-Patent、MCP servers 处于 MIT→Apache 过渡、anthropics/skills 根目录无 LICENSE、Aegisub 为 BSD-3-Clause 混合、ShortGPT 默认分支是 master）。**未安装/未运行任何项目** |
| Skill | **安装 0 个**。`anthropics/skills` 许可未确认 → 不复制代码，只提取 6 条工作方法并转成项目内部规范；MCP servers 参考其只读/写白名单设计 |
| 免费本地工具 | 适合 Intel 核显/CPU：已具备 FFmpeg + cv2/numpy/PIL；待批准候选 `faster-whisper`（CPU ASR）、`PySceneDetect`（纯 CPU 镜头切分）、`MeloTTS`（CPU 中文 TTS）。明确排除需独显的 ComfyUI 与需联网在线服务的 edge-tts |
| TTS | 中文 SAPI 语音存在，但 `Add-Type`、COM 实例化、脚本宿主三条路径全被工具安全策略拦截；**未绕过**；0 段中文语音 WAV。产出的 WAV 是明确标注的 440 Hz 合成测试音（2.5 s / 48 kHz / 单声道 / mean -33.1 dB / 0 长静音），只证明音频 QA 链路可用 |
| Vidova | 18 工具实测；无任何 MCP 工具能打开编辑器窗口；新发现注册了 `vidova://` 协议、单实例处理与 `showMainWindow`，但包内唯一 URL 是 `vidova://auth/callback`，**没有项目打开 URL 的证据** → 只是线索，不是解决方案 |
| 剪映 | 主程序当前未运行、20066 未监听；外部直接调用 CLI `--help` 退出码 `3221226505`；hubcli 启动脚本明确要求 Host 注入 `CUSTOM_AGENT_BUN_EXECUTABLE`；token 环境变量在当前 shell 不存在。**未找到合法自动化路径**；两个现有草稿 SHA-256 与上一轮完全一致 |

## 6. 已形成的规范资产

- `ad-director-workflow.md`：六角色（产品研究员 / 创意导演 / 分镜导演 / AI 视觉导演 / 自动剪辑师 / 质量总监）+ **22 字段分镜 schema**（任务书 19 项 + 3 个治理字段）+ 产品真实性三态 + 6 套可复用提示词模板 + 质量否决权。
- `product-ad-editing-guide.md`：《AI 产品广告剪辑规范》v1，覆盖开场 3 秒、产品展示、情景演绎、J/L-cut 等 10 类节奏技法逐项判定"药到适不适合"、画面包装、独立 9:16 布局、15–20 s 示范节奏表、规范→质检映射。
- `recommended-architecture.md`：L0–L9 分层、5 类数据契约、能力四级分级、权限三级、证据治理、现状矩阵、ADR 7 条。

---

## 7. 逐项回答任务书 §11 的十三个问题

| # | 问题 | 回答 |
|---|---|---|
| 1 | 字幕人工签核是否真正做到逐项审核？ | **是**。三个 `MANUAL_ITEMS` 各有独立状态、证据、具名审核人、时间，并绑定帧/时间段/视频版本/字幕版本；任一缺失即不能 `FIXED`。见 `subtitle-signoff-fix.md` §2–§3。 |
| 2 | 测试是否覆盖伪造签核和不完整签核？ | **是，26/26 通过**。含旧全局 APPROVED 对象、空审核人、空证据、模拟审核人冒充生产、只有一项通过、一项未审核、错误视频/字幕版本、错误帧/时间段、重复记录、自动 FAIL + 人工 APPROVED、自动 PASS + 人工未审核。 |
| 3 | 找到了哪些有价值的 GitHub 项目和 Skills？ | 17 个真实项目（详见 `github-project-research.md`）：高价值方法来源为 `faster-whisper`、`PySceneDetect`、`whisperX`、`MeloTTS`、`ffmpeg-python`、`Netflix/vmaf`、`modelcontextprotocol/servers`；工作流参考 `MoneyPrinterTurbo`；`anthropics/skills` 提供 Skill 结构方法但许可未确认。 |
| 4 | 哪些 Skill 真正值得集成？ | **代码层面：0 个**。理由是 `anthropics/skills` 无 LICENSE、MCP servers 许可过渡、多数项目依赖付费 API 或 GPU。真正值得"集成"的是**工作方法**：文件夹式规范、YAML 元数据、渐进加载、指令/脚本分离、只读与写白名单、可验证输出 —— 已转成项目内部 6 条规则与模板（`skill-research.md` §3）。 |
| 5 | 是否形成广告导演工作流？ | **是**（规范文档）。六角色职责、交接门槛、22 字段分镜、真实性红线、提示词模板、质量否决权齐备。**但尚未执行任何真实广告制作**，属于设计产物。 |
| 6 | 是否形成产品广告剪辑规范？ | **是**（`product-ad-editing-guide.md`）。含开场/展示/情景/节奏/包装/横竖屏六部分与示范节奏表；每条规范映射到自动可检项或人工项。同样是规范，不是已完成成片。 |
| 7 | 是否找到了适合当前 Intel 核显电脑的免费工具？ | **找到了候选，但未安装验证**。已具备 FFmpeg 7.1 + cv2/numpy/PIL 并实测；CPU 友好候选 `faster-whisper`（MIT）、`PySceneDetect`（BSD-3-Clause）、`MeloTTS`（MIT）均通过静态依赖/许可证检查；需批准后试装。明确排除 ComfyUI（需独显）与 edge-tts（在线服务 + LGPL）。 |
| 8 | 本地 TTS 是否真正生成了 WAV？ | **生成了 WAV，但不是中文语音**。真实产出是 440 Hz 合成测试音（240,078 B，SHA-256 `a2400386…`），用于验证音频 QA 链路；`chinese_tts_wav_generated = false`、`tts_status = NOT_COMPLETE`。三条合法 SAPI 路径均被安全策略拦截，未绕过；需批准安装依赖后才可能产出中文语音。 |
| 9 | Vidova 窗口门是否有合法解决方案？ | **有候选线索，未验证**。托盘 GUI/限定 UIA 是最现实路径；本轮新发现 `vidova://` 协议与 `showMainWindow`/`second-instance`，但包内只有 auth 回调 URL，无项目打开 URL；MCP 无开窗口工具。**不得写成"已解决"**。 |
| 10 | 剪映是否找到合法的自动化路径？ | **否**。Host 注入 `CUSTOM_AGENT_BUN_EXECUTABLE` 与 `JIANYING_AGENT_RUNTIME_TOKEN` 的受控环境是唯一合法方向；外部调用失败，token 未提取/伪造；GUI 独立草稿需批准。 |
| 11 | 哪些功能已经实际测试？ | ① 26 项字幕签核/字号/对比度/遮挡测试（本地 PIL+FFmpeg，真实运行）；② Vidova MCP 握手/18 工具/端口；③ asar 与注册表静态扫描；④ 剪映 CLI/环境变量/草稿 SHA；⑤ 17 仓库 raw/Atom/HTML 真实 GET；⑥ FFmpeg 音频 QA 链路；⑦ 用户工程 SHA-256 前后一致。 |
| 12 | 哪些仍然只是研究方案？ | 六角色工作流、剪辑规范、推荐架构、22 字段分镜、15–20 s 示范节奏表、D004 竖屏重排方案、TTS 安装后验证流程、Vidova deep link 验证、剪映 Host 授权与独立草稿流程、所有第三方项目的"可运行"判断。 |
| 13 | 下一阶段需要用户批准什么？ | 9 项集中清单（`blockers.md` §5）：1 次最小额度生成 + 余量上限、剪映 GUI 独立草稿、限定窗口 UIA、本地 TTS 依赖、faster-whisper/PySceneDetect 试装与模型下载、`vidova://` 行为观察、清理空测试项目、撤销轮换 PAT、D004 是否进第 3 轮返工。 |

---

## 8. 交付清单（相对 `outbox/WB-VIDEO-004/`）

| 文件 | 内容 |
|---|---|
| `report.md` | 本主报告 |
| `subtitle-signoff-fix.md` | P0 修复、数据结构、决策规则、三项额外改进、前后对比 |
| `subtitle-signoff-tests.json` | 26 项测试完整结果（期望/实际/证据） |
| `skill-research.md` | Skill 机制、候选 12 字段评估、零安装结论、内部规则 |
| `github-project-research.md` | 17 仓库真实检查、许可证纠错、10 方向映射、适配清单 |
| `ad-director-workflow.md` | 六角色 + 22 字段分镜 + 提示词模板 + 质量否决权 |
| `product-ad-editing-guide.md` | 《AI 产品广告剪辑规范》v1 |
| `tts-research.md` | 方案对比、三层拦截证据、音频链路实测、安装批准清单 |
| `vidova-jianying-next-steps.md` | 窗口门/Host 授权研究、零额度测试清单、下一步 |
| `blockers.md` | 缺陷台账、D004/D005 处理、B1–B13 阻塞、9 项批准清单 |
| `recommended-architecture.md` | L0–L9 架构、数据契约、现状矩阵、ADR |
| `subtitle_checks.py` / `run_signoff_tests.py` | 修复后源码与测试源码 |
| `evidence/*.json` + `signoff_sample_contact_sheet.jpg` | 9 份证据文件 + 1 份 SHA-256 清单 |
| `../status/pipeline-status.json` | 升级到 schema 1.3 |

大媒体（测试帧 MP4/PNG、成片、合成测试音 WAV）只存本机 `pipeline/qa004/`、`pipeline/tts004/`，**未提交**；本机绝对路径只存仓库外 `pipeline/config.local.json`。

## 9. 验证与合规检查

| 检查 | 结果 |
|---|---|
| 自动化测试 | **26 / 26 PASS**，退出码 0 |
| Python 编译 | `subtitle_checks.py` / `run_signoff_tests.py` 全部通过 |
| JSON 校验 | 交付目录 10 个 JSON 全部解析通过（含全部证据文件与哈希清单） |
| 敏感扫描 | 23 个文本文件，**0 命中**（PAT / 私钥 / token 值 / 本机用户路径），`evidence/secret_scan_004.json` 可复算 |
| 证据可验证 | `evidence/manifest.sha256.json` 列出全部证据文件 bytes + sha256 |
| 用户原有工程 | 2 个剪映草稿 SHA-256 前缀 `75e07786574bf6d9` / `0792b2c4e809a6b6`，与 WB-VIDEO-003 完全一致；空 Vidova 测试项目保留未删 |
| 付费 / 额度 | `generate_asset` 0 次、在线 TTS 0 次、购买/充值 0、剪映云额度 0 |
| 依赖安装 | **0 个**第三方包 / Skill / 模型 |
| 凭据 | 本轮未读取、打印、复制、提交任何明文 PAT / token；推送用系统凭据管理器 |
| 安全策略 | 未禁用、未修改、未绕过；被拦能力未通过包装器重试 |

## 10. 已知问题与未验证假设

- D004 / D005 未修复；返工 2/2 用尽，第 3 轮硬停 `REVIEW_REQUIRED`。
- 帧内字号与对比度是像素级**估计**，不是认证测量；不可测时返回 `NEEDS_MANUAL_REVIEW`。
- 26 项测试中的审核人全部是合成测试数据；**没有产生任何真实人工签核**，也没有写入生产签核台账。
- `anthropics/skills` 根目录无 LICENSE：本轮只读检查，未复制任何文件；若后续引用需先确认许可。
- GitHub REST API 匿名限额耗尽（403），维护状态来自 commits Atom feed 而非 API，star 数/版本未取。
- 17 个第三方项目**全部未在本机安装或运行**；"适合 Windows/CPU"是基于依赖与许可证的判断，不是实测。
- 剪映 `--help` 本轮外部调用返回 `3221226505` 且无输出，与 WB-VIDEO-003 记录的 5 个子命令来源不同，如实并列、不否定历史。
- 免费额度剩余量、自动续费风险：UNVERIFIED。
- 此前明文出现过的 GitHub PAT 仍建议撤销并轮换。

## 11. 最终结论：**B · `CONDITIONAL PASS`**

| 判定 | 依据 |
|---|---|
| 为什么不是 A `PASS` | 任务书要求"本轮所有约定的研究、修复和测试均有真实证据"：P0 修复与调研证据充分，但**中文语音 WAV 未产出**（第 8 问）、Vidova 窗口门与剪映授权**只是研究线索**（第 9/10 问）、第三方项目**未本机运行**、工作流与剪辑规范仍是设计文档而非已执行产物。约定目标未全部达成。 |
| 为什么不是 C `FAIL` | 关键问题（P0 逐项签核）**确已修复**，26/26 自动化测试、修复前后对比、真实测试帧数值证据、逐 URL SHA-256 调研证据齐备；11 份规定交付文件全部产出；零付费、零工程改动、零凭据泄露。不属于"关键问题没解决或证据不足"。 |
| 为什么是 B | 符合"部分工作完成，仍有明确阻塞"：允许继续已验证的本地质检与规范工作，**不允许进入正式宣传片制作**。 |

**准入含义**：
- ✅ 允许继续：本地质检/字幕签核门、manifest 与状态机、只读环境调查、文档规范、参考渲染（占位）、音频 QA 链路验证。
- ❌ 不允许：真实素材生成、真实剪映导入/导出、正式旁白、第 3 轮自动返工、把研究方案写成已打通、把测试信号/占位音频/模拟界面冒充真实产物。

**本轮到此停止，等待 ChatGPT 复核 WB-VIDEO-004 报告与证据，再下达下一轮指令。**

---

## 12. 提交与 GitHub 链接

| 项 | 值 |
|---|---|
| 仓库 / 分支 | `swdscsc/yaodao-agent` / `main` |
| 基准提交 | `addca7883c59f8aeb490376d71478095799e5d97` |
| **主体交付 commit SHA** | **`a5659e3eba3b44969f964889df95ad19d4048ee6`** |
| 推送结果 | `addca78..a5659e3  main -> main`，退出码 0；`ls-remote origin refs/heads/main` 已核对一致 |
| 提交规模 | 25 个文件，7,617 行新增 / 101 行删除；含 11 份规定文档、2 份源码、10 份证据、状态文件、`.gitignore` |
| 推送方式 | `git -c credential.helper= -c credential.helper=wincred`（先清空全局 `manager` helper 链）+ `GIT_TERMINAL_PROMPT=0` + 本机代理；**系统受保护凭据**，本轮未读取/打印/复制/提交明文 PAT；未 force-push、未改 remote 或全局 git 配置 |
| 首次推送故障（如实记录） | 全局 `credential.helper=manager` 触发 GCM 弹窗挂起 5m52s，远端未更新；终止该后台任务后改用上面的 helper 链重置方式，一次成功。代理对 `github.com` 普通网页返回 504，但 git 协议端点可用 |
| 补记说明 | 本节为推送成功后追加的元数据，随一次独立小修订提交推送；**最终远端 HEAD 会晚于 `a5659e3`**，以会话回报的 `ls-remote` 结果为准。主体交付内容未变 |

主要链接（相对仓库 `main`）：

- 主报告：`docs/ai-collaboration/outbox/WB-VIDEO-004/report.md`
- P0 修复与测试：`subtitle-signoff-fix.md` / `subtitle-signoff-tests.json`
- 研究：`github-project-research.md` / `skill-research.md` / `tts-research.md` / `vidova-jianying-next-steps.md`
- 规范：`ad-director-workflow.md` / `product-ad-editing-guide.md` / `recommended-architecture.md`
- 阻塞与批准清单：`blockers.md`
- 机器可读状态：`docs/ai-collaboration/status/pipeline-status.json`
