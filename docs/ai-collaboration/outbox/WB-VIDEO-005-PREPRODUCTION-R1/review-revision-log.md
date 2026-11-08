# 审核修订记录（WB-VIDEO-005-PREPRODUCTION-R1）

| 项 | 值 |
|---|---|
| 基准 commit | `334ddbc60a50a794300188fa886d388a85c9edd2` |
| 修订方式 | **改权威数据源 `scripts/build_deliverables_r1.py` 的 SHOTS 表 → 重新生成全部派生物**，不是只改说明文档 |
| 重新生成 | `main-film-shotlist.csv`、`subtitle-draft.srt`、`evidence/dialogue-subtitle-draft.srt`、`narration-draft.md`、`main-film-script.md`、`vertical-cut-plan.md`、`product-claims-register.md`、`evidence/consistency-check.json`、`evidence/subtitle-draft.meta.json`、`evidence/narration-table.md` |
| 报告 | R1 `report.md` 由 `scripts/build_r1_docs.py` 从证据 JSON 生成；R0 `report.md` 作为历史报告保持字节不变，另加 `R1-SUPERSEDES.md` 指针 |
| 重跑结果 | `errors = 0` / `warnings = 14` / `all_consistency_checks_passed = true` |
| 保留上一轮 | 11 份修订前原文在 `evidence/r0-originals/`；10 份历史证据未改动 |

---

## 逐条修订

