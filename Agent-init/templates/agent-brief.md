# Agent Brief: <task>

- **目标 / 完成标准：** <一个可验收结果>
- **角色与模型：** <现有 role；本任务显式 model + reasoning>
- **上下文：** 跨任务默认 fresh；同一有界任务内，上下文明显节省重读/重建成本时优先复用，说明待续部分。
- **授权状态：** <Spec / evidence / approved implementation / approved Ops>
- **事实源：** <相关 Plan / OpenSpec / 代码与 overlay 章节路径，不粘贴全文>
- **工作目录与允许写入：** <worktree / paths；禁止面仍遵守 overlay>
- **协作：** 你不是唯一协作者，不回退他人改动；遇到重叠写入先交回 Director 协调。
- **验证与回填：** <必要命令/验收；verification.md、tasks.md 或报告路径>
- **回传：** 结果、改动、退出码/证据、未完成项；见 worker-report.md。阶段回报不自动结束 worker；有界任务完成验收后按生命周期收口。
