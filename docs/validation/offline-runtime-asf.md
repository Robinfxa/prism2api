# 离线核心修复验证报告 · 0.1.1

日期：2026-09-16。GitHub 基线：`59aad2f182232be41577a9e29adb7fe35d148776`。本文件描述交付补丁，不代表 main 已更新。

## 范围和来源

经 GitHub connector 读取最新 main 与原始文件。21 份基线代码／测试文件（14 生产＋7 测试）逐一匹配 Git blob SHA；README、Overlay、gitignore 另行与已读取的当前 blob 核对。环境没有 GitHub 网络下载能力，采用已核对的文本重建；没有把失败的 git clone 说成成功 clone。

用户授权直接完成核心修复，Gemini 只做本机真实协议与集成。保留既有模块，新增4个生产文件，现18份生产 Python。未调用真实 Prism、未使用用户 Cookie、未更改用户本机。GitHub `create_branch` 返回403，未创建远端分支、PR或提交。

## 已交付行为

1. 全部已观察终态、归属与正文的一致性检查；错任务／冲突／缺结局不成功；合法空输出保留；未知模型与 token 用量不编造。
2. 原始输入、上下文版本、账号、配置、能力快照原子冻结；完整 fingerprint 与并发幂等；执行参数不可替换已接受输入；缓存丢失410而不是重新生成。
3. 资源操作及提交意图先落账；回执独立持久化；保存回执之后再验证 context；失联 uncertain 跨重启阻断新生成。
4. 精确、只读核对已有任务，不提交／建项目／自动发送取消；原账号与已绑定工作区必须相符。queued 取消无上游副作用；cancel receipt 不是成功确认。
5. SDK/HTTP 共用 OS 锁、SQLite writer 与一个 generation worker；关闭期间不提前释放锁；数据库失败提交显式回滚；同步 FULL 与文件fsync。
6. 严格 API 请求边界、跨主体权限、Origin/Host/本地APIkey、分块正文预算；响应错误不回显秘密输入。默认 unconfigured，mock 必须显式选择和标识。
7. 原生提交→后台worker→结果闭环；daemon SDK 经本机HTTP工作且不创建第二个本地 writer；CLI 和可构建 wheel。

## 实际执行证据

完整原始日志在交付包 `evidence/`，不是由摘要倒推测试结果。

| 集合／命令 | 实际结果 | 日志 |
|---|---|---|
| 未修改基线原19测试 | 19 passed | baseline.log / baseline.xml |
| 未修改基线，两轮审计原43测试 | 22 failed, 21 passed | red-audits.log / red-audits.xml |
| 初步修复后，原19＋审计43 | 62 passed | first-green.log / first-green.xml |
| 初步新增运行时测试 | 34 passed | readiness-first.log |
| 再审5项：COMMIT失败、旧owner、账号scope、队列年龄、活动期恢复扫描 | 5 failed，修后进入最终通过集 | red-final-boundaries.log |
| 再审2项：回执不能被后续验证回滚、close幂等 | 2 failed，修后进入最终通过集 | red-receipt-and-close.log |
| 源码最终 `python -m pytest -q` | **103 passed**，4.11s | final-tests.log / final-tests.xml |
| 源码重复全量 | **103 passed**，4.02s | repeat-tests.log |
| 独立目录、已安装wheel的全量测试 | **103 passed**，3.55s | installed-tests.log / installed-tests.xml |
| `pip wheel . --no-build-isolation --no-deps --no-index` | 成功构建0.1.1 | build-wheel.log |
| wheel CLI `smoke --mock` | 明确合成正文，model/usage null | wheel-cli-smoke.log |
| 18份 wheel 生产源码与交付源码逐字节比较 | 全部一致 | artifact-static-checks.log |
| Python3.12 grammar parse | 通过，不等于实际Python3.12执行 | artifact-static-checks.log |

最终103=原19＋审计43＋新增41。原19保留原断言；fixtures 因显式mock和真实lifespan调整。原跨主体取消反例用真实 generation mutex 固定排队竞态，在释放前断言状态／cancel_intent未变，不屏蔽权限错误。没有声称103等于整本T01–T52产品验收。

网络守卫默认封锁连接与外部DNS、清除 ambient key；只有 loopback 测试允许真实本机 HTTP。进程崩溃测试真正执行子进程 `_exit(37)`，记录提交意图与一次dispatch后重启检查不重发。模拟 transport 只在外部边界，不 mock 核心归一器、状态机或 Journal。

前43审计以及最后7边界有真实RED→GREEN证据；其余新增34是写完后执行的行为测试，未宣称逐条观察RED。并未跑覆盖率或真实LLM评测。

## 安装验证的准确范围

实际环境 Linux/Python3.13.5；pytest9.0.2、FastAPI0.128.2、Pydantic2.13.4、httpx0.28.1、Uvicorn0.48.0，完整版本见 environment.json。

wheel 安装到单独 venv，并从没有 src 树的目录运行全部103测试。该 venv 起初无法看到宿主的预装依赖（原始失败日志保留），随后通过 `.pth` 引用已有依赖目录；`prism2api` 本身明确来自新安装wheel的 site-packages。**这验证了打包、安装及脱离源码路径后的行为，不是全新机器联网解析全部依赖的验证。** 没有重新下载依赖，不伪造依赖锁文件。

## 明确保留的边界

- 未实现／验证真实 Prism 登录、HTTP wire schema、字段、模型、额度、隔离与取消／查询能力；由本机 Gemini 根据真实证据对接。
- macOS、Windows、Python3.12未执行；目标 POSIX，Windows锁当前明确不支持。Python3.12仅语法解析检查。
- 不提供完整SSE、通用tools、多轮Chat Completions、多模态、多账号、自动远端清理、缺句柄人工解闸UI或GC；`idempotency_tombstone_days`尚无自动清理实现。
- 网络阻塞硬超时必须由具体transport实现。线程不能强杀任意I/O；安全停机失败时保留锁，防止第二writer，不以“运行正常”隐瞒。
- OpenSpec CLI不在环境中，**未执行 strict validate 或 archive**。新增change的格式与链接作本地检查；live specs与历史archive未手改。
- 初次本机验证使用仓库外新scratch home，避免混入旧模拟状态；不允许通过清空尚有uncertain任务的home来规避恢复闸门。

## 来源与状态分层

- 本次事实：源文件／测试／原始日志／文件SHA。
- 长期设计：`docs/architecture/`，不将尚未实现的SSE等写成已完成。
- 本次变化：`openspec/changes/complete-offline-core-asf/`；该change保持待本地CLI验证与归档。
- 方法参考：FastAPI lifespan（https://fastapi.tiangolo.com/advanced/events/）、lifespan testing（https://fastapi.tiangolo.com/advanced/testing-events/）、SQLite synchronous与WAL（https://www.sqlite.org/pragma.html）。这些参考不证明本地产品测试通过，测试结论只来自实际日志。