| # | R0 实际问题（带文件/行号） | R1 修订（落在权威数据源） | 落点文件 | 机器/人工复核 | 结果 |
|---|---|---|---|---|---|
| 1 | R0 `product-claims-register.md:8` 写「只有 VERIFIED_SOURCE 与 KNOWN_LIMITATION 两类可以进旁白；其余一律不写」，但同一文件 §A 标题为「允许写入旁白的功能主张」，其中 A10 / A11 状态是 `VERIFIED_DOC_ONLY` 且落点写 N10 / S12、N09 / S11。分类规则、表格归属、旁白实际表述三者互相矛盾。 | 重写台账：新增 §0 五条分类规则（R1-C1..C5）、状态枚举新增 `DESIGN_INTENT_DOC_ONLY`、把 A10/A11 移出 A 表进 §A.2、新增 §A.1「分类 ↔ 旁白实际表述一致性矩阵」逐条核对 28 句旁白。 | R0/R1 `product-claims-register.md`、`scripts/build_deliverables_r1.py` | 台账 §A.1 逐条映射 + 规则文本一致性人工复核；R1-C3 与 A10/A11 新状态对应 | ✅ |
| 2 | R0 `narration-draft.md:48-49`：N09「一块放在桌上的小屏，一个能听懂普通话的声音。」、N10「它说『您』，一次只说一件事，不着急，也不打断。」两句都是无源码证据能力的事实陈述（硬件形态、普通话识别、对话节奏），却由 `VERIFIED_DOC_ONLY` 条目支撑。 | 在 SHOTS 权威表中改写 N09/N10 并同步 S11/S12 的 visual / screen / source / gap / truth：N09「这一段是设计示意，不是真机，也不是录屏。」；N10「按设计，它一次只说一件事，说完等你，不打断。」；删除「能听懂普通话」；画面常驻「产品设计示意（非真机 · 非实测）」；truth 改为 `ORIGINAL_GRAPHIC / MOCK_UI`，去掉真人/真机拍摄依赖。 | `main-film-shotlist.csv`、`subtitle-draft.srt`、`narration-draft.md`、`main-film-script.md`、`evidence/subtitle-draft.meta.json` | `design_intent_qualifiers_present = {str(consistency['r1_assertions']['design_intent_qualifiers_present']).lower()}`，且 `能听懂普通话` 全局 0 命中 | ✅ |
| 3 | R0 `main-film-script.md:12` 写「约 560 字」，`evidence/consistency-check.json:9` 写 `narration_character_count: 473`，两个字数并存且口径不同（人工估算 vs 汉字计数）。 | 在 `build_deliverables_r1.py` 定义唯一 `char_count()` 与 `NARRATION_CHAR_COUNT`（从 SHOTS 计算 = **471**），通过 `build_markdown_r1.py` 的 `fill()` 注入 `main-film-script.md`、`narration-draft.md`、`narration-revised.md`；删除所有手写估算。R0 两个旧值只在 `character-count-audit.json` 中作为「已废弃历史值」留证。 | `main-film-script.md`、`narration-draft.md`、`narration-revised.md`、`evidence/character-count-audit.json` | `character-count-audit.json` 断言所有当前权威文档的字数声明 == {NARRATION_CHAR_COUNT} | ✅ |
| 4 | R0 `evidence/subtitle-draft.meta.json` 与 `consistency-check.json` 的 collisions 中，S04 两条对白都用 `S04-D`、S16 两条都用 `S16-D`；warnings 出现 4 条重复文案，无法区分是哪条对白与旁白重叠。 | 对话 cue ID 改为 `f"{{shot}}-D{{idx:02d}}"`，16 条对白得到 16 个唯一 ID；新增 `evidence/dialogue-cue-index.csv`（cue_id ↔ SRT 序号 ↔ 镜头 ↔ 时间码 ↔ 文本 ↔ truth_label）；`narration-draft.md` §4 对白表新增 cue ID 列；meta 新增 `cue_id_scheme` 与 `dialogue_cue_ids`。 | `evidence/dialogue-cue-index.csv`、`evidence/subtitle-draft.meta.json`、`evidence/consistency-check.json`、`narration-draft.md` | `cue_ids_globally_unique = {str(consistency['r1_assertions']['cue_ids_globally_unique']).lower()}`、`collision_pairs_unique = {str(consistency['r1_assertions']['collision_pairs_unique']).lower()}` | ✅ |
| 5 | R0 S08 / S15 对白「我每天早饭后吃一片降压药。」、S09「您听听对不对：早饭后，一片。」、S16「早饭后：一片。」，以及 `vertical-cut-plan.md` V04/V05，含具体药名与剂量。 | SHOTS 中 S08/S15 → 「早饭后的那一次，帮我记上。」、S09 → 「您听听对不对：早饭后那一次。」、S16 第二条 → 「早饭这一段，就这些。」；`vertical-cut-plan.md` V04/V05 同步；新增 C07 禁止项与 10 词 fail-closed 扫描（S30 否定式「不改剂量」白名单保留）。 | `subtitle-draft.srt`、`evidence/dialogue-subtitle-draft.srt`、`main-film-shotlist.csv`、`main-film-script.md`、`vertical-cut-plan.md` | `specific_drug_or_dosage_removed = {str(consistency['r1_assertions']['specific_drug_or_dosage_removed']).lower()}` | ✅ |
| 6 | R0 `consistency_check()` 只覆盖时间码、旁白↔字幕、禁用词、source/gap/truth 完整性，未对上述任何修正设断言。 | `consistency_check()` 新增 4 组 R1 断言：cue ID 全局唯一 + collision pair 唯一、具体药名/剂量 0 命中、设计示意限定词与屏幕标注齐全、且 `all_consistency_checks_passed` 要求全部 R1 断言为真。 | `evidence/consistency-check.json`（`revision_id = WB-VIDEO-005-PREPRODUCTION-R1`） | `r1_assertions_all_passed = {str(consistency['r1_assertions_all_passed']).lower()}`，`errors = {len(consistency['errors'])}` | ✅ |

---

## 修订前后关键数值对照

| 指标 | R0 | R1 | 说明 |
|---|---|---|---|
| 旁白字数声明 | 560（估算）+ 473（机器） | **471**（唯一机器值） | 改写 N09/N10 后重算 |
| 对白 cue ID | `S04-D` ×2、`S16-D` ×2 等重复 | 16 条对白 → 16 个唯一 ID | `<镜头>-D<两位序号>` |
| 双轨重叠记录 | 14 条，其中 4 条文案完全重复 | 14 条，`collision_pairs_unique = true` | 每条可追溯到唯一对白 |
| 具体药名/剂量 | S08/S09/S15/S16 + 竖屏 V04/V05 | 0 命中 | 10 词 fail-closed 扫描 |
| N09/N10 | 陈述硬件形态与识别能力 | 明确「设计示意 / 按设计」+ 屏幕常驻标注 | `DESIGN_INTENT_DOC_ONLY` |
| 首段 | S08–S10（22 s，依赖实拍与真机） | **S14-S17（27 s，0 实拍 / 0 真机）** | 见 `first-cut-selection.md` |
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
