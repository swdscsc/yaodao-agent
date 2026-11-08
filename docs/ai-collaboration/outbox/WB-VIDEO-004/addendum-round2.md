# WB-VIDEO-004 · 第一轮复核补充（Round 2 Addendum）

| 项 | 值 |
|---|---|
| Task ID | `WB-VIDEO-004-REVIEW-ROUND2` |
| 性质 | ChatGPT 第一轮复核的三项后续事项补充，**不是重新执行 WB-VIDEO-004** |
| 基准提交 | `8c261166253fbfc1f5d52669eca1277a0d776661`（远端 `main`，拉取后与本地一致，工作区干净） |
| 采集时间 | 2026-11-08 17:47–17:52 +0800（`datetime.now().astimezone()`，读取本机时区） |
| 采集方法 | 只读取证；`captured_at` 由脚本运行时生成，未回填、未伪造 |
| 本轮结论 | 三项全部完成；**WB-VIDEO-004 最终结论不变：`B · CONDITIONAL PASS`** |
| 停止条件 | 补充完成后停止；**未**消耗 Vidova 额度、**未**安装依赖、**未**下载模型、**未**操作剪映 GUI、**未**进入正式宣传片制作 |

> 本文件是**新增 addendum**。`report.md`、`subtitle-signoff-fix.md`、`blockers.md`、`github-project-research.md`、`skill-research.md`、`tts-research.md`、`ad-director-workflow.md`、`product-ad-editing-guide.md`、`recommended-architecture.md`、`vidova-jianying-next-steps.md`、`subtitle-signoff-tests.json` 以及 `evidence/` 下所有 round-1 证据**均未改动**（见 §6 的 mtime / SHA-256 核对）。唯一被更新的既有机器状态文件是 `status/pipeline-status.json`，改动逐条列在 §6.3。

---

## 1. 三项后续事项逐条结论

| # | 复核意见 | 结论 | 主要证据 |
|---|---|---|---|
| 1 | `evaluate_subtitle_fix()` 的 context 必须生产固定，不能依赖调用者传入；补充测试证明测试上下文不能误用于生产签核 | **已修复** | `subtitle_checks.py` 内部常量 `PRODUCTION_CONTEXT`；10 条新增 context 用例；`evidence/round2/context-fix-before-after.json` |
| 2 | 字号帧差算法只能称「像素高度估算」，不得称真实字体字号精确测量；生产质检继续保留人工复核 | **已修复 + 已收紧** | 源码措辞与字段全面改写；新增具名人工字号确认作为 `FIXED` 前置条件；5 条新增 font 用例；`evidence/round2/font-wording-audit.json` |
| 3 | 时间戳异常必须解释核实，给出 Windows 系统时间、时区、Git 提交时间来源真实证据 | **已核实：无时钟偏差、无伪造、无回填** | `evidence/round2/timestamp-audit.json`（17,651 bytes，6 类取证、6 条结论） |

---

## 2. 事项 1：生产签核 context 固定

### 2.1 Round-1 的真实缺陷

Round-1 代码（`WB-VIDEO-004/subtitle_checks.py` 修复前）：

```python
def evaluate_subtitle_fix(spec: dict, context: str | None = None) -> dict:
    supplied = spec.get("manual_review") or {}
    ctx = context or supplied.get("context") or "production"
    review = verify_signoff_set(spec, records, context=ctx)
    ...
    can_mark_fixed = all(prerequisites.values())   # 未检查 production_admissible
```

两个问题叠加：

1. `ctx` 完全由**外部调用者**（参数或 `spec["manual_review"]["context"]`）决定。
2. `can_mark_fixed` 只看 `all_items_approved` 与 `binding_valid`，**没有**检查 `signoff_integrity.production_admissible`。

因此 `context="unit_test"` + 模拟审核人时，`validate_signoff_record()` 不会拒绝 synthetic 记录，三项都通过，函数会输出 **`fix_result="FIXED"`** —— 一个不可用于生产的签核被当成了生产判定。虽然 `append_production_signoff()` 硬编码了 production，但 `evaluate_subtitle_fix()` 本身的 `FIXED` 结论仍可被误用。

### 2.2 修复实现

