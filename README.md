# prism2api

**Prism 网页工作区 → 可验证的 Python 客户端与本地 API。**

当前交付：**架构书 v0.1.0 / 完整评审初稿 / 2026-09-16**。

这不是已可运行的软件发行版。本包没有实现 Prism transport，没有登录或调用用户账号，没有验证模型身份、额度、上游协议或客户端兼容性，也没有启用开发工作流。

## 阅读入口

| 入口 | 内容 |
|---|---|
| [架构总设计书](docs/architecture/00-master-design-book.md) | 北极星、范围、不变量、构件关系与阅读路由 |
| [模块细稿](docs/architecture/appendices/a4-contract-index.md) | 8 个模块的字段、生命周期、失败与验收合同索引 |
| [参考项目借鉴矩阵](docs/architecture/appendices/a1-borrow-matrix.md) | ValueHermes 与五个 xx2api 项目的继承／改造／放弃 |
| [证据与待验证事项](docs/architecture/appendices/a2-evidence-and-open-questions.md) | 事实、设计、假设分离；协议未知项与开闸要求 |
| [首阶段 Director Plan](docs/plans/active/architecture-and-protocol-readiness-prb.md) | 已交付文档与尚未批准的实施切片 |
| [项目 Overlay](Agent-init/PROJECT_OVERLAY.md) | 对接上传的 Codex/GPT 工作流；不虚构已安装工具 |
| [来源登记](docs/research/prior-art-prb/sources.md) | 上传包 SHA-256、ValueHermes 固定提交、同行资料及阅读范围 |
| [交付说明](DELIVERY.md) | 文件范围、GitHub 写入状态、验证边界与入库方式 |

## 当前阶段边界

用户已授权创建架构书。**本书提出的实现选择仍待评审；架构成书不等于生产实现开闸。**

仓库目标：`Robinfxa/prism2api`。连接器写入返回 `403 Resource not accessible by integration`，本包未写入远端、未创建 PR、未合并 main。

项目是独立 gateway，不是 ValueHermes 插件、投研系统或统一多供应商平台。Hermes/Oak/ValueHermes 只是后续候选调用方。

本文档未为仓库选择软件许可证；复用第三方实现前应检查具体代码和依赖的许可证。访问上游服务须遵守适用授权和条款，技术可行性不代表获得许可。
