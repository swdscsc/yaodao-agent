# collaboration/ — WorkBuddy × ChatGPT 共享交接工作区

> 仓库：https://github.com/swdscsc/yaodao-agent（公开仓库）
> 建立日期：2026-11-09 · 本目录只用于视频项目交接，不影响根目录的药到设备工程代码。

## 一、分工

| 角色 | 职责 |
|---|---|
| **WorkBuddy**（执行方） | 视频制作、素材处理、代码修改、质量检查；每阶段上传真实交付物 + 执行报告 + 问题清单到本目录 |
| **ChatGPT**（独立审核方） | 独立审核交付物、分析问题、给出下一阶段具体执行指令；**是审核方，不是自动批准方** |
| **用户**（交接人） | 把 ChatGPT 的审核意见与指令带回给 WorkBuddy |

## 二、目录结构

```text
collaboration/
├── README.md               本文件：规则与索引
├── CURRENT_STATUS.md       当前状态快照（每阶段更新）
├── TASK_BOARD.md           任务看板（任务编号 × 版本 × 状态）
├── chatgpt_reviews/        ChatGPT 审核意见归档（用户代为提交）
├── workbuddy_reports/      WorkBuddy 执行报告归档
└── deliverables/           各任务真实交付物（含 MP4 成片）
```

## 三、交接规则（双方共同遵守）

1. 每次更新必须记录：任务编号和版本号、当前完成情况、实际修改的文件、新增交付物、
   测试与验收结果、尚未解决的问题、需要 ChatGPT 审核的具体内容、下一步建议。
2. **不得把计划中的工作写成已经完成。** 自检 ≠ 验收。
3. 不得擅自忽略审核意见；不得擅自删除原始素材；不得覆盖已验收版本。
4. 所有迭代保留版本记录（git 历史即是版本记录），确保可回退。
5. 公开仓库内不存放隐私信息：无身份证号、密码、token、人脸、家庭住址/电话。

## 四、入口

- 当前状态：[CURRENT_STATUS.md](CURRENT_STATUS.md)
- 任务看板：[TASK_BOARD.md](TASK_BOARD.md)
- 最新成片：[deliverables/WB-VIDEO-007/final_mg_sample.mp4](deliverables/WB-VIDEO-007/final_mg_sample.mp4)
- 最新执行报告：[workbuddy_reports/WB-VIDEO-007-v1-EXECUTION-REPORT.md](workbuddy_reports/WB-VIDEO-007-v1-EXECUTION-REPORT.md)
- 审核意见提交方式：[chatgpt_reviews/README.md](chatgpt_reviews/README.md)
