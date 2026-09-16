# M08 验证体系与 Codex/GPT 工作流接入

> v0.1.0 · draft。**生产行为、上游真实能力和开发流程分别验证。** 本次只有文档验证，不存在已通过的运行时 suite。

## 1. 采用的工作流版本

主基线是用户本次上传的 `dev-flow-GPT.zip`，SHA-256 与精确读过的文件见 [W1](../../research/prior-art-prb/sources.md#w1)。它定义 Director＋arc-imp／Validation／Ops／Researcher，入口为 `/ms-start` 与 `/ms-loop`，采用 `AGENTS.md`、`Agent-init/`、`.agents/skills/`、`.codex/agents/*.toml`。

此前单独上传的 Claude 版用 `.claude/`、文件锁审批及 code-reader 母体；**本书不把它们写成 GPT 包已具备的机制**。源文档对 Codex 产品能力的说明仍是该包的陈述，不因本书引用就变成本会话已验证的工具能力。

本会话没有可用的项目子代理运行环境，没有调用这些角色或伪造 IPC。成书者是单一执行者；独立 Validation gate 仍未执行。

## 2. 文档与变更事实分层

| 载体 | 在本项目的落点 | 用途 |
|---|---|---|
| 设计圣经 | `docs/architecture/` | 长期意图、模块和不变量；当前全部 draft |
| 领域语汇 | `docs/CONTEXT.md` | 词义、边界、同名消歧，不放开发流水账 |
| Research Dossier | `docs/research/prior-art-prb/` | 外部证据、已读范围、可信度和建议 |
| Director Plan | `docs/plans/active/architecture-and-protocol-readiness-prb.md` | 成书与后续待批切片 |
| OpenSpec change | 未来 `openspec/changes/<slug>-<sid>/` | proposal/design/tasks/delta/verification；本次未创建 |
| capability spec | 未来 `openspec/specs/` | 只经归档合并；本次没有当前行为合同 |
| Validation report | `docs/validation/` | 证据附件，不独自定义交付行为 |
| MEMORY | 未来 `MEMORY.md` | 只留索引和教训，按需创建 |

遵循上传文档的 Source of Truth 分层；本书不另造第二套“总状态数据库”来管开发。[W1](../../research/prior-art-prb/sources.md#w1)

## 3. 三档路线的项目落地

本次属于 **Major 架构成书与立项前对齐**：有阶段计划、来源和设计，尚无生产实现。不是把涉及模块与数据合同的变化偷塞进 Fast，也不为尚未获批的实现伪造 live specs。

后续 Fast 用于不改变语义的文案／索引／文档校验；Normal 用于一个行为切片及其 OpenSpec change；Major 用于跨合同或多切片阶段。每次仅启用必要角色，不默认拉全队。

Spec 阶段：arc-imp 回传 artifacts，Director 审阅后发 implementation brief。不是等待文件锁唤醒；不使用旧 Claude `APPROVED` 信号来解锁 GPT 的 code 阶段。

上传 GPT 包不保证长期上下文继承，也没有长期读码母体。少量 worker 复用可作为未来运行环境支持下的调度优化，但不能代替完整 brief、现状核对或权限重发；本次不修改工作流核心来兑现这种优化。

## 4. 三种验证面，不能叫同一个 tier

| 验证面 | 目的 | 能证明什么／不能证明什么 |
|---|---|---|
| **工作流 tier-1 / tier-2** | 按靶区与全量范围区分执行责任 | tier-1 由 worker，tier-2 由 Director；不是 LLM 智能评测层 |
| **产品确定性验证** | schema、状态、隔离、stream、重启、权限 | 用断言、回放与故障注入；不能证明未测试账号今日可用 |
| **真实上游与客户端验收** | 实际登录／提交／完成／客户端行为 | 必须授权与现场证据；不被 mock-only 测试替代 |

ValueHermes 的双层评测把确定性合同与非确定性模型输出区分开；本项目继承这个区分，但**不建立 LLM 裁判平台**。gateway 的文本传输完整性必须用确定性检查；回答质量只作为可选体验观察，不冒充协议正确性的证据。[V3](../../research/prior-art-prb/sources.md#v3)

## 5. 按行为切片验证

每个未来 `tasks.md` 条目至少写：外部可观察行为、场景、测试 seam、命令、是否要 RED、预期 GREEN、证据落点、ponytail rung。先一条 tracer bullet 跑通，再扩场景，不先横向建一堆空框架。

mock 只放在真实系统边界，例如远端传输、时钟、随机、磁盘失败注入。不要 mock 掉 RunSupervisor、Journal 状态迁移和事件汇编器，再宣称主路径可靠。

最小 exemplar 建议选**提交 intent 已持久化后进程崩溃、重启不得再次 submit**。它覆盖硬边界且可独立验证；不先用最简单 happy path 建一个无法表达失败的模板。

### 5.1 候选测试布局（尚未实现）

```text
tests/
  unit/          # 纯 schema、状态转换、增量解析
  contract/      # 公共 SDK/API → 真 core → 边界 fake transport
  recovery/      # 子进程崩溃、文件/DB 窗口、幂等与资源锁
  replay/        # 脱敏的上游语义事件样本
  live/          # 显式授权、独立账号配置；缺省不运行
  fixtures/     # 版本化、去秘密样本
```

### 5.2 候选验证命令（仅在对应 harness 落地后使用）

```bash
python -m pytest -q tests/unit tests/contract tests/recovery tests/replay
python -m pytest -q -m live tests/live
```

当前这些路径与 pytest harness 尚不存在，不能把命令写成“已通过”。实现阶段默认 suite 必须有真实断网 guard，并在测试中确认 guard 正在生效；CI 不装载个人凭证。live 命令还需显式许可配置，不能仅靠目录名防误触。

## 6. passed-count 与 byte-identical 的差异登记

上传包把 passed-count 不变作为某些 gated-off / 重构的守护 gate。**本书保留这一来源事实，但新增项目要求：计数相同只能证明测试数量层面的卫生，不能证明输出逐字节相同。** 真正 byte-identical 需明确的 golden bytes／digest 差分或行为 characterization。

这是对项目验收的补强设计，不宣称上传工作流已经做了这些检查；差异登记见 [A5](../appendices/a5-decisions-and-source-differences.md)。

## 7. 实测记录与发布能力

一次 live 证据至少包含被授权 profile 的匿名引用、客户端／adapter／parser 版本、能力范围、输入类别、上下文归属、关键事件、完成判据、时长与错误。无权分享的正文不能为了证明测试而上传。

指标阈值不预填“99%”“30 秒”或“无限量”；采样后由用户／Director 确认目标。真实成功数、失败数、样本窗口、跳过与盲区同时报告。

发布描述必须区别 `design-complete`、`offline-verified`、`live-verified`、`client-qualified`；这些是文档状态说明，不引入另一套运行状态机。能力上架仍由 M02 的 snapshot 决定。

## 8. 安装与 git 边界

本包只填 `Agent-init/PROJECT_OVERLAY.md`，不偷偷安装 hooks、全局角色或 workflow 内核。后续使用上传包的 `skills/ms-init/init.sh` 时，须从独立内核目录执行；该脚本会重写目标 `.agents/skills/ms-*` 和部分内核文档，应先审 diff，不能对已存在工作流无脑覆盖。[W1](../../research/prior-art-prb/sources.md#w1)

OpenSpec 初始化、具体 CLI 版本和命令验证在首次实现准备切片完成。不能直接写 `openspec/specs/**` 冒充归档产物，不能将其他仓库的 specs 当本项目当前行为。

未来文档入库建议独立 `docs/architecture-v0.1` 分支，显式路径暂存，不 force push，不自动 merge main。当前连接器写入失败，未创建分支／PR／commit；不是已 push 待 merge。

## 9. 验收与未决

`T48` 离线 guard 真正禁止联网与个人凭证；`T49` 公共路径 RED→GREEN；`T50` passed-count 不冒充 byte-identical；`T51` live／skip／mock 证据不混淆；`T52` 指定客户端真实请求与流截断识别。

未决 `U12–U15` 见 [A2](../appendices/a2-evidence-and-open-questions.md)。文档完整性本次已单独验证，不能用于把这些未来测试 ID 标为 passed。
