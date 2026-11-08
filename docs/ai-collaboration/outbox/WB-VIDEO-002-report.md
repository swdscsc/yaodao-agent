# WB-VIDEO-002 阶段报告 — 完整技术调查 / 接口验证 / 架构设计 / 最小端到端测试

| 项 | 值 |
|---|---|
| Task ID | WB-VIDEO-002（承接 WB-VIDEO-001，inbox 无更新任务） |
| Status | `partial` — 参考链路端到端跑通；Vidova GUI 窗口绑定与剪映 Host 授权两处**未打通** |
| Start / End | 2026-11-08 14:55 / 15:22 +0800（Asia/Shanghai, UTC+8） |
| 基线提交 | `5a5dbb6fde2d4bb6182328c31b4a3a2cf9fdb9c9`（WB-VIDEO-001 报告，本轮已确认在远端） |
| 分支 | `main` |
| 报告路径 | `docs/ai-collaboration/outbox/WB-VIDEO-002-report.md` |
| 源码 / 证据 | `docs/ai-collaboration/outbox/WB-VIDEO-002/` |

---

## 0. 结论与边界声明

本轮**真实跑通了一条零付费额度的端到端参考链路**：分镜表 → 本地合成素材 → 自动质检 → 统一 manifest → 缺陷检测 → 有界返工 → 重新导出 → 成片质检 → AI 视觉复核。产物是两个可解码、可验证的 MP4（横屏 1920×1080、竖屏 1080×1920，各 12.036 s / 30 fps，9 项质检全 PASS）。

**但必须明确**：这两个成片由 **FFmpeg 参考渲染器**产出，**不是剪映导出**；素材是 **FFmpeg 合成测试图案**，**不是 AI 生成、也不是真实拍摄**；旁白只有文本与字幕，**没有真实 TTS 音轨**。**整条目标流水线（Vidova 生成 → 剪映剪辑 → 导出 → 质检 → 返工）尚未打通**，两处硬阻塞见 §7。本报告不把参考链路成功等同于流水线成功。

---

## 1. 开工前状态核对（避免重复劳动）

- `git fetch` + `ls-remote`：远端 HEAD = `5a5dbb6…`，与本地一致。
- `inbox/` 仅有 `WB-VIDEO-001-bootstrap-pipeline.md`，**无新任务**；`outbox/` 仅有 `WB-VIDEO-001-report.md`；`status/` 有上一轮 `pipeline-status.json`。
- WB-VIDEO-001 报告遗留的推送问题已解决（用用户提供的凭据完成一次性认证，未写入仓库、未改 remote 配置、未改全局 git config），`ca4afb7..5a5dbb6 main -> main` 已确认。
- 因此本轮在 WB-VIDEO-001 的发现基础上继续，**未重复调查**端口/工具清单，只验证新增能力。

---

## 2. 机器与应用版本（沿用 WB-VIDEO-001，新增项已标注）

| 项 | 值 |
|---|---|
| OS | Windows 11 家庭中文版 10.0.22631.6199 |
| git / curl | 2.55.0.windows.3 / 8.13.0 |
| Python / Node | 3.13.14 / v22.22.2 |
| FFmpeg | 7.1-essentials（PATH）；滤镜 `blackdetect / silencedetect / freezedetect / volumedetect / subtitles / gblur / concat` 全部可用 |
| ffprobe | 不在 PATH；使用剪映内置 `1.0.0-401a53202a` |
| Python 库 | PIL / numpy / cv2 / requests 均可用 |
| Vidova | 1.0.66.0，`127.0.0.1:17373`，MCP `POST /mcp`（18 工具） |
| 剪映专业版 | 11.7.0.14652，`jianying-agent-cli.exe`，47 条 hubcli 契约 |
| 网络 | GitHub 需本机 `127.0.0.1:7897` 代理（按命令临时指定，全局配置未改） |

---

## 3. 架构设计（已落地为可运行源码）

