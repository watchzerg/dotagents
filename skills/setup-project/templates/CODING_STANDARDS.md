# 编码标准

code-review 按本文评审 diff。只写工具查不出的判断类标准；可机械判定的规则进 lint、typecheck 或测试，不在此重复。动手前的流程约束在 [AGENTS.md](AGENTS.md)，测试专项规则在 [docs/agents/testing.md](docs/agents/testing.md)。

## 通用

- 改动涉及用户可见失败、数据完整性、资源清理或凭据时，diff 必须包含对应处理，不留给调用方或下一次迭代。
- 同一规则只有一处实现，调用方消费而不复制。
- 新抽象必须比直接实现更简单；为未来需求预留的参数、hook 和层应删除。
- 命名使用 [GLOSSARY.md](GLOSSARY.md) 的术语，不引入术语表明确避免的同义词。
- diff 改变了模块页描述的行为、接口或代码位置，或让新行为首次被测试覆盖，却没有同步或新建对应模块页（规则见 [docs/agents/documentation.md](docs/agents/documentation.md#随交付同步)），视为交付不完整；判断依据是模块页正文与 diff 后的代码是否仍一致，不以"改动很小"豁免。代码移动、新增或删除时模块页的 `covers` 同步改；`just docs-affected` 标出的未修改页可作核对起点。
- 新增或移动的测试归属正确：core 不启动真实服务、不占固定端口或桌面；full 已放入所属 stack 的 full 层位置并被 `gate-full` 收录（位置见 [docs/development/test-layers.md](docs/development/test-layers.md)）。分层标准见 [docs/agents/testing.md](docs/agents/testing.md#分层)。

## 项目特定

随 retro 逐条追加；每条写清规则与判断依据。超过约 1000 行时拆到 `docs/` 并在此留导航指针。
