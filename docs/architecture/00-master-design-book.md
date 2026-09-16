# prism2api 架构总设计书

> **版本：v0.1.0 · 状态：draft / 完整评审初稿 · 日期：2026-09-16**
>
> 本书定义 prism2api 应当成为什么，不描述一个已经运行的系统。用户已授权成书；尚未批准生产实现、真实账号探测、工作流安装或合并 main。
>
> 组织方式参考 ValueHermes：**总书 + modules 细稿 + appendices**；按构件分章，以强类型合同连接，并附“生命周期 × 构件”视图。继承方法，不继承投研业务与平台规模。[V1](../research/prior-art-prb/sources.md#v1)
>
> 本次工作流基线为上传的 **`dev-flow-GPT.zip`**，不是前面散装的 Claude Code 版。其实际文件、阅读范围和差异见 [W1](../research/prior-art-prb/sources.md#w1)。

## 00. 成书契约与证据纪律

### 00.1 四种陈述必须分开

| 标签 | 含义 | 可以据此做什么 |
|---|---|---|
| **来源事实** | 从用户文件、仓库或官方文档实际读到的内容 | 只在来源覆盖范围内引用 |
| **本书设计** | 为 prism2api 新提出的合同、状态或切片 | 评审通过后转为实现输入 |
| **待验证** | 上游行为、模型、额度或边界没有真实证据 | 进入验证清单，不能当已有能力 |
| **已实现／已实测** | 存在目标代码、调用者、运行证据 | 本次运行时能力均不属于此类 |

以下“必须／不得”均为**拟议架构约束**，不是对当前软件状态的断言。每章按“定位 → 职责 → 合同 → 正常路径 → 失败路径 → 借鉴 → 验收 → 未决”编排。用户评审前不标“✅ 定稿”。

### 00.2 单一事实源

总书拥有北极星、范围和全局不变量；模块拥有本域详细合同；附录只索引、登记跨模块借鉴及待验证事项。Research Dossier 保存外部证据，不自动批准采纳；Director Plan 保存阶段路线，不冒充当前行为；未来 OpenSpec change 保存一次变化与验证，archive 后的 capability spec 才表述交付行为。[W1](../research/prior-art-prb/sources.md#w1)

资料中的设计描述不等于源码保证，源码存在不等于真实路径已通过。同行项目的浏览器选择器、Cookie 名称和请求地址均不作为 Prism 协议证据。

## 01. 北极星与产品定位

**一句话：把用户获授权使用的 Prism 工作区能力，封装成可解释、可隔离、可恢复的 Python 接口与本地 API；宁可明确失败，不伪造模型、上下文、输出或成功状态。**

价值不在“免费无限调用某模型”，而在将一次网页任务变成有输入边界、执行归属、结果证明和恢复路径的程序调用。官方将 Prism 描述为项目感知的科研写作工作区，而非普通无状态聊天框；这要求我们把项目和文件副作用作为核心边界。[O1](../research/prior-art-prb/sources.md#o1)

### 01.1 目标用户与使用场景

| 场景 | 期望 | 本书边界 |
|---|---|---|
| 本机 Python 脚本 | 提交任务、获取结果、检查失败 | 共享同一运行核心，不绕过状态与认证 |
| 通用 OpenAI-compatible 客户端 | 调用有限的 chat 接口 | 只支持被证明可映射的子集 |
| Hermes / Oak / ValueHermes | 作为受控文本能力使用 | 独立客户端验收，不默认充当完整 agent 主模型 |
| 协议研究与维护 | 离线回放、定位上游变化 | 证据脱敏、版本明确、未验证能力不宣称可用 |

### 01.2 不做的事情

首版不做账号池、轮号、公共中转站、收费售卖、验证码自动绕过、反风控框架、代理池、分布式调度、通用 agent 引擎、管理后台、自动远程文件编辑、Responses/Anthropic 协议全集或工具调用模拟器。对第三方服务的限流、访问控制和资格限制保持尊重，不把本地部署视为条款豁免。

“本地优先”只指网关、凭证及运行记录由本机控制；**提示与上下文依然会发往云端 Prism**，不是本地模型，也不是零数据外发承诺。

## 02. 来源对照与采纳方式

| 来源 | 本次采用的方法 | 不搬入的内容 |
|---|---|---|
| 上传 GPT 工作流 | Source of Truth、Major 阶段计划、切片验证、显式 worker brief | Claude 文件锁、长期读码母体、未运行的审批信号 |
| ValueHermes | 模块与生命周期双视图、强类型接口、证据链、封存边界 | 投研漏斗、三库、常驻分析 agent、L1–L4 全套平台 |
| WebAI-to-API | provider / adapter / runtime 分层、资源归属、流式清理 | 多 provider 框架、五级锁体系及已知网页协议 |
| AIstudioProxyAPI | API、页面控制、流式链路分离 | Google 专用页面逻辑、多实例管理界面 |
| Gemini-API | 客户端抽象、会话续接、输出分类 | Gemini Cookie、RPC、Gems 语义 |
| grok2api | 网关错误与凭证状态的工程化思路 | 账号池、Grok 多模态及多产品线 |
| chat2api | 历史消息／网页会话适配教训 | 老认证、老模型表、旧端点仍可用的假设 |

详细证据等级及落点见 [A1 借鉴矩阵](appendices/a1-borrow-matrix.md)。**矩阵里的“采纳设计”不等于“已 borrow 代码”。**

## 03. 全局不变量

| ID | 约束 | 执法所有者 |
|---|---|---|
| **I01** | 未证明的上游字段、模型、额度、端点不得伪装为事实 | M01 / M02 |
| **I02** | 独立请求不能静默复用另一个请求的项目、会话或隐藏历史 | M04 |
| **I03** | 同一上下文同时只能有一个变更所有者 | M03 / M04 |
| **I04** | 进入提交边界后的不确定结果不得自动重新生成 | M03 |
| **I05** | 只有真实完成且结果完整、持久化成功才能形成成功结果；传输结束不等于生成完成 | M03 / M05 / M06 |
| **I06** | 对外流不得重复、乱序、静默丢片或伪造正常结束 | M05 |
| **I07** | 清理只能操作明确归属本次任务的资源；关页面不等于删项目 | M04 / M06 |
| **I08** | 不支持的参数、角色和 tools 明确拒绝；禁止隐式降档或偷偷换供应商 | M01 / M02 |
| **I09** | 凭证、原始 HAR、真实论文和用户输入不进入仓库或默认遥测 | M06 / M07 |
| **I10** | SDK、CLI 与 API 共用运行核心和锁；第二个进程不得绕过单实例约束 | M03 / M07 |
| **I11** | 每个结果都有本地 run_id 和机器可读证据说明；无证据部分明确 unknown | M06 |
| **I12** | 设计、工作流验证、离线测试、真实链路和产品兼容各自声明；不能相互替代 | M08 |

不变量的对应验收见 [A3](appendices/a3-delivery-and-acceptance.md)。它们是首版安全与正确性底线，不是未来优化。

## 04. 系统结构

```text
Python SDK / CLI                         OpenAI-compatible HTTP
         │                                       │
         └──────────────┬────────────────────────┘
                        ▼
             M01 入口与能力校验
                        │
                        ▼
             M03 RunSupervisor
            队列 / 提交账 / 生命周期
                │               │
                ▼               ▼
        M04 ContextManager   M06 Journal + Evidence
                │
                ▼
          M02 PrismAdapter
           能力 / 语义适配
                │
                ▼
     M07 单一已验证 Transport + Auth
          HTTP 或 browser-assisted
                │
                ▼
              Prism
                │
                ▼
      M05 事件归一 → 结果汇编 → 交付
                │                  │
                └────── M06 ──────┘

M08：契约测试 / 离线回放 / 真实验收 / 工作流治理
```

这是静态职责图，不表示每一层独立进程。首版为**一个 Python 进程、一个账号配置、一个生成 worker、一套本地运行目录**；不引入消息中间件或分布式锁。浏览器仅在证据证明必要时启用，transport 首轮只实现一种。

### 04.1 模块索引与代码落点

下列 `src/` 路径均为**建议落点，尚未创建**。

| 模块 | 详细合同 | 建议落点 | 唯一职责 |
|---|---|---|---|
| M01 | [入口与兼容协议](modules/01-api-and-client-contract.md) | `api/`、`client.py` | 参数、鉴权、协议投影 |
| M02 | [Prism 适配与能力](modules/02-prism-adapter-and-capabilities.md) | `provider/` | 上游语义、能力证据、解析契约 |
| M03 | [请求生命周期](modules/03-run-lifecycle-and-idempotency.md) | `runtime/supervisor.py` | 唯一生成调度、幂等、恢复 |
| M04 | [上下文与资源归属](modules/04-context-and-resource-ownership.md) | `runtime/context.py` | 隔离、续接、lease、清理权限 |
| M05 | [流式与结果](modules/05-streaming-and-result-normalization.md) | `runtime/events.py` | 事件顺序、文本完整性、完成投影 |
| M06 | [状态与证据](modules/06-journal-evidence-and-storage.md) | `storage/` | 持久化、结果提交、证据与保留 |
| M07 | [认证与部署](modules/07-auth-security-and-deployment.md) | `transport/`、`config.py` | 登录态、安全边界、进程运行 |
| M08 | [验证与开发治理](modules/08-evaluation-and-workflow.md) | `tests/`、开发文档 | 独立验收面、切片与阶段 gate |

建议统一命名空间 `src/prism2api/`；M01–M08 不是八个插件，也不要求八层继承结构。先用函数与少量 typed records，只有真实替换需求才引入抽象。

## 05. 生命周期 × 构件

| 生命周期 | 主路径 | 完成证据 |
|---|---|---|
| 能力发现 | M07 登录状态 → M02 能力证据 → M01 对外可用项 | 不等同于生成成功；只返回已验证且未失效的能力 |
| 独立请求 | M01 → M03 入账 → M04 新隔离目标 → M02/M07 提交 → M05 → M06 | run、上下文归属、结果摘要和终态一致 |
| 显式续接 | M01 token → M04 校验归属与上下文版本 → M03 串行执行 | 只追加新输入，不重复完整历史 |
| 取消／掉线 | M03 保存意图 → M02 精确停止或只读核对 → M06 | 不把本地断开伪装成上游取消 |
| 崩溃恢复 | M06 读账 → M03 标记不确定 → M04/M02 只读核对 | 无隐式 resend；未知任务保持阻塞 |
| 上游变更 | M02 发现协议漂移 → 下线受影响能力 → M08 回放与实测 | 重新登记版本与证据，未通过不恢复宣传 |

## 06. 跨模块契约与唯一写权

| 合同 | 定义所有者 | 生产者 → 消费者 |
|---|---|---|
| `GenerationRequest` / `ApiPolicy` | M01 | SDK/API → M03 |
| `CapabilitySnapshot` / `RemoteHandle` | M02 | Adapter → M01/M03 |
| `RunRecord` / `SubmitAttempt` | M03（状态）；M06（存储） | Supervisor → Journal |
| `ContextBinding` / `ResourceLease` | M04 | ContextManager → M03/M07 |
| `NormalizedEvent` / `GenerationResult` / `DeliveryRecord` | M05 | Adapter → Supervisor/交付层 |
| `EvidenceManifest` / 保留策略 | M06 | Supervisor/Storage → 查询与审计 |
| `AuthProfile` / `TransportSession` | M07 | AuthManager → Adapter |

字段表与验收均在各模块；[A4](appendices/a4-contract-index.md) 只给索引。不得在 API handler、browser callback 或 CLI 再维护一个独立 `current_run/current_chat`。语义冲突先修改合同所属章节，再更新消费者，不用“兼容字段”藏第二真相。

## 07. 关键设计取舍

### 07.1 独立仓库、共享核心、薄入口

不 fork ValueHermes，也不从旧 ChatGPT 项目整仓改域名。库与服务共享 `RunSupervisor`；独立库模式必须获得同一运行目录的排他进程锁。daemon 运行时 SDK 通过本地 HTTP 调用它，不能另起隐藏 worker。

### 07.2 先验证协议，再冻结 transport

HTTP 候选优先调查；若认证或提交确需浏览器，则 browser-assisted；DOM-only 仅作为受限实验选择，且完成语义必须有证据。**本书不写任何猜测的 Prism 内部 URL、请求字段或 Cookie 名称。** 转换路线以 P0 证据决定。

### 07.3 原生运行接口先于兼容接口

原生接口能表达 `uncertain`、显式上下文与长任务查询；OpenAI Chat Completions 只是其受限投影。不能为兼容而把上下文、参数支持或取消结果抹平。

### 07.4 一个数据库，不搬三库

首版一套 SQLite `runtime.db` + 受保护结果文件 + 脱敏测试 fixtures。学习 ValueHermes 的账别与证据分层，不复制它的三库拓扑或 Inspector agent。[V1](../research/prior-art-prb/sources.md#v1)

### 07.5 接受可见的不确定，不承诺 exactly-once

本地去重只能约束本地调度。上游未证明支持幂等时，崩溃点与网络不确定性无法由本地事务消除；系统选择保留 `uncertain` 和人工核对，牺牲自动重试便利，避免重复工作及文件副作用。

## 08. 阶段性产品范围

| 阶段 | 目标 | 不提前承诺 |
|---|---|---|
| P0 协议证据 | 单次授权实验、脱敏录制、提交与完成证据 | 不搭完整网关、不宣称具体模型或不限量 |
| P1 客户端最小闭环 | 原生文本 run、单所有者、持久化、错误查询 | 不承诺通用聊天角色语义 |
| P2 本地 API | 原生接口 + 被验证的 Chat Completions 子集 | 没有隔离证据则不开放兼容入口 |
| P3 流式与恢复 | 真增量、取消竞态、崩溃核对、漂移处置 | 不把缓冲后分片称实时流式 |
| P4 候选客户端验收 | 明确的客户端版本、请求集和结果证据 | 不把一个 curl 成功称 Hermes 全兼容 |

这些是**建议阶段**，不是并行启动的五项工程。当前仅架构书交付完成；P0 及以后仍待批准。阶段验收映射见 [A3](appendices/a3-delivery-and-acceptance.md)。

## 09. 真实的未决边界

当前没有 Prism 实际网络证据，以下均保持 unknown：传输协议、认证续期、远端幂等、模型选择／推理档位、项目清空语义、角色映射、取消确认、任务查询、流式事件、token 用量、额度规则与服务级保障。不会用模型自述或论坛体验替代证据。

**不阻塞成书，但阻塞相应能力启用。** 验证方法、所有者与失败回退集中在 [A2](appendices/a2-evidence-and-open-questions.md)，避免散落为多个 TODO 清单。

## 10. 开发工作流接入

上传包采用 `AGENTS.md`、`Agent-init/`、`.agents/skills/`、`.codex/agents/`；Spec 阶段回传后由 Director 审阅，再发送 implementation brief，不采用 Claude 文件锁挂起流程。[W1](../research/prior-art-prb/sources.md#w1)

本次是 **Major 的架构对齐／成书阶段**，不是普通 Fast 文案修补。交付 Director Plan、设计与证据索引；**尚未初始化 OpenSpec，也不伪造已批准 change 或 live capability spec**。首次行为实现前必须完成工具初始化和 artifact gate。工作流安装方案在 M08；填好的 Overlay 是对接草稿，不代表安装完成。

本会话没有实际启动独立 Researcher、Validation 或 Ops 子代理；引用这些角色只描述未来开发分工，不冒充已执行的审查。

## 11. 安全、许可与部署边界

首版仅 loopback、一个 principal、显式 API key；不启用公网暴露、cookie 上传门户、自动登录、验证码处理或账号切换。日志不得默认包含正文与凭证；离线测试不读个人浏览器 profile。上游权限、使用条款和可访问资格在真实探测前确认；**自建 gateway 不等于官方 API，也不保证与账号订阅权益等价**。[O3](../research/prior-art-prb/sources.md#o3)

远端文件编辑的能力与普通文本生成分开：用户真实项目默认不接入；只允许显式授权的受控实验上下文。不能靠一句 prompt 宣称“只读执行”。

## 12. 封存清单与重开条件

| 封存项 | 重开必须具备 |
|---|---|
| 多账号／多租户／公网服务 | 明确新需求、许可审查、身份与数据隔离设计、独立威胁建模 |
| 通用多 provider 框架 | 第二个真实 provider 已出现，且重复机制经过测量 |
| 高并发／多个进程 | 上游额度与并发证据、资源锁设计、恢复测试和资源预算 |
| 自动远端清理或文件编辑 | 精确归属、可审计授权、副作用确认与失败恢复 |
| tools / Responses / Anthropic 兼容 | 可证明的协议映射、客户端样本和端到端合同 |
| 自动模型选择／降档／供应商 fallback | 用户明确授权及可观察路由证明；不得隐式启用 |
| 常驻巡检 agent / 自愈 agent | 确定性诊断确实不足，新增复杂度有证据支撑 |

封存接口只是设计边界，不应先建空插件、空数据库或无调用者框架。

## 13. 本次交付与阅读顺序

首读 §01、§03、§07，再读 **M03 生命周期**与 **M04 上下文**；这两个边界成立后，才有可靠的 API 与流。API 使用者接着读 M01、M05；实现者读 M02、M06、M07；Director 读 M08、A2、A3 与 [阶段计划](../plans/active/architecture-and-protocol-readiness-prb.md)。

交付验证只覆盖文档路径、锚点、结构、引用 ID、分发包与敏感模式检查；运行时测试、真实账号调用、上游协议验证和客户端联调均未执行。详见 [验证报告](../validation/architecture-book-prb-report.md)。
