# WB-VIDEO-004 · P0 字幕人工签核机制修复报告

| 项 | 值 |
|---|---|
| Task ID | WB-VIDEO-004 / P0 |
| 修复对象 | `outbox/WB-VIDEO-003/subtitle_checks.py::evaluate_subtitle_fix()` |
| 修复后源码 | `outbox/WB-VIDEO-004/subtitle_checks.py`（**不修改 003 文件，保留为修复前证据**） |
| 测试源码 | `outbox/WB-VIDEO-004/run_signoff_tests.py` |
| 测试结果 | `subtitle-signoff-tests.json` — **26 / 26 PASS，退出码 0** |
| 对比证据 | `evidence/signoff_before_after.json`、`evidence/signoff_sample_contact_sheet.jpg` |
| 状态 | **FIXED**（机制层面）；历史缺陷 D004 仍 `STILL_FAILING`，本轮**未伪造任何人工审核** |

---

## 1. 缺陷复现（修复前）

ChatGPT 审核指出的问题真实存在。`WB-VIDEO-003/subtitle_checks.py` 第 319–320 行：

```python
review = spec.get("manual_review") or {}
signed = bool(review.get("verdict") == "APPROVED" and review.get("reviewer")
              and review.get("evidence"))
```

只要一个**顶层** `{verdict: "APPROVED", reviewer: ..., evidence: ...}` 对象，就把整条字幕缺陷判为已签核。三个 `MANUAL_ITEMS`：

- `text_content_matches_srt`
- `semantic_readability`
- `occlusion_by_undeclared_content`

**从未被逐项检查**；`evidence` 可以是 `looks good` 这类占位词；没有审核时间、没有帧/时间段/版本绑定；没有防模拟审核人机制。

修复前后同输入对比（`evidence/signoff_before_after.json`）：

| 输入 | WB-VIDEO-003 门 | WB-VIDEO-004 门 |
|---|---|---|
| `{"verdict":"APPROVED","reviewer":"QA_LEAD_AAA","evidence":"looks good"}` | `signed_off = true` | `approved_items = []`，3 项全部 `NOT_REVIEWED`，`verdict = NOT_PERFORMED`，**拒绝 FIXED** |

---

## 2. 修复后的逐项签核数据结构

`MANUAL_ITEMS` 每一项必须提供**独立记录**，字段如下（建议结构 + 本轮强制的绑定字段）：

| 字段 | 要求 | 校验 |
|---|---|---|
| `reviewer` | 具名审核人，去空格后非空、长度 ≥3 | 拒绝空值 / `auto` / `system` / `anonymous` / 任何含 `test_`/`mock`/`simulat`/`dummy`/`fake` 的名字 |
| `reviewed_at` | 带时区的 ISO-8601 | 拒绝缺字段、非法格式、无时区、未来时间、早于 2020 年 |
| `item_id` | 必须是 3 个 `MANUAL_ITEMS` 之一 | 拒绝未知 / 缺失 / 重复 |
| `verdict` | 必须是 `APPROVED` | `REJECTED` / `NEEDS_MANUAL_REVIEW` 一律不通过 |
| `evidence` | 实质审核证据（字符串或含 `observation` 的对象） | 拒绝空值、<12 字符、`ok`/`pass`/`approved`/`looks good` 等占位词 |
| `notes` | 必须存在（可为空串） | 缺字段即无效 |
| `frame_ref` | 审核的**哪一帧** | 必须等于 spec 的 `frame_id` |
| `time_range` | 审核的**哪个时间段** `[start,end]` | 数值递增，且必须落在 spec 的 `review_time_range` 内 |
| `video_version` | 审核的**哪个视频版本** | 必须严格等于 spec 的 `video_version` |
| `subtitle_version` | 审核的**哪个字幕版本** | 必须严格等于 spec 的 `subtitle_version`（如 SRT 的 sha256 前缀） |

输出结构（`verify_signoff_set()`）：

```json
{
  "policy": "per_item_signoff_v1",
  "context": "production | unit_test",
  "items": { "<item_id>": { "verdict": "APPROVED|REJECTED|NOT_REVIEWED|INVALID",
                            "valid": true, "errors": [], "synthetic": false,
                            "binding": {}, "reviewer": "...", "reviewed_at": "...",
                            "evidence": "...", "notes": "...",
                            "record_sha256": "...", "independent_status": true } },
  "approved_items": [], "missing_or_invalid_items": [],
  "all_items_approved": false, "verdict": "APPROVED|REJECTED|NOT_PERFORMED",
  "signoff_integrity": { "signoff_hash": "...", "binding_valid": false,
                         "synthetic_records": 0, "production_admissible": false,
                         "automatic_and_manual_recorded_separately": true }
}
```

