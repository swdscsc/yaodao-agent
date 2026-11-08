# WB-VIDEO-005-PREPRODUCTION · 阶段 1 执行报告

| 项 | 值 |
|---|---|
| 任务 | `docs/ai-collaboration/inbox/WB-VIDEO-005-preproduction.md`（零风险预制作） |
| 状态 | **阶段 1 完成，停在审核前** |
| 拉取基准 | 远端 `main` 最新 HEAD `c753f0714e75bf7328b9263f957304a0ac69fcd3`（`Start video production: create zero-risk preproduction task`, 2026-11-08T19:22:30+08:00） |
| 拉取方式 | `git fetch origin main` + `merge --ff-only`（`7940d95..c753f07`），`GIT_TERMINAL_PROMPT=0` + 受保护的系统凭据存储；**未读取/打印/提交任何明文 PAT** |
| 本地 HEAD（执行前） | 与远端一致，工作区干净（`git status --short --branch` → `## main...origin/main`） |
| 基准差异说明 | 会话里的 WB-VIDEO-005 主任务书目标是**阶段 1–6 全流程**；仓库里的 `preproduction` 任务书把已授权范围明确限定为「只读核查 + 脚本/分镜/剪辑准备」，并要求「完成后提交核对远端 HEAD，然后停止等待 ChatGPT 审核，不得自行扩大到正式 E2E」。**本轮按仓库中的阶段授权执行**，不越过它 |
| 本轮结论 | `B · CONDITIONAL PASS`（预制作交付完整且可复核；真实视频制作未获授权、素材与配音均不具备） |
| 本轮视频产出 | **0 个 MP4**。**没有任何宣传片文件被剪出或上传** |

---

## 1. 本轮实际完成了什么

1. 拉取并核对远端最新 `main`，记录真实 HEAD 与快进结果（见上表）。
2. 阅读产品真实资料：`README.md`（230 行）、`agent.ts`、`src/medTools.ts` / `medVision.ts` / `medPromptBuilder.ts` / `medStore.ts` / `medicinePhotoHandler.ts`，逐项把功能主张落到文件路径 + 符号/行号。
3. 只读盘点工作区与仓库全部媒体文件：**56 个**，逐文件计算 SHA-256 并用 `ffmpeg -i` 解析时长/分辨率/帧率/编码；结论 `real_product_footage_count = 0`。
4. 只读探测本机能力：FFmpeg 7.1（含 `drawtext` / `subtitles` / `ass` / `xfade` / `zoompan` 等滤镜）、Python 3.13.14、16 个中文字体文件、SAPI 语音 token（桌面 2 个、OneCore 3 个）、`ffprobe` **不在 PATH**。
5. 两次只读公开检索，形成原创创意方向与「排除项」清单（案例仅作方法论，不引用其中任何数字）。
6. 完成 **4:00 主片逐镜头脚本（33 镜 / 8 章 / 28 句旁白）**、**55 s 竖屏原生重排（11 镜）**、双轨字幕草稿、完整旁白稿、素材缺口与开剪就绪度评估。
7. 用**同一份镜头数据表**生成 CSV / SRT / Markdown，并跑一致性校验：时间码连续、总长 240.0 s、28 句旁白↔28 条主字幕逐字一致、字幕不越镜、禁用词 0 命中、每镜都有素材来源 / 缺口 / 真实性标签。

---

## 2. 实际生成了哪些文件

目录：`docs/ai-collaboration/outbox/WB-VIDEO-005-PREPRODUCTION/`

**任务书要求的 10 份交付（全部存在）**

| # | 文件 | 内容 |
|---|---|---|
| 1 | `report.md` | 本文件 |
| 2 | `asset-inventory.csv` | 56 行素材盘点，逐行含 SHA-256、技术参数、`is_real_product_footage`、`usability_for_final_film` |
| 3 | `product-claims-register.md` | 12 项可用主张 + 5 项限制 + 6 项禁用宣称 + 文档/源码差异 + 标注规则 |
| 4 | `main-film-script.md` | 8 章 33 镜逐镜脚本 + 视觉/声音/导出/合规规范（574 行） |
| 5 | `main-film-shotlist.csv` | 33 行 × 19 列可执行剪辑指令 |
| 6 | `narration-draft.md` | 28 句旁白 + 16 句画内台词 + 配音要求与合规约束 |
| 7 | `subtitle-draft.srt` | 主旁白字幕轨 28 条，**DRAFT、未烧录** |
| 8 | `vertical-cut-plan.md` | 55 s / 11 镜 9:16 原生重排 + 竖屏字幕安全区与 D004 预防 |
| 9 | `first-cut-readiness.md` | 首段 22 s 能否开剪的判定、6 项缺口、U0–U6 解锁步骤与费用/额度 |
| 10 | `evidence/manifest.sha256.json` | 主体交付文件的 SHA-256（自身除外；提交后追加的 `push-verification.json` 在清单头声明并单独记录自身哈希） |

