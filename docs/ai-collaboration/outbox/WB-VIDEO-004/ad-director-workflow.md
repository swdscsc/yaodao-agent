# WB-VIDEO-004 · AI 产品广告导演工作流（可复用规范 v1）

| 项 | 值 |
|---|---|
| 定位 | 独立广告导演模块：让系统**知道什么样的广告才好看**，而不只是"会自动拼接" |
| 适用项目 | 「药到 AI 用药管家」及后续同类产品广告 |
| 运行状态 | **设计规范，尚未执行任何真实广告制作**；本轮不生成正式宣传片 |
| 关联 | `product-ad-editing-guide.md`（剪辑规范）、`recommended-architecture.md`（系统分层）、`subtitle-signoff-fix.md`（质量门） |
| 设计来源 | `skill-research.md` 提取的 6 条 Skill 工作方法（无外部代码依赖） |

---

## 1. 三条不可逾越的红线

1. **产品真实性**：绝不编造产品功能、医疗效果、用户评价、使用数据。任何功能必须标注 `implemented / in_development / concept_demo` 之一。
2. **不冒充**：模拟界面必须画面内明确标注"模拟演示"；测试信号不得冒充真实镜头；占位音频不得冒充旁白；FFmpeg 参考渲染不得冒充剪映成片。
3. **质量否决**：质量总监拥有独立一票否决权；自动 PASS 不等于质量合格，人工逐项签核不可被自动结果顶替。

---

## 2. 六个角色

每个角色是一份独立规范（文件夹式、渐进加载），头部元数据格式：

```yaml
role: <角色标识>
inputs: [<输入契约>]
outputs: [<输出契约>]
veto_power: true|false
requires_approval: [<需人工批准的动作>]
evidence_required: true
```

### 2.1 A · 产品研究员 `product_researcher`

| 项 | 内容 |
|---|---|
| 输入 | 产品资料、界面截图/录屏、需求文档、访谈记录（**用户提供的真实资料，不联网臆测**） |
| 输出 | `product_facts.json`：功能清单、目标用户、痛点、卖点、证据来源、功能状态 |
| 职责 | 读取资料 → 梳理真实功能 → 识别目标用户 → 提炼痛点 → 提取核心卖点 → 区分实现状态 |
| 禁止 | 编造功能 / 医疗效果 / 用户评价 / 使用数据；把"计划做"写成"已有"；无来源的量化表述 |
| 否决权 | 有（对任何未标注真实性状态的卖点可拒绝进入下一环节） |
| 需批准 | 上传含隐私的产品资料、公开发布 |

**功能状态枚举（强制）**：

| 状态 | 含义 | 画面允许程度 |
|---|---|---|
| `implemented` | 有可验证的真实实现/界面 | 可作真实功能展示，需录屏证据 |
| `in_development` | 开发中、未完成 | 只可文字提及进度，不得演示"已可用" |
| `concept_demo` | 概念演示 / 设想 | 必须在画面内标注「概念演示」，不得配"已上线"类旁白 |

`product_facts.json` 最小字段：`feature_id / name / status / evidence_ref / target_user / pain_point / claim_text / claim_type / risk_notes`。`claim_type` 只能是 `functional / emotional / none`；涉及诊断、疗效、治愈率、用户数量的一律 `REJECTED`。

### 2.2 B · 广告创意导演 `creative_director`

| 项 | 内容 |
|---|---|
| 输入 | `product_facts.json` + 投放平台 + 时长 + 横竖屏要求 |
| 输出 | `creative_brief.md`：定位、主题、开场钩子、叙事结构、情绪曲线、产品出现时机、结尾 CTA |
| 职责 | 确定广告定位与设计创意主题；设计前 3 秒钩子；规划叙事结构与情绪变化；设计产品出现时机与行动引导 |
| 禁止 | **所有广告套同一模板**；用长 Logo 开场；用无意义空镜拖时间；承诺疗效 |
| 否决权 | 有（可否决与产品真实性冲突的创意） |
| 需批准 | 涉及真人肖像、真实用户案例、对外发布 |