**自动与人工两个独立数据结构**：`report["automatic"]` 只含自动检查（含 `checks / failures / needs_review`），`report["manual_review"]` 只含人工逐项记录；两者互不嵌套，测试 `automatic_and_manual_structures_separate` 显式断言。

---

## 3. 决策规则（只有全部满足才允许 `FIXED`）

`evaluate_subtitle_fix()` 的 7 个先决条件（`prerequisites` 全为 `true`）：

1. `no_automatic_failure` — 自动检查无 FAIL；
2. `burned_in_pixel_proof` — 与无字幕参考帧存在真实像素差；
3. `render_produced` — 有渲染产出（仅证据，`decision_weight = 0`）；
4. `font_size_frame_measured_pass` — **帧内实测字号**通过，不接受渲染参数；
5. `text_contrast_measured_pass` — **文字/邻近背景实测对比度**通过；
6. `all_three_manual_items_individually_approved` — 3 项逐项独立 APPROVED；
7. `signoff_binding_valid` — 帧 / 时间段 / 视频版本 / 字幕版本绑定全部匹配。

结果枚举：

| 情形 | `fix_result` |
|---|---|
| 自动检查 FAIL | `STILL_FAILING`（**人工 APPROVED 不能覆盖自动 FAIL**） |
| 自动 PASS、人工未审核 / 不完整 / 无效 | `NEEDS_MANUAL_REVIEW`（**自动 PASS ≠ 人工 PASS**） |
| 全部满足 | `FIXED` |

生产台账 `append_production_signoff()` 会再次以 `context="production"` 校验；模拟审核人被拒时抛 `SignoffError`，**不写入任何生产签核记录**。

---

## 4. 防伪造与测试隔离

| 风险 | 防护 |
|---|---|
| 伪造默认 APPROVED | 顶层全局对象被识别为 `extraneous_records`，3 项全部 `NOT_REVIEWED` |
| 空审核人 / 空证据 / 占位证据 | 逐字段 fail-closed 校验 |
| 审核记录引用错误视频版本 / 字幕版本 / 帧 / 时间段 | 与 spec 锚点严格比对，任一不符即该项 `REJECTED` |
| 测试模拟审核人混入真实生产签核 | `test_only` 标记、`review_source`、`reviewer` 关键词三重识别；`production` 上下文一律拒绝；`unit_test` 上下文允许但 `production_admissible` 恒为 `false` |
| 重复记录 / 未知 item | 拒绝 |
| 审核记录被事后篡改 | 每条 `record_sha256` + 整体 `signoff_hash` |

本轮测试中的全部审核人姓名均为**合成测试数据**，测试只写到本机临时目录，仓库内**没有产生任何生产签核台账**；D004 的三项人工复核状态仍是 `NOT_PERFORMED`。

---

## 5. 额外改进：三项"假准确率"问题

### 5.1 字号检测不再只读取渲染参数

WB-VIDEO-003 用 `spec["font_px"]`（渲染参数）直接判 PASS。现在明确区分三态：

| 状态 | 字段 | 决策权重 |
|---|---|---|
| 渲染参数字号 | `font_px_render_param` | **0**（仅记录，可计算与实测的差异百分比） |
| 实际画面测量字号 | `font_px_measured` | 唯一可产生自动 PASS 的来源 |
| 人工确认字号 | `font_px_human_confirmed` | 仅由真实生产签核记录填充；本轮恒为 `null` |

实测方法：字幕帧与无字幕参考帧的像素差掩膜 → 最长连续变化行组高度，作为**字形高度估计**。实测证据：`font_three_states_recorded_separately` 用例中渲染参数 36 px、帧内实测 26 px（差异 27.8%），三态分别存储。当无参考帧、无法实测时，`font_size.verdict = NEEDS_MANUAL_REVIEW`，渲染参数不会顶替（`font_size_render_param_only_not_pass` 用例）。

> 诚实边界：这是字形高度估计，不是经过认证的字体度量；`measurement_confidence = estimate_glyph_height_not_font_size_truth`。

### 5.2 对比度真正测量文字与背景

WB-VIDEO-003 用整个字幕带的 `p95 - p5` 灰度分布，会被背景纹理、装饰条、边框污染。现在：

- 用帧差掩膜提取**文字像素**（`>10` 灰阶差）；
- 对掩膜做 5×5 膨胀，取**紧邻文字的环形背景像素**；
- 分别取中位亮度，按 sRGB 相对亮度近似计算 WCAG 风格对比度 `(Lmax+0.05)/(Lmin+0.05)` 与绝对亮度差；
- 阈值 `contrast_ratio ≥ 4.5` 且 `abs_luma_delta ≥ 45`；像素不足时 `NEEDS_MANUAL_REVIEW`；
- 旧的 band spread 降级为 `band_spread_diagnostic_only`，`band_spread_used_for_verdict = false`。

实测证据：

