# 远端推送与可访问性校验（WB-VIDEO-006）

> 本文件由 `project/verify_remote.py` 通过公网 curl 实际下载生成，
> 不是本地路径声明，也不是推测链接。

## 提交

- 成片交付提交（commit1）：`b22b24cd5fed5e510f9e385a90ed737014e6bec1`
- `git push origin main` 结果：`39672f2..b22b24c  main -> main`（成功）
- `git ls-remote origin refs/heads/main`：`本次查询失败（代理 CONNECT 502）：fatal: unable to access 'https://github.com/swdscsc/yaodao-agent.git/': CONNECT tunnel failed, response 502 `
  （push 命令自身返回成功，且下列 commit-pinned raw 文件均实际 HTTP 200 回读成功。）
- 本校验文件所在提交为**最终提交**（commit2），其 SHA 由交接消息给出；
  下方所有链接固定到 commit1，指向内容不变的同一批 blob。

## 公网可访问链接（commit-pinned，无需登录）

| 文件 | 链接 |
|---|---|
| 主片 MP4 | https://raw.githubusercontent.com/swdscsc/yaodao-agent/b22b24cd5fed5e510f9e385a90ed737014e6bec1/docs/ai-collaboration/outbox/WB-VIDEO-006-FINAL-PRODUCTION/final_main.mp4 |
| 竖屏 MP4 | https://raw.githubusercontent.com/swdscsc/yaodao-agent/b22b24cd5fed5e510f9e385a90ed737014e6bec1/docs/ai-collaboration/outbox/WB-VIDEO-006-FINAL-PRODUCTION/final_vertical.mp4 |
| 主片字幕 | https://raw.githubusercontent.com/swdscsc/yaodao-agent/b22b24cd5fed5e510f9e385a90ed737014e6bec1/docs/ai-collaboration/outbox/WB-VIDEO-006-FINAL-PRODUCTION/final_main.srt |
| 竖屏字幕 | https://raw.githubusercontent.com/swdscsc/yaodao-agent/b22b24cd5fed5e510f9e385a90ed737014e6bec1/docs/ai-collaboration/outbox/WB-VIDEO-006-FINAL-PRODUCTION/final_vertical.srt |
| 质检报告 | https://raw.githubusercontent.com/swdscsc/yaodao-agent/b22b24cd5fed5e510f9e385a90ed737014e6bec1/docs/ai-collaboration/outbox/WB-VIDEO-006-FINAL-PRODUCTION/quality_report.md |
| 完整哈希清单 | https://raw.githubusercontent.com/swdscsc/yaodao-agent/b22b24cd5fed5e510f9e385a90ed737014e6bec1/docs/ai-collaboration/outbox/WB-VIDEO-006-FINAL-PRODUCTION/sha256.txt |

备用（main 分支，可能有 CDN 缓存）：`https://raw.githubusercontent.com/swdscsc/yaodao-agent/main/docs/ai-collaboration/outbox/WB-VIDEO-006-FINAL-PRODUCTION/final_main.mp4`、
`https://raw.githubusercontent.com/swdscsc/yaodao-agent/main/docs/ai-collaboration/outbox/WB-VIDEO-006-FINAL-PRODUCTION/final_vertical.mp4`。

## 公网回读结果

| 文件 | HTTP | 远端字节 | 本地字节 | 远端 SHA-256 == 本地 |
|---|---|---|---|---|
| `final_main.mp4` | 200 | 10537954 | 10537954 | **是** |
| `final_vertical.mp4` | 200 | 2056331 | 2056331 | **是** |
| `final_main.srt` | 200 | 3719 | 3719 | **是** |
| `final_vertical.srt` | 200 | 1037 | 1037 | **是** |
| `ffprobe.json` | 200 | 6713 | 6713 | **是** |

全部校验通过：**是**。

## 文件大小与 LFS 决策

- 交付目录总大小约 93.45 MB，最大单文件 `voiceover.wav` = 52,752,044 B
  （50.31 MiB）。GitHub 在推送时给出「超过推荐 50 MB」的**警告**，
  但仍在普通 Git 100 MB 单文件硬限制内，push 成功。
- 仓库**未启用** Git LFS（无 `.gitattributes`）；未使用 GitHub Release；
  未购买任何额度、未产生费用。选择普通 `git push` 是因为成片 MP4 仅
  10.54 MB / 2.06 MB，可直接通过 public raw 链接读取。

## 校验方法

对每个文件执行 `curl -sS -L --proxy <本机代理> -o <临时文件> <commit-pinned raw URL>`，
记录 HTTP 状态与下载字节数，再计算下载文件的 SHA-256 与本地交付文件比对。
临时下载文件保存在本机工作区，未提交到仓库。

## 未完成 / 需人工复核

- 本文件所在的最终提交 SHA 无法写进本文件自身（自引用），请在交接消息或
  `git ls-remote origin refs/heads/main` 核对。
- 未在 GUI 播放器中人工实时观看全片；机器完整解码与抽帧目视见 `quality_report.md`。
- 无人工具名审核签核，无 ChatGPT 审核结论。
