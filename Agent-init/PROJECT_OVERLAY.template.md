# 项目 Overlay — <NAME>

只填项目事实与差异；通用流程见 `/ms-loop`，模型与 session 策略见 `Codex_Specialization.md`。
保留章节编号供规则引用；不适用的节写「不适用」，不要留下未填占位符。
参考：`examples/valuehermes/PROJECT_OVERLAY.md`（结构示例，路径需在目标项目核实）。

## 0. 项目身份
- 项目：<NAME>；目标：<一句话>。
- 运行时与真实入口：<语言、环境、启动命令；尚无入口则明确写明>。

## 1. 代码与知识入口
只列本项目的重要边界，不复制全树文件清单。

| 领域 / 边界 | 路径 | 关键入口 / 约束 |
|---|---|---|
| <领域> | <path> | <symbol / contract> |

## 2. 架构与领域文档
- 长期架构：<路径与相关章节索引>。
- 领域语言 / ADR：<已有 CONTEXT / CONTEXT-MAP / ADR 路径；未建立则说明>。
- 复用与历史资料：<相关考古 / 底座入口；无则不适用>。
- 特殊验收约定：<范例、用户 gate 或其他项目要求；无则不适用>。

## 3. 验证
- 靶区验证：<命令与选择范围>。
- 集成 / 全量验证：<命令、触发条件；Director 调度验收，可派 worker 执行>。
- 环境与数据边界：<离线、临时数据库、fixture、禁止访问的数据源>。
- 证据：<对应 change / Plan 的位置；命令、退出码、摘要、代码与输入标识>。
- 使用 driver 时先 export 项目变量：`DL_PY`、`DL_TEST_CMD`、`TIER2_PATH`、`DL_AMBIENT_RE`；变量说明见 `skills/ms-loop/driver.sh`（安装后位于 `.agents/skills/`）。
- `.multi-subflow/driver.env` 不会被 driver 自动加载；如用此文件，先审查，再由调用方显式加载并导出。非默认 runner 还需配置摘要与计数正则。
- 通过数量只核对套件完整性；行为不变使用 characterization，要求 byte-identical 时比较实际输出字节。

## 4. OpenSpec
- Normal / Major 使用 OpenSpec；Fast 不强制初始化或创建 change。
- 状态与入口：<是否初始化、项目所用 schema / 合同路径>。
- 不直接编辑 live specs；通过已验证 delta 的 archive 更新。
- 改用其他规格体系需修改工作流与 driver gate，不能仅在 overlay 关闭验证。

## 5. 项目不变量
- <必须保持的领域不变量及其守门证据>。
- <只读目录、受保护数据、禁止操作>。
- <哪些数值 / 行为必须由配置或已批准决策提供>。

## 6. 文件所有权
- 实现：<本次 brief 可授权的代码、测试、change 路径>。
- 研究：<研究目录>；验证：<证据附件位置>。
- Director：<阶段 Plan 路径>；Ops：<Git / 部署等职责的项目边界>。
- 架构文档写入须在 brief 中明确；同文件或共享契约的写入串行。

## 7. Git 与部署边界
- 追踪面 / ambient：<可提交与绝不暂存的路径>。
- 分支与提交约定：<分支策略、trailer 等项目差异>。
- merge 到主线：<用户授权要求>；部署：<入口和授权边界，或不适用>。

## 8. 外部研究
- <资料入口、来源要求、借鉴矩阵；没有则不适用>。

## 9. 产品原则
- <影响实际决策的原则；没有则不适用>。

## 10. 模型策略差异
遵循 `Codex_Specialization.md` §2；这里只记录明确的项目覆盖，没有则写「无」。

## 11. 当前状态入口
- `git status --short --branch`、`git log --oneline -8`。
- `openspec list`（已初始化时）、<active / archive Plan 路径>。
- MEMORY 若存在只放索引；不在 overlay 固化当前 SHA、测试分母或在制阶段。

## 12. 本地工具与 Hooks
- <已核实可用的工具、配置路径及适用范围>。
- <hook 实际启用与信任状态；未启用则明确写明>。
- Hooks 只做确定性检查，不替代规格、review 或验证事实。
