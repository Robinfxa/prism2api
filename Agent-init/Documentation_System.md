# 文档系统与 Source of Truth（multi-subflow 内核）

> 本文件定义项目开发中哪些文档负责记录什么事实。目标是：保留留痕，但不让同一事实散落在多个长期文档里互相打架。
> 领域路径、测试命令、设计圣经路径、研究目录等项目专属值仍由 `Agent-init/PROJECT_OVERLAY.md` 填。

---

## 1. Source of truth 分层

| 文档面 | 负责什么 | 不负责什么 | 更新时机 |
|---|---|---|---|
| **OpenSpec change** `openspec/changes/<slug>/` | 当前变更的事实：proposal、design、tasks、delta specs、verification 摘要 | 长期架构愿景、跨阶段路线图 | 每个 change 创建、实现、验证、archive 前 |
| **OpenSpec specs** `openspec/specs/**` | 当前系统行为合同 | 过程记录、讨论历史、临时计划 | `openspec archive <slug> -y` 合并后 |
| **设计圣经** overlay §2 | 长期架构意图、核心不变式、模块关系、设计原则 | 单次任务流水账、测试日志、证据全文 | 大阶段结束后；架构语义变化时 |
| **ADR** `docs/adr/` | 少数难逆转、会被未来重新争论、或违反直觉的决策 | 普通实现选择、短期排期、显而易见事实 | 决策定稿时，按需懒创建 |
| **CONTEXT** `CONTEXT.md` / `CONTEXT-MAP.md` | 领域词汇和边界语言 | 需求、架构、实现、计划 | grill-with-docs 中术语被澄清时 |
| **Director Plan** `docs/plans/active/<slug>.md` | 一个大阶段的执行指南：目标、范围、拆分策略、风险、验收线 | 行为合同、代码事实、验证正文 | `/ms-loop` 前，重大阶段才创建 |
| **Research Dossier** `docs/research/<slug>/` | 外部证据成册：同行、行业共识、论文、博客、借鉴矩阵 | 采纳决策、OpenSpec 任务、架构圣经正文 | explore/brainstorm/grill 后仍缺外部证据时 |
| **Validation report** | 验证原始证据附件：命令、日志、audit 结果 | source of truth；不单独定义项目事实 | 验证发生时；摘要回填 OpenSpec change |
| **Agent Brief / Worker Report** | 单次派工输入与回执：目标、边界、证据、下一步 | 长期事实、行为合同、架构意图 | 每次派工/完工；必要摘要回填 OpenSpec / plan |
| **MEMORY** `MEMORY.md` + `memory/**` | 索引、教训、指向事实正文的链接 | 事实正文、架构正文、完整计划 | 阶段结束或发现可复用教训时 |

规则：同一事实只放在一个长期 source of truth；其他文档只链接或摘要。Validation report 不是 source of truth，它是证据附件；最终结论必须回填到 OpenSpec change 的 `verification.md` 或 `tasks.md` 对应项。

并行命名可用唯一 slug 或可选 sid 后缀避免冲突；已有文档不因 session 更换而重命名。Session 生命周期见 `Codex_Specialization.md` §1。

## 2. 立项前文档对齐

重要架构或领域决策未定时使用 `/grill-with-docs`；目标、边界和验收已清楚时直接执行。影响实现的讨论结论在实现前写入下面已有 source of truth，不强制访谈或另建文档。

durable alignment record 不是新的长期文档类型；它是对齐结论写入现有 source of truth 的要求：

| 对齐结论 | 写入位置 |
|---|---|
| 术语、边界语言 | CONTEXT / CONTEXT-MAP |
| 难逆转或反直觉 trade-off | ADR |
| Major lane 范围、路线、风险、验收线 | Director Plan |
| Normal lane 行为与任务边界 | OpenSpec proposal / design / tasks |
| 外部证据缺口 | Research Dossier |

