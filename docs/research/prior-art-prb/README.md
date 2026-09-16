# prism2api 参考研究与来源包

**Session 标签：** `prb`。这是本次文档分发的命名标签，不是已经在远端登记的 Codex session。

**Question：** 如何借鉴用户的开发工作流、ValueHermes 架构方法与成熟网页转 API 项目，设计一个小而可信的 Prism gateway？

**Decision Needed：** 确定职责边界、提交／上下文／流式／恢复合同，以及哪些能力必须等待真实协议证据。

**Current State Checked：** 当前会话的 GitHub 读取返回目标仓库为空；写入 README 的尝试返回 403。交付包不含运行时实现。ValueHermes 仅按指定文档／片段参考，不作运行现状审计。

**Findings：** 用户 GPT 工作流明确采用 Codex 原生目录与显式派工；ValueHermes 适合借鉴文档形态、证据纪律与合同所有权；WebAI-to-API 最接近浏览器运行边界，Gemini-API 适合客户端抽象参考。Prism 真实协议、权限和能力仍无证据。

**Recommendation：** 先用一次授权低风险任务验证提交、上下文和完成，选一种 transport；之后做共享核心与原生 run，再开放有限兼容层。不先构建多账号、多 provider 或完整管理平台。

**Confidence：** 对已读文档的形态判断有来源；对本项目架构是设计推导；对真实 Prism 能力全部保持 unknown。

**Source of Truth：** 研究不批准实现。长期设计见[架构总书](../../architecture/00-master-design-book.md)，阶段路线见[Director Plan](../../plans/active/architecture-and-protocol-readiness-prb.md)。

阅读：[sources.md](sources.md)；[comparison-matrix.md](comparison-matrix.md)。没有复制第三方源码、完整私有架构书或上传 ZIP 的 `.git` 历史。
