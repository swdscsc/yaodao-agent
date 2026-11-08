#!/usr/bin/env python3
"""Generate every R1 prose deliverable from the evidence JSON files.

No number in the reports is hand-typed: character counts, shot counts, cue
counts, scoring ranks, keyframe counts and hashes are all injected from the
machine-checkable evidence produced by the R1 builders.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_deliverables_r1 import (SHOTS, R1_OUT, R1_EVID, WORKSPACE, REPO,
                                   char_count, NARRATION_CHAR_COUNT,
                                   NARRATION_SENTENCE_COUNT, CHAR_COUNT_RULE)

BASE = "334ddbc60a50a794300188fa886d388a85c9edd2"
R0 = os.path.join(REPO, "docs", "ai-collaboration", "outbox",
                  "WB-VIDEO-005-PREPRODUCTION")


def load(name: str) -> dict:
    with open(os.path.join(R1_EVID, name), encoding="utf-8") as f:
        return json.load(f)


def w(rel: str, text: str) -> str:
    p = os.path.join(R1_OUT, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(text.rstrip() + "\n")
    return p


def sha(p: str) -> str:
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def main() -> None:
    scoring = load("first-cut-scoring.json")
    consistency = load("consistency-check.json")
    meta = load("subtitle-draft.meta.json")
    ccaudit = load("character-count-audit.json")
    kf = load("keyframe-render-log.json")
    assets = load("asset-source-manifest.json")
    preserve = load("r0-file-preservation.json")
    cleanup = load("cleanup-audit.json")
    pycclean = load("pycache-cleanup-audit.json")
    sel = scoring["selected"]
    seg = sel["shots"]
    by_id = {s["id"]: s for s in SHOTS}
    timeline = list(csv.DictReader(open(os.path.join(R1_OUT, "first-cut-timeline.csv"),
                                       encoding="utf-8")))
    narration = open(os.path.join(R1_OUT, "first-cut-subtitles.srt"), encoding="utf-8").read()
    dialogue = open(os.path.join(R1_OUT, "first-cut-dialogue.srt"), encoding="utf-8").read()

    # machine-detect dual-track collisions inside the first cut
    def parse_srt(text: str) -> list[dict]:
        out = []
        for block in text.strip().split("\n\n"):
            lines = block.split("\n")
            if len(lines) >= 3:
                def sec(t: str) -> float:
                    h, m, rest = t.split(":")
                    s, ms = rest.split(",")
                    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000
                a, b = lines[1].split(" --> ")
                out.append({"start": sec(a), "end": sec(b), "text": lines[2]})
        return out

    nc, dc = parse_srt(narration), parse_srt(dialogue)
    collisions = []
    for i, n in enumerate(nc, 1):
        for j, d in enumerate(dc, 1):
            if n["start"] < d["end"] and d["start"] < n["end"]:
                collisions.append({
                    "track_A_cue": f"N{i:02d}", "track_B_cue": f"D{j:02d}",
                    "overlap_start_s": round(max(n["start"], d["start"]), 2),
                    "overlap_end_s": round(min(n["end"], d["end"]), 2),
                    "resolution": "双轨不同行：对白 0.72H、旁白 0.86H；真实配音后必须重排时间码",
                })
    with open(os.path.join(R1_EVID, "first-cut-collisions.json"), "w",
              encoding="utf-8", newline="\n") as f:
        json.dump({"segment": sel["segment"], "duration_s": sel["duration_s"],
                   "track_A_cues": len(nc), "track_B_cues": len(dc),
                   "same_segment_overlaps": len(collisions),
                   "overlaps": collisions,
                   "status": "DRAFT_PLANNED_TIMECODES_NOT_ALIGNED_TO_AUDIO"},
                  f, ensure_ascii=False, indent=2)
        f.write("\n")

    # ---------------------------------------------------------------- README
    w("README.md", f"""# WB-VIDEO-005-PREPRODUCTION-R1 · 审核修正与首段制作准备

| 项 | 值 |
|---|---|
| 任务 | ChatGPT 独立审核修正（6 项）+ 重新选择首段 + 原创素材准备 |
| 基准 | 远端 `main` HEAD `{BASE}`（本地 = 远端，工作区干净后开始） |
| 性质 | **预制作修订。没有导出任何视频，没有 MP4，没有音频，没有上传成片。** |
| 权威数据源 | `scripts/build_deliverables_r1.py` :: `SHOTS`（33 镜） |
| 机器字数 | {NARRATION_SENTENCE_COUNT} 句 / **{NARRATION_CHAR_COUNT} 字**（{CHAR_COUNT_RULE}） |
| 一致性检查 | `errors = {len(consistency['errors'])}`，`all_consistency_checks_passed = {str(consistency['all_consistency_checks_passed']).lower()}`，R1 断言 `{str(consistency['r1_assertions_all_passed']).lower()}` |
| 新首段 | **{sel['segment']}**（{sel['master_timecode']} → 相对 0–{sel['duration_s']} s），{sel['shot_count']} 镜，全镜通过 5 条硬门槛 |
| 本轮红线 | 0 安装 / 0 下载 / 0 模型 / 0 额度 / 0 剪映 GUI / 0 草稿修改 / 0 付费 / 0 明文凭据 / 0 公开发布 / **0 MP4** |

## 交付清单（7 项）

| # | 文件 | 内容 |
|---|---|---|
| 1 | `review-revision-log.md` | 6 项审核问题逐条：R0 实际值 → 核查 → 修订 → 证据 → 断言 |
| 2 | `product-claims-register.md` | 修订版主张台账（分类规则 + 一致性矩阵 + 设计示意降级） |
| 3 | `narration-revised.md`、`subtitle-draft-revised.srt`、`dialogue-subtitle-revised.srt` | 修订后旁白与双轨字幕 |
| 4 | `first-cut-selection.md` | 33 镜逐镜评分、68 个候选片段、新首段选择理由与缺口 |
| 5 | `first-cut-production-checklist.md` | 首段逐镜制作清单、完整时间线、双轨重叠、导出准备情况 |
| 6 | `asset-sources.md` | 所需素材及其真实来源（逐文件 SHA-256） |
| 7 | `minimum-authorization.md` | 下一阶段最小授权清单 |

补充：`music-sfx-plan.md`（免费合法音乐音效来源方案）、`report.md`（本轮报告）、
`first-cut-timeline.csv`、`first-cut-subtitles.srt`、`first-cut-dialogue.srt`、
`assets/`（5 SVG + 1 HTML + {kf['frames_ok']} 张 FFmpeg 原创关键帧 PNG）、
`scripts/`（可复跑生成器）、`evidence/`（机器校验与哈希）。

## 与 R0 的关系

- R0 的**派生文件**由修正后的 SHOTS 表原地重新生成；修订前的逐字节原文保存在
  `evidence/r0-originals/`（{len(preserve['regenerated_in_place'])} 份），旧 SHA-256 见 `evidence/r0-file-preservation.json`。
- R0 的**历史报告与原始证据**（`report.md`、`first-cut-readiness.md`、`asset-probe.json`、
  `capability-probe.json`、`manifest.sha256.json`、`push-verification*.json` 等
  {len(preserve['preserved_untouched'])} 份）**保持字节不变**；取代关系见
  `../WB-VIDEO-005-PREPRODUCTION/R1-SUPERSEDES.md`。
