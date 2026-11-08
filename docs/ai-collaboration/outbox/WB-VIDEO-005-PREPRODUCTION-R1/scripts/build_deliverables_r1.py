#!/usr/bin/env python3
"""WB-VIDEO-005-PREPRODUCTION-R1 deliverable builder (review-revision build).

R1 changes (all traceable in ../outbox/WB-VIDEO-005-PREPRODUCTION-R1/review-revision-log.md):
  R1-1  claims policy made consistent: DOC_ONLY claims may NOT be stated as facts
  R1-2  N09 / N10 reworded as explicitly labelled product DESIGN INTENT
  R1-3  one single machine-counted narration character count, injected everywhere
  R1-4  every in-scene dialogue cue gets a globally unique cue ID
  R1-5  drug name / dosage removed from all example dialogue
  R1-6  consistency check re-run with new fail-closed assertions

Generates the machine-checkable artefacts from ONE authoritative shot table so
that timecodes, narration and subtitles cannot drift apart:

  - main-film-shotlist.csv
  - subtitle-draft.srt          (clean, standards-compliant, DRAFT status in meta)
  - narration-draft.md          (narration section, hand-written prose wrapper added separately)
  - asset-inventory.csv         (from evidence/asset-probe.json)
  - evidence/consistency-check.json
  - evidence/subtitle-draft.meta.json

No video is rendered. No asset is modified. No network / install / GUI / credentials.
"""
from __future__ import annotations

import csv
import json
import os
import re
import shutil
from datetime import datetime

def _find_workspace() -> str:
    """Locate the workspace by walking up until yaodao-agent/ exists.

    This keeps the script runnable both from pipeline/probe005/r1/ (working
    copy) and from the committed scripts/ snapshot inside the repository.
    """
    p = os.path.abspath(__file__)
    for _ in range(10):
        p = os.path.dirname(p)
        candidate = os.path.join(p, "yaodao-agent")
        if (os.path.isdir(os.path.join(candidate, ".git"))
                and os.path.isdir(os.path.join(candidate, "docs", "ai-collaboration", "inbox"))):
            return p
    raise RuntimeError("workspace root containing the real yaodao-agent git repo not found")


WORKSPACE = _find_workspace()
REPO = os.path.join(WORKSPACE, "yaodao-agent")
OUT = os.path.join(REPO, "docs", "ai-collaboration", "outbox", "WB-VIDEO-005-PREPRODUCTION")
EVID = os.path.join(OUT, "evidence")
R1_OUT = os.path.join(REPO, "docs", "ai-collaboration", "outbox",
                      "WB-VIDEO-005-PREPRODUCTION-R1")
R1_EVID = os.path.join(R1_OUT, "evidence")

# One and only one character-count rule. Every document that states a narration
# length MUST use this exact function; no hand-written "about N characters".
CHAR_COUNT_RULE = "CJK Unified Ideographs only (U+4E00-U+9FFF); punctuation, " \
                  "digits, Latin letters and whitespace excluded"


def char_count(text: str) -> int:
    return len(re.sub(r"[^\u4e00-\u9fff]", "", text))


# NARRATION_CHAR_COUNT is computed once, right after the SHOTS table below.

# ---------------------------------------------------------------------------
# Authoritative shot table. Fields are deliberately explicit so the CSV is a
# directly executable editing instruction, not a mood board.
# truth_label vocabulary:
#   DRAMATIZATION        acted everyday-life scene, must be labelled on screen
#   MOCK_UI              simulated product interface, must be labelled on screen
#   PRODUCT_UI_REQUIRED  needs a REAL product capture (currently MISSING)
#   ORIGINAL_GRAPHIC     original typography / motion graphic, zero external assets
#   TEXT_CARD            chapter / safety text card
#   BRAND_CARD           end card
#   STILL_LIFE_REQUIRED  needs real object photography (currently MISSING)
# ---------------------------------------------------------------------------

