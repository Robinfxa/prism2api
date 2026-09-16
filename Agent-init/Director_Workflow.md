# Director 工作流

## 1. 执行入口

开发路由与 Fast / Normal / Major 流程只在 `.agents/skills/ms-loop/SKILL.md` 定义。目标、边界和验收已清楚时直接执行；事实缺口先查代码/文档，只有重要未决选择才进入 `/grill-with-docs`。

Director 决定范围、派工和验收；角色权限见 `Team_Roles.md`。新 Major Plan 和 worker 的生命周期、模型选择见 `Codex_Specialization.md`，不依赖旧对话保管事实。

## 2. 硬约束

- 项目不变量、只读面和 Git / destructive-operation 边界见 `PROJECT_OVERLAY.md` §5、§7，动手前读取。
- commit / push / archive / merge 由 Director 批准、Ops 执行；merge 到 main 须用户明确指令。Code worker 不做 tree-global git（stash/checkout/reset）。
- 禁止 `git add -A` / `git add -p` / `--no-verify` / force push / `git reset --hard` / `git checkout --`；只暂存明确路径，不暂存 ambient。
- 禁止直接编辑 `openspec/specs/**`；已验证 delta 通过 OpenSpec archive 合并。
- 临时日志、进程状态和审计附件放 gitignored scratch；长期事实按 `Documentation_System.md` 分层回填。

## 3. 验证与验收

- 按变更影响选择有意义的证据，具体套件与 offline 要求见 overlay §3；改签名或返回结构时查全 caller。
- Director 负责测试范围、单次调度和最终验收；可派 fresh worker 执行。全量套件串行，已有覆盖当前代码和相关输入的通过证据可复用。只因代码、环境、输入变化或未解风险才扩大/重跑。
- 公共接口和真实通道证据优先；mock 不应绕开被测路径。通过数量只用于完整性核对，不能证明 byte-identical。
- 检查真实命令退出码、测试摘要和目标结果，不能仅凭 compound exit、日志中的 passed 或 Ops 口头完成判绿。

## 4. Spec 与文档

Normal / Major 需要 OpenSpec；Fast 不强制安装、创建或归档 change。Artifact 与代码验收在 `/ms-loop`；文档归属和阶段归档在 `Documentation_System.md`。只更新发生变化的长期事实。

## 5. 状态恢复

恢复入口见 `/ms-start`。当前进度从 Git、对应 OpenSpec change 和 Director Plan 核实；MEMORY 只作索引。不要把旧 overlay 快照、测试分母或 worker 上下文当 current truth。
