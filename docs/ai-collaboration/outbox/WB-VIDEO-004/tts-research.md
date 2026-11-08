# WB-VIDEO-004 · 免费本地配音（TTS）研究与实测

| 项 | 值 |
|---|---|
| 任务目标 | 生成一段真正可播放的**中文** WAV，并检查有声、完整、无截断、语速、音量、可导入剪映 |
| **本轮结论** | **`chinese_tts_wav_generated = false`，`tts_status = NOT_COMPLETE`** |
| 真实产出 | 一个 **440 Hz 正弦合成测试音** WAV（**明确标注不是语音、不是旁白**），用于验证音频质检链路 |
| 机器可读证据 | `evidence/tts_probe_004.json` |
| 付费 / 云端额度 | **0 购买、0 充值、0 自动续费、0 未批准云端调用** |

---

## 1. 为什么没有中文语音 WAV（逐层拦截，均未绕过）

任务书要求"不要绕过系统安全策略"。本轮尝试了三条使用 Windows 内置 SAPI 的路径，全部被**工具层安全策略**拒绝：

| # | 尝试 | 结果 | 安全层原文 |
|---|---|---|---|
| 1 | 运行时加载 .NET 语音程序集以使用托管语音合成 API | **BLOCKED** | `Command blocked for security: Add-Type compiles and loads .NET code at runtime` |
| 2 | 实例化系统已注册的 SAPI 语音 COM 组件 | **BLOCKED** | `Command blocked for security: COM object instantiation can run arbitrary code (e.g. WScript.Shell)` |
| 3 | 通过 Windows 脚本宿主调用 SAPI | **BLOCKED** | `Command blocked for security: Known Windows LOLBin that can execute arbitrary code outside command validation` |
| 4 | 用 Python `ctypes` / 进程内 COM 绕开上述拦截 | **NOT_ATTEMPTED** | 属于规避同一安全策略，任务书明确禁止 |

**合规声明**：没有禁用、修改、规避任何安全策略；没有用包装器重试被拦能力；没有安装来源不明的程序；没有读取或伪造任何凭据。

只读注册表确认系统存在语音 token（本轮 `HKLM\SOFTWARE\Microsoft\Speech\Voices\Tokens`）：

- `TTS_MS_EN-US_ZIRA_11.0`（英文）
- **`TTS_MS_ZH-CN_HUIHUI_11.0`（中文普通话）**

上一轮 `environment_probe.json` 还记录了 4 个中文 SAPI/OneCore 语音名（Huihui Desktop / Huihui / Kangkang / Yaoyao），来源是不同注册表分支（SAPI 5 桌面 vs OneCore）。**语音存在 ≠ 能合成**：调用通道被安全策略挡住。

本机 Python TTS 包检查：`whisper / faster_whisper / torch / onnxruntime / edge_tts / TTS / pyttsx3 / win32com / comtypes` **全部缺失**；PATH 中也没有 `espeak-ng / piper / flite / festival / say / sox` 等本地免费 TTS 可执行文件。

---

## 2. 真实做成的部分：音频链路与质检工具验证

用本机已装的 FFmpeg 7.1 生成一段**明确标注为合成测试信号**的 WAV，并跑通音频质检命令：

| 检查 | 实测值 |
|---|---|
| 文件 | `pipeline/tts004/audio_chain_test_tone.wav`（**仅本机，未提交仓库**），240,078 bytes，SHA-256 `a24003869a02105b0ba9a354c2850e6fc5357bb3262441252c20b12d9cceadd5` |
| ffprobe | `pcm_s16le` / 48,000 Hz / 单声道 / 16 bit / 2.500000 s |
| `volumedetect` | `mean_volume = -33.1 dB`，`max_volume = -30.1 dB` |
| `silencedetect`（-40 dB, ≥0.5 s） | **0 个长静音事件** |
| 导入剪映 | **未测试**（未创建独立草稿，见 `vidova-jianying-next-steps.md`） |

⚠️ **这段 WAV 是 440 Hz 正弦波，不是中文语音、不是旁白、不是配音。** 它只能证明"FFmpeg 能产出可播放 PCM WAV + 音频 QA 命令可用"，**不能证明 TTS 完成**。任务书明确"没有实际音频文件，不允许标记 TTS 完成"，因此本轮 TTS 状态保持 `NOT_COMPLETE`，也没有把占位音频标成正式旁白。

---

## 3. 方案对比（任务书要求的字段）