| 机制 | 实现 |
|---|---|
| 内部常量 | `PRODUCTION_CONTEXT = "production"`、`UNIT_TEST_CONTEXT = "unit_test"`、`CONTEXT_SOURCE = "internal_constant"` |
| 生产入口 | `evaluate_subtitle_fix(spec, context=None)` 内部**固定** `context=PRODUCTION_CONTEXT`；传入非 production 参数直接抛 `SignoffError`；`spec["manual_review"]["context"]` 一律忽略并记录进 `context_policy.caller_context_attempted_but_ignored` 供审计 |
| 硬门槛 | `FIXED` 前置条件由 7 项增至 **11 项**，新增 `font_size_named_human_confirmation`、`production_context_is_internal_constant`、`production_signoff_admissible`、`no_synthetic_reviewers_in_signoff` |
| 隔离测试入口 | 新增 `evaluate_subtitle_fix_unit_test(spec)`：允许观察模拟审核人，但 `fix_result` **恒为** `TEST_ONLY_OBSERVATION`，`can_mark_fixed=False`，`admissible_for_production=False` |
| 低层校验器 | `verify_signoff_set(spec, records, context=...)` 保留可传 context，仅供单元测试与对比复现，**不是**生产判定入口 |
| 缺陷复现 | 新增 `legacy_wb004_context_gate()`，明确标注 `DEFECTIVE ... evidence only`，用于修复前后对比 |

### 2.3 修复前后对比（同一输入）

输入：`spec.manual_review.context = "unit_test"`，3 个 `MOCK_UNIT_REVIEWER`（`test_only=True`, `review_source=unit_test`），其余条件完全相同。

| | Round-1 门 | Round-2 生产入口 |
|---|---|---|
| 有效 context | `unit_test`（外部传入） | `production`（`internal_constant`） |
| `fix_result` | **`FIXED`** ❌ | **`NEEDS_MANUAL_REVIEW`** ✅ |
| `all_items_approved` | `true` | `false` |
| `production_admissible` | `false` | `false` |
| synthetic 记录 | 3 条被放行 | 3 条被拒 |
| 调用者显式传 `context="unit_test"` | 被接受并放行 | 抛 `SignoffError` |
| 隔离测试 harness | 不存在 | `TEST_ONLY_OBSERVATION`，`admissible_for_production=false` |

证据：`evidence/round2/context-fix-before-after.json`（含完整对象与错误信息原文）。

### 2.4 新增 context 用例（10 条，全部通过）

`caller_supplied_unit_test_context_refused` · `spec_unit_test_context_cannot_produce_fixed` · `production_context_source_is_internal_constant` · `production_admissible_is_fixed_prerequisite` · `unit_test_approval_does_not_unlock_production` · `test_harness_never_emits_production_fixed` · `test_harness_allows_synthetic_for_observation_only` · `test_harness_signoff_refused_by_production_ledger` · `round1_context_gate_reproduces_defect` · `round2_gate_refuses_what_round1_allowed`

自动结果与人工结果仍是两个独立数据结构；模拟审核人仍被 `append_production_signoff()` 拒绝写入生产台账。

---

## 3. 事项 2：字号措辞与生产人工复核

### 3.1 历史措辞更正声明（**原文不改写**）

以下 round-1 表述曾暗示「真实/精确字号测量」，现统一更正为**「像素高度估算」**。按复核要求**不覆盖历史报告**，仅在此逐条声明：

| 文件与位置 | Round-1 原文 | 更正后的准确表述 |
|---|---|---|
| `subtitle-signoff-fix.md:88` | `font_size_frame_measured_pass` — **帧内实测字号**通过 | `font_pixel_height_estimate_threshold_pass` — **像素高度估算阈值**通过 |
| `subtitle-signoff-fix.md:129` | 实际画面测量字号 / `font_px_measured` / 唯一可产生自动 PASS 的来源 | 画面差分**像素高度估算** / `font_px_pixel_height_estimate`；仅为阈值判定，且**不能单独**产生生产 `FIXED` |
| `blockers.md:33` | 帧内实测 `font_px_measured ≥ 32` | 像素高度估算 ≥ 32 **且**具名人工字号确认通过 |
| `subtitle-signoff-tests.json`（历史快照） | `font_size_frame_measured_pass`；limitations 中 "Frame-measured font size is an estimated glyph height" | 保留为 round-1 快照；准确口径见本 addendum 与 round-2 结果文件 |
| `status/pipeline-status.json`（见 §6.3） | `font_size_frame_measured_pass` / capability id `font_three_states_and_frame_measurement` / "frame-measured 26 px" | 已更新为 `font_pixel_height_estimate_threshold_pass` 与 pixel-height-estimate 口径 |

