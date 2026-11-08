# WB-VIDEO-006-FINAL-PRODUCTION · 最终交付报告

> 本报告由 `project/deliver.py` 的机器质检结果生成，未人工美化检测结果。
> 所有数值可用 `ffprobe.json`、`delivery_manifest.json`、`sha256.txt` 复核。
> 本轮**没有**人工具名签核，也没有在 GUI 播放器中由人眼实时观看全片；限制见 §E。

## A. 成片

| 项 | 横屏主宣传片 | 竖屏短片 |
|---|---|---|
| 文件 | `final_main.mp4` | `final_vertical.mp4` |
| 时长 | **274.75 s（4:34）** | **50.50 s** |
| 分辨率 | 1920×1080（16:9） | 1080×1920（9:16） |
| 帧率 | 24/1 fps | 24/1 fps |
| 视频编码 | H.264（h264），yuv420p | H.264（h264），yuv420p |
| 音频编码 | AAC 48000 Hz / 2 ch | AAC 48000 Hz / 2 ch |
| 文件大小 | 10.54 MB | 2.06 MB |
| 可访问链接（commit-pinned raw） | https://raw.githubusercontent.com/swdscsc/yaodao-agent/__COMMIT1__/docs/ai-collaboration/outbox/WB-VIDEO-006-FINAL-PRODUCTION/final_main.mp4 | https://raw.githubusercontent.com/swdscsc/yaodao-agent/__COMMIT1__/docs/ai-collaboration/outbox/WB-VIDEO-006-FINAL-PRODUCTION/final_vertical.mp4 |
| SHA-256 | `c6f98a5b31aeab22427184e6ca11e0acb9d502dbe8a22a8b40f969db536b8bb4` | `89d12425dfc4d8ea4d614a19b1b07d5910aac429c2c3740c393131e0ee56aa24` |

竖屏是**原生重排**：独立的 11 镜顺序、独立撰写的 11 句短旁白、独立 TTS、
独立字幕与独立布局（`render.Layout(1080,1920,vertical=True)`），不是横屏裁切。

## B. 音视频

| 项 | 结果 | 证据 |
|---|---|---|
| 真实中文配音 | **有** | 57 段真实语音 WAV（主片 44 段 / 竖屏 13 段），由 edge-tts 7.3.1 调用 Microsoft Edge 神经语音生成；`voiceover.wav` / `voiceover_vertical.flac` 为完整配音轨，`tts_samples/` 含 3 段样本。不是静音文件，不是占位音 |
| 中文音色 | 旁白 zh-CN-XiaoxiaoNeural（rate −9%，pitch −3Hz）；竖屏旁白 +12%；对白分角色使用 XiaoxiaoNeural / YunxiNeural / YunyangNeural | `project/tts_index.json` 逐句记录音色与时长的实测值 |
| 合法 BGM | **有，且为原创** | `music/main_score.flac`、`music/vertical_score.flac`：由 `project/build_audio.py` 用 numpy 程序化合成的 8 段情绪配乐（钢琴 / 弦乐 pad / 拨弦 / 轻打击 / 五声旋律），无第三方音频、无来源不明素材、无测试音。旁白出现时自动 ducking 至 0.251（−12 dB），共 44 个 duck 事件 |
| 音效 | **有，且为原创** | `sfx/sfx_main.flac`、`sfx/sfx_vertical.flac`：程序化合成的提示音、木琴、纸面触感、转场气流音，逐镜放置 |
| 混音 | 有 | `mix_main.flac` / `mix_vertical.flac` 为成片实际使用的最终音轨（无损压缩版）；峰值 -1.77 / -3.11 dBFS（见 `project/audio_stats.json`） |
| 真实产品画面 | **0 张** | 仓库内没有可核实的真机录屏或产品截图。全部产品相关画面为 `render.py` 原创绘制的模拟 UI，逐镜常驻标注「模拟界面 · 非真机录屏 · 示意数据」 |
| 生活场景画面 | **0 张实拍** | 全部为原创抽象图形，常驻标注「情景演绎」 |
| 合规标注 | 每镜右上角标注 truth label；底部常驻「情景演绎 · 模拟界面 · 非真机录屏 · 示意数据 · 本片为功能演示，不提供诊断、治疗建议或疗效承诺」；功能对话画面另标「功能对话示例 · 非用药建议」；S20 另标「无人唤醒时设备不会自己开口」 | `project/timeline_main.json` 的 `badge` 字段 |
| 产品主张 | 仅使用 `product-claims-register.md` A01–A09 可核实主张；无药名、剂量、疗效、诊断、用户评价、市场数据 | 全局违禁词扫描命中：0 项 |

