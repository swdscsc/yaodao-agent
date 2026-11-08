# WB-VIDEO-004 · Skill 学习机制研究

| 项 | 值 |
|---|---|
| 目标 | 找到**真正能提高商业产品广告制作质量**的可复用 Skill / 工作方法 |
| 实际动作 | 只读检查 3 类候选的仓库结构、许可证、依赖与 `SKILL.md` 原文 |
| **本轮安装数量** | **0** —— 没有安装任何 Skill，没有运行任何不明脚本 |
| 证据 | `evidence/github_repo_probe.json`、`evidence/github_repo_probe_addendum.json` |
| 结论 | 不直接采用任何外部 Skill 代码；**提取工作方法，转成项目内部规则/提示词/模板**（见 `ad-director-workflow.md` 附录） |

---

## 1. 先定义"Skill"是什么

`anthropics/skills` 的 README 原文（raw 摘录，200 OK）定义：Skill 是**文件夹**，内含 instructions、scripts 和 resources，由 Agent 在需要时动态加载，用来提升专门任务的表现。其 `skills/pdf/SKILL.md`（8,058 B）与 `skills/docx/SKILL.md`（6,897 B）都以 YAML frontmatter 开头，正文是分步骤的作业指令和脚本调用约定。

这个机制对本项目的价值不在"多装几个技能"，而在于：**把广告导演的专业判断写成可版本化、可审核、可复用的指令文件**，而不是散落在对话里。

---

## 2. 候选逐项评估（任务书要求的 12 个字段）

### A. `anthropics/skills`

| 字段 | 值 |
|---|---|
| 名称 | Anthropic Skills（Claude 官方示例技能集） |
| GitHub | `https://github.com/anthropics/skills` |
| 作者 / 来源 | Anthropic 官方；`main` 分支 |
| 许可证 | **根目录无 LICENSE**（`LICENSE`/`LICENSE.md`/`LICENSE.txt`/`LICENCE`/`COPYING` 全部 404；HTML 页无 license 标注）→ **许可未确认，不可复制其文件** |
| 适用场景 | 文档类专门任务（pdf / docx / xlsx 等）的作业规范示范 |
| 依赖 | 无统一依赖清单；各 skill 自带脚本（Python/Node） |
| 是否联网 | 文档本身不需要；个别脚本可能需要下载依赖 |
| 是否需要 GPU | 否 |
| 是否收费 | 仓库本身免费；运行 Claude 技能需相应平台 |
| 是否适合当前 Windows 环境 | 文档层面适合；脚本层面未验证 |
| 实际测试结果 | **只读静态检查**：README 200（5,547 B）、`skills/pdf/SKILL.md` 200（8,058 B）、`skills/docx/SKILL.md` 200（6,897 B）、入口脚本 `skills/pdf/scripts/check_bounding_boxes.py` 200；确认 YAML frontmatter + 分步骤指令结构。**未安装、未执行任何脚本** |
| 是否值得集成 | **不集成代码/脚本**（许可未确认）；**只提取工作方法** |

### B. `modelcontextprotocol/servers`

| 字段 | 值 |
|---|---|
| 名称 | Model Context Protocol reference servers |
| GitHub | `https://github.com/modelcontextprotocol/servers` |
| 作者 / 来源 | MCP 项目官方（Linux Foundation 旗下生态） |
| 许可证 | **MIT → Apache-2.0 过渡中的混合许可**（LICENSE 原文声明，需按文件核对） |
| 适用场景 | 工具调用协议、能力边界、只读/读写 server 分离 |
| 依赖 | Node（`package.json` v0.6.2） |
| 是否联网 | 依 server 而定 |
| 是否需要 GPU | 否 |
| 是否收费 | 免费开源 |
| 是否适合当前 Windows 环境 | 是（Node 已装 v22.22.2），但许可过渡期需复核 |
| 实际测试结果 | 只读检查 README / LICENSE / `package.json` / `src/filesystem/index.ts` 均 200；确认 `--read-only` 参数与允许目录白名单设计。**未安装、未运行** |
| 是否值得集成 | **方法参考**：把"只读能力 / 写能力 / 允许路径白名单"的分层照搬到本项目工具层；不安装 server |

### C. WorkBuddy 平台内置 Skill 机制（本机已具备）

