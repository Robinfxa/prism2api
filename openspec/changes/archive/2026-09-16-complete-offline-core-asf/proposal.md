# Complete offline core before local Prism integration

## Why

用户要求直接完成两轮审计暴露的离线核心缺口，让本机 Gemini 只承担真实登录、协议取证与 transport 集成。基线为 `59aad2f`。该需求明确扩大上一轮只读审核为代码修复授权，不包含真实账号自动调用。

## What Changes

保留现有模块并修复终态、冻结请求、身份隔离、意图账、回执、只读恢复、单实例、队列 worker、SDK/HTTP 和安装入口；默认未配置 fail-closed，mock 显式选择。新增回归测试、安装元数据和接手指南。

## Impact

改动 src、tests、pyproject、README、Overlay、保护性 gitignore 与本 change／验证文档。数据库仅加列／加表，不删除旧数据；旧活跃但无冻结输入记录不会被重新提交。真实 transport、SSE/tools、多账号和远端清理不在本次范围。

## Authorization and status

Code implementation approved by the user's explicit instruction. Local implementation and deterministic verification complete; upstream live proof, macOS/Python 3.12 matrix and OpenSpec CLI validation/archive remain separate gates. Remote write attempt returned 403; no remote branch/PR/commit exists from this delivery.
