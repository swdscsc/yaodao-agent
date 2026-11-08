#!/usr/bin/env python3
"""Generate the two prose deliverables from the authoritative SHOTS table.

Keeps the human-written creative direction, but derives every timecode,
narration line, dialogue line and label from build_deliverables.SHOTS so the
Markdown, the CSV and the SRT cannot disagree.
"""
from __future__ import annotations

import json
import os
import re
import shutil

from build_deliverables_r1 import (SHOTS, OUT, R1_OUT, EVID, timecode, char_count,
                                   CHAR_COUNT_RULE, NARRATION_CHAR_COUNT,
                                   NARRATION_SENTENCE_COUNT)

SCRIPT_HEAD = """# 《药到 · 不用学，只要说》主宣传片 · 逐镜头脚本

| 项 | 值 |
|---|---|
| 任务 | WB-VIDEO-005-PREPRODUCTION · 阶段 1 |
| 状态 | **脚本 / 分镜 / 剪辑准备，不是成片**；本轮未导出任何视频 |
| 目标时长 | 240.0 s（4:00，落在 3–5 分钟要求内） |
| 画幅 / 帧率 | 1920×1080（16:9）/ 25 fps 全片统一 |
| 编码 | H.264（`libx264`, yuv420p, CRF 18–20）/ AAC 48 kHz stereo 192 kbps |
| 语言 | zh-CN 普通话 |
| 镜头数 | 33 镜 / 8 章 |
| 旁白 | __SENTENCES__ 句，共 __CHARS__ 字（__RULE__；机器校验见 `evidence/consistency-check.json`）；留白约 100 s 给画面、音乐与画内台词 |
| 可执行版本 | `main-film-shotlist.csv`（19 列，含素材来源/缺口/真实性标签/转场/节奏） |
| 字幕 | `subtitle-draft.srt`（主旁白轨）+ `evidence/dialogue-subtitle-draft.srt`（对白轨），均为 **DRAFT，未烧录** |

---

## 1. 定位与创意

- **产品**：药到 · 给爸妈的 AI 用药管家（服务长辈日常用药记录与提醒）。**硬件形态在本片中只以「产品设计示意」呈现，不宣称真机或实测能力**（R1 修订，见 `product-claims-register.md`）。
- **核心创意**：把「记得吃药」这句话，从子女反复的叮嘱，还给老人自己说出口。
- **一句话梗概**：一个总是答不上「今天吃没吃」的早晨，因为一句自然说出口的话，变成了一天里能被自己说清的三顿饭。
- **品牌记忆点**：`药到 · 不用学，只要说` / `老人不会用智能手机，但一定会说话`。
- **差异化**：不卖远程监控，不卖「AI 有多懂你」，卖**它知道自己不该管什么**。
- 创意来源与排除项见 `creative-research.md`；可写入旁白的功能边界见 `product-claims-register.md`。

---

## 2. 叙事结构

| 章 | 时间 | 时长 | 作用 | 情绪 |
|---|---|---|---|---|
| C0 冷开场 | 00:00–00:18 | 18 s | 只有物件与光，不出现产品 | 静 |
| C1 痛点 | 00:18–00:52 | 34 s | 一通电话、一张药单、一条发不出去的关心 | 微微发紧 |
| C2 转折 | 00:52–01:14 | 22 s | 她只是说了一句话；品牌第一次出现 | 松开 |
| C3 产品形态 | 01:14–01:42 | 28 s | 一块小屏、一个声音、一次只说一件事 | 清楚 |
| C4 核心功能 | 01:42–02:42 | 60 s | 7 组「人说一句 → 设备答一句」 | 稳定节奏 |
| C5 一天 | 02:42–03:18 | 36 s | 早/午/晚时间流，回应 C1 那通电话 | 暖 |
| C6 安全边界 | 03:18–03:44 | 26 s | 它不接什么问题；把限制讲成可信度 | 郑重 |
| C7 落版 | 03:44–04:00 | 16 s | 品牌句 + 行动引导 + 合规声明 | 留白 |

**起承转合检查**：C0/C1 提问题 → C2 给转折 → C3/C4 给证据 → C5 给情感回报 → C6 主动收边界 → C7 收束。功能段不被拆散到片尾，也不机械重复开场镜头。

---

## 3. 视觉规范

| 维度 | 规范 |
|---|---|
| 色彩 | 暖米白 `#F6F1E8` 为底；木色 `#C8A98A`；豆绿 `#7E9B86` 作信息色；陶土橙 `#D98E5F` 只用于药盒/便利贴等少量强调。**不使用蓝紫渐变、冷光 UI、粒子光效** |
| 光线 | 自然光为主，晨光偏清、午后与夜晚偏暖；同一桌面用光变完成时间流逝（C5） |
| 构图 | 大量留白；人物以侧面/肩背/手部为主，不做直视镜头的证言式表演；产品只占画面 1/3，不炫技 |
| 字体 | 本机已装 `Noto Sans SC` / `Deng` / `msyh` 系列；标题用 Medium/Bold，正文用 Regular；**不使用**装饰性手写体 |
| 字幕安全区 | 左右各留 10%；字幕带下沿 **≤ 0.90 H**，基线不越过 0.88 H；字号 @1080p **≥ 40 px**；单行 ≤ 20 字，最多 2 行；描边/半透明底保证在亮背景可读 |
| 双轨位置 | 主旁白轨 0.86 H；画内对白轨 0.72 H，两者不同行、不堆叠 |
| 文字动画 | 字幕淡入 6 帧、淡出 6 帧；关键词用下划线划过，**不做**弹跳/缩放/打字机 |
| 转场 | 以声音先行（J-cut）与尾音延续（L-cut）为主；章节间用物件匹配切（药格 ↔ 卡片 ↔ 屏幕方形）；淡入淡出只用于品牌卡，8–12 帧 |
| 品牌统一 | 全片只出现两次品牌字卡（S10、S32）；所有功能卡的编号、左对齐、字号、留白一致 |
| 禁用 | 测试彩条、合成图案、静态图片循环、同一素材反复凑时长 |

> 字幕阈值来自历史缺陷 D004（横屏底部 0.947 H 越 0.94 安全线、竖屏 26 px < 32 px、竖屏字幕中心 0.6208 H）。本方案把三条都收紧，避免复现。

---

## 4. 声音设计

| 项 | 设计 | 当前状态 |
|---|---|---|
| 旁白 | 成熟、平实的普通话；约 4 字/秒；不朗诵、句尾不抬调；C6 语速再放慢 | **未产出**：本机无可用中文配音通道，见 `first-cut-readiness.md` |
| 音乐 | 极简钢琴单音 → 弦乐铺底 → C5 主题完整 → C6 全段无音乐 → C7 收束和弦 | **未解决**：`pipeline/renders/bgm.wav` 是 WB-002 合成测试音，不可用于成片；需合法授权或原创制作 |
| 音效 | 只用生活质感：纸张、水杯、快门（极轻）、单记木琴；**不用**「成功提示」电子音、转场 whoosh | 需制作或取自合法音效库 |
| 响度 | 目标约 −16 LUFS，真峰值 ≤ −1 dBTP；**旁白比音乐高 ≥ 12 dB**；C6 无音乐段单独复查 | 待导出后实测 |
| J-cut / L-cut | S03→S04 铃声提前 0.6 s；S07→S08 提示音提前；S14 弦乐提前进 C4；S12/S16/S22/S31 用 L-cut 让尾音压到下一镜 | 已在分镜逐镜标注 |
| 静音段 | 只允许刻意留白（S03、S07、S27、S29），导出后须用 `silencedetect` 逐段确认是设计而非事故 | 待质检 |

---

## 5. 导出与质检参数（供阶段 2 复用，本轮不执行）

- 容器 MP4；`-c:v libx264 -pix_fmt yuv420p -r 25 -crf 18`；`-c:a aac -ar 48000 -b:a 192k`；`-movflags +faststart`。
- 解码完整性、`volumedetect`、`silencedetect`、`freezedetect`（白名单只允许 S03/S07/S27/S29 的刻意静止）、帧率一致性、字幕烧录前后像素差、安全区与遮挡检查。
- 字幕逐项人工签核沿用 WB-004 的 `per_item_signoff_v1`：**自动 PASS ≠ 人工 PASS**，不得使用虚构审核人。
- 横竖屏分别导出，竖屏独立构图（见 `vertical-cut-plan.md`），不得裁切横屏。

---

## 6. 真实性标注（每镜强制）

| 标签 | 含义 | 呈现 |
|---|---|---|
| `DRAMATIZATION` | 情景演绎 | 右上角常驻「情景演绎」 |
| `MOCK_UI` | 模拟界面，非真机录屏 | 常驻「模拟界面」 |
| `PRODUCT_UI_REQUIRED` / `STILL_LIFE_REQUIRED` | 需要真实产品画面，当前**缺失** | 分镜中标记缺口，不得用测试素材顶替 |
| `ORIGINAL_GRAPHIC` / `TEXT_CARD` / `BRAND_CARD` | 原创文字/图形，可零风险绘制 | 片尾统一声明 |
| 功能对话示例 | 涉及药名/餐次/剂量的演示对话 | 「功能对话示例 · 非用药建议」 |

片尾 S33 保持 ≥6 秒：`情景演绎 · 模拟界面 · 本片为功能演示，不提供诊断、治疗建议或疗效承诺`。

---

## 7. 逐镜头脚本

> 以下每镜字段与 `main-film-shotlist.csv` 由同一份数据表生成，时间码、旁白、字幕、真实性标签不会互相矛盾。
> **所有 `MISSING` 项都还没有素材**，不是「已经有画面」。

"""

