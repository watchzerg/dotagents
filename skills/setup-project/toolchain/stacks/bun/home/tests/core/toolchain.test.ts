import { expect, test } from "bun:test";
import { readFileSync } from "node:fs";

test("Bun 版本符合 mise.toml 的版本 line", () => {
  const config = Bun.TOML.parse(readFileSync("{{ROOT}}/mise.toml", "utf8")) as {
    tools: { bun: string };
  };
  expect(Bun.version.startsWith(`${config.tools.bun}.`)).toBe(true);
});
