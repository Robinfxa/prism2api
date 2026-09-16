# Codex 派工与 Session 约定

本文件是项目 session 生命周期和任务模型矩阵的唯一规则源。工具可用性以当前运行环境为准；以下是项目策略，不是产品强制行为。

## 1. Session 生命周期

- **Director：一个完整 Major Plan → 一个 session。** 同一未完成 Plan 可跨回合、压缩或必要恢复继续；完成后先归档 Plan、回填 OpenSpec / docs、核实 Git 与剩余事项，再结束该 Director session。
- **下一个 Plan 使用 fresh Director session**，从 Git、OpenSpec、Director Plan 和相关文档恢复。若已获用户持续推进授权，交接后继续推进，无需重复请求授权；新建用户可见任务仍遵守用户授权与当前工具边界。
- **Worker 跨任务边界默认 fresh；同一有界任务内，如果已有上下文明显能节省重新读取和重建成本，则优先复用。** 角色可复用；以目标和验收边界划分任务，不把一次回报或 Spec→Code 阶段切换自动视为新任务。实现前的 Director review 仍必须通过。
- 同一任务续做时按需核验 durable state 的变化，保留有用上下文；无需为了 fresh 重建已掌握的事实。跨任务不因缓存命中或派工方便而默认复用。
- report 必须把结果和未完成事项交回 durable state；不能让正确性依赖 prompt-cache、fork history 或长期 agent context。
- 有关闭能力时，有界任务完成并验收后关闭 worker；没有关闭接口时，确认无运行任务、记录已完成并停止复用，不把 interrupt、idle 或 final 回答谎称物理关闭。Director 同理：留下交接并结束本轮；只有工具支持且已授权时关闭/归档用户可见任务。

## 2. 模型与 reasoning（按任务选择）

| 任务 | 默认模型 | Reasoning / 升级条件 |
|---|---|---|
| Director / 主 session | `gpt-6-astra` | `medium` |
| 文档、Plan、Spec、Research synthesis | `gpt-6-astra` | `medium` |
| Code implementation | `gpt-6-astra` | `medium` |
| Test execution / log triage | `gpt-5.6-luna` | `max` |
| 普通 Ops | `gpt-5.6-luna` | `medium` |
| 复杂 validation | `gpt-6-astra` | `medium` |

按用户最新成本判断，除明确适合 Luna 的执行任务外默认 Astra medium；Luna 仅使用 max / medium。Sol 不进入常规分档或自动升级链。用户点名或有具体任务对比依据时仍可临时选择，不固化到角色。

`.codex/agents/*.toml` 只定义角色职责与边界，不固定 `model` 或 `model_reasoning_effort`。Director 在 spawn 时显式传入本任务的模型和 effort；未配置时可能继承父任务，不等于执行了本矩阵。一个任务混合多个阶段时按主要工作选择，或按已有自然交付边界拆分；不为档位额外拆 agent。

项目 `.codex/config.toml` 设置主 session 默认；显式启动参数或会话选择可能覆盖默认。文件修改不代表正在运行的 session 或已加载角色已切换。若当前接口不能选择所需模型，报告限制，不伪称实际使用了目标模型；按需使用已有通用 worker 携带同一角色 brief，不新增角色。

## 3. 最小上下文与并行

- brief 给目标/完成标准、事实源路径与相关章节、读写边界、验证和回传位置；模板见 `templates/agent-brief.md`。不要复制整本架构或先让每个 worker 通读 Agent-init。
- 只显式派有独立收益的工作；同文件、契约重叠或依赖任务串行，并行写入优先独立 worktree。可并行不等于必须并行。
- 用户可见新任务、内部 subagent、后台进程分别按可用工具管理；不要把创建进程或设置监控当作完成任务。
- Hooks 策略与信任状态只在 overlay §12 维护；文档归属见 `Documentation_System.md`，无需在每个 skill 重述。

## 4. 长测试后台收口

- 用户指定监督节奏：新 Director 派工后约 10 分钟确认实际启动，随后每小时监督一次；首次确认后将同一监控切为每小时，完成后停止。执行方内部的必要测试等待不等于新增外层监督。

- 长测试保存命令、工作目录、代码/输入标识、PID、开始时间、日志路径；wrapper 在退出时独立写最终退出码与摘要。区分运行中、失败、通过待验收和已收口，不依赖模型轮询落盘。
- 优先使用当前环境已验证的完成通知/等待接口。需要跨回合跟进且有用户授权时使用同任务 heartbeat，按预计耗时选择低频检查；不在回合内反复轮询、不重读整份历史。
- 无变化保持安静，只在有意义的进展、完成、失败、超时风险或需用户行动时通知。没有实测退出回调时，不承诺自动即时唤醒。
- 任务列表缺项只表示状态未知，不证明未开工。用创建回执中的正式 ID、对应工作区的 Git/归档证据或只读运行元数据交叉核验；已知状态源持续无效时停止该轮询并换事实源，不能反复把查不到解释为初始化。
- 完成后继续已授权的验收和证据回填，收口后移除或暂停对应监控；不能只报测试通过便等用户催促。

依据（核验于 2026-09-12）：[Astra 提示与技能化简](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra)、[Subagents：继承与显式选择](https://developers.openai.com/codex/agent-configuration/subagents)、[项目配置与优先级](https://developers.openai.com/codex/config-file/config-basic)。模型矩阵与 session 生命周期是用户指定的项目策略。