**附加证据（不改变任务书要求的 10 份）**

| 文件 | 内容 |
|---|---|
| `creative-research.md` | 创意研究：6 个公开案例 + 7 条叙事决策 + 排除项（用户主任务书 §四.1 要求「先研究」） |
| `evidence/asset-probe.json` | 56 个媒体文件的原始只读探测数据（含每条 SHA-256 与 ffmpeg 元数据） |
| `evidence/capability-probe.json` | 本机 FFmpeg / 字体 / SAPI / Git / 时区 / 红线计数 |
| `evidence/consistency-check.json` | 时间码、旁白↔字幕、禁用词、标签完整性校验结果（`all_consistency_checks_passed: true`） |
| `evidence/subtitle-draft.meta.json` | 双轨字幕设计、DRAFT 声明、14 处待重排的时间码重叠 |
| `evidence/dialogue-subtitle-draft.srt` | 画内对白轨 16 条，与主旁白轨分离 |
| `evidence/narration-table.md` | 由同一数据表生成的旁白逐句表（供交叉核对） |
| `evidence/push-verification.json` | 提交后的 commit SHA、远端 HEAD、文件链接校验（提交后追加） |

> 本轮**未修改** `status/pipeline-status.json`：该文件仍如实记录 WB-004 的 `B_CONDITIONAL_PASS`。把预制作写进正式流水线状态会被误读为「WB-VIDEO-005 已执行」，建议 ChatGPT 审核后由下一任务书统一更新。

---

## 3. 哪些是真实素材，哪些是测试 / 模拟素材

| 类别 | 明细 | 判定 |
|---|---|---|
| **真实产品资料** | `README.md`、`src/*.ts` 源码、`agent.ts`、`tests/*.ts` | ✅ 真实，且是本轮唯一被允许写进旁白的功能证据来源 |
| **真实产品画面** | **0 个** | ❌ 仓库里没有界面截图、真机照片或录屏 |
| **本地测试素材** | `pipeline/assets/*.mp4`（5 个，1920×1080@30fps，2–3 s，`local_synthetic`） | ❌ FFmpeg 合成测试信号，`NOT_USABLE_AS_FINAL_FOOTAGE` |
| **本地参考成片** | `pipeline/renders/final_horizontal*.mp4` / `final_vertical*.mp4` 等 18 个文件 | ❌ WB-002 参考渲染，含 D005 标记的 `smptebars` 占位段；**不得**进 `final/` |
| **本地音频** | `bgm.wav`(12 s) / `sfx.wav`(0.4 s) / `audio_chain_test_tone.wav`(2.5 s, 440 Hz) | ❌ 合成测试音，不是配乐、不是旁白 |
| **仓库内 7 张 JPG** | WB-002/003/004 的质检证据帧与联系表 | ❌ 测试证据截图，不是产品画面 |
| **本轮新产出的图/视频/音频** | **0 个** | 只有文本、表格、JSON、SRT |
| **脚本中的画面** | 33 镜里 `DRAMATIZATION` / `MOCK_UI` / `MISSING` 已逐镜标注 | ⚠️ 全部是**计划**，不是已存在的素材 |

---

## 4. 任务书 §4 四个必答问题

### Q1：仓库里到底有没有可用的真实产品画面？逐项列证据。

**没有，一个都没有。**

| 证据 | 值 |
|---|---|
| `git ls-files` 全量文件类型 | 70 `.ts` / 38 `.json` / 23 `.md` / 10 `.py` / 7 `.jpg` / 1 `.srt` / 1 `.txt`；无 `.png` 产品截图、无产品录屏 |
| 7 张 JPG 的实际身份 | `WB-VIDEO-002/evidence/*`（测试帧、联系表）、`WB-VIDEO-003/evidence/subtitle_contact_sheet.jpg`、`WB-VIDEO-004/evidence/*contact_sheet.jpg` —— 全是 QA 证据 |
| `asset-inventory.csv` | 56 行全部 `is_real_product_footage = NO`、`usability_for_final_film = NOT_USABLE_AS_FINAL_FOOTAGE` |
| `evidence/asset-probe.json` | `summary.real_product_footage_count = 0`，`in_repo_count = 7`，`local_only_count = 49` |
| `WB-VIDEO-002/shotlist.json:6,13,23,33` | 明确 `Assets in this E2E are FFmpeg-synthesised LOCAL test material`、`source_type: local_synthetic` |
| `WB-VIDEO-003` D005 | 5.5–8.5 s 为 `smptebars` 测试信号占位，须标 `is_placeholder=true, allow_edit=false` |