### 3.1 统一素材协议
`manifest.json` 实件，去重键 `(shot_id, source_type, checksum_sha256)`，`asset_id = S###-A##` 唯一编号。每条记录含用户要求的全部字段：`asset_id / file_path（相对） / file_type / duration_seconds / width / height / fps / shot_id（对应分镜） / source_type + source（素材来源） / is_ai_generated + is_real_footage / qa_status + quality_checks / allow_edit`，另加 `checksum_sha256 / generation_status / retry_count / timecode_start / notes`。

**`allow_edit` 是硬门槛**：仅当 `qa_status == PASS` 且 SHA-256 已记录且未被标记为 SUPERSEDED 才为 `true`。本轮 5 条素材中只有 3 条允许进入剪辑。

### 3.2 任务状态机
`PENDING / GENERATING / COMPLETED / FAILED / VALIDATING / REVIEW_REQUIRED / APPROVED / EDITING / EXPORTED / QA_CHECKING / DELIVERED / ESCALATED`，非法流转直接抛错。实测累计 **56 次**流转，全部记录在 `evidence/state_log.json`。

### 3.3 有界重试与硬停止
- 单镜头最大生成尝试 3 次，生产退避 5/15/45 s（E2E 注入 0.2/0.4/0.8 s 加速档，已在报告中标注）。
- 返工闭环最大 **2 轮**；实测第 2 轮后 `third_cycle_allowed = False`，`REWORK_CYCLE_3` 被置为 `REVIEW_REQUIRED` 人工审核节点，**不再自动修复**。
- 缺陷路由：`asset → vidova`、`clip → jianying`、`audio → audio_module`、`subtitle → subtitle_module`、`render → renderer`。

### 3.4 源码清单

| 文件 | 职责 |
|---|---|
| `core.py` | MCP 客户端、manifest、状态机、重试策略、缺陷台账 |
| `qa.py` | FFmpeg 9 项质检、关键帧、帧内/跨素材重复检测 |
| `run_e2e.py` | 首次端到端编排（含 Vidova MCP 编排与参考渲染） |
| `rework.py` | 返工闭环、缺陷修复、重新导出、重新质检 |
| `shotlist.json` | AI 导演形态的分镜表输入样例 |

---

## 4. 端到端执行与逐阶段真实证据

### A. 素材生成（零额度）
`shotlist.json` 3 个镜头 → FFmpeg 合成 3 个 1920×1080/30fps MP4（`testsrc2` / `smptebars` / 纯黑+静音）。全部生成成功，文件存于本机 `<PIPELINE>/assets/`，**未调用 `generate_asset`、未调用 `transcribe`、未消耗任何托管额度**。

### B. 自动质检 + manifest
S001-A01、S002-A01 通过；S003-A01 被判定 FAIL（`black_frames` + `silence`，`peak_db = -91.0`，blackdetect 命中 `0.0–1.9667s`、silencedetect 命中 `0.0–2.0053s`）。3 条记录写入 manifest，只有 2 条 `allow_edit=true`。

### C. 第一轮返工闭环
- 缺陷 D001（黑屏，`owner=vidova`）、D002（静音，`owner=audio_module`）。
- 修复：生成**新文件** `S003-A02.mp4`（不覆盖、不删除 `S003-A01`），重新质检 PASS，两条缺陷 `FIXED`，`retry_count=1`。
- 素材总数 3 → 4，允许进入剪辑 3 条。

### D. Vidova MCP 真实编排（**发现硬阻塞**）
`initialize` + `tools/list`（18 工具）+ `get_active_project` + `create_project` 均成功，但 `create_project` 返回：

```
Created local project "WB-E2E-20261108-TEST" (893d1af1-0d6e-42a9-9489-a996307faeb7)
and set it active. Open it in Vidova before using editor tools.
```

其后 `import_asset / asset list / timeline_edit / timeline_get_state / preview` **全部**返回：

```
No open Vidova editor window is registered for projectId 893d1af1-...
```

已尝试的合理替代方案（均真实执行）：
1. `import_asset` 参数名探测 5 种（`paths / files / filePaths / path / absolutePaths`）→ 全部因窗口未注册失败，**参数契约仍未确认，不虚构**。
2. `set_active_project` 切到新项目 → editor 工具仍失败。
3. 对照验证：切回原项目 `042ac827-…`（GUI 已打开）→ `timeline_get_state` 立即恢复正常（1 layer / 1 clip / 58.33 s）。
4. 静态分析 `app.asar`（317 MB）：定位错误串 `"MCP dispatch failed; project editor is not registered"`，并发现 **`AppTrayCommandSchema` 定义了 `open-project` + `projectId` 托盘命令**，但 MCP 的 18 个工具中**没有对应工具**。