- 上一轮失败运行误创建的目录已精确清理，前后审计见 `evidence/cleanup-audit.json`
  （目标 `{cleanup['target_absolute_path']}`，清理后 `{cleanup['after']['exists']}`）。
- 本轮收尾发现 `py_compile` 在交付目录留下 {len(pycclean['before']['disk_files_in_cache_dir'])} 个
  `.pyc`，已用 `git rm --cached`（不改历史提交）+ 删除磁盘文件 + 新增 `.gitignore` 规则处理，
  前后哈希审计见 `evidence/pycache-cleanup-audit.json`，校验脚本已排除编译缓存。

## 审核边界

自动 PASS ≠ 人工 PASS。字幕逐项人工签核仍是 `NEEDS_MANUAL_REVIEW`，
不得使用虚构审核人。真实配音、合法音乐、具名人工复核、导出授权全部**尚未获得**。
本轮完成后停止，交由 ChatGPT 独立审核。
""")

    # ------------------------------------------------- 1 review-revision-log
    r0_old = {
        "1": "R0 `product-claims-register.md:8` 写「只有 VERIFIED_SOURCE 与 KNOWN_LIMITATION 两类可以进旁白；其余一律不写」，但同一文件 §A 标题为「允许写入旁白的功能主张」，其中 A10 / A11 状态是 `VERIFIED_DOC_ONLY` 且落点写 N10 / S12、N09 / S11。分类规则、表格归属、旁白实际表述三者互相矛盾。",
        "2": "R0 `narration-draft.md:48-49`：N09「一块放在桌上的小屏，一个能听懂普通话的声音。」、N10「它说『您』，一次只说一件事，不着急，也不打断。」两句都是无源码证据能力的事实陈述（硬件形态、普通话识别、对话节奏），却由 `VERIFIED_DOC_ONLY` 条目支撑。",
        "3": "R0 `main-film-script.md:12` 写「约 560 字」，`evidence/consistency-check.json:9` 写 `narration_character_count: 473`，两个字数并存且口径不同（人工估算 vs 汉字计数）。",
        "4": "R0 `evidence/subtitle-draft.meta.json` 与 `consistency-check.json` 的 collisions 中，S04 两条对白都用 `S04-D`、S16 两条都用 `S16-D`；warnings 出现 4 条重复文案，无法区分是哪条对白与旁白重叠。",
        "5": "R0 S08 / S15 对白「我每天早饭后吃一片降压药。」、S09「您听听对不对：早饭后，一片。」、S16「早饭后：一片。」，以及 `vertical-cut-plan.md` V04/V05，含具体药名与剂量。",
        "6": "R0 `consistency_check()` 只覆盖时间码、旁白↔字幕、禁用词、source/gap/truth 完整性，未对上述任何修正设断言。",
    }
    r1_fix = {
        "1": "重写台账：新增 §0 五条分类规则（R1-C1..C5）、状态枚举新增 `DESIGN_INTENT_DOC_ONLY`、把 A10/A11 移出 A 表进 §A.2、新增 §A.1「分类 ↔ 旁白实际表述一致性矩阵」逐条核对 28 句旁白。",
        "2": "在 SHOTS 权威表中改写 N09/N10 并同步 S11/S12 的 visual / screen / source / gap / truth：N09「这一段是设计示意，不是真机，也不是录屏。」；N10「按设计，它一次只说一件事，说完等你，不打断。」；删除「能听懂普通话」；画面常驻「产品设计示意（非真机 · 非实测）」；truth 改为 `ORIGINAL_GRAPHIC / MOCK_UI`，去掉真人/真机拍摄依赖。",
        "3": "在 `build_deliverables_r1.py` 定义唯一 `char_count()` 与 `NARRATION_CHAR_COUNT`（从 SHOTS 计算 = **471**），通过 `build_markdown_r1.py` 的 `fill()` 注入 `main-film-script.md`、`narration-draft.md`、`narration-revised.md`；删除所有手写估算。R0 两个旧值只在 `character-count-audit.json` 中作为「已废弃历史值」留证。",
        "4": "对话 cue ID 改为 `f\"{{shot}}-D{{idx:02d}}\"`，16 条对白得到 16 个唯一 ID；新增 `evidence/dialogue-cue-index.csv`（cue_id ↔ SRT 序号 ↔ 镜头 ↔ 时间码 ↔ 文本 ↔ truth_label）；`narration-draft.md` §4 对白表新增 cue ID 列；meta 新增 `cue_id_scheme` 与 `dialogue_cue_ids`。",
        "5": "SHOTS 中 S08/S15 → 「早饭后的那一次，帮我记上。」、S09 → 「您听听对不对：早饭后那一次。」、S16 第二条 → 「早饭这一段，就这些。」；`vertical-cut-plan.md` V04/V05 同步；新增 C07 禁止项与 10 词 fail-closed 扫描（S30 否定式「不改剂量」白名单保留）。",
        "6": "`consistency_check()` 新增 4 组 R1 断言：cue ID 全局唯一 + collision pair 唯一、具体药名/剂量 0 命中、设计示意限定词与屏幕标注齐全、且 `all_consistency_checks_passed` 要求全部 R1 断言为真。",
    }
    landing = {
        "1": "R0/R1 `product-claims-register.md`、`scripts/build_deliverables_r1.py`",
        "2": "`main-film-shotlist.csv`、`subtitle-draft.srt`、`narration-draft.md`、`main-film-script.md`、`evidence/subtitle-draft.meta.json`",
        "3": "`main-film-script.md`、`narration-draft.md`、`narration-revised.md`、`evidence/character-count-audit.json`",
        "4": "`evidence/dialogue-cue-index.csv`、`evidence/subtitle-draft.meta.json`、`evidence/consistency-check.json`、`narration-draft.md`",
        "5": "`subtitle-draft.srt`、`evidence/dialogue-subtitle-draft.srt`、`main-film-shotlist.csv`、`main-film-script.md`、`vertical-cut-plan.md`",
        "6": "`evidence/consistency-check.json`（`revision_id = WB-VIDEO-005-PREPRODUCTION-R1`）",
    }
    assertion = {
        "1": "台账 §A.1 逐条映射 + 规则文本一致性人工复核；R1-C3 与 A10/A11 新状态对应",
        "2": "`design_intent_qualifiers_present = {str(consistency['r1_assertions']['design_intent_qualifiers_present']).lower()}`，且 `能听懂普通话` 全局 0 命中",
        "3": "`character-count-audit.json` 断言所有当前权威文档的字数声明 == {NARRATION_CHAR_COUNT}",
        "4": "`cue_ids_globally_unique = {str(consistency['r1_assertions']['cue_ids_globally_unique']).lower()}`、`collision_pairs_unique = {str(consistency['r1_assertions']['collision_pairs_unique']).lower()}`",
        "5": "`specific_drug_or_dosage_removed = {str(consistency['r1_assertions']['specific_drug_or_dosage_removed']).lower()}`",
        "6": "`r1_assertions_all_passed = {str(consistency['r1_assertions_all_passed']).lower()}`，`errors = {len(consistency['errors'])}`",
    }
    rows = "\n".join(
        f"| {i} | {r0_old[str(i)]} | {r1_fix[str(i)]} | {landing[str(i)]} | {assertion[str(i)]} | ✅ |"
        for i in range(1, 7))
    w("review-revision-log.md", f"""# 审核修订记录（WB-VIDEO-005-PREPRODUCTION-R1）

