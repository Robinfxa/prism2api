# A5 决议草案与来源差异登记

> v0.1.0 · draft。用户已批准“创建架构书”，**没有逐项批准下面的技术取舍**。本表把本书建议与来源原文分开，防止作者推断被后来者当作用户裁决。

## 1. 本次授权与未授权

已授权：依据上传工作流、ValueHermes 架构方法和已研究同行项目创建 prism2api 架构文档。

未执行／未获额外批准：真实账号协议探测、生产实现、安装 hooks、创建多账号能力、把文件副作用开放给真实论文、合并 main。GitHub 文档写入曾尝试但返回 403，因此远端交付没有完成。

## 2. 设计决议草案

| ID | 建议取舍 | 理由 | 重开条件 | 状态 |
|---|---|---|---|---|
| D01 | 独立 Python 项目，不 fork 大网关 | 上游语义未知，避免带入无关复杂度 | 原型证明成熟底座显著降低成本 | proposed |
| D02 | 单账号、单进程、单生成 worker | 降低归属与恢复复杂度 | 并发需求、额度证据与隔离设计齐全 | proposed |
| D03 | 原生 run 语义为核心，Chat 为投影 | 不确定状态与上下文不能被兼容层抹掉 | 有更小且无语义损失的表达 | proposed |
| D04 | 协议证据决定 transport，先一种 | 避免“HTTP＋浏览器＋DOM”一次全做 | 实际维护／能力证据支持第二路线 | proposed |
| D05 | intent 后 unknown 不重发 | 避免重复生成与文件副作用 | 上游证明幂等且有明确合同 | proposed |
| D06 | 单 SQLite＋结果文件 | 够用且易恢复，不搬 ValueHermes 三库 | 有已测的规模／隔离需求 | proposed |
| D07 | 独立请求必须验证工作区层隔离 | Prism 是项目感知工作区 | 供应商有等价、可证明的无状态执行面 | proposed |
| D08 | read-only 未证明就不宣传 | prompt 不是权限机制 | 上游强制边界与实测齐全 | proposed |
| D09 | 非流式先行，真实流后置 | 避免把 DOM 改写伪装成标准 delta | 可靠 append-only／终态证据 | proposed |
| D10 | 模型 alias 与 backend identity 分开 | 防止 UI／自述冒充证明 | 可靠路由回执存在 | proposed |
| D11 | 只填 Overlay，不安装完整工作流 | 当前任务是成书 | 用户启动实现并审查安装 diff | proposed |
| D12 | 初始模型角色分配不硬编码 | 上传模板保留旧占位，不能从记忆猜可用值 | 用户／本地有效配置明确 | proposed |
| D13 | 真 byte-identical 另有字节证据 | passed-count 相同不证明行为相同 | 仅文档无需运行行为差分 | proposed |
| D14 | 暂不选软件许可证 | 涉及源码引用和依赖，需单独决定 | 用户确定分发方式与依赖 | proposed |

## 3. 来源差异与未静默修正

| 差异 | 来源实际内容 | 本书处理 |
|---|---|---|
| GPT 与 Claude 编排 | GPT 包为回传→review→新 implementation brief；旧散装 Claude 文档有文件锁与 code-reader | GPT 包作当前基线，旧机制不移植；未改原件 |
| 开工读序精简 | 上传 GPT 的 ms-start 仍列显式多文档读序 | 不把聊天中提到的精简版本当本包已落地；未擅改内核 |
| 模型分配占位 | GPT Overlay 模板 §10 仍有 opus/sonnet 等模板项 | 项目 Overlay 标尚未配置，不自动换成记忆中的模型组合 |
| passed-count | GPT workflow 用计数守护部分 byte-identical 场景 | 保留其规则说明，项目验收新增 bytes/行为检查 |
| 同行 rewrite | R1 文档讨论 rewrite 与后缀输出 | 本书只在前缀关系成立时允许追加；一般改写显式截断 |
| ValueHermes 架构复杂度 | 原书有三库、投研构件、分形 agent 层 | 只借方法并缩小；不是复制其产品架构 |
| “Prism” 同名 | ValueHermes 引用的 legacy Prism 是旧知识层 | 与 OpenAI Prism 明确区分，不拿旧模块作上游实现证据 |
| 产品介绍与实时权限 | 官方产品页说明工作区定位，不能证明本账号可用 | 真实资格与服务状态纳入 U12，不替用户推断 |

## 4. 裁决与更新方式

评审可逐 D 编号接受、调整或拒绝；接受后回填对应 owner 模块。难逆转决定在实现期按需形成 ADR，不为每个字段建一个 ADR。没有 user-approved 标记前，后续 worker 不得把 proposed 改写成“用户已定”。
