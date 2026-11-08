# WB-VIDEO-004 · 推荐系统架构（可复用 AI 视频生产系统 v1）

| 项 | 值 |
|---|---|
| 目标 | 产品分析 → 创意策划 → 广告脚本 → 分镜 → AI 素材 → 配音 → 自动剪辑 → 后期包装 → 质量检查 → 返工 → 成片交付 |
| 定位 | **架构设计 + 现状矩阵**，不是已实现系统的宣传 |
| 本轮状态 | 规范与质检门已落地；真实素材生成、真实配音、真实剪映导入导出**均未打通** |
| 关联 | `ad-director-workflow.md`、`product-ad-editing-guide.md`、`github-project-research.md` |

---

## 1. 分层架构

| 层 | 模块 | 输入 | 输出 | 当前状态 |
|---|---|---|---|---|
| L0 | 资料与真实性治理 | 用户提供的产品资料 | `product_facts.json` | 规范已定，未执行 |
| L1 | 创意与脚本 | L0 + 投放约束 | `creative_brief.md` / 脚本 | 规范已定，未执行 |
| L2 | 分镜与提示词 | L1 | `shotlist.json`（22 字段） | 规范已定，未执行 |
| L3 | 素材生成 / 采集 | L2 | `manifest.json` + 素材文件 | **阻塞**：Vidova 额度 + 窗口门 |
| L4 | 配音与音频 | 脚本 | 中文 WAV / SRT / BGM / SFX | **阻塞**：TTS 未产出中文 WAV |
| L5 | 自动剪辑 | L2 + L3 + L4 | EDL + 剪映工程 | **阻塞**：剪映 Host 授权 |
| L6 | 后期包装 | L5 | 字幕动画 / 调色 / 片头片尾 | 未开始 |
| L7 | 质量检查 | 全部 | `qa_verdict.json` + 证据 | **部分可用**：本地 FFmpeg/像素质检 + 本轮逐项签核门 |
| L8 | 有界返工 | 缺陷台账 | 修复版本 | 已实现 2 轮上限；**第 3 轮硬停 `REVIEW_REQUIRED`** |
| L9 | 交付 | 全部 + 签核 | 横屏 / 竖屏 / 工程 / 源码 / 报告 | 未开始（禁止进入正式制作） |

**关键设计**：L0 的真实性状态与 L2 的 `source_type` 会一路传递到 L7，任何一层丢失标注都会让质检 FAIL。这样能防止"模拟界面被当成真实功能""测试信号被当成真实镜头"。

---

## 2. 数据契约（机器可校验）

### 2.1 `manifest.json`（素材）

沿用 WB-VIDEO-002 的 17 字段（`asset_id / file_path / file_type / duration_seconds / width / height / fps / shot_id / source_type / is_ai_generated / is_real_footage / qa_status / quality_checks / allow_edit / generation_status / retry_count / checksum_sha256 / notes`），**新增**：

| 新增字段 | 用途 |
|---|---|
| `feature_status` | 与 L0 真实性台账对齐 |
| `consistency_group` | 视觉一致性分组 |
| `generation_tool` | `vidova / ffmpeg_reference / real_capture / simulated_ui` |
| `quota_consumed` | 是否消耗托管额度（成本审计） |
| `is_placeholder` | 测试信号 / 占位素材显式标记 |

`allow_edit = true` 是进入 L5 的硬门槛；`is_placeholder = true` 的素材**永远不得进入正式交付**。

### 2.2 `shotlist.json`（分镜）

22 字段，见 `ad-director-workflow.md` §3。

### 2.3 人工签核记录（本轮新增，强制）

见 `subtitle-signoff-fix.md` §2：每个 `MANUAL_ITEMS` 独立 `reviewer / reviewed_at / item_id / verdict / evidence / notes` + `frame_ref / time_range / video_version / subtitle_version` 绑定。自动与人工两个独立结构，`FIXED` 需 7 个先决条件全满足。

### 2.4 缺陷台账

`defect_id / timecode / description / severity / owner_module / fix_plan / fix_result / evidence_ref / rework_cycle`。有界返工：最大 2 轮，`third_cycle_allowed = false`，第 3 轮停 `REVIEW_REQUIRED`。

### 2.5 状态机

`PENDING → GENERATING → COMPLETED → VALIDATING → (APPROVED | REVIEW_REQUIRED | FAILED) → EDITING → QA_CHECKING → (DELIVERED | ESCALATED)`；失败有界重试；每次流转写 `state_log`（含 artifact sha256 与 gate_result）。

---

## 3. 质量否决权（系统级，不是某个脚本）

1. 质量总监独立于创意/剪辑/调度，**任一维度 FAIL 即整体 REJECTED**。
2. 自动 PASS ≠ 质量合格；自动 FAIL 不可被人工 APPROVED 覆盖。
3. 程序不可判定项一律 `NEEDS_MANUAL_REVIEW`，且必须**逐项具名签核**（本轮 P0 修复）。
4. `NEEDS_MANUAL_REVIEW` 不得被汇总成 PASS；未审核项不得被整体签核顶替。
5. 交付门：所有证据有 SHA-256 清单、所有人工项有独立签核、无占位素材混入、无未批准的额度消耗。

---

## 4. 工具能力四级与权限分级（防止"接口存在=成功"）

