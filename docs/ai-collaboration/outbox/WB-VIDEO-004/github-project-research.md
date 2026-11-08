# WB-VIDEO-004 · GitHub 成熟项目真实调研报告

| 项 | 值 |
|---|---|
| 调研时间 | 2026-11-08 16:41–16:54 +0800 |
| 仓库数量 | **17 个真实仓库**，覆盖任务书 10 个方向 |
| 机器可读证据 | `evidence/github_repo_probe.json`（145 KB，逐 URL 记录 HTTP 状态 / bytes / SHA-256 / 摘录）、`evidence/github_repo_probe_addendum.json` |
| 调研方式 | 只读 HTTPS GET；**未 clone、未安装、未运行、未修改任何第三方项目** |
| 重要限制 | GitHub REST API 匿名限额已耗尽（`api.github.com` 返回 403），改用公开 HTML 页 + commits Atom feed + `raw.githubusercontent.com` 原文 |

---

## 1. 调研方法（可复算）

探测脚本位于仓库外本机 `probe/research004/probe_repos.py`，对每个仓库依次抓取：

1. `https://github.com/<repo>` HTML → 确认仓库真实存在，取 `<title>` / meta description；
2. `https://github.com/<repo>/commits/<branch>.atom` → 最近提交时间（维护状态）；
3. `raw.githubusercontent.com/.../README.md` → 运行方式 / 定位；
4. `.../LICENSE*` → **许可证原文**（不靠 README 宣传）；
5. `.../requirements.txt | pyproject.toml | setup.py | package.json` → 真实依赖；
6. 一个入口源码文件 → 真实代码头（imports / 结构）。

每个请求都记录 URL、HTTP 状态、字节数、响应体 SHA-256 与文本摘录；猜错的路径如实记录 404，不补写、不虚构。

**纠错过程（体现"不只根据 README 判断"）**：

| 初判 | 复核后 | 依据 |
|---|---|---|
| `RayVentura/ShortGPT` 抓空（main 全 404） | 默认分支是 **`master`**，README / MIT LICENSE / requirements 均 200 | addendum 逐文件状态 |
| `rany2/edge-tts` 自动识别成 MIT | **LGPL-3.0 为主 + 仅 `srt_composer.py` 为 MIT** | LICENSE 首行原文 |
| `Netflix/vmaf` 自动识别成 BSD | **`BSD-2-Clause-Patent`（BSD+Patent）** | LICENSE 首行 SPDX |
| `modelcontextprotocol/servers` 自动识别成 MIT | **MIT → Apache-2.0 过渡中的混合许可** | LICENSE 声明 |
| `anthropics/skills` 许可证 UNKNOWN | 根目录 **确实没有 LICENSE 文件**（5 个候选名全 404），HTML 页也无 license 标注 | addendum |
| `Aegisub` 自动识别成 MIT | 实际是 **BSD-3-Clause 风格** 的主许可 + 第三方组件（混合许可需逐项核对） | LICENCE 原文 |
| `kkroening/ffmpeg-python` | 最后提交 **2022-07-11**，已停更（但纯封装、稳定） | Atom feed |

---

## 2. 十个方向与项目映射

| # | 方向 | 真实项目 |
|---|---|---|
| 1 | AI 视频导演 / 分镜生成 | MoneyPrinterTurbo、ShortGPT、f/awesome-chatgpt-prompts、langchain |
| 2 | 文生视频 / 图生视频 / 镜头运动 | ComfyUI（代表需 GPU 路线） |
| 3 | AI 视频自动剪辑 | MoneyPrinterTurbo、ShortGPT、PySceneDetect |
| 4 | FFmpeg 自动化后期 | ffmpeg-python、PySceneDetect |
| 5 | 字幕自动生成与排版 | openai/whisper、faster-whisper、whisperX、Aegisub |
| 6 | TTS 配音与音频后期 | MeloTTS、coqui-ai/TTS、edge-tts |
| 7 | 视频质量检测 | Netflix/vmaf |
| 8 | 素材管理与镜头一致性 | ComfyUI（一致性工作流）、PySceneDetect（镜头切分） |
| 9 | 产品广告脚本与创意策划 | awesome-chatgpt-prompts、langchain |
| 10 | Agent Skill 与 MCP 工作流 | anthropics/skills、modelcontextprotocol/servers |

---

## 3. 逐项目真实检查结论