NARRATION_HEAD = """# 完整中文旁白稿（DRAFT · 未录制）

| 项 | 值 |
|---|---|
| 任务 | WB-VIDEO-005-PREPRODUCTION |
| 状态 | **文案草稿**。**没有任何旁白音频文件**；本文件不是配音，也不是字幕成品 |
| 句数 / 字数 | __SENTENCES__ 句，共 __CHARS__ 字（__RULE__）；机器校验见 `evidence/consistency-check.json`，逐句字数见 `evidence/narration-table.md` |
| 时间码 | 按 240 s 计划片长与约 4 字/秒估算，**必须在真实配音完成后重新对齐** |
| 字幕 | `subtitle-draft.srt` 与主旁白逐句一一对应（由同一数据表生成）；画内对白另见 `evidence/dialogue-subtitle-draft.srt` |
| 合规 | 无疗效、诊断、治疗保证、用户评价、市场数据、效果数字；`evidence/consistency-check.json` 逐句扫描 0 命中 |

---

## 1. 配音要求

- **音色**：成熟、温和的普通话，不年轻化、不播音腔、不撒娇；像家里人说话，不像广告配音。
- **语速**：约 4 字/秒，句间留出真实停顿；C0 更慢，C4 功能段保持稳定，C6 再放慢，`120` 三个字必须清楚。
- **情绪**：C0 平视、C1 克制（不怜悯）、C2 松开、C4 清楚不兴奋、C5 暖但不煽情、C6 郑重、C7 收住。
- **断句**：不把「饭前 / 饭后」「早 / 午 / 晚」连读成词串；引号内的话略作停顿，但不改变音色去「演」角色。
- **技术**：无爆音、无喷麦、无明显底噪、无 >0.5 s 意外静音；首尾不截断；导出后跑 `volumedetect` / `silencedetect` 并人工试听。
- **禁止**：机器朗读式的等长停顿、把「AI」读成夸张重音、在句尾统一上扬。

---

## 2. 合规约束（逐句适用）

1. 只说仓库里能核实的功能（见 `product-claims-register.md` A 组）。
2. 不说「到点自动提醒」（实际是唤醒后的下一轮对话，见 B01）。
3. 不说家属微信周报、方言识别、任何用户数/百分比（C02–C04）。
4. 不出现诊断、治疗建议、疗效承诺；不推荐任何药物、剂量或疗程。
5. 引号内的功能对话是**示例**，画面须同时标注「功能对话示例 · 非用药建议」。
6. 「情景演绎」与「模拟界面」在画面上标注，旁白不负责澄清，也不能反过来暗示画面是真实的。

---

## 3. 逐句旁白

"""