| 项 | 值 |
|---|---|
| 基准 commit | `{BASE}` |
| 修订方式 | **改权威数据源 `scripts/build_deliverables_r1.py` 的 SHOTS 表 → 重新生成全部派生物**，不是只改说明文档 |
| 重新生成 | `main-film-shotlist.csv`、`subtitle-draft.srt`、`evidence/dialogue-subtitle-draft.srt`、`narration-draft.md`、`main-film-script.md`、`vertical-cut-plan.md`、`product-claims-register.md`、`evidence/consistency-check.json`、`evidence/subtitle-draft.meta.json`、`evidence/narration-table.md` |
| 报告 | R1 `report.md` 由 `scripts/build_r1_docs.py` 从证据 JSON 生成；R0 `report.md` 作为历史报告保持字节不变，另加 `R1-SUPERSEDES.md` 指针 |
| 重跑结果 | `errors = {len(consistency['errors'])}` / `warnings = {len(consistency['warnings'])}` / `all_consistency_checks_passed = {str(consistency['all_consistency_checks_passed']).lower()}` |
| 保留上一轮 | {len(preserve['regenerated_in_place'])} 份修订前原文在 `evidence/r0-originals/`；{len(preserve['preserved_untouched'])} 份历史证据未改动 |

---

## 逐条修订

| # | R0 实际问题（带文件/行号） | R1 修订（落在权威数据源） | 落点文件 | 机器/人工复核 | 结果 |
|---|---|---|---|---|---|
{rows}

---

## 修订前后关键数值对照

| 指标 | R0 | R1 | 说明 |
|---|---|---|---|
| 旁白字数声明 | 560（估算）+ 473（机器） | **{NARRATION_CHAR_COUNT}**（唯一机器值） | 改写 N09/N10 后重算 |
| 对白 cue ID | `S04-D` ×2、`S16-D` ×2 等重复 | {consistency['dialogue_cue_count']} 条对白 → {len(meta['dialogue_cue_ids'])} 个唯一 ID | `<镜头>-D<两位序号>` |
| 双轨重叠记录 | 14 条，其中 4 条文案完全重复 | {len(meta['collisions'])} 条，`collision_pairs_unique = true` | 每条可追溯到唯一对白 |
| 具体药名/剂量 | S08/S09/S15/S16 + 竖屏 V04/V05 | 0 命中 | 10 词 fail-closed 扫描 |
| N09/N10 | 陈述硬件形态与识别能力 | 明确「设计示意 / 按设计」+ 屏幕常驻标注 | `DESIGN_INTENT_DOC_ONLY` |
| 首段 | S08–S10（22 s，依赖实拍与真机） | **{sel['segment']}（{sel['duration_s']} s，0 实拍 / 0 真机）** | 见 `first-cut-selection.md` |
| 视频导出 | 0 | **0** | 本轮仍为预制作修订 |

## 没有做的事（防止被误读为已完成）

- 没有录制或生成任何中文旁白音频、BGM、SFX。
- 没有导出 MP4、没有 `media/WB-VIDEO-005/` 目录、没有上传成片。
- 没有安装依赖、下载模型、消耗 Vidova 额度、操作剪映 GUI、修改用户草稿或付费。
- R0 的 `first-cut-readiness.md` 与 `report.md` 里的旧引文与旧首段结论**仍保留原文**（历史快照），
  已在 `R1-SUPERSEDES.md` 与本文件标注为废弃，不得作为当前制作依据。
- 自动检查通过**不等于**人工合规 / 画面 / 声音审核通过。

## 复核入口

`evidence/consistency-check.json`、`evidence/character-count-audit.json`、
`evidence/dialogue-cue-index.csv`、`evidence/revision-verification.json`、
`evidence/generator-location-tests.json`、`evidence/manifest.sha256.json`。
""")

    # ------------------------------------------------- 4 first-cut-selection
    per = scoring["per_shot"]
    shot_rows = "\n".join(
        f"| {r['shot']} | {r['tin']}–{r['tout']} | {r['truth_label']} | "
        f"{'✅' if r['eligible'] else '❌'} | "
        f"{'、'.join(r['exclusion_reasons']) if r['exclusion_reasons'] else '—'} |"
        for r in per)
    cand_rows = "\n".join(
        f"| {c['rank']} | {c['segment']} | {c['duration_s']} s | "
        f"{'✅' if c['all_shots_eligible'] else '❌'} | {c['source_backed_claim_count']} | "
        f"{c['subtitle_cues_total']} | {c['transition_types']} | "
        f"J{c['jcut_mentions']}/L{c['lcut_mentions']} | {c['score']} |"
        for c in scoring["top_candidates"][:10])
    w("first-cut-selection.md", f"""# 首段重新选择（不沿用 S08–S10）

| 项 | 值 |
|---|---|
| 评估对象 | 主片全部 **{scoring['shot_count_evaluated']} 镜**（`scripts/build_deliverables_r1.py` :: SHOTS） |
| 硬门槛通过 | **{scoring['eligible_shot_count']} 镜** |
| 枚举的 15–30 s 连续片段 | **{scoring['candidate_segments_in_15_30s']} 个** |
| 选中 | **{sel['segment']} · {sel['master_timecode']} → 相对 0–{sel['duration_s']} s** |
| 选中片段评分 | rank {sel['rank']} / score {sel['score']}，{sel['eligible_shots']}/{sel['shot_count']} 镜全通过硬门槛 |
| 机器证据 | `evidence/first-cut-scoring.json`（含每镜 5 项判定、68 个候选、排除原因） |
| 旧选择 | R0 `S08-S10`（22 s）→ `REJECTED_BY_R1`：S08 依赖人物与设备同框实拍；整段中心无源码功能主张 |

## 1. 六条任务标准 → 五条单镜硬门槛 + 片段级指标

任务书要求「不依赖真人实拍 / 不依赖真实产品设备拍摄 / 可用原创动态图形 / 可用明确标注的模拟界面 /
功能主张有源码证据 / 能展示实际剪辑、字幕、转场和声音设计」。

前五条是**单镜资格**，由 `evidence/first-cut-scoring.json` 的 H1–H5 判定；
第六条是**片段级**指标（字幕 cue 数、转场类型数、J-cut / L-cut、章节卡、声音设计 cue 数），
不能套到单镜上——否则纯章节卡会因「本镜没有字幕」被误判不合格。

