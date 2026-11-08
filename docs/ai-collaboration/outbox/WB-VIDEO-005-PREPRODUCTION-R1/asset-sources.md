# 所需素材及其真实来源

| 项 | 值 |
|---|---|
| 片段 | S14-S17（27 s） |
| 素材总数 | 18 个文件（5 SVG + 1 HTML + 9 PNG + 时间线/字幕 3 份） |
| 第三方素材 | **0**（无图库、无模板、无素材站下载、无测试视频） |
| 真实产品画面 | **0**（R0 `asset-inventory.csv` 实测 `real_product_footage_count = 0`） |
| 本轮下载 / 安装 / 额度 / GUI / 付费 | 0 / 0 / 0 / 0 / 0 |
| 机器清单 | `evidence/asset-source-manifest.json`（逐文件 SHA-256） |
| 渲染日志 | `evidence/keyframe-render-log.json`（每条 FFmpeg 命令、退出码、尺寸、哈希） |

## 1. 逐文件来源

| 文件 | 类型 | 字节 | SHA-256（前 16） | 来源 |
|---|---|---|---|---|
| `assets/s14-chapter-cards.svg` | svg | 1917 | `feb12cb00a69604a…` | 原创 |
| `assets/s15-mockui-save.svg` | svg | 1788 | `01afa3f41cbda91b…` | 原创 |
| `assets/s16-mockui-query.svg` | svg | 1901 | `2733877c1ca0d62c…` | 原创 |
| `assets/s17-mockui-checkin.svg` | svg | 1744 | `3e2e3a04d91a7205…` | 原创 |
| `assets/subtitle-safe-area.svg` | svg | 1257 | `6b2e0eeb068737eb…` | 原创 |
| `assets/first-cut-mockui.html` | html | 5277 | `8750a15b3fbaaf6a…` | 原创 |
| `first-cut-timeline.csv` | csv | 2122 | `9422d2ffa2bfd5c8…` | 原创 |
| `first-cut-subtitles.srt` | srt | 270 | `6fa76878f0e3a366…` | 原创 |
| `first-cut-dialogue.srt` | srt | 241 | `4318e08d9ab5066a…` | 原创 |
| `assets/keyframes/s14-state1.png` | png_keyframe | 46499 | `402674878b542d45…` | 原创 |
| `assets/keyframes/s14-state2.png` | png_keyframe | 48806 | `6d4f86c40322117c…` | 原创 |
| `assets/keyframes/s14-state3.png` | png_keyframe | 52399 | `1920e4464aebd26e…` | 原创 |
| `assets/keyframes/s15-state1.png` | png_keyframe | 62853 | `53ca1ba2e7c043d5…` | 原创 |
| `assets/keyframes/s15-state2.png` | png_keyframe | 74855 | `d4cdad80e85ed0ca…` | 原创 |
| `assets/keyframes/s16-state1.png` | png_keyframe | 63124 | `66fe538d6336757f…` | 原创 |
| `assets/keyframes/s16-state2.png` | png_keyframe | 78388 | `dd00ef3ac9953a1a…` | 原创 |
| `assets/keyframes/s17-state1.png` | png_keyframe | 59091 | `7d43ca779b1efe9a…` | 原创 |
| `assets/keyframes/s17-state2.png` | png_keyframe | 64008 | `9a63105cd61b6a5e…` | 原创 |

## 2. 来源说明（逐类）

| 类别 | 真实来源 | 可否用于成片 | 标注 |
|---|---|---|---|
| 章节卡 / 功能卡 | 本轮手写 SVG 矢量，文字与形状原创 | 可以（原创） | `原创动态图形 · 章节卡` / `原创图形 · 非产品画面` |
| 模拟界面 | 本轮手写 SVG + HTML/CSS，按台账 A01/A02/A03 的功能语义自绘 | 可以（明确标注） | `模拟界面 · 非真机录屏` |
| 关键帧 PNG | 本机 FFmpeg 7.1 的 `drawbox` + `drawtext`，用已安装的 `msyh.ttc` 绘制 | 可以（原创） | `预制作素材 · 非成片` |
| 字体 | 本机已安装 Microsoft YaHei / Noto Sans SC，未复制、未下载 | 系统字体，本地渲染 | — |
| 字幕安全区图 | 本轮手写 SVG | 制作参照，不进成片 | `原创图示 · 非成片` |
| 旁白音频 | **无** | 不可用 | — |
| BGM / SFX | **无** | 不可用 | 见 `music-sfx-plan.md` |
| 真实产品界面 / 真机录屏 | **无** | 不可用 | 不得伪装，见台账 C06 |
| WB-002 测试素材 | `pipeline/assets/*`、`pipeline/renders/*` 共 56 个文件 | **禁止** | `NOT_USABLE_AS_FINAL_FOOTAGE` / D005 红线 |

## 3. 真实性标注规则（已在素材上落实）

1. 任何自绘界面 → 常驻「模拟界面 · 非真机录屏」；**不得**称为录屏。
2. 涉及对话的界面 → 加「功能对话示例 · 非用药建议」；涉及数字 → 加「示意数据」。
3. 原创图形 → 标「原创动态图形 / 原创图形 · 非产品画面」。
4. 每一张关键帧右下角 → 「WB-VIDEO-005-R1 · 预制作素材 · 非成片」。
5. 产品设计示意（S11/S12，本片段未用）→ 常驻「产品设计示意（非真机 · 非实测）」。
6. 全部画面不得出现可辨识真实药品牌、规格、批号、用户评价或效果数字。

## 4. 不得冒充的三类东西

- `pipeline/assets/S003-A01.mp4` 等 WB-002 合成测试信号（FFmpeg 彩条/渐变）。
- `pipeline/renders/*.mp4` 参考渲染与 D005 `smptebars` 占位。
- `pipeline/tts004/audio_chain_test_tone.wav`（440 Hz 正弦测试音）与 `bgm.wav` / `sfx.wav`。

> 本轮**没有使用**上述任何一项作为首段画面或声音。