> "维护"取 commits Atom feed 的 `feed_updated`；"本机实测"一列全部为「未安装/未运行」，因为本轮明确不允许擅自安装大量依赖。

| 项目 | 许可证（原文核对） | 真实依赖摘录 | 最近提交 | Windows / 无独显 / 免费 | 本机实测 | 是否值得集成 |
|---|---|---|---|---|---|---|
| `harry0703/MoneyPrinterTurbo` | MIT | `moviepy==2.2.1`、`streamlit==1.66.1`、`starlette`；主依赖已迁 `pyproject.toml`/`uv.lock` | 2026-11-07（活跃） | 可跑，但**脚本→成片依赖在线 LLM/素材 API，可能产生费用** | 未运行 | **仅借鉴工作流**，不整包替换现有架构 |
| `RayVentura/ShortGPT` | MIT（master 分支） | `python-dotenv` 等，需 OpenAI/ ElevenLabs 类密钥 | Atom 未取到（main 504 / master 404） | 依赖付费 API，成熟度不足 | 未运行 | **不集成** |
| `Breakthrough/PySceneDetect` | **BSD-3-Clause** | `pyproject.toml`（OpenCV / numpy / click 系） | 2026-11-08（活跃） | ✅ 纯 CPU、Windows、免费 | 未运行 | **高价值，待批准试装**：镜头切分 / 节奏检测 |
| `kkroening/ffmpeg-python` | Apache-2.0 | `setup.py`（纯封装，依赖外部 ffmpeg 可执行文件） | 2022-07-11（停更） | ✅ 已具备同等能力（本机已有 FFmpeg 7.1 + 自建命令封装） | 未运行 | **不必新增依赖**，仅参考 API 设计 |
| `openai/whisper` | MIT | `numba / numpy / torch / tiktoken` | 2026-08-31 | CPU 可跑但慢、模型需下载 | 未运行 | 备选；优先 faster-whisper |
| `SYSTRAN/faster-whisper` | MIT | `ctranslate2>=4.0,<5`、`huggingface_hub`、`onnxruntime`、`av` | 2026-11-06（活跃） | ✅ **CTranslate2 CPU 推理，无需独显**；模型需联网下载 | 未运行 | **高价值，待批准试装**：字幕时间码 |
| `m-bain/whisperX` | **BSD-2-Clause** | `pyproject.toml`，torch 系 + 强制对齐模型 | 2026-10-22 | CPU 可跑但依赖重 | 未运行 | **中期**：词级时间戳、字幕断句 |
| `Aegisub/Aegisub` | BSD-3-Clause 主许可 + 第三方混合 | `CMakeLists.txt`（C++ 构建） | 2019-10-06（停更） | ✅ 有 Windows 原生版；但需人工 GUI | 未运行 | **仅参考 ASS 排版规范**，不自动化集成 |
| `myshell-ai/MeloTTS` | MIT | `torch / torchaudio / transformers==4.27.4 / librosa / soundfile` | 2024-12-24 | ✅ 官方称 CPU 可推理；中文支持；模型体积/下载量**未核实** | 未运行 | **候选 TTS，需批准安装**（见 `tts-research.md`） |
| `coqui-ai/TTS` | **MPL-2.0**（弱 copyleft） | `pyproject.toml`，cython / numpy / torch | 2024-02-10（停更） | 模型大、依赖重 | 未运行 | **不优先**：停更 + 许可约束 |
| `rany2/edge-tts` | **LGPL-3.0 为主 + 单文件 MIT** | `setup.py`，asyncio 网络客户端 | 2026-10-14 | ❌ **需联网调用微软 Edge 在线 TTS 服务**，非本地；服务条款/合规边界未核实 | 未运行 | **不采用**（合规与许可双重不确定） |
| `Netflix/vmaf` | **BSD-2-Clause-Patent** | `libvmaf/meson.build`（C/C++，需 meson 构建） | 2026-11-02（活跃） | CPU 可跑，但 Windows 需编译；本机 FFmpeg 未确认含 libvmaf | 未运行 | **中期质量度量**，先核实构建成本 |
| `comfyanonymous/ComfyUI` | **GPL-3.0**（强 copyleft） | `requirements.txt`，torch / CUDA 系 | 2026-11-08（活跃） | ❌ 依赖独立 NVIDIA GPU，不满足本机 Intel 核显条件 | 未运行 | **不采用**（硬件 + 许可） |
| `modelcontextprotocol/servers` | MIT → Apache-2.0 过渡混合 | `package.json` Node 系 | 2026-11-04 | ✅ 可跑；但许可状态需按文件核对 | 未运行 | **方法参考**，不直接安装 |
| `anthropics/skills` | **根目录无 LICENSE，许可未确认** | 无依赖清单；纯 Markdown + 脚本目录 | 2026-11-06（活跃） | ✅ 文档型，无运行依赖 | 只读检查 SKILL.md 结构 | **不集成代码**，仅提取工作方法（见 `skill-research.md`） |
| `f/awesome-chatgpt-prompts` | MIT | 无依赖（Prompt 集合） | 2026-11-08 | ✅ 纯文本 | 未运行 | **仅作为创意提示词参考**，不直接套用 |
| `langchain-ai/langchain` | MIT | `pyproject.toml`，大型框架 | 2026-11-06 | ✅ 可跑但依赖庞大 | 未运行 | **不引入**；现有调度器足够 |

