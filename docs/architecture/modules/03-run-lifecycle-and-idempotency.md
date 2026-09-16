# M03 RunSupervisor、提交边界与幂等恢复

> v0.1.0 · draft。**本章是请求状态与生成写权的唯一语义源。** 适配器不会自行重发，API handler 不决定任务终态，数据库只执行本章定义的合法状态迁移。

## 1. 定位与核心取舍

RunSupervisor 负责准入后的整个生命周期：持久化入队、取得上下文、跨越提交边界、消费事件、结果提交、取消和恢复。

首版一个账号、一个生成 worker、单进程排他运行目录。限制并发是降低正确性复杂度的设计选择，不代表 Prism 上游只支持并发一。**队列可有多个待执行请求，但未知的在途任务会阻止受影响账号继续生成。**

## 2. 状态机

```text
queued → preparing → submitting → running → succeeded
   │          │            │          ├──→ failed
   │          │            │          ├──→ cancelled
   │          │            └──────────┴──→ uncertain
   └──────────┴──→ failed / cancelled

uncertain ──精确只读核对──→ running / succeeded / failed / cancelled
```

图中的主线之外：preparing 中的远端资源操作结果不明也进入 uncertain；submitting 收到明确的拒绝／失败或取消证据，可以直接进入相应终态，无须伪造 running 过渡。

`uncertain` 不是“稍后重试”，也不是可重新分配的空闲资源。终态为 succeeded / failed / cancelled；unknown 只作为证据值，不能用另一个同义运行状态替代 uncertain。

| 状态 | 进入证据 | 允许的下一步 |
|---|---|---|
| `queued` | 输入与准入配置已持久化、没有远端副作用 | 排队、取消；恢复可重新调度本地队列项 |
| `preparing` | worker 已持有 lease，准备上下文 | 已记账的准备操作；未越提交边界才能安全失败 |
| `submitting` | SubmitAttempt 已持久化，**下一步可能发送请求** | 一次 submit；之后所有不明确结果都按 uncertain |
| `running` | 上游已接受的证据或明确生成事件 | observe、精确 cancel、只读 lookup |
| `succeeded` | 权威完成、文本完整、结果与 manifest 已提交 | 只读交付／查询，不重新执行 |
| `failed` | 本地确认未提交的失败，或上游确认的失败 | 只读；新任务由调用方显式决定 |
| `cancelled` | 提交前已阻止生成，或上游精确取消确认 | 只读；不得从断开连接推导该状态 |
| `uncertain` | 不能判断提交／运行／结束，或关键证据链丢失 | 冻结相关写入，查询已有任务或等待人工核对 |

### 2.1 三种状态不能混用

运行状态回答“远端工作发生了什么”；`cancel_intent` 回答“调用方是否要求停止”；`delivery_state` 回答“本次 HTTP/SDK 消费是否完整收到”。一次 run 可以 succeeded，但某次交付 truncated。不能为了给 HTTP 返回错误而把远端成功改成 failed。

`cancel_intent` 与交付状态正交，不继续扩展成几十个复合运行状态。**同一 run 可以被多次查询或交付，每次有自己的 delivery_id**；不能用 RunRecord 上一个可覆盖字段表示所有消费结果。DeliveryRecord 的详细语义归 M05，运行记录只关联它们。

## 3. `RunRecord` 和 `SubmitAttempt`

| 记录 | 必需内容 |
|---|---|
| `RunRecord` | run_id、principal_id、auth_profile_ref、state、state_version、input_ref、request_fingerprint、context_ref、capability_snapshot_ref、config_revision、created_at、updated_at、cancel_intent、terminal_evidence_ref、result_ref |
| `SubmitAttempt` | attempt_id、run_id、owner_epoch、intent_committed_at、dispatch_outcome、remote_handle、receipt_evidence_ref |
| `ResourceOperation` | operation_id、run_id、动作种类、目标归属、发出前 intent、已确认 handle、结果／不确定标记 |

一次逻辑 run 首版最多一次生成 SubmitAttempt。浏览器重连、只读查询和取消请求是不同操作，不能为了“重试”增加第二次生成 attempt。

`state_version` 用于 compare-and-swap 防止并发覆盖；`owner_epoch` 用于拒绝过期 callback。它们只约束本地所有者，不被宣传为远端 fencing 或 exactly-once。

## 4. 提交事务边界

### 4.1 必须先记录，再尝试网络写入

1. 在本地短事务中创建 `RunRecord(queued)`，关联输入引用及配置快照。
2. 单 worker 领取任务，检查取消意图与能力，持有上下文所有权，进入 preparing。
3. 若创建上下文会发远端写操作，先写 ResourceOperation intent；收到回执再记归属。准备操作不确定时停止，不能连续创建更多工作区掩盖问题。
4. 在短事务中保存 SubmitAttempt 并将 run 置 submitting，提交事务。
5. **事务结束后**调用 adapter.submit，最多一次。网络等待期间不持有 SQLite 事务锁。
6. 收到远端回执即持久化 handle，再转 running；没有 handle 但有生成开始证据也要记录证据及恢复限制。
7. 消费结果；只有 M05 判完整、M06 提交结果成功，才能原子转 succeeded。