→ 结论：Vidova editor 类自动化必须先通过 GUI（托盘/项目列表）打开项目窗口，MCP 自身做不到。`evidence/mcp_call_log.json` 记录 17 次调用，`quota_consuming_calls = []`。

**副作用与处置**：新建的空测试项目 `WB-E2E-20261108-TEST`（`893d1af1-...`）已保留且**未导入任何素材**；`finally` 中已把 active project 恢复为 `042ac827-…` 并验证成功（`get_active_project` 返回原项目）。MCP 无 `delete_project` 工具，清理需用户批准，见 §11 审批项 3。

### E. 剪映自动化（**仍被 Host 授权阻塞**，本轮深挖）
- `jianying-agent-cli.exe draft query-content --input <json文件> --output <json文件>` → `PERMISSION_DENIED: JIANYING_AGENT_RUNTIME_TOKEN is required`。
- `hubcli/cli.mjs` 源码明写：`参数和回执仅用于 Shell I/O；业务身份、授权和交付由 Host 持有` → 该 CLI **无法脱离剪映主程序独立运行**；主程序本轮仍**未启动**。
- `contracts.json`：protocol `custom-agent.hub-cli.v1`，47 条命令；写操作 `risk=confirm_before_write`（如 `asset.export` 需 `request_id/asset_id/relative_path`，`canvas.batch` 需 `request_id/input`）。
- **新增发现**：两个草稿工程的 `draft_content.json` **格式不同** —— `11月7日` 是 4,928 B 的加密 base64 风格文本（头 `8ec4+gKe5...`），`yaodao_yaodao_ep` 是 29,205 B 明文 JSON（`canvas_config.width=1920`）。这进一步证明**伪造工程文件不可行**，也说明导入导出需走官方通道。
- 两个现有工程**只读解析，一个字节未改**。

### F. 参考渲染（替代路径，明确非剪映导出）
按统一分镜表与 timecode 生成：片头卡 / S001 / 章节卡 / S002 / S003 / 片尾卡 → concat → 字幕烧录（`subtitles.srt`）→ BGM（220 Hz 低音量）+ 转场音效 + 主音轨 `amix` → 横屏成片；竖屏用**模糊背景填充**替代纯黑 letterbox。片头/章节/片尾卡片为高饱和撞色 + 粗黑边硬阴影（贴合用户美式漫画偏好）。字幕 `.srt` 与旁白 `narration.txt` 作为文本交付。

### G. 成片质检 + AI 视觉复核（发现 3 个真实问题并修复）

**质检模块自身的假阴性（已修复）**：`freezedetect` 实际输出为 `lavfi.freezedetect.freeze_start: 0`，且整段冻结时**不输出 `freeze_end`**；原正则要求三字段同时出现，导致静态彩条/纯黑帧全部漏检。已修正 `qa.py`，并做阳性对照：

| 素材 | 修复后 freeze 命中 | 判定 |
|---|---|---|
| S001-A01（动态 testsrc2） | 否 | PASS |
| S002-A01（静态彩条） | 是（freeze until EOF） | `EXPECTED_STATIC` |
| S003-A01（纯黑） | 是 | FAIL |
| S003-A02（动态） | 否 | PASS |

新增 `static_material_expected` 策略：静态图形卡按设计意图不算缺陷，但**原始检测区间完整保留**在 `qa_report.json`，不隐瞒。

**跨素材重复镜头（真实缺陷）**：像素比对 `S001-A01` vs `S003-A02` 平均绝对差 **0.000**（完全相同），AI 视觉复核也确认两格画面一致 → 记为 D003。

**竖屏视觉缺陷**：letterbox 版约 **69% 纯黑**、`bottom_text_band_luma = 0.0`，字幕随横屏缩放后过小且偏位 → 记为 D004。

