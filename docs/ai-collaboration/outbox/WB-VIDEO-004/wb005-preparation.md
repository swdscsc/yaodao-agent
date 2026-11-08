# WB-VIDEO-005 准备草案（**未批准 · 未执行**）

| 项 | 值 |
|---|---|
| 状态 | `DRAFT / AWAITING_EXPLICIT_USER_APPROVAL` |
| 性质 | 下一阶段任务准备，**不是 WB-VIDEO-005 执行报告** |
| 前置基准 | `WB-VIDEO-004` 及本轮 `addendum-round2.md`（最终结论 `B · CONDITIONAL PASS`） |
| 本轮实际执行 | **无**。0 额度消耗、0 依赖安装、0 模型下载、0 剪映 GUI 操作、0 UI Automation、0 付费 |
| 生效条件 | 用户对本文件 §3 的审批项逐项明确批准后，才可在新任务书中下达执行 |

---

## 1. 目标

把 WB-VIDEO-003/004 已验证的「质检 + manifest + 状态机 + 只读调查」升级为**最小真实链路**，但**仍不制作正式宣传片**：

1. 解除 B1（Vidova GUI 窗口门）、B2（额度边界）、B4（剪映 Host 授权）、B6（本地 TTS）。
2. 按 `WB-VIDEO-003/e2e-plan.md` 的 15–20 秒、13 环节跑一次真实 E2E。
3. 产出可复算证据：真实素材、真实剪映导入/时间线/导出、真实中文旁白、逐项质检与返工记录。
4. 结束时停在正式宣传片制作之前，等待 ChatGPT 复核。

## 2. 必须继续遵守的防冒充红线

| 不得冒充 | 真实要求 |
|---|---|
| FFmpeg 参考渲染 ≠ 剪映导出 | 必须有剪映独立草稿导出的成片文件 |
| 合成图案 / 测试彩条 ≠ AI 生成素材 | 必须标注 `source_type`，D005 的 5.5–8.5 s 明确为占位 |
| 静音或 440 Hz 测试音 ≠ 正式旁白 | 必须产出可播放中文语音 WAV 并通过音频质检 |
| 占位界面 ≠ 真实产品功能 | 真实界面优先；模拟界面必须显式标注 |
| 接口存在 / 可调用 ≠ 生成有效视频 | 四级能力分级继续沿用 |
| 自动 PASS ≠ 人工 PASS | 三个 MANUAL_ITEMS + 具名字号确认逐项签核，生产 context 固定 |
| 测试上下文 ≠ 生产签核 | `evaluate_subtitle_fix()` 内部固定 production，隔离 harness 结果永不入生产台账 |

## 3. 需用户明确批准的 10 项（集中清单）

| # | 审批项 | 风险/边界 | 未批准时的状态 |
|---|---|---|---|
| A1 | **1 次最小额度 `generate_asset`**，并给出剩余额度上限与单次成本 | 必须先确认免费额度余量、单次是否扣额度、有无自动续费；额度不明确即停止 | 0 调用 |
| A2 | 在独立空草稿中启动/操作剪映 GUI，现有 2 个草稿只读 | 不得覆盖、删除、导入到用户正在使用的项目 | 0 草稿 |
| A3 | 限定窗口内的 UI Automation（Vidova 托盘 `open-project`、剪映测试草稿） | 只允许具名窗口，不操作账号设置或其他窗口 | 0 次 |
| A4 | 安装本地免费 TTS 依赖（包来源、许可证、体积、联网/GPU 需求见 `tts-research.md` §4） | 不装来源不明程序；CPU/核显方案优先 | 0 安装 |
| A5 | 试装 `faster-whisper`（CPU）、`PySceneDetect`（纯 CPU）并下载模型 | 需列明模型体积与来源；不依赖独立 NVIDIA 显卡 | 0 下载 |
| A6 | 观察 `vidova://` 协议行为（不触发登录/账号动作） | 只是线索，尚未证明能打开项目 | 0 观察 |
| A7 | 是否清理空 Vidova 测试项目 `893d1af1-…` | 删除类操作，默认保留 | 保留 |
| A8 | 撤销并轮换此前明文出现过的 GitHub 凭据 | 继续只用系统受保护凭据存储 | 仅提醒 |
| A9 | D004 是否允许进入第 3 轮返工 | 当前返工 2/2 用尽，`third_cycle_allowed=false`，硬停在 `REVIEW_REQUIRED` | 不返工 |
| A10 | 竖屏原生重排是否按 `blockers.md` §2 执行 | 不得简单裁切横屏；需独立 9:16 布局与安全区复检 | 不执行 |