| 方案 | 本地? | 许可证 | 中文普通话质量 | 情绪 / 语速控制 | 免费额度 / 限制 | 输出格式 | 剪映集成 | 当前可用性 |
|---|---|---|---|---|---|---|---|---|
| **Windows 内置 SAPI 5（Huihui 等）** | ✅ 纯本地 | 系统组件（随 Windows） | 机械、可懂，非商业广告级 | 语速可控；**无情绪控制** | 免费、无额度；需系统语音已安装 | PCM WAV（SpFileStream），FFmpeg 可转 AAC | 理论可行（作为音轨导入），**未验证** | ❌ **本轮被安全策略阻断，0 段语音** |
| **MeloTTS**（`myshell-ai/MeloTTS`） | ✅ 本地推理 | **MIT** | 支持中文，质量优于 SAPI | 语速可控，情绪有限 | 免费；**模型文件需联网下载，体积未核实** | WAV（Python） | 可经 WAV 导入 | 需批准安装 torch 系依赖 + 模型下载 |
| **Coqui TTS / XTTS**（`coqui-ai/TTS`） | ✅ 本地推理 | **MPL-2.0**（弱 copyleft） | 多语言含中文，可克隆音色 | 较丰富 | 免费；模型大；**项目 2024-02 后停更** | WAV | 可经 WAV 导入 | 不优先（停更 + 许可约束 + 依赖重） |
| **edge-tts**（`rany2/edge-tts`） | ❌ 调用微软 Edge **在线**服务 | **LGPL-3.0 为主 + 单文件 MIT** | 中文自然度较好 | 语速 / 音量可控 | 表面免费，但**依赖第三方在线服务，服务条款与稳定性未核实** | MP3 / SRT | 可经音频导入 | **不采用**：非本地 + 合规/许可未核实 |
| **Piper / 其他开源中文 TTS** | ✅ 本地 | 未核实 | 未核实 | 未核实 | **许可证、模型体积、硬件要求均未核实** | 未核实 | 未核实 | 本轮未纳入探测，不做结论 |
| **剪映内置 TTS** | ❌ 依赖剪映 | 商业软件 | 未知 | hubcli 契约有 `setTtsVoice` / `setSpeechRate` | **可能消耗会员/云额度，未核实** | 剪映内部音轨 | 原生（但需 Host token） | ❌ 未验证；`JIANYING_AGENT_RUNTIME_TOKEN` 门槛未解 |

> 上表中"未核实"是刻意保留的，不用猜测填充；也不把"有免费额度"当成"已确认可用"。

---

## 4. 需要用户批准的安装清单（本轮**未安装**）

按任务书要求，先列明来源、许可证、大小、联网与硬件需求，等待批准：

| # | 安装包 / 依赖 | 来源 | 许可证 | 预估大小 | 需联网 | GPU | 风险 / 说明 |
|---|---|---|---|---|---|---|---|
| 1 | `pywin32`（仅用于让 Python 调用已装 SAPI） | PyPI 官方 | PSF 风格 / 需核对 | 小（数 MB 级，**未核实**） | 仅下载时 | 否 | 仍需确认安全策略是否允许 COM 调用；**不保证能解封** |
| 2 | `faster-whisper` + CTranslate2 + 中文 ASR 模型 | PyPI / Hugging Face | MIT + 各自依赖许可 | 依赖中等；**模型体积未核实** | 是 | 否（CPU 可跑） | 用于字幕时间码，可顺带为配音对齐提供参考 |
| 3 | `MeloTTS` + torch / torchaudio CPU 版 + 中文模型 | PyPI / 官方仓库 | MIT + torch 系许可 | **大（torch CPU 版 + 模型，未核实具体 GB）** | 是 | 否（CPU 可推理，速度未测） | 最可能产生真实中文 WAV 的方案；需先确认磁盘与下载来源可信 |
| 4 | `piper` 或同类轻量本地 TTS | 官方 GitHub Release | **待核实** | **待核实** | 是 | 否 | 只有核实许可证 + 来源后才考虑 |

**批准前不做的事**：不下载模型、不 `pip install`、不改系统设置、不调用在线 TTS、不使用剪映可能的付费额度。

---

## 5. 一旦获批，最小验证流程（已设计，未执行）

1. 安装最小依赖 → 生成一句中文旁白 WAV（例如「药到，帮您按时正确用药」，**不含任何疗效承诺**）；
2. `ffprobe` 确认格式与时长；
3. `volumedetect` 确认 `mean_volume` 在合理区间（建议 -20 ~ -12 dB）、`max_volume` 不削波；
4. `silencedetect` 检查无 ≥0.5 s 静音、首尾无截断；
5. 用 ASR（若已批准 faster-whisper）回听校验**语音完整性**与文字一致性；
6. 人工试听判断语速自然度、情绪、断句（程序不可靠项 → `NEEDS_MANUAL_REVIEW`）；
7. 在**独立剪映测试草稿**中导入该 WAV，验证音轨；
8. 只有 2–7 全部有证据，才把 `tts_status` 从 `NOT_COMPLETE` 改为完成。

---

## 6. 结论

- 找到了**适合 Intel 核显 / CPU 的免费候选**（SAPI、MeloTTS、faster-whisper 等），但本轮**没有在本机跑通任何中文语音合成**。
- 系统内置中文 SAPI 语音确实存在；障碍是执行环境的安全策略，不是缺少许可证或需要付费。
- 本轮产出的 WAV 是**明确标注的合成测试音**，只用于验证音频 QA 链路，绝不冒充配音。
- **没有实际中文语音 WAV，因此不标记 TTS 完成**；这是本轮 `B · CONDITIONAL PASS` 的主要阻塞之一。
