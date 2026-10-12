"""对一次 setup-project 真实运行的产物做确定性检查，并从 transcript 提取流程指标。"""

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .cases import CONTRACT_RECIPES, Case

# 与模板 docs/agents/documentation.md 里给出的清单命令同一个 pattern，规则正文不会自命中。
MARKER = re.compile(r"<待填 (初始化|阶段3|首个模块|按需)：")
IGNORED_DIRS = {".git", ".venv", "node_modules", ".build", ".beads", "__pycache__", ".mise"}


@dataclass
class Check:
    name: str
    ok: bool | None
    detail: str = ""


def snapshot(project: Path) -> dict[str, str]:
    """项目内所有文件的内容哈希，排除构建产物与 Beads 数据库。"""
    result: dict[str, str] = {}
    for path in project.rglob("*"):
        if any(part in IGNORED_DIRS for part in path.relative_to(project).parts):
            continue
        if path.is_file():
            result[path.relative_to(project).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return result


def sh(args: list[str], cwd: Path, timeout: int = 600) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def tail(text: str, lines: int = 15) -> str:
    return "\n".join(text.strip().splitlines()[-lines:])


# ---------------------------------------------------------------- 产物检查


def check_project(case: Case, project: Path, baseline: dict[str, str]) -> list[Check]:
    checks: list[Check] = []
    after = snapshot(project)

    for rel in case.present:
        checks.append(Check(f"present:{rel}", (project / rel).exists()))
    for rel in case.absent:
        checks.append(Check(f"absent:{rel}", not (project / rel).exists()))
    for rel in case.untouched:
        checks.append(
            Check(f"untouched:{rel}", baseline.get(rel) == after.get(rel) and rel in after)
        )

    checks.extend(_check_agents_md(case, project))
    checks.extend(_check_claude_md(project, baseline))
    checks.extend(_check_markers(case, project))
    checks.extend(_check_description(case, project))
    checks.extend(_check_toolchain(case, project))
    checks.append(Check("beads-initialised", (project / ".beads").is_dir()))
    checks.append(_check_git_clean_of_commits(project, baseline))
    return checks


def _check_agents_md(case: Case, project: Path) -> list[Check]:
    path = project / "AGENTS.md"
    if not path.exists():
        return [Check("agents-md:exists", False)]
    text = path.read_text(encoding="utf-8")
    headings = re.findall(r"^## (.+)$", text, re.M)
    out = [
        Check("agents-md:no-agent-skills-section", "Agent skills" not in headings),
        Check("agents-md:has-template-sections", {"常驻约束", "按任务读取"} <= set(headings)),
        Check(
            "agents-md:no-duplicate-sections",
            len(headings) == len(set(headings)),
            ", ".join(h for h in headings if headings.count(h) > 1),
        ),
        Check(
            "agents-md:triage-row",
            ("triage-labels.md" in text) == case.triage,
            "触发表的分诊行应与 triage-labels.md 是否存在一致",
        ),
    ]
    for pattern, needle, expected in case.text_rules:
        files = sorted(project.glob(pattern))
        hits = [
            f.relative_to(project).as_posix()
            for f in files
            if needle in f.read_text(encoding="utf-8")
        ]
        ok = bool(hits) if expected else not hits
        out.append(
            Check(
                f"text:{pattern}:{'含' if expected else '不含'}「{needle[:24]}」",
                ok,
                "匹配文件：" + ", ".join(hits) if hits else "无匹配文件",
            )
        )
    for rel, needles in case.sentinels.items():
        body = (project / rel).read_text(encoding="utf-8")
        missing = [n for n in needles if n not in body]
        out.append(Check(f"sentinels:{rel}", not missing, "缺失：" + "；".join(missing)))
    return out


def _check_claude_md(project: Path, baseline: dict[str, str]) -> list[Check]:
    if "CLAUDE.md" not in baseline:
        return [Check("claude-md:not-created", not (project / "CLAUDE.md").exists())]
    text = (project / "CLAUDE.md").read_text(encoding="utf-8").strip()
    return [Check("claude-md:only-at-agents", text == "@AGENTS.md", repr(text[:80]))]


def _check_markers(case: Case, project: Path) -> list[Check]:
    found: dict[str, list[str]] = {}
    for path in project.rglob("*.md"):
        if any(part in IGNORED_DIRS for part in path.relative_to(project).parts):
            continue
        for timing in MARKER.findall(path.read_text(encoding="utf-8")):
            found.setdefault(timing, []).append(path.relative_to(project).as_posix())
    out: list[Check] = []
    if case.description:
        out.append(
            Check(
                "markers:init-filled",
                "初始化" not in found,
                ", ".join(found.get("初始化", [])),
            )
        )
    if case.expect_mode == "new" and case.expect_stacks != ("none",):
        out.append(
            Check("markers:stage3-filled", "阶段3" not in found, ", ".join(found.get("阶段3", [])))
        )
    summary = {t: len(v) for t, v in found.items()}
    out.append(Check("markers:remaining", None, json.dumps(summary, ensure_ascii=False)))
    return out


def _check_description(case: Case, project: Path) -> list[Check]:
    if not case.description:
        return []
    # 描述允许被 agent 展开或改写措辞，只要求至少两个四字片段原样出现。
    grams = {
        run[i : i + 4]
        for run in re.findall(r"[\u4e00-\u9fff]{4,}", case.description)
        for i in range(len(run) - 3)
    }
    out = []
    for rel in case.description_targets:
        path = project / rel
        body = path.read_text(encoding="utf-8") if path.exists() else ""
        hits = sorted(g for g in grams if g in body)
        # GLOSSARY 的标记要求改写成领域上下文，只要求一个片段。
        needed = 1 if rel == "GLOSSARY.md" else 2
        out.append(
            Check(f"description:{rel}", len(hits) >= needed, "命中片段：" + " ".join(hits[:6]))
        )
    return out


def _check_toolchain(case: Case, project: Path) -> list[Check]:
    out: list[Check] = []
    justfile = project / "justfile"
    if case.expect_mode == "new":
        if not justfile.exists():
            return [Check("justfile:exists", False)]
        summary = sh(["just", "--summary"], project)
        names = set(summary.stdout.split())
        missing = sorted(set(CONTRACT_RECIPES) - names)
        out.append(Check("justfile:contract-recipes", not missing, "缺失：" + " ".join(missing)))
        docs = sh(["just", "docs-check"], project)
        out.append(Check("just docs-check", docs.returncode == 0, tail(docs.stdout + docs.stderr)))
        gate = sh(["just", "gate-core"], project, timeout=1800)
        if case.expect_stacks == ("none",):
            expected = gate.returncode != 0 and "check-toolchain" in (gate.stdout + gate.stderr)
            out.append(
                Check(
                    "just gate-core (none: 应在 check-toolchain 失败)",
                    expected,
                    tail(gate.stdout + gate.stderr),
                )
            )
        else:
            out.append(
                Check("just gate-core", gate.returncode == 0, tail(gate.stdout + gate.stderr))
            )
        gitignore = project / ".gitignore"
        out.append(Check(".gitignore:exists", gitignore.exists()))
    else:
        docs = sh(["python3", "scripts/check_docs.py"], project)
        out.append(
            Check(
                "python3 scripts/check_docs.py",
                docs.returncode == 0,
                tail(docs.stdout + docs.stderr),
            )
        )
        if justfile.exists():
            listing = sh(["just", "--summary"], project)
            out.append(
                Check("just --summary parses", listing.returncode == 0, tail(listing.stderr))
            )
            names = set(listing.stdout.split())
            missing = sorted(set(CONTRACT_RECIPES) - names)
            out.append(
                Check(
                    "justfile:contract-recipes-after-fill",
                    not missing,
                    "缺失：" + " ".join(missing),
                )
            )
    return out


def _check_git_clean_of_commits(project: Path, baseline: dict[str, str]) -> Check:
    log = sh(["git", "log", "--oneline"], project).stdout.strip().splitlines()
    # fixture 一次 commit，bd init 允许一次自动 commit；agent 本身不得 commit。
    return Check("git:no-agent-commits", len(log) <= 2, "\n".join(log))


# ---------------------------------------------------------------- transcript 指标


def transcript_metrics(transcript: Path) -> dict[str, object]:
    tool_counts: dict[str, int] = {}
    scripts: list[str] = []
    questions: list[str] = []
    result: dict[str, object] = {}
    for line in transcript.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "assistant":
            for block in event.get("message", {}).get("content", []):
                if block.get("type") != "tool_use":
                    continue
                name = block.get("name", "?")
                tool_counts[name] = tool_counts.get(name, 0) + 1
                command = str(block.get("input", {}).get("command", ""))
                # 一条命令里可能串联多个脚本，按出现位置逐个记录。
                found = sorted(
                    (command.find(script), script)
                    for script in (
                        "init_beads",
                        "init_docs",
                        "init_toolchain",
                        "check_docs",
                        "just ",
                    )
                    if script in command
                )
                scripts.extend(
                    f"{script} ⟵ {command.strip().splitlines()[0][:120]}" for _, script in found
                )
                if name == "AskUserQuestion":
                    questions.append(json.dumps(block.get("input"), ensure_ascii=False)[:400])
        elif event.get("type") == "result":
            result = {
                "subtype": event.get("subtype"),
                "num_turns": event.get("num_turns"),
                "duration_min": round((event.get("duration_ms") or 0) / 60000, 1),
                "total_cost_usd": round(event.get("total_cost_usd") or 0, 2),
                "permission_denials": len(event.get("permission_denials") or []),
                "final_message": event.get("result"),
            }
    return {
        "tool_counts": dict(sorted(tool_counts.items())),
        "script_commands": scripts,
        "ask_user_question_calls": questions,
        "result": result,
    }


def transcript_checks(metrics: dict[str, object]) -> list[Check]:
    result = metrics["result"]
    assert isinstance(result, dict)
    scripts = metrics["script_commands"]
    assert isinstance(scripts, list)
    order = [s.split(" ⟵ ", 1)[0] for s in scripts]
    order = [o for o in order if o in ("init_beads", "init_docs", "init_toolchain")]
    # shell 失误导致的重跑不算顺序错误，只看去掉连续重复后的序列。
    order = [o for i, o in enumerate(order) if o and (i == 0 or o != order[i - 1])]
    expected_prefix = ["init_beads", "init_docs", "init_toolchain"]
    return [
        Check(
            "transcript:completed", result.get("subtype") == "success", str(result.get("subtype"))
        ),
        Check("transcript:no-ask-user-question", not metrics["ask_user_question_calls"]),
        Check("transcript:no-permission-denials", result.get("permission_denials") == 0),
        Check(
            "transcript:script-order",
            order[:3] == expected_prefix,
            " → ".join(order),
        ),
    ]
