# 来源登记与阅读覆盖

> 检索／阅读日期：2026-09-16。表中“已读”描述本会话及紧接的前序研究实际可见内容；不代表完整源码审计或账号实测。未重新访问的资料按前序已取得结果标注，不冒充本轮复验。

## 0. 两条证据轴

**来源等级**：A = 用户提供的实际字节／官方一手页面／已取回的一手资料；B = 同行一手文档或局部元数据、未核源码；C = 历史／社区线索；D = 本书设计推导或待证假设。

**证明范围**单独记录：`document-content`、`repository-metadata`、`product-description`、`runtime-behavior`。A级文档也不能证明 runtime-behavior。本文没有 Prism runtime-behavior 的已验证来源。

<a id="w1"></a>
## W1 — 用户上传的 Codex/GPT 工作流

- 来源：当前会话附件 `dev-flow-GPT.zip`，内部根目录 `dev-flow-GPT/`。
- ZIP SHA-256：`c0548f97fdaa96d61751d9b94b47d74834e44dd2ec53564b87b35d80a1468278`。
- 等级：A / document-content；按实际文件读取，不执行安装脚本。
- 关键读取：`AGENTS.kernel.md`、`Agent-init/Documentation_System.md`、`Agent-init/Team_Roles.md`、`Agent-init/PROJECT_OVERLAY.template.md`、`Agent-init/Codex_Specialization.md`、`skills/ms-loop/SKILL.md`、`skills/ms-start/SKILL.md`、`skills/ms-init/init.sh`。
- 支持的判断：事实源分层；Fast/Normal/Major；Codex 路径；Spec 回传后 review；不依赖文件锁或母体；安装脚本的复制／覆盖行为。
- 未验证：这些 skills、角色和 hooks 在用户本机当前工具版本下是否可运行。本包未安装它们。
- 原包含 `.git`、macOS 噪音等非任务内容；仅提取所需文本阅读，未随交付包分发。

<a id="w2"></a>
## W2 — 前面散装上传的 Claude 工作流与 refact Overlay

- 来源：本会话 `Claude_Code_Specialization.md`、`Director_Workflow.md`、`Team_Roles.md`、`Documentation_System.md`、`PROJECT_OVERLAY.md` 等实际加载材料。
- 等级：A / document-content。
- 用途：识别旧 Claude `.claude/`、文件锁与 code-reader，以及 refact 的 ValueHermes 形态参考。
- 边界：当前 GPT 工作流优先；旧项目的 baseline、codegraph、路径、模型分配与“已定稿”状态不迁入新仓库。

<a id="v1"></a>
## V1 — ValueHermes 架构总书