这会产生一个保守窗口：本地 intent 已写、进程在真正发包前崩溃，恢复仍判 uncertain。**宁可增加人工核对，不使用“应该没发出去”猜测来重发。**

### 4.2 准备操作也有副作用

项目创建、会话创建、文件上传不是无害的本地预处理。只有明确无远端副作用的校验和纯本地准备可安全自动重试。不能因生成尚未开始，就无限重试创建远端资源。

## 5. 幂等键合同

建议接受可选 `Idempotency-Key`，真实可靠重试的调用方应提供并在一次用户意图内保持稳定。

唯一索引为 `(principal_id, idempotency_key_digest)`，在一个事务中判重：

| 请求 | 行为 |
|---|---|
| 同 key、同 fingerprint、queued/running | 返回同 run_id；不再入队或提交 |
| 同 key、同 fingerprint、succeeded | 返回既有结果；结果被清除则明确不可用，不再生成 |
| 同 key、同 fingerprint、failed/cancelled/uncertain | 返回原状态；不得以“重试相同 API”绕过 |
| 同 key、不同 fingerprint | 409 `idempotency_conflict` |
| 不提供 key | 每次调用是新意图；仅返回 run_id 供后续查回，不能保证 SDK 自动重试不重复 |

fingerprint 包含原始有序消息的规范编码、model_alias、context_policy、明确上下文 revision、语义转换版本、影响请求的配置。不要 trim、Unicode 归一化或摘要式压缩后当完全相同。使用带本地秘密的摘要，避免日志中的低熵 prompt hash 被枚举；日志不显示原 key。

对先前已有 key，先读取其冻结的规范化与配置版本再比较；不能因为服务升级默认值变化而把旧意图静默改投新行为。无法理解旧版本时明确报不兼容，不自动重新执行。

**去重窗口要公开。** 只要 key tombstone 仍在，就不得重新提交。保留期由配置与隐私策略明确决定；窗口外无 dedupe 保证，不能宣称永久幂等。结果过期与 key 过期是不同事件。

## 6. 超时、取消与客户端断线

区分 queue_wait、preparation、submit_ack、first_output、inter_event、total_run、cleanup 预算，均由配置显式给出，尚无实测默认数值。心跳可以表明连接活着，不能替代总时限或语义进度。

取消在 queued/preparing 且没有在途写操作时，可阻止提交并转 cancelled；已经 submitting/running 时记录意图，调用精确 cancel 或停止能力。上游确认前保持 running 或 uncertain。

首版建议客户端断开采用统一 `cancel_on_disconnect` 策略，策略名称记录在 run；它只是停止意图，不保证上游已停止。需要耐久长任务的用户走原生 submit＋query，避免用掉线来代替任务控制。

生成完成与取消竞态以真实证据处理：已确认成功不会因晚到的取消 intent 被改成 cancelled；相互矛盾的远端终态需要核对，不能取本地回调“最后写入者”。

## 7. 重启恢复与隔离闸

启动先取得运行目录 OS 排他锁，读账重建现场，再决定 readiness。上次提交中或运行中且无终态的任务转为 uncertain，设置账号级 generation admission latch；等待已有 handle 只读核对，不自动重新执行 prompt。

操作系统释放了进程锁不等于远端已结束。lease 超时、PID 消失和浏览器窗口关闭也不证明上游取消。恢复若无法拿到精确 handle，就输出具体盲区供 operator 核对。

上下文只在确认任务不再运行后解除写入保护；不采用“等了一段时间应该结束了”。人工标记 abandoned 可以记录决定，但不能改写远端事实为 cancelled，也不自动消除安全闸。

## 8. 借鉴与简化

从 WebAI-to-API 借鉴 lease 单所有者、取消清理及请求／进程生命周期分工；不照搬多 provider 的锁层次。独立引入提交账、uncertain 和去重语义，是针对本项目副作用风险的**新设计**，不声称同行已经实现相同保障。[R1](../../research/prior-art-prb/sources.md#r1)

## 9. 验收与未决

`T12` 同 key 并发一次提交；`T13` key/body 冲突；`T14` intent 之后崩溃不重发；`T15` 准备写操作不确定不连建资源；`T16` 客户端断线不等于上游取消；`T17` 完成／取消竞态；`T18` 旧 epoch 不改新状态；`T19` 结果过期不补生成。

未决 `U06` 回执与提交幂等、`U07` 查询、`U08` 取消、`U10` 副作用，见 [A2](../appendices/a2-evidence-and-open-questions.md)。