**创意模板不复用规则**：每次必须从 `creative_patterns` 中选出**与上次不同**的结构，并记录选择理由。可选结构举例（非穷举）：问题→解决、一天时间线、误解→澄清、单一功能深挖、对比前后、场景切片、第一人称提问、物件特写串联。

`emotion_curve` 必须给出至少 4 个带时间码的锚点（如 `0s 困惑 / 4s 安心 / 10s 清晰 / 16s 信任`），供剪辑师安排节奏。

### 2.3 C · 分镜导演 `storyboard_director`

输入：`creative_brief.md` + `product_facts.json`。输出：`shotlist.json`，每个镜头 **22 字段**（任务书 19 项 + 3 个治理字段）。见 §3。

职责：把创意拆成可生成、可质检、可追溯的镜头；为每个镜头写生成提示词与质检要求。
禁止：只写"画面描述"而不写主体动作/景别/运镜/光线/时长；给 AI 生成任务不写一致性组。

### 2.4 D · AI 视觉导演 `visual_director`

| 项 | 内容 |
|---|---|
| 输入 | `shotlist.json` + 候选素材 + 参考帧 |
| 输出 | `visual_consistency.json`：逐镜头一致性判定与畸形/构图检查 |
| 职责 | 人物一致性、场景一致性、产品外观一致性、镜头衔接、光影连续性、色彩风格统一、画面畸形检测、构图与主体位置控制 |
| 硬规则 | 同一人物在连续镜头中**不得**突然换脸、换衣服、改变年龄；产品 UI 不得换配色/布局；同一场景光线方向不得翻转 |
| 禁止 | 把"看起来差不多"写成已验证一致；无参考帧就宣称连续 |
| 否决权 | 有（一致性 FAIL 直接退回素材生成） |
| 需批准 | 任何消耗托管额度的 `generate_asset` 调用 |

一致性校验至少包含：`consistency_group` 分组、跨镜头参考帧像素/特征比对、主体位置与景别连续性、色彩直方图趋势、光影方向标注。程序不可判定项（如"脸是否还是同一个人"）标 `NEEDS_MANUAL_REVIEW`，不自动 PASS。

### 2.5 E · 自动剪辑师 `auto_editor`

| 项 | 内容 |
|---|---|
| 输入 | 通过质检的素材 + `shotlist.json` + 旁白 WAV + 字幕 SRT + 音乐/音效清单 |
| 输出 | 剪映工程（或经授权的参考渲染）+ `edit_decision_list.json` |
| 职责 | 按脚本排镜头顺序；**按旁白长度调整画面**；按音乐节奏安排剪辑点；选择转场；控制镜头节奏；设计字幕动画；安排音效；调整音乐音量；完成调色与片尾包装 |
| 禁止 | **只是把图片依次拼接**；把静态截图当"功能操作过程"；忽略 J/L-cut 与声音桥接；把横屏简单裁成竖屏 |
| 否决权 | 无（受质量总监否决） |
| 需批准 | 剪映 GUI 操作、Host 授权、独立测试草稿创建、任何导出 |

EDL 字段：`clip_id / shot_id / source_asset / in_point / out_point / duration / transition_in / transition_out / audio_ducking / subtitle_animation / speed_ramp / beat_aligned`。剪辑点必须可追溯到音乐节拍或旁白断句，不允许随机等分。

### 2.6 F · 质量总监 `quality_director`

| 项 | 内容 |
|---|---|
| 输入 | 全部阶段产物 + `product_facts.json` + 自动质检报告 |
| 输出 | `qa_verdict.json`：`APPROVED / REJECTED / NEEDS_MANUAL_REVIEW` + 缺陷台账 |
| 职责 | 画面质量、镜头连续性、字幕质量、旁白质量、音画同步、音乐与音效、信息准确性、产品真实性、横屏与竖屏适配 |
| **独立否决权** | ✅ 任一维度 FAIL 即整体 REJECTED，**不受创意/剪辑/进度压力影响**；不得由自动 PASS 覆盖；不得由单一全局人工 APPROVED 顶替 |
| 需批准 | 返工第 3 轮及以后、对外交付 |

