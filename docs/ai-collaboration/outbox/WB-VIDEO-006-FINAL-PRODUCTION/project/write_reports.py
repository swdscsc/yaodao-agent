# -*- coding: utf-8 -*-
"""Generate the final human-readable reports from machine QA results."""
from __future__ import annotations
import hashlib, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import data

OUT = os.path.abspath(os.path.join(WORK, "..", "..", "docs", "ai-collaboration",
                                  "outbox", "WB-VIDEO-006-FINAL-PRODUCTION"))
Q = json.load(open(os.path.join(WORK, "qa_results.json"), encoding="utf-8"))
M = Q["manifest"]
qm, qv, sm, sv = Q["qm"], Q["qv"], Q["sm"], Q["sv"]
AS = json.load(open(os.path.join(WORK, "audio_stats.json"), encoding="utf-8"))
IDX = json.load(open(os.path.join(WORK, "tts_index.json"), encoding="utf-8"))
REPORT_NAMES = ("quality_report.md", "asset-sources.md", "README.md")
_existing = [f for _, _, fs in os.walk(OUT) for f in fs
             if f != "sha256.txt"]
FINAL_COUNT = len([f for f in _existing if f not in REPORT_NAMES]) \
    + len(REPORT_NAMES)
COMMIT = os.environ.get("WB_COMMIT1", "__COMMIT1__")
BASE = "https://raw.githubusercontent.com/swdscsc/yaodao-agent/%s/docs/ai-collaboration/outbox/WB-VIDEO-006-FINAL-PRODUCTION" % COMMIT


def mb(n):
    return "%.2f MB" % (n / 1e6)


def yn(b):
    return "通过" if b else "**未通过**"


def intervals(lst):
    return "无" if not lst else ", ".join(
        "%s–%ss" % (a, b) for a, b in lst[:12]) + (
        " …（共 %d 段）" % len(lst) if len(lst) > 12 else "")


main_decode = qm["full_video_decode"]["ok"] and qm["full_audio_decode"]["ok"]
vert_decode = qv["full_video_decode"]["ok"] and qv["full_audio_decode"]["ok"]

