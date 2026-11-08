# 首段重新选择（不沿用 S08–S10）

| 项 | 值 |
|---|---|
| 评估对象 | 主片全部 **33 镜**（`scripts/build_deliverables_r1.py` :: SHOTS） |
| 硬门槛通过 | **17 镜** |
| 枚举的 15–30 s 连续片段 | **68 个** |
| 选中 | **S14-S17 · 96-123 s → 相对 0–27 s** |
| 选中片段评分 | rank 1 / score 195.0，4/4 镜全通过硬门槛 |
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
| S01 | 0–6 | DRAMATIZATION | ❌ | H1_no_live_action、H3_original_graphic_or_mock_ui、H5_source_backed_claim_or_no_claim |
| S02 | 6–12 | DRAMATIZATION | ❌ | H1_no_live_action、H3_original_graphic_or_mock_ui、H5_source_backed_claim_or_no_claim |
| S03 | 12–18 | DRAMATIZATION | ❌ | H1_no_live_action、H3_original_graphic_or_mock_ui |
| S04 | 18–26 | DRAMATIZATION | ❌ | H1_no_live_action、H3_original_graphic_or_mock_ui、H5_source_backed_claim_or_no_claim |
| S05 | 26–34 | DRAMATIZATION | ❌ | H1_no_live_action、H3_original_graphic_or_mock_ui、H5_source_backed_claim_or_no_claim |
| S06 | 34–43 | DRAMATIZATION / MOCK_UI | ❌ | H1_no_live_action、H5_source_backed_claim_or_no_claim |
| S07 | 43–52 | DRAMATIZATION | ❌ | H1_no_live_action、H3_original_graphic_or_mock_ui、H5_source_backed_claim_or_no_claim |
| S08 | 52–59 | DRAMATIZATION | ❌ | H1_no_live_action、H3_original_graphic_or_mock_ui |
| S09 | 59–66 | MOCK_UI | ✅ | — |
| S10 | 66–74 | BRAND_CARD | ✅ | — |
| S11 | 74–81 | ORIGINAL_GRAPHIC / MOCK_UI | ✅ | — |
| S12 | 81–88 | ORIGINAL_GRAPHIC / MOCK_UI | ✅ | — |
| S13 | 88–96 | MOCK_UI | ✅ | — |
| S14 | 96–102 | TEXT_CARD | ✅ | — |
| S15 | 102–109 | MOCK_UI | ✅ | — |
| S16 | 109–116 | MOCK_UI | ✅ | — |
| S17 | 116–123 | MOCK_UI | ✅ | — |
| S18 | 123–130 | MOCK_UI | ✅ | — |
| S19 | 130–137 | MOCK_UI | ✅ | — |
| S20 | 137–145 | DRAMATIZATION / MOCK_UI | ❌ | H1_no_live_action |
| S21 | 145–152 | DRAMATIZATION | ❌ | H1_no_live_action、H3_original_graphic_or_mock_ui |
| S22 | 152–159 | MOCK_UI | ✅ | — |
| S23 | 159–162 | MOCK_UI | ✅ | — |
| S24 | 162–170 | DRAMATIZATION | ❌ | H1_no_live_action、H3_original_graphic_or_mock_ui、H5_source_backed_claim_or_no_claim |
| S25 | 170–178 | DRAMATIZATION | ❌ | H1_no_live_action、H3_original_graphic_or_mock_ui、H5_source_backed_claim_or_no_claim |
| S26 | 178–186 | DRAMATIZATION | ❌ | H1_no_live_action、H3_original_graphic_or_mock_ui、H5_source_backed_claim_or_no_claim |
| S27 | 186–192 | DRAMATIZATION | ❌ | H1_no_live_action、H3_original_graphic_or_mock_ui |
| S28 | 192–198 | DRAMATIZATION / STILL_LIFE_REQUIRED | ❌ | H1_no_live_action、H2_no_real_device_capture、H3_original_graphic_or_mock_ui、H5_source_backed_claim_or_no_claim |
| S29 | 198–206 | MOCK_UI | ✅ | — |
| S30 | 206–215 | TEXT_CARD | ✅ | — |
| S31 | 215–224 | DRAMATIZATION / TEXT_CARD | ❌ | H1_no_live_action、H5_source_backed_claim_or_no_claim |
| S32 | 224–232 | BRAND_CARD | ✅ | — |
| S33 | 232–240 | BRAND_CARD / TEXT_CARD | ✅ | — |