质量门与本轮 P0 修复直接对接：字幕缺陷必须满足 `subtitle_checks.py::evaluate_subtitle_fix()` 的 7 个先决条件且三个 `MANUAL_ITEMS` 逐项具名签核，才允许 `FIXED`；否则一律 `REJECTED` 或 `NEEDS_MANUAL_REVIEW`。

---

## 3. 分镜 22 字段 schema（机器可校验）

任务书列出 19 项；本规范补充 3 个治理字段（`feature_status`、`consistency_group`、`safe_area_spec`）。

| # | 字段 | 类型 | 必填 | 校验 / 说明 |
|---|---|---|---|---|
| 1 | `shot_id` | string | ✅ | 唯一，格式 `S###`；禁止重复导入 |
| 2 | `purpose` | string | ✅ | 该镜头在叙事中的作用，不得为空泛词 |
| 3 | `scene` | string | ✅ | 时间 / 地点 / 环境 |
| 4 | `subject` | string | ✅ | 主体（人物 / 产品 / UI） |
| 5 | `subject_action` | string | ✅ | 主体具体动作，**不得写"展示产品"** |
| 6 | `shot_size` | enum | ✅ | 远景/全景/中景/近景/特写/微距 |
| 7 | `camera_movement` | enum | ✅ | 固定/推/拉/摇/移/跟/升降/手持 |
| 8 | `composition` | string | ✅ | 三分法 / 居中 / 引导线 / 留白位置 |
| 9 | `lighting` | string | ✅ | 光源方向、色温、硬软、时段 |
| 10 | `color` | string | ✅ | 主色 / 辅助色 / 情绪色调 |
| 11 | `visual_content` | string | ✅ | 画面里实际出现的东西，供一致性比对 |
| 12 | `narration` | string | ✅ | 对应旁白文本；无旁白写 `null` 并说明 |
| 13 | `subtitle` | string | ✅ | 屏幕字幕（可与旁白不同，需注明） |
| 14 | `sfx` | list | ✅ | 音效清单，含时间点 |
| 15 | `transition` | object | ✅ | `{type, duration, reason}`，转场必须有理由 |
| 16 | `duration_seconds` | number | ✅ | >0；横竖屏可各给一份 |
| 17 | `source_type` | enum | ✅ | `real_footage / real_ui_capture / ai_generated / simulated_ui / test_signal` |
| 18 | `generation_prompt` | string | 条件 | AI 生成必填；含一致性锚点与负面提示 |
| 19 | `qa_requirements` | list | ✅ | 该镜头的专项质检项（含人工项） |
| 20 | `feature_status` | enum | ✅ | `implemented / in_development / concept_demo / not_applicable` |
| 21 | `consistency_group` | string | ✅ | 同组镜头共享人物/场景/产品外观锚点 |
| 22 | `safe_area_spec` | object | ✅ | 横屏与 9:16 竖屏各自的主体/字幕/UI 安全区 |

**强制联动**：`source_type = simulated_ui` 或 `test_signal` 时，画面内必须有可见的标注文字；`feature_status ≠ implemented` 时不得使用"已上线/已可用"类旁白。`shotlist.json` 校验不通过则禁止进入素材生成。

---

## 4. 可复用提示词模板（项目内部资产，无外部依赖）

模板变量用 `{{...}}`；每个角色单独加载，不合并进一次调用。

**A 产品研究员**

```
你是产品研究员。只使用以下提供的资料，不得补充任何外部事实：{{source_material}}
输出 JSON：功能清单、目标用户、痛点、卖点、证据来源。
每个功能必须标记 implemented / in_development / concept_demo。
若资料不足以判断状态，写 unknown 并列入待补证据，禁止推测。
禁止出现诊断、疗效、治愈率、用户数量、用户评价类表述。
```

**B 创意导演**

```
你是广告创意导演。基于 {{product_facts}}，为 {{platform}} / {{duration}}s / {{orientation}} 设计创意。
必须给出：定位、主题、前 3 秒钩子、叙事结构（不得与上一次 {{last_pattern}} 相同，写明选择理由）、
至少 4 个带时间码的情绪锚点、产品出现时机、结尾 CTA。
所有卖点必须引用 feature_id；concept_demo 功能不得写成已可用。
```

**C 分镜导演**

