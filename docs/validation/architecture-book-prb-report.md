# 架构书文档验证报告

**Session label：** prb（交付命名；未冒充已登记的 Codex 并行 session）。  
**版本／日期：** v0.1.0 · 2026-09-16。  
**Scope：** 本地架构文档结构、交叉引用及分发卫生。  
**Status：** 文档结构自查 PASS（实际退出码 0）；运行时能力未验证。

## 1. 可复验命令

在交付目录执行，或给脚本绝对路径：

```bash
python docs/validation/check_book.py
```

脚本仅用 Python 标准库，不访问网络、不读取用户浏览器或凭证、不运行 Prism 请求。它不是生产测试，也不是完整的 Markdown 渲染器、秘密扫描器或独立架构审计。

## 2. 实际输出

```json
{
  "scope": "architecture-document-structure-only",
  "status": "pass",
  "markdown_files": 23,
  "module_documents": 8,
  "appendix_documents": 5,
  "local_links_checked": 93,
  "balanced_fenced_blocks": 11,
  "canonical_ids_checked": {
    "I": 12,
    "U": 15,
    "T": 52,
    "D": 14
  },
  "source_anchors_checked": 13,
  "network_requests": 0,
  "runtime_tests_executed": false,
  "independent_architecture_audit": false,
  "errors": []
}
```

## 3. 本次检查的边界

本次自查覆盖必要文档、8 个模块、5 个附录、本地链接与锚点、闭合代码围栏、12 条不变量、15 项未决问题、52 个计划验收场景、14 项 proposed 决议，以及来源登记和少量明显敏感模式。文件中的运行时实现路径均为规划，不以它们不存在判本文验证失败。

没有执行生产单元测试、offline core/replay、真实账号调用、客户端联调、OpenSpec validate/archive、工作流安装或独立 Validation 子代理审计。A3 的 T01–T52 是待实现验收目标，不能写成 52 passed。没有观察到运行时 RED→GREEN；这次不需要为纯文档虚构 RED。

## 4. 分发核对

分发检查已执行：ZIP 共 27 个文件成员，CRC 检查通过；各成员与源文件逐字节一致，路径无越界，未混入输入源包或私有凭证。单页 HTML 的 139 处内部链接均可解析，231 个锚点无重名，无外部脚本／样式／字体依赖。最终压缩包重建后再次执行相同检查。

文档校验器的负向 smoke 也已执行：只在临时副本注入一个不存在的本地链接，校验器正确报告该链接并以退出码 1 结束；原始文档未被此测试修改。该检查验证文档工具的一条失败路径，不是产品运行时 RED→GREEN。

HTML 已完成静态结构与锚点检查，并使用本机 Chromium 离线渲染：抽查 1440×1080 桌面首页与 390×844 移动端 M03，均无整页横向溢出；截图已人工查看。此为两处版式抽查，不冒充全书逐页视觉审计。最初默认浏览器／file URL 方式未成功，后用系统 Chromium 的内存 HTML 渲染完成；没有为此访问 Prism。

包内 `MANIFEST.sha256` 列出除其自身之外全部入库文件的字节指纹。可在仓库根运行 `shasum -a 256 -c MANIFEST.sha256` 再核对本地文件。源 Markdown 才是后续修改位置；合订 Markdown 与单页 HTML 为生成阅读视图，不设立第二套架构真相。

## 5. 权限与后续事实归属

GitHub 文件写入返回 403，没有远端 commit、push、PR 或 merge。交付物为本地可入库文件包。未来实现证据进入真实 OpenSpec change 的 verification，而不是在本报告中延伸成运行时事实账本。