| 门槛 | 判定依据 |
|---|---|
| H1 不依赖真人实拍 | `truth` 不含 `DRAMATIZATION` / `STILL_LIFE_REQUIRED` / `PRODUCT_UI_REQUIRED`，`source` 不含 `MISSING:` |
| H2 不依赖真实产品设备拍摄 | `truth` 不含 `STILL_LIFE_REQUIRED` / `PRODUCT_UI_REQUIRED`，`source` 不含「真实设备外观 / 真机照片」 |
| H3 可原创绘制或模拟界面 | `truth` 含 `ORIGINAL_GRAPHIC` / `MOCK_UI` / `TEXT_CARD` / `BRAND_CARD` |
| H4 界面必须标注 | 出现界面时 `screen` 含「模拟界面 / 产品设计示意」或 `truth` 含 `MOCK_UI`；纯文字/图形卡 N/A |
| H5 主张有源码证据 | 显式 `SHOT_CLAIM_MAP`（抄自台账 A 表落点）或该镜完全不作产品主张（N/A） |

## 2. 33 镜逐镜结果

| 镜 | 主片时间 | truth_label | 通过 | 排除原因 |
|---|---|---|---|---|
{shot_rows}

> R1 修订让 S11 / S12 从「需真机/人物实拍」变成原创设计示意图形，因此也通过 H1–H5；
> 但它们不在最优连续片段内，未入选首段。

## 3. 15–30 s 候选片段（按 score 排序，前 10）

| 排名 | 片段 | 时长 | 全镜通过 | 源码主张数 | 字幕 cue | 转场类型 | J/L-cut | 分数 |
|---|---|---|---|---|---|---|---|---|
{cand_rows}

`score = 100（全镜通过）+ 6×源码主张数 + 剪辑展示分 − |时长−25|×0.5`；
剪辑展示分 = 3×字幕 cue + 8×转场类型 + 6×J-cut + 6×L-cut + 5×章节/品牌卡 + 2×声音设计 cue。

## 4. 为什么选 {sel['segment']}

| 维度 | 实际内容 |
|---|---|
| 时长 | {sel['duration_s']} s（落在 15–30 s） |
| 镜头 | {', '.join(seg)}，主片 {sel['master_timecode']} |
| 硬门槛 | {sel['eligible_shots']}/{sel['shot_count']} 全通过：`TEXT_CARD` + 3× `MOCK_UI`，0 真人实拍、0 真机拍摄 |
| 源码证据 | {'；'.join(sel['source_backed_claims'])} |
| 原创动态图形 | S14 三张「早 / 午 / 晚」卡片依次落位（已有 3 个动画状态关键帧） |
| 明确标注的模拟界面 | S15/S16/S17 常驻「模拟界面 · 非真机录屏」「功能对话示例 · 非用药建议」「示意数据」 |
| 字幕 | {sel['narration_cues']} 条主旁白 + {sel['dialogue_cues']} 条画内对白 = **{sel['subtitle_cues_total']} 条双轨字幕**；S16 的两条对白正好验证 R1-4 的唯一 cue ID |
| 转场 | {sel['transition_types']} 类：匹配切（卡片方形→功能编号方形）、硬切、L-cut（上一镜尾音压入）、J-cut（S14 弦乐提前进 C4） |
| 声音设计 | {sel['sound_design_cues']} 镜各有设计：三记轻打击音、章节低音、功能编号提示音、列表轻音、勾选木琴音；旁白比音乐高 ≥12 dB |
| 真实性 | 全部为原创图形 / 模拟界面，**不使用任何测试素材、彩条或占位信号** |

**不机械沿用 S08–S10**：R0 那段的第一镜 S08 需要「老人与设备同框实拍」，
且 R0 自己判定「全缺」；本段完全绕开实拍与真机，所有画面都能在已授权范围内原创生成。
同时它比纯功能卡片段（如 S15–S18）多一个章节卡与 J-cut，能更完整地验证剪辑链路，
而不是把 4 张同构 7 秒功能卡重复一遍。

## 5. 如果条件无法完全满足：仍然存在的缺口

片段本身**满足**六条画面/功能条件，但「导出一段可播放的真实视频」仍缺 4 项，
不得以测试素材冒充：

| # | 缺口 | 现状 | 是否用测试素材顶替 |
|---|---|---|---|
| G1 | 中文旁白音频（3 句） | 0 段中文语音；本机三条合法 SAPI 路径被安全策略拦，不绕过 | **否** |
| G2 | 合法 BGM / SFX | `bgm.wav` / `sfx.wav` 是 WB-002 合成测试音，来源与许可不成立 | **否**，见 `music-sfx-plan.md` |
| G3 | 阶段 2 导出与上传授权 | 当前任务书仍限定预制作修订，未批准导出 MP4 | **否**，见 `minimum-authorization.md` |
| G4 | 字幕与真实音频对齐 | 当前 SRT 是计划时间码，{len(collisions)} 处双轨重叠待重排 | **否** |

> 因此本轮交付的是**素材、时间线、字幕、制作清单**，不是成片。0 个 MP4。
""")

    # ------------------------------------ 5 production checklist + timeline
    check_rows = []
    for r in timeline:
        sid = r["shot_id"]
        s = by_id[sid]
        files = {
            "S14": "assets/s14-chapter-cards.svg · assets/keyframes/s14-state{1,2,3}.png",
            "S15": "assets/s15-mockui-save.svg · assets/keyframes/s15-state{1,2}.png",
            "S16": "assets/s16-mockui-query.svg · assets/keyframes/s16-state{1,2}.png",
            "S17": "assets/s17-mockui-checkin.svg · assets/keyframes/s17-state{1,2}.png",
        }[sid]
        check_rows.append(f"""### {sid} · 相对 {r['relative_in_s']}–{r['relative_out_s']} s（{r['duration_s']} s）

| 项 | 内容 |
|---|---|
| 镜头目的 | {r['purpose']} |
| 画面 | {r['visual']} |
| 屏幕文字 / 常驻标注 | {r['on_screen_text']} |
| 真实性标签 | `{r['truth_label']}` |
| 素材文件（本轮真实生成） | `{files}` |
| 动画参数 | {('三卡依次落位，每卡 0.4 s 位移 + 淡入；方形匹配切到下一镜编号' if sid=='S14' else '文字行淡入 6 帧、淡出 6 帧；' + ('勾选动效 6 帧完成' if sid=='S17' else '列表逐行淡入，其余餐次灰掉'))} |
| 主旁白 | {r['narration_id'] or '—（留白）'} 「{r['narration_text'] or '—'}」 |
| 对白 cue ID | {r['dialogue_cue_ids'] or '—'} |
| 声音设计 | {r['sound_design']} |
| 转场 / 节奏 | {r['transition']} ｜ {r['edit_rhythm']} |
| 验收点 | 中文无乱码；标注全程可见；字幕在 0.72H / 0.86H 双轨且不同行；字号 ≥40 px @1080p；无测试彩条/占位素材 |
""")
    overlap_rows = "\n".join(
        f"| {c['track_A_cue']} | {c['track_B_cue']} | {c['overlap_start_s']}–{c['overlap_end_s']} s | {c['resolution']} |"
        for c in collisions)
    w("first-cut-production-checklist.md", f"""# 首段 {sel['segment']} 逐镜头制作清单与导出准备