SHOTS: list[dict] = [
    # C0 cold open 0-18
    dict(id="S01", chapter="C0 冷开场", tin=0, tout=6,
         purpose="用一个没有台词的早晨把观众放进真实生活，而不是放进科技感",
         visual="清晨厨房桌面：三只药盒、一副老花镜、一张写了又划掉的手写药单；自然侧光，浅景深",
         camera="微距横移，从药盒移到药单，f/2.8 左右",
         screen="情景演绎（右上角常驻小字）",
         nid="N01", narration="早上七点半，桌上有三盒药，一张写了又划掉的单子。",
         dialogue=[], music="只有环境音：窗外鸟声、水杯落桌；钢琴单音在第 4 秒进入",
         source="MISSING: 真实生活场景实拍", gap="真实药盒/桌面/手部实拍或已授权的原创画面",
         truth="DRAMATIZATION", trans="硬切进入", rhythm="慢，6 秒不给任何解释"),
    dict(id="S02", chapter="C0 冷开场", tin=6, tout=12,
         purpose="把'记不清'具体化到可看见的细节，不靠旁白喊痛点",
         visual="手指沿药单上的『早 / 午 / 晚』划过，停在被划掉的一行；老花镜下的说明书小字失焦",
         camera="手部特写 + 焦点从手指移到小字",
         screen="情景演绎",
         nid="N02", narration="哪盒饭前，哪盒饭后，昨天到底吃没吃——",
         dialogue=[], music="钢琴单音延续，加一声很轻的纸张摩擦",
         source="MISSING: 真实生活场景实拍", gap="手部/药单特写实拍",
         truth="DRAMATIZATION", trans="同场景内匹配切（手指动作接手指动作）", rhythm="稍紧，句尾留 1.5 秒空白"),
    dict(id="S03", chapter="C0 冷开场", tin=12, tout=18,
         purpose="留白，让观众自己补上那句没说出口的话",
         visual="老人抬头看墙上的钟，没有说话；画面在暖光里停住",
         camera="中近景，固定机位，轻微手持呼吸感",
         screen="情景演绎",
         nid="", narration="", dialogue=[],
         music="环境音为主，钢琴停一拍；第 16 秒起极轻的弦乐铺底（J-cut 提前进 C1）",
         source="MISSING: 真实生活场景实拍", gap="人物实拍（可不露正脸，肩背/侧影即可）",
         truth="DRAMATIZATION", trans="声音先行 J-cut：下一段电话铃在 17.4 秒提前入", rhythm="全片第一次留白"),
    # C1 pain 18-52
    dict(id="S04", chapter="C1 痛点", tin=18, tout=26,
         purpose="用一通电话把'远距离照护'的无力感讲清楚，双方都没有错",
         visual="电话响起，老人接起；切到子女在通勤车厢里，一手扶杆一手举着手机",
         camera="过肩镜头切手持中景，两个空间用冷/暖轻微区分",
         screen="情景演绎",
         nid="N03", narration="电话那头问一句『今天吃药了吗』，这头常常答不上来。",
         dialogue=[("妈，今天药吃了吗？", 1.0, 2.2), ("……吃了吧。", 3.4, 1.8)],
         music="铃声淡出后弦乐低音持续；地铁环境音短暂叠入",
         source="MISSING: 双场景实拍", gap="老人室内 + 子女通勤两个实拍场景",
         truth="DRAMATIZATION", trans="L-cut：上一场钟声余音拖入本场", rhythm="对话留真实停顿，不抢拍"),
    dict(id="S05", chapter="C1 痛点", tin=26, tout=34,
         purpose="把'不是不上心'说出口，避免把老人拍成无能",
         visual="三连特写：字很小的说明书、贴了又撕的便利贴、按早中晚分好的分药盒",
         camera="三个微距定点，各 2 秒左右",
         screen="情景演绎",
         nid="N04", narration="不是不上心。是字太小，规矩太多，一天要记好几回。",
         dialogue=[], music="每切一次给一记极轻的纸/塑料触感音效，不叠音乐",
         source="MISSING: 物件实拍", gap="说明书/便利贴/分药盒微距实拍",
         truth="DRAMATIZATION", trans="节奏切（三个定点击点）", rhythm="短促，形成全片第一次节奏抬升"),
    dict(id="S06", chapter="C1 痛点", tin=34, tout=43,
         purpose="让年轻观众认出自己，而不是被说教",
         visual="子女翻聊天记录，一屏都是『记得吃药』；打了几个字又删掉，最后还是发出同一句",
         camera="手机屏幕俯拍特写 + 人物虚焦侧脸",
         screen="情景演绎 · 模拟聊天界面",
         nid="N05", narration="在外的人，能做的也只剩再发一句『记得吃药』。",
         dialogue=[], music="手机输入法轻音；弦乐收窄到单声部",
         source="MISSING: 手机界面与人物实拍", gap="原创模拟聊天界面（须标注）+ 人物实拍",
         truth="DRAMATIZATION / MOCK_UI", trans="匹配切：上一镜便利贴的方形接手机屏幕的方形", rhythm="放慢，给一句之后 2 秒静默"),
    dict(id="S07", chapter="C1 痛点", tin=43, tout=52,
         purpose="完成从痛点到主张的转身，不出现产品",
         visual="镜头退回桌面全景，药盒静静摆着；窗外光往前移了一寸",
         camera="固定机位，缓慢拉远",
         screen="情景演绎",
         nid="N06", narration="可这件事，本来不该靠谁替她记着。",
         dialogue=[], music="弦乐停，只留环境音；第 50 秒起一记很轻的设备提示音提前入（J-cut）",
         source="MISSING: 真实生活场景实拍", gap="同一桌面的空镜实拍",
         truth="DRAMATIZATION", trans="声音桥接进入 C2", rhythm="全片第二次留白，9 秒"),
    # C2 turn 52-74
    dict(id="S08", chapter="C2 转折", tin=52, tout=59,
         purpose="全片的价值支点：不学新东西，只要开口",
         visual="老人对着桌上的小屏设备自然地说了一句话；没有点按、没有菜单",
         camera="侧面中近景，固定，浅景深；设备只占画面右下三分之一",
         screen="情景演绎 · 功能对话示例 · 非用药建议",
         nid="N07", narration="她没打开什么 App，只是说了一句话。",
         dialogue=[("早饭后的那一次，帮我记上。", 3.0, 2.6)],
         music="提示音落下后钢琴重新进入，音区更亮",
         source="MISSING: 人物与设备同框实拍", gap="真实设备/外观画面；若无，须以『模拟界面』明确标注",
         truth="DRAMATIZATION", trans="硬切，声音先入 0.4 秒", rhythm="第一次出现产品，但不给特写、不炫技"),
    dict(id="S09", chapter="C2 转折", tin=59, tout=66,
         purpose="展示产品最被看重的行为：复述确认，而不是自作主张",
         visual="设备屏幕以极简文字卡显示复述内容；语音波形轻轻起伏",
         camera="屏幕正面微距，缓慢推近 5%",
         screen="模拟界面 · 功能对话示例 · 非用药建议",
         nid="", narration="",
         dialogue=[("您听听对不对：早饭后那一次。", 1.0, 3.4)],
         music="每出现一行字给一记木琴单音；弦乐不进",
         source="ORIGINAL_GRAPHIC: 可用本机字体与图形原创绘制（须标注模拟界面）",
         gap="真实设备 UI 录屏（优先）；缺失时以模拟界面替代并逐镜标注",
         truth="MOCK_UI", trans="L-cut：上一句尾音与提示音重叠", rhythm="慢，让复述听清"),
    dict(id="S10", chapter="C2 转折", tin=66, tout=74,
         purpose="品牌第一次也是唯一一次正式亮相",
         visual="暖白背景，『药到』二字与一行小字『不用学，只要说』；无任何光效粒子",
         camera="静态字卡，字重极缓淡入",
         screen="药到 · 不用学，只要说",
         nid="N08", narration="药到。不用学，只要说。",
         dialogue=[], music="钢琴落一个完整和弦，之后留 3 秒空白",
         source="ORIGINAL_GRAPHIC: 原创字体排版", gap="品牌标准字（如已有 VI 需提供）",
         truth="BRAND_CARD", trans="淡入淡出各 8 帧", rhythm="品牌落版不加旁白堆叠"),
    # C3 product form 74-102
    dict(id="S11", chapter="C3 产品形态", tin=74, tout=81,
         purpose="R1 修订：先向观众说明这是产品设计示意，不把硬件形态当已验证事实",
         visual="原创绘制的设备形态示意图：只保留轮廓与留白，不出现品牌、型号、真实界面",
         camera="静态图形缓慢淡入，无实拍运镜",
         screen="产品设计示意（非真机 · 非实测）· 模拟界面",
         nid="N09", narration="这一段是设计示意，不是真机，也不是录屏。",
         dialogue=[], music="钢琴回到单音，环境音有水杯轻响",
         source="ORIGINAL_GRAPHIC: 原创示意图形（R1 起不再依赖真机外观素材）",
         gap="无（可零风险原创绘制）；若要展示真机须另行提供真实素材并重新标注",
         truth="ORIGINAL_GRAPHIC / MOCK_UI", trans="匹配切：字卡留白接桌面留白", rhythm="稳，7 秒不切"),
    dict(id="S12", chapter="C3 产品形态", tin=81, tout=88,
         purpose="R1 修订：把适老化讲成设计意图，而不是已实测的产品能力",
         visual="原创信息图形：三行设计原则逐行落位，每次只出现一行；无人物实拍",
         camera="静态图形，逐行淡入",
         screen="产品设计示意（非真机 · 非实测）· 模拟界面：一次只显示一行",
         nid="N10", narration="按设计，它一次只说一件事，说完等你，不打断。",
         dialogue=[], music="无音乐，只留环境音与极轻提示音",
         source="ORIGINAL_GRAPHIC: 原创设计原则图形（R1 起不再依赖人物实拍）",
         gap="无（可零风险原创绘制）；原则来自 README 提示词约定，非实测结论",
         truth="ORIGINAL_GRAPHIC / MOCK_UI", trans="L-cut：旁白尾音压到下一镜", rhythm="放慢，体现'不着急'"),
    dict(id="S13", chapter="C3 产品形态", tin=88, tout=96,
         purpose="讲清复述确认机制，为后面所有功能建立信任",
         visual="语音波形 → 结构化文字卡（药名/时间）→ 一行『您听听对不对？』",
         camera="图形动效，横向 3 段推进",
         screen="模拟界面 · 功能对话示例 · 非用药建议",
         nid="N11", narration="说定了，它把药名和时间复述一遍，问一句『您听听对不对』。",
         dialogue=[], music="三段各一记木琴单音，音量低于旁白 ≥12 dB",
         source="ORIGINAL_GRAPHIC: 原创信息图形", gap="真实交互录屏（优先）",
         truth="MOCK_UI", trans="图形横向 wiped 与下一段餐次卡对齐", rhythm="信息密度最高的一镜，字幕不得遮挡图形主体"),
    dict(id="S14", chapter="C3 产品形态", tin=96, tout=102,
         purpose="用物件匹配切进入功能章节，建立章节节奏",
         visual="『早 / 午 / 晚』三张卡片依次落位，卡片形状与药盒分格一致",
         camera="俯拍定格动画感，逐张落下",
         screen="早 · 午 · 晚",
         nid="", narration="", dialogue=[],
         music="三记轻打击音，弦乐在第三记后进入（J-cut 提前进 C4）",
         source="ORIGINAL_GRAPHIC: 原创文字卡", gap="无（可零风险原创绘制）",
         truth="TEXT_CARD", trans="匹配切：卡片方形 → 功能编号方形", rhythm="全片最轻快的 6 秒"),
    # C4 functions 102-162
    dict(id="S15", chapter="C4 核心功能", tin=102, tout=109,
         purpose="功能 01：一句话建档 + 复述确认（源码 med_plan_save）",
         visual="屏幕出现『功能 01 / 一句话建档』，下方一句对话与复述结果两行",
         camera="正面屏幕构图，固定",
         screen="功能 01 一句话建档 · 模拟界面 · 功能对话示例 · 非用药建议",
         nid="N12", narration="建档，只要一句话；它会复述，不替您猜。",
         dialogue=[("早饭后的那一次，帮我记上。", 1.2, 2.4)],
         music="章节低音铺底，功能编号出现时一记提示音",
         source="MOCK_UI / ORIGINAL_GRAPHIC", gap="真实设备交互录屏（优先）",
         truth="MOCK_UI", trans="硬切，编号统一左对齐", rhythm="功能段统一 7 秒/镜，形成可预期的节奏"),
    dict(id="S16", chapter="C4 核心功能", tin=109, tout=116,
         purpose="功能 02：按早/午/晚分组查询（源码 med_plan_list）",
         visual="只列出『早饭』一组的三行，其余餐次灰掉不显示",
         camera="屏幕构图同 S15，保持位置一致",
         screen="功能 02 按餐次查询 · 模拟界面 · 功能对话示例",
         nid="N13", narration="问早上吃什么，它只念早饭那一段。",
         dialogue=[("早上该吃什么？", 1.0, 2.0), ("早饭这一段，就这些。", 3.2, 2.0)],
         music="保持低音，只在列表出现时一记轻音",
         source="MOCK_UI / ORIGINAL_GRAPHIC", gap="真实设备交互录屏（优先）",
         truth="MOCK_UI", trans="L-cut：上一镜复述尾音压入", rhythm="保持 7 秒网格"),
    dict(id="S17", chapter="C4 核心功能", tin=116, tout=123,
         purpose="功能 03：打卡与温和反馈（源码 med_take）",
         visual="一行『我吃过了』→ 一个勾选标记与一句鼓励",
         camera="同构图，勾选动效 6 帧完成",
         screen="功能 03 吃过就记上 · 模拟界面 · 功能对话示例",
         nid="N14", narration="一句『我吃过了』，就算记上；漏了也不责怪。",
         dialogue=[("我吃过了。", 1.0, 1.8)],
         music="勾选音用木琴，不用'成功提示'电子音",
         source="MOCK_UI / ORIGINAL_GRAPHIC", gap="真实设备交互录屏（优先）",
         truth="MOCK_UI", trans="硬切 + 勾选动效承接", rhythm="7 秒网格"),
    dict(id="S18", chapter="C4 核心功能", tin=123, tout=130,
         purpose="功能 04：当日依从性小结（源码 med_report，纯本地 KV 计算）",
         visual="三行数字卡：应服 / 已服 / 还差；不出现任何百分比或疗效暗示",
         camera="同构图，数字逐行淡入",
         screen="功能 04 当日小结 · 模拟界面 · 示意数据",
         nid="N15", narration="问一句今天吃得怎么样，它算出还差几次，说得清清楚楚。",
         dialogue=[("我今天吃药情况怎样？", 1.0, 2.2)],
         music="低音加一层很轻的拨弦",
         source="MOCK_UI / ORIGINAL_GRAPHIC", gap="真实设备交互录屏（优先）",
         truth="MOCK_UI", trans="L-cut", rhythm="7 秒网格"),
    dict(id="S19", chapter="C4 核心功能", tin=130, tout=137,
         purpose="功能 05：稍后提醒（源码 med_snooze，5–120 分钟）",
         visual="一个时钟图形从当前刻度向后滑一小段，不标注具体分钟数",
         camera="同构图",
         screen="功能 05 等会儿再提醒 · 模拟界面 · 功能对话示例",
         nid="N16", narration="正忙着？说一声『等会儿』，它就晚一点再来。",
         dialogue=[("等会儿再提醒我。", 1.0, 2.0)],
         music="时钟滑动时一记很轻的摩擦音",
         source="MOCK_UI / ORIGINAL_GRAPHIC", gap="真实设备交互录屏（优先）",
         truth="MOCK_UI", trans="硬切", rhythm="7 秒网格"),
    dict(id="S20", chapter="C4 核心功能", tin=137, tout=145,
         purpose="功能 06：到药提醒，必须同时说清边界（源码 MedPromptBuilder；README 已知限制）",
         visual="人物唤醒设备，屏幕先出现一条提醒再回答问题；旁边一行常驻小字说明触发条件",
         camera="人物与设备同框，中景",
         screen="功能 06 到药提醒 · 唤醒后的下一轮对话提醒，无人唤醒时设备不会自己开口 · 模拟界面",
         nid="N17", narration="下次唤醒它，到点还没打卡的那一次，它会先提一句。",
         dialogue=[], music="提示音用与 S08 同一音色，形成呼应",
         source="MISSING: 人物与设备同框", gap="真实设备/人物实拍或明确标注的模拟画面",
         truth="DRAMATIZATION / MOCK_UI", trans="J-cut：提示音提前 0.5 秒进入", rhythm="8 秒，本段唯一被拉长的一镜，因为要说清限制"),
    dict(id="S21", chapter="C4 核心功能", tin=145, tout=152,
         purpose="功能 07a：拍照建档入口（源码 MedicinePhotoHandler）",
         visual="老人把药盒举到设备前；画面只给盒子的色块与形状，不出现可辨识的品牌与规格文字",
         camera="过肩看药盒，浅景深虚化文字",
         screen="功能 07 拍个照记上 · 情景演绎 · 功能对话示例",
         nid="N18", narration="记不清名字，就把药盒举起来给它看。",
         dialogue=[("帮我拍个照记上。", 1.0, 2.0)],
         music="快门音极轻，不用相机特效音",
         source="MISSING: 人物与药盒实拍", gap="人物/道具实拍；药盒须无真实品牌露出",
         truth="DRAMATIZATION", trans="硬切", rhythm="7 秒网格"),
    dict(id="S22", chapter="C4 核心功能", tin=152, tout=159,
         purpose="功能 07b：一项一项确认（源码 medVision 缺项提问）",
         visual="屏幕只出现一个问题：『是饭前吃还是饭后吃呀？』，其余字段保持空白",
         camera="屏幕正面，固定",
         screen="功能 07 一次只问一件 · 模拟界面 · 功能对话示例 · 非用药建议",
         nid="N19", narration="它念出认到的内容，认不清的，一次只问一件。",
         dialogue=[("是饭前吃还是饭后吃呀？", 1.0, 2.8)],
         music="只留问题出现时的一记单音，其余静默",
         source="MOCK_UI / ORIGINAL_GRAPHIC", gap="真实设备交互录屏（优先）",
         truth="MOCK_UI", trans="L-cut", rhythm="7 秒网格"),
    dict(id="S23", chapter="C4 核心功能", tin=159, tout=162,
         purpose="把'识别只是辅助'讲完，避免观众误以为它能替代医嘱",
         visual="卡片收拢，屏幕留白；一行小字：识别结果需您确认",
         camera="同构图，缓慢淡出",
         screen="识别结果需您确认 · 模拟界面",
         nid="", narration="", dialogue=[], music="音乐收窄到单声部，留出转场空白",
         source="ORIGINAL_GRAPHIC", gap="无（可零风险原创绘制）",
         truth="MOCK_UI", trans="淡出 8 帧，声音桥接进入 C5", rhythm="3 秒短呼吸"),
    # C5 a day 162-198
    dict(id="S24", chapter="C5 一天", tin=162, tout=170,
         purpose="用一天的时间流证明功能不是列表，而是能过完的日子",
         visual="早：粥、水杯、药盒；光是清冷的晨光",
         camera="桌面 45 度俯拍，缓慢下移",
         screen="情景演绎 · 早",
         nid="N20", narration="一天还是那些事：早饭、午饭、晚饭。",
         dialogue=[], music="水声、碗筷声先于画面 0.6 秒进入（J-cut）；钢琴主题完整呈现",
         source="MISSING: 生活场景实拍", gap="三个时段的同机位实拍",
         truth="DRAMATIZATION", trans="同机位光变匹配切（晨→午）", rhythm="整段放慢，回到生活速度"),
    dict(id="S25", chapter="C5 一天", tin=170, tout=178,
         purpose="把主动权交还给老人，这是全片的情感转折",
         visual="午：光变暖，老人自己开口问，没有人提醒她",
         camera="侧面中景，机位与 S08 呼应但略远",
         screen="情景演绎 · 午",
         nid="N21", narration="只是现在，她自己问得清，也自己答得上。",
         dialogue=[("早上那盒，我吃过了。", 1.4, 2.2)],
         music="弦乐加入，音量仍低于旁白 ≥12 dB",
         source="MISSING: 人物实拍", gap="人物实拍（可与 S08 同场景一次拍摄）",
         truth="DRAMATIZATION", trans="L-cut：老人说话声压到下一镜", rhythm="留 2 秒空白再进下一场"),
    dict(id="S26", chapter="C5 一天", tin=178, tout=186,
         purpose="回应 C1 的那通电话，完成叙事闭环",
         visual="晚：电话再响，老人笑着答话，语气笃定；桌上灯是暖的",
         camera="过肩中近景，与 S04 构图镜像",
         screen="情景演绎 · 晚",
         nid="N22", narration="电话再响的时候，那句『吃了』，终于不用猜。",
         dialogue=[("吃了，早上那盒也吃了。", 2.6, 2.4)],
         music="钢琴主题回到 C0 的动机，但更完整",
         source="MISSING: 人物实拍", gap="与 S04 同一场景的补拍",
         truth="DRAMATIZATION", trans="镜像构图与 S04 形成呼应", rhythm="本段情绪最高点，不加音效"),
    dict(id="S27", chapter="C5 一天", tin=186, tout=192,
         purpose="给子女观众一个不需要台词的释放",
         visual="子女在车厢里把手机贴回耳边，肩膀松下来，窗外灯流过",
         camera="手持中景，轻微晃动后稳住",
         screen="情景演绎",
         nid="", narration="", dialogue=[], music="弦乐上扬后收住，只留车窗环境音",
         source="MISSING: 通勤场景实拍", gap="与 S04 同一场景的补拍",
         truth="DRAMATIZATION", trans="J-cut：下一镜的静物环境音提前入", rhythm="6 秒无旁白"),
    dict(id="S28", chapter="C5 一天", tin=192, tout=198,
         purpose="把产品从'机器'退回成'家里的一个位置'",
         visual="空镜：药盒、老花镜、小屏设备同框，没有人",
         camera="固定机位，浅景深",
         screen="情景演绎",
         nid="N23", narration="牵挂没变少，只是有了一个能被听见的地方。",
         dialogue=[], music="钢琴落单音，弦乐退出",
         source="MISSING: 静物实拍", gap="真实设备或标注的产品示意图",
         truth="DRAMATIZATION / STILL_LIFE_REQUIRED", trans="淡出 10 帧进 C6", rhythm="慢，6 秒"),
    # C6 safety 198-224
    dict(id="S29", chapter="C6 安全边界", tin=198, tout=206,
         purpose="用一次真实的'拒绝'建立可信度：这是全片最不像广告的 8 秒",
         visual="屏幕只出现一问一答两行，没有任何装饰动效",
         camera="屏幕正面，固定，不推近",
         screen="模拟界面 · 功能对话示例 · 非用药建议",
         nid="N24", narration="有些问题，它不接。",
         dialogue=[("这药能停了吗？", 1.0, 2.0), ("这事得问您大夫，我不敢替您拿主意。", 3.2, 3.4)],
         music="全段无音乐，只留环境音",
         source="MOCK_UI / ORIGINAL_GRAPHIC", gap="真实设备交互录屏（优先）",
         truth="MOCK_UI", trans="硬切，从暖调生活直接切到留白界面", rhythm="刻意的冷场，8 秒"),
    dict(id="S30", chapter="C6 安全边界", tin=206, tout=215,
         purpose="逐条说明安全边界，避免任何疗效或诊疗暗示",
         visual="三行文字依次出现：不推荐药物/剂量/疗程；不舒服建议联系家人或就医；紧急情况建议拨打 120",
         camera="静态字卡，左对齐，无动画",
         screen="安全边界（逐条列出）",
         nid="N25", narration="不推荐药，不改剂量；不舒服就让您找家人、找大夫；紧急情况，先拨 120。",
         dialogue=[], music="无音乐；每行出现时一记极轻的纸面触感音",
         source="ORIGINAL_GRAPHIC: 原创文字卡", gap="无（可零风险原创绘制）",
         truth="TEXT_CARD", trans="硬切", rhythm="9 秒，语速放慢，确保 120 听清"),
    dict(id="S31", chapter="C6 安全边界", tin=215, tout=224,
         purpose="把品牌边界收成一句人话",
         visual="回到桌面空镜，光比 C0 更暖；屏幕文字只有一行",
         camera="固定机位，浅景深，缓慢下移 5%",
         screen="只做提醒 · 记录 · 复述 · 转述医生嘱咐",
         nid="N26", narration="它管的不是病，是那句总被忘掉的『记得』。",
         dialogue=[], music="钢琴最后一次出现主题，弦乐在句尾轻轻进来",
         source="MISSING: 静物实拍", gap="与 S01 同机位空镜",
         truth="DRAMATIZATION / TEXT_CARD", trans="L-cut 进落版", rhythm="9 秒，句尾留 3 秒"),
    # C7 end 224-240
    dict(id="S32", chapter="C7 落版", tin=224, tout=232,
         purpose="品牌记忆点，用产品自己的那句话收束",
         visual="暖白底，『药到』+『不用学，只要说』；右下角小字标注本片性质",
         camera="静态字卡，极缓淡入",
         screen="药到 · 不用学，只要说",
         nid="N27", narration="老人不会用智能手机，但一定会说话。",
         dialogue=[], music="钢琴收束和弦，之后留白",
         source="ORIGINAL_GRAPHIC: 原创字体排版", gap="品牌标准字（如已有 VI 需提供）",
         truth="BRAND_CARD", trans="淡入 12 帧", rhythm="8 秒"),
    dict(id="S33", chapter="C7 落版", tin=232, tout=240,
         purpose="行动引导 + 合规声明，不虚构购买渠道、用户评价或效果数据",
         visual="同一暖白底，主句居中；底部三行小字为合规声明与项目说明",
         camera="静态字卡，保持到片尾黑场 0.5 秒",
         screen="今天，给爸妈打个电话，问一句：今天吃药了吗。／情景演绎 · 模拟界面 · 本片为功能演示，不提供诊断、治疗建议或疗效承诺 · 项目说明见仓库文档（开发者信息）",
         nid="N28", narration="今天，给爸妈打个电话，问一句：今天吃药了吗。",
         dialogue=[], music="钢琴尾音自然衰减，不加片尾音效",
         source="ORIGINAL_GRAPHIC: 原创字体排版", gap="无（可零风险原创绘制）",
         truth="BRAND_CARD / TEXT_CARD", trans="末帧保持 1 秒后黑场", rhythm="8 秒，不叠信息"),
]

