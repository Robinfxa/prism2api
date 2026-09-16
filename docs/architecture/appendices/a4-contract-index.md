# A4 合同所有权、章节路由与修改影响

> v0.1.0 · draft。这里只做索引，不复制字段正文；任何合同字段变动先改 owner 模块，再同步消费者。

## 1. 八个模块

| 编号 | 章节 | 回答的主要问题 |
|---|---|---|
| M01 | [入口与兼容 API](../modules/01-api-and-client-contract.md) | 用户能传什么、拿到什么，哪里明确不兼容 |
| M02 | [适配与能力](../modules/02-prism-adapter-and-capabilities.md) | 上游事实怎么证明、协议与模型能力怎么映射 |
| M03 | [生命周期与幂等](../modules/03-run-lifecycle-and-idempotency.md) | 谁能提交、什么时候不能重发、怎么恢复 |
| M04 | [上下文与归属](../modules/04-context-and-resource-ownership.md) | 读取哪些材料、复用什么、清理能碰哪里 |
| M05 | [流式与结果](../modules/05-streaming-and-result-normalization.md) | 什么是正文、什么是完整、如何表达失败 |
| M06 | [状态与证据](../modules/06-journal-evidence-and-storage.md) | 存什么、谁写、崩溃和保留期如何处理 |
| M07 | [认证与部署](../modules/07-auth-security-and-deployment.md) | 凭证、浏览器、网络和单实例的边界 |
| M08 | [验证与工作流](../modules/08-evaluation-and-workflow.md) | 什么证据才算通过、下一轮开发怎么进入 |

## 2. 字段／行为所有者

| 合同 | 唯一正文 | 直接消费者 | 修改必查 |
|---|---|---|---|
| GenerationRequest | M01 §3 | M03/M02 | 参数拒绝、fingerprint、客户端样本 |
| 原生 API／兼容子集 | M01 §2/§4 | SDK/CLI/目标客户端 | schema、错误、模型表与 live 资格 |
| CapabilitySnapshot | M02 §2 | M01/M03/M07 | 依赖能力、过期／隔离与 activation |
| RemoteHandle | M02 §4 | M03/M04/M06 | 精确查询、取消、秘密信息过滤 |
| RunRecord／SubmitAttempt | M03 §2–§4 | M06/API 查询 | 恢复、状态 CAS、重复提交、终态 |
| ResourceOperation | M03 §3–§4 | M04/M06 | 远端创建副作用和不确定性 |
| ContextBinding／ResourceLease | M04 §3/§5 | M02/M03/M07 | 页签身份、revision、winner preservation |
| NormalizedEvent | M05 §2 | M03/M06/交付层 | 顺序、重写、结果完整性与旧 epoch |
| GenerationResult | M05 §6 | M01/M06 | usage、finish_reason、文本／artifact 分类 |
| DeliveryRecord | M05 §1 | M03/M06/M01 | 多次交付、掉线、快照时点与终态不混淆 |
| EvidenceManifest | M06 §5 | 诊断／查询／评测 | unknown、来源、脱敏、散列和保留 |
| AuthProfile／TransportSession | M07 §2–§3 | M02/M04 | 授权、失效、专用 profile 与 origin |
| Test evidence / stage gates | M08 / A3 | Director/Validation/Ops | offline-live 分离、真实命令与 skip |

## 3. 禁止的跨层捷径

API handler 不能直接点浏览器发送；browser callback 不能直接把 runs 写成 succeeded；SDK 不能在超时后自行另建 adapter 重发；lookup 不能隐式 submit；cleanup 不能按 URL 模糊匹配关闭所有标签页；模型输出不能修改 capability 或 auth 配置。

发现需要捷径时，先检查是否缺少 owner 合同，而不是“先实现，后补文档”。这里不是禁止合理扩展；扩展必须有明确写权与测试。

## 4. 版本与兼容规则

本地 schema_version、adapter/parser revision、capability evidence revision、config_revision 与客户端 compatibility profile 分开。修改任何影响 fingerprint 或结果映射的字段必须说明旧 run 如何读取、旧幂等 key 如何判重、何时需要迁移。

迁移不把 uncertain 自动改为 cancelled，不补填没有来源的模型／usage 字段，不因新解析器上线就重发历史请求。破坏性变化必须有具体 change、数据备份与回滚／拒绝旧格式方案。