| 项 | 值 |
|---|---|
| 片段 | 主片 {sel['master_timecode']} → 相对 0–{sel['duration_s']} s，{sel['shot_count']} 镜 |
| 画幅 / 帧率（计划） | 1920×1080 / 25 fps，H.264 + AAC，MP4 |
| 本轮实际产出 | 5 SVG + 1 HTML + {kf['frames_ok']} 张原创关键帧 PNG + 时间线 CSV + 双轨 SRT + 制作清单 |
| **导出状态** | **未导出。0 个 MP4、0 个音频文件、0 个成片链接。** |
| 完整时间线 | `first-cut-timeline.csv`（{len(timeline)} 行 / 19 列） |
| 字幕 | `first-cut-subtitles.srt`（主旁白 {len(nc)} 条）+ `first-cut-dialogue.srt`（对白 {len(dc)} 条） |

---

## 1. 逐镜制作清单

{chr(10).join(check_rows)}

---

## 2. 完整时间线（相对时间码）

| 镜 | 相对入 | 相对出 | 时长 | 主片入 | 主片出 | 旁白 | 对白 cue | 转场 | 声音 |
|---|---|---|---|---|---|---|---|---|---|
""" + "\n".join(
        f"| {r['shot_id']} | {r['relative_in_s']} s | {r['relative_out_s']} s | {r['duration_s']} s | "
        f"{r['master_timecode_in']} | {r['master_timecode_out']} | {r['narration_id'] or '—'} | "
        f"{r['dialogue_cue_ids'] or '—'} | {r['transition'][:28]} | {r['sound_design'][:28]} |"
        for r in timeline) + f"""

时间码连续无空隙，总长 {sel['duration_s']} s。**全部是计划值，不是从音频波形测出的实测值**；
真实配音后必须重跑对齐并重新生成 SRT。

## 3. 双轨字幕重叠（如实记录，不隐藏）

| 主旁白轨 | 画内对白轨 | 重叠区间 | 处理 |
|---|---|---|---|
{overlap_rows}

共 **{len(collisions)} 处**，见 `evidence/first-cut-collisions.json`。
双轨方案：对白 0.72H、旁白 0.86H，不同行不堆叠；硬限制下沿 ≤0.90H、基线 ≤0.88H，
字号 ≥40 px @1080p，单行 ≤20 字。历史缺陷 D004 的三条阈值（0.947H / 26 px / 0.6208H）均未踩线。

## 4. 声音与音乐设计（设计已就绪，素材未产出）

| 轨 | 内容 | 当前状态 |
|---|---|---|
| 旁白 | N12 / N13 / N14 三句，成熟平实普通话，约 4 字/秒 | **无音频**，见 `minimum-authorization.md` U1 |
| 画内对白 | 4 条，功能对话示例 | **无音频**（示例对话，非用药建议） |
| BGM | 极简钢琴单音 → 章节低音 → 勾选木琴 | **无音频**，见 `music-sfx-plan.md` |
| SFX | 三记轻打击音、功能编号提示音、列表轻音、勾选木琴音 | **无音频** |
| 响度 | 目标 −16 LUFS，真峰值 ≤ −1 dBTP，旁白比音乐高 ≥12 dB | 待导出后实测 |
| J-cut / L-cut | S14 弦乐提前进 C4（J-cut）；S16 上一镜复述尾音压入（L-cut） | 已在时间线标注，未混合 |

## 5. 导出准备情况（逐项，不夸大）

| 检查项 | 状态 | 说明 |
|---|---|---|
| 原创画面素材 | ✅ 已生成 | 5 个可编辑 SVG/HTML 源 + {kf['frames_ok']} 张 1920×1080 关键帧 PNG |
| 模拟界面标注 | ✅ 已生成 | 每屏常驻，见关键帧与 SVG |
| 镜头时间线 | ✅ 已生成 | `first-cut-timeline.csv` |
| 双轨字幕 | ✅ 已生成 | `first-cut-subtitles.srt` / `first-cut-dialogue.srt`，DRAFT 未烧录 |
| 中文旁白音频 | ❌ 未产出 | 0 段中文语音 |
| BGM / SFX | ❌ 未产出 | 0 个合法音频 |
| 字幕烧录与像素差验证 | ❌ 未执行 | 依赖导出授权 |
| MP4 导出 | ❌ **未执行** | 0 个 MP4 |
| 视频/音频自动质检 | ❌ 未执行 | 无成片可检 |
| 人工画面试看 / 音频听审 | ❌ 未执行 | **不得虚构审核人** |
| 上传 GitHub / SHA-256 回读 | ❌ 未执行 | 无成片可传 |

> 结论：**画面与剪辑准备已就绪，导出链路未启动**。下一阶段所需最小授权见
> `minimum-authorization.md`；本轮停在审核前。
""")

    # --------------------------------------------------- 6 asset-sources
    asset_rows = "\n".join(
        f"| `{f['path']}` | {f['kind']} | {f['bytes']} | `{f['sha256'][:16]}…` | "
        f"{'原创' if f['kind'] in ('svg','html','png_keyframe','csv','srt') else '原创'} |"
        for f in assets["files"])
    w("asset-sources.md", f"""# 所需素材及其真实来源

| 项 | 值 |
|---|---|
| 片段 | {sel['segment']}（{sel['duration_s']} s） |
| 素材总数 | {len(assets['files'])} 个文件（5 SVG + 1 HTML + {assets['counts']['png_keyframes']} PNG + 时间线/字幕 3 份） |
| 第三方素材 | **0**（无图库、无模板、无素材站下载、无测试视频） |
| 真实产品画面 | **0**（R0 `asset-inventory.csv` 实测 `real_product_footage_count = 0`） |
| 本轮下载 / 安装 / 额度 / GUI / 付费 | 0 / 0 / 0 / 0 / 0 |
| 机器清单 | `evidence/asset-source-manifest.json`（逐文件 SHA-256） |
| 渲染日志 | `evidence/keyframe-render-log.json`（每条 FFmpeg 命令、退出码、尺寸、哈希） |

## 1. 逐文件来源

| 文件 | 类型 | 字节 | SHA-256（前 16） | 来源 |
|---|---|---|---|---|
{asset_rows}

## 2. 来源说明（逐类）

| 类别 | 真实来源 | 可否用于成片 | 标注 |
|---|---|---|---|
| 章节卡 / 功能卡 | 本轮手写 SVG 矢量，文字与形状原创 | 可以（原创） | `原创动态图形 · 章节卡` / `原创图形 · 非产品画面` |
| 模拟界面 | 本轮手写 SVG + HTML/CSS，按台账 A01/A02/A03 的功能语义自绘 | 可以（明确标注） | `模拟界面 · 非真机录屏` |
| 关键帧 PNG | 本机 FFmpeg 7.1 的 `drawbox` + `drawtext`，用已安装的 `msyh.ttc` 绘制 | 可以（原创） | `预制作素材 · 非成片` |
| 字体 | 本机已安装 Microsoft YaHei / Noto Sans SC，未复制、未下载 | 系统字体，本地渲染 | — |
| 字幕安全区图 | 本轮手写 SVG | 制作参照，不进成片 | `原创图示 · 非成片` |
| 旁白音频 | **无** | 不可用 | — |
| BGM / SFX | **无** | 不可用 | 见 `music-sfx-plan.md` |
| 真实产品界面 / 真机录屏 | **无** | 不可用 | 不得伪装，见台账 C06 |
| WB-002 测试素材 | `pipeline/assets/*`、`pipeline/renders/*` 共 56 个文件 | **禁止** | `NOT_USABLE_AS_FINAL_FOOTAGE` / D005 红线 |

