# M01 入口、Python 客户端与兼容 API

> v0.1.0 · draft。本文为本书设计；所有 endpoint 都是**拟议本地 gateway 接口**，不是 Prism 的内部端点。全局不变量见[总书](../00-master-design-book.md)。

## 1. 定位与边界

把用户输入校验成 `GenerationRequest`，并把结果投影到原生 API 或 Chat Completions。不得操作网页、选择隐含模型、修改 Journal 状态或自行重新提交任务。

对外提供两种语义面：**原生 run 接口**完整保留运行状态，**OpenAI-compatible 子集**提供有限兼容。二者共用 M03 核心，不是两套执行系统。

## 2. 拟议接口

| 阶段 | 本地接口 | 合同 |
|---|---|---|
| P1/P2 | `POST /prism/v1/runs` | 鉴权、校验、持久化入队后返回 `202` 与 `run_id`；不声称已提交上游 |
| P1/P2 | `GET /prism/v1/runs/{run_id}` | 返回本 principal 的状态、已知远端归属和结果可用性 |
| P1/P2 | `POST /prism/v1/runs/{run_id}/cancel` | 保存取消意图；不能仅因返回 202 就称上游已取消 |
| P1/P2 | `GET /prism/v1/capabilities` | 能力状态、证据版本、变更／过期信息；无秘密值 |
| P2 | `GET /v1/models` | 仅列兼容通道已验证可用的别名；没有则 `data: []` |
| P2 | `POST /v1/chat/completions` | 单候选、文本优先，独立上下文经过验证才启用 |
| P2 | `GET /health/live`、`GET /health/ready` | 存活与可接新请求分开；不触发试生成、续费或绕过登录 |

这些接口的请求／响应 schema 需在实现 change 中冻结。没有实现与验证前，不提供“可运行 curl”误导用户。

原生查询的 `200` 只说明查询成功，响应中的 run 仍可能是 `failed/uncertain`。跨 principal 的 run 返回不泄露存在性的 `404`；权限不是随机 run_id 的副作用。

## 3. `GenerationRequest`：核心输入合同

| 字段 | 类型／含义 | 规则 |
|---|---|---|
| `schema_version` | 本地合同版本 | 与协议适配版本分开 |
| `request_id` | 本地唯一 ID | 由服务分配，不把客户端任意字符串当内部主键 |
| `principal_id` | 调用主体 | 来自已验证 API key，不接受 body 自报 |
| `model_alias` | 注册的路由别名 | 初期候选 `prism-default`；不是底层模型身份保证 |
| `input_messages` | 有序文本消息 | 原样保留角色、顺序和文本字节语义，不偷偷截断 |
| `context_policy` | `isolated` / `explicit` | 由 M04 验证；兼容入口只走已验证 isolated |
| `context_token` | 本地不透明上下文引用或 null | explicit 必填，绑定 principal 和 auth profile |
| `side_effect_policy` | 声明的上下文副作用策略 | 初期只允许已授权的受控工作区；read-only 能力未知 |
| `stream_requested` | boolean | 真流式未验证时提交前拒绝，不自动改成伪流式 |
| `idempotency_key` | 可选外部去重键 | header 输入；以 principal 隔离，哈希存储 |
| `deadline_policy` | 本地各阶段预算引用 | 来源为已验证配置，不编造上游 SLA |
| `config_revision` | 运行配置指纹 | 执行前冻结，纳入任务证据 |

模型／参数／输入大小／角色合法性校验尽量在持久化和远程副作用之前完成。上下文创建等网络操作只能发生在 M03 已入账之后。

## 4. Chat Completions 子集

