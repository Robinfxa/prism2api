# 架构书交付说明

**交付日：** 2026-09-16。**版本：** v0.1.0。**性质：** 完整评审初稿，而不是已实现软件或已批准规格。

## 1. 交付范围

总书 1 份、模块细稿 8 份、附录 5 份；另有领域词汇、研究来源／比较索引、Director Plan、按上传 GPT 包填写的 Overlay、文档验证工具与报告、README 及保护性 .gitignore。

文档不含 Prism 内部端点猜测、实际 Cookie、用户论文或从 ValueHermes 私有资料整篇复制的内容。引用私有仓库的链接需要相应访问权限；这里仅提炼设计方法，没有公开其源码。

## 2. GitHub 交付状态

目标仓库为 `Robinfxa/prism2api`。此前连接器读目录返回空仓库；创建 README 的实际写入返回 `403 Resource not accessible by integration`。**没有成功 commit、push、PR 或 merge 的证据。**

因此本次交付的是按目标仓库目录组织的本地文件包，不是已写入远端的分支。未用替代认证、强推或其他路径绕过连接器权限。

## 3. 入库方式

本包顶层目录中的内容对应仓库根目录。导入前先读取仓库的当前状态，查看是否已有 README、Overlay 或 docs；对已有同名文件做 diff，不直接覆盖。建议放在独立文档分支，明确路径暂存，审查后再由用户决定是否合并 main。

不要将本次输入 `dev-flow-GPT.zip` 中的 `.git`、个人配置或全部历史复制入新项目。工作流安装是后续独立步骤；本包只提供项目 Overlay。上传内核的 init 脚本会覆盖某些目标 skills 和内核文档，必须先审查。

## 4. 可直接交给下一轮开发者的接手指令

> 读取 `docs/architecture/00-master-design-book.md`、M03、M04、A2/A5 与 active Director Plan；以 `Agent-init/PROJECT_OVERLAY.md` 为项目入口。先核本地仓库和工具现状，不假设已有 runtime、OpenSpec 或已通过 baseline。当前只批准了架构书创建；所有技术决议标 proposed。若用户另行批准实施，先完成工作流／工具准备和经授权的 P0 协议证据，再按阶段 plan 创建真实 OpenSpec change。不要编造 Prism 端点或模型路由，不直接写 live specs，不把 unknown 当能力，不自动合并 main。

## 5. 验证边界

文档验证工具可以重跑：

```bash
python docs/validation/check_book.py
```

它检查本地路径、内部链接／锚点、必要章节、来源锚点、验收编号与明显敏感模式，不执行网络或产品测试。报告中所有 runtime／live／客户端测试均明确未执行。结构通过不等于架构已独立审计或行为已正确实现。
