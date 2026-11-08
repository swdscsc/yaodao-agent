# WB-VIDEO-004 · 未解决问题、缺陷处理与批准清单

| 项 | 值 |
|---|---|
| 本轮修复 | P0 字幕人工签核漏洞 → **FIXED**（26/26 测试） |
| 历史缺陷 | D004 `STILL_FAILING`、D005 `OPEN / REVIEW_REQUIRED`（**均未擅自返工**） |
| 返工策略 | 2/2 轮已用尽，`third_cycle_allowed = false`，第 3 轮硬停 `REVIEW_REQUIRED` |
| 结论 | `B · CONDITIONAL PASS` |

---

## 1. 缺陷台账

| 编号 | 描述 | 严重度 | 责任模块 | 本轮处理 | 状态 |
|---|---|---|---|---|---|
| **P0（新）** | WB-VIDEO-003 `evaluate_subtitle_fix()` 只认一个顶层全局 `APPROVED`，三个 `MANUAL_ITEMS` 从未逐项审核 | 高 | 字幕质检 | 重写 `subtitle_checks.py`：逐项独立记录 + 具名审核人/时间/证据 + 帧/时间段/视频版本/字幕版本绑定 + 防模拟审核人 + 自动/人工分离 | ✅ **FIXED**（26/26） |
| **QA-1（新）** | 字号只读渲染参数就判 PASS | 中 | 字幕质检 | 三态分离，只有帧内实测可自动 PASS | ✅ FIXED |
| **QA-2（新）** | 对比度用整带灰度分布，非文字/背景 | 中 | 字幕质检 | 帧差文字掩膜 + 邻近背景环 + WCAG 风格比值 | ✅ FIXED |
| **QA-3（新）** | 纯 IoU 会漏掉小主体完全落在字幕带内的遮挡 | 中 | 字幕质检 | 增加 intersection/subject、intersection/subtitle、包含关系 | ✅ FIXED |
| **D004** | 竖屏字幕中心 0.6208 H、字号 26 px < 32 px；横屏底边 0.947 H 超 0.94 安全线 | 中 | 字幕 / 剪辑 | **本轮未修复画面**，只修复判定机制；旧 `FIXED` 是虚假判定 | **`STILL_FAILING`** |
| **D005** | WB-VIDEO-002 参考渲染 5.5–8.5 s 为 `smptebars` 静态彩条测试信号，旧质检漏报冻结 | 中 | 素材 | 明确声明为**测试占位素材**，不是真实镜头 | **`OPEN / REVIEW_REQUIRED`** |
| D003 | 跨素材重复镜头 | — | Vidova | WB-VIDEO-002 已修，本轮未复现 | 历史 FIXED |

---

## 2. D004 竖屏原生重排方案（**方案，未执行；不批准第 3 轮返工**）

任务书明确"本轮先修复质检签核机制，再制定竖屏原生重排方案""不批准第 3 轮自动返工"。方案如下，供 WB-VIDEO-005 在批准后执行：

| 步骤 | 动作 | 验收证据 |
|---|---|---|
| 1 | 为 9:16 **独立设计**画面布局：主体上移到上 1/3–1/2，产品界面重新构图（只截关键功能区并放大），不裁切横屏 | `shotlist.json` 竖屏 `safe_area_spec` + 布局草图 |
| 2 | 字幕重排到 y ∈ [0.72H, 0.94H]，字号 ≥32 px，单行 ≤18 字，避免 0.35–0.65H 中部带 | 帧内实测 `font_px_measured ≥ 32` + `safe_area = PASS` |
| 3 | 文字/邻近背景对比度 ≥4.5 且 Δ亮度 ≥45；提供无字幕参考帧证明真实烧录 | `subtitle_checks.py` 的 `contrast` / `burned_in_evidence` |
| 4 | 与已声明主体/UI 框做 IoU + 覆盖率双检；未声明内容遮挡走人工项 | `subject_overlap` + 人工记录 |
| 5 | 三个 `MANUAL_ITEMS` **逐项具名人工签核**（帧 / 时间段 / 视频版本 / 字幕版本绑定） | `signoff_integrity.production_admissible = true` |
| 6 | 只有 7 个先决条件全 true 才允许把 D004 标 `FIXED` | `evaluate_subtitle_fix()` 输出 |

**硬门槛**：没走完 1–6 且没有真实人工签核，D004 保持 `STILL_FAILING`；不得用"重新渲染了一个文件"再次冒充修复完成。

## 3. D005 占位声明

- 5.5–8.5 s 的 `smptebars` 是**本地 FFmpeg 生成的测试信号**，用途是验证冻结检测链路，**不是**老人用药情景、不是产品界面、不是 AI 生成素材。
- 不得把它写进任何正式素材 manifest 的交付部分；`manifest.json` 中必须 `is_placeholder = true`、`allow_edit = false`。
- 后续真实镜头需要重新生成（或真实拍摄/录屏）→ 重新走素材验证 → 重新登记 → 重新质检。
- 本轮**没有**批准任何自动返工，`third_cycle_allowed = false`。

---

## 4. 未打通的技术阻塞（更新）

