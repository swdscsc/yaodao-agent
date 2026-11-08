# 产品主张台账（Product Claims Register）· R1 修订版

> 本文件在 R0 与 R1 两个目录中各有一份，**内容完全相同**。`R1` 指 `docs/ai-collaboration/outbox/WB-VIDEO-005-PREPRODUCTION-R1/`。

| 项 | 值 |
|---|---|
| 任务 | WB-VIDEO-005-PREPRODUCTION-**R1**（ChatGPT 独立审核修正） |
| 核对基准 | `334ddbc60a50a794300188fa886d388a85c9edd2`（远端 `main` 最新 HEAD，本轮拉取后确认本地 = 远端） |
| 上一版 | R0 原文逐字节保存在 `R1/evidence/r0-originals/product-claims-register.md` |
| 核对方法 | 只读阅读 `README.md`、`agent.ts`、`src/*.ts`，用符号名 + 行号定位；**没有**运行产品、没有真机演示、没有联网调用产品服务 |
| 结论口径 | 见 §0「R1 分类规则」。**R0 的自相矛盾已修正**：R0 第 8 行写「只有 VERIFIED_SOURCE 与 KNOWN_LIMITATION 可以进旁白」，却把两条 `VERIFIED_DOC_ONLY` 放在「允许写入旁白」的 A 表里 |
| 机器校验 | `evidence/consistency-check.json`：`r1_assertions_all_passed = true`，`errors = []`；逐句旁白 28 句 / **471 字** |
| 本轮执行 | 0 运行产品、0 联网产品调用、0 视频导出、0 安装、0 下载、0 额度、0 GUI |

**证据代码**
- `R` = 仓库 `README.md`（行号）
- `S` = 源码文件（行号为符号定义处）
- `—` = 仓库中找不到证据

**状态枚举（R1 起生效）**

| 状态 | 含义 | 能否作为「已验证事实」进旁白 |
|---|---|---|
| `VERIFIED_SOURCE` | 源码可核实 | **能** |
| `KNOWN_LIMITATION` | 已上线但有限制 | 必须与其对应的 `VERIFIED_SOURCE` **同时**说清 |
| `VERIFIED_DOC_ONLY` | 仅 README / 文档描述，无源码实现证据 | **不能** |
| `DESIGN_INTENT_DOC_ONLY` | 文档描述的是**设计意图 / 提示词约定**，不是已实测的产品能力 | **不能**；只允许以「设计示意」表述，且画面必须常驻标注 |
| `NOT_SHIPPED_ROADMAP` | 路线图，未上线 | 禁止 |
| `UNVERIFIED` | 无任何证据 | 禁止 |
| `EXCLUDED` | 广告禁用 | 禁止 |

---

## 0. R1 分类规则（修正 R0 矛盾）

| 规则 | 内容 |
|---|---|
| R1-C1 | **只有 `VERIFIED_SOURCE` 能作为功能事实被旁白陈述。** |
| R1-C2 | `KNOWN_LIMITATION` 不是独立主张，必须随其对应的 `VERIFIED_SOURCE` 一起出现，隐瞒即构成误导。 |
| R1-C3 | `VERIFIED_DOC_ONLY` / `DESIGN_INTENT_DOC_ONLY` **一律不得**作为已验证事实。若确需提及，只能写成带限定词的设计示意（「按设计」「设计示意」），且画面必须常驻「产品设计示意（非真机 · 非实测）」。 |
| R1-C4 | `NOT_SHIPPED_ROADMAP` / `UNVERIFIED` / `EXCLUDED` 不进旁白，也不进画面文字（S33 的**否定式**免责声明除外）。 |
| R1-C5 | 任何分类变动必须同步到 A 表、A.1 一致性矩阵与 `main-film-shotlist.csv` 的 `truth_label`；由 `R1/scripts/build_deliverables_r1.py` 的 SHOTS 表作为**唯一权威数据源**生成，不允许只改说明文档。 |

> R0 的 A10、A11 违反 R1-C3：它们被列在「A. 允许写入旁白的功能主张」下，状态却是 `VERIFIED_DOC_ONLY`。R1 已把它们移入 §A.2，并改写 N09 / N10。

---

## A. 允许作为已验证功能事实进旁白（`VERIFIED_SOURCE`）