| 级别 | 含义 | 允许写入报告的表述 |
|---|---|---|
| L1 接口存在 | 代码/契约里看到 | "检测到工具/契约" |
| L2 可调用 | 参数齐、能发起请求 | "可调用" |
| L3 调用成功 | 返回成功结果 | "调用成功 + 回执" |
| L4 生成有效素材 | 文件可解码、经质检 | "生成了有效素材" |

**本项目当前**：Vidova MCP 到 L3（只读/项目创建），`generate_asset` 停在 L2 之前（额度未批准）；`import_asset` 停在 L2（窗口门）；剪映 CLI 停在 L1（契约存在，写入被 Host token 门阻断）；TTS 停在 L1（语音存在，合成被安全策略阻断）。

工具权限三级：

| 级别 | 例子 | 是否需批准 |
|---|---|---|
| `READ_ONLY` | MCP `tools/list`、注册表查询、asar 静态扫描、raw GitHub 抓取 | 否 |
| `LOCAL_REVERSIBLE` | 本机 FFmpeg 测试媒体、独立测试帧、临时 WAV | 否 |
| `NEEDS_APPROVAL` | 额度消耗、剪映 GUI/草稿、UI Automation、安装依赖、删除、公开发布、凭据变更 | **是** |

---

## 5. 证据治理

- 每阶段产出 `evidence/*.json` + `manifest.sha256.json`（对全部证据文件计算 bytes + sha256）。
- 本机绝对路径只存仓库外 `pipeline/config.local.json`；提交内容用 `<LOCAL>` / `%LOCALAPPDATA%` / `<PIPELINE>` 占位符。
- 自动检查与人工签核分文件存储；测试模拟审核人不得进入生产台账。
- 提交前：JSON 解析、Python 编译、敏感信息扫描、用户原有工程 SHA-256 前后对比、`git diff` 复核。
- 大媒体只留本机，不提交公开仓库。

---

## 6. 现状矩阵（真实，不含推测）

| 能力 | 状态 | 证据 |
|---|---|---|
| 逐项人工签核门 + 字幕质检增强 | ✅ 已实现并测试 26/26 | `subtitle-signoff-tests.json` |
| FFmpeg 参考渲染 / 黑屏静音冻结质检 | ✅ WB-VIDEO-002/003 已验证 | 历史报告 |
| 静态时间区间白名单（P0-1） | ✅ 已修复 | `WB-VIDEO-003/qa-fix-report.md` |
| 广告导演六角色 + 22 字段分镜 + 剪辑规范 | ✅ 文档已成 | 本目录两份规范 |
| GitHub 项目 / Skill 真实调研 | ✅ 17 仓库只读检查 | `github_repo_probe.json` |
| 真实 AI 素材生成 | ❌ 0 次 `generate_asset` | 额度红线 |
| 真实中文配音 | ❌ 0 段语音 WAV | `tts_probe_004.json` |
| 剪映真实导入 / 编辑 / 导出 | ❌ 0 次 | `jianying_host_research.json` |
| Vidova 窗口门 | ⚠️ 找到 URL scheme 线索，未验证 | `vidova_deeplink_research.json` |
| 剪映 Host 授权 | ⚠️ 未找到合法外部路径 | `jianying_host_research.json` |
| 本地第三方工具安装 | ❌ 0 个 | 需批准清单 |

---

## 7. 阶段路线（建议，非本轮执行）

| 阶段 | 目标 | 前置批准 |
|---|---|---|
| WB-VIDEO-005 | 解 B1/B4/B6：合法打开 Vidova 窗口、剪映独立测试草稿、本地中文 TTS 最小验证 | 额度上限、GUI/UIA、依赖安装 |
| WB-VIDEO-006 | 15–20 s 最小真实 E2E：1 个真实素材 + 1 个独立草稿 + 1 次真实导出 | 同上 + 明确成本上限 |
| WB-VIDEO-007 | 完整宣传片制作（横屏 + 竖屏 + 工程 + 全部交付物） | ChatGPT 对前两阶段审核通过 |

每一阶段仍按 `docs/ai-collaboration/` 协议：inbox 任务 → 执行 → outbox 报告 + 证据 → 提交推送 → **停止等待审核**。

---

## 8. 架构决策记录（ADR 摘要）

| # | 决策 | 理由 |
|---|---|---|
| ADR-1 | 不整包引入 MoneyPrinterTurbo / ShortGPT | 依赖付费 LLM/素材 API，替换掉现有可审计状态机与证据链 |
| ADR-2 | 不引入 ComfyUI 等 GPU 工作流 | 本机 Intel 核显，无独显 |
| ADR-3 | 不复制 `anthropics/skills` 代码 | 根目录无 LICENSE，许可未确认；只提取工作方法 |
| ADR-4 | 字幕质量判定必须逐项人工签核 | ChatGPT 审核发现全局 APPROVED 漏洞；自动 PASS 不能代表人工判断 |
| ADR-5 | 渲染参数字号 / 全带灰度分布 / 纯 IoU 不得作为质量判据 | 三者都会产生"假准确率"，本轮已用真实测试帧证明 |
| ADR-6 | 测试信号、模拟界面、占位音频显式标记并禁止进入交付 | 防止冒充真实素材与真实功能 |
| ADR-7 | 所有付费/额度/GUI/删除/发布操作集中在 `NEEDS_APPROVAL` 层 | 与用户长期执行规则一致 |