### H. 第二轮有界返工 + 重新导出 + 重新质检
- D003 → 用 `testsrc`（明显不同的圆形动态图案）生成 **新文件** `S003-A03.mp4`，质检 PASS；把 `S003-A02` 标记 `SUPERSEDED`（`allow_edit=false`，防止重复导入），原文件全部保留。
- D004 → 竖屏改为从**无字幕**时间线构建 + 模糊背景填充 + 独立竖屏字号字幕重烧 + 音轨复用。
- 重新导出 `final_horizontal_v2.mp4` / `final_vertical_v2.mp4`（v1 全部保留作前后对比证据，**未覆盖任何文件**）。
- 重新质检与复核结果：

| 指标 | 横屏 v2 | 竖屏 v2 |
|---|---|---|
| 分辨率 / 帧率 | 1920×1080 / 30 fps | 1080×1920 / 30 fps |
| 时长 | 12.036 s | 12.036 s |
| 9 项质检 | 全 PASS | 全 PASS |
| 音频峰值 | −20.7 dB（无爆音） | −20.7 dB |
| 音画同步 | Δ 0.036 s | Δ 0.036 s |
| 关键帧 | 5 张 | 5 张 |
| 帧内重复镜头 | 0 | 0 |
| 冻结原始检测 | 命中（静态卡片，策略放行） | 命中（静态卡片，策略放行） |

- 缺陷台账：**4 条全部 FIXED**；重复镜头 **1 → 0**；返工 **2/2 轮**，`REWORK_CYCLE_3` 被硬停止在 `REVIEW_REQUIRED`。
- AI 视觉复核（联系表 `evidence/contact_sheet_v2.jpg`）确认：S001 与 S003-A03 画面明显不同；S003-A01 全黑；横屏字幕在底部安全区清晰可读；竖屏字幕已放大可读。**遗留**：竖屏字幕仍偏画面中部、上下为模糊填充而非原生竖屏重排 —— 因已达返工上限，按纪律**不再自动修复**，交人工审核。
- 语义一致性 / 人物物体畸形检查：本轮素材为合成测试图案，**不适用**，需在真实素材阶段验证，不能伪造结论。

---

## 5. 五类结论汇总

| 类别 | 项目 |
|---|---|
| **confirmed working** | GitHub 拉取/推送；Vidova MCP 握手与 18 工具；本地只读工具；素材真实路径；FFmpeg 合成 5 条素材；9 项自动质检（含修复后的冻结检测）；manifest 去重与唯一编号；状态机 56 次流转；2 轮返工闭环与硬停止；横/竖屏参考渲染与导出；成片 9 项质检全 PASS；关键帧 + AI 视觉复核；字幕/旁白文本交付 |
| **detected but not tested** | Vidova `import_asset` 的真实参数名；`timeline_edit / preview / component` 写操作；剪映 47 条 hubcli 写契约；剪映工程 UI 导入导出；UI Automation 窗口自动化 |
| **unavailable** | Vidova MCP 导出/渲染工具；Vidova ↔ 剪映官方直连接口；MCP 中打开项目窗口的工具；剪映 CLI 的 `delete_project` 类能力；真实 TTS 引擎 |
| **blocked by permissions** | 剪映 agent CLI 实际编辑调用（`JIANYING_AGENT_RUNTIME_TOKEN`，由 Host 持有）；Vidova editor 类工具（需 GUI 项目窗口已注册） |
| **not attempted** | `generate_asset` 真实生成任务（消耗托管额度，需审批）；真实 jobId 轮询；剪映创建空草稿/导入/剪辑/导出；真实 AI 生成素材的语义一致性与畸形检查（需真实素材） |

---

## 6. 交付清单

**仓库内（本轮提交，全部为文本/小图）**

| 路径 | 内容 |
|---|---|
| `outbox/WB-VIDEO-002-report.md` | 本报告（唯一阶段报告） |
| `outbox/WB-VIDEO-002/*.py/.json` | 调度器、质检、返工、分镜表源码 |
| `outbox/WB-VIDEO-002/evidence/*.json` | manifest / defects / state_log / mcp_call_log / e2e_result / rework_result / qa_report（均已脱敏） |
| `outbox/WB-VIDEO-002/evidence/manifest.sha256.json` | 所有证据文件 SHA-256（可验证性） |
| `outbox/WB-VIDEO-002/evidence/contact_sheet_v2.jpg` + 3 张关键帧 | AI 视觉复核缩略图 |
| `outbox/WB-VIDEO-002/evidence/subtitles.srt`, `narration.txt` | 字幕与旁白文本 |
| `status/pipeline-status.json` | 机器可读流水线状态 |