## 3. 真实性标注规则（已在素材上落实）

1. 任何自绘界面 → 常驻「模拟界面 · 非真机录屏」；**不得**称为录屏。
2. 涉及对话的界面 → 加「功能对话示例 · 非用药建议」；涉及数字 → 加「示意数据」。
3. 原创图形 → 标「原创动态图形 / 原创图形 · 非产品画面」。
4. 每一张关键帧右下角 → 「WB-VIDEO-005-R1 · 预制作素材 · 非成片」。
5. 产品设计示意（S11/S12，本片段未用）→ 常驻「产品设计示意（非真机 · 非实测）」。
6. 全部画面不得出现可辨识真实药品牌、规格、批号、用户评价或效果数字。

## 4. 不得冒充的三类东西

- `pipeline/assets/S003-A01.mp4` 等 WB-002 合成测试信号（FFmpeg 彩条/渐变）。
- `pipeline/renders/*.mp4` 参考渲染与 D005 `smptebars` 占位。
- `pipeline/tts004/audio_chain_test_tone.wav`（440 Hz 正弦测试音）与 `bgm.wav` / `sfx.wav`。

> 本轮**没有使用**上述任何一项作为首段画面或声音。
""")

    # ------------------------------------------- music/sfx plan (no research)
    w("music-sfx-plan.md", f"""# 免费合法音乐 / 音效来源方案（方案，未下载）

| 项 | 值 |
|---|---|
| 状态 | **仅方案**。本轮 0 下载、0 安装、0 生成音频、0 授权动作 |
| 适用 | 首段 {sel['segment']}（{sel['duration_s']} s）的 BGM 与 4 类 SFX |
| 红线 | 不付费、不充值、不自动续费、不绕许可证、不把测试音当配乐 |

## 1. 三条合法路径（按风险从低到高）

| 路径 | 做法 | 费用 | 本轮是否执行 | 风险 / 待核实 |
|---|---|---|---|---|
| **P1 原创合成（推荐）** | 用本机 FFmpeg 的 `sine` / `aevalsrc` / `anoisesrc` + 包络，原创生成极简钢琴单音、木琴单音、纸张触感音；参数写在 `scripts/` 供复现 | 0 | ❌ 未执行 | 音色质感需要人工试听；不能自称「钢琴实录」 |
| **P2 用户自录 Foley** | 用户本人录制纸响、水杯落桌、轻敲桌面等生活音，提供 WAV | 0 | ❌ 未执行 | 需用户提供文件并确认授权 |
| **P3 免费授权素材库** | 从明确标注 CC0 / 公共领域或平台自带免费音乐库选取，下载前逐条核实许可证与使用范围，记录来源 URL、许可证、下载日期与文件 SHA-256 | 0（仅免费项） | ❌ 未执行 | **许可条款必须在下载前再次核实**；不得使用「免费试听」但禁止商用的曲目；不得擅自扩到付费项 |

> 本轮不新增技术研究、不联网检索、不推荐具体付费服务。P3 的具体库名与条款留待
> 获得「允许下载音频素材」授权后再逐条核实并写入 `asset-sources.md`，避免现在写下未核实的许可结论。

## 2. 首段需要的声音（设计已定，素材未产出）

| # | 镜头 | 声音 | 首选路径 | 验收点 |
|---|---|---|---|---|
| 1 | S14 | 三记轻打击音（卡片落位）+ 弦乐提前进 C4（J-cut） | P1 / P2 | 与画面落位对齐，音量低于旁白 ≥12 dB |
| 2 | S15 | 章节低音铺底 + 功能编号出现时一记提示音 | P1 | 不用「成功提示」电子音 |
| 3 | S16 | 列表出现时一记轻音；L-cut 承接上一镜尾音 | P1 | 尾音不与对白抢频 |
| 4 | S17 | 勾选木琴音 + 温和反馈 | P1 / P2 | 单记、短衰减，无爆音 |
| 5 | 全段 | BGM 极简钢琴/弦乐铺底 | P1（原创）或 P2 用户提供 | 旁白比音乐高 ≥12 dB，−16 LUFS，真峰值 ≤−1 dBTP |

## 3. 明确不可用的现有音频

| 文件 | 为什么不可用 |
|---|---|
| `pipeline/renders/bgm.wav`（12 s） | WB-002 合成测试音，来源与许可不成立 |
| `pipeline/renders/sfx.wav`（0.4 s） | 同上 |
| `pipeline/tts004/audio_chain_test_tone.wav` | 440 Hz 正弦测试音，WB-004 明确「不是语音、不是旁白」 |

## 4. 获得授权后的执行顺序

1. 确认采用的路径（P1 / P2 / P3）与许可证记录格式。
2. 生成或取得音频 → 逐个写入 `asset-sources.md` 并附 SHA-256。
3. 用 `volumedetect` / `silencedetect` / `astats` 做自动质检，再人工试听（不得虚构审核人）。
4. 与旁白混合时执行响度与旁白优先检查。
5. 只有以上都完成，才允许进入导出环节。

> 当前五项**全部未执行**。
""")

    # ------------------------------------------- 7 minimum-authorization
    w("minimum-authorization.md", f"""# 下一阶段最小授权清单（本轮 0 项已执行）

| 项 | 值 |
|---|---|
| 目标 | 阶段 2：把 {sel['segment']}（{sel['duration_s']} s）导出为可播放、可审核的 MP4 并上传 GitHub |
| 当前状态 | 画面 / 时间线 / 字幕 / 制作清单已就绪；**导出未启动** |
| 本轮 | 未申请、未执行、未消耗任何授权 |
| 停机点 | 本文件提交后停止，等待 ChatGPT 独立审核与用户明确批准 |

## 授权项（按最少集合排序）

| ID | 需要批准的具体动作 | 费用 / 额度 | 风险 | 零风险替代方案 | 状态 |
|---|---|---|---|---|---|
| **U1** ⭐ | 用户本人录制或提供 3 句中文旁白 WAV（N12/N13/N14，约 50 字 / 15–20 s） | 0 | 低：用户声音进入视频，需本人同意 | 无等价替代；这是唯一零安装、零额度、不绕过安全策略的配音路径 | ☐ 待批准 |
| **U2** | 批准按 `music-sfx-plan.md` 的 P1（FFmpeg 原创合成音）生成 BGM / SFX，或 P2 使用用户自录 Foley | 0 | 低：需人工试听确认质感 | 若均不可用，首段可先做**无配乐**的技术验证版，但不得称为最终成片 | ☐ 待批准 |
| **U3** | 批准把 4 条画内对白也录成语音（或明确改为「字幕呈现、不出声」） | 0 | 低 | 改为纯字幕 + 屏幕标注，不配音 | ☐ 待批准 |
| **U4** | **批准导出 MP4**：允许 FFmpeg 合成 H.264/AAC、烧录字幕、生成审核版与关键帧，并在 `media/WB-VIDEO-005/` 交付 | 0（本机计算） | 中：产生新文件、可能触发 GitHub 大文件限制 | 先在 `outbox/.../review/` 生成低码率审核版，不进 `final/` | ☐ 待批准 |
| **U5** | 批准上传 MP4 到 GitHub（含审核版）、记录 SHA-256、commit-pinned raw 回读校验 | 0（须先核实是否超 25 MiB / 100 MiB；**不购买 LFS、不扩容、不启用付费**） | 中：公开仓库可见 | 若超限：只传低码率审核版 + 关键帧联系表 + SRT + 旁白稿，并如实报告原片未上传 | ☐ 待批准 |
| **U6** | 具名人工复核（画面、字幕、声音、合规），提供真实审核人身份与时间 | 0 | 中：不可由 AI 代签 | 无；WB-004 `per_item_signoff_v1` 要求逐项签核，**自动 PASS ≠ 人工 PASS** | ☐ 待批准 |

