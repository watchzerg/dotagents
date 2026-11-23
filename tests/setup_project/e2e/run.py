"""在临时项目上用 headless Claude Code 真实执行 /setup-project，并对产物做检查。

用法（仓库根目录）：

    uv run python -m tests.setup_project.e2e.run [case ...] [--out DIR] [--model opus]
                                                  [--build-only] [--rerun] [--review] [--jobs N]

不传用例名时运行全部。每个用例在 `<out>/<case>/` 下留下 `<case>/`（目标项目，目录名即项目名）、
`transcript.jsonl`、`report.md`（agent 写的汇总报告）、`checks.json`、`summary.md`，
`--review` 时还有 `review.md`；`<out>/summary.md` 汇总所有用例。退出码：全部用例硬检查通过为 0，否则为 1。
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from .cases import CASES, E2E_DIR, SKILL_DIR, Case, apply_matt
from .checks import Check, check_project, snapshot, transcript_checks, transcript_metrics

RUN_TIMEOUT = 60 * 60
SCRUB_ENV_PREFIXES = (
    "CLAUDECODE",
    "CLAUDE_CODE_",
    "CLAUDE_AGENT_SDK",
    "CLAUDE_PID",
    "CLAUDE_EFFORT",
)


COMMON_TOOLS = ("claude", "git", "mise", "uv", "bd")


def preflight(cases: list[Case]) -> list[str]:
    """跑之前确认被测的是本 checkout 的 skill、所需命令都在 PATH 上；返回问题列表。"""
    problems: list[str] = []
    config = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    installed = config / "skills" / "setup-project"
    if installed.resolve() != SKILL_DIR:
        problems.append(
            f"{installed} 未指向本 checkout 的 {SKILL_DIR}，headless 会话会测到别的版本；先执行 setup-dotagents"
        )
    needed = set(COMMON_TOOLS).union(*(c.tools for c in cases))
    problems += [f"PATH 上缺少 {tool}" for tool in sorted(needed) if shutil.which(tool) is None]
    return problems


def harness_prompt(case: Case, report_path: Path) -> str:
    stacks = " ".join(case.stacks) if case.stacks else "(not applicable: detection must not exit 3)"
    description = (
        case.description or "(none provided: keep the 初始化 marker and list it in the report)"
    )
    return f"""You are running the /setup-project skill inside an automated end-to-end harness. No human is available.

Non-interactive rules:
- Never call AskUserQuestion. Where SKILL.md phase 1 step 4 would ask the user, use these pre-supplied answers and continue:
  - 项目一句话描述: {description}
  - stack 选择 (only relevant if init_toolchain.py --detect-only exits 3): {stacks}