**本机（未提交大媒体，路径仅存仓库外 `config.local.json`）**

`<PIPELINE>/renders/final_horizontal_v2.mp4`（2,631,613 B）、`final_vertical_v2.mp4`（949,375 B）、5 条素材、v1 成片、卡片 PNG、BGM/SFX、全部关键帧。**证据 JSON 中不含任何绝对路径、用户名或密钥**（已脚本扫描，`leaks: []`）。

---

## 7. 使用说明（复现）

```bash
# 依赖：Python 3.13 + pillow/numpy/opencv-python、FFmpeg 7.1、ffprobe
# 本机 config.local.json 提供 ffmpeg/ffprobe/mcp_url（不提交仓库）
cd docs/ai-collaboration/outbox/WB-VIDEO-002
python -m py_compile core.py qa.py run_e2e.py rework.py
python run_e2e.py --root <本机 pipeline 目录> --config <config.local.json> --shots shotlist.json
python rework.py  --root <本机 pipeline 目录> --config <config.local.json> --shots shotlist.json
```

`run_e2e.py` 的 `finally` 保证恢复 Vidova 原 active project；`--skip-mcp` / `--skip-render` 可分段调试。所有产物写到新的 `*_v2` 文件，不覆盖既有文件。校验请对照 `evidence/manifest.sha256.json`。

---

## 8. 已知问题与未验证假设

1. **成片不是剪映导出**：剪映 Host 授权未打通，FFmpeg 参考渲染器只是占位实现，不能替代剪映工程交付。
2. **Vidova editor 写操作未验证**：`import_asset` 参数名、时间线编排、预览取帧均因 GUI 窗口未注册而未执行；`app.asar` 中的 `open-project` 托盘命令是下一阶段最有希望的入口，但未验证可触发。
3. **Vidova 无导出工具**：即使 editor 打通，成片仍需剪映或外部渲染器。
4. **额度边界未验证**：`generate_asset` 的 `prompt/durationSeconds/jobId` 等参数未出现在 `inputSchema`，参数契约仍未知；本轮零调用。
5. **竖屏非原生重排**：模糊背景填充 + 字幕偏中部，属已知遗留，已因返工上限转人工审核。
6. **静态素材冻结策略**：`static_material_expected` 是为测试图案设计的白名单，生产真实素材**不得**开启，否则会掩盖真冻结。
7. **语义一致性 / 畸形检查不适用**：合成彩条素材无人物与叙事，不能据此宣称 AI 视觉质检已完备。
8. **剪映草稿格式不统一**（加密 / 明文并存），任何绕过官方通道的工程写入都不可靠。
9. **测试项目残留**：`WB-E2E-20261108-TEST`（`893d1af1-...`）为空项目，无素材，需用户批准才能清理。
10. **GitHub 凭据**：本轮使用用户提供的凭据完成一次性推送；凭据值未写入任何仓库文件、remote 或全局配置。由于该值曾以明文出现在对话中，**建议用户在方便时轮换**。

---

## 9. 下一阶段完整任务建议（可直接作为 inbox 任务书 WB-VIDEO-003）

