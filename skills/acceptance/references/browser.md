# 浏览器观测

契约声明 web 界面时读本文。SKILL.md 只写能力要求与操作边界，本文给各 harness 的具体做法。

## 要做的事

1. **确认连接**：阶段 0 确认能操作用户自己的 Chrome；不能时是硬阻塞，提示用户打开 Chrome 并连接，不回退到无登录态的独立浏览器。
2. **新建专用标签页**：阶段 2 新建一个标签页，记下其标识，全程只在它（及按需新建并记录的标签页）里操作。
3. **取证**：每项读该标签页的页面文本或截图、console 错误与失败的 network 请求。
4. **收尾**：阶段 5 结束时关闭自己开的标签页。

## 各 harness 的做法

| harness | 方案 | 确认连接 | 新建与关闭标签页 | 取证 |
| --- | --- | --- | --- | --- |
| Claude Code | Claude in Chrome 扩展（`mcp__claude-in-chrome__*`）；不用桌面 app 内置浏览器 | `tabs_context_mcp` | `tabs_create_mcp`、`tabs_close_mcp` | `get_page_text` 或 `computer` 截图、`read_console_messages`、`read_network_requests` |
| 有其他原生方案的 harness | 该 harness 连接用户 Chrome 的原生方案 | 按其文档完成上面四件事 | | |
| 没有原生方案的 harness | Playwright 官方 skill + CLI | 确认 Playwright CLI 可执行 | 由 CLI 打开页面 | CLI 的页面文本、截图、console 与 network 输出 |

Claude Code 中工具是延迟加载时，先用 ToolSearch 一次加载全部所需工具，不逐个加载。

没有原生方案时没有用户登录态，登录方式只按契约声明，契约没写就是硬阻塞。任何情况都不用 Playwright MCP。
