# 团队角色与权限

角色契约在 `.codex/agents/*.toml`；角色可复用，实例生命周期与模型选择统一见 `Codex_Specialization.md`。不为模型档位新增角色，也不要求每个任务凑齐团队。

| 角色 | 负责 | 边界 |
|---|---|---|
| Director | 范围、Plan、采纳决策、派工、证据验收 | 用户 gate 不能代批；Git 约束见 overlay §7 |
| arc-imp | 一个已授权切片的 Spec 或 code/tests | 实现前需 artifacts review；不自批、不 git、不直接改 live spec |
| Validation | 测试执行、日志分析、证据审计 | 不改生产代码/tests/spec；全量仅按 Director 指定范围单独执行 |
| Ops | Director 批准的 archive、commit、push、branch/PR、工作树卫生 | 不写生产代码/spec，不自行决定 merge；遵守 overlay §7 |
| Researcher | 外部证据与建议 | 不写生产代码、OpenSpec、Director Plan 或架构采纳结论 |

职责界定用于防止越权，不意味着每个步骤都必须启动 worker。Fast 可由 Director inline 完成；复杂度路由只在 `/ms-loop` 定义。

派工使用短 brief（`templates/agent-brief.md`），明确本次目标、事实源章节、允许写入、验证和返回要求。告知写入 worker 存在其他协作者，不得回退他人改动。报告（`templates/worker-report.md`）回填对应 OpenSpec / Plan；仅有协调需要时才创建额外进度文件。

文件所有权以 `PROJECT_OVERLAY.md` §6 和本次 brief 为准。同文件、共享契约或有依赖的任务串行。Researcher 只在确有外部证据缺口时使用；独立 audit 只在不变量、不可逆风险、薄弱证据或用户要求时增加。
