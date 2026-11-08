# 素材来源清单（WB-VIDEO-006）

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