TITLE = "药到 · 给爸妈的 AI 用药管家"
MAIN_DURATION = 240.0
NARRATION_CHAR_COUNT = sum(char_count(s["narration"]) for s in SHOTS)
NARRATION_SENTENCE_COUNT = sum(1 for s in SHOTS if s["narration"])


def srt_time(sec: float) -> str:
    ms = int(round(sec * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def timecode(sec: float) -> str:
    m, s = divmod(int(sec), 60)
    return f"00:{m:02d}:{s:02d}.000"


def build_shotlist() -> None:
    path = os.path.join(OUT, "main-film-shotlist.csv")
    cols = ["shot_id", "chapter", "timecode_in", "timecode_out", "duration_s",
            "purpose", "visual", "shot_size_camera", "on_screen_text",
            "narration_id", "narration_text", "in_scene_dialogue",
            "subtitle_status", "music_sfx", "asset_source", "asset_gap",
            "truth_label", "transition", "edit_rhythm"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(cols)
        for s in SHOTS:
            w.writerow([
                s["id"], s["chapter"], timecode(s["tin"]), timecode(s["tout"]),
                s["tout"] - s["tin"], s["purpose"], s["visual"], s["camera"],
                s["screen"], s["nid"], s["narration"],
                " | ".join(d[0] for d in s["dialogue"]),
                "DRAFT_NOT_BURNED_IN", s["music"], s["source"], s["gap"],
                s["truth"], s["trans"], s["rhythm"],
            ])


def build_subtitles() -> tuple[list[dict], list[dict], dict]:
    """Two separate subtitle TRACKS, mirroring a real edit session.

    Track A = main narration subtitles (subtitle-draft.srt, the deliverable).
    Track B = in-scene dialogue subtitles (evidence/dialogue-subtitle-draft.srt).
    Putting both in one SRT would force overlapping cues onto the same line and
    would silently truncate narration to <1 s; a real edit keeps them on two
    differently-styled tracks and resolves any on-screen collision in the mix.
    """
    narration_cues: list[dict] = []
    dialogue_cues: list[dict] = []
    for s in SHOTS:
        if s["narration"]:
            start = s["tin"] + 0.4
            est = max(2.0, min(char_count(s["narration"]) / 4.0,
                               s["tout"] - s["tin"] - 0.9))
            narration_cues.append(dict(kind="narration", ref=s["nid"], shot=s["id"],
                                       start=round(start, 2),
                                       end=round(min(start + est, s["tout"] - 0.2), 2),
                                       text=s["narration"]))
        for idx, (text, off, dur) in enumerate(s["dialogue"], 1):
            start = s["tin"] + off
            # R1-4: a stable, globally unique cue ID per line of dialogue.
            # The old "<shot>-D" reused one ID for every line in a shot, which
            # made S04 / S16 overlaps impossible to count correctly.
            dialogue_cues.append(dict(kind="in_scene_dialogue",
                                      ref=f"{s['id']}-D{idx:02d}", shot=s["id"],
                                      cue_index_within_shot=idx,
                                      start=round(start, 2),
                                      end=round(min(start + dur, s["tout"] - 0.2), 2),
                                      text=text))

    def resolve(cues: list[dict]) -> list[dict]:
        cues.sort(key=lambda c: (c["start"], c["end"], c["ref"]))
        for i in range(len(cues) - 1):
            if cues[i]["end"] > cues[i + 1]["start"] - 0.08:
                cues[i]["end"] = round(max(cues[i]["start"] + 0.6, cues[i + 1]["start"] - 0.08), 2)
        return cues

    narration_cues = resolve(narration_cues)
    dialogue_cues = resolve(dialogue_cues)

    def write_srt(path: str, cues: list[dict]) -> None:
        with open(path, "w", encoding="utf-8", newline="") as f:
            for i, c in enumerate(cues, 1):
                f.write(f"{i}\n{srt_time(c['start'])} --> {srt_time(c['end'])}\n{c['text']}\n\n")

    write_srt(os.path.join(OUT, "subtitle-draft.srt"), narration_cues)
    write_srt(os.path.join(EVID, "dialogue-subtitle-draft.srt"), dialogue_cues)

    # R1-4: publish the cue ID -> SRT ordinal -> shot mapping as evidence.
    os.makedirs(R1_EVID, exist_ok=True)
    cue_rows = []
    for i, c in enumerate(dialogue_cues, 1):
        shot = next(s for s in SHOTS if s["id"] == c["shot"])
        cue_rows.append([c["ref"], i, c["shot"], c["cue_index_within_shot"],
                         srt_time(c["start"]), srt_time(c["end"]), c["text"],
                         shot["truth"]])
    for base in (EVID, R1_EVID):
        with open(os.path.join(base, "dialogue-cue-index.csv"), "w",
                  encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["cue_id", "srt_index", "shot_id", "cue_index_within_shot",
                        "timecode_in", "timecode_out", "text", "truth_label"])
            w.writerows(cue_rows)

    # DRAFT timecodes are planned against a script, not a recorded voice.
    # Report honestly where a dialogue and a narration cue would share a frame.
    collisions = []
    for n in narration_cues:
        for d in dialogue_cues:
            if n["shot"] == d["shot"] and n["start"] < d["end"] and d["start"] < n["end"]:
                collisions.append({"shot": n["shot"], "narration_ref": n["ref"],
                                   "dialogue_ref": d["ref"],
                                   "resolution": "keep two tracks; place dialogue at 0.72H and "
                                                 "narration at 0.86H, or delay the narration cue "
                                                 "until the dialogue ends; re-align to real audio"})

    meta = {
        "file": "subtitle-draft.srt",
        "status": "DRAFT_NOT_BURNED_IN",
        "declared_in": ["report.md", "main-film-shotlist.csv:subtitle_status",
                        "narration-draft.md", "vertical-cut-plan.md"],
        "note": "Both SRT bodies are intentionally clean and standards-compliant so they can be "
                "handed straight to an editor. DRAFT status is declared in the filename and in "
                "the documents above, never injected as visible subtitle text.",
        "track_design": {
            "track_A": "subtitle-draft.srt — main narration, bottom safe area 0.86H",
            "track_B": "evidence/dialogue-subtitle-draft.srt — in-scene dialogue, 0.72H",
            "collision_policy": "two styled tracks, never stacked on the same line; re-align both "
                                "to the real narration audio after recording",
        },
        "narration_cue_count": len(narration_cues),
        "dialogue_cue_count": len(dialogue_cues),
        "cue_id_scheme": "narration=<NID>; dialogue=<SHOT>-D<two-digit index within shot>; "
                         "globally unique across both tracks (R1-4)",
        "dialogue_cue_ids": [c["ref"] for c in dialogue_cues],
        "same_shot_timecode_collisions": len(collisions),
        "collisions": collisions,
        "timecode_basis": "planned 240.0 s main film, 25 fps; MUST be re-aligned to the real "
                          "narration audio after recording. No narration audio exists yet.",
        "language": "zh-CN",
    }
    with open(os.path.join(EVID, "subtitle-draft.meta.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return narration_cues, dialogue_cues, meta


def build_narration_section() -> str:
    lines = ["| ID | 镜头 | 时间码 | 字数 | 预计时长 | 语气 / 断句 | 文本 | 合规检查 |",
             "|---|---|---|---|---|---|---|---|"]
    for s in SHOTS:
        if not s["narration"]:
            continue
        n = char_count(s["narration"])
        lines.append(
            f"| {s['nid']} | {s['id']} | {timecode(s['tin'])}–{timecode(s['tout'])} | {n} | "
            f"≈{n/4.0:.1f}s | 平实、不朗诵；句尾不抬调 | {s['narration']} | "
            f"无疗效/无诊断/无数据/无用户评价 |"
        )
    return "\n".join(lines)


def build_asset_inventory() -> dict:
    with open(os.path.join(EVID, "asset-probe.json"), encoding="utf-8") as f:
        probe = json.load(f)
    path = os.path.join(OUT, "asset-inventory.csv")
    cols = ["relative_path", "group", "bytes", "sha256", "media_kind", "duration_s",
            "resolution", "fps", "video_codec", "audio_codec", "sample_rate_hz",
            "source_type", "is_real_product_footage", "in_git_repository", "usability_for_final_film"]
    count = 0
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(cols)
        for r in probe["records"]:
            md = r.get("metadata", {})
            streams = md.get("streams", [])
            v = next((x for x in streams if x.get("kind") == "video"), {})
            a = next((x for x in streams if x.get("kind") == "audio"), {})
            res = f"{v.get('width')}x{v.get('height')}" if v.get("width") else ""
            w.writerow([
                r["relative_path"], r["group"], r["bytes"], r["sha256"],
                os.path.splitext(r["relative_path"])[1].lower().lstrip("."),
                md.get("duration_seconds", ""), res, v.get("fps", ""),
                v.get("codec", ""), a.get("codec", ""), a.get("sample_rate_hz", ""),
                r["source_type"], r["is_real_product_footage"],
                "YES" if r["in_git_repository"] else "NO",
                "NOT_USABLE_AS_FINAL_FOOTAGE",
            ])
            count += 1
    return {"rows": count, "real_product_footage": probe["summary"]["real_product_footage_count"]}


def consistency_check(narration_cues: list[dict], dialogue_cues: list[dict],
                      meta: dict, inventory: dict) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    for c in meta["collisions"]:
        warnings.append(f"{c['shot']}: narration {c['narration_ref']} overlaps dialogue "
                        f"{c['dialogue_ref']}; DRAFT timecodes must be re-aligned to real audio")

    # shot continuity / total duration
    if SHOTS[0]["tin"] != 0:
        errors.append("first shot does not start at 0")
    for a, b in zip(SHOTS, SHOTS[1:]):
        if a["tout"] != b["tin"]:
            errors.append(f"timecode gap/overlap {a['id']}->{b['id']}: {a['tout']} != {b['tin']}")
    if SHOTS[-1]["tout"] != MAIN_DURATION:
        errors.append(f"total duration {SHOTS[-1]['tout']} != {MAIN_DURATION}")

    shot_by_id = {s["id"]: s for s in SHOTS}
    narration_by_ref = {c["ref"]: c for c in narration_cues}
    narration_ids = {s["nid"] for s in SHOTS if s["nid"]}
    if set(narration_by_ref) != narration_ids:
        errors.append(f"narration cue ids mismatch: {set(narration_by_ref) ^ narration_ids}")

    for ref, c in narration_by_ref.items():
        s = next(x for x in SHOTS if x["nid"] == ref)
        if c["text"] != s["narration"]:
            errors.append(f"{ref}: subtitle text differs from narration draft")
        if not (s["tin"] <= c["start"] < c["end"] <= s["tout"]):
            errors.append(f"{ref}: cue {c['start']}-{c['end']} escapes shot {s['tin']}-{s['tout']}")

    for c in narration_cues + dialogue_cues:
        s = shot_by_id.get(c["shot"])
        if not s or not (s["tin"] <= c["start"] < c["end"] <= s["tout"]):
            errors.append(f"{c['ref']}: cue escapes its shot")
    for track in (narration_cues, dialogue_cues):
        for a, b in zip(track, track[1:]):
            if a["end"] > b["start"]:
                errors.append(f"subtitle overlap within one track: {a['ref']} / {b['ref']}")

    # claims hygiene: banned phrasing is forbidden in NARRATION. On-screen text
    # may contain those words ONLY inside the S33 negative disclaimer.
    banned = ["治愈", "疗效", "保证", "有效率", "用户评价", "销量", "第一", "最好", "包治", "诊断", "治疗建议"]
    for s in SHOTS:
        for b in banned:
            if b in s["narration"] and b not in ("诊断", "治疗建议"):
                errors.append(f"{s['id']}: banned claim phrase '{b}' in narration")
        if s["id"] != "S33":
            for b in banned:
                if b in s["screen"]:
                    errors.append(f"{s['id']}: banned claim phrase '{b}' in on-screen text")
    for s in SHOTS:
        if s["id"] != "S33" and ("诊断" in s["narration"] or "治疗建议" in s["narration"]):
            errors.append(f"{s['id']}: diagnosis wording outside disclaimer")
    if "疗效承诺" not in SHOTS[-1]["screen"] or "不提供" not in SHOTS[-1]["screen"]:
        errors.append("S33: explicit negative disclaimer missing")

    # every shot must name its source and its gap
    for s in SHOTS:
        if not s["source"] or not s["gap"] or not s["truth"]:
            errors.append(f"{s['id']}: missing source/gap/truth label")

    # ---- R1-4: cue IDs must be globally unique and collisions countable -----
    all_refs = [c["ref"] for c in narration_cues + dialogue_cues]
    cue_ids_unique = len(all_refs) == len(set(all_refs))
    if not cue_ids_unique:
        dup = sorted({r for r in all_refs if all_refs.count(r) > 1})
        errors.append(f"R1-4 duplicate cue IDs: {dup}")
    for c in dialogue_cues:
        if not re.fullmatch(r"S\d{2}-D\d{2}", c["ref"]):
            errors.append(f"R1-4 malformed dialogue cue ID: {c['ref']}")
    pairs = [(c["shot"], c["dialogue_ref"]) for c in meta["collisions"]]
    collision_pairs_unique = len(pairs) == len(set(pairs))
    if not collision_pairs_unique:
        errors.append("R1-4 collision list reuses a (shot, dialogue cue ID) pair")
    for sid in {s["id"] for s in SHOTS if len(s["dialogue"]) > 1}:
        refs = [c["dialogue_ref"] for c in meta["collisions"] if c["shot"] == sid]
        if len(refs) != len(set(refs)) and refs:
            errors.append(f"R1-4 {sid}: multi-dialogue shot still reuses one cue ID: {refs}")

    # ---- R1-5: no specific drug name or dosage anywhere in spoken/on-screen text
    specific = ["降压药", "一片", "两片", "半片", "毫克", "每日三次", "早晚各",
                "阿司匹林", "二甲双胍", "硝苯地平"]
    drug_free = True
    for s in SHOTS:
        for field in ("narration", "screen"):
            for kw in specific:
                if kw in s[field]:
                    drug_free = False
                    errors.append(f"R1-5 {s['id']}: specific drug/dose '{kw}' in {field}")
        for text, _off, _dur in s["dialogue"]:
            for kw in specific:
                if kw in text:
                    drug_free = False
                    errors.append(f"R1-5 {s['id']}: specific drug/dose '{kw}' in dialogue")
    for s in SHOTS:
        if "我每天早饭后吃一片降压药" in s["narration"] + s["screen"]:
            drug_free = False
            errors.append(f"R1-5 {s['id']}: original dosage example still present")
    # N25's \"不改剂量\" is a NEGATIVE safety statement and must be preserved.
    n25 = next(s for s in SHOTS if s["id"] == "S30")
    if "不改剂量" not in n25["narration"]:
        errors.append("R1-5 S30: the negative safety boundary statement was lost")

    # ---- R1-2: N09/N10 must be explicitly qualified as design intent --------
    design_ok = True
    for sid in ("S11", "S12"):
        s = shot_by_id[sid]
        if not any(k in s["narration"] for k in ("设计示意", "按设计")):
            design_ok = False
            errors.append(f"R1-2 {sid}: design-intent qualifier missing from narration")
        if "产品设计示意" not in s["screen"]:
            design_ok = False
            errors.append(f"R1-2 {sid}: on-screen design-intent label missing")
        if "STILL_LIFE_REQUIRED" in s["truth"] or "DRAMATIZATION" in s["truth"]:
            design_ok = False
            errors.append(f"R1-2 {sid}: still depends on live-action / real-device footage")
    for s in SHOTS:
        blob = s["narration"] + s["screen"] + "".join(d[0] for d in s["dialogue"])
        if "能听懂普通话" in blob:
            design_ok = False
            errors.append(f"R1-2 {s['id']}: unverified speech-recognition claim still present")

    r1_assertions = {
        "cue_ids_globally_unique": cue_ids_unique,
        "collision_pairs_unique": collision_pairs_unique,
        "specific_drug_or_dosage_removed": drug_free,
        "design_intent_qualifiers_present": design_ok,
    }

    result = {
        "schema_version": "1.0",
        "task_id": "WB-VIDEO-005-PREPRODUCTION",
        "checked_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "main_film_planned_duration_s": MAIN_DURATION,
        "shot_count": len(SHOTS),
        "chapter_count": len({s["chapter"] for s in SHOTS}),
        "narration_sentence_count": len(narration_ids),
        "narration_character_count": sum(char_count(s["narration"]) for s in SHOTS),
        "character_count_rule": CHAR_COUNT_RULE,
        "revision_id": "WB-VIDEO-005-PREPRODUCTION-R1",
        "r1_assertions": r1_assertions,
        "r1_assertions_all_passed": all(r1_assertions.values()),
        "subtitle_cue_count": len(narration_cues),
        "dialogue_cue_count": len(dialogue_cues),
        "timecode_collisions_requiring_realignment": len(meta["collisions"]),
        "asset_inventory_rows": inventory["rows"],
        "real_product_footage_count": inventory["real_product_footage"],
        "subtitle_status": "DRAFT_NOT_BURNED_IN",
        "video_exported": False,
        "errors": errors,
        "warnings": warnings,
        "all_consistency_checks_passed": len(errors) == 0 and all(r1_assertions.values()),
    }
    with open(os.path.join(EVID, "consistency-check.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return result


def main() -> None:
    os.makedirs(EVID, exist_ok=True)
    os.makedirs(R1_EVID, exist_ok=True)
    build_shotlist()
    narration_cues, dialogue_cues, meta = build_subtitles()
    narration_table = build_narration_section()
    with open(os.path.join(EVID, "narration-table.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(narration_table + "\n")
    inv = build_asset_inventory()
    chk = consistency_check(narration_cues, dialogue_cues, meta, inv)

    # R1 evidence snapshots (never overwrite the R0 historical manifests).
    for name in ("consistency-check.json", "subtitle-draft.meta.json",
                 "narration-table.md", "dialogue-cue-index.csv"):
        shutil.copyfile(os.path.join(EVID, name), os.path.join(R1_EVID, name))
    with open(os.path.join(R1_EVID, "character-count-audit.json"), "w",
              encoding="utf-8", newline="\n") as f:
        json.dump({
            "revision_id": "WB-VIDEO-005-PREPRODUCTION-R1",
            "machine_count": NARRATION_CHAR_COUNT,
            "sentence_count": NARRATION_SENTENCE_COUNT,
            "rule": CHAR_COUNT_RULE,
            "source_of_truth": "outbox/WB-VIDEO-005-PREPRODUCTION/evidence/consistency-check.json"
                               " : narration_character_count",
            "r0_conflicting_values": [
                {"value": 560, "where": "R0 main-film-script.md line 12",
                 "status": "REJECTED_ESTIMATE_NOT_MACHINE_COUNTED"},
                {"value": 473, "where": "R0 evidence/consistency-check.json",
                 "status": "HISTORICAL_MACHINE_COUNT_BEFORE_R1_REWORD"}],
            "single_authoritative_value_in_r1": NARRATION_CHAR_COUNT,
            "all_documents_must_state_this_value": True,
            "per_sentence_counts": [
                {"id": s["nid"], "shot": s["id"], "chars": char_count(s["narration"]),
                 "text": s["narration"]}
                for s in SHOTS if s["narration"]],
        }, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(json.dumps({
        "shots": len(SHOTS), "duration": MAIN_DURATION,
        "narration_characters": NARRATION_CHAR_COUNT,
        "narration_sentences": NARRATION_SENTENCE_COUNT,
        "subtitle_cues": len(narration_cues), "dialogue_cues": len(dialogue_cues),
        "unique_dialogue_cue_ids": len({c["ref"] for c in dialogue_cues}),
        "timecode_collisions": len(meta["collisions"]),
        "inventory_rows": inv["rows"],
        "real_product_footage": inv["real_product_footage"],
        "consistency_errors": chk["errors"],
        "warnings": len(chk["warnings"]),
        "r1_assertions": chk["r1_assertions"],
        "all_passed": chk["all_consistency_checks_passed"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