- **Task ID**：WB-VIDEO-003
- **Goal**：打通两个硬阻塞，把「参考链路」升级为「Vidova 生成 → 剪映编辑 → 剪映导出」的真实链路，并把 FFmpeg 渲染器降级为兜底。
- **Scope**：接口打通 + 1 个镜头的最小真实生成/剪辑/导出验证；不生成完整宣传片。
- **Inputs / source commit**：本报告、`evidence/*.json`、`WB-VIDEO-002/*.py`、本机 `<PIPELINE>/`、剪映 11.7.0.14652、Vidova 1.0.66.0。
- **Exact actions**：
  1. **Vidova GUI 窗口**：验证 `app.asar` 中 `AppTrayCommandSchema` 的 `open-project` 命令能否经托盘/项目列表 UI Automation 触发；或在 UI 中手动打开 `WB-E2E-20261108-TEST` 后，重新跑 `import_asset` 5 种参数探测，确定真实契约，再实测 `timeline_edit addClip → timeline_get_state → preview captureFrame`。
  2. **额度测试（仅审批后）**：调用 1 次 `generate_asset kind=image`（最小尺寸），记录真实参数、`jobId`、`kind=status` 轮询序列、结果落盘绝对路径、ffprobe 校验；同时确认账户额度余量，绝不购买。
  3. **剪映 Host 授权**：启动剪映主程序，确认 `JIANYING_AGENT_RUNTIME_TOKEN` 是否由运行时注入；若可用，按 `query-content → plan-patch → validate-patch → apply-patch` 顺序，在**全新独立草稿**上验证导入 1 个素材、排 1 个镜头、烧 1 条字幕、导出 1 个 MP4。全程不打开/不修改 `11月7日`、`yaodao_yaodao_ep`。
  4. **若剪映原生接口仍不可用**：评估 UI Automation 可行性（Qt/CEF 控件树枚举），并明确记录不可行的具体原因，不得伪造工程文件。
  5. **真实 TTS**：调研本机可用 TTS（剪映 `canvas.audio.add/setTtsVoice` 或系统语音），生成 1 段旁白音轨替换占位。
  6. **竖屏原生重排**：按竖屏分镜重新构图（非缩放），修复字幕位置遗留问题。
  7. 更新 manifest / 状态机 / 质检报告，重新跑 `rework.py` 验证闭环。
- **Acceptance criteria**：① Vidova 至少有 1 次真实 `import_asset` + `timeline_edit` 成功的原始返回；② 剪映至少有 1 次真实 `apply-patch` 或导出 MP4 的证据（ffprobe 可验证）；③ 成片来自剪映导出而非 FFmpeg 参考渲染；④ 所有现有工程与素材未被修改；⑤ 额度消耗有明确上限与记录；⑥ 报告区分五类结论。
- **Safety limits（需用户集中确认，见下）**：不购买额度、不删除/覆盖任何现有工程或素材、不公开发布、不上传隐私素材、不提交任何凭据。
- **Expected report path**：`docs/ai-collaboration/outbox/WB-VIDEO-003-report.md`。

### 需用户一次性确认的审批清单（集中列出，不逐条打断）

| # | 事项 | 类别 |
|---|---|---|
| 1 | 是否允许消耗 **1 次最小额度**做 `generate_asset` 测试，并确认额度余量上限 | 付费/额度 |
| 2 | 是否允许**启动剪映专业版主程序**、创建独立空草稿（不触碰现有 2 个工程） | 应用操作 |
| 3 | 是否允许清理本轮新建的空 Vidova 项目 `893d1af1-0d6e-42a9-9489-a996307faeb7` | 删除 |
| 4 | 是否允许 UI Automation 控制桌面（会短暂占用鼠标/键盘） | 桌面控制 |
| 5 | 是否允许使用剪映/系统 TTS 生成旁白（若涉及会员或云端额度需先说明） | 潜在付费 |
| 6 | GitHub 推送凭据后续沿用方式（建议轮换并改用本机凭据管理器，不再明文传递） | 凭据 |

---

## 10. 安全与合规声明

- 未删除或覆盖任何原有素材、草稿工程、仓库文件；所有新产物使用新文件名与唯一 `asset_id`。
- 未购买任何服务、未消耗任何托管额度：`generate_asset` / `transcribe` 调用数 **0**。
- 未伪造接口、未伪造项目文件、未把未验证能力标为成功；剪映与 Vidova 的两处阻塞均如实记录。
- 未提交任何 token / PAT / 密码 / 个人隐私路径；证据已脚本扫描确认无泄漏。
- 未公开发布任何内容；推送仅限用户指定的私有协作仓库 `main` 分支，无 force-push。
- **参考链路端到端成功 ≠ 整条流水线成功**，下一阶段仍需 ChatGPT 审核后再执行。

**本轮到此停止，等待审核。**