NARRATION_TAIL = """
---

## 4. 画内台词（对白轨，非旁白）

> 这些句子由画面里的人物/设备说出，单独一条字幕轨；文本同样来自同一份镜头表。
> 涉及餐次、用药安排的示例对话在画面上必须标注「功能对话示例 · 非用药建议」。
> **R1 修订**：每条对白分配一个全局唯一 `cue ID`，与 `evidence/dialogue-cue-index.csv` 一一对应，
> 不再用同一个 `<镜头>-D` 代表同镜的多条对白。

| cue ID | 镜头 | 时间码 | 台词 | 标注 |
|---|---|---|---|---|
"""

SCRIPT_TAIL = """
---

## 8. 与其他交付物的关系

| 文件 | 关系 |
|---|---|
| `main-film-shotlist.csv` | **执行版**：19 列完整剪辑指令，本文件第 7 节是其可读版 |
| `subtitle-draft.srt` | 主旁白字幕轨，28 条，与本文件逐句一致 |
| `evidence/dialogue-subtitle-draft.srt` | 画内对白轨，16 条 |
| `narration-draft.md` | 配音稿与逐句合规约束 |
| `vertical-cut-plan.md` | 独立的 9:16 版本，不是本片的裁切 |
| `first-cut-readiness.md` | 第一段 15–30 秒能否开剪的真实结论 |
| `evidence/consistency-check.json` | 时间码连续、旁白↔字幕一致、禁用词、素材/标签完整性的机器校验 |

## 9. 本脚本尚未解决的事

1. **没有任何真实产品画面**：所有 `MOCK_UI` / `MISSING` 镜头需要真实录屏或明确标注的原创示意图。
2. **没有中文旁白音频**、**没有合法 BGM/SFX**。
3. **没有拍摄素材**：C0/C1/C5 的生活场景全部待拍或待以合法原创视觉替代。
4. **时间码是计划值**，需在真实配音后重排；`evidence/subtitle-draft.meta.json` 已标出 __COLLISIONS__ 处同镜对白/旁白时间码重叠，须在剪辑阶段用双轨错位解决。
5. 本轮按 `WB-VIDEO-005-preproduction.md` 授权，**不导出视频、不上传 MP4**。

> 脚本完成 ≠ 视频已剪好。这句话在本项目里必须按字面理解。
"""