> R1 修订让 S11 / S12 从「需真机/人物实拍」变成原创设计示意图形，因此也通过 H1–H5；
> 但它们不在最优连续片段内，未入选首段。

## 3. 15–30 s 候选片段（按 score 排序，前 10）

| 排名 | 片段 | 时长 | 全镜通过 | 源码主张数 | 字幕 cue | 转场类型 | J/L-cut | 分数 |
|---|---|---|---|---|---|---|---|---|
| 1 | S14-S17 | 27 s | ✅ | 3 | 7 | 4 | J1/L1 | 195.0 |
| 2 | S15-S18 | 28 s | ✅ | 4 | 9 | 3 | J0/L2 | 193.5 |
| 3 | S16-S19 | 28 s | ✅ | 4 | 9 | 3 | J0/L2 | 193.5 |
| 4 | S13-S16 | 28 s | ✅ | 2 | 6 | 4 | J1/L1 | 185.5 |
| 5 | S12-S15 | 28 s | ✅ | 1 | 4 | 4 | J1/L1 | 173.5 |
| 6 | S15-S17 | 21 s | ✅ | 3 | 7 | 3 | J0/L1 | 173.0 |
| 7 | S14-S16 | 20 s | ✅ | 2 | 5 | 3 | J1/L1 | 171.5 |
| 8 | S16-S18 | 21 s | ✅ | 3 | 7 | 2 | J0/L2 | 171.0 |
| 9 | S17-S19 | 21 s | ✅ | 3 | 6 | 3 | J0/L1 | 170.0 |
| 10 | S10-S13 | 30 s | ✅ | 1 | 4 | 4 | J0/L1 | 166.5 |

`score = 100（全镜通过）+ 6×源码主张数 + 剪辑展示分 − |时长−25|×0.5`；
剪辑展示分 = 3×字幕 cue + 8×转场类型 + 6×J-cut + 6×L-cut + 5×章节/品牌卡 + 2×声音设计 cue。

## 4. 为什么选 S14-S17

| 维度 | 实际内容 |
|---|---|
| 时长 | 27 s（落在 15–30 s） |
| 镜头 | S14, S15, S16, S17，主片 96-123 s |
| 硬门槛 | 4/4 全通过：`TEXT_CARD` + 3× `MOCK_UI`，0 真人实拍、0 真机拍摄 |
| 源码证据 | A01 一句话建档 + 复述确认 (med_plan_save)；A02 按餐次分组查询 (med_plan_list)；A03 打卡与温和反馈 (med_take) |
| 原创动态图形 | S14 三张「早 / 午 / 晚」卡片依次落位（已有 3 个动画状态关键帧） |
| 明确标注的模拟界面 | S15/S16/S17 常驻「模拟界面 · 非真机录屏」「功能对话示例 · 非用药建议」「示意数据」 |
| 字幕 | 3 条主旁白 + 4 条画内对白 = **7 条双轨字幕**；S16 的两条对白正好验证 R1-4 的唯一 cue ID |
| 转场 | 4 类：匹配切（卡片方形→功能编号方形）、硬切、L-cut（上一镜尾音压入）、J-cut（S14 弦乐提前进 C4） |
| 声音设计 | 4 镜各有设计：三记轻打击音、章节低音、功能编号提示音、列表轻音、勾选木琴音；旁白比音乐高 ≥12 dB |
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
| G4 | 字幕与真实音频对齐 | 当前 SRT 是计划时间码，4 处双轨重叠待重排 | **否** |

> 因此本轮交付的是**素材、时间线、字幕、制作清单**，不是成片。0 个 MP4。
