# M04 上下文隔离、资源所有权与精确清理

> v0.1.0 · draft。**新对话不自动等于新上下文；关闭本地页面不自动等于删除远端内容。**

## 1. 定位与风险

Prism 官方描述其 AI 理解项目、文稿和既往修订；本章据此把项目视为潜在上下文输入，而不是仅隔离聊天消息。[O1](../../research/prior-art-prb/sources.md#o1)

ContextManager 为一次 run 绑定可解释、可审计的上下文，管理 lease 与续接边界，不负责消息协议格式，也不参与模型选择。

## 2. 三个上下文层必须分别看待

| 层 | 例子 | 网关能证明的范围 |
|---|---|---|
| 工作区层 | 文件、文稿、修订、项目指令 | 需实际读回机制与权限证据；空聊天不能代替空项目 |
| 对话层 | 旧消息、线程分支、任务状态 | 需会话标识、关联与续接证据 |
| 账号／供应商层 | 账号配置、不可见服务端状态 | 通常无法穷尽证明；应记录边界而非宣称零记忆 |

因此本书 `isolated_context verified` 指**本次适配器能控制和验证的工作区／对话隔离范围**，不作服务端绝对无记忆或零保留承诺。盲区写入 manifest 的 `context_limitations`。

## 3. `ContextBinding` 合同

| 字段 | 含义 |
|---|---|
| `context_id` | 本地不透明引用，不使用用户输入 URL 作为信任根 |
| `principal_id` / `auth_profile_id` | 谁能调用、用哪个上游授权会话 |
| `context_policy` | isolated / explicit |
| `workspace_ref` / `conversation_ref` | 仅填实际确认值；映射到 RemoteHandle |
| `context_revision` | 本地观察版本；是否有上游版本证据另记 |
| `scope_manifest_ref` | 被允许的文件／指令范围与观察到的上下文说明 |
| `isolation_evidence_ref` | 验证方式、时点和盲区 |
| `side_effect_policy` | 允许的副作用范围，不靠 prompt 伪装只读 |
| `ownership_proof_ref` | 本项目创建或用户显式授权绑定的证据 |
| `busy_run_id` / `lease_epoch` | 唯一在途 owner 与本地代数 |

binding 与 lease 不同：binding 可以长期存在，lease 是一次 run 的变更权限。持有合法 context_token 也不能绕过 busy 检查。

## 4. 两种执行模式

### 4.1 isolated：兼容接口的前提

理想实现为每个独立请求新建受控上下文，并有证据证明不会读到前一请求的工作区／会话。若上游允许安全重置，也必须验证重置具体清了什么，不能把 UI “清空”按钮等同全部上下文删除。

首轮不做 workspace pool、隐藏 conversation cache 或自动复用。若没有可验证的独立上下文机制，通用 `/v1/chat/completions` 保持关闭，最多提供明确标注上下文的原生实验接口。

### 4.2 explicit：有状态原生调用

context_token 绑定 principal、auth profile、工作区与会话，调用方明确愿意续接。输入只包含新增 turn；可使用 `expected_context_revision` 拒绝过期提交。删除／编辑旧消息后不能仍沿旧 revision 续接。

不得把 A 客户端的显式 context_token 自动用于 B 请求，即便都是同一个账号。工作区共享给合作者时，外部编辑也可能改变上下文；首版只使用无人并行编辑的专用实验范围，不能承诺对共享工作区加本地锁就完全隔离。

## 5. `ResourceLease` 与所有者验证

lease 至少绑定 run_id、context_id、owner_epoch、可选浏览器 generation、精确 page/target 标识与允许动作。所有变更操作前检查 lease 有效且 owner 匹配；页面导航到不同项目、浏览器重建或上下文观测漂移时使 lease 失效。

只有当前 owner 能写入或释放。冲突失败者不关闭赢家的页面、不撤销其 registry、不清理其 callback。释放用 compare-and-release，重复释放无副作用。

本地锁不能约束人工在同一页面输入，也不能约束远端其他合作者；发现未经声明的导航或修改就 quarantine，不继续往“当前页面”发 prompt。

## 6. 文件与工作区副作用

首版不接入用户真实论文项目。允许的实验范围是用户明确授权的专用工作区，其创建、生成过程可能修改哪些内容都要被声明。

拟议策略 `owned_workspace_only` 限制 gateway 发出的动作只指向受控工作区，但**不声称能控制模型内部所有工具操作**。供应商无法提供边界证据时，相应能力保持 experimental。`read_only` 只有上游有实际强制机制且验证后才注册；提示“不要改文件”不是权限控制。

`Artifact` 只表示结果里出现文件或修改建议；不得因为看到它就下载、执行、写入用户工程，或把其内容当作新的系统指令。

## 7. 清理分级

| 动作 | 首版默认 | 安全条件 |
|---|---|---|
| 移除本次 callback、释放本地 buffer | 自动 | run_id 与 epoch 匹配 |
| 关闭本次新建且独占的页面 | 可自动 | 精确 target、ownership 标记、没有待核对任务依赖 |
| 断开自己创建的 transport 连接 | 自动 | 不操作其他客户端连接 |
| 停止远端生成 | 条件调用 | 精确 handle、取消意图及已验证能力 |
| 删除远端会话／工作区／文件 | 默认禁止 | 单独批准、准确归属、审计与失败处理 |
| 关闭整个用户浏览器 | 禁止 | 不作为请求清理手段 |

没有远端自动删除时会积累实验资源。因此 P0/P1 要记录已创建数量、未清理集合和可追踪 ID，并设置明确的本地 admission 预算；预算到达后停止新建，提醒 operator 手工管理，**不为继续运行而广域清空账号项目**。

远端删除将来启用也不能保证服务端彻底抹除，文档不得将本地“已删除标记”解释成供应商数据保留保证。

## 8. 隔离验证方法

使用合成、非敏感、各自不同的 nonce 文本测试 A/B 上下文，在已知可控工作区内检查 B 的实际输入、文件范围和历史是否包含 A。续接验证 A2 能引用 A1 且不混入 B1；再测试人工导航／revision 改变会被拒绝。

**只问模型“你记得 A 吗”不是隔离证明。** negative canary 只是辅证；需要机制级上下文绑定、生成请求证据和资源归属记录。证据缺失写 partial，不因为答案碰巧没泄露就记全绿。

## 9. 借鉴与验收

借鉴 WebAI-to-API 的单 owner、条件释放和 lease 失效；改造到 Prism 的工作区＋对话双层。ValueHermes 的“材料不能取得执行权”思想在这里仅转化为产物非指令边界，不复制其投资判断权系统。[R1](../../research/prior-art-prb/sources.md#r1) [V2](../../research/prior-art-prb/sources.md#v2)

验收：`T20` A/B 上下文隔离；`T21` explicit 不重复历史；`T22` busy 冲突不损伤赢家；`T23` 页签身份／revision 漂移拒绝；`T24` 清理不碰用户页面与远端文件；`T25` 无只读证据不宣传只读；`T26` 资源预算耗尽停止新建。

未决 `U05` 隔离、`U07` 归属查询、`U10` 文件副作用，见 [A2](../appendices/a2-evidence-and-open-questions.md)。