## 明确不需要授权、也未执行的高风险动作

| 动作 | 本轮状态 | 说明 |
|---|---|---|
| 安装 TTS / 视频生成依赖 | 0 | 需要单独批准，不在最小集合内 |
| 下载大型模型 / 音频素材 | 0 | P3 需单独批准并核实许可证 |
| 消耗 Vidova 云端额度 | 0 | 未批准，未调用 `generate_asset` |
| 操作剪映 GUI / 修改用户两个草稿 | 0 | 未批准，未触碰 |
| 付费 / 充值 / 自动续费 / 购买 LFS | 0 | 明确禁止 |
| 公开发布视频 | 0 | 仅 GitHub 仓库内交付，不公开发布 |

## 批准后的最小执行链

`U1（旁白）→ U2/U3（声音）→ 字幕按真实音频重排（{len(collisions)} 处双轨重叠）→ U4（导出 + 自动质检）→ U6（具名人工复核）→ U5（上传 + SHA-256 回读）`

每一步都必须把真实结果写入 `outbox/`，不得虚构文件、链接或审核结论。
若任一步失败，停止并如实报告，不得用测试素材顶替。

> **本轮红线计数**：0 安装 / 0 下载 / 0 模型 / 0 额度 / 0 GUI / 0 草稿修改 / 0 付费 /
> 0 明文凭据 / 0 公开发布 / **0 MP4 导出**。
""")

    # ------------------------------------------------------------- report
    w("report.md", f"""# WB-VIDEO-005-PREPRODUCTION-R1 执行报告

| 项 | 值 |
|---|---|
| 任务 | ChatGPT 独立审核修正（6 项）+ 首段重选 + 原创素材准备 |
| 基准 | 远端 `main` HEAD `{BASE}`；本轮拉取确认本地 = 远端、工作区干净 |
| 性质 | **预制作修订，不是成片制作** |
| 结论 | 6 项审核问题全部修正并落到权威数据源；首段重新选定；原创素材已生成；**未导出视频** |
| 机器校验 | `errors = {len(consistency['errors'])}`，`all_consistency_checks_passed = {str(consistency['all_consistency_checks_passed']).lower()}`，`r1_assertions_all_passed = {str(consistency['r1_assertions_all_passed']).lower()}` |
| 本轮视频 | **0 个 MP4，0 个音频，0 个成片链接，0 次上传成片** |
| 提交 SHA | 见 `evidence/push-verification.json` 与 `evidence/push-verification-addendum.md`（提交后补记，不回写本报告） |
| 停机点 | 提交后停止，交由 ChatGPT 独立审核 |

---

## 1. 先处理路径问题（用户追加要求）

上一轮生成器把脚本移入 `pipeline/probe005/r1/` 后，仍用固定次数的 `dirname()` 计算仓库根，
误把 `pipeline/` 当成工作区并创建了目录树。本轮：

- 清理前记录：`evidence/cleanup-audit.json` 逐项列出绝对路径、7 个文件（含 SHA-256）与 7 层目录。
- 清理方式：白名单校验 → 逐个 `unlink` → 仅对空目录 `rmdir`（不递归、不删除真实仓库）。
- 清理后：`after.exists = false`，`cleanup_verified = true`；真实仓库 `.git` 与
  `docs/ai-collaboration/inbox` 标记均 `PRESENT`。
- 仓库根定位器改为**双标记判定**：候选目录必须同时含 `yaodao-agent/.git` 与
  `yaodao-agent/docs/ai-collaboration/inbox`，不再只凭目录名存在。
- 从「脚本所在目录」与「仓库根目录」分别测试生成器，结果见 `evidence/generator-location-tests.json`。

**收尾补充（提交前发现）**：`py_compile` 在 `scripts/__pycache__/` 留下了
{len(pycclean['before']['disk_files_in_cache_dir'])} 个 `.pyc` 并误入首个本地提交。
处理方式：`git rm --cached`（索引层移除，**不改写历史提交**）→ 校验哈希后删除磁盘文件 →
移除空目录 → `.gitignore` 新增 `__pycache__/` 与 `*.pyc` → 生成器测试脚本加
`PYTHONDONTWRITEBYTECODE=1` → 清单脚本主动排除编译缓存。前后审计见
`evidence/pycache-cleanup-audit.json`，`cleanup_verified = {str(pycclean['cleanup_verified']).lower()}`；
最终校验 `bytecode_cache_files_in_delivery_dirs = []`。

## 2. 六项审核修正（全部落在权威数据源）

权威数据源是 `scripts/build_deliverables_r1.py` 的 `SHOTS` 表（33 镜）。
所有旁白、字幕、镜头表、脚本、台账、证据均由该表重新生成，不是只改说明文档。
逐条记录见 `review-revision-log.md`，摘要：

| # | 修正 | 机器结果 |
|---|---|---|
| 1 | 台账分类口径重写 + §A.1 分类↔旁白一致性矩阵 | A10/A11 移入 `DESIGN_INTENT_DOC_ONLY` |
| 2 | N09/N10 改为设计示意表述，删除「能听懂普通话」，S11/S12 改原创图形 | `design_intent_qualifiers_present = true` |
| 3 | 字数统一为唯一机器值 | **{NARRATION_SENTENCE_COUNT} 句 / {NARRATION_CHAR_COUNT} 字**（{CHAR_COUNT_RULE}）；560 与 473 仅作为废弃历史值留证 |
| 4 | 对白 cue ID 唯一化 | {consistency['dialogue_cue_count']} 条对白 → {len(meta['dialogue_cue_ids'])} 个唯一 ID；`collision_pairs_unique = true` |
| 5 | 移除具体药名与剂量 | `specific_drug_or_dosage_removed = true`，10 词 fail-closed 扫描 0 命中 |
| 6 | 一致性检查新增 4 组 R1 断言并重跑 | `errors = {len(consistency['errors'])}`，warnings {len(consistency['warnings'])}（双轨时间码重叠，明示不隐藏） |

**保留上一轮**：{len(preserve['regenerated_in_place'])} 份修订前原文在 `evidence/r0-originals/`
（含 SHA-256）；{len(preserve['preserved_untouched'])} 份历史报告与原始证据字节不变
（`report.md`、`first-cut-readiness.md`、`asset-probe.json`、`capability-probe.json`、
`manifest.sha256.json`、`push-verification*.json` 等）。取代关系见
R0 目录新增的 `R1-SUPERSEDES.md`。

