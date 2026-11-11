import { readFileSync } from "node:fs";
import { expect, test } from "vitest";

test("Node 版本符合 mise.toml 的版本 line", () => {
  const line = /^node\s*=\s*"(.+)"/m.exec(
    readFileSync("{{ROOT}}/mise.toml", "utf8"),
  )?.[1];
  const actual = process.versions.node;
  expect(actual === line || actual.startsWith(`${line}.`)).toBe(true);
});