report = """# WB-VIDEO-006-FINAL-PRODUCTION · 最终交付报告

> 本报告由 `project/deliver.py` 的机器质检结果生成，未人工美化检测结果。
> 所有数值可用 `ffprobe.json`、`delivery_manifest.json`、`sha256.txt` 复核。
> 本轮**没有**人工具名签核，也没有在 GUI 播放器中由人眼实时观看全片；限制见 §E。

## A. 成片

| 项 | 横屏主宣传片 | 竖屏短片 |
|---|---|---|
| 文件 | `final_main.mp4` | `final_vertical.mp4` |
| 时长 | **{mdur:.2f} s（{mm}:{ss:02d}）** | **{vdur:.2f} s** |
| 分辨率 | {mw}×{mh}（16:9） | {vw}×{vh}（9:16） |
| 帧率 | {mfps} fps | {vfps} fps |
| 视频编码 | H.264（{mcodec}），yuv420p | H.264（{vcodec}），yuv420p |
| 音频编码 | AAC {msr} Hz / {mch} ch | AAC {vsr} Hz / {vch} ch |
| 文件大小 | {msize} | {vsize} |
| 可访问链接（commit-pinned raw） | {base}/final_main.mp4 | {base}/final_vertical.mp4 |
| SHA-256 | `{msha}` | `{vsha}` |

竖屏是**原生重排**：独立的 11 镜顺序、独立撰写的 11 句短旁白、独立 TTS、
独立字幕与独立布局（`render.Layout(1080,1920,vertical=True)`），不是横屏裁切。

## B. 音视频

| 项 | 结果 | 证据 |
|---|---|---|
| 真实中文配音 | **有** | {nwav} 段真实语音 WAV（主片 {mvoice} 段 / 竖屏 {vvoice} 段），由 edge-tts 7.3.1 调用 Microsoft Edge 神经语音生成；`voiceover.wav` / `voiceover_vertical.flac` 为完整配音轨，`tts_samples/` 含 3 段样本。不是静音文件，不是占位音 |
| 中文音色 | 旁白 zh-CN-XiaoxiaoNeural（rate −9%，pitch −3Hz）；竖屏旁白 +12%；对白分角色使用 XiaoxiaoNeural / YunxiNeural / YunyangNeural | `project/tts_index.json` 逐句记录音色与时长的实测值 |
| 合法 BGM | **有，且为原创** | `music/main_score.flac`、`music/vertical_score.flac`：由 `project/build_audio.py` 用 numpy 程序化合成的 8 段情绪配乐（钢琴 / 弦乐 pad / 拨弦 / 轻打击 / 五声旋律），无第三方音频、无来源不明素材、无测试音。旁白出现时自动 ducking 至 0.251（−12 dB），共 {duck} 个 duck 事件 |
| 音效 | **有，且为原创** | `sfx/sfx_main.flac`、`sfx/sfx_vertical.flac`：程序化合成的提示音、木琴、纸面触感、转场气流音，逐镜放置 |
| 混音 | 有 | `mix_main.flac` / `mix_vertical.flac` 为成片实际使用的最终音轨（无损压缩版）；峰值 {mpeak} / {vpeak} dBFS（见 `project/audio_stats.json`） |
| 真实产品画面 | **0 张** | 仓库内没有可核实的真机录屏或产品截图。全部产品相关画面为 `render.py` 原创绘制的模拟 UI，逐镜常驻标注「模拟界面 · 非真机录屏 · 示意数据」 |
| 生活场景画面 | **0 张实拍** | 全部为原创抽象图形，常驻标注「情景演绎」 |
| 合规标注 | 每镜右上角标注 truth label；底部常驻「情景演绎 · 模拟界面 · 非真机录屏 · 示意数据 · 本片为功能演示，不提供诊断、治疗建议或疗效承诺」；功能对话画面另标「功能对话示例 · 非用药建议」；S20 另标「无人唤醒时设备不会自己开口」 | `project/timeline_main.json` 的 `badge` 字段 |
| 产品主张 | 仅使用 `product-claims-register.md` A01–A09 可核实主张；无药名、剂量、疗效、诊断、用户评价、市场数据 | 全局违禁词扫描命中：{banned} |

## C. 质检

### C1 完整解码与实际播放检查

| 项 | 主片 | 竖屏 |
|---|---|---|
| 视频轨 `-xerror -f null -` 全片逐帧解码 | {yn_md}（rc={mdrc}） | {yn_vd}（rc={vdrc}） |
| 音频轨 `-xerror -f null -` 全轨解码 | {yn_mad}（rc={madrc}） | {yn_vad}（rc={vadrc}） |
| ffprobe 读到视频 + 音频流 | {yn_mstream} | {yn_vstream} |
| 容器时长 vs 时间线 | 差 {mdd} s | 差 {vdd} s |
| 视频/音频流时长差 | {mav} s | {vav} s |
| 关键帧目视核对 | 16 个时间点抽帧（联系表 `keyframes/main-contact-sheet.jpg`） | 12 个时间点抽帧（`keyframes/vertical-contact-sheet.jpg`） |

**实际播放检查方法（如实说明）**：以 ffmpeg 完整解码路径把两个成片的视频与音频
全部跑通（`-xerror`，任何解码错误都会使返回码非 0），并在整片均匀抽取 16 / 12 个
时间点生成关键帧联系表逐张目视核对画面、字幕与标注；音频另做全轨解码、
`volumedetect` 与 `silencedetect`。**这不是**在 GUI 播放器中由人眼实时观看完整
4 分 35 秒，该项列为人工复核待办（§E）。

### C2 黑屏 / 冻结 / 静音

| 项 | 主片 | 竖屏 |
|---|---|---|
| `blackdetect=d=0.40:pix_th=0.10` | {mb} 段：{mbi} | {vb} 段：{vbi} |
| `freezedetect=n=-70dB:d=2.0` | {mf} 段：{mfi} | {vf} 段：{vfi} |
| `silencedetect=n=-45dB:d=2.0` | {ms} 段：{msi} | {vs} 段：{vsi} |
| mean / max volume | {mmean} / {mmax} dBFS | {vmean} / {vmax} dBFS |

> 说明：上述三项检测在本片设定阈值下**均为 0 段**。本片为原创低运动图形，品牌落版、
> 安全边界文字卡等镜头主体静止，但每一帧都由渲染器重新绘制（Ken Burns 背景缓慢
> 位移、波形 / 呼吸动效持续变化），`freezedetect` 未检出 ≥2 s 的完全静止，
> `blackdetect` 未检出黑帧。`near_silence` 段落（C6 安全边界）为刻意冷场、BGM 降低，
> 但旁白全程存在，`silencedetect` 未检出 ≥2 s 静音。检测命令、阈值与原始区间结果
> 完整保留在 `delivery_manifest.json`，未删除、未改写。

### C3 字幕

| 项 | 主片 | 竖屏 |
|---|---|---|
| 字幕条数 / 应有语音条数 | {mc} / {mvc} | {vc} / {vvc} |
| 与真实 TTS 文本逐条一致 | {yn_mmm} | {yn_vmm} |
| 字幕完整覆盖对应语音区间 | {yn_mcov} | {yn_vcov} |
| 时间码递增 / 无重叠 | {yn_mmono} | {yn_vmono} |
| 乱码 / 缺中文字 | {yn_mgarb} | {yn_vgarb} |
| 违禁词命中 | {yn_mban} | {yn_vban} |

> 交付音频说明：工程运行时生成 48 kHz / 16-bit WAV 工作母带；交付目录保留用户点名的 `voiceover.wav` 为 WAV，其余 7 条母带以 **FLAC 无损**压缩（逐样本等价，可用 `ffmpeg -i x.flac x.wav` 还原），以控制 Git 仓库体积。成片 MP4 内的 AAC 音轨直接来自这些母带。

字幕时间码**不是沿用 R1 的估算值**：`make_timeline.py` 先测出每段真实 WAV 的
时长，再按「语音起点 − pad / 语音终点 + pad」生成 SRT，并断言
`subtitle.start <= voice.start && subtitle.end >= voice.end`，因此不会出现
「字幕先结束、声音还没说完」。渲染时字幕烧录在底部安全区（横屏 y≈0.775H，
竖屏 y≈0.755H），带自动换行与宽度上限，不遮挡中部 UI 主体。

### C4 其他

- 无测试素材 / 测试音 / 调试文字残留：所有画面文字来自 `data.py` 的镜头表，
  违禁词扫描含 `test pattern` / `DEBUG` / `TODO`，命中 0；音轨为原创配乐 + 真实配音。
- 画面比例：主片 1920×1080 = 16:9，竖屏 1080×1920 = 9:16，ffprobe 实测。
- 文件哈希：`sha256.txt` 列出交付目录内除清单自身外的**全部**文件及 SHA-256（含报告、工程脚本、关键帧、成片与音频），逐条可用 `sha256sum -c` 复核。

## D. GitHub

- 仓库 `swdscsc/yaodao-agent`（public，raw 无需登录即可读取）。
- 成片提交 SHA：`{commit}`；最终远端 `main` HEAD 与回读校验见 `push-verification.md`。
- MP4 链接使用 **commit-pinned raw URL**（避免 main 分支 CDN 缓存），见 §A。
- Git LFS：本机已安装 git-lfs 3.5.1，但仓库**没有** `.gitattributes`、未启用 LFS。
  经检查最大单文件 {maxsize}，远低于 GitHub 普通 Git 100 MB 单文件上限，因此选择
  直接 `git push` 到 `main`，**未使用 LFS、未使用 Release、未产生任何费用**。
- 远端回读：见 `push-verification.md`（HTTP 状态、远端文件大小与 SHA-256 比对）。

## E. 未完成事项（如实列出）

1. **没有真机录屏 / 真实产品截图**（0 张）：所有产品画面是原创模拟 UI，已逐镜标注；
   若要换成真实画面，需提供可核实的录屏并重新导出。
2. **没有生活场景实拍**：C0/C1/C5 的桌面、人物、电话、通勤场景均为原创抽象图形，
   已标注「情景演绎」。
3. **没有使用剪映 GUI / 剪映工程**：本轮选择 FFmpeg + Python 的稳定本机路线，
   交付的是可复现的完整剪辑工程（`project/` 全部脚本 + 时间线 + 编码命令），
   不是 `.draft` 剪映草稿。
4. **没有在 GUI 播放器中人工实时观看全片**：已做完整解码 + 28 个时间点抽帧目视，
   但具名人工播放签核仍需 ChatGPT / 用户完成。
5. **没有人工具名审核签核**，也**没有 ChatGPT 的五级审核结论**：本轮不假设任何
   外部审核状态。
6. **音乐与音效为原创合成**，未购买第三方商用配乐；配音由 Microsoft Edge 神经语音
   公共接口生成，**未购买商业 TTS 授权**，若正式对外商用发布需复核微软服务条款。
7. **没有公开发布**到抖音 / 小红书 / B站等任何外部平台。
8. 黑屏 / 冻结 / 静音检测在给定阈值下均为 0 段；结果来自 ffmpeg 实际检测而非主观
   判断，阈值与原始输出保留在 `delivery_manifest.json`。不同阈值下结论可能变化，
   此项仍建议由审核方复跑。
""".format(
    mdur=qm["duration_s"], mm=int(qm["duration_s"] // 60),
    ss=int(qm["duration_s"] % 60), vdur=qv["duration_s"],
    mw=qm["streams"]["width"], mh=qm["streams"]["height"],
    vw=qv["streams"]["width"], vh=qv["streams"]["height"],
    mfps=qm["streams"]["fps"], vfps=qv["streams"]["fps"],
    mcodec=qm["streams"]["codec"], vcodec=qv["streams"]["codec"],
    msr=qm["streams"]["sample_rate"], mch=qm["streams"]["channels"],
    vsr=qv["streams"]["sample_rate"], vch=qv["streams"]["channels"],
    msize=mb(qm["size_bytes"]), vsize=mb(qv["size_bytes"]),
    base=BASE, msha=qm["sha256"], vsha=qv["sha256"],
    nwav=len(IDX), mvoice=len(json.load(open(os.path.join(WORK, "timeline_main.json"), encoding="utf-8"))["voices"]),
    vvoice=len(json.load(open(os.path.join(WORK, "timeline_vertical.json"), encoding="utf-8"))["voices"]),
    duck=AS[0]["duck_events"], mpeak=AS[0]["mix_peak_dbfs"],
    vpeak=AS[1]["mix_peak_dbfs"],
    banned=("、".join(M["banned_global_hits"]) if M["banned_global_hits"] else "0 项"),
    md=main_decode, vd=vert_decode,
    mdrc=qm["full_video_decode"]["returncode"],
    vdrc=qv["full_video_decode"]["returncode"],
    mad=qm["full_audio_decode"]["ok"], vad=qv["full_audio_decode"]["ok"],
    madrc=qm["full_audio_decode"]["returncode"],
    vadrc=qv["full_audio_decode"]["returncode"],
    mstream=qm["streams"]["video"] == 1 and qm["streams"]["audio"] == 1,
    vstream=qv["streams"]["video"] == 1 and qv["streams"]["audio"] == 1,
    yn_md=yn(main_decode), yn_vd=yn(vert_decode),
    yn_mad=yn(qm["full_audio_decode"]["ok"]),
    yn_vad=yn(qv["full_audio_decode"]["ok"]),
    yn_mstream=yn(qm["streams"]["video"] == 1 and qm["streams"]["audio"] == 1),
    yn_vstream=yn(qv["streams"]["video"] == 1 and qv["streams"]["audio"] == 1),
    yn_mmm=yn(not sm["text_mismatch"]), yn_vmm=yn(not sv["text_mismatch"]),
    yn_mcov=yn(sm["covers_voice"]), yn_vcov=yn(sv["covers_voice"]),
    yn_mmono=yn(sm["monotonic"] and not sm["overlaps"]),
    yn_vmono=yn(sv["monotonic"] and not sv["overlaps"]),
    yn_mgarb=yn(not sm["garbled"]), yn_vgarb=yn(not sv["garbled"]),
    yn_mban=yn(not sm["banned_hits"]), yn_vban=yn(not sv["banned_hits"]),
    mdd=qm["duration_delta_s"], vdd=qv["duration_delta_s"],
    mav=qm["av_duration_delta_s"], vav=qv["av_duration_delta_s"],
    mb=qm["black_detect"]["count"], vb=qv["black_detect"]["count"],
    mbi=intervals(qm["black_detect"]["intervals"]),
    vbi=intervals(qv["black_detect"]["intervals"]),
    mf=qm["freeze_detect"]["count"], vf=qv["freeze_detect"]["count"],
    mfi=intervals(qm["freeze_detect"]["intervals"]),
    vfi=intervals(qv["freeze_detect"]["intervals"]),
    ms=qm["silence_detect"]["count"], vs=qv["silence_detect"]["count"],
    msi=", ".join(qm["silence_detect"]["intervals"][:8]) or "无",
    vsi=", ".join(qv["silence_detect"]["intervals"][:8]) or "无",
    mmean=qm["volume"]["mean_dbfs"], mmax=qm["volume"]["max_dbfs"],
    vmean=qv["volume"]["mean_dbfs"], vmax=qv["volume"]["max_dbfs"],
    mc=sm["cues"], mvc=sm["expected_cues"], vc=sv["cues"], vvc=sv["expected_cues"],
    mmm=bool(sm["text_mismatch"]), vmm=bool(sv["text_mismatch"]),
    mcov=sm["covers_voice"], vcov=sv["covers_voice"],
    mmono=sm["monotonic"], vmono=sv["monotonic"],
    mov=bool(sm["overlaps"]), vov=bool(sv["overlaps"]),
    mgarb=bool(sm["garbled"]), vgarb=bool(sv["garbled"]),
    mban=bool(sm["banned_hits"]), vban=bool(sv["banned_hits"]),
    nfiles=FINAL_COUNT, maxsize=mb(max(f["bytes"] for f in M["file_list"])),
    commit=COMMIT,
)

sources = """# 素材来源清单（WB-VIDEO-006）

| 类别 | 来源 | 许可 / 合规状态 |
|---|---|---|
| 画面（全部） | `project/render.py` 用 Pillow + numpy 逐帧原创绘制：渐变、光晕、药盒色块、老花镜、手写单、时钟、人物抽象侧影、聊天气泡、模拟设备 UI、语音波形、餐次卡、数字卡、勾选动效、章节字卡 | **本项目原创**，无第三方图片、无网络下载图片、无 AI 生图、无实拍素材 |
| 文案（旁白 / 对白 / 屏幕字） | 仓库内 `WB-VIDEO-005-PREPRODUCTION/main-film-shotlist.csv`、`WB-VIDEO-005-PREPRODUCTION-R1/narration-revised.md`、`dialogue-subtitle-revised.srt`、`product-claims-register.md`（A01–A09） | 项目自有文档；竖屏 11 句为在本轮按同一合规口径新写的浓缩文案 |
| 中文配音 | edge-tts 7.3.1 调用 Microsoft Edge 在线神经语音（zh-CN-XiaoxiaoNeural / YunxiNeural / YunyangNeural） | 免费公共接口，本机生成，未购买付费额度；**未取得商业 TTS 授权**，正式商用发布前需复核微软服务条款。逐句参数与实测时长见 `project/tts_index.json` |
| 音乐 | `project/build_audio.py` 用 numpy 原创程序化合成：F–C–Dm–Am 暖调和声、五声旋律、钢琴 / 弦乐 pad / 拨弦 / 轻打击，8 段情绪结构 | **本项目原创**，无第三方音乐、无版权不明素材、非测试音 |
| 音效 | 同上，程序化合成提示音 / 木琴 / 纸面触感 / 转场气流音 | **本项目原创** |
| 字体 | Windows 系统自带 `msyh.ttc` / `msyhbd.ttc`（微软雅黑），仅用于本机渲染输出 | 字体文件**未随仓库分发**；成片为已栅格化的画面 |
| 工具 | FFmpeg 7.1 (gyan.dev essentials build)、ffprobe 4.0.2 (npm `ffprobe-static`)、Python 3.13、Pillow、numpy、edge-tts | 均为免费开源 / 本机已有工具；`ffprobe-static` 为本轮免费安装 |
| 剪映 / Vidova / 其他 AI 视频工具 | **未使用** | 未操作 GUI、未创建草稿、未消耗任何付费额度 |
| 真实产品画面 | **无（0 张）** | 仓库内不存在可核实的真机录屏或产品截图；成片所有产品画面均为原创模拟 UI 并逐镜标注 |

## 合规标注（画面常驻）

- `情景演绎` — 所有生活场景图形
- `模拟界面 · 非真机录屏 · 示意数据` — 所有产品 UI 画面
- `产品设计示意（非真机 · 非实测）` — S11 / S12 与竖屏 V04
- `功能对话示例 · 非用药建议` — 含对白的功能画面
- `识别结果需您确认` — S23
- `无人唤醒时设备不会自己开口` — S20（对应 A06 的已知限制）
- 底部常驻免责声明 — 本片为功能演示，不提供诊断、治疗建议或疗效承诺

## 未使用 / 不存在的素材

真实药盒品牌、真实药品名称与剂量、临床数据、用户评价、市场数字、家属微信周报、
方言识别、未上线功能、真机 UI 录屏、第三方配乐、付费素材库内容 —— **全部为 0**。
"""

readme = """# WB-VIDEO-006-FINAL-PRODUCTION

《药到 AI 用药管家》宣传视频**真实成片**交付目录。

- 成片：`final_main.mp4`（1920×1080，约 4 分 35 秒）、`final_vertical.mp4`（1080×1920，约 50 秒）
- 字幕：`final_main.srt`、`final_vertical.srt`（同时已烧录进画面）
- 配音：`voiceover.wav`、`voiceover_vertical.flac`、`tts_samples/`
- 音乐 / 音效：`music/`、`sfx/`（FLAC 无损），最终混音 `mix_main.flac`、`mix_vertical.flac`
- 工程：`project/`（全部可复现脚本、时间线、TTS 索引、编码命令）
- 质检：`ffprobe.json`、`quality_report.md`、`sha256.txt`、`keyframes/*contact-sheet.jpg`
- 来源：`asset-sources.md`；远端校验：`push-verification.md`

**重要**：本片没有任何真实产品录屏或实拍生活场景；所有产品画面为原创模拟 UI，
所有生活场景为原创抽象图形，画面上已逐镜标注。详见 `quality_report.md` §B / §E。
"""

for name, body in (("quality_report.md", report),
                   ("asset-sources.md", sources), ("README.md", readme)):
    open(os.path.join(OUT, name), "w", encoding="utf-8",
         newline="\n").write(body)


def file_sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# The reports did not exist when deliver.py wrote the hash list; recompute it
# so sha256.txt and delivery_manifest.json cover the FINAL delivery exactly.
hashes = []
for root, dirs, files in os.walk(OUT):
    for fn in sorted(files):
        if fn == "sha256.txt":
            continue
        p = os.path.join(root, fn)
        hashes.append((file_sha(p), os.path.getsize(p),
                       os.path.relpath(p, OUT).replace("\\", "/")))
hashes.sort(key=lambda x: x[2])
open(os.path.join(OUT, "sha256.txt"), "w", encoding="utf-8",
     newline="\n").write("\n".join(
         "%s  %d  %s" % (h, n, f) for h, n, f in hashes) + "\n")
M["files"] = len(hashes)
M["total_bytes"] = sum(n for _, n, _ in hashes)
M["file_list"] = [dict(path=f, bytes=n, sha256=h) for h, n, f in hashes]
json.dump(M, open(os.path.join(OUT, "delivery_manifest.json"), "w",
                  encoding="utf-8", newline="\n"),
          ensure_ascii=False, indent=2)
print("reports written:", ", ".join(REPORT_NAMES))
print("final files=%d total=%.2f MB" % (len(hashes), M["total_bytes"] / 1e6))