---

## 4. 适合当前 Intel 核显 / Windows / 免费本地的清单

| 层级 | 工具 | 状态 | 说明 |
|---|---|---|---|
| 已具备 | **FFmpeg 7.1 + ffprobe**（本机已装并实测） | ✅ 真实运行 | 黑屏/静音/冻结/音量/字幕烧录/合成/转码全部验证过（WB-VIDEO-002/003/004） |
| 已具备 | Python + cv2 5.0.0 + numpy 2.5.4 + PIL 13.0.0 | ✅ 真实运行 | 帧差、文字掩膜、对比度、字幕带检测均已在本轮测试跑通 |
| 低风险、待批准 | `PySceneDetect`（BSD-3-Clause，纯 CPU） | 静态检查通过 | 镜头切分、节奏检查，可与 manifest 对接 |
| 低风险、待批准 | `faster-whisper`（MIT，CTranslate2 CPU） | 静态检查通过 | 中文 ASR + 字幕时间码；**模型需联网下载，体积未核实** |
| 中风险、待批准 | `MeloTTS`（MIT，torch CPU） | 静态检查通过 | 中文 TTS；依赖体积大、模型需下载 |
| 中风险、待批准 | `whisperX`（BSD-2-Clause） | 静态检查通过 | 词级对齐；依赖最重 |
| 明确不适合 | ComfyUI / 各类文生视频大模型 | 静态检查 | 需 NVIDIA 独显 |
| 明确不适合 | edge-tts | 静态检查 | 需联网调用在线服务 + LGPL 混合许可 |
| 明确不适合 | MoneyPrinterTurbo / ShortGPT 整包 | 静态检查 | 依赖付费 LLM/素材 API，会替换现有可审计架构 |

---

## 5. 关键判断（不含宣传口径）

1. **没有发现"开箱即用的 AI 产品广告导演"完整项目**。MoneyPrinterTurbo / ShortGPT 是"脚本→素材→拼接"的短视频流水线，不含广告创意评估、产品真实性校验、质量否决权、逐项人工签核——这些正是本项目自建 `ad-director-workflow.md` 的原因。
2. **许可证必须读原文**。自动扫描把 edge-tts 判成 MIT、vmaf 判成 BSD、Aegisub 判成 MIT 都会出错；本轮已按 LICENSE 原文逐条纠正。若将来真的集成，需按**文件级**再核一次（尤其 MCP servers 的过渡期与 Aegisub 的第三方组件）。
3. **`anthropics/skills` 虽活跃但没有许可证文件**，因此不复制其代码/脚本进仓库；只提取"技能文件夹 + 渐进加载 + 脚本与指令分离"的**工作方法**，转成项目内部规范。
4. **本机没有安装或运行任何上述项目**。所有"可在 Windows 运行"是基于依赖、许可证、构建方式与文档的判断，不是实测结论；安装必须走批准清单。
5. **未发现官方的 Vidova ↔ 剪映桥接项目**，仍需在 `vidova-jianying-next-steps.md` 里按本机真实接口处理。

---

## 6. 证据索引

- `evidence/github_repo_probe.json` — 17 仓库 ×（HTML / Atom / README / LICENSE / 依赖 / 入口源码）逐 URL 状态与 SHA-256。
- `evidence/github_repo_probe_addendum.json` — 分支纠错、许可证原文首行、`anthropics/skills` 的 `SKILL.md` 真实结构摘录。
- 复算方式：按 JSON 中的 `url` 重新 GET，比对 `http_status` 与 `sha256`（正文为公开仓库内容）。
