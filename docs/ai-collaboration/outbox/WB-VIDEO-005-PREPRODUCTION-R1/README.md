# WB-VIDEO-005-PREPRODUCTION-R1 · 审核修正与首段制作准备

| 项 | 值 |
|---|---|
| 任务 | ChatGPT 独立审核修正（6 项）+ 重新选择首段 + 原创素材准备 |
| 基准 | 远端 `main` HEAD `334ddbc60a50a794300188fa886d388a85c9edd2`（本地 = 远端，工作区干净后开始） |
| 性质 | **预制作修订。没有导出任何视频，没有 MP4，没有音频，没有上传成片。** |
| 权威数据源 | `scripts/build_deliverables_r1.py` :: `SHOTS`（33 镜） |
| 机器字数 | 28 句 / **471 字**（CJK Unified Ideographs only (U+4E00-U+9FFF); punctuation, digits, Latin letters and whitespace excluded） |
| 一致性检查 | `errors = 0`，`all_consistency_checks_passed = true`，R1 断言 `true` |
| 新首段 | **S14-S17**（96-123 s → 相对 0–27 s），4 镜，全镜通过 5 条硬门槛 |
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
`assets/`（5 SVG + 1 HTML + 9 张 FFmpeg 原创关键帧 PNG）、
`scripts/`（可复跑生成器）、`evidence/`（机器校验与哈希）。

## 与 R0 的关系

- R0 的**派生文件**由修正后的 SHOTS 表原地重新生成；修订前的逐字节原文保存在
  `evidence/r0-originals/`（11 份），旧 SHA-256 见 `evidence/r0-file-preservation.json`。
- R0 的**历史报告与原始证据**（`report.md`、`first-cut-readiness.md`、`asset-probe.json`、
  `capability-probe.json`、`manifest.sha256.json`、`push-verification*.json` 等
  10 份）**保持字节不变**；取代关系见
  `../WB-VIDEO-005-PREPRODUCTION/R1-SUPERSEDES.md`。
- 上一轮失败运行误创建的目录已精确清理，前后审计见 `evidence/cleanup-audit.json`
  （目标 `C:\Users\asus\WorkBuddy\2026-11-08-14-19-50\pipeline\yaodao-agent`，清理后 `False`）。

## 审核边界

自动 PASS ≠ 人工 PASS。字幕逐项人工签核仍是 `NEEDS_MANUAL_REVIEW`，
不得使用虚构审核人。真实配音、合法音乐、具名人工复核、导出授权全部**尚未获得**。
本轮完成后停止，交由 ChatGPT 独立审核。
