# 提交与远端校验补记（Addendum）

> 本文件是**提交后追加的补记**，不改写、不覆盖 `report.md` 或任何历史报告。
> 目的：给出真实 commit SHA、远端 HEAD 复核、raw 链接校验结果，以及 `report.md` §8 中一处措辞的澄清。

| 项 | 值 |
|---|---|
| 任务 | WB-VIDEO-005-PREPRODUCTION |
| 拉取基准（任务书 HEAD） | `c753f0714e75bf7328b9263f957304a0ac69fcd3` |
| 主体交付 commit | `ea0f5f87fe463fbe3c698bc1f2d543eafa8c4895` |
| 行尾归一化 commit | `7064f423f471ef6531a8dedbcd161c0289c993af` |
| 本补记 commit | **自引用不可能**，其 SHA 在本轮会话汇报中给出 |
| 校验时刻的远端 HEAD | `7064f423f471ef6531a8dedbcd161c0289c993af`（`git ls-remote origin refs/heads/main` 与本地 HEAD 一致） |
| 最终远端 HEAD | 第三个提交推送后在本轮会话汇报中给出 |
| 推送方式 | `git -c credential.helper= -c credential.helper=wincred` + `GIT_TERMINAL_PROMPT=0` + 本地代理；系统受保护凭据存储；**未读取/打印/提交任何明文 PAT**；无 force-push |

---

## 1. 远端文件完整性校验

`evidence/push-verification.json` 记录了逐个文件从 GitHub 重新下载后的结果：

| 指标 | 值 |
|---|---|
| 主体交付文件数（manifest 覆盖） | **16** |
| raw HTTP 200 且 SHA-256 与本地一致 | **16 / 16** |
| `all_remote_files_verified` | `true` |
| 本地交付校验 | 7 个 JSON 合法、2 个 CSV 列数一致、2 个 SRT 格式合法、manifest 16 条重算全部匹配、18 个文本文件敏感扫描 **0 命中**、0 errors |

**两次如实记录的过程问题（都已定位并解决，未掩盖）：**

1. **CSV 行尾不一致**：首次远端回读时 2 个 CSV 因本机 Git 把 CRLF 归一化为 LF，导致本地字节与 raw 字节不同（内容相同）。已把生成脚本改为 `lineterminator="\n"`，重新生成 CSV；提交 `7064f42` 后本地与远端逐字节一致。
2. **raw CDN 缓存**：分支相对 `raw.githubusercontent.com/.../main/...` 存在路径级 CDN 缓存，短时间内返回了旧 blob（表现为 2 个 JSON 哈希不匹配、1 个偶发 HTTP 000）。改用**按 commit SHA 固定的 immutable raw URL** 校验后 16/16 全部匹配。`push-verification.json` 里同时保留了给用户使用的 `main` 分支 raw 链接和实际校验用的 `verification_url_commit_pinned`。

> 结论：远端文件完整、可下载、SHA-256 可复核；但不意味着 ChatGPT 已实际读取或播放任何内容——本轮**没有视频文件**。

---

## 2. 校验类文件的 SHA-256

这三个文件被有意排除在 manifest 之外，避免清单自引用循环；各自哈希在此列出：

| 文件 | 字节 | SHA-256 |
|---|---|---|
| `evidence/manifest.sha256.json` | 3550 | `54c086da76cecd6f232d162e3f071fe00bbfa3652596dee1406ba767591e7b95` |
| `evidence/delivery-verification.json` | 538 | `fd5cab0d60a2ba0061879bd13a88c42ba1484537451453e146ea200cefed7cc5` |
| `evidence/push-verification.json` | 14944 | `fafc77557da888242690aea3cc6b73537f450a049f1fa1cf000b19f86b676a36` |
| `evidence/push-verification-addendum.md`（本文件） | — | **自引用不可能**，SHA-256 在本轮会话汇报中给出 |

manifest 覆盖的 16 个主体交付文件 SHA-256 见 `evidence/manifest.sha256.json`。

---

## 3. `report.md` §8 措辞澄清

`report.md` §8 原句「其自身 SHA-256 记录在该文件的 `self_hash` 字段」不够准确：
**任何文件都不可能包含自己的 SHA-256**。`push-verification.json` 的 `self_hash` 字段实际值为
`SELF_REFERENCE_IMPOSSIBLE__SHA256_LISTED_IN_ADDENDUM_AND_SESSION_REPLY`，
真实哈希见本 addendum §2 与会话汇报。

按项目惯例「不回填、不改写历史报告」，此处以补记方式更正，不修改 `report.md` 正文。

---

## 4. 10 份必需交付的 GitHub 链接

