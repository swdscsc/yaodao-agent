# R1 推送校验补记（提交后生成，不改写历史报告）

> 本文件与 `push-verification.json` 在推送成功后才能生成，因此**不进入**
> `manifest.sha256.json` 的主体清单（该清单已在提交中固定）。本补记不覆盖、
> 不回填任何历史报告或历史证据。

## 提交链（均基于远端 `main` 最新 HEAD）

| 顺序 | Commit | 内容 |
|---|---|---|
| 基准 | `334ddbc60a50a794300188fa886d388a85c9edd2` | R0 预制作最终远端 HEAD（本轮开始前） |
| 1 | `9bb8ae1e9cb9b3120cecce37fa9d2afe7c1f0140` | R1 主体：六项审核修正、S14–S17 新首段、原创 SVG/HTML 与 FFmpeg 关键帧、11 份文档（本地提交，含 2 个误入的 `.pyc`） |
| 2 | `c13a6975c4d6d09f66e621679d1c60fcad4aba54` | 修正提交：移除 2 个 `.pyc`、新增 `.gitignore` 规则、加固生成器与校验脚本、补清理审计与文档说明 |
| 3 | 本补记提交 | 仅新增 `push-verification.json` 与本文件；最终 HEAD SHA 在交付回复中给出 |

- 推送结果：`334ddbc..c13a697  main -> main`，`git rev-parse HEAD` 与
  `git ls-remote origin refs/heads/main` 均为 `c13a697…`，工作区干净。
- 提交 1 未推送前即发现缓存问题，**未改写历史提交**，用独立的修正提交处理，链条完整可审计。

## 远端回读校验结果

- 方法：commit-pinned raw URL + cache buster，逐文件 SHA-256 字节级比对。
- 结果：**89 / 89 全部匹配**（`all_matched = true`，`mismatches = []`）。
- 推送树内 `.pyc` 文件数：**0**（`pyc_cleanup_confirmed_remotely = true`）。
- Git blob 与本地文件哈希一致性：抽查 `README.md`、`manifest.sha256.json`、
  `pycache-cleanup-audit.json` 三者 `git show HEAD:<file>` 均等于本地 SHA-256，
  说明 Windows CRLF→LF 归一化未造成 R0 曾出现的哈希漂移。
- `push-verification.json` 中 `per_file` 逐条记录了每个文件的 raw URL、网页 URL、
  HTTP 状态码、期望/实际字节数与期望/实际 SHA-256。

## 本轮测试结果（最终态）

| 项目 | 结果 |
|---|---|
| 六项审核修正断言 | 全部 PASS |
| 权威表 `SHOTS` 镜头数 / 主片时长 | 33 镜 / 240.0 s |
| 旁白 | 28 句，**471 字**（CJK 汉字，机器计数，单一权威值；R0 的 473 / 560 已废弃） |
| 对白 cue ID | 16 条、16 个全局唯一 ID（`Sxx-Dnn`），S04/S16 重叠统计已修正 |
| 一致性检查 | `errors = []`，`all_consistency_checks_passed = true` |
| 跨目录生成器测试 | 5 次运行（脚本目录、仓库根、交付副本、Markdown 两处）全部 exit 0、输出字节一致、定位器一致 |
| 原创动态图形关键帧 | FFmpeg 渲染 9/9 成功，中文与「模拟界面 / 非真机录屏 / 示意数据 / 预制作素材·非成片」标注齐全 |
| 首段 | `S14–S17`，96–123 s，**27 s**，机器评分 rank 1，4 镜全部通过 5 条硬门槛 |
| 历史证据 | R0 `preserved_untouched` 10 份与基准 commit blob 逐字节一致；R0 修订前原始文件 11 份留存在 `evidence/r0-originals/`（`regenerated_in_place` 11 条，另 `vertical-cut-plan.md` 原地修订） |
| 敏感扫描 | 凭据命中 0；本机绝对路径命中 1（README 中按用户要求保留的清理前绝对路径记录） |
| JSON 合法性 | 0 个非法文件 |
| 交付目录内视频/音频 | 0 个（**未导出任何 MP4**） |
| 交付目录内编译缓存 | 0 个 |

## 可访问链接（commit-pinned，避免 main 分支 CDN 缓存）

- 报告：`https://raw.githubusercontent.com/swdscsc/yaodao-agent/c13a6975c4d6d09f66e621679d1c60fcad4aba54/docs/ai-collaboration/outbox/WB-VIDEO-005-PREPRODUCTION-R1/report.md`
- 网页版：`https://github.com/swdscsc/yaodao-agent/blob/c13a6975c4d6d09f66e621679d1c60fcad4aba54/docs/ai-collaboration/outbox/WB-VIDEO-005-PREPRODUCTION-R1/report.md`
- 完整逐文件链接见 `push-verification.json` 的 `per_file[].raw_url` 与 `web_url`。

## 仍未解决的问题（全部如实保留）

1. **没有导出任何视频**：`media/WB-VIDEO-005/` 未创建，无 MP4、无视频 SHA-256、无审核版链接。
   ChatGPT 审核五级状态（已上传 / 可下载 / 已读取 / 画面已检查 / 音频已听审）**全部为 false**。
2. **中文配音缺失**：三条合法 SAPI 路径被系统安全策略拦截，未绕过；0 中文语音 WAV。
3. **合法 BGM / 音效素材缺失**：`music-sfx-plan.md` 只有来源方案，未下载、未生成音频。
4. **真实产品画面为 0**：56 个媒体文件全为测试信号 / QA 截图；首段使用原创图形与明确标注的模拟界面。
5. **字幕时间码为计划值**：需真实配音后重排。主片双轨计划时间码重叠 14 处
   （`evidence/subtitle-draft.meta.json`，R1 后每条已绑定唯一 cue ID）；
   首段 `S14–S17` 独立重算为 4 处（`evidence/first-cut-collisions.json`）。两者口径不同，均已如实记录。
6. **人工签核状态 `NEEDS_MANUAL_REVIEW`**：不得使用虚构审核人或模拟签核。
7. **未获授权**：Vidova 云端额度、剪映 GUI / Host token、TTS 安装、模型下载、付费操作全部为 0。
   最小授权清单见 `minimum-authorization.md`。

## 边界声明

本轮仍属**预制作修订**，不得声称已导出视频、已配音或已完成审核。
按用户要求，本轮完成后停止，交由 ChatGPT 独立审核。
