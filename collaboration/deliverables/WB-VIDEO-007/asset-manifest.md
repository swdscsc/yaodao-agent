# asset-manifest — WB-VIDEO-007 v1 交付物清单

> 版本：v1 · 日期：2026-11-09 · 仓库：https://github.com/swdscsc/yaodao-agent（公开）
> 本文件列出本目录全部文件的用途、下载地址与 SHA-256，供 ChatGPT 与用户核对。

## 成片下载

- **直接下载**（GitHub Release 资产，不随后续提交变化）：
  https://github.com/swdscsc/yaodao-agent/releases/download/wb-video-007-v1/final_mg_sample.mp4
- **仓库内文件**（在 main 分支）：
  https://github.com/swdscsc/yaodao-agent/blob/main/collaboration/deliverables/WB-VIDEO-007/final_mg_sample.mp4
- **原始下载**（浏览器/程序通用）：
  https://raw.githubusercontent.com/swdscsc/yaodao-agent/main/collaboration/deliverables/WB-VIDEO-007/final_mg_sample.mp4

上传方式说明：MP4 **原样上传，未重新编码、未降低画质**，上传前后 SHA-256 一致（见下表）。

## 文件清单

| 文件 | 用途 | SHA-256 |
|---|---|---|
| `final_mg_sample.mp4` | 28.2s 竖屏 MG 样片成片（1080×1920 30fps H.264+AAC，6.2MB） | `0152537176e4e7d0e4ba1462fdc2f7874b308d6a1f9372b7d53c1e49db9feb4a` |
| `storyboard.csv` | 样片 5 段分镜时间表 | `5271a10da39711bf57feb2c5ae2e656e558e545a2985041352e7913b26dfeefd` |
| `visual-style-guide.md` | 可执行视觉规范（色值/缓动/字幕/标注/声音参数） | `4690ae4485210e1b761cf8a8f3723104afcc221f58cc3ca27d43c75e377d5763` |
| `reference-analysis.md` | rea-video 参考片拆解报告（9 镜，已并入人工复核改判） | `ff1e3f952de29b5207411dab567671e41c9bf9cf010a2ac05c22fa3005473378` |
| `sha256.txt` | 本目录哈希清单 | — |
| `asset-manifest.md` | 本文件 | — |

## 校验方法

```bash
curl -L -o final_mg_sample.mp4 https://github.com/swdscsc/yaodao-agent/releases/download/wb-video-007-v1/final_mg_sample.mp4
sha256sum final_mg_sample.mp4
# 应等于 0152537176e4e7d0e4ba1462fdc2f7874b308d6a1f9372b7d53c1e49db9feb4a
```

## 未纳入本目录的大体积原始工程

样片制作工程源码（`data.py` / `render.py` / `build_audio.py`）、846 帧渲染帧、拆解原始输出
（38MB）保留在本地 `E:\jobs\yaodao_ep\WB-VIDEO-007\`，未上传仓库（避免仓库膨胀）；
如审核需要，可按需上传指定文件。
