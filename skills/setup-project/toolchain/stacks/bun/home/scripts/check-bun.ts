import { readFileSync } from "node:fs";

const config = Bun.TOML.parse(readFileSync("{{ROOT}}/mise.toml", "utf8")) as {
  tools: { bun: string };
};
if (!Bun.version.startsWith(`${config.tools.bun}.`)) {
  console.error("错误：Bun 版本 line 不匹配，请运行 mise install 后重试。");
  process.exit(1);
}
