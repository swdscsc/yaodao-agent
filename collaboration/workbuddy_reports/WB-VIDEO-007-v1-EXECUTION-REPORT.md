# WB-VIDEO-007 执行报告（第一阶段样片）

日期：2026-11-09 · 状态：**样片已交付，等待 ChatGPT 对实际 MP4 独立审核**

## 一、成片（唯一核心交付）

- 文件：`E:\jobs\yaodao_ep\WB-VIDEO-007\final_mg_sample.mp4`
- SHA-256：`0152537176e4e7d0e4ba1462fdc2f7874b308d6a1f9372b7d53c1e49db9feb4a`
- 时长 28.2s（目标 20–30s ✓）· 1080×1920 竖屏 · 30fps · H.264 + AAC 48kHz 立体声 · 6.2MB
- 结构：钩子大字(3.3s) → 真机实拍介绍(6.9s) → 模拟服药卡(5.8s) → 安全边界对话(8.7s) → 品牌落版(3.3s)

## 二、质检结果（全部实测）

| 检查项 | 结果 |
|---|---|
| ffprobe 流信息 | 视频 h264 1080×1920 30/1 + 音频 aac 48kHz 双声道 ✓（ffprobe.json） |
| `-xerror` 全片逐帧解码 | exit 0，无损坏 ✓ |
| 渲染扫描 | 846 帧逐帧预检 0 异常后才落盘渲染 ✓ |
| 画面目检（16 帧联系表） | 无黑屏/花屏/乱码/出界/重叠 ✓ |
| ✓ 对勾字形 | 雅黑缺 U+2713 → 改矢量绘制后修复 ✓ |
| 音频电平 | mean −22.3dB / peak −0.9dB；无 ≥1.5s 静音 ✓ |
| 中文字幕 | 6 条与语音逐句对位，关键词双色高亮，宽度自适应不出界 ✓ |
| 合规标注 | 真机段「真实设备实拍」；模拟段「模拟界面·设计示意·示意数据」「对话示例·非用药建议」✓ |

**实际播放检查说明**：机器层面的验证已全绿；`-xerror` 全解码 + 16 帧联系表逐格目检已覆盖
「可播放、无坏帧、无乱码」。请审核方以实际播放为准，若发现音画不同步等问题按帧号反馈。

## 三、rea-video 接入与使用（免费本地模式）

- 仓库：`E:\jobs\rea-video`（GitHub 直连 502，codeload tarball 安装）；venv：`E:\jobs\rea-video\.venv`
- CLI 验证：`rea-video --help` 正常；`decompose` 实跑成功（112s）
- OCR extra 未装（Python 3.13 无 rapidocr 兼容版）→ 字幕时间轴由 agent 看帧核对
- VLM 未配置（不买 API）→ 由 agent 看图复核 9/9 镜并 apply-review 并入（改判 2 镜：
  shot_005 cg_3d→code_render、shot_006 still_motion→screen_capture）
- WorkBuddy Skill 接入：**install_skill.sh 不支持 WorkBuddy（读源码证实，非假设）**；
  已手动安装到 `C:\Users\asus\.workbuddy\skills\rea-video\`（SKILL.md + 8 个 references +
  LOCAL-SETUP.md），下个会话进入 Skill 列表
- 小红书链接：**在用户 Edge 浏览器成功打开**（《没有Opus，也能做自媒体MG动效视频！》，
  介绍 Fotor Agent）。笔记文字完整获取；页面 video 元素媒体地址为运行时签名加载，
  **无法合法取得文件直链，不做绕过** → 用仓库自带 v10 案例视频完成实机拆解

## 四、交付物清单（均在 E 盘）

| 文件 | 说明 |
|---|---|
| `WB-VIDEO-007\final_mg_sample.mp4` | 成片（见上） |
| `WB-VIDEO-007\reference-materials.md` | 仓库/小红书链接/用户原文/学习目的登记 |
| `WB-VIDEO-007\reference-analysis\report.html / report.md` | rea-video 拆解报告（已并入 agent 复核） |
| `WB-VIDEO-007\reference-analysis\visual-style-guide.md` | 可执行视觉规范（色值/缓动/字幕/标注/声音参数） |
| `WB-VIDEO-007\reference-analysis\storyboard.csv` | v10 案例 9 镜分镜表 |
| `WB-VIDEO-007\reference-analysis\rea-v10\` | 拆解原始输出（38MB：breakdown/报告/shots/stems） |
| `WB-VIDEO-007\sample_project\` | 制作工程源码（data.py/render.py/build_audio.py）+ frames + storyboard.csv |
| `WB-VIDEO-007\keyframes\contact-sheet.jpg` | 16 帧联系表 |
| `WB-VIDEO-007\ffprobe.json` / `sha256.txt` | 质检结果与哈希清单 |
| `WB-VIDEO-007\用户补拍素材清单.md` | 第二阶段清单（A/B/C 分级，6 项） |

## 五、素材来源与版权

- 旁白 n01/n04/n05：`E:\jobs\yaodao_ep\auto\narration\`（此前项目已生成的 TTS，文本见最终旁白稿.md，已核对产品事实红线）
- 真机实拍：`E:\jobs\yaodao_ep\raw\new_footage\cloud_A.mp4` t=40–47.06s（用户自有素材）
- 音效 whoosh/click/success/chime：`E:\jobs\yaodao_ep\auto\sfx\`（剪映素材库通用提示音）
- 配乐：**本工程 numpy 原创合成**（build_audio.py），无第三方音乐
- 参考片仅学手法，未搬运任何画面/配乐/素材

## 六、修改记录

1. v1 渲染在 t≈10.9s 崩溃（元组缺逗号）但管道吞掉退出码 → 产出无效 MP4 → **已删除重做**，
   并建立「全片逐帧预检 0 异常才落盘」流程
2. 钩子段逐字全部画在中心叠成一团 → 改为先测宽再逐字定位
3. 真机段出现两个重复「真实设备实拍」标注 → 去掉右下角标重复
4. 字幕过宽溢出 → 加自适应缩字（56→34px 分档）
5. 安全段用户气泡文字定位错误越界 → 改为气泡内边距定位
6. 「✓」缺字形显示 tofu → 改矢量 draw_check

## 七、未完成事项（如实）

- Remotion 未使用：Node 22 可用，但考虑到依赖下载与时间，样片用已验证的 PIL+FFmpeg
  代码渲染路线（同样是代码 MG，每帧重绘）；下一轮若需 CSS/React 级动效可切 Remotion
- 小红书教程视频未能合法下载，未做 decompose；其方法论已通过笔记文字 + v10 实机拆解覆盖
- 竖屏样片即为本次目标，未重做全片（按任务要求先样片后返工）
- 剪映两份原草稿（11月7日 加密格式、yaodao_yaodao_ep 7 张静态卡）已盘点，未做修改，
  原样保留
