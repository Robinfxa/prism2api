# prism2api 架构成书与协议就绪阶段计划

**Session 标签：** `prb`（文档标签，非已注册的远端 runtime session）。

**状态：** 架构书已形成完整初稿，待用户评审；P0 及后续实施未启动。

**Goal：** 依据上传工作流与参考项目，建立可供后续开发使用的职责、合同、证据和阶段边界，不把未经验证的网页协议硬编码进系统设计。

**Trigger：** 这是新项目跨模块架构与多行为切片阶段，非普通文案修补；按 Major 的立项前对齐组织。此次尚未进入 production-code artifact gate。

## Inputs

[总书](../../architecture/00-master-design-book.md)、[来源](../../research/prior-art-prb/sources.md)、[借鉴矩阵](../../architecture/appendices/a1-borrow-matrix.md)、[未知项](../../architecture/appendices/a2-evidence-and-open-questions.md)、[Overlay](../../../Agent-init/PROJECT_OVERLAY.md)。

已有 OpenSpec：没有初始化／没有 active change／没有 capability spec 的已知证据；不得编造当前行为。

## 已确定的任务边界

用户授权创建架构书；交付采用 Markdown 总书＋8 模块＋5 附录，并附来源、阶段路线、项目 Overlay 和文档验证。仅把设计写完整，不调用真实账号、不实施 transport、不部署服务、不自动合并 main。

技术选择见 [D01–D14](../../architecture/appendices/a5-decisions-and-source-differences.md)，均是 proposed 而非用户逐项裁决。

## 当前交付与阻塞

| 项目 | 状态 |
|---|---|
| 读取上传 GPT 工作流关键文件 | 已完成 |
| 对照 ValueHermes 与已读同行资料 | 已完成；阅读范围已登记 |
| 架构总书、模块细稿、附录 | 已编写 |
| 文档结构与交叉引用检查 | 结果以[验证报告](../../validation/architecture-book-prb-report.md)为准 |
| GitHub commit／PR | 未完成：实际写入返回 403 |
| 独立 reviewer 审核 | 未执行 |
| 实现与 live 探测 | 未执行，等待新阶段批准 |

## Loop Breakdown：待批准的实施切片

下列 slug 只是候选基名，未创建 change。正式开工按本机真实 sid 后缀，不能把 `prb` 当现成锁登记。

| 顺序 | 候选切片 | 产物与退出线 | 依赖 |
|---|---|---|---|
| S0 | `prepare-project-workflow` | 审查并安装 GPT 内核、填实际工具版本、OpenSpec 初始化与离线验证 harness | 用户批准实现准备；不读个人凭证 |
| S1 | `probe-prism-protocol` | 经授权低风险交互、脱敏 fixtures、U01/U03/U06/U09/U12 更新，选一种 transport | 权限／条款与独立实验范围明确 |
| S2 | `add-native-run-core` | RunSupervisor＋Journal＋单 owner；提交 intent 崩溃 exemplar RED→GREEN | S0/S1 的核心协议语义稳定 |
| S3 | `add-context-bound-client` | 真实 adapter 单次文本闭环、explicit／isolated 证据，unknown 恢复 | S2；U05/U07/U10 |
| S4 | `add-local-api-subset` | 原生 API 与有限 chat 接口、鉴权与严格参数拒绝 | S3；仅合格子集开放 |
| S5 | `add-streaming-and-recovery` | 真实增量、rewrite、cancel、丢流、重启、漂移的故障覆盖 | S4；U08/U09 |
| S6 | `qualify-target-client` | 指定客户端版本和请求 corpus 实测；更新 compatibility profile | 所需能力验证齐全 |

S0 与 S1 的纯资料工作可按实际边界调整先后；**共享核心合同 S2→S3→S4 必须串行**。不得为并行而提前编造上游协议或拆出两个相互不兼容的核心。

P0 失败时可留下可用的研究结论并停止实现，或回到设计调整；不把研究成本变成继续堆代码的理由。

## Route / Gates

采用上传 GPT 的 review→implementation brief 路线。需要外部证据才派 Researcher；触及核心不变量或证据不足才派 Validation；独立 file-disjoint 任务才并行。没有母体长期继承或 Claude 文件锁。当前会话没有实际启动这些 worker。

每个实现 change 的 tasks 必须指定行为、seam、验证命令、RED 要求与 evidence target；全量基线由 Director 运行，Ops 在验证与归档后只暂存明确文件。

## Validation Line

本次：文档链路、结构、来源与状态声明、敏感模式、打包验证。后续：按 [A3 的 T01–T52](../../architecture/appendices/a3-delivery-and-acceptance.md) 转为真实测试；没有执行的测试标 planned/skip，不标 passed。外部协议、客户端和权限均需真实证据。

## Minimal Implementation Line

ponytail 预期：先 skip 不必要框架，复用标准库／已选依赖，最后 minimum custom。省掉管理 UI、账号池、多 provider、三库、通用事件总线和 LLM 裁判；不省 Journal、隔离、权限与完整性。

## Exit / Archive Rule

文档评审通过后，只把已接受的长期决策更新到 owner 章节；如批准进入实施，创建真实 OpenSpec change，不直接编辑 live specs。阶段完成后再按工作流归档本 plan。**此计划不会自动启动 S0/S1，也没有承诺后台推进。**

远端写权限不足时本地包可以作为交付物，但不得记录为已 push、已创建 PR 或已合并。
