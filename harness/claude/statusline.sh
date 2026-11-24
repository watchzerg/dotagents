#!/bin/bash
# Claude Code statusLine in Starship's default look (needs a Nerd Font in the terminal):
#   dir  branch [status] 󰙅 worktree 󰚩 model-effort  󰍛 84k/200k  󰈸 4m
#   󰔟 5h 18% ↻2h13m · 7d 85% ↻3d4h  $1.84  +120 -34
# Each segment is skipped when its data is absent. Delete a segment block to hide it.
input=$(cat)

IFS=$'\x1f' read -r dir model effort used ctx_in ctx_size over200k worktree \
  cost added removed five five_reset week week_reset cache_seen cache_warm cache_expires \
  < <(echo "$input" | jq -r '[
  (.workspace.current_dir // .cwd // ""),
  (.model.display_name // ""),
  (.effort.level // ""),
  (.context_window.used_percentage // ""),
  (.context_window.total_input_tokens // ""),
  (.context_window.context_window_size // ""),
  (.exceeds_200k_tokens // ""),
  (.worktree.name // .workspace.git_worktree // ""),
  (.cost.total_cost_usd // ""),
  (.cost.total_lines_added // ""),
  (.cost.total_lines_removed // ""),
  (.rate_limits.five_hour.used_percentage // ""),
  (.rate_limits.five_hour.resets_at // ""),
  (.rate_limits.seven_day.used_percentage // ""),
  (.rate_limits.seven_day.resets_at // ""),
  (.prompt_cache.caching_observed // ""),
  (.prompt_cache.warm // ""),
  (.prompt_cache.expires_at // "")
] | map(tostring) | join("\u001f")')

esc=$'\033'
reset="${esc}[0m"
bold_cyan="${esc}[1;36m"
bold_purple="${esc}[1;35m"
bold_yellow="${esc}[1;33m"
bold_red="${esc}[1;31m"
green="${esc}[32m"
red="${esc}[31m"
blue="${esc}[34m"
orange="${esc}[38;5;208m"
dim="${esc}[2m"
sky="${esc}[38;5;117m"
pink="${esc}[38;5;213m"
branch_icon=$'\xee\x82\xa0'  # Nerd Font U+E0A0, written as bytes so editors can't drop it
now=$(date +%s)

# Green below 50%, yellow below 80%, red otherwise.
level_color() {
  local p=${1%.*}
  if [ "$p" -lt 50 ]; then printf '%s' "${esc}[32m"
  elif [ "$p" -lt 80 ]; then printf '%s' "${esc}[33m"
  else printf '%s' "${esc}[31m"; fi
}

# 84000 -> 84k, 1000000 -> 1M
human_tokens() {
  local n=${1%.*}
  if [ "$n" -ge 1000000 ]; then
    awk -v n="$n" 'BEGIN { v = n / 1000000; if (v == int(v)) printf "%dM", v; else printf "%.1fM", v }'
  elif [ "$n" -ge 1000 ]; then printf '%dk' $(((n + 500) / 1000))
  else printf '%d' "$n"; fi
}

# Seconds until an epoch timestamp -> 3d4h / 2h13m / 7m
until_epoch() {
  local s=$(( ${1%.*} - now ))
  [ "$s" -lt 0 ] && s=0
  local d=$((s / 86400)) h=$((s % 86400 / 3600)) m=$((s % 3600 / 60))
  if [ "$d" -gt 0 ]; then printf '%dd%dh' "$d" "$h"
  elif [ "$h" -gt 0 ]; then printf '%dh%dm' "$h" "$m"
  else printf '%dm' "$m"; fi
}

out=""

# Directory, git branch and status
if [ -n "$dir" ]; then
  root=$(git -C "$dir" --no-optional-locks rev-parse --show-toplevel 2>/dev/null)
  if [ -n "$root" ]; then
    # Like Starship: show the path from the repository name down.
    shown="$(basename "$root")${dir#"$root"}"
  else
    shown="${dir/#$HOME/~}"
    # Keep the last three components, as Starship's truncation_length does.
    if [ "$(echo "$shown" | awk -F/ '{print NF}')" -gt 3 ]; then
      shown=$(echo "$shown" | awk -F/ '{print $(NF-2)"/"$(NF-1)"/"$NF}')
    fi
  fi
  out="${bold_cyan}${shown}${reset}"

  if [ -n "$root" ]; then
    branch=$(git -C "$dir" --no-optional-locks symbolic-ref --short HEAD 2>/dev/null \
      || git -C "$dir" --no-optional-locks rev-parse --short HEAD 2>/dev/null)
    out+=" ${bold_purple}${branch_icon} ${branch}${reset}"

    status=$(git -C "$dir" --no-optional-locks status --porcelain=v1 --branch 2>/dev/null)
    flags=""
    echo "$status" | grep -q '^[MADRC]' && flags+="+"
    echo "$status" | grep -q '^.[MD]' && flags+="!"
    echo "$status" | grep -q '^??' && flags+="?"
    head=$(echo "$status" | head -1)
    [[ "$head" == *"ahead "* ]] && flags+="⇡"
    [[ "$head" == *"behind "* ]] && flags+="⇣"
    [ -n "$flags" ] && out+=" ${bold_red}[${flags}]${reset}"
  fi
fi

# Worktree
[ -n "$worktree" ] && out+=" ${green}󰙅 ${worktree}${reset}"

# Model and effort
if [ -n "$model" ]; then
  out+=" ${bold_yellow}󰚩 ${model// /-}${reset}"
  [ -n "$effort" ] && out+="${sky}-${effort}${reset}"
fi

# Context tokens, colored by the used percentage; the used count turns bold red past 200k
if [ -n "$ctx_in" ] && [ "${ctx_in%.*}" -gt 0 ] && [ -n "$ctx_size" ]; then
  color=$green
  [ -n "$used" ] && color=$(level_color "$used")
  used_color=$color
  [ "$over200k" = "true" ] && used_color=$bold_red
  out+="  ${color}󰍛 ${used_color}$(human_tokens "$ctx_in")${reset}${color}/$(human_tokens "$ctx_size")${reset}"
fi

# Prompt cache: warm with time left, or cold
if [ "$cache_seen" = "true" ]; then
  if [ "$cache_warm" = "true" ] && [ -n "$cache_expires" ] && [ "${cache_expires%.*}" -gt "$now" ]; then
    out+="  ${orange}󰈸 $(until_epoch "$cache_expires")${reset}"
  else
    out+="  ${blue}󰜗 cold${reset}"
  fi
fi

# 5-hour and 7-day usage with time until reset
usage=""
if [ -n "$five" ]; then
  usage="$(level_color "$five")5h $(printf '%.0f' "$five")%${reset}"
  [ -n "$five_reset" ] && usage+=" ${dim}↻$(until_epoch "$five_reset")${reset}"
fi
if [ -n "$week" ]; then
  usage+="${usage:+${dim} · ${reset}}$(level_color "$week")7d $(printf '%.0f' "$week")%${reset}"
  [ -n "$week_reset" ] && usage+=" ${dim}↻$(until_epoch "$week_reset")${reset}"
fi
[ -n "$usage" ] && out+="  󰔟 ${usage}"

# Estimated session cost
[ -n "$cost" ] && [ "$(printf '%.2f' "$cost")" != "0.00" ] && out+="  ${pink}\$$(printf '%.2f' "$cost")${reset}"

# Lines added and removed
if [ "${added:-0}" != "0" ] || [ "${removed:-0}" != "0" ]; then
  out+="  ${green}+${added:-0}${reset} ${red}-${removed:-0}${reset}"
fi

printf '%s' "$out"
