# M02 PrismAdapter、能力注册与协议发现

> v0.1.0 · draft。本章明确区分网关自定义合同与尚未知晓的 Prism wire protocol。当前没有真实上游协议样本。

## 1. 定位

唯一理解 Prism 产品语义的组件。它完成请求转换、上下文能力检查、提交回执解释、远端只读查询和事件解码；不拥有本地调度、SDK 重试或 SQLite 写权。

借鉴 WebAI-to-API 的 provider/backend 分工与 Gemini-API 的客户端边界；不先搭多 provider 注册框架。[R1](../../research/prior-art-prb/sources.md#r1) [R3](../../research/prior-art-prb/sources.md#r3)

## 2. `CapabilitySnapshot` 合同

每项能力单独记录，不用一个全局 `works=true`：

| 字段 | 含义 |
|---|---|
| `capability_id` | 本地稳定名称，例如 text_generation、isolated_context、delta_stream |
| `evidence_state` | `unknown / observed / verified / unsupported / stale` |
| `activation_state` | `disabled / enabled / quarantined`，独立于证据状态 |
| `account_scope` | 本地 auth profile 引用；不暴露账号秘密 |
| `transport_revision`、`parser_revision` | 本次实现版本 |
| `tested_at`、`review_due_at` | 观测时间与需复核时间；不从网页更新时间猜能力 |
| `evidence_refs` | 脱敏样本、回放结果、真实验证回执的引用 |
| `limitations` | 适用角色、输入、上下文、副作用和盲区 |

**可启用 = verified + enabled + 无隔离标记 + 账号适用 + 依赖能力全部满足**。observed 只是一次观测，不能直接进入 `/v1/models`。stale 或协议指纹变化时，受影响能力停止新准入；不要对全部功能无差别失败，也不要偷偷换 transport。

候选能力至少包括：text_generation、isolated_context、explicit_continuation、task_lookup、cancel_confirmation、delta_stream、model_selection、role_mapping、usage_reporting、read_only_mode。当前全部缺真实验证。

## 3. 内部接口：职责而非虚构端点

| 操作 | 输入 → 输出 | 限制 |
|---|---|---|
| `inspect_capabilities` | 已登录会话 → 能力观察 | 不自动发测试 prompt |
| `prepare_context` | 显式 policy 与资源归属 → binding 或 gap | 远端创建有副作用，须经 M03 记账 |
| `submit` | prepared request、lease、attempt → receipt/事件源 | 每个 attempt 只调用一次；不含自动重试 |
| `observe` | RemoteHandle → 归一事件流 | 不能隐式生成 |
| `lookup` | RemoteHandle → 状态／结果证据 | unknown handle 不猜测最近对话 |
| `request_cancel` | 精确 handle/lease → 已送达、确认或未知 | 不做广域 Stop、不杀共享浏览器 |
| `release_local` | 归属明确的本地 lease → 释放结果 | 不删除远端工作区 |

接口可以初期以普通 Python protocol / dataclass 表达；不要求加载插件或动态发现。

## 4. `RemoteHandle` 与能力事实

本地对象可含 `workspace_ref`、`conversation_ref`、`task_ref`、`message_ref`、`server_event_cursor`，但**每一项允许 unknown**，且只有上游证据给出时才填。它们是本地规范字段名，不是猜测的网络 JSON key。

模型身份分开记录 `requested_alias`、`ui_label_observed`、`wire_route_observed`、`provider_model_id_confirmed`。请求中的模型字符串只能证明请求意图；UI 标签只能证明界面显示；模型自述不能证明 backend identity。没有可靠回执时确认值保持 null，不夸大一项证据的含义。

免费项目／协作者不等于推理不限量；本项目不靠绕开 Codex 额度的论坛推断设计调度或预算。[O1](../../research/prior-art-prb/sources.md#o1)

## 5. P0 协议调查的封闭范围

真实探测前必须有用户授权的账号与独立实验工作区，且对适用条款、访问资格及数据外发作确认。先通过正常界面完成一个低风险文本任务，记录提交、响应、终态与资源归属；若无法合法进行，不扩展为绕过控制的方案。

产物包含：脱敏请求／响应形状、协议说明、事件样本、确认为何完成的依据、每个未知字段、发生时间、构建线索和样本散列。原始 HAR、Cookie、正文与真实账号标识不进入 repo。

必须区分网络分片和语义事件：TCP/HTTP chunk 可能把一个 UTF-8 字符或 JSON 对象拆开；SSE、NDJSON、WebSocket、轮询哪个存在由证据决定。没有证据时不先写某种上游解析器。

## 6. transport 选择矩阵

| 观测到的事实 | 建议 | 为什么 |
|---|---|---|
| 合法会话下直接协议稳定、结果可追踪 | HTTP transport | 少网页生命周期；但认证与版本漂移仍需维护 |
| 登录／提交必须浏览器，网络事件可读 | browser-assisted transport | 浏览器做必要步骤，网络事件优先承载结果 |
| 只能读 DOM | DOM 实验 adapter | 限定页面版本、单请求；没有权威终态不能标稳定成功 |
| 无法证明隔离、完成或安全归属 | 保留实验状态 | 不以“看起来回答了”开放通用 API |

切换 transport 是显式版本变化：旧 run 继续沿原 handle 做只读核对，不把同一 run 换 transport 再 submit。第二条实现只有测得必要性后才建。

## 7. 协议漂移策略

版本以 adapter 实现、parser、schema、样本集和能力依赖图共同标识。对于新增非关键 metadata 可有显式 allowlist；未知的提交确认、终态、上下文或文本事件不得直接忽略后报成功。

漂移发现 → 标记受影响 capability 为 stale/quarantined → 拒绝新请求 → 保存脱敏诊断 → 离线回放 → 经授权实测 → 更新 evidence → 显式恢复。线上失败不自动启动 Researcher、不大量试探接口、不换账号顶上。

## 8. 验收与未决

验收：`T07` 未验证能力不可激活；`T08` 路由标签不等于模型确认；`T09` submit 无内部重试；`T10` 未知关键事件触发能力隔离；`T11` 解析边界覆盖截断 UTF-8、网络分片与终态事件。

未决 `U01–U04`、`U06–U09`、`U11` 见 [A2](../appendices/a2-evidence-and-open-questions.md)。这些缺口由 P0 实验回答，不能靠移植同行 Cookie/端点填空。