def fill(text: str) -> str:
    """Inject the ONE machine-counted narration length everywhere it is stated."""
    with open(os.path.join(EVID, "subtitle-draft.meta.json"), encoding="utf-8") as f:
        collisions = json.load(f)["same_shot_timecode_collisions"]
    return (text.replace("__SENTENCES__", str(NARRATION_SENTENCE_COUNT))
                .replace("__CHARS__", str(NARRATION_CHAR_COUNT))
                .replace("__RULE__", CHAR_COUNT_RULE)
                .replace("__COLLISIONS__", str(collisions)))


def build_script_md() -> None:
    parts = [fill(SCRIPT_HEAD)]
    current_chapter = None
    for s in SHOTS:
        if s["chapter"] != current_chapter:
            current_chapter = s["chapter"]
            parts.append(f"### {current_chapter}\n\n")
        parts.append(f"#### {s['id']} · {timecode(s['tin'])}–{timecode(s['tout'])} · {s['tout']-s['tin']} s\n\n")
        parts.append(f"- **镜头目的**：{s['purpose']}\n")
        parts.append(f"- **画面 / 景别运镜**：{s['visual']} ｜ {s['camera']}\n")
        parts.append(f"- **屏幕文字**：{s['screen']}\n")
        if s["narration"]:
            parts.append(f"- **旁白 {s['nid']}**：「{s['narration']}」\n")
        else:
            parts.append("- **旁白**：—（留白）\n")
        parts.append(f"- **画内台词**：{' ／ '.join(d[0] for d in s['dialogue']) if s['dialogue'] else '—'}\n")
        parts.append(f"- **音乐 / 音效**：{s['music']}\n")
        parts.append(f"- **素材来源**：{s['source']}\n")
        parts.append(f"- **素材缺口**：{s['gap']}\n")
        parts.append(f"- **真实性标签**：`{s['truth']}`\n")
        parts.append(f"- **转场 / 节奏**：{s['trans']} ｜ {s['rhythm']}\n\n")
    parts.append(fill(SCRIPT_TAIL))
    with open(os.path.join(OUT, "main-film-script.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("".join(parts))


def build_narration_md() -> None:
    parts = [fill(NARRATION_HEAD)]
    parts.append("| ID | 镜头 | 时间码 | 字数 | 预计时长 | 旁白文本 | 语气 / 合规 |\n")
    parts.append("|---|---|---|---|---|---|---|\n")
    for s in SHOTS:
        if not s["narration"]:
            continue
        n = char_count(s["narration"])
        parts.append(
            f"| {s['nid']} | {s['id']} | {timecode(s['tin'])}–{timecode(s['tout'])} | {n} | "
            f"≈{n/4.0:.1f} s | {s['narration']} | 平实、句尾不抬调；无疗效/诊断/数据/评价 |\n"
        )
    parts.append(fill(NARRATION_TAIL))
    for s in SHOTS:
        for idx, (text, _off, _dur) in enumerate(s["dialogue"], 1):
            label = "功能对话示例 · 非用药建议" if any(
                k in text for k in ("药", "吃", "饭", "提醒")) else "情景演绎"
            cue_id = f"{s['id']}-D{idx:02d}"
            parts.append(f"| {cue_id} | {s['id']} | {timecode(s['tin'])}–{timecode(s['tout'])} "
                         f"| {text} | {label} |\n")
    parts.append(fill("""
---

## 5. 时间码声明

- 全部时间码是**按脚本估算的计划值**，不是从音频波形测出的实测值。
- `evidence/consistency-check.json` 已校验：33 镜时间码连续无空隙、总长 240.0 s、28 句旁白与 28 条主字幕逐字一致、每条字幕都落在自己镜头内。
- `evidence/subtitle-draft.meta.json` 记录了 **__COLLISIONS__ 处**同镜内旁白与对白的计划时间码重叠；这些不是错误，而是双轨字幕在真实配音后必须重排的位置。
- 一旦拿到真实配音，须重跑对齐并**重新生成** SRT，不得沿用本草稿冒充已对齐字幕。

## 6. 配音未产出声明

本轮**没有**生成任何语音文件。仓库与本地工作区中唯一的 WAV 语音相关文件是
`pipeline/tts004/audio_chain_test_tone.wav`（440 Hz 正弦测试音，WB-004 明确标注「不是语音、不是旁白」），
以及 `pipeline/renders/bgm.wav` / `sfx.wav`（WB-002 合成测试音）。三者**都不允许**作为本片旁白或配乐。
"""))
    with open(os.path.join(OUT, "narration-draft.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("".join(parts))


def main() -> None:
    build_script_md()
    build_narration_md()

    # R1 deliverable copies with an explicit version banner.
    banner = ("> **R1 修订版（WB-VIDEO-005-PREPRODUCTION-R1）**：本文件为预制作修订后的权威稿，"
              "取代 R0 对应文件。N09 / N10 已限定为产品设计示意，具体药名与剂量已从示例对白移除，"
              f"旁白统一为 {NARRATION_SENTENCE_COUNT} 句 / {NARRATION_CHAR_COUNT} 字（{CHAR_COUNT_RULE}）。"
              "逐条修订见 `review-revision-log.md`。**本轮仍没有任何旁白音频、没有导出视频。**\n\n")
    src = open(os.path.join(OUT, "narration-draft.md"), encoding="utf-8").read()
    lines = src.split("\n")
    lines.insert(1, banner.rstrip())
    with open(os.path.join(R1_OUT, "narration-revised.md"), "w",
              encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))
    shutil.copyfile(os.path.join(OUT, "subtitle-draft.srt"),
                    os.path.join(R1_OUT, "subtitle-draft-revised.srt"))
    shutil.copyfile(os.path.join(EVID, "dialogue-subtitle-draft.srt"),
                    os.path.join(R1_OUT, "dialogue-subtitle-revised.srt"))
    print(json.dumps({
        "narration_characters": NARRATION_CHAR_COUNT,
        "narration_sentences": NARRATION_SENTENCE_COUNT,
        "rule": CHAR_COUNT_RULE,
        "generated": ["main-film-script.md", "narration-draft.md",
                       "narration-revised.md", "subtitle-draft-revised.srt",
                       "dialogue-subtitle-revised.srt"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