| # | 阻塞 | 本轮验证到哪一步 | 状态 |
|---|---|---|---|
| B1 | Vidova editor GUI 窗口门 | MCP 18 工具实测；无任何工具能开窗口；发现 `vidova://` 协议但只有 auth 回调；`open-project` 是内部托盘 IPC | **OPEN**（有线索，未验证） |
| B2 | Vidova 托管额度 | `generate_asset` 明确消耗 hosted quota；无额度查询工具；余额/自动续费 UNVERIFIED；本轮 0 次调用 | **STOP（等审批）** |
| B3 | Vidova 无导出/渲染工具 | 18 工具中确认不存在 | 架构限制 |
| B4 | 剪映 CLI Host token 门 | 主程序当前未运行、20066 未监听；外部 `--help` 退出码 3221226505；hubcli 需 Host 注入 `CUSTOM_AGENT_BUN_EXECUTABLE`；token 环境变量不存在 | **OPEN** |
| B5 | 独立剪映测试草稿未创建 | 0 个；两个现有工程 SHA-256 前后一致，保持只读 | **NOT_STARTED** |
| B6 | 真实中文 TTS 未打通 | 中文 SAPI 语音存在；三条调用路径全被安全策略拦截；Python TTS 包全缺；**0 段中文语音 WAV** | **OPEN（等依赖批准）** |
| B7 | UI Automation 未执行 | 0 次；需在明确限定窗口内授权 | **NOT_ATTEMPTED** |
| B8 | 竖屏非原生重排 | D004 重判仍 `STILL_FAILING` | **OPEN** |
| B9 | PAT 安全 | 未读取/打印/提交明文 PAT；仍建议撤销并轮换此前明文出现过的值 | **待用户操作** |
| B10 | 空 Vidova 测试项目残留 | `893d1af1-…` 保留，未删除 | **保留** |
| **B11（新）** | 第三方开源项目未在本机安装/运行 | 17 个仓库只做只读静态检查；`实际测试结果 = 静态检查通过` | **需批准试装** |
| **B12（新）** | `anthropics/skills` 许可未确认 | 根目录 5 个 LICENSE 候选全 404；未复制任何文件 | **不集成** |
| **B13（新）** | GitHub REST API 匿名限额耗尽 | `api.github.com` 403；已用 raw + Atom + HTML 替代，证据完整 | 已绕过（合规替代） |

---

## 5. 下一阶段需要用户批准（集中清单，不逐条打断）

| # | 事项 | 类别 | 关联 |
|---|---|---|---|
| 1 | 1 次最小额度 `generate_asset` + 明确额度余量上限（确认不购买、不开自动续费） | 付费 / 额度 | B2 |
| 2 | 启动剪映 GUI 并在**独立空白测试草稿**中做导入/编辑/导出（现有 2 工程只读） | 应用操作 | B4/B5 |
| 3 | 在明确限定窗口内使用 UI Automation（Vidova 托盘打开项目、剪映测试草稿） | 桌面控制 | B1/B7 |
| 4 | 安装本地 TTS 依赖（见 `tts-research.md` §4：来源 / 许可证 / 大小 / 联网 / GPU 已列明） | 本地依赖 | B6 |
| 5 | 试装 `faster-whisper`（CPU）与 `PySceneDetect`（纯 CPU）并下载模型 | 本地依赖 + 联网下载 | B11 |
| 6 | 验证 `vidova://` 协议行为（只观察，不触发登录/账号操作） | 应用研究 | B1 |
| 7 | 是否清理空 Vidova 测试项目 `893d1af1-…` | 删除 | B10 |
| 8 | 撤销并轮换此前明文出现的 GitHub PAT | 凭据 | B9 |
| 9 | D004 是否允许进入第 3 轮返工（当前硬停 `REVIEW_REQUIRED`） | 人工审核节点 | D004 |

**未批准前不做**：任何付费/额度消耗、任何 GUI 桌面控制、任何依赖安装、任何模型下载、任何删除、任何公开发布、任何凭据变更。

---

## 6. 建议的下一任务书（WB-VIDEO-005）

- **Goal**：解除 B1 / B4 / B6，完成"1 个真实素材 + 1 个独立剪映草稿 + 1 段真实中文旁白"的最小真实验证。
- **Scope**：按 `e2e-plan.md`（WB-VIDEO-003）的 13 环节与 `ad-director-workflow.md` 的 A→C 流程，产出 1 份 22 字段分镜表与 `product_facts.json`；**仍不制作正式宣传片**。
- **Inputs**：本目录全部文件、`WB-VIDEO-003/e2e-plan.md`、`status/pipeline-status.json`、本机 `pipeline/`（仓库外）。
- **Acceptance**：真实素材文件 + ffprobe 证据 + manifest 登记；独立草稿 + 导入/导出回执；中文 WAV + 音频 QA + 人工试听记录；全程 0 未批准成本。
- **Safety**：不购买额度、不改/删现有工程、不公开发布、不上传隐私与凭据、不绕过安全策略。
- **Expected report**：`docs/ai-collaboration/outbox/WB-VIDEO-005/report.md`。
- **Stop**：完成后停止，等待 ChatGPT 复核。