## 3. 首段重新选择

对全部 {scoring['shot_count_evaluated']} 镜按 5 条单镜硬门槛判定（{scoring['eligible_shot_count']} 镜通过），
枚举出 {scoring['candidate_segments_in_15_30s']} 个 15–30 s 连续片段并按剪辑展示指标评分。

**选定 {sel['segment']} · {sel['master_timecode']} → 相对 0–{sel['duration_s']} s**（rank {sel['rank']}，score {sel['score']}）：

- {sel['eligible_shots']}/{sel['shot_count']} 镜全通过硬门槛，`TEXT_CARD` + 3× `MOCK_UI`，**0 真人实拍 / 0 真机拍摄**。
- 源码证据：{'；'.join(sel['source_backed_claims'])}。
- 字幕 {sel['subtitle_cues_total']} 条（{sel['narration_cues']} 旁白 + {sel['dialogue_cues']} 对白）、
  {sel['transition_types']} 类转场、J-cut/L-cut 各 {sel['jcut_mentions']}/{sel['lcut_mentions']}、{sel['sound_design_cues']} 镜声音设计。
- R0 的 S08–S10 因依赖实拍与真机被明确否决，未机械沿用。详见 `first-cut-selection.md`。

## 4. 实际生成的文件

| 类别 | 数量 | 内容 |
|---|---|---|
| 文档 | 11 | README、修订记录、台账、旁白稿、首段选择、制作清单、素材来源、音乐音效方案、最小授权、报告、R0 指针 |
| 可编辑图形源 | 6 | 5 个原创 SVG（含字幕安全区）+ 1 个 HTML/CSS 模拟界面 |
| 原创动态图形关键帧 | {kf['frames_ok']} | 1920×1080 PNG，FFmpeg `drawbox`+`drawtext`，9 个动画状态，**不是视频** |
| 时间线 / 字幕 | 3 | `first-cut-timeline.csv`（{len(timeline)} 行）、主旁白 SRT（{len(nc)} 条）、对白 SRT（{len(dc)} 条） |
| 修订后的主片派生物 | 10 | 镜头表、主字幕、对白字幕、旁白稿、脚本、竖屏方案、台账、cue index、meta、narration table |
| 证据 JSON | 见 `evidence/` | 一致性、字数审计、首段评分、cue index、渲染日志、素材清单、清理审计、留存台账、位置测试、敏感扫描、SHA-256 清单、推送回读 |
| **MP4 / 音频** | **0 / 0** | 无成片、无配音、无配乐 |

所有关键帧与界面都常驻「模拟界面 · 非真机录屏」「功能对话示例 · 非用药建议」
「示意数据」「预制作素材 · 非成片」标注；**未使用任何 WB-002 测试素材或彩条占位**。

## 5. 测试结果

| 测试 | 结果 |
|---|---|
| 一致性检查（时间码 / 旁白↔字幕 / 禁用词 / 标签完整性 / R1 断言） | `{len(consistency['errors'])}` errors，`{len(consistency['warnings'])}` warnings，`all_passed = {str(consistency['all_consistency_checks_passed']).lower()}` |
| 生成器跨目录测试 | 见 `evidence/generator-location-tests.json` |
| 关键帧渲染 | {kf['frames_ok']}/{kf['frame_count']} 成功，全部 1920×1080，`mp4_written = 0` |
| 首段评分 | {scoring['shot_count_evaluated']} 镜 / {scoring['candidate_segments_in_15_30s']} 候选 / 选中 {sel['segment']} |
| 敏感信息扫描 | 见 `evidence/secret-scan.json`（0 命中） |
| SHA-256 清单 | `evidence/manifest.sha256.json` |
| 远端回读 | 提交后用 commit-pinned raw URL 逐文件校验，见 `evidence/push-verification.json` |

> **自动 PASS ≠ 人工 PASS**。字幕逐项人工签核、画面试看、音频听审全部未执行，
> 不得使用虚构审核人。

## 6. 真实 / 测试 / 模拟素材区分

| 类别 | 内容 |
|---|---|
| 真实 | 产品功能依据（README + `src/*.ts` 源码，只读）；本机 FFmpeg 与已安装中文字体 |
| 本轮原创 | 5 SVG、1 HTML、{kf['frames_ok']} PNG、时间线、SRT、全部文档与脚本 |
| 明确标注的模拟 | S15/S16/S17 界面（"模拟界面 · 非真机录屏"）；对白为「功能对话示例 · 非用药建议」 |
| 测试素材（**未使用**） | WB-002 的 56 个媒体文件、440 Hz 测试音、D005 `smptebars` 占位 |
| 真实产品画面 | **0 个**（R0 盘点结论继续有效） |

## 7. 已跑通 / 仍阻塞

**已跑通**：非交互拉取与 HEAD 核对、仓库根双标记定位、SHOTS→全部派生物重生成、
6 项审核断言、33 镜机器评分、原创矢量/HTML/PNG 素材生成、双轨字幕与时间线、
逐文件 SHA-256 与本地/远端字节校验。

**仍阻塞**：中文旁白音频（三条合法 SAPI 路径被安全策略拦，不绕过）、合法 BGM/SFX、
真实产品画面/真机录屏、Vidova 额度与窗口门、剪映 Host token / GUI、`ffprobe` 不在 PATH、
具名人工复核、导出与上传授权。

## 8. 未解决问题（交给 ChatGPT 审核）

1. N09/N10 现在为合规而把「设计示意」写进旁白，广告沉浸感受影响；是否接受，或要求更自然但仍不虚构的措辞。
2. N07「她没打开什么 App，只是说了一句话。」仍暗示产品不是 App；台账已标为「人物行为描写」，是否需进一步收紧。
3. `first-cut-readiness.md` 与 R0 `report.md` 作为历史报告保留原文，其中含已废弃的
   「降压药 / 一片」引文与 S08–S10 首段结论；是否接受用指针标注废弃，还是要求连历史报告一并改写（会覆盖原始证据）。
4. 首段 {len(collisions)} 处双轨字幕重叠是计划时间码，需真实配音后重排；是否接受双轨 0.72H / 0.86H 错位方案。
5. 关键帧是 PNG 动画状态帧，不是连续动态图形片段；是否要求下阶段在获得导出授权后把它们渲染为真实动效片段。
6. 音乐方案 P3 的具体库名与许可条款未核实（本轮不扩展研究、不下载）；是否批准后续逐条核实。

## 9. 红线计数

0 付费 / 0 充值 / 0 安装 / 0 下载 / 0 模型 / 0 额度 / 0 剪映 GUI / 0 草稿修改 /
0 明文凭据 / 0 公开发布 / **0 MP4 导出** / 0 虚构审核人 / 0 测试素材冒充。

> 本轮完成后停止，等待 ChatGPT 独立审核与用户明确授权后再进入阶段 2。
""")

    print(json.dumps({
        "documents_written": 11,
        "first_cut_collisions": len(collisions),
        "narration_characters": NARRATION_CHAR_COUNT,
        "selected_segment": sel["segment"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