执行顺序与启用哪些工具由 `/ms-loop` 按任务决定；不要为对齐记录额外创建访谈、Research Dossier 或 Director Plan。

Researcher 不写 Director Plan，不写 OpenSpec，也不改设计圣经。Researcher 的工作是把证据和可借鉴选项整理成册；采纳与排序由 Director 做。

## 3. Research Dossier 格式

默认目录：

```text
docs/research/<slug>/
  README.md              # 研究问题、结论、推荐优先级
  sources.md             # 论文/博客/项目/标准的可追溯来源
  comparison-matrix.md   # 同行/行业/我们现状的矩阵
  notes/                 # 可选：摘录、代码路径、实验记录
```

必须包含：

- 研究问题与决策需要。
- 已有设计圣经 § / 代码现状对照，避免把已实现内容误报成缺口。
- 证据强度、适配条件、工程量、风险、ROI。
- 三态借鉴矩阵：已 borrow / 精简版漏算法 / 未 borrow。
- 建议是否值得进入 Director Plan 或 OpenSpec change。

小规模研究可在已有 change 或 Plan 中记录带来源的结论；需要多来源比较时才建立完整 dossier，不填无用空表。

## 4. Director Plan 格式

默认路径：

```text
docs/plans/active/<slug>.md
docs/plans/archive/<YYYY-MM-DD>-<slug>.md
```

Director Plan 是 Major lane 的大阶段指南，不是 OpenSpec 的替代品。Fast / Normal lane 默认不写。建议结构：

```markdown
# <Stage / Plan Name>

**Goal:** <阶段目标>

**Inputs:**
- grill-with-docs: <链接或摘要>
- research dossier: <路径，若有>
- design bible sections: <overlay §2 的 § 链接>

**Decisions:**
- <已定决策>

**Open Questions:**
- <仍未定但不阻塞 / 必须先定>

**Loop Breakdown:**
- <预计拆成哪些 OpenSpec changes 或 behavior slices>

**Validation Line:**
- <tier-1 / tier-2 / audit / byte-identical 预期>

**Exit / Archive Rule:**
- <完成后哪些文档需要更新，哪些只留链接>
```

必须写 Director Plan 的情况：

- 一个目标会拆成多个 OpenSpec changes。
- 会改变架构意图、模块边界、数据契约或长期不变式。
- 跨模块协调无法由单个 change 清楚表达。
- 有不可逆/难回滚决策，或很可能需要 ADR。

可以不写 Director Plan 的情况：单点 bugfix、纯文档微调、低风险局部重构、一次 OpenSpec change 可完整表达的工作。

模板在 `Agent-init/templates/director-plan.md`。

## 5. 阶段结束归档

每个大阶段结束时按此顺序收口；这些文档变更必须发生在最终 commit/push 前：

1. OpenSpec change 完成并 archive。
2. `openspec/specs/**` 成为当前行为合同。
3. 如架构意图变化，更新设计圣经；只写长期意图，不复制任务日志。
4. 如有难逆转/会被未来争论的决策，新增或更新 ADR。
5. 如术语变化，更新 CONTEXT。
6. Director Plan 从 `docs/plans/active/<slug>.md` 移到 `docs/plans/archive/<YYYY-MM-DD>-<slug>.md`。
7. MEMORY 只追加索引/教训/链接，不存事实正文。
8. Ops 将 OpenSpec archive 结果 + 文档收口一起 commit/push。

完成后按 `Codex_Specialization.md` §1 结束本 Plan 的 Director session，留下 Git/worktree、archive/Plan 路径、有效证据和未完成项的短交接。下一阶段须有用户授权；已有持续推进授权不重复询问，在 fresh session 恢复。

## 6. Codex 工作计划目录

本仓库里的 `docs/superpowers/plans/` 是 Codex 执行本 workflow 仓库维护任务时使用的计划记录，不是目标项目里的 Director Plan。迁移到业务项目时，业务开发阶段计划使用 `docs/plans/active|archive/`。