```
你是分镜导演。把 {{creative_brief}} 拆成 22 字段镜头表（见 schema）。
source_type 明确区分真实拍摄 / 真实界面录屏 / AI 生成 / 模拟界面 / 测试信号。
AI 生成镜头必须写 generation_prompt，含人物、服装、场景、产品外观、光线、色彩的一致性锚点与负面提示。
每个镜头给出 qa_requirements，并标注哪些项必须人工复核。
```

**D 视觉导演**

```
你是 AI 视觉导演。按 consistency_group 分组检查 {{candidate_assets}} 与 {{reference_frames}}。
逐项报告：人物脸/服装/年龄、场景、产品外观、光线方向、色彩趋势、镜头衔接、构图与主体位置、畸形。
程序无法可靠判断的项输出 NEEDS_MANUAL_REVIEW，禁止自动 PASS。
任一硬规则违反即 REJECTED 并写明镜头号与证据帧。
```

**E 自动剪辑师**

```
你是自动剪辑师。依据 {{shotlist}} + {{narration_wav}} + {{srt}} + {{music_beats}} 生成 EDL。
镜头时长按旁白断句调整，剪辑点绑定节拍或语义停顿，转场写明理由。
字幕动画、音效、音乐 ducking、调色、片尾包装分别给出参数。
禁止等分切片、禁止把静态截图串成"操作过程"、禁止横屏直接裁竖屏。
```

**F 质量总监**

```
你是质量总监，拥有独立否决权。审查 {{all_artifacts}}。
九个维度逐项给出 PASS / FAIL / NEEDS_MANUAL_REVIEW 与证据。
字幕缺陷必须调用 subtitle_checks.py 的逐项签核门；自动 PASS 不等于合格。
任一 FAIL 即整体 REJECTED，并生成缺陷台账（编号/时间码/严重度/责任模块/修复方案/证据）。
不得因进度压力降级判定。
```

---

## 5. 角色交接与数据流

| 阶段 | 产出 | 下一角色 | 硬门槛 |
|---|---|---|---|
| A 产品研究 | `product_facts.json` | B | 每个功能有状态与证据引用 |
| B 创意 | `creative_brief.md` | C | 情绪曲线 ≥4 锚点、创意结构不与上次重复 |
| C 分镜 | `shotlist.json` | D / E | 22 字段校验通过、真实性标注齐全 |
| D 视觉 | `visual_consistency.json` | E | 无 REJECTED 一致性项 |
| E 剪辑 | EDL + 工程 | F | 素材全部 `allow_edit = true` |
| F 质检 | `qa_verdict.json` | 返工 / 交付 | 逐项人工签核 + 无自动 FAIL |

每次交接写 `state_log`：`from_role / to_role / artifact / sha256 / timestamp / gate_result`，与 `pipeline-status.json` 的状态机一致。

---

## 6. 从 Skill 研究提取的内部规则（落地）

| # | 规则 | 落地位置 |
|---|---|---|
| 1 | 一个角色一份独立规范，不混写 | §2 六节 |
| 2 | YAML 元数据声明输入/输出/否决权/审批 | §2 头部模板 |
| 3 | 渐进加载：按阶段只加载当前角色模板 | §4 分角色模板 |
| 4 | 判断写文档、执行写可独立测试的 Python | `subtitle_checks.py` / `qa.py` |
| 5 | 工具能力分 `READ_ONLY / LOCAL_REVERSIBLE / NEEDS_APPROVAL` 三级 | `recommended-architecture.md` §4 |
| 6 | 输出可验证、可追溯，人工/自动分离 | §5 交接 + `subtitle-signoff-fix.md` |

---

## 7. 当前状态（诚实声明）

- 本文件是**规范与模板**，本轮**没有**执行产品分析、创意策划、真实分镜生成或广告制作。
- 六个角色尚未实现为独立可执行模块；`shotlist.json` / `product_facts.json` / `qa_verdict.json` 是**契约定义**，不是已产出的数据。
- 下一步（WB-VIDEO-005 建议）：先用「药到」的真实资料跑 A→C，产出 1 份 22 字段分镜表与真实性台账，再申请素材生成额度。
- 本规范不依赖任何外部 Skill 代码，可直接在仓库内版本化与审核。