### 3.2 源码实现改动

| 项 | Round-2 |
|---|---|
| 方法名 | `pixel_height_estimate_from_frame_difference_mask`（原 `longest_changed_row_run_in_difference_mask`） |
| 主字段 | `font_px_pixel_height_estimate`；`font_px_measured` 降级为 **DEPRECATED 兼容别名** |
| 显式否定 | `is_precise_font_size_measurement: False`、`measurement_confidence: pixel_height_estimate__not_a_font_size_measurement`、docstring 与 `measurement_note` 明确写 "NOT a precise font-size measurement" |
| 判定范围 | `verdict_scope: pixel_height_estimate_threshold_only` |
| 人工复核 | `production_font_size_human_review: NEEDS_MANUAL_REVIEW`、`human_confirmation_required_in_production: True`、`font_px_human_confirmed` 不由自动流程填充 |
| 新增前置条件 | `validate_font_human_confirmation(spec)`：必须具名审核人、合法时间、实质证据、`verdict=APPROVED`，且 `frame_ref / video_version / subtitle_version` 与 spec 绑定；拒绝模拟审核人、空值、错版本。**缺此项则生产 `FIXED` 不可达** |

自动检测与人工复核继续分开记录：`automatic.checks.font_size`（估算）+ `font_size_human_review`（人工）是两个独立结构。

### 3.3 新增 font 用例（5 条，全部通过）

`font_is_pixel_height_estimate_not_font_size_measurement` · `font_size_human_confirmation_required_for_fixed` · `font_confirmation_mock_reviewer_rejected` · `font_confirmation_wrong_video_version_rejected` · `production_font_size_human_review_retained`

证据：`evidence/round2/font-wording-audit.json`（含源码 SHA-256 与 6 项措辞断言）。

> **行为变化如实记录**：新增字号人工确认后，生产 `FIXED` 门槛由 7 项收紧为 11 项。round-1 的 `subtitle-signoff-tests.json` 是历史快照（26 项、原门槛），本轮 `subtitle-signoff-tests-round2.json` 是 41 项、新门槛；两者都保留，未互相覆盖。

---

## 4. 事项 3：时间戳异常核实

### 4.1 复核方提出的疑点

会话文本给出「当前会话时间 2026-11-08 16:34 +0800」，而报告写「16:46:36 测试、17:06 结束」，最终提交换算约 17:28 —— 看起来像报告记录了「未来时间」。

### 4.2 六类真实证据（全部可复算）

证据文件：`evidence/round2/timestamp-audit.json`。

| 类别 | 实测结果 |
|---|---|
| Windows 时区 | `China Standard Time`，`(UTC+08:00)`，`BaseUtcOffset=8h`，`SupportsDaylightSavingTime=false`，当前非夏令时；W32Time `Type=NTP`，`NtpServer=time.windows.com,0x9` |
| 多源本机时钟 | PowerShell `Get-Date 2026-11-08T17:43:57+08:00` / UTC `09:43:57Z`；Git Bash `date` `17:43:45+0800`；Python `datetime.now()` `17:43:45`、`time.time()` `1794131025`、`tzname=('中国标准时间','中国夏令时')`、`time.timezone=-28800`；`git var GIT_COMMITTER_IDENT` 与平台注入的会话时钟同样落在 17:42–17:44 +0800 |
| Git 原始提交对象 | `8c26116`：`committer ... 1794130093 +0800` → `2026-11-08T17:28:13+08:00` = UTC `09:28:13`；`a5659e3`：`1794129663 +0800` → `17:21:03+0800`；`%aI == %cI == 原始 epoch 换算值`，author = committer |
| 时间来源 | Git 自身在提交时用 OS 系统时钟打戳，原始对象存 `<unix-epoch> <+0800>`。`GIT_AUTHOR_DATE_present=false`、`GIT_COMMITTER_DATE_present=false`；无 `--date` 覆盖、无 `amend`、无历史改写、无 force-push |
| 报告声明窗口 | `report.md:8` = `2026-11-08 16:30 / 17:06 +0800`；`pipeline-status.json` 的 `started_at=16:30:00`、`ended_at=17:06:00`。二者均为**人工撰写时的估计窗口**，不是机器时间戳 |
| `captured_at` 与文件 mtime | `subtitle-signoff-tests.json` `16:46:36+08:00` vs mtime `16:46:36`（差 −0.9 s）；`signoff_before_after.json` 同为 `16:46:36`（−0.9 s）；`github_repo_probe.json` `16:41:40`（−1.0 s）；`tts_probe_004.json` `16:51:20`（−1.1 s）；`secret_scan_004.json` `17:08:20`（−0.5 s）；`vidova_deeplink_research.json` `16:53:47`（−1.8 s）。全部为「先取时间、再写文件」的正常 1–2 秒差 |