| 用例 | band spread（旧指标） | 文字/背景对比（新指标） | 新判定 |
|---|---|---|---|
| 低对比文字 + 高对比装饰条 | **145.0**（旧逻辑会 PASS） | ratio `1.177`、Δ`11.0`、文字亮度 112 / 背景 101 | **FAIL** |
| 白字 + 深底 | 215.0 | ratio `13.881`、Δ`207.0`、文字亮度 245 / 背景 38 | **PASS** |

> 诚实边界：`measurement_confidence = estimate_srgb_gray_proxy_not_certified_wcag`，彩色字幕与复杂背景仍需人工复核。

### 5.3 主体遮挡不再只看 IoU

WB-VIDEO-003 用 `max_iou > 0.02`。当字幕带很大、遮挡物很小时，IoU 趋近 0 会漏检。现在同时报告 IoU、`intersection_over_subject`、`intersection_over_subtitle`、包含关系，任一覆盖率 ≥0.05 即 FAIL。

实测证据（`small_occluder_iou_miss_detected`）：字幕带 `[40,288,560,46]`，遮挡物 `[300,300,8,8]` 完全落在带内。

| 指标 | 值 | 旧逻辑 | 新逻辑 |
|---|---|---|---|
| IoU | 0.0025 | PASS（漏检） | 记录 |
| intersection / subject | **1.0** | 未计算 | **FAIL** |
| `legacy_iou_would_pass` | true | — | 显式记录以证明漏检被修复 |

> 诚实边界：只覆盖**已声明**的 subject/UI 框；未声明内容遮挡仍是人工项 `occlusion_by_undeclared_content`，本轮未伪装成自动可判。

---

## 6. 测试覆盖（26 项，全部通过）

任务书要求的 10 项，全部有独立用例：

| # | 任务书要求 | 用例 | 结果 |
|---|---|---|---|
| 1 | 三项全部审核通过 | `all_three_items_approved` | `FIXED`，7 个先决条件全 true |
| 2 | 只有一项审核通过 | `only_one_item_approved` | 2 项缺失，拒绝 FIXED |
| 3 | 有一项未审核 | `one_item_not_reviewed` | `NOT_REVIEWED` 阻断 |
| 4 | 审核人为空 | `empty_reviewer_rejected` | 拒绝 |
| 5 | 证据为空 | `empty_evidence_rejected` | 拒绝 |
| 6 | 错误视频版本 | `wrong_video_version_rejected` | 绑定失败 |
| 7 | 错误字幕版本 | `wrong_subtitle_version_rejected` | 绑定失败 |
| 8 | 自动 FAIL 但人工 APPROVED | `auto_fail_but_human_approved` | `STILL_FAILING` |
| 9 | 自动 PASS 但人工未审核 | `auto_pass_but_human_not_reviewed` | `NEEDS_MANUAL_REVIEW` |
| 10 | 模拟审核人不能冒充真实审核 | `synthetic_reviewer_cannot_impersonate_production` | 3 项全部拒绝 + 生产台账写入被拒 |

额外 16 项：旧全局 APPROVED 对象、未来时间戳、错误帧引用、时间段越界、重复记录、人工 REJECTED、字号仅渲染参数、字号三态、对比度两种方向、小遮挡 IoU 漏检、自动/人工分离、逐项独立哈希、unit_test 隔离、SRT 存在但画面无字幕、生产台账接受合法签核。

分组统计：`P0_signoff` 15 项、`font` 2 项、`contrast` 2 项、`occlusion` 1 项、`regression` 1 项，合计 26 项（详见 `subtitle-signoff-tests.json`）。

---

## 7. 与 D004 / D005 的关系

- **D004**：竖屏字幕中心 0.6208 H、字号 26 px < 32 px、横屏底边 0.947 H 超安全线 → 仍 `STILL_FAILING`。本轮修复的是**判定与签核机制**，不是字幕画面本身；未批准第 3 轮自动返工（返工 2/2 用尽）。竖屏原生重排方案见 `blockers.md`。
- **D005**：历史参考渲染 5.5–8.5 s 是 `smptebars` 静态彩条**测试占位素材**，不是真实镜头；后续真实镜头需重新生成并重新质检。
- 本轮**没有**把任何测试素材冒充真实素材，也没有把任何合成测试帧冒充正式成片。

## 8. 已知局限

- 帧内字号 / 对比度是像素级估计，不是认证测量；不足像素时返回 `NEEDS_MANUAL_REVIEW`，不猜测。
- 未声明主体/UI 的遮挡、文字内容是否与 SRT 一致（需 OCR）、语义可读性，仍全部保留人工项。
- 26 项测试证明的是**门控逻辑**正确，不证明任何真实字幕缺陷已被修复。
- 所有测试审核人均是合成数据；真实生产签核需要具名真人逐项填写，本轮无此记录。