- 仓库：`Robinfxa/ValueHermes`。
- 已取回 main 指向提交：`171a4cabd96a9f69af6242ff1f79e9eeffd5711d`，提交时间记录为 2026-09-05。
- 文件：`docs/architecture/00-master-design-book.md`，内容 blob SHA `e826e74a289cd7b30d45af872fe9a2928de689f6`（此前目录元数据）。
- 稳定参考：[固定提交中的总书](https://github.com/Robinfxa/ValueHermes/blob/171a4cabd96a9f69af6242ff1f79e9eeffd5711d/docs/architecture/00-master-design-book.md)。
- 等级：A / document-content；读取到总纲、成书契约、系统画像和构件／生命周期相关片段；长响应存在截断，未宣称全书逐章审计。
- 采用：总书＋modules＋appendices、愿景与事实分离、字段／规则单 owner、证据 manifest、本地优先、封存能力。
- 不采用：投研业务模块、三库拓扑、agent-first 产品定义和全套分形编排。这里的“定稿”属于 ValueHermes，不属于 prism2api。

<a id="v2"></a>
## V2 — ValueHermes 透明度与判断权模块

- 文件：[modules/14-transparency-and-judgment.md](https://github.com/Robinfxa/ValueHermes/blob/171a4cabd96a9f69af6242ff1f79e9eeffd5711d/docs/architecture/modules/14-transparency-and-judgment.md)。
- 等级：A / document-content；本轮读取开头与定位、判断权边界的可见片段，响应存在截断。
- 采用：规则集中定义、材料与控制权分开、不能靠自律代替验证。
- 不采用：任何金融判断公式、veto、票面或投研角色。旧文档里同名 Prism 是 legacy 知识层，不是本项目上游。

<a id="v3"></a>
## V3 — ValueHermes 双层评测模块

- 文件：[modules/13-two-tier-eval.md](https://github.com/Robinfxa/ValueHermes/blob/171a4cabd96a9f69af6242ff1f79e9eeffd5711d/docs/architecture/modules/13-two-tier-eval.md)。
- 等级：A / document-content；前序已取回定位、对象分型、确定性断言相关可见片段；未全文件审计。
- 采用：确定性合同与非确定性输出质量不能用同一验证代替。
- 不采用：投资领域 golden set、多裁判系统或已有通过计数。

<a id="r1"></a>
## R1 — Amm1rr/WebAI-to-API

- 仓库：[Amm1rr/WebAI-to-API](https://github.com/Amm1rr/WebAI-to-API)。
- 实际读取资料：[architecture.md](https://github.com/Amm1rr/WebAI-to-API/blob/master/docs/architecture.md)、[streaming-pipeline.md](https://github.com/Amm1rr/WebAI-to-API/blob/master/docs/specs/streaming-pipeline.md)、[concurrency-model.md](https://github.com/Amm1rr/WebAI-to-API/blob/master/docs/specs/concurrency-model.md)。
- 内容 SHA：architecture fetch 返回 `eaee459278625957f8a17a56ead21723dee56e8a`；concurrency fetch 返回 `6aa2eb60b50b3ee63af7c75ec409df023865eab0`。这些是内容 blob，不冒充仓库 commit。
- 等级：B / document-content 与 repository-metadata。架构／流式文档此前已读取，本轮追加读取 concurrency 的 1–115 行；没有账号实测或全仓 code audit。
- 采用：Provider/Adapter/Runtime、单 owner lease、条件释放、callbacks、有界队列、异常流不得伪 DONE。
- 限制：文档声称不是源码完整性保证；首版不照搬锁层级；非前缀 rewrite 的可表达性由本书独立收紧。
- 根级许可证元数据：MIT；具体源码／依赖采用前重新核验。

<a id="r2"></a>
## R2 — CJackHwang/AIstudioProxyAPI

- 仓库：[CJackHwang/AIstudioProxyAPI](https://github.com/CJackHwang/AIstudioProxyAPI)。
- 等级：B / repository-metadata；此前研究已取得元数据，并据 README 说明 API、browser 与 stream 分层。本轮未再次审计其源码。
- 观察：FastAPI、Playwright、Camoufox 的网页接入方案；`api_utils/`、`browser_utils/`、`stream/` 为之前研究中记录的阅读入口，采用前重新定位。
- 采用：浏览器操作与服务层解耦这一机制参考；不采用 Google DOM、凭证协议与多实例功能。
- 根级许可证元数据：AGPL-3.0。没有实测当前网页适配仍有效。

<a id="r3"></a>
## R3 — HanaokaYuzu/Gemini-API

- 仓库：[HanaokaYuzu/Gemini-API](https://github.com/HanaokaYuzu/Gemini-API)。
- 资料：[README.md](https://github.com/HanaokaYuzu/Gemini-API/blob/master/README.md)，前序实际取回 1–125 行，内容 SHA `a898725f665a48d1c584c23fbc50300b8e7ba9f4`。
- 等级：B / document-content 与 repository-metadata。
- 观察：异步 Python wrapper、流式、持久会话、多轮／续接章节和输出分类；这些是 README 能力描述，不是本会话验证结果。
- 采用：客户端抽象与会话边界；不采用任何 Gemini Cookie 名称、RPC 或 Gems 语义。
- 根级许可证元数据：AGPL-3.0。

<a id="r4"></a>
## R4 — chenyme/grok2api

- 仓库：[chenyme/grok2api](https://github.com/chenyme/grok2api)。
- 等级：B / repository-metadata；此前取得元数据：当前以 Go 为主、覆盖 Grok Web/Build/Console；本轮未审具体实现。
- 用途：较完整网关工程的后置参考，不把账号池／多协议功能当作本项目必需。
- 根级许可证元数据：MIT。错误、并发等具体实现需实施相关切片时再次读码。

<a id="r5"></a>
## R5 — lanqian528/chat2api

- 仓库：[lanqian528/chat2api](https://github.com/lanqian528/chat2api)。
- 等级：B（元数据）／C（作为历史实现启发）；前序取得 `pushed_at=2025-05-17`，不把近期 stars 更新时间当代码维护时间。
- 用途：ChatGPT 网页到 OpenAI 格式的历史分层参考；当前可用性未实测，旧模型和认证不能用于 Prism。
- 根级许可证元数据：MIT。本轮未重新 fetch 代码，不把历史说明当今天的 upstream 事实。

<a id="o1"></a>
## O1 — OpenAI Prism 官方产品说明

- 官方页面：[Prism](https://openai.com/prism/)，本轮通过 web 实际访问。
- 等级：A / product-description，非 runtime-behavior。
- 支持：Prism 为科研 LaTeX 工作区，具有项目感知的 AI 与编辑能力；页面列出不限项目／协作者等，不构成推理无限量或某模型档位承诺。
- 仅据此解释上下文与副作用风险。没有用发布时历史模型说明替代 2026-09-16 的当前路由；本账号资格、服务存续与具体 API 均待 P0 核实。

<a id="o2"></a>
## O2 — OpenAI Chat Completions API Reference

- 官方入口：[Chat API Reference](https://developers.openai.com/api/reference/resources/chat)。原访问入口 `platform.openai.com/docs/api-reference/chat/create` 重定向到该页。
- 等级：A / protocol-description；本轮核对 chat 消息、stream options 和 `[DONE]` 相关说明。
- 用途：本地兼容表示的参考，绝不证明 Prism 内部采用同一协议或支持所有参数。
- 本书自定义的原生 `/prism/v1/*` 不属于官方 API。

<a id="o3"></a>
## O3 — OpenAI Terms of Use（地区需区分）

- 非 EEA／瑞士／英国页面：[Terms of Use](https://openai.com/policies/row-terms-of-use/)，页面生效日期 2026-01-01；本轮实际访问。
- 原通用入口本轮呈现 Europe 版本，后跟随页面提供的地区链接核对非欧洲页面；没有把地区不同的条款混为一份。
- 等级：A / policy-text，非具体项目法律意见。
- 相关范围：个人服务中的程序化提取、反向工程、账号和绕过限制等条款。本文只提示核查适用授权，不判定特定账户／用法已经合规，不以本地运行或登录成功作为许可证明。

## 1. 未纳入承重依据

V2EX 帖子只作为前序研究动机；锚定回复未完整取得，不引用其具体模型／额度主张作设计事实。搜索出现的其他新闻不替代一手协议证据，也未用于断言产品今天一定关闭或一定可用。

本书状态机、submit journal、幂等、API 子集、资源预算和安全约束均为**D / 本书设计推导**；引用同行机制不代表其已实现同样的合同。

## 2. W1 已读文件的字节指纹

| 原包内相对路径 | 行数 | SHA-256 |
|---|---:|---|
| `AGENTS.kernel.md` | 24 | `e963b91921858a5fa72193f62189e0165ee5201216959ee0b5a2043a36b6b414` |
| `Agent-init/Documentation_System.md` | 138 | `5e3654b87ad4cf222af510fa12edfae2d6262d0234024bbc4fc77fc7fcf2c530` |
| `Agent-init/Team_Roles.md` | 86 | `99a38c3e1e86b49c4a446a94b219fe20fe9cc3f0b130ed93e30655bc3ab48b47` |
| `Agent-init/PROJECT_OVERLAY.template.md` | 99 | `099c2f0f256fc23bab22b4abe4fe3a52a43b2b13ddc84e0ef28d5ec342111305` |
| `Agent-init/Codex_Specialization.md` | 103 | `69ef4a5f6e876944e14e38ca49d387a257edc87b51579f5138fd97a30b991c23` |
| `skills/ms-loop/SKILL.md` | 181 | `25221267347ca9ecddc586bd45f92cde4b552ba3e337b85cb41667a91023a5f1` |
| `skills/ms-start/SKILL.md` | 59 | `7ffdd2960276ab01da99fb071b00831f10b421e1ac7b6f1d5690925cfa023a58` |
| `skills/ms-init/init.sh` | 168 | `71881e1b929086afb6bcb52c86b78ce7abcdb592f7c0c950531558159718aee7` |