### 4.3 真实时间线（+0800）

| 时刻 | 事件 | 来源 |
|---|---|---|
| 16:30 | 报告头部人工填写的开始时间 | `report.md:8`（估计值） |
| 16:41:40 | 最早机器证据 `github_repo_probe.json` | captured_at = mtime |
| 16:43:28 / 16:46:22 | `subtitle_checks.py` / `run_signoff_tests.py` mtime | 文件系统 |
| **16:46:36** | **26 项测试产出 `subtitle-signoff-tests.json`** | captured_at = mtime |
| 16:49:55 – 16:53:47 | 补查、TTS、Vidova 证据 | 各 evidence JSON |
| 16:54:51 – 17:03:30 | 各规范文档 mtime | 文件系统 |
| **17:06** | **报告头部人工填写的结束时间** | `report.md:8`（**低估**） |
| 17:08:20 | 最终敏感扫描 `secret_scan_004.json` | captured_at |
| **17:21:03** | **主体交付 commit `a5659e3`** | Git 原始对象 `1794129663 +0800` |
| 17:27:24 | `report.md` 补记编辑 mtime | 文件系统（属补记 commit） |
| **17:28:13** | **补记 commit `8c26116` / 最终远端 HEAD** | Git 原始对象 `1794130093 +0800` = UTC 09:28:13 → +0800 17:28:13 |
| 17:47:37 | 本轮时间取证 `timestamp-audit.json` | `datetime.now().astimezone()` |

### 4.4 结论：**无系统时钟偏差，无伪造时间，无回填**

差异由三个独立原因完整解释，**没有任何一个是时钟被改动或时间被回填**：

1. **人工估计窗口低估**：`16:30 / 17:06` 是写在散文与状态元数据里的估计值，实际机器证据一直延续到 `17:08:20`，主体提交 `17:21:03`、补记提交 `17:28:13`。报告声明的「结束」比真实最终提交早约 **22 分钟**。这是**记录精度问题**，不是时间造假。
2. **会话时钟是另一个时钟源**：`16:34` 出自审核方/会话文本，不是本机系统时钟。本机在该时段已有 16:41–16:46 的机器证据；不存在「本机时间倒退」或「写入未来时间」。本机无法验证外部时钟的绝对正确性，但本机时间链完全自洽。
3. **round-1 脚本硬编码 `+08:00`**：所有 probe 用 `datetime.now(timezone(timedelta(hours=8)))`，**未读取系统时区**。本机时区确为 UTC+08:00 且无 DST，因此数值正确（`captured_at` 与 mtime 逐项吻合即为证明），但这仍是实现缺陷。本轮新增证据已改用 `datetime.now().astimezone()`。

补充：`17:28` 可由 Git 原始对象 `1794130093 +0800` 或 UTC `09:28:13` 换算得到，与本机时钟一致；「换算后约 17:28」本身是**正确换算**，不构成异常。

**按要求处理**：未伪造或回填任何时间；未覆盖、未改写任何历史报告；本 addendum 是唯一解释该差异的新增文件。若后续仍希望把 `report.md:8` 的估计窗口改成机器时间，应在**新任务**中作为新 addendum 处理，而不是原地修改历史。

---

## 5. 全量验证

