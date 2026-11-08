# WB-VIDEO-003 · P0 质检漏洞修复记录

| 项 | 值 |
|---|---|
| 基准提交 | `08ffda5199cffccf762e810f139ab8bf1522fe2b`（远端 `main`） |
| 测试时间 | 2026-11-08 15:50–16:00 +0800 |
| 修复策略 | **WB-VIDEO-002 原文件保持不动，作为「修复前」证据**；修复版全部放在 `outbox/WB-VIDEO-003/` |
| 自动化结果 | **17 / 17 全部通过**（`test-results.json`），退出码 0 |
| 付费/额度调用 | 0；全部测试媒体由本机 FFmpeg / PIL 生成 |

---

## 1. P0-1：全片冻结检测豁免

### 1.1 漏洞定位（真实代码）

`outbox/WB-VIDEO-002/qa.py:206-267`

```python
def qa_media(..., static_material_expected: bool = False) -> dict:
    ...
    freeze_is_defect = freeze["detected"] and not static_material_expected
    ...
    "frozen_frame": ("PASS" if not freeze["detected"]
                     else ("EXPECTED_STATIC" if static_material_expected else "FAIL")),
```

`outbox/WB-VIDEO-002/rework.py:222-224` 在**最终成片**上调用：

```python
r = qa_media(..., expect=expect, static_material_expected=True)
```

即一个布尔量把整条视频（12.036 s，含 3 段动态素材）的冻结检测全部关掉。任何真实动态镜头冻结都会被判 `EXPECTED_STATIC` / PASS。

### 1.2 修复（`WB-VIDEO-003/qa.py`）

1. **删除全局豁免参数**。`qa_media` 不再接受 `static_material_expected`；若旧代码传入，抛出 `ValueError`（测试中 `legacy_global_exemption_is_removed`）。
2. **改为明确时间区间白名单** `static_intervals=[{"start","end","reason"}]`。
3. **白名单 fail-closed 校验** `validate_static_whitelist()`：
   - `0 <= start < end`；
   - `end <= 媒体时长 + 0.05 s`（越界报 `OUT_OF_RANGE`）；
   - 必须带 `reason`（只允许**已确认的静态区间**）；
   - 区间不得重叠；
   - 总覆盖率不得超过视频时长的 **50%**，防止白名单变相变成全片豁免；
   - 媒体时长未知时直接判错，不做任何豁免。
4. **逐区间判定** `evaluate_freeze()`：每条 `freeze_start/end` 区间单独与白名单比对；只有**完全**落入某个白名单区间才 `ALLOWED_STATIC`；否则 `FAIL` + `needs_manual_review=True` + 具体原因。白名单校验失败时**所有区间一律不豁免**。
5. `static_intervals=None`（默认）时，动态素材任何冻结都 → FAIL。
6. 结果中完整保留 `raw_intervals`、`evaluated_intervals`、`whitelist_errors`、`whitelist_coverage_ratio`。

`WB-VIDEO-003/rework.py` 的最终成片 QA 改为：

```python
FINAL_TIMELINE_STATIC_INTERVALS = [
    {"start": 0.0,  "end": 1.5,  "reason": "confirmed static intro title card"},
    {"start": 4.5,  "end": 5.5,  "reason": "confirmed static chapter card"},
    {"start": 10.5, "end": 12.0, "reason": "confirmed static outro card"},
]
```

来源为 WB-VIDEO-002 真实 concat 时间线（片头 1.5 / S001 3.0 / 章节卡 1.0 / S002 3.0 / S003 2.0 / 片尾 1.5）。**S002 是静态彩条素材，不是卡片，故意不加入白名单** —— 它是被冻结的动态镜头，必须报错。

### 1.3 测试证据（P0-1 共 8 项，全部通过）

| # | 用例 | 实际结果 |
|---|---|---|
| 1 | 正常动态视频（`testsrc2` 4 s） | `PASS / frozen_frame=PASS`，无冻结区间 |
| 2 | 动态视频中间冻结（`freezeframes first=45 last=105`） | `FAIL`，区间 **1.500–3.533 s**，`frozen_frames_outside_whitelist` |
| 3 | 合法静态片头 + 白名单 `[0,1.5]` | `PASS_ALLOWED_STATIC / verdict=PASS`，覆盖率 30% |
| 4 | 静态片头之后动态镜头冻结 + 同一白名单 | `FAIL`，1 个区间在白名单外，`needs_manual_review=true` |
| 5 | 白名单配置错误 ×4（重叠 / 起止颠倒 / 缺 reason / 覆盖率 >50%） | 4 个全部 `FAIL` + `invalid_static_whitelist`，**豁免次数 0**（fail-closed） |
| 6 | 白名单越界 `end=999`（媒体 5 s） | `FAIL` + `OUT_OF_RANGE end 999.0 exceeds media duration 5.0` |
| 7 | 传入已删除的 `static_material_expected=True` | `ValueError`，无法绕过 |
| 8 | 同一文件修复前后对比 | 见下 |