API 形状参考官方 Chat Completions，而不是假设 Prism 内部实现了同一协议。[O2](../../research/prior-art-prb/sources.md#o2)

| 项目 | 首次兼容切片 | 以后如何增加 |
|---|---|---|
| `model` | 只接受本地已验证别名 | 能力注册＋真实 outbound/响应证据 |
| `messages` | 先支持单个 user 文本消息 | 多轮 user/assistant 需历史回放验证 |
| `system` / `developer` 角色 | 默认拒绝 | 上游原生优先级证据，或明确 opt-in 的降级转换合同 |
| tools / tool_choice / tool role | 默认拒绝 | 不用 prompt 模拟原生 tool_calls |
| `n` | 缺省或 1；其他拒绝 | 多候选另立项 |
| `stream` | false 先交付；true 由 P3 gate 开放 | M05 完整链路验证 |
| `temperature`、`top_p`、token limit、`stop` 等 | 未证明可执行则拒绝，包括看似常见的默认值 | 逐参数登记映射与证据，不静默吞掉 |
| `response_format`、JSON Schema | 拒绝未实现选项 | 提示词输出 JSON 不等于严格 schema 支持 |
| `usage` | 只有上游权威用量可映射才返回 | 无数据省略或在已验证客户端合同下为 null；不伪造 0 |

对于一些 SDK 自动附带的字段，实现前收集真实请求样本；只有不改变推理语义的 envelope 元信息才能白名单接收，规则写入 schema。未知字段缺省拒绝，而不是 `extra=ignore`。

兼容子集标注为明确版本，例如 `chat-text-v1`。Hermes 主模型可能需要多角色与 tools；完成文本接口不能宣称满足其全部 agent 工作负载。

### 4.1 历史消息不能被重复注入

未来 stateless 模式：客户端持有完整历史，gateway 为每次请求建立经过验证的独立上下文，一次投递已明确转换的历史。explicit 模式：调用方只给新增输入，并可提供预期上下文 revision 做冲突检测。二者不自动混合。

把 role 标记拼进一个大字符串只是**转换策略**，不是原生 system/developer 优先级；启用时必须让客户端显式选择，并在证据中记录转换版本。不能把这种降级隐藏在“OpenAI 兼容”四个字后面。

## 5. Python SDK 与 CLI

建议公共操作：`submit`、`wait`、`get_run`、`cancel`、`capabilities`；返回 typed result 或携带 run_id 的 typed error，不只返回一段文本。

SDK 有两个显式模式：`daemon` 经本地 API 调现有核心；`embedded` 在当前进程初始化同一核心并取得运行目录排他锁。不能自动从 daemon 失败回退 embedded，否则可能产生第二个提交者。协议 probe 是独立、需批准的开发实验，不是第三条逃逸生产路径。

CLI 先服务 operator：查看能力、查看 run、诊断登录、读取脱敏证据。首版不加入 shell 执行、插件市场、账户采集或上传任意 Cookie 的 HTTP 管理接口。

## 6. HTTP 错误与真实状态

| 情况 | 提交前 HTTP 建议 | 运行记录策略 |
|---|---|---|
| 无效 API key | 401 | 不产生上游任务 |
| 参数／角色不支持 | 400 | 校验失败，不提交 |
| 输入超过本地明确限制 | 413 | 不截断后继续 |
| key 冲突／context busy | 409 | 不改变赢家的 run/lease |
| 本地队列满或限流 | 429 | 可给本地 Retry-After，但不伪装上游额度信息 |
| 登录失效或能力隔离 | 503 | readiness=false；不因重试自动修复账号 |
| 上游协议失败 | 502 | 保留失败或不确定证据 |
| 等待超时 | 504 | run_id 保留；不得据此称远端未提交 |
| 原生结果已按策略清除 | 410 | 不能自动再生成“补结果” |

错误统一含 `type`、`code`、安全的 `message` 与本地 `run_id`（已有时）。取消和未知状态通过稳定 error code 表达。流式 headers 发出后 HTTP 状态不可再修改，交付失败按 M05 终止。

## 7. 借鉴判断

继承 WebAI-to-API 的薄 API 与执行层分离，改造成单 provider；借鉴 Gemini-API 的独立客户端形态，但不复用 Gemini 协议。API 标准只是对外表示依据，不是上游能力证据。[R1](../../research/prior-art-prb/sources.md#r1) [R3](../../research/prior-art-prb/sources.md#r3)

## 8. 验收与未决

验收 ID：`T01` 未鉴权无副作用；`T02` 未支持参数提交前失败；`T03` 兼容模型表不宣传 unknown；`T04` 跨主体查询隔离；`T05` 完整历史不重复注入；`T06` SDK 两种模式不能绕过单实例。

未决引用：`U02` 模型映射、`U04` 角色语义、`U05` 隔离、`U13` 客户端请求集，见 [A2](../appendices/a2-evidence-and-open-questions.md)。当前合同字段为拟议本地 schema；不是从 Prism 抓到的字段。
