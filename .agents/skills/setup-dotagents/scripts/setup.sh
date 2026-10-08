#!/usr/bin/env bash
# 支持 macOS 自带 Bash 3.2，无第三方运行时依赖。
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../../.." && pwd -P)"
user_home="${HOME:?缺少 HOME}"
codex_dir="${CODEX_HOME:-$user_home/.codex}"
if [[ "$user_home" != /* || "$codex_dir" != /* ]]; then
    echo '错误：HOME 和 CODEX_HOME 必须为绝对路径。' >&2
    exit 1
fi

sources=("$repo_root/global/AGENTS.md" "$user_home/.agents/AGENTS.md")
targets=("$user_home/.agents/AGENTS.md" "$codex_dir/AGENTS.md")
parents=("$user_home/.agents" "$user_home/.agents/skills" "$codex_dir" "$codex_dir/skills")
if [[ ! -f "$repo_root/global/AGENTS.md" || ! -d "$repo_root/skills" ]]; then
    echo "错误：缺少 dotagents 源文件：$repo_root" >&2
    exit 1
fi
for skill_dir in "$repo_root"/skills/*; do
    [[ -d "$skill_dir" && -f "$skill_dir/SKILL.md" ]] || continue
    skill_name="${skill_dir##*/}"
    sources+=("$skill_dir")
    # 沿用仓库 README 记录的现有加载入口。
    if [[ "$skill_name" == prune-tests ]]; then
        targets+=("$codex_dir/skills/$skill_name")
    else
        targets+=("$user_home/.agents/skills/$skill_name")
    fi
done

conflicts=0
for parent in "${parents[@]}"; do
    ancestor="$parent"
    while [[ "$ancestor" != / && "$ancestor" != "$user_home" ]]; do
        if [[ -L "$ancestor" || ( -e "$ancestor" && ! -d "$ancestor" ) ]]; then
            echo "冲突：父路径不是普通目录：$ancestor" >&2
            conflicts=1
            break
        fi
        ancestor="$(dirname -- "$ancestor")"
    done
done
for ((i = 0; i < ${#targets[@]}; i++)); do
    target="${targets[$i]}"
    source="${sources[$i]}"
    if [[ -L "$target" && "$(readlink "$target")" == "$source" ]]; then
        continue
    fi
    if [[ -e "$target" || -L "$target" ]]; then
        echo "冲突：$target 已存在；期望链接到 $source" >&2
        conflicts=1
    fi
done
if ((conflicts)); then
    echo '检查失败，未创建任何链接；请先处理以上冲突。' >&2
    exit 1
fi

mkdir -p -- "${parents[@]}"
for ((i = 0; i < ${#targets[@]}; i++)); do
    target="${targets[$i]}"
    source="${sources[$i]}"
    if [[ -L "$target" && "$(readlink "$target")" == "$source" ]]; then
        echo "已存在：$target -> $source"
    else
        # 不使用强制覆盖；创建期间出现的新冲突应直接失败。
        ln -s -- "$source" "$target"
        echo "已创建：$target -> $source"
    fi
done
for ((i = 0; i < ${#targets[@]}; i++)); do
    target="${targets[$i]}"
    if [[ ! -L "$target" || "$(readlink "$target")" != "${sources[$i]}" || ! -e "$target" ]]; then
        echo "错误：链接核验失败：$target" >&2
        exit 1
    fi
done
echo '全部链接核验通过。请开启新的 Codex 会话验证规则和 skills 加载。'
