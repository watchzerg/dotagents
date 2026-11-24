#!/bin/bash
# Grok Build status line，外观对齐 Claude Code 的 Starship 风格（终端需要 Nerd Font）：
#   dir   branch [status] 󰙅 worktree 󰚩 model-effort  󰍛 84k/200k  $1.84  󰔟 2m13s  session
# 缺数据的段直接跳过。Grok 不提供速率限制、prompt cache 冷热、以及本次会话改动行数，这些段不显示。
input=$(cat)

parsed=$(printf '%s' "$input" | jq -r '
  def shval: tostring | @sh;
  [
    "dir=\((.workspace.current_dir // .cwd // "") | shval)",
    "model=\((.model.display_name // "") | shval)",
    "effort=\((.effort.level // "") | shval)",
    "used=\((.context_window.used_percentage // "") | shval)",
    "ctx_in=\((.context_window.context_tokens // "") | shval)",
    "ctx_size=\((.context_window.context_window_size // "") | shval)",
    "repo_root=\((.workspace.repo_root // "") | shval)",
    "branch=\((.workspace.branch // "") | shval)",
    "worktree=\((.worktree.name // .workspace.git_worktree // "") | shval)",
    "cost=\((.cost.total_cost_usd // "") | shval)",
    "session_name=\((.session_name // "") | shval)",
    "turn_started=\((.turn.started_at_ms // "") | shval)",
    "session_id=\((.session_id // "") | shval)"
  ] | join("\n")
') || exit 0
eval "$parsed"

esc=$'\033'
reset="${esc}[0m"
bold_cyan="${esc}[1;36m"
bold_purple="${esc}[1;35m"
bold_yellow="${esc}[1;33m"
bold_red="${esc}[1;31m"
green="${esc}[32m"
dim="${esc}[2m"
sky="${esc}[38;5;117m"
pink="${esc}[38;5;213m"
branch_icon=$''
worktree_icon=$'󰙅'
model_icon=$'󰚩'
ctx_icon=$'󰍛'
timer_icon=$'󰔟'
now=$(date +%s)

# 只留下十进制整数；空或非数字变成空串。
as_int() {
  local v=${1%.*}
  case $v in
    ""|*[!0-9]*) printf '' ;;
    *) printf '%s' "$v" ;;
  esac
}

# 50% 以下绿色，80% 以下黄色，其余红色。
level_color() {
  local p
  p=$(as_int "$1")
  if [ -z "$p" ]; then printf '%s' "$green"
  elif [ "$p" -lt 50 ]; then printf '%s' "${esc}[32m"
  elif [ "$p" -lt 80 ]; then printf '%s' "${esc}[33m"
  else printf '%s' "${esc}[31m"; fi
}

# 84000 -> 84k，1000000 -> 1M
human_tokens() {
  local n
  n=$(as_int "$1")
  [ -z "$n" ] && return
  if [ "$n" -ge 1000000 ]; then
    awk -v n="$n" 'BEGIN { v = n / 1000000; if (v == int(v)) printf "%dM", v; else printf "%.1fM", v }'
  elif [ "$n" -ge 1000 ]; then printf '%dk' $(((n + 500) / 1000))
  else printf '%d' "$n"; fi
}

# 秒数 -> 1h2m / 2m13s / 7s
elapsed_fmt() {
  local s=$1
  local h=$((s / 3600)) m=$((s % 3600 / 60)) sec=$((s % 60))
  if [ "$h" -gt 0 ]; then printf '%dh%dm' "$h" "$m"
  elif [ "$m" -gt 0 ]; then printf '%dm%ds' "$m" "$sec"
  else printf '%ds' "$sec"; fi
}

# 回合进行中 Grok 会连续调用本脚本，git status 缓存两秒。
git_status() {
  local dir="$1" sid="$2" hash f now_s mtime
  hash=$(printf '%s' "$sid:$dir" | cksum | awk '{print $1}')
  f="${TMPDIR:-/tmp}/grok-statusline-$hash"
  now_s=$(date +%s)
  if [ -f "$f" ]; then
    mtime=$(stat -c %Y "$f" 2>/dev/null || stat -f %m "$f" 2>/dev/null || printf '0')
    if [ $((now_s - mtime)) -lt 2 ]; then
      cat "$f"
      return
    fi
  fi
  if git -C "$dir" --no-optional-locks status --porcelain=v1 --branch >"$f.tmp" 2>/dev/null; then
    mv "$f.tmp" "$f"
  else
    rm -f "$f.tmp"
    : >"$f"
  fi
  cat "$f"
}