因此脚本中所有涉及设备的镜头都标为 `MOCK_UI` / `PRODUCT_UI_REQUIRED` / `STILL_LIFE_REQUIRED`，并写明「不得把占位画面升级为真实画面」。

### Q2：第一段 15–30 秒能否仅用现有素材剪出来？如果不能，最少缺哪几项？

**不能。** 选定首段为主片 **S08–S10（52–74 s，22 s）**，逐镜缺口见 `first-cut-readiness.md` §2。

最少缺 **4 项硬缺口**：
1. **G1 真实或明确标注的产品画面** —— 0 张真实截图/录屏；用现有 MP4 顶替即冒充（D005 红线）。
2. **G2 中文旁白音频** —— 0 段中文语音；本机 SAPI 调用被安全策略阻断，440 Hz 测试音不是旁白。
3. **G3 合法 BGM / SFX** —— `bgm.wav` / `sfx.wav` 是合成测试音，来源与许可不成立。
4. **G4 导出与上传授权** —— 本轮任务书 §0 明确禁止导出视频，§3 要求完成后停止等待审核。

（G5 真实生活实拍、G6 字幕与音频对齐影响完整主片与竖屏，但不阻塞这 22 秒首段。）

### Q3：要进入真实剪辑，下一步最少需要用户批准哪一项操作？写清风险、是否免费、是否会消耗额度。

**最少是 U1：由用户本人录制或提供一段中文旁白 WAV（首段约 60–90 字 / 15–30 s）。**

| 维度 | U1 的属性 |
|---|---|
| 是否免费 | ✅ 是 |
| 是否消耗 Vidova / 云端额度 | ❌ 0 |
| 是否安装依赖 / 下载模型 / 联网 TTS | ❌ 0 |
| 是否操作剪映 GUI / UIA / 用户工程 | ❌ 0 |
| 是否绕过系统安全策略 | ❌ 否（正是为了不绕过） |
| 风险 | 几乎无技术风险；仅需用户提供一段音频文件，agent 只读引用 |
| 一次解除 | G2 + G6（旁白与字幕对齐） |

**但仅 U1 仍不能开剪**，还必须有：
- **U6**：新任务书 / 明确授权「阶段 2 导出 MP4 → 质检 → 上传 GitHub」，因为当前 `preproduction` 任务书明确「不导出视频、完成后停止等待 ChatGPT 审核」；
- **U0**（零风险、无需额外批准）：确认接受「模拟界面 / 情景演绎」标注口径，或提供真机画面。

其余 U2（安装本地 TTS：免费但需联网下载、改变环境、不保证解封）、U3（**消耗额度**的 Vidova `generate_asset`，须先核实余量与自动续费）、U4（剪映 GUI / Host token 未解）、U5（合法音乐来源）均**未批准、未执行**。完整表见 `first-cut-readiness.md` §4。

### Q4：不得把「脚本/分镜完成」表述成「视频已剪好」。

本轮**没有**任何视频文件。全文统一口径：
- `videos_rendered = 0`、`video_exported = false`（`evidence/capability-probe.json` / `consistency-check.json`）；
- 字幕状态 `DRAFT_NOT_BURNED_IN`；
- ChatGPT 审核五级状态（已上传 / 可下载 / 已读取 / 画面已检查 / 音频已听审）**全部为 false**；
- `media/WB-VIDEO-005/` 目录**未创建**，避免空目录被误读为已交付。

---

## 5. 已实际跑通 / 仍阻塞

| 能力 | 状态 | 证据 |
|---|---|---|
| 非交互拉取远端 main + 核对 HEAD | ✅ 跑通 | 本文件 §0 表；`evidence/capability-probe.json` |
| 产品功能 → 源码符号/行号逐项核对 | ✅ 跑通 | `product-claims-register.md` |
| 全量媒体文件 SHA-256 + ffmpeg 元数据只读盘点 | ✅ 跑通 | `asset-inventory.csv`、`evidence/asset-probe.json` |
| 由单一数据表生成 CSV/SRT/Markdown 并做一致性校验 | ✅ 跑通 | `evidence/consistency-check.json`（0 errors，14 条诚实的重排 warnings） |
| 本机 FFmpeg / 中文字体 / 语音 token 只读探测 | ✅ 跑通 | `evidence/capability-probe.json` |
| 中文配音（任何一条合法通道） | ❌ 阻塞 | WB-004 `tts-research.md`：三条合法 SAPI 路径被安全策略阻断；不绕过 |
| 真实中文语音 WAV | ❌ 0 个 | `tts_status = NOT_COMPLETE`（`pipeline-status.json`） |
| 合法 BGM / SFX | ❌ 0 个 | 现有均为合成测试音 |
| Vidova 编辑器窗口 / 额度 / 素材生成 | ❌ 未解 | `quota_status` 余量未核实；`generate_asset_calls = 0` |
| 剪映 Host token / 真实导入导出 | ❌ 未解 | 现有 2 个草稿保持不变 |
| 真实产品画面 / 生活实拍 | ❌ 0 个 | 见 Q1 |
| 视频导出、GitHub MP4 上传、ChatGPT 视频审核 | ❌ 未执行 | 本轮授权明确禁止 |