| # | 主张（广告里的说法） | 证据 | 状态 | 旁白/画面落点 | 必须同时标注 |
|---|---|---|---|---|---|
| A01 | 说一句话就能记下服药规律，设备会复述确认 | `R:16`, `R:41`；`S:src/medTools.ts:126` `med_plan_save`（描述含「把返回的 confirm_text 完整念给用户，并问一句『对吗』」） | VERIFIED_SOURCE | N11 N12 / S08 S09 S13 S15 | 功能对话示例 · 非用药建议 |
| A02 | 问「早上吃什么」，按早/午/晚分组回答，不把一天全堆出来 | `R:17`, `R:42`, `R:113`；`S:src/medTools.ts:108 groupPlans`, `:150 med_plan_list` | VERIFIED_SOURCE | N13 / S16 | 模拟界面 |
| A03 | 说「我吃过了」即记录一次打卡，并给温和反馈 | `R:18`, `R:43`；`S:src/medTools.ts:176 med_take` | VERIFIED_SOURCE | N14 / S17 | 模拟界面 · 功能对话示例 |
| A04 | 问今天吃得怎么样，算出「应服 / 已服 / 还差」 | `R:19`, `R:45`；`S:src/medTools.ts:192 med_report`（描述明确「纯本地 KV 计算」） | VERIFIED_SOURCE | N15 / S18 | 示意数据 · 模拟界面 |
| A05 | 说「等会儿再提醒我」，可推迟提醒 | `R:46`；`S:src/medTools.ts:202 med_snooze` | VERIFIED_SOURCE | N16 / S19 | 模拟界面 |
| A06 | 用户**唤醒设备后的下一轮对话**，若存在到期未打卡且未播报过的剂量，会先提醒再回答问题 | `R:156-161`, `R:167`；`S:src/medPromptBuilder.ts:10 MedPromptBuilder`, `S:src/medStore.ts:33 MedStore` | VERIFIED_SOURCE + **KNOWN_LIMITATION** | N17 / S20 | 屏幕常驻「无人唤醒时设备不会自己开口」 |
| A07 | 举药盒拍照 → 识别 → 念出已识别内容 → **一次只问一个**缺失项 → 齐全后落库 | `R:20`, `R:55-71`；`S:src/medicinePhotoHandler.ts`, `S:src/medVision.ts:83 parseVisionOutput`, `:160 nextQuestion`, `S:src/medTools.ts:218/228 med_draft_get/set` | VERIFIED_SOURCE | N18 N19 / S21 S22 | 情景演绎 · 模拟界面 · 识别结果需用户确认 |
| A08 | 问「能不能停药」，回答「这事得问您大夫」；不推荐药物、剂量、疗程 | `R:21`, `R:100-105`；`S:src/medTools.ts:162 med_plan_delete` 描述含「用户只是问能不能停药…应建议咨询医生」 | VERIFIED_SOURCE | N24 N25 / S29 S30 | 功能对话示例 · 非用药建议 |
| A09 | 紧急情况建议拨打 120 并联系家人 | `R:105`；`S:src/*.ts` 中 `120` 出现 9 处（`grep -rho` 实测） | VERIFIED_SOURCE | N25 / S30 | 安全边界文字卡。**注：这是提示语文本，不是急救功能** |
| A12 | 用药数据按设备 ID 隔离存储 | `R:93`；`S:src/medTools.ts` 中 `yaodao.meds.` / `yaodao.doses.` 键 | VERIFIED_SOURCE | **不进旁白**（架构细节，与观众无关） | — |

### A.1 分类 ↔ 旁白实际表述一致性矩阵（审核问题 1 的逐条答案）

「旁白实际表述」取自 `narration-draft.md` / `subtitle-draft.srt`，由同一份 SHOTS 表生成。