| 项 | 结果 |
|---|---|
| 自动化测试 | **41/41 通过**（26 项 round-1 回归 + 15 项 round-2 新增），退出码 0，`subtitle-signoff-tests-round2.json` |
| Python 编译 | `subtitle_checks.py`、`run_signoff_tests.py` `py_compile` 通过 |
| JSON 校验 | 整个 `docs/ai-collaboration/` 共 **32 个 JSON 全部解析通过**，0 非法 |
| 修复前后对比 | `evidence/round2/context-fix-before-after.json`（round-1 `FIXED` → round-2 `NEEDS_MANUAL_REVIEW`） |
| 时间取证 | `evidence/round2/timestamp-audit.json`，6 条结论、逐文件 mtime 对照、6 个 commit 原始 epoch |
| 证据哈希 | `evidence/round2/manifest.sha256.json`（对 round-2 目录内除清单自身外的 **6 个**证据文件计算 bytes + SHA-256） |
| 敏感扫描 | 本轮新增/修改的 **10 个**文本文件，**0 命中**（凭据前缀 / 私钥 / token 值 / 本机绝对路径），`evidence/round2/secret_scan_round2.json` 可复算 |
| 未改动用户工程 | 两个现有剪映草稿 SHA-256 前缀仍为 `75e07786574bf6d9` / `0792b2c4e809a6b6`，与 WB-VIDEO-004 一致；Vidova 项目、原素材均只读核对，未写入 |
| 红线 | 0 付费 / 0 额度 / 0 依赖安装 / 0 模型下载 / 0 GUI 自动化 / 0 公开发布 / 0 明文凭据读取 |

---

## 6. 文件清单与「不覆盖历史」核对

### 6.1 新增文件（全部在 `WB-VIDEO-004/` 内）

| 文件 | 说明 |
|---|---|
| `addendum-round2.md` | 本文件 |
| `subtitle-signoff-tests-round2.json` | 41 项完整结果（round 2） |
| `wb005-preparation.md` | WB-VIDEO-005 **待批准草案**，本轮不执行 |
| `evidence/round2/timestamp-audit.json` | 时间戳取证 |
| `evidence/round2/context-fix-before-after.json` | context 修复前后对比 |
| `evidence/round2/font-wording-audit.json` | 字号措辞断言 + 源码 SHA-256 |
| `evidence/round2/signoff_before_after.json` | round-2 重跑的 WB-VIDEO-003 旧门对比（独立目录，不覆盖历史） |
| `evidence/round2/signoff_sample_contact_sheet.jpg` | round-2 重跑的测试帧拼图（独立目录） |
| `evidence/round2/secret_scan_round2.json` | 本轮敏感信息扫描结果（0 命中） |
| `evidence/round2/manifest.sha256.json` | round-2 证据哈希清单 |

### 6.2 修改的既有源码（P0 修复所必需）

- `subtitle_checks.py` — context 固定、字号像素高度估算措辞、具名人工字号确认、`FIXED` 11 项前置条件、隔离测试 harness、round-1 缺陷复现函数。
- `run_signoff_tests.py` — 增加 `--out` / `--evidence-dir`（round-2 输出走独立路径）、`FONT_REVIEW` 具名人工确认样例、#18 断言更新、15 条新增用例、round-2 证据输出。

### 6.3 更新的既有状态文件

`status/pipeline-status.json` 是唯一被更新的**机器可读状态文件**（`schema_version 1.3 → 1.4`），改动逐条：

- 新增 `review_round2` 段：三项结论、41/41 测试、15 条新增用例、context 修复前后、字号口径更正、时间取证结论、本轮红线。
- `p0_signoff_fix.fix_prerequisites` 由 7 项更新为 11 项（新增字号人工确认与 production 门禁）。
- `p0_signoff_fix.additional_qa_fixes.font_size`、`capabilities` 中字号条目的措辞改为「像素高度估算 + 具名人工确认」。
- `test_results` 增加 `round2` 子对象，保留 round-1 的 26 项快照记录不变。
- `quota_and_cost` 增加本轮 0 消耗的显式字段。
- **保留** `final_verdict = "B_CONDITIONAL_PASS"`、`defects`、`approval_batch_for_next_stage`、`next_task` 原值。

### 6.4 明确未改动的历史文件（mtime 复核）

