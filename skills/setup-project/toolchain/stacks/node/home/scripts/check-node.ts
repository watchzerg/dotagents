import { readFileSync } from "node:fs";

const line = /^node\s*=\s*"(.+)"/m.exec(
  readFileSync("{{ROOT}}/mise.toml", "utf8"),
)?.[1];
const actual = process.versions.node;
if (actual !== line && !actual.startsWith(`${line}.`)) {
  console.error("错误：Node 版本 line 不匹配，请运行 mise install 后重试。");
  process.exit(1);
}