| 主张 | 旁白 ID | 旁白实际措辞 | 状态 | 是否一致 | 说明 |
|---|---|---|---|---|---|
| A01 | N11 | 说定了，它把药名和时间复述一遍，问一句『您听听对不对』。 | VERIFIED_SOURCE | ✅ | 复述确认，源码可核实 |
| A01 | N12 | 建档，只要一句话；它会复述，不替您猜。 | VERIFIED_SOURCE | ✅ | 「不替您猜」是复述确认的修辞，非独立功能宣称 |
| A02 | N13 | 问早上吃什么，它只念早饭那一段。 | VERIFIED_SOURCE | ✅ | 对应 `groupPlans` |
| A03 | N14 | 一句『我吃过了』，就算记上；**漏了也不责怪**。 | VERIFIED_SOURCE | ✅ 有条件 | 前半句对应 `med_take`；后半句是**情景演绎的语气**，不作为功能事实 |
| A04 | N15 | 问一句今天吃得怎么样，它算出还差几次，说得清清楚楚。 | VERIFIED_SOURCE | ✅ | 画面须标「示意数据」 |
| A05 | N16 | 正忙着？说一声『等会儿』，它就晚一点再来。 | VERIFIED_SOURCE | ✅ | 对应 `med_snooze` |
| A06 | N17 | 下次唤醒它，到点还没打卡的那一次，它会先提一句。 | VERIFIED_SOURCE + KNOWN_LIMITATION | ✅ | 「下次唤醒它」是限制条件；**没有**写「到点自动提醒」 |
| A07 | N18 | 记不清名字，就把药盒举起来给它看。 | VERIFIED_SOURCE | ✅ | 情景演绎标注 |
| A07 | N19 | 它念出认到的内容，认不清的，一次只问一件。 | VERIFIED_SOURCE | ✅ | 对应 `nextQuestion` |
| A08/A09 | N24 N25 | 有些问题，它不接。／不推荐药，不改剂量；不舒服就让您找家人、找大夫；紧急情况，先拨 120。 | VERIFIED_SOURCE | ✅ | 否定式安全边界，必须保留 |
| **A10** | **N10** | **按设计，它一次只说一件事，说完等你，不打断。** | **DESIGN_INTENT_DOC_ONLY** | ✅ **R1 修订** | R0 原句「它说『您』，一次只说一件事，不着急，也不打断。」是**陈述事实**；R1 加「按设计」限定，画面常驻标注 |
| **A11** | **N09** | **这一段是设计示意，不是真机，也不是录屏。** | **DESIGN_INTENT_DOC_ONLY** | ✅ **R1 修订** | R0 原句「一块放在桌上的小屏，一个能听懂普通话的声音。」含两项无源码证据的宣称；R1 全部删除 |
| A12 | — | 不进旁白 | VERIFIED_SOURCE | ✅ | 架构细节 |
| 叙事旁白 | N07 | 她没打开什么 App，只是说了一句话。 | 非功能主张 | ✅ 保留 | 描述**人物行为**，未宣称硬件形态或识别能力；如 ChatGPT 要求进一步收紧，R2 再处理 |
| 叙事旁白 | N01–N06, N20–N23, N26–N28 | 生活场景、情感、行动引导 | 非功能主张 | ✅ | 不含产品能力宣称 |

---

## A.2 仅可作为设计示意的表述（不得作为已验证事实）

| # | R0 主张 | 证据 | R0 状态 | **R1 状态** | R1 处理 |
|---|---|---|---|---|---|
| A10 | 称呼用户「您」；一次只说一件事；不玩梗、不说教 | `R:25-33`, `R:111-115`（README 的**提示词约定**）；`S` 中无对应实现 | `VERIFIED_DOC_ONLY` | **`DESIGN_INTENT_DOC_ONLY`** | N10 改为「**按设计**，它一次只说一件事…」；S12 画面常驻「产品设计示意（非真机 · 非实测）」；`truth_label` 改为 `ORIGINAL_GRAPHIC / MOCK_UI` |
| A11 | 载体是一块小屏语音设备，不是手机 App | `R:3`, `R:33`, `R:77-90`（README 描述）；`S` 中无硬件证据 | `VERIFIED_DOC_ONLY` | **`DESIGN_INTENT_DOC_ONLY`** | N09 不再描述任何硬件形态；S11 改为原创示意图形并常驻标注；`truth_label` 由 `STILL_LIFE_REQUIRED` 改为 `ORIGINAL_GRAPHIC / MOCK_UI` |

### A.3 N09 / N10 中「无充分源码证据的能力」逐项判定（审核问题 2 的答案）

| R0 原句片段 | 被宣称的能力 | 源码证据 | 判定 | R1 处置 |
|---|---|---|---|---|
| 「一块放在桌上的小屏」 | 具体硬件形态（小屏、桌面摆放） | `—`（仅 README 文字） | 无充分证据 | **删除**，画面只保留原创轮廓示意并标注「非真机」 |
| 「一个能听懂普通话的声音」 | 普通话语音识别能力 | `—`（仓库无 ASR 实现；`R:204` 把方言识别列为「平台能力，启用即可」且无启用证据） | **无充分证据 + 与 C03 相邻风险** | **完全删除**，`R1/scripts/build_deliverables_r1.py` 的 `design_ok` 断言对该字符串 fail-closed |
| 「它说『您』」 | 固定敬语输出 | `—`（仅提示词约定） | 文档意图，非实测 | 删除；改由「按设计」统一限定 |
| 「一次只说一件事，不着急，也不打断」 | 对话节奏控制 | `—`（仅提示词约定） | 文档意图，非实测 | 保留语义，但加「按设计」前缀，不再作为事实陈述 |
| 「N09/N10 画面需真人/真机拍摄」 | — | `—` | 与「不依赖实拍」目标冲突 | S11/S12 改为 `ORIGINAL_GRAPHIC / MOCK_UI`，素材缺口改为「无（可零风险原创绘制）」 |

