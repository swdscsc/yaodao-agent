# R0 → R1 取代关系指针

| 项 | 值 |
|---|---|
| 文件性质 | **新增指针**，不修改、不覆盖 R0 任何历史报告或原始证据 |
| R0 基准 commit | `334ddbc60a50a794300188fa886d388a85c9edd2` |
| 触发 | WB-VIDEO-005-PREPRODUCTION-R1（ChatGPT 独立审核修正） |
| 修订版目录 | `../WB-VIDEO-005-PREPRODUCTION-R1/` |

## 1. 本目录中被 R1 **原地重新生成**的派生物

这些文件由修正后的唯一权威数据源 `WB-VIDEO-005-PREPRODUCTION-R1/scripts/build_deliverables_r1.py`（SHOTS 表）重新生成；**修订前的逐字节原文**保存在 `../WB-VIDEO-005-PREPRODUCTION-R1/evidence/r0-originals/`，旧/新 SHA-256 对照见 `../WB-VIDEO-005-PREPRODUCTION-R1/evidence/r0-file-preservation.json`。

`main-film-shotlist.csv`、`subtitle-draft.srt`、`narration-draft.md`、`main-film-script.md`、`product-claims-register.md`、`vertical-cut-plan.md`、`evidence/consistency-check.json`、`evidence/subtitle-draft.meta.json`、`evidence/narration-table.md`、`evidence/dialogue-subtitle-draft.srt`

`evidence/dialogue-cue-index.csv` 是 R1 新增文件（R0 无对应项）。

## 2. 本目录中**保持字节不变**的历史报告与原始证据

| 文件 | 性质 | R1 处理 |
|---|---|---|
| `report.md` | R0 执行报告（历史结论） | 不改；其中 S08–S10 首段结论由 R1 `first-cut-selection.md` 取代 |
| `first-cut-readiness.md` | R0 就绪度评估（历史判定） | 不改；§2 的 S08–S10 及第 48–49 行的两句旧对白引文**已废弃**，不得作为当前制作依据 |
| `creative-research.md`、`asset-inventory.csv` | 创意研究 / 素材盘点 | 不改，继续有效 |
| `evidence/asset-probe.json`、`capability-probe.json` | 只读探测原始证据 | 不改 |
| `evidence/manifest.sha256.json`、`delivery-verification.json` | R0 提交时的哈希快照 | 不改；它们对应 commit `334ddbc`，是历史快照，不因 R1 修订回写 |
| `evidence/push-verification.json`、`push-verification-addendum.md` | R0 推送与远端回读证据 | 不改 |

> 当前工作树的全量哈希见 `../WB-VIDEO-005-PREPRODUCTION-R1/evidence/manifest.sha256.json`（R1 重新计算，覆盖 R0 + R1 两个目录）。

## 3. 已废弃的 R0 数值 / 结论

| R0 值 | 位置 | R1 权威值 | 说明 |
|---|---|---|---|
| 约 560 字 | `main-film-script.md:12`（R0 版） | **471 字** | 人工估算，已删除；统一为机器计数 |
| 473 字 | `evidence/consistency-check.json`（R0 版） | **471 字** | R0 文案的机器计数；R1 改写 N09/N10 后重新计算 |
| S08–S10 / 22 s 首段 | `report.md:98`、`first-cut-readiness.md:40` | **S14–S17 / 27 s** | 新首段须不依赖真人/真机实拍，见 R1 `first-cut-selection.md` |
| `S04-D` / `S16-D` 复用 | `subtitle-draft.meta.json`（R0 版） | `S04-D01/D02`、`S16-D01/D02` | 每条对白唯一 cue ID |
| 「我每天早饭后吃一片降压药。」 | R0 台词 / SRT / 竖屏 V04 | 「早饭后的那一次，帮我记上。」 | 移除具体药名与剂量 |
| 「只有 VERIFIED_SOURCE 与 KNOWN_LIMITATION 可以进旁白」却把 DOC_ONLY 放进 A 表 | `product-claims-register.md`（R0 版） | R1 §0 五条分类规则 + §A.1 一致性矩阵 | 分类口径自相矛盾 |

## 4. 仍然成立、不得放宽的边界

- 真实产品画面 **0 个**；所有界面必须标「模拟界面」，产品设计图形必须标「产品设计示意（非真机 · 非实测）」。
- 中文旁白音频、合法 BGM/SFX 均未产出；R1 也未产出。
- **R1 仍属于预制作修订：没有导出任何视频，没有 MP4，没有上传成片。**
- 自动 PASS ≠ 人工 PASS；字幕逐项人工签核不得使用虚构审核人。