测试媒体由本机 `ffmpeg` 的 `testsrc2 / color / freezeframes / sine` 生成；`freezeframes` 需要 2 个视频输入，已按 `filter_complex "[0:v][1:v]freezeframes=...:replace=0[v]"` 构造真实冻结段。

### 1.4 修复前后对比（`evidence/before_after.json`）

同一文件 `dynamic_mid_freeze.mp4`：

| | 调用 | `frozen_frame` | `verdict` | 具体区间 |
|---|---|---|---|---|
| **修复前**（WB-VIDEO-002/qa.py） | `static_material_expected=True` | `EXPECTED_STATIC` | **PASS** | 被隐藏 |
| **修复后**（WB-VIDEO-003/qa.py） | 无白名单 | `FAIL` | **FAIL** | `1.500–3.533 s`，`decision=FAIL`，原因「freeze outside every confirmed static interval」 |

### 1.5 对历史成片的严格重质检（新发现的真实漏报）

用修复后的 QA 重跑 WB-VIDEO-002 宣称「9 项全 PASS」的两个成片：

| 成片 | 新 verdict | 白名单外冻结区间 | 判定 |
|---|---|---|---|
| `final_horizontal_v2.mp4` | **FAIL** | **5.533–8.533 s** | `frozen_frames_outside_whitelist` |
| `final_vertical_v2.mp4` | **FAIL** | **5.5–8.5 s** | `frozen_frames_outside_whitelist` |

同时片头 `[0.033,1.533]`、章节卡 `[4.533,5.533]`、片尾 `[10.533,12.036]` 三个区间被正确识别为 `ALLOWED_STATIC`（竖屏为 `[0,1.5] / [4.5,5.5] / [10.5,12.036]`）。

**结论**：5.5–8.5 s 正是静态彩条素材 S002 所在区间。旧版把整条视频豁免后宣称 PASS，属于**真实漏报**；修复后精确指出了区间与原因。证据：`evidence/d004_reassessment.json` → `p0_1.*.evaluated_freeze_intervals`。

---

## 2. P0-2：D004 字幕问题的虚假 FIXED 判定

### 2.1 漏洞定位（真实代码）

`outbox/WB-VIDEO-002/rework.py:242-247`

```python
for did in ("D003", "D004"):
    for d in ledger.data["defects"]:
        if d["defect_id"] == did and d["fix_result"] == "OPEN":
            fixed = (dup2.get("duplicates") == [] if did == "D003"
                     else bool(v2.exists() and v2.stat().st_size > 0))
            ledger.resolve(did, "FIXED" if fixed else "STILL_FAILING", cycle)
```

文件存在且非空 ⇒ D004 被标 `FIXED`。文件存在只能证明「渲染产出」，不能证明字幕位置、字号、清晰度、遮挡、安全区或文字内容正确。

### 2.2 修复（`WB-VIDEO-003/subtitle_checks.py` + `rework.py`）

`artifact_exists` 仍记录（作为产出证据），但显式 `decision_weight: 0`，**不参与 FIXED 判定**。

自动检测（逐项保留实测值）：

| 检查 | 方法 |
|---|---|
| 字幕文件解析 | 解析 SRT 时间码与文本；有效条目数 |
| 越界 | `declared_box` 是否完整落在画布内，记录 `overflow_right/overflow_bottom` |
| 横屏安全区 | 字幕带须在画面高度 `[0.70, 0.94]` 内 |
| 竖屏安全区 | 须在 `[0.72, 0.94]` 内，且中心不得落在 `[0.35,0.65]` 中部缺陷带 |
| 字号 | 横屏 ≥24 px、竖屏 ≥32 px（按 1080/1920 高度） |
| 对比度 | 字幕带灰度 `p95-p5 ≥ 55` |
| 主体/UI 遮挡 | 与 `subject_boxes` 计算 IoU，>0.02 判 FAIL；未声明主体时标 `NEEDS_MANUAL_REVIEW` |
| 是否真的烧进画面 | 与**同一时间点的无字幕参考帧**做字幕带像素差 `MAD ≥ 2.0`；无参考帧则标 `NEEDS_MANUAL_REVIEW` |
| 字幕带定位 | `detect_subtitle_band()` 用像素差**实测**字幕带几何，不靠猜渲染参数 |

程序无法可靠判断的 3 项一律 `NEEDS_MANUAL_REVIEW`，绝不自动 PASS：
`text_content_matches_srt`（需 OCR/人读）、`semantic_readability`（语义可读性）、`occlusion_by_undeclared_content`（未声明主体/UI）。