`ffprobe` 不在 PATH（本机只找到 FFmpeg 7.1），已如实记录并在质检计划里写明替代方案，未假装它可用。

---

## 6. 一致性与合规校验结果

| 检查 | 结果 |
|---|---|
| 33 镜时间码连续无空隙、总长 240.0 s | ✅ |
| 28 句旁白 ↔ 28 条主字幕逐字一致 | ✅ |
| 每条字幕落在自己镜头内、同轨无重叠 | ✅ |
| 禁用词（疗效/治愈/保证/有效率/用户评价/销量/第一/最好/包治 等）在旁白中 | ✅ 0 命中；S33 的**否定式免责声明**单独白名单 + 存在性断言 |
| 每镜都有素材来源 / 缺口 / 真实性标签 | ✅ 33/33 |
| 双轨字幕同镜时间码重叠 | ⚠️ 14 处，作为 warnings 明示，要求真实配音后重排（不隐藏、不伪造对齐） |
| 竖屏字幕安全区 / 字号 vs D004 | ✅ 0.76–0.84 H、≥52 px、下沿 ≤0.86 H，三条历史缺陷阈值均未踩线 |
| 人工审核 / 人工签核 | ❌ **未进行**；无具名审核人，无模拟签核记录 |

---

## 7. 红线核对（本轮全部为 0）

| 项 | 计数 |
|---|---|
| 付费 / 充值 / 自动续费 | 0 |
| Vidova 云端额度消耗 / `generate_asset` | 0 |
| 依赖安装 / 模型下载 / 联网 TTS / 生图 / 视频生成服务 | 0 |
| 剪映 GUI / 草稿创建或修改 / UI Automation | 0 |
| Vidova GUI / 协议操作 / 删除空项目 / 清理缓存 | 0 |
| 读取、打印、复制、提交 PAT / Token / 密码 | 0 |
| 修改、覆盖、移动、删除现有素材或用户工程 | 0 |
| 公开发布 / 上传隐私 | 0 |
| 把测试信号、静态图、合成音当正式素材或旁白 | 0 |
| 导出视频 / 上传 MP4 | 0 |
| 联网操作 | 2 次只读公开网页检索（叙事方法论），0 媒体下载、0 登录、0 付费服务 |

---

## 8. 提交与链接

- 本轮主体提交的 commit SHA、远端 HEAD 复核、以及每份交付的 GitHub 网页 / raw 链接校验，记录在 **`evidence/push-verification.json`**（提交完成后追加，不回填或改写本报告正文）。
- 主体交付文件（提交时存在的全部文件）的 SHA-256 见 **`evidence/manifest.sha256.json`**；`evidence/push-verification.json` 是提交后追加，其自身 SHA-256 记录在该文件的 `self_hash` 字段。
- **视频文件链接：无** —— 本轮没有产生任何 MP4，因此不存在「原始 MP4 链接」「低码率审核版链接」或「视频 SHA-256」。这不是遗漏，是任务书授权边界的结果。

---

## 9. 停止条件与下一步

按 `WB-VIDEO-005-preproduction.md` §3：

> 「完成后提交并核对远端 HEAD，贴出所有文件链接和 SHA-256，**然后停止等待 ChatGPT 审核。不得自行扩大到 WB-VIDEO-005 正式 E2E**。」

本轮到此停止。等待：
1. ChatGPT 对脚本、分镜、主张台账、字幕与素材盘点的复核意见；
2. 用户对 `first-cut-readiness.md` §4 中 **U1（提供中文旁白 WAV）** 与 **U6（授权阶段 2 导出与上传）** 的明确批准；
3. 新的阶段 2 任务书（含额度、安装、剪映 GUI、BGM 来源等逐项授权）。

**在获得上述批准前，不会导出视频、不会上传 MP4、不会把脚本/分镜表述成成片。**
