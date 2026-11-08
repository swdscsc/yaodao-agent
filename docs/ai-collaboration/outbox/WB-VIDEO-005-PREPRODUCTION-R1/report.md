# WB-VIDEO-005-PREPRODUCTION-R1 执行报告

| 项 | 值 |
|---|---|
| 任务 | ChatGPT 独立审核修正（6 项）+ 首段重选 + 原创素材准备 |
| 基准 | 远端 `main` HEAD `334ddbc60a50a794300188fa886d388a85c9edd2`；本轮拉取确认本地 = 远端、工作区干净 |
| 性质 | **预制作修订，不是成片制作** |
| 结论 | 6 项审核问题全部修正并落到权威数据源；首段重新选定；原创素材已生成；**未导出视频** |
| 机器校验 | `errors = 0`，`all_consistency_checks_passed = true`，`r1_assertions_all_passed = true` |
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

## 2. 六项审核修正（全部落在权威数据源）

权威数据源是 `scripts/build_deliverables_r1.py` 的 `SHOTS` 表（33 镜）。
所有旁白、字幕、镜头表、脚本、台账、证据均由该表重新生成，不是只改说明文档。
逐条记录见 `review-revision-log.md`，摘要：

| # | 修正 | 机器结果 |
|---|---|---|
| 1 | 台账分类口径重写 + §A.1 分类↔旁白一致性矩阵 | A10/A11 移入 `DESIGN_INTENT_DOC_ONLY` |
| 2 | N09/N10 改为设计示意表述，删除「能听懂普通话」，S11/S12 改原创图形 | `design_intent_qualifiers_present = true` |
| 3 | 字数统一为唯一机器值 | **28 句 / 471 字**（CJK Unified Ideographs only (U+4E00-U+9FFF); punctuation, digits, Latin letters and whitespace excluded）；560 与 473 仅作为废弃历史值留证 |
| 4 | 对白 cue ID 唯一化 | 16 条对白 → 16 个唯一 ID；`collision_pairs_unique = true` |
| 5 | 移除具体药名与剂量 | `specific_drug_or_dosage_removed = true`，10 词 fail-closed 扫描 0 命中 |
| 6 | 一致性检查新增 4 组 R1 断言并重跑 | `errors = 0`，warnings 14（双轨时间码重叠，明示不隐藏） |

**保留上一轮**：11 份修订前原文在 `evidence/r0-originals/`
（含 SHA-256）；10 份历史报告与原始证据字节不变
（`report.md`、`first-cut-readiness.md`、`asset-probe.json`、`capability-probe.json`、
`manifest.sha256.json`、`push-verification*.json` 等）。取代关系见
R0 目录新增的 `R1-SUPERSEDES.md`。

## 3. 首段重新选择

对全部 33 镜按 5 条单镜硬门槛判定（17 镜通过），
枚举出 68 个 15–30 s 连续片段并按剪辑展示指标评分。

**选定 S14-S17 · 96-123 s → 相对 0–27 s**（rank 1，score 195.0）：

- 4/4 镜全通过硬门槛，`TEXT_CARD` + 3× `MOCK_UI`，**0 真人实拍 / 0 真机拍摄**。
- 源码证据：A01 一句话建档 + 复述确认 (med_plan_save)；A02 按餐次分组查询 (med_plan_list)；A03 打卡与温和反馈 (med_take)。
- 字幕 7 条（3 旁白 + 4 对白）、
  4 类转场、J-cut/L-cut 各 1/1、4 镜声音设计。
- R0 的 S08–S10 因依赖实拍与真机被明确否决，未机械沿用。详见 `first-cut-selection.md`。

## 4. 实际生成的文件

| 类别 | 数量 | 内容 |
|---|---|---|
| 文档 | 11 | README、修订记录、台账、旁白稿、首段选择、制作清单、素材来源、音乐音效方案、最小授权、报告、R0 指针 |
| 可编辑图形源 | 6 | 5 个原创 SVG（含字幕安全区）+ 1 个 HTML/CSS 模拟界面 |
| 原创动态图形关键帧 | 9 | 1920×1080 PNG，FFmpeg `drawbox`+`drawtext`，9 个动画状态，**不是视频** |
| 时间线 / 字幕 | 3 | `first-cut-timeline.csv`（4 行）、主旁白 SRT（3 条）、对白 SRT（4 条） |
| 修订后的主片派生物 | 10 | 镜头表、主字幕、对白字幕、旁白稿、脚本、竖屏方案、台账、cue index、meta、narration table |
| 证据 JSON | 见 `evidence/` | 一致性、字数审计、首段评分、cue index、渲染日志、素材清单、清理审计、留存台账、位置测试、敏感扫描、SHA-256 清单、推送回读 |
| **MP4 / 音频** | **0 / 0** | 无成片、无配音、无配乐 |

所有关键帧与界面都常驻「模拟界面 · 非真机录屏」「功能对话示例 · 非用药建议」
「示意数据」「预制作素材 · 非成片」标注；**未使用任何 WB-002 测试素材或彩条占位**。

## 5. 测试结果

| 测试 | 结果 |
|---|---|
| 一致性检查（时间码 / 旁白↔字幕 / 禁用词 / 标签完整性 / R1 断言） | `0` errors，`14` warnings，`all_passed = true` |
| 生成器跨目录测试 | 见 `evidence/generator-location-tests.json` |
| 关键帧渲染 | 9/9 成功，全部 1920×1080，`mp4_written = 0` |
| 首段评分 | 33 镜 / 68 候选 / 选中 S14-S17 |
| 敏感信息扫描 | 见 `evidence/secret-scan.json`（0 命中） |
| SHA-256 清单 | `evidence/manifest.sha256.json` |
| 远端回读 | 提交后用 commit-pinned raw URL 逐文件校验，见 `evidence/push-verification.json` |

> **自动 PASS ≠ 人工 PASS**。字幕逐项人工签核、画面试看、音频听审全部未执行，
> 不得使用虚构审核人。

## 6. 真实 / 测试 / 模拟素材区分

| 类别 | 内容 |
|---|---|
| 真实 | 产品功能依据（README + `src/*.ts` 源码，只读）；本机 FFmpeg 与已安装中文字体 |
| 本轮原创 | 5 SVG、1 HTML、9 PNG、时间线、SRT、全部文档与脚本 |
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
4. 首段 4 处双轨字幕重叠是计划时间码，需真实配音后重排；是否接受双轨 0.72H / 0.86H 错位方案。
5. 关键帧是 PNG 动画状态帧，不是连续动态图形片段；是否要求下阶段在获得导出授权后把它们渲染为真实动效片段。
6. 音乐方案 P3 的具体库名与许可条款未核实（本轮不扩展研究、不下载）；是否批准后续逐条核实。

## 9. 红线计数

0 付费 / 0 充值 / 0 安装 / 0 下载 / 0 模型 / 0 额度 / 0 剪映 GUI / 0 草稿修改 /
0 明文凭据 / 0 公开发布 / **0 MP4 导出** / 0 虚构审核人 / 0 测试素材冒充。

> 本轮完成后停止，等待 ChatGPT 独立审核与用户明确授权后再进入阶段 2。