**FIXED 判定规则**：自动检查无 FAIL **且** 每一条人工项都有具名审核人 + `APPROVED` + 证据 **且** 烧录像素证据为 PASS **且** 成片存在。自动结果与人工复核分别存放在 `automatic` / `manual_review` 两个独立字段。

`rework.py` 的 `resolve_defect()` 只依据 `can_mark_fixed`；文件存在权重为 0。

### 2.3 测试证据（P0-2 共 9 项，全部通过）

| # | 用例 | 实际结果 |
|---|---|---|
| 1 | 正常字幕（无人工签核） | 自动 `PASS`，但 `fix_result=NEEDS_MANUAL_REVIEW`，`can_mark_fixed=false` |
| 2 | 正常字幕 + 具名人工 APPROVED | `FIXED`（证明只有在证据充分时才允许） |
| 3 | 字幕超出画面右边界 | `box_within_canvas=FAIL` → `STILL_FAILING` |
| 4 | 字幕贴近底部安全边界（底边 0.991 H） | `safe_area=FAIL` |
| 5 | 字幕与声明主体框重叠 | `subject_overlap=FAIL` |
| 6 | 竖屏字幕在画面中部 vs 底部 | 中部 `midframe_defect=true / FAIL`，底部 `PASS` |
| 7 | SRT 存在但画面无字幕像素 | `srt_parse=PASS` 但 `burned_in_evidence=FAIL`（MAD≈0）→ 整体 FAIL |
| 8 | 文件存在不能标 FIXED | 旧表达式 `legacy=FIXED`，修正后 `STILL_FAILING`；`artifact_exists.decision_weight=0` |
| 9 | 自动与人工分开记录 | `automatic` / `manual_review` 独立字段，人工 `NOT_PERFORMED` |

视觉证据：`evidence/subtitle_contact_sheet.jpg`（6 格测试帧缩略图）。

### 2.4 对历史 D004 的重判（真实帧，非文件存在）

用 WB-VIDEO-002 的真实成片关键帧 + 从**无字幕渲染** `timeline_raw_v2.mp4` / `vertical_nosub_v2.mp4` 抽取的 2.5 s 参考帧，做像素差定位字幕带：

| 成片 | 实测字幕带 `[x,y,w,h]` | 中心高度 | 自动 FAIL 项 | 新结论 |
|---|---|---|---|---|
| 横屏 v2 | `[477, 948, 1053, 75]` | 0.9125 H，底边 0.947 H | `safe_area`（略超 0.94 底线） | `STILL_FAILING` |
| 竖屏 v2 | `[62, 1179, 950, 26]` | **0.6208 H（画面中部）** | `safe_area`（中部缺陷）、`font_size`（26 px < 32 px） | `STILL_FAILING` |

| 项 | 修复前 | 修复后 |
|---|---|---|
| D004 `fix_result` | **FIXED** | **STILL_FAILING** |
| 依据 | `final_vertical_v2.mp4` 存在且 949,375 B | 真实帧像素证据：字幕在中部 + 字号不足 |
| 人工复核 | 无记录 | `NOT_PERFORMED`，3 项 `NEEDS_MANUAL_REVIEW` |

**这直接证明 WB-VIDEO-002 的 D004「FIXED」是虚假判定**，且与 WB-VIDEO-002 报告里"竖屏字幕仍偏画面中部"的遗留描述一致。证据：`evidence/d004_reassessment.json`。

---

## 3. 未验证 / 明确不宣称的项目

- OCR 文字内容比对、语义可读性、未声明主体的遮挡：**程序未验证**，全部 `NEEDS_MANUAL_REVIEW`，需人工在成片上签核。
- `font_px` 在历史重判中取自 WB-VIDEO-002 渲染参数 `FontSize=26/30`，非从帧内测量；已作为元数据记录，不宣称是精确测量值。
- 本轮没有修复竖屏字幕本身，只修复了**判定逻辑**；字幕仍是已知缺陷，停在 `REVIEW_REQUIRED` 人工门（返工 2/2 轮已用尽，第 3 轮 `third_cycle_allowed=false`）。
- 本轮未改动 WB-VIDEO-002 的 `defects.json`；重判结果单独写入 `evidence/d004_reassessment.json`。

## 4. 复现

```bash
cd docs/ai-collaboration/outbox/WB-VIDEO-003
python -m py_compile qa.py subtitle_checks.py rework.py run_tests.py
python run_tests.py --root <本机临时目录> --config <本机 config.local.json> --out test-results.json
python rework.py  --root <本机 pipeline 目录> --config <本机 config.local.json> \
                  --legacy-defects ../WB-VIDEO-002/evidence/defects.json \
                  --out evidence/d004_reassessment.json
```

`config.local.json` 只存本机工具路径，位于仓库外，**不提交**。