- In the final report add a section titled "本应提问" quoting verbatim the question(s) and options you would have asked, or stating that no question was needed and why.
- Write the phase-3 汇总报告 (Simplified Chinese) to this absolute path outside the project: {report_path}
  and also print it as your final message."""


def build_case(case: Case, case_dir: Path) -> Path:
    if case_dir.exists():
        shutil.rmtree(case_dir)
    project = case_dir / case.name
    project.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=project, check=True)
    case.build(project)
    apply_matt(project, case.triage)
    subprocess.run(["git", "add", "-A"], cwd=project, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=e2e",
            "-c",
            "user.email=e2e@example.invalid",
            "commit",
            "-q",
            "-m",
            "fixture",
        ],
        cwd=project,
        check=True,
    )
    return project


def run_claude(case: Case, project: Path, case_dir: Path, model: str, tag: str) -> Path:
    """运行一次 headless 会话；超时视为未完成，由 transcript:completed 判失败。"""
    transcript = case_dir / f"transcript{tag}.jsonl"
    report = case_dir / f"report{tag}.md"
    env = {k: v for k, v in os.environ.items() if not k.startswith(SCRUB_ENV_PREFIXES)}
    args = [
        "claude",
        "-p",
        "/setup-project",
        "--model",
        model,
        "--dangerously-skip-permissions",
        "--output-format",
        "stream-json",
        "--verbose",
        "--no-session-persistence",
        "--append-system-prompt",
        harness_prompt(case, report),
    ]
    with (
        transcript.open("w", encoding="utf-8") as out,
        (case_dir / f"stderr{tag}.log").open("w") as err,
    ):
        try:
            subprocess.run(args, cwd=project, env=env, stdout=out, stderr=err, timeout=RUN_TIMEOUT)
        except subprocess.TimeoutExpired:
            err.write(f"\n[harness] 超过 {RUN_TIMEOUT} 秒被终止\n")
    return transcript


def run_review(case: Case, case_dir: Path, model: str) -> None:
    brief = (E2E_DIR / "review-prompt.md").read_text(encoding="utf-8")
    prompt = (
        brief.replace("{{CASE_DIR}}", str(case_dir))
        .replace("{{PROJECT_DIR}}", case.name)
        .replace("{{CASE_NOTES}}", case.notes)
        .replace("{{SKILL_DIR}}", str(SKILL_DIR))
    )
    env = {k: v for k, v in os.environ.items() if not k.startswith(SCRUB_ENV_PREFIXES)}
    args = [
        "claude",
        "-p",
        prompt,
        "--model",
        model,
        "--dangerously-skip-permissions",
        "--output-format",
        "json",
        "--no-session-persistence",
        "--add-dir",
        str(case_dir),
    ]
    proc = subprocess.run(
        args, cwd=case_dir, env=env, capture_output=True, text=True, timeout=RUN_TIMEOUT
    )
    try:
        text = json.loads(proc.stdout).get("result", "")
    except json.JSONDecodeError:
        text = proc.stdout
    (case_dir / "review.md").write_text(text + "\n", encoding="utf-8")


def write_summary(
    case: Case, case_dir: Path, checks: list[Check], metrics: dict[str, object]
) -> list[Check]:
    """写 summary.md 与 checks.json，返回失败的硬检查。"""
    hard = [c for c in checks if c.ok is not None]
    failed = [c for c in hard if not c.ok]
    lines = [
        f"# {case.name}",
        "",
        case.notes,
        "",
        f"硬检查：{len(hard) - len(failed)}/{len(hard)} 通过",
        "",
        "| 检查 | 结果 | 说明 |",
        "| --- | --- | --- |",
    ]
    for c in checks:
        mark = "info" if c.ok is None else ("ok" if c.ok else "FAIL")
        detail = c.detail.replace("\n", "<br>").replace("|", "\\|")
        lines.append(f"| `{c.name}` | {mark} | {detail} |")
    result = metrics.get("result")
    assert isinstance(result, dict)
    shown = {k: v for k, v in metrics.items() if k != "result"}
    shown["result"] = {k: v for k, v in result.items() if k != "final_message"}
    lines += [
        "",
        "## 运行指标",
        "",
        "```json",
        json.dumps(shown, ensure_ascii=False, indent=2),
        "```",
    ]
    (case_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (case_dir / "checks.json").write_text(
        json.dumps([asdict(c) for c in checks], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return failed


@dataclass
class Outcome:
    case: str
    failed: list[str]
    minutes: float = 0.0
    cost_usd: object = ""
    review: str = ""


def run_case(case: Case, out: Path, args: argparse.Namespace) -> Outcome:
    """单个用例出任何异常都只让本用例失败，不中断其他用例。"""
    started = time.monotonic()
    try:
        outcome = _run_case(case, out / case.name, args)
    except Exception as exc:  # noqa: BLE001 — 记录后继续其他用例
        outcome = Outcome(case.name, [f"harness 异常：{type(exc).__name__}: {exc}"])
    outcome.minutes = round((time.monotonic() - started) / 60, 1)
    print(f"[{case.name}] {'FAIL' if outcome.failed else 'PASS'} in {outcome.minutes} min")
    return outcome


def _run_case(case: Case, case_dir: Path, args: argparse.Namespace) -> Outcome:
    project = case_dir / case.name
    if args.check_only:
        baseline = json.loads((case_dir / "baseline.json").read_text(encoding="utf-8"))
    else:
        project = build_case(case, case_dir)
        baseline = snapshot(project)
        (case_dir / "baseline.json").write_text(json.dumps(baseline, indent=1), encoding="utf-8")
        if args.build_only:
            print(f"[{case.name}] built at {project}")
            return Outcome(case.name, [])
        run_claude(case, project, case_dir, args.model, "")

    metrics = transcript_metrics(case_dir / "transcript.jsonl")
    checks = transcript_checks(metrics) + check_project(case, project, baseline)

    if args.rerun and not args.check_only:
        before = snapshot(project)
        run_claude(case, project, case_dir, args.model, "-rerun")
        after = snapshot(project)
        rerun = transcript_checks(transcript_metrics(case_dir / "transcript-rerun.jsonl"))
        checks += [Check(f"rerun:{c.name}", c.ok, c.detail) for c in rerun]
        changed = sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k))
        checks.append(Check("rerun:idempotent", not changed, ", ".join(changed)))

    failed = write_summary(case, case_dir, checks, metrics)
    if args.review and not args.check_only:
        run_review(case, case_dir, args.model)
    result = metrics.get("result")
    assert isinstance(result, dict)
    return Outcome(
        case.name,
        [c.name for c in failed],
        cost_usd=result.get("total_cost_usd", ""),
        review=review_verdicts(case_dir / "review.md"),
    )


def review_verdicts(path: Path) -> str:
    """从 review.md 的 VERDICTS 行取各结论计数；没有 review 时为空。"""
    if not path.exists():
        return ""
    found = [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("VERDICTS:")
    ]
    return found[-1].removeprefix("VERDICTS:").strip() if found else "（未给出 VERDICTS 行）"


def write_index(out: Path, outcomes: list[Outcome]) -> None:
    lines = [
        "# e2e 总览",
        "",
        "| 用例 | 硬检查 | 失败项 | 分钟 | 美元 | reviewer |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for o in outcomes:
        shown = [f"`{n}`" for n in o.failed[:5]]
        if len(o.failed) > 5:
            shown.append(f"等 {len(o.failed)} 项")
        failed = "<br>".join(shown) or "—"
        lines.append(
            f"| [{o.case}]({o.case}/summary.md) | {'FAIL' if o.failed else 'PASS'} "
            f"| {failed} | {o.minutes} | {o.cost_usd} | {o.review} |"
        )
    (out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("cases", nargs="*", choices=[*CASES, []], help="用例名；不传则全部")
    parser.add_argument("--out", type=Path, help="输出目录；默认在系统临时目录下按时间戳新建")
    parser.add_argument(
        "--model", default="opus", help="headless 会话与 review 使用的模型；不得为 Fable 系列"
    )
    parser.add_argument("--build-only", action="store_true", help="只构造 fixture，不运行 agent")
    parser.add_argument(
        "--check-only", action="store_true", help="不重跑 agent，只对 --out 下已有的产物重新检查"
    )
    parser.add_argument("--rerun", action="store_true", help="跑完后再跑一次，检查幂等")
    parser.add_argument("--review", action="store_true", help="跑完后派 reviewer 会话写 review.md")
    parser.add_argument("--jobs", type=int, default=3, help="并行用例数")
    args = parser.parse_args()
    if "fable" in args.model.lower():
        parser.error("子会话不得使用 Fable 系列模型")

    if args.check_only and not args.out:
        parser.error("--check-only 需要 --out 指向已有的输出目录")
    out = args.out or Path(tempfile.gettempdir()) / "dotagents-e2e" / datetime.now().strftime(
        "%Y%m%d-%H%M%S"
    )
    out.mkdir(parents=True, exist_ok=True)
    cases = [CASES[n] for n in args.cases or CASES]
    if not (args.check_only or args.build_only) and (problems := preflight(cases)):
        parser.error("；".join(problems))
    print(f"输出目录：{out}")
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        outcomes = list(pool.map(lambda c: run_case(c, out, args), cases))
    write_index(out, outcomes)
    passed = sum(not o.failed for o in outcomes)
    print(f"\n{passed}/{len(outcomes)} 用例硬检查通过；总览见 {out / 'summary.md'}")
    return 0 if passed == len(outcomes) else 1


if __name__ == "__main__":
    sys.exit(main())
