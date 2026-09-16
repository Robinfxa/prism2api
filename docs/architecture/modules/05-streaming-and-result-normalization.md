# M05 事件归一、流式交付与结果完整性

> v0.1.0 · draft。**本章拥有事件到文本的语义；M03 拥有 run 状态。流式连接的终止，不自行宣告 run 完成。**

## 1. 两条管线，不把慢客户端变成生成调度者

```text
上游 frame → 增量解码 → 本地 NormalizedEvent
                           │
                           ▼
                  有界 ingestion queue
                           │
                           ▼
                    权威结果汇编器
                      │         │
                      ▼         ▼
                  M06 存储   有界 delivery queue → HTTP/SDK
```

两种 queue 不是两个通用总线，只是内存边界。慢客户端堵塞 delivery 时可以截断这次交付，不阻塞事件采集；ingestion 丢失则结果完整性本身受损，必须显式恢复或判不确定。

`DeliveryRecord` 由本章定义：delivery_id、run_id、principal_id、协议／兼容版本、state、已发字节数、开始／结束时刻与安全错误代码。状态为 `not_started / streaming / completed / disconnected / truncated`；这里 completed 只指网关完成本次响应写出，不证明客户端应用已持久化或采纳。多次查询不能互相覆盖交付状态。

## 2. `NormalizedEvent`：本地归一事件

公共信封：run_id、attempt_id、owner_epoch、local_seq、received_at、event_type、payload、source_event_ref（可空）、parser_revision。序号是本地 FIFO 顺序，不伪装服务端序号。

| 类型 | payload 语义 | 允许的影响 |
|---|---|---|
| `SubmissionObserved` | 已接受任务的证据、可用 handle | M03 可转 running；不得仅凭按钮点击 |
| `TextDelta` | 明确属于用户可见正文的追加文本 | 顺序追加 |
| `TextSnapshot` | 权威正文快照、是否最终 | 与已缓冲文本核对 |
| `ArtifactObserved` | 文件／引用／修改建议等分类产物 | 单独保存，不自动拼成最终正文或执行 |
| `UsageObserved` | 有来源的用量及口径 | 只有可映射数据才到兼容 usage |
| `RunCompleted` | 权威完成依据、可用终态元信息 | 启动完整性及持久化检查 |
| `RunFailed` | 权威失败与安全错误代码 | 交给 M03 状态处理 |
| `CancellationConfirmed` | 精确任务已被停止的依据 | 与已到达终态进行竞态协调 |
| `ProtocolUnknown` | 无法解释的关键语义 | 不忽略后伪造成功，触发核对／隔离 |

这些类型是本项目设计，不是实际 Prism event 名称。adapter 只有能证明映射时才产出，不能用“安静了一会儿”合成 RunCompleted。

## 3. 文本处理与改写

### 3.1 增量规则

真实 delta 直接追加；累计快照只有当 `new.startswith(buffer)` 时才可取新后缀。重复事件只有在上游有稳定唯一事件 ID、重放合同可证明时才按 ID 去重；相同文本片段可能是合法重复，不能按文本内容删掉。

UTF-8、JSON/SSE 等 parser 在 frame 边界保留状态；未解码完整时不发出坏字符。网络层和语义层的结束信号分开。

### 3.2 非前缀改写无法由标准追加流撤销

上游把已经输出的旧句子替换为新句子时，普通 Chat Completions 文本 delta 没有撤回机制。禁止通过 `current[len(previous):]` 或最长公共前缀切片掩盖已发内容的错误。

本书选择：非流式优先，以权威最终快照作为结果；真实流式只对已证明 append-only 的内容启用。若 live 流仍发生已交付前缀冲突，**终止该次兼容交付、不发正常结束**，run 汇编可继续等待权威最终结果并经原生查询返回。不得把后来的完整结果再追加到已错误的流上。