> **结论**：R1 后 N09 / N10 不再陈述任何产品能力，只陈述「这是设计示意」与「按设计我们希望它怎样」。两者都不构成 `VERIFIED_SOURCE` 事实宣传。

---

## B. 必须一起说清的限制（隐瞒即构成误导）

| # | 限制 | 证据 | 状态 | 处理 |
|---|---|---|---|---|
| B01 | **无人唤醒时设备不会自己开口**；主动提醒发生在用户唤醒后的下一轮对话（云端 Agent 无推送 API） | `R:169`, `R:194` | KNOWN_LIMITATION | S20 屏幕文字明确写出，旁白 N17 用「下次唤醒它」措辞，**不写「到点自动提醒」** |
| B02 | 拍照识别只是辅助，认不清要如实说「没看清」，不臆测药量/疗程 | `R:66`；`S:src/medVision.ts` 含「没看清」4 处 | KNOWN_LIMITATION | S23 「识别结果需您确认」 |
| B03 | KV 按云端实例隔离，换实例靠长期记忆快照兜底，极端情况可能读到稍旧状态 | `R:192` | KNOWN_LIMITATION | 不进旁白，但不得宣称「永不丢失 / 绝对可靠」 |
| B04 | 唤醒词「王道长」可改 | `R:30` | VERIFIED_DOC_ONLY | 不进旁白 |
| B05 | 北京时间 0:00–8:00 的时区边界曾出错，v1.1.0 已修复 | `R:174` | KNOWN_LIMITATION（历史） | 不进旁白；不得据此宣称「零误差」 |

---

## C. 明确未上线 / 禁止宣称

| # | 说法 | 证据 | 状态 | 处理 |
|---|---|---|---|---|
| C01 | 「到点自动开口提醒 / 不用说话它也会提醒」 | `R:194`, `R:202` 明确「仍未实现，需设备端定时 + 云端推送」 | NOT_SHIPPED_ROADMAP | **禁止**；见 B01 |
| C02 | 「家属微信远程报告 / 子女手机能收到周报」 | `R:203` 明确「缺自建服务端」 | NOT_SHIPPED_ROADMAP | **禁止**；C5 子女场景改为「打电话」 |
| C03 | 「方言识别 / 老人乡音也能听懂」 | `R:204` 标为「平台能力，启用即可」，仓库无启用证据 | UNVERIFIED | **禁止**；R1 同时删除 N09 中「能听懂普通话」的能力宣称 |
| C04 | 「已在 XX 个家庭使用 / 依从性提升 X% / 医生推荐」 | — | UNVERIFIED | **禁止**（编造用户评价、市场数据、医疗效果） |
| C05 | 「诊断、治疗建议、疗效、保证按时吃药」 | `R:100` 明确不越界 | EXCLUDED | **禁止**，片尾以否定式声明排除 |
| C06 | 「真实用户界面 / 真机实录」（当前无素材） | `asset-inventory.csv`：真实产品画面 **0 个** | UNVERIFIED | **禁止**；所有界面必须标 `模拟界面` |
| C07 | 示例对白中出现具体药名、剂量、片数 | — | EXCLUDED | **R1 新增禁止**：`降压药` / `一片` 等词由 `consistency_check()` fail-closed 扫描，S30 的否定式「不改剂量」白名单保留 |

---

## D. 文档与源码的差异（如实记录，不用于宣传）

| 项 | README 写法 | 源码实际 | 处理 |
|---|---|---|---|
| 工具数量 | `R:37` 写「5 个本地工具 + 1 个拍照识别处理器」，表格列 6 个工具名 | `src/medTools.ts` 中 `name:` 共 **9** 个：`med_plan_save / list / delete / take / report / snooze / draft_get / draft_set / remind_once` | 差异存在；**广告不宣称任何工具数量** |
| 一次性提醒 | 未列入能力表 | `med_remind_once`（`:251`）支持「X 分钟后提醒我」 | 本片不展示，避免与 B01 混淆 |
| 端侧零固件改动 | `R:92` | 属部署说明，非用户可感知功能 | 不进旁白 |