| 文件 | mtime（+0800） |
|---|---|
| `report.md` | 2026-11-08T17:27:24 |
| `subtitle-signoff-tests.json` | 2026-11-08T16:46:36 |
| `evidence/signoff_before_after.json` | 2026-11-08T16:46:36 |
| `evidence/signoff_sample_contact_sheet.jpg` | 2026-11-08T16:46:36 |
| `subtitle-signoff-fix.md` | 2026-11-08T16:54:51 |
| `github-project-research.md` | 2026-11-08T16:56:26 |
| `blockers.md` | 2026-11-08T17:03:30 |
| `evidence/manifest.sha256.json` 及其余 round-1 证据 | 保持原状 |

---

## 7. 对最终结论的影响与停止条件

- WB-VIDEO-004 的最终结论**不变**：`B · CONDITIONAL PASS`。本轮只补强质检签核与证据可信度，不产生任何新的「真实素材生成 / 剪映导入导出 / 中文配音 / 独立草稿」证据，因此**仍不具备正式宣传片制作准入条件**。
- D004 仍为 `STILL_FAILING`；D005 仍为测试占位素材、`OPEN / REVIEW_REQUIRED`；第 3 轮返工仍未批准。
- **本轮到此停止**。WB-VIDEO-005 仅有 `wb005-preparation.md` 草案，等待用户明确批准后才可执行；批准前不会消耗 Vidova 额度、不会安装依赖、不会下载模型、不会操作剪映 GUI。
- 提醒：此前明文出现过的 GitHub 凭据应撤销并轮换，继续只使用系统受保护凭据存储。

---

## 8. 提交与 GitHub 链接

| 项 | 值 |
|---|---|
| 基准提交 | `8c261166253fbfc1f5d52669eca1277a0d776661` |
| **主体交付 commit** | **`3fd5e99e000bb638561af1d8c1632717238f4db3`**（13 文件，2,563 行新增 / 78 行删除） |
| 主体推送 | `8c26116..3fd5e99  main -> main`，退出码 0，`ls-remote origin refs/heads/main` 已核对一致 |
| 推送方式 | `git -c credential.helper= -c credential.helper=wincred` + `GIT_TERMINAL_PROMPT=0` + 本机代理；Windows 系统受保护凭据。**未读取/打印/提交明文凭据**，无 force-push |
| 补记 commit / 最终远端 HEAD | 见本轮会话最终回报；补记提交自身的 SHA 无法写入它自己的内容中（自引用不可能），本文件不虚构该值 |

主要链接（仓库 `swdscsc/yaodao-agent`，分支 `main`）：

- [本 addendum](https://github.com/swdscsc/yaodao-agent/blob/main/docs/ai-collaboration/outbox/WB-VIDEO-004/addendum-round2.md)
- [41 项 round-2 测试结果](https://github.com/swdscsc/yaodao-agent/blob/main/docs/ai-collaboration/outbox/WB-VIDEO-004/subtitle-signoff-tests-round2.json)
- [时间戳取证](https://github.com/swdscsc/yaodao-agent/blob/main/docs/ai-collaboration/outbox/WB-VIDEO-004/evidence/round2/timestamp-audit.json)
- [context 修复前后对比](https://github.com/swdscsc/yaodao-agent/blob/main/docs/ai-collaboration/outbox/WB-VIDEO-004/evidence/round2/context-fix-before-after.json)
- [字号措辞审计](https://github.com/swdscsc/yaodao-agent/blob/main/docs/ai-collaboration/outbox/WB-VIDEO-004/evidence/round2/font-wording-audit.json)
- [round-2 证据哈希清单](https://github.com/swdscsc/yaodao-agent/blob/main/docs/ai-collaboration/outbox/WB-VIDEO-004/evidence/round2/manifest.sha256.json)
- [WB-VIDEO-005 待批准草案](https://github.com/swdscsc/yaodao-agent/blob/main/docs/ai-collaboration/outbox/WB-VIDEO-004/wb005-preparation.md)
- [修复后的 subtitle_checks.py](https://github.com/swdscsc/yaodao-agent/blob/main/docs/ai-collaboration/outbox/WB-VIDEO-004/subtitle_checks.py)
- [机器状态文件](https://github.com/swdscsc/yaodao-agent/blob/main/docs/ai-collaboration/status/pipeline-status.json)
- [主体交付提交](https://github.com/swdscsc/yaodao-agent/commit/3fd5e99e000bb638561af1d8c1632717238f4db3)
