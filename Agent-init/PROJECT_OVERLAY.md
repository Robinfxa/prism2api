# 项目 Overlay — prism2api

> v0.1.0 / draft / 2026-09-16。依据用户上传 `dev-flow-GPT.zip` 的 0–12 节形态填写。当前为文档接入草稿；完整内核、skills、custom agents、hooks 和 OpenSpec 尚未安装。
>
> **阶段开关：架构评审。** 本次授权创建文档，不自动进入真实账号探测或生产实现。运行时能力一律未验证。每节区分现有文档与计划路径。

## 0. 项目身份

- 项目：`prism2api`；仓库目标 `Robinfxa/prism2api`。
- 产品入口：尚无可运行 CLI/API。
- 语言：当前中文 Markdown；拟议运行时 Python 3.12，未建立依赖锁文件。
- codegraph：未启用，不宣称已索引；当前按精确文档路径查找。
- 文档状态入口：[总书](../docs/architecture/00-master-design-book.md)。

## 1. 入口与知识地图

| 面 | 真实文档／建议代码位置 | 状态 |
|---|---|---|
| 设计 | `docs/architecture/00-master-design-book.md`＋modules＋appendices | 本包已提供 |
| 证据 | `docs/research/prior-art-prb/sources.md` | 已登记读取范围 |
| 阶段路线 | `docs/plans/active/architecture-and-protocol-readiness-prb.md` | 待评审／实施待批 |
| 本次文档验证 | `docs/validation/check_book.py` | 本包文档工具，非产品实现 |
| API／SDK | 拟议 `src/prism2api/api/`、`client.py` | 尚不存在 |
| 生成与上下文 | 拟议 `src/prism2api/runtime/` | 尚不存在 |
| 上游适配／传输 | 拟议 `src/prism2api/provider/`、`transport/` | 尚不存在 |
| 状态与证据 | 拟议 `src/prism2api/storage/` | 尚不存在 |

## 2. 设计圣经

[总书](../docs/architecture/00-master-design-book.md) 管全局；[A4](../docs/architecture/appendices/a4-contract-index.md) 路由到字段 owner。核心读序：总书 §03/§07 → M03/M04 → 本切片模块。来源／未决查 A1/A2，未来 change 不自行扩大事实或写权。

所有章节当前 draft，未获用户终审。更新长期意图，不把任务日志与原始测试输出塞进架构正文。重大取舍见 A5；ADR 按需创建。

## 3. 测试体系

当前唯一实际可运行的项目级验证是文档工具：

```bash
python docs/validation/check_book.py
```

产品 tier-1／tier-2：**尚未建立**，passed-count unknown。未来候选命令及 offline/live 边界见 M08，不将其复制成已执行基线。DL_PY、DL_TEST_CMD、DL_SUMMARY_RE、DL_PASS_RE、DL_FAIL_RE、DL_REMOTE、DL_BRANCH 必须在真实初始化后按项目环境设置；当前不生成虚假的 driver.env。

敏感／ambient 边界至少覆盖 `.multi-subflow/`、reference clones、凭证、浏览器 profile、原始 HAR、真实账号材料和运行数据库。offline 测试必须主动阻断网络，不能依赖没有配置凭证的偶然失败。

passed-count gate 只作卫生检查，真实 byte-identical 另需 bytes／digest 证据；这是本项目补强，详见 M08 §6。

## 4. Spec 工具

拟用 OpenSpec，但当前未初始化。首次行为实现前完成工具版本与 artifact gate。当前只有设计与阶段计划，没有 live capability spec。

未来 change 路径 `openspec/changes/<slug>-<sid>/`；capability spec `openspec/specs/**` 只经 archive 合并，禁止直接编辑。纯文档校验不伪造 OpenSpec validate 成功。

## 5. 项目铁律

不变量正文只在总书 §03（I01–I12），本节为必要索引：

- 未证实的端点／模型／额度不得编造，M02/A2。
- 上下文隔离与精确 owner，M04。
- submit intent 后 uncertain 不重发，M03。
- 真终态＋完整结果＋持久化后才成功，M05/M06。
- 不支持的角色／tools／参数明确拒绝，M01。
- 只清理精确归属资源，不碰日用浏览器／真实论文，M04/M07。
- 凭证、原始流量和真实输入不进仓库，M06/M07。
- 设计通过、离线通过、实测通过与客户端合格分开，M08。

所有数值预算待配置与实测标定；单账号／单进程／单生成 worker 是本书拟议结构选择，不是上游限制数字。

## 6. 角色写入边界

当前仅文档态：允许 `README.md`、`DELIVERY.md`、`docs/**`、本 Overlay 与保护性 `.gitignore`。文档检查脚本属于验证工具，不含 runtime 实现。

未来 arc-imp 仅获批 change 的 artifacts、代码与测试；Researcher 只写 research；Validation 只写证据与有界 audit；Ops 执行获批 git；Director 决策与阶段计划。当前禁止擅写 `src/`、runtime tests、真实 `.env`、credentials、browser profile 与 `openspec/specs/`。

## 7. git / Ops 约束

当前 GitHub 写操作实际返回 403，未 push、未建 PR。后续先看实际树再导入文档，不覆盖用户新增内容。

建议独立文档分支 `docs/architecture-v0.1`；merge main 需用户明确指令。不 `git add -A`、不 force push、不 `--no-verify`，只暂存本次允许路径。提交归属按本机工作流配置，本包不伪造作者或 Co-Authored-By。

## 8. 延伸研究

[来源包](../docs/research/prior-art-prb/README.md) 为当前入口；本包没有 clone 同行源码到 reference。修改模块时按 source ID 与 tag 精读，不能把整片参考资料设为每次必读。

[A1](../docs/architecture/appendices/a1-borrow-matrix.md) 为唯一采纳矩阵；实际代码状态均未 borrow。

## 9. 北极星

可验证、可隔离、可恢复的 Prism 接入；本地优先但明确云端外发；可信失败优于伪成功。不是免费无限量模型获取器，不做多账号轮换或限流绕过。

## 10. 角色模型分配

尚未为本项目配置具体模型标识。上传模板中的 opus/sonnet 是模板项，不能当作当前 GPT 运行时有效值；也不从聊天记忆自动写入新的模型组合。首次安装时沿用用户明确有效的本机配置，本书不更改模型矩阵。

## 11. 状态外置

后续进入真实仓库时看 `git status`、`git log`、active plan、`openspec list`（工具存在时），不把本包描述当仓库实时事实。未初始化工具返回缺失不能解释为“零 active changes 已核实”。

本次证据：[文档验证报告](../docs/validation/architecture-book-prb-report.md)。MEMORY 尚未创建，未来只留索引／教训。文档包标签 prb 不等于已注册远端 sid。

## 12. Codex 特化 / Hooks

目标形态依据 GPT 包：`AGENTS.md`、`Agent-init/`、`.agents/skills/`、`.codex/agents/`。本次仅提供项目 Overlay，不声称这些入口已安装或能在本会话运行。

hooks 不启用；以后只做确定性 guardrail，不替代 review、OpenSpec 或运行证据。GPT 路线不使用旧 Claude 文件锁／母体协议。安装脚本的覆盖行为需先审 diff；本次不执行安装。