---

## E. 真实性标注与画面来源规则

| 规则 | 内容 |
|---|---|
| 真实产品画面 | 目前 **0 个**。所有涉及设备的镜头标 `MOCK_UI` 或 `ORIGINAL_GRAPHIC` |
| 产品设计示意 | **R1 新增**：S11 / S12 及任何原创设备图形，画面常驻「产品设计示意（非真机 · 非实测）」 |
| 情景演绎 | 所有有人物表演的生活镜头标 `DRAMATIZATION`，右上角常驻「情景演绎」 |
| 模拟界面 | 所有自绘 UI 标 `MOCK_UI`，常驻「模拟界面」；**不得**称为录屏 |
| 测试素材 | `pipeline/assets/*` 与 `pipeline/renders/*` 共 56 个媒体文件全部是 WB-002 的 FFmpeg 本地合成测试信号 / QA 夹具，`usability_for_final_film = NOT_USABLE_AS_FINAL_FOOTAGE` |
| 药盒品牌 | S21 药盒需虚焦，不出现可辨识的真实药品牌、规格与批号 |
| 数字 | 界面中出现的数字一律标「示意数据」，不出现百分比、样本量、效果对比 |
| 片尾声明 | S33 保持 ≥6 秒：「情景演绎 · 模拟界面 · 本片为功能演示，不提供诊断、治疗建议或疗效承诺」 |

---

## F. 机器校验结果（R1 重跑）

| 项 | 结果 |
|---|---|
| 旁白句数 / 字数 | **28 句 / 471 字**（`CJK Unified Ideographs only (U+4E00-U+9FFF)`，不含标点 / 数字 / 字母） |
| 字数口径 | R0 曾同时出现「约 560 字」（`main-film-script.md:12`，人工估算）与 473（`consistency-check.json`，机器计数）。**R1 统一为唯一机器值 471**，由 `NARRATION_CHAR_COUNT` 从 SHOTS 表计算并注入 `main-film-script.md`、`narration-draft.md`、`narration-revised.md`；不允许任何手写估算 |
| 禁用词逐句扫描 | 0 命中（治愈 / 疗效 / 保证 / 有效率 / 用户评价 / 销量 / 第一 / 最好 / 包治 / 诊断 / 治疗建议） |
| 具体药名 / 剂量 | 0 命中（`降压药` / `一片` / `两片` / `半片` / `毫克` 等 10 个词，覆盖旁白、屏幕文字、画内对白） |
| 设计示意限定 | S11 / S12 旁白含「设计示意 / 按设计」，屏幕含「产品设计示意」，断言通过 |
| cue ID 唯一性 | 16 条对白 → 16 个唯一 ID；`r1_assertions_all_passed = true` |
| 一致性检查 | `errors = []`，`all_consistency_checks_passed = true`；14 处双轨时间码重叠作为 warnings 明示 |

> 自动扫描只覆盖字面词，**不等于人工合规审核**。正式制作前仍需具名人工复核。

---

## G. R1 修订摘要

| 审核项 | R0 问题 | R1 修正 | 落点 |
|---|---|---|---|
| 1 | 分类口径自相矛盾、A10/A11 分类与旁白表述不一致 | 新增 §0 五条分类规则 + §A.1 逐条一致性矩阵，A10/A11 移出 A 表 | 本文件 + SHOTS 表 |
| 2 | N09/N10 把无源码证据的能力当事实宣传 | 改写两句旁白、删除「能听懂普通话」、S11/S12 改原创示意图形并常驻标注 | `narration-draft.md`、`main-film-shotlist.csv`、`main-film-script.md` |
| 3 | 473 与 560 两个字数并存 | 统一为机器值 471，所有文档由同一常量注入 | 上述三份文档 + `R1/evidence/character-count-audit.json` |
| 4 | S04/S16 多条对白共用一个 `<镜头>-D` ID | 改为 `<镜头>-D<两位序号>`，生成 `dialogue-cue-index.csv`，新增唯一性断言 | SRT meta、consistency-check、cue index |
| 5 | 示例对白含「降压药 / 一片」 | 改为不含药名、剂量的通用示例，并加 fail-closed 扫描 | 主片 SRT、竖屏 V04/V05、脚本、镜头表 |
| 6 | 一致性检查未覆盖上述修正 | 新增 4 组 R1 断言并重跑 | `evidence/consistency-check.json` |

> 完整逐条修订记录见 `R1/review-revision-log.md`。