原生 `reset/full_snapshot` 扩展是后置选项，不伪装为标准 OpenAI delta。

## 4. 成功、失败与 `[DONE]`

成功输出链必须按顺序：

1. 收到真实终态依据，且没有未解释的关键事件。
2. 汇编完整最终结果，确认 run、上下文与 attempt 一致。
3. M06 原子提交结果引用与 manifest，M03 状态置 succeeded。
4. 兼容流发最终 choice、适用的 finish_reason，再发 `data: [DONE]`。

任何一步失败都不能发送伪成功 sentinel。上游 EOF、DOM 不变化、timeout、queue overflow、浏览器关闭都不直接满足完成条件。

若终态可确认但上游没有原生 finish_reason，兼容映射为 stop 时必须有本地明确规则，且 manifest 标记 `finish_reason_origin=gateway_mapping`。只有明确截断／预算耗尽证据才映射 length；未知情况不猜。

已发送 headers 后无法改 HTTP code；默认截断 body、不发送 `[DONE]`，日志写 delivery_truncated。客户端是否正确识别这种不完整结束必须通过 P4 验证；对于把 EOF 当成功的客户端，不能宣称流式兼容。标准协议形状参考 [O2](../../research/prior-art-prb/sources.md#o2)。

## 5. 内存、背压与清理

所有队列、正文大小、artifact 元数据量和事件数都要有显式预算，默认值在实现阶段按测试确定，不复制同行数值。

| 异常 | 处理 |
|---|---|
| delivery queue 满 | 截断该交付并执行已声明的 disconnect 策略；不静默丢文字 |
| ingestion queue 满 | 结果链不可信；尝试精确只读取最终 snapshot，否则 uncertain |
| 结果字节超过预算 | 停止接收/发出，记录 limit；不能截断后标正常成功 |
| 乱序／非法 epoch | 拒绝污染当前 run；关键链缺失则核对 |
| 客户端掉线 | 保存 delivery 状态，取消意图交 M03；不由 callback 自删 run |
| 清理再次被取消 | 受限 shield + cleanup deadline；未释放资源隔离，不能无限等待 |

浏览器 callback 只校验最小信封并非阻塞 enqueue，不能等待网络、数据库或慢客户端。`finally` 清理 callback、observer、订阅与自有 lease；task exception 必须被收集。清理失败要有证据并隔离资源，不允许报成功清理但泄露旧 observer。

## 6. `GenerationResult`

结果合同包含：run_id、requested_alias、可空 provider_model_id_confirmed、最终可见 text、结构化 artifact 描述、可选权威 usage、finish_reason 与来源、context_ref、manifest_ref、result_digest。

进度信息、文件编辑日志、引用元数据和模型公开提供的其他输出类型与最终正文分开；**不把猜测的内部推理过程当正文或产品能力**。上游没有提供的字段保持缺失，不能由 LLM 补齐。

结果可供脚本读取，但永远是非受信数据。禁止 adapter 或网关把生成的 shell/code 当指令执行。

## 7. 借鉴的适用边界

WebAI-to-API 文档给出 bridge、request_id、有界队列、rewrite 与异常截断的设计。这里借鉴事件清理和失败可见性；对一般文本改写，明确不采用“总能通过 suffix 修正已发送流”的强假设，这是本项目新增约束，不是对其全部源码的审计结论。[R1](../../research/prior-art-prb/sources.md#r1)

## 8. 验收与未决

`T27` 网络分片不损伤语义；`T28` 累积快照无重复；`T29` 已发送非前缀改写不伪修复；`T30` 慢客户端不能卡死采集；`T31` ingestion overflow 不静默丢片；`T32` 无真终态不发 DONE；`T33` 持久化失败不发成功；`T34` callbacks/observer 取消后无泄漏。

未决 `U01` 协议、`U09` 流式／终态、`U11` 用量，见 [A2](../appendices/a2-evidence-and-open-questions.md)。
