# prism2api 领域词汇与边界

> v0.1.0 · draft。本文只定义用语，不记录运行状态或任务进度。

| 术语 | 本项目含义 | 不等于 |
|---|---|---|
| Prism | `prism.openai.com` 对应的 OpenAI 工作区产品 | ValueAgents 历史同名“Prism 知识／playbook 层” |
| prism2api | 独立的 Python 接入与本地网关项目 | 官方 API、ValueHermes 插件、公共中转服务 |
| provider / adapter | 解释 Prism 语义与外部事件的边界组件 | 另一个自主研究或执行 agent |
| transport | 具体授权会话与网络／浏览器执行方式 | 智能路由器、账号池、风控绕过层 |
| principal | 本地网关调用主体 | 上游账号、客户端自报 user 字段 |
| auth profile | 获授权的上游会话配置 | 可公开转发的 API key |
| context | 工作区＋对话＋已知配置的明确绑定 | 当前浏览器标签页、仅一串历史 messages |
| isolated | 网关可控制并已验证范围内的独立上下文 | 服务端绝对无记忆、零保留或零外发 |
| explicit | 用户明确选择有状态续接 | 隐式缓存命中 |
| run | 一次用户意图对应的本地执行记录 | 一次 TCP 连接、一个上游 chunk |
| submit attempt | 跨越一次生成提交边界的记录 | 自动无限 retry |
| uncertain | 远端事实不足，禁止盲目重发 | 失败、已取消、已空闲 |
| lease | 精确资源的单所有者使用权 | 永久所有权或对人工／供应商的全局锁 |
| completed delivery | 某个客户端收到了完整结果 | 仅远端生成结束 |
| capability verified | 有版本、范围与证据的能力判断 | README 声称、论坛体验、模型自述 |
| replay | 对脱敏样本的离线解析／行为回放 | 重发 prompt 后得到相似答案 |
| 本地优先 | 网关和本地记录由用户控制 | 模型在本地运行 |
| sealed / 封存 | 未获新阶段批准前不实现、不启用 | 预先创建大量空抽象与依赖 |

术语变化需回填其合同所有者，避免把相似名称混当同一机制。来源对照见[登记表](research/prior-art-prb/sources.md)。