raw 前缀：`https://raw.githubusercontent.com/swdscsc/yaodao-agent/main/docs/ai-collaboration/outbox/WB-VIDEO-005-PREPRODUCTION/`
网页链接：把 raw 前缀替换为 `https://github.com/swdscsc/yaodao-agent/blob/main/docs/ai-collaboration/outbox/WB-VIDEO-005-PREPRODUCTION/`
（完整 URL 列表亦可由 `push-verification.json` 的 `files[].raw_url` / `files[].web_url` 直接取得。）

| # | 文件 | raw 链接 |
|---|---|---|
| 1 | `report.md` | https://raw.githubusercontent.com/swdscsc/yaodao-agent/main/docs/ai-collaboration/outbox/WB-VIDEO-005-PREPRODUCTION/report.md |
| 2 | `asset-inventory.csv` | https://raw.githubusercontent.com/swdscsc/yaodao-agent/main/docs/ai-collaboration/outbox/WB-VIDEO-005-PREPRODUCTION/asset-inventory.csv |
| 3 | `product-claims-register.md` | https://raw.githubusercontent.com/swdscsc/yaodao-agent/main/docs/ai-collaboration/outbox/WB-VIDEO-005-PREPRODUCTION/product-claims-register.md |
| 4 | `main-film-script.md` | https://raw.githubusercontent.com/swdscsc/yaodao-agent/main/docs/ai-collaboration/outbox/WB-VIDEO-005-PREPRODUCTION/main-film-script.md |
| 5 | `main-film-shotlist.csv` | https://raw.githubusercontent.com/swdscsc/yaodao-agent/main/docs/ai-collaboration/outbox/WB-VIDEO-005-PREPRODUCTION/main-film-shotlist.csv |
| 6 | `narration-draft.md` | https://raw.githubusercontent.com/swdscsc/yaodao-agent/main/docs/ai-collaboration/outbox/WB-VIDEO-005-PREPRODUCTION/narration-draft.md |
| 7 | `subtitle-draft.srt` | https://raw.githubusercontent.com/swdscsc/yaodao-agent/main/docs/ai-collaboration/outbox/WB-VIDEO-005-PREPRODUCTION/subtitle-draft.srt |
| 8 | `vertical-cut-plan.md` | https://raw.githubusercontent.com/swdscsc/yaodao-agent/main/docs/ai-collaboration/outbox/WB-VIDEO-005-PREPRODUCTION/vertical-cut-plan.md |
| 9 | `first-cut-readiness.md` | https://raw.githubusercontent.com/swdscsc/yaodao-agent/main/docs/ai-collaboration/outbox/WB-VIDEO-005-PREPRODUCTION/first-cut-readiness.md |
| 10 | `evidence/manifest.sha256.json` | https://raw.githubusercontent.com/swdscsc/yaodao-agent/main/docs/ai-collaboration/outbox/WB-VIDEO-005-PREPRODUCTION/evidence/manifest.sha256.json |

附加交付：`creative-research.md`，以及 `evidence/` 下的
`asset-probe.json`、`capability-probe.json`、`consistency-check.json`、
`subtitle-draft.meta.json`、`dialogue-subtitle-draft.srt`、`narration-table.md`、
`delivery-verification.json`、`push-verification.json`、`push-verification-addendum.md`。

---

## 5. 视频交付状态（必须逐项区分）

| 状态 | 当前值 |
|---|---|
| 文件已上传 | ❌ 无 MP4 |
| 文件可下载 | ❌ |
| 文件已被实际读取 | ❌ |
| 视频画面已被检查 | ❌ |
| 音频已被实际听审 | ❌ |
| 原始 MP4 / 低码率审核版 / 视频 SHA-256 | **不存在** |
| `media/WB-VIDEO-005/` 目录 | **未创建**（避免空目录被误读为已交付） |

本轮按 `WB-VIDEO-005-preproduction.md` §0/§3 授权，**只做只读核查、脚本、分镜、剪辑准备**。
「脚本完成」不等于「视频已剪好」。

---

## 6. 红线复核（补记阶段同样为 0）

0 付费 / 0 额度消耗 / 0 `generate_asset` / 0 依赖安装 / 0 模型下载 / 0 联网 TTS 或生图 /
0 剪映 GUI / 0 UIA / 0 草稿变更 / 0 明文凭据读取 / 0 用户工程或素材修改 / 0 公开发布 /
0 视频导出与上传。

---

## 7. 停止条件

按任务书 §3：完成后提交并核对远端 HEAD、贴出链接与 SHA-256，**然后停止等待 ChatGPT 审核，不得自行扩大到 WB-VIDEO-005 正式 E2E**。

等待：① ChatGPT 对脚本、分镜、主张台账、字幕与素材盘点的复核；
② 用户对 `first-cut-readiness.md` §4 的 **U1（提供中文旁白 WAV）** 与 **U6（授权阶段 2 导出与上传）** 的明确批准；
③ 新的阶段 2 任务书。