out=""

# 目录、分支和 git 状态
if [ -n "$dir" ]; then
  root="$repo_root"
  if [ -n "$root" ] && [ "$dir" != "$root" ] && [ "${dir#"$root"/}" = "$dir" ]; then
    root=""
  fi
  if [ -z "$root" ]; then
    root=$(git -C "$dir" --no-optional-locks rev-parse --show-toplevel 2>/dev/null)
  fi
  if [ -n "$root" ]; then
    shown="$(basename "$root")${dir#"$root"}"
  else
    shown="${dir/#$HOME/~}"
    if [ "$(printf '%s' "$shown" | awk -F/ '{print NF}')" -gt 3 ]; then
      shown=$(printf '%s' "$shown" | awk -F/ '{print $(NF-2)"/"$(NF-1)"/"$NF}')
    fi
  fi
  out="${bold_cyan}${shown}${reset}"

  if [ -n "$root" ]; then
    if [ -z "$branch" ]; then
      branch=$(git -C "$dir" --no-optional-locks symbolic-ref --short HEAD 2>/dev/null \
        || git -C "$dir" --no-optional-locks rev-parse --short HEAD 2>/dev/null)
    fi
    out+=" ${bold_purple}${branch_icon} ${branch}${reset}"

    status=$(git_status "$dir" "$session_id")
    flags=""
    printf '%s\n' "$status" | grep -q '^[MADRC]' && flags+="+"
    printf '%s\n' "$status" | grep -q '^.[MD]' && flags+="!"
    printf '%s\n' "$status" | grep -q '^??' && flags+="?"
    head=$(printf '%s\n' "$status" | head -1)
    case $head in
      *ahead\ *) flags+="⇡" ;;
    esac
    case $head in
      *behind\ *) flags+="⇣" ;;
    esac
    [ -n "$flags" ] && out+=" ${bold_red}[${flags}]${reset}"
  fi
fi

# Worktree
[ -n "$worktree" ] && out+=" ${green}${worktree_icon} ${worktree}${reset}"

# 模型与 effort
if [ -n "$model" ]; then
  out+=" ${bold_yellow}${model_icon} ${model// /-}${reset}"
  [ -n "$effort" ] && out+="${sky}-${effort}${reset}"
fi

# 当前窗口占用的 token，按使用率着色；超过 200k 时分子加粗变红
ctx_in_n=$(as_int "$ctx_in")
ctx_size_n=$(as_int "$ctx_size")
if [ -n "$ctx_in_n" ] && [ "$ctx_in_n" -gt 0 ] && [ -n "$ctx_size_n" ] && [ "$ctx_size_n" -gt 0 ]; then
  color=$green
  [ -n "$(as_int "$used")" ] && color=$(level_color "$used")
  used_color=$color
  [ "$ctx_in_n" -gt 200000 ] && used_color=$bold_red
  out+="  ${color}${ctx_icon} ${used_color}$(human_tokens "$ctx_in_n")${reset}${color}/$(human_tokens "$ctx_size_n")${reset}"
fi

# 会话费用。没有标价时字段缺席，不显示成 $0.00。
if [ -n "$cost" ]; then
  cost_fmt=$(printf '%.2f' "$cost" 2>/dev/null) || cost_fmt=""
  if [ -n "$cost_fmt" ] && [ "$cost_fmt" != "0.00" ]; then
    out+="  ${pink}\$${cost_fmt}${reset}"
  fi
fi

# 正在进行的回合已耗时，满 1 秒才显示
turn_n=$(as_int "$turn_started")
if [ -n "$turn_n" ]; then
  elapsed=$((now - turn_n / 1000))
  if [ "$elapsed" -ge 1 ]; then
    out+="  ${dim}${timer_icon} $(elapsed_fmt "$elapsed")${reset}"
  fi
fi

# 会话名，过长则截断
if [ -n "$session_name" ]; then
  session_name=${session_name//$'\n'/ }
  if [ "${#session_name}" -gt 40 ]; then
    session_name="${session_name:0:39}…"
  fi
  out+="  ${dim}${session_name}${reset}"
fi

[ -n "$out" ] && printf '%s\n' "$out"