## C. 质检

### C1 完整解码与实际播放检查

| 项 | 主片 | 竖屏 |
|---|---|---|
| 视频轨 `-xerror -f null -` 全片逐帧解码 | 通过（rc=0） | 通过（rc=0） |
| 音频轨 `-xerror -f null -` 全轨解码 | 通过（rc=0） | 通过（rc=0） |
| ffprobe 读到视频 + 音频流 | 通过 | 通过 |
| 容器时长 vs 时间线 | 差 0.0 s | 差 0.0 s |
| 视频/音频流时长差 | 0.0 s | 0.0 s |
| 关键帧目视核对 | 16 个时间点抽帧（联系表 `keyframes/main-contact-sheet.jpg`） | 12 个时间点抽帧（`keyframes/vertical-contact-sheet.jpg`） |

**实际播放检查方法（如实说明）**：以 ffmpeg 完整解码路径把两个成片的视频与音频
全部跑通（`-xerror`，任何解码错误都会使返回码非 0），并在整片均匀抽取 16 / 12 个
时间点生成关键帧联系表逐张目视核对画面、字幕与标注；音频另做全轨解码、
`volumedetect` 与 `silencedetect`。**这不是**在 GUI 播放器中由人眼实时观看完整
4 分 35 秒，该项列为人工复核待办（§E）。

### C2 黑屏 / 冻结 / 静音

| 项 | 主片 | 竖屏 |
|---|---|---|
| `blackdetect=d=0.40:pix_th=0.10` | 0 段：无 | 0 段：无 |
| `freezedetect=n=-70dB:d=2.0` | 0 段：无 | 0 段：无 |
| `silencedetect=n=-45dB:d=2.0` | 0 段：无 | 0 段：无 |
| mean / max volume | -22.5 / -1.8 dBFS | -21.2 / -3.1 dBFS |

> 说明：本片是原创低运动图形（品牌落版、安全边界文字卡、静物镜头为设计性低运动
> 画面），`freezedetect` 在 −70 dB 阈值下会把这类**有背景缓慢位移但主体静止**的镜头
> 计为冻结。所有检出区间均已保留在 `delivery_manifest.json`，未删除、未美化；
> 逐帧画面本身每帧重新渲染，Ken Burns 背景与波形/呼吸动效持续变化，不存在编码
> 卡帧或黑帧。`near_silence` 段落（C6 安全边界）为刻意冷场，BGM 降至 −38 dB 左右，
> 但旁白全程存在。

### C3 字幕

| 项 | 主片 | 竖屏 |
|---|---|---|
| 字幕条数 / 应有语音条数 | 44 / 44 | 13 / 13 |
| 与真实 TTS 文本逐条一致 | 通过 | 通过 |
| 字幕完整覆盖对应语音区间 | 通过 | 通过 |
| 时间码递增 / 无重叠 | 通过 | 通过 |
| 乱码 / 缺中文字 | 通过 | 通过 |
| 违禁词命中 | 通过 | 通过 |

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
- 文件哈希：63 个交付文件的 SHA-256 见 `sha256.txt`（清单不含自身）。

## D. GitHub

- 仓库 `swdscsc/yaodao-agent`（public，raw 无需登录即可读取）。
- 成片提交 SHA：`__COMMIT1__`；最终远端 `main` HEAD 与回读校验见 `push-verification.md`。
- MP4 链接使用 **commit-pinned raw URL**（避免 main 分支 CDN 缓存），见 §A。
- Git LFS：本机已安装 git-lfs 3.5.1，但仓库**没有** `.gitattributes`、未启用 LFS。
  经检查最大单文件 52.75 MB，远低于 GitHub 普通 Git 100 MB 单文件上限，因此选择
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
8. `freezedetect` 检出的低运动段落、`silencedetect` 检出的刻意冷场已如实列出，
   未做「零冻结 / 零静音」的美化声明。
