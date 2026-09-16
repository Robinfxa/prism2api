# Workflow User Guide

这是一份按需查阅的使用指南，不是 agent 的常驻必读文档。

日常直接描述任务即可，Director 从 `/ms-loop` 选择最小路径：文档/配置维护走 Fast；单个行为变更走 Normal；跨 change 的阶段走 Major。无需为普通任务预先召集全部角色、研究或反复对齐。

## 初始化

```bash
# 从母版目录运行
bash skills/ms-init/init.sh <target-repo-dir> <project-name>
# 从已安装项目运行
bash .agents/skills/ms-init/init.sh <target-repo-dir> <project-name>
```

填好目标项目 overlay 的入口、测试、不变量和 Git 边界；进入 Normal / Major 前初始化 OpenSpec。安装器保留已有 AGENTS、overlay 和同名角色；更新共享 skills/docs 时会覆盖对应安装副本，先查看目标现状。不要靠删除已有文件来强制重装。

目标项目可在 `.codex/config.toml` 配置主 session 默认；安装器不创建或覆盖此配置。模型策略见 `Codex_Specialization.md`。

## 使用与恢复

- 新 session：`/ms-start` 只恢复当前任务相关事实；不通读所有文档。
- 重要架构/领域问题未定：`/grill-with-docs` 先查事实，再解决需要用户决定的选择。
- 并行：请求具体独立工作，Director 判断收益和路径冲突；同文件或依赖工作串行。
- 大阶段：一个 Major Plan 对应一个 Director session；完成后交接，下个 Plan fresh。Worker 默认一次性。完整策略及模型矩阵见 [Codex_Specialization.md](Codex_Specialization.md)。
- 长测试：后台保存可核验结果，由可用完成通知或低频监控续接；无变化不刷屏。测试完成还要验收和回填证据。
- 必须新增职责时才用 `/ms-add-role`；模型档位通过派工参数选择，不创建新角色。

## 规则在哪里

| 内容 | 唯一入口 |
|---|---|
| 开发步骤与验证选择 | `.agents/skills/ms-loop/SKILL.md` |
| 领域不变量、Git 约束、测试命令 | `PROJECT_OVERLAY.md` §3、§5、§7 |
| Session 与模型 | `Codex_Specialization.md` |
| 角色权限 | `Team_Roles.md` 与 `.codex/agents/` |
| OpenSpec / Plan / 架构 / 研究的事实归属 | `Documentation_System.md` |

验证与已批准 gate 仍必须完成；精简不等于跳过证据。只有需要用户权限或重要取舍时停下，同一授权无需反复确认。