> A1–A5、A9、A10 会消耗额度、安装软件或改变工程状态，**必须逐项明确批准**；A6–A8 属于只读/安全类，也一并列出以便一次确认。

## 4. 批准后建议的执行顺序（仅计划，本轮不执行）

| 阶段 | 动作 | 可验证产物 |
|---|---|---|
| S0 | 拉取远端 `main`，核对最新 inbox / 历史报告 / `pipeline-status.json` | 基准 commit SHA、干净工作区 |
| S1 | 零消耗前置：确认额度余量、剪映 Host 授权链路、TTS 依赖清单 | `environment-audit.md`、`quota-and-cost.json` |
| S2 | 合法打开 Vidova 编辑器窗口（A3/A6），零额度完成项目创建 + `absolutePaths` 素材导入 | MCP 调用日志、窗口状态证据 |
| S3 | 1 次最小额度生成（A1），登记 12 字段 manifest，跑严格 QA | 真实素材文件 + `qa_report.json` |
| S4 | 本地 TTS 生成中文 WAV（A4），检查有声/完整/无截断/语速/音量/可导入剪映 | `narration.wav` + 音频质检证据 |
| S5 | 剪映独立空草稿（A2）：导入 → 时间线 → 字幕 → 音轨 → 导出 | `draft_content.json` 前后 SHA、导出成片 |
| S6 | 15–20 秒 13 环节真实 E2E，逐环节记录实际状态 | `e2e-result.json`，区分 PLAN/RUN/BLOCKED |
| S7 | 成片严格质检（冻结白名单、字幕逐项签核、横竖屏安全区）+ 有界返工 | `qa_report.json`、缺陷台账 |
| S8 | 汇总 `report.md` + 状态文件，推送并核对远端 HEAD | commit SHA + 全部链接 |

## 5. 准入与停止条件

- **准入**：A1–A5 至少全部获批，且额度/授权/依赖三项均有可验证证据；否则只允许继续只读调查与质检工作。
- **费用边界**：0 购买、0 充值、0 自动续费、0 未批准的云端额度消耗。发现免费额度也要先确认余量、单次成本与收费条件。
- **工程边界**：不修改用户已有剪映工程、不覆盖草稿、不删除素材/缓存、不导入到用户正在使用的项目、不公开发布视频、不上传隐私或密钥。
- **停止**：完成最小真实 E2E 后**立即停在正式宣传片制作之前**，提交阶段报告并等待 ChatGPT 复核；不得因局部成功宣称整条流水线打通。
- **结论口径**：仍只能给 A `PASS` / B `CONDITIONAL PASS` / C `FAIL` 三者之一，不得为提高状态虚构证据。

## 6. 建议交付目录

`docs/ai-collaboration/outbox/WB-VIDEO-005/`：`report.md`、`environment-audit.md`、`quota-and-cost.json`、`shot-manifest.json`、`narration/`、`jianying-draft-evidence/`、`e2e-result.json`、`qa_report.json`、`test-results.json`、`blockers.md`、`evidence/`（含 `manifest.sha256.json`）；并更新 `docs/ai-collaboration/status/pipeline-status.json`。

> 本文件仅为准备草案。**在用户逐项明确批准前，不会执行上表任何动作。**