| 字段 | 值 |
|---|---|
| 名称 | WorkBuddy Skills（`~/.workbuddy/skills/` 与插件内置 skills） |
| GitHub | 不适用（平台内置） |
| 作者 / 来源 | WorkBuddy 内置 / 用户级安装 |
| 许可证 | 平台内使用，不涉及引入第三方代码 |
| 适用场景 | 文档、表格、PPT、浏览器、办公文件编辑等 |
| 依赖 | 平台提供 |
| 是否联网 | 部分能力需要 |
| 是否需要 GPU | 否 |
| 是否收费 | 平台额度内，无额外付费（符合用户既定偏好） |
| 是否适合当前 Windows 环境 | ✅ 本机已可用 |
| 实际测试结果 | 本轮未安装新 Skill；平台现有能力已支撑本报告的调研与文档产出 |
| 是否值得集成 | 作为**运行载体**；本项目的"广告导演"应写成仓库内 Markdown 规范 + Python 模块，而非外部依赖 |

### D. 明确排除

| 候选 | 排除理由 |
|---|---|
| 批量安装 "AI 视频/广告" 类社区 Skill | 无许可证审查、脚本来源不明、与用户"不安装来源不明程序""不装几十个无关 Skill"冲突 |
| MoneyPrinterTurbo / ShortGPT 当 Skill 用 | 依赖付费 LLM/素材 API，且会替换现有可审计架构 |
| ComfyUI 工作流 | 需 NVIDIA 独显，本机为 Intel 核显 |
| `edge-tts` 类在线服务封装 | 需联网调用第三方在线服务 + LGPL 混合许可，合规未核实 |

---

## 3. 提取出的工作方法 → 项目内部规则

从 A/B 的**结构**（不复制代码）提炼 6 条，已写入 `ad-director-workflow.md` 与 `recommended-architecture.md`：

| # | 提取的方法 | 项目内部落地 |
|---|---|---|
| 1 | 一个 Skill = 一个文件夹，含 `SKILL.md` 指令 + 可选脚本 + 资源 | 六个导演角色各自一份独立规范文件，互不混写；`ad-director-workflow.md` 定义目录与职责 |
| 2 | YAML frontmatter 声明 name / description / 适用条件 | 每个角色规范头部带 `role / inputs / outputs / veto_power / requires_approval` 元数据 |
| 3 | 渐进披露：只在需要时加载对应指令 | 调度器按阶段只加载当前角色的规则，不把全部提示词塞进一次调用 |
| 4 | 脚本与指令分离，脚本可单独验证 | 判断写 Markdown，执行写 Python（`subtitle_checks.py` / `qa.py` / `run_signoff_tests.py`），测试可独立运行 |
| 5 | 明确能力边界与只读/写白名单 | 参考 MCP filesystem server 的 `--read-only` 与允许目录：本项目的工具层分 `READ_ONLY` / `LOCAL_REVERSIBLE` / `NEEDS_APPROVAL` 三级 |
| 6 | 输出必须可验证、可追溯 | 每阶段产出 evidence JSON + SHA-256 清单；`NEEDS_MANUAL_REVIEW` 与 `FIXED` 严格分离（本轮 P0 修复的核心） |

---

## 4. 转化成的项目内部可复用资产（全部在仓库内，无外部依赖）

| 资产 | 位置 | 用途 |
|---|---|---|
| 六角色职责与交接契约 | `ad-director-workflow.md` §2 | 产品研究员 / 创意导演 / 分镜导演 / 视觉导演 / 自动剪辑师 / 质量总监 |
| 22 字段分镜 schema + 提示词模板 | `ad-director-workflow.md` §3–§4 | 每个镜头可机器校验，杜绝"只写画面描述" |
| 产品真实性红线模板 | `ad-director-workflow.md` §2.1 | 区分已实现 / 开发中 / 概念演示，禁止编造医疗效果与用户数据 |
| 广告剪辑规范 | `product-ad-editing-guide.md` | 开场 / 产品展示 / 节奏 / 包装 / 横竖屏 |
| 质量否决权规则 | `ad-director-workflow.md` §2.6 + `recommended-architecture.md` | 质量总监可一票否决，人工逐项签核不可被自动 PASS 顶替 |
| 工具能力分级 | `recommended-architecture.md` §4 | 接口存在 / 可调用 / 调用成功 / 生成有效素材，四级不得混用 |

---

## 5. 诚实边界

- 本 Skill 研究是**只读文档与结构检查**，没有在本机运行任何第三方 Skill 脚本，因此不宣称"某 Skill 在本机可用 / 效果好"。
- `anthropics/skills` 许可未确认：如后续要引用其具体文本或脚本，必须先取得明确授权或确认许可证，再走安全审查。
- "零安装"是刻意的：任务书要求"不要为了数量安装几十个无关 Skill""未经安全检查不要直接运行不明脚本"。
- 本项目最需要的能力（广告创意判断、产品真实性、逐项人工签核、质量否决）在现有开源项目里**没有现成实现**，所以采用"提取方法 + 自建规范"而不是"装一个 Skill 就宣称具备能力"。
