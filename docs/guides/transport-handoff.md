# Live transport 接口交接 · 0.1.1

**这里定义的是本项目内部接口，不是已知 Prism wire protocol。** 本版仅 `UnconfiguredTransport` 与 `MockTransport`；真实 HTTP 请求必须由本机捕获、脱敏样本和重复实验支撑。

## 装配与所有权

可信本地 `module:factory(settings)` 返回 `BaseTransport` 子类。factory 应只创建对象／读取显式凭证位置，不登录、不创建项目、不发生成请求；副作用必须在 supervisor 已取得锁并写意图后发生。`SDKClient(settings=..., adapter=PrismAdapter(transport))` 或 `create_app(settings, adapter=...)` 均可注入。运行目录只允许一个 Journal/worker。

`AuthProfile` 是由 adapter 引用的同一个对象；续期后更新它的状态，而不是留下陈旧 READY 引用。凭证只在 transport 内；`RemoteHandle.raw_metadata`、规范事件、异常消息、日志都不得装入 Cookie、Authorization 或完整抓包。

## 需要实现的接口

| 接口 | 输入与义务 | 输出 |
|---|---|---|
| `inspect_capabilities(session)` | 缓存／本地证据读取；不得生成、登录或创建项目 | `CapabilitySnapshot` 列表；未验证默认关闭 |
| `prepare_context(session, context, operation_id)` | supervisor 已记录资源操作意图；根据 isolated/explicit 只操作本人授权且精确绑定的资源；不得内部重试有副作用请求 | `RemoteHandle`，含已观察 workspace/conversation |
| `submit(run_id, attempt_id, session, input_text, model_alias)` | 输入已经冻结；session.context_binding 为已验证绑定；提交意图已提交；一次网络提交，无隐式重发 | 含 task 或 message 精确标识的 `RemoteHandle` |
| `observe_events(handle)` | 对精确 handle 观察／轮询；网络每次读取有截止时间；逐条 yield 规范事件，不无限积累 | 可迭代规范事件字典 |
| `lookup_events(session, handle)` | 对已有句柄的**只读核对**；不得新生成、创建资源或自动发送 cancel | 完整可验证的最终快照／状态，仍不清楚就保留 uncertain |
| `request_cancel(handle)` | 精确任务取消请求；返回只是请求回执，不是取消成功 | bool；真实确认随后由事件表示 |
| `close()` | 只释放自身资源；不得停止用户的日用浏览器或清理未知项目 | 无 |

`observe_events` 的历史抽象返回注解仍允许 list；live 实现应使用有界 iterator/generator。保留 submit/lookup 收到的 session 对象，以读取其动态 I/O 预算；不要把它当无限有效凭证。

## 内部规范事件

```json
{"type":"TextDelta","payload":{"task_ref":"<真实任务标识映射>","text":"<正文>"}}
```

内部可用类型：`SubmissionObserved`、`TextDelta`、`TextSnapshot`、`ArtifactObserved`、`UsageObserved`、`RunCompleted`、`RunFailed`、`CancellationConfirmed`、`ProtocolUnknown`。这不是要求上游出现这些字符串，wire→规范映射由真实样本证明。

所有出现的 task/message/workspace/conversation/run/attempt/epoch 标识均须与已接受请求一致。若响应天然不带标识，只有证明连接／轮询结果被绑定到精确任务后，才可声明 `handle_scoped_events=True`；默认 False。不得通过删除矛盾标识或加上本地 run_id 来“通过”校验。

完成要求：真实终态映射＋归属可核对＋正文证据＋无冲突。`RunCompleted.payload.text` 明确为 `""` 是合法空结果；字段不存在不是空结果。冲突终态、未知实质事件、错任务、EOF 未完成、超预算必须进入 uncertain，不选择最先／最后一个来掩盖冲突。已进入缓冲区的事件必须全部验证；无害重复终态允许，正常重复文本 delta 不能随意去重。

## 能力闸门与模型

Live `text_generation` 以及所用 `isolated_context`／`explicit_continuation` 必须 verified+enabled，绑定 account_scope，并有 tested_at、review_due_at 和 evidence_refs。当前 `/v1/chat/completions` 只支持已验证隔离上下文。task_lookup、取消、模型选择不能因为文字生成能用就顺便开启。

`prism-default` 只是本地路由别名。当前核心不解析／发布真实模型确认值和 token 计数，缺失保持 null；不得拿自称的模型回答、UI 显示名称或群聊额度说法填入权威字段。

## 不确定任务如何处置

提交回执持久化后，`POST /prism/v1/runs/{id}/reconcile` 只读查询原任务，可能将 uncertain 核定为 succeeded/failed/cancelled。没有回执、回执与已绑定工作区矛盾、实际不支持任务查询时，必须留在 uncertain 并请本机操作者核对。不要删除数据库、更换 home、修改状态为 failed 或创建新账号来解除闸门。

资源创建后掉线也可能留下未知项目；自动远端项目删除与缺句柄的人工裁决 UI **本版未实现**。保留精确操作账，暂停并记录实际情况。

## 预算与部署边界

`session.deadline_monotonic` 是总截止；`session.io_timeout_seconds` 是当前阶段预算。设置 httpx 的 connect/read/write/pool timeout，并保证每次轮询及每次读取不超过剩余总预算；没有进度也要及时返回／抛错，不在 transport 内重新 submit。具体轮询间隔先参考实际服务响应，不以高频探测推测上游上限。

Python 线程不能强行中止任意阻塞 I/O。核心在事件边界和调用后检时；transport 必须履行网络超时义务。关闭时若 worker 不退出，DB 与 OS 锁仍保留，拒绝启动第二写入者；这不是无限期等待正常化，而是安全停机失败。

仅单进程、单 worker、单账号、本机 API。无真实 SSE、通用工具调用、多模态、自动远端清理、分布式锁或多账号调度。配置中的本地预算不是 Prism 的官方额度。`idempotency_tombstone_days` 是保留配置，自动过期／GC 暂未实现；本版不自动删除幂等记录。
