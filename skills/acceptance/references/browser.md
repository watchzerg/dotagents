# 浏览器观测

契约声明 web 界面时，用 harness 原生方案操作用户自己的 Chrome：最接近真实使用，复用已有登录态，能读 console 与 network。它操作的是真实浏览器与真实账号，所以：

- 只访问契约声明的地址，只在自己新建的标签页里操作；用户的其他标签页、账号与浏览器设置保持原样，不登出。
- 原生方案未连接是硬阻塞：提示用户打开 Chrome 并连接，不换成没有登录态的独立浏览器。

## 步骤

1. **确认连接**（阶段 0）。
2. **新建专用标签页**（阶段 2）：记下标识，告知用户运行期间别操作它；需要多窗口的行为按需再建并记录。
3. **取证**（阶段 3）：每项读该标签页的页面文本或截图、console 错误与失败的 network 请求。
4. **收尾**（阶段 5）：关闭自己开的全部标签页。

## 各 harness 的做法

| harness | 方案 | 确认连接 | 新建与关闭标签页 | 取证 |
| --- | --- | --- | --- | --- |
| Claude Code | Claude in Chrome 扩展（`mcp__claude-in-chrome__*`） | `tabs_context_mcp` | `tabs_create_mcp`、`tabs_close_mcp` | `get_page_text` 或 `computer` 截图、`read_console_messages`、`read_network_requests` |
| 有其他原生方案的 harness | 该 harness 连接用户 Chrome 的原生方案 | 按其文档完成上面四步 | | |
| 没有原生方案的 harness | Playwright 官方 skill + CLI | 确认 CLI 可执行 | 由 CLI 打开页面 | CLI 的页面文本、截图、console 与 network 输出 |

Claude Code 中这些工具延迟加载时，先用 ToolSearch 一次加载全部所需工具。

走 Playwright CLI 时没有用户登录态，登录方式只按契约声明；契约没写是硬阻塞。
