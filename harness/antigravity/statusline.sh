#!/bin/bash
# Antigravity CLI (agy) statusLine in Starship's default look (needs a Nerd Font):
#   dir  branch [status] 󰙅 worktree 󰚩 model-effort  󰍛 88k/1M  󰈸 25%
#   󰔟 7d 6% ↻6d11h  $0.42  +120 -34  plan
# Adapts automatically between 1 line (wide terminal) and 2 lines (narrow/split).
# Each segment is skipped when its data is absent. Delete a segment block to hide it.
export LC_NUMERIC=C

COMPACT_WARN_TOKENS=300000

input=$(cat)

IFS=$'\x1f' read -r dir model effort used ctx_in ctx_size \
  cache_read cur_in cur_cache_create cost agent_state cycle_mode vim_mode \
  subagents_running task_count pending_input tool_confirm cols quota_raw _ \
  < <(printf '%s' "$input" | jq -r '[
  (.workspace.current_dir // .cwd // ""),
  (.model.display_name // ""),
  (.model.effort // ""),
  (.context_window.used_percentage // ""),
  (.context_window.total_input_tokens // ""),
  (.context_window.context_window_size // ""),
  (.context_window.current_usage.cache_read_input_tokens // ""),
  (.context_window.current_usage.input_tokens // ""),
  (.context_window.current_usage.cache_creation_input_tokens // ""),
  (.cost.total_usd // ""),
  (.agent_state // ""),
  (.cycle_mode // ""),
  (.vim.mode // ""),
  ([(.subagents // [])[] | select(.status == "running")] | length),
  (.task_count // ""),
  (.pending_input_count // ""),
  (.tool_confirmation_pending // ""),
  (.terminal_width // ""),
  (
    (.quota // {}) | to_entries
    | map(select(
        (.value.disabled // false) != true
        and (.key | test("^(3p|third[-_]?party|claude|gpt|openai|anthropic)($|[-_])"; "i") | not)
      ))
    | sort_by(
        (.key
          | gsub("-wtu(?=-|$)"; "")
          | gsub("five[-_]hour"; "5h")
          | gsub("seven[-_]day|weekly"; "7d")
          | gsub("daily"; "1d")
          | split("-")
        ) as $p
        | [
            ($p[0] // ""),
            (if ($p | length) <= 2 then 0 else 1 end),
            (if $p[-1] == "5h" then 0
             elif $p[-1] == "1d" then 1
             elif $p[-1] == "7d" then 2
             else 3 end),
            .key
          ]
      )
    | map(
        .key as $k
        | if (.value.remaining_fraction != null) then
            "\($k)|pct|\((1 - .value.remaining_fraction) * 100)|\(.value.reset_in_seconds // "")"
          elif (.value.remaining_amount != null) then
            "\($k)|amt|\(.value.remaining_amount)|\(.value.reset_in_seconds // "")"
          else empty end
      )
    | join(";")
  ),
  "_"
] | map(tostring) | join("\u001f")' 2>/dev/null)

esc=$'\033'
reset="${esc}[0m"
bold_cyan="${esc}[1;36m"
bold_purple="${esc}[1;35m"
bold_yellow="${esc}[1;33m"
bold_red="${esc}[1;31m"
green="${esc}[32m"
yellow="${esc}[33m"
red="${esc}[31m"
blue="${esc}[34m"
orange="${esc}[38;5;208m"
dim="${esc}[2m"
sky="${esc}[38;5;117m"
pink="${esc}[38;5;213m"
branch_icon=$'\xee\x82\xa0'  # Nerd Font U+E0A0, written as bytes so editors can't drop it

# Green below 50%, yellow below 80%, red otherwise.
level_color() {
  local p=${1%.*}
  p=${p:-0}
  if [ "$p" -lt 50 ]; then printf '%s' "$green"
  elif [ "$p" -lt 80 ]; then printf '%s' "$yellow"
  else printf '%s' "$red"; fi
}

# 84000 -> 84k, 1000000 / 1048576 -> 1M
human_tokens() {
  local n=${1%.*}
  n=${n:-0}
  if [ "$n" -eq 1048576 ]; then
    printf '1M'
  elif [ "$n" -eq 2097152 ]; then
    printf '2M'
  elif [ "$n" -ge 1000000 ]; then
    awk -v n="$n" 'BEGIN {
      v = n / 1000000
      s = sprintf("%.1f", v)
      sub(/\.0$/, "", s)
      printf "%sM", s
    }'
  elif [ "$n" -ge 1000 ]; then
    printf '%dk' $(((n + 500) / 1000))
  else
    printf '%d' "$n"
  fi
}

# Seconds duration -> 3d4h / 2h13m / 7m
format_duration() {
  local s=${1%.*}
  s=${s:-0}
  [ "$s" -lt 0 ] && s=0
  local d=$((s / 86400)) h=$((s % 86400 / 3600)) m=$((s % 3600 / 60))
  if [ "$d" -gt 0 ]; then printf '%dd%dh' "$d" "$h"
  elif [ "$h" -gt 0 ]; then printf '%dh%dm' "$h" "$m"
  else printf '%dm' "$m"; fi
}

# Visible length after stripping ANSI SGR sequences.
visible_len() {
  local stripped
  stripped=$(printf '%s' "$1" | sed $'s/\033\\[[0-9;]*m//g')
  printf '%d' "${#stripped}"
}

append_seg() {
  local var=$1 sep=$2 seg=$3
  [ -z "$seg" ] && return
  eval "if [ -n \"\$$var\" ]; then $var=\"\${$var}\${sep}\${seg}\"; else $var=\"\${seg}\"; fi"
}

line1=""
line2=""
git_dirty_tracked=0
git_root=""

# Directory, git branch, status and worktree
if [ -n "$dir" ]; then
  git_info=$(git -C "$dir" --no-optional-locks rev-parse --show-toplevel --git-dir --show-prefix 2>/dev/null)
  if [ -n "$git_info" ]; then
    git_root=$(printf '%s\n' "$git_info" | sed -n '1p')
    git_dir=$(printf '%s\n' "$git_info" | sed -n '2p')
    git_prefix=$(printf '%s\n' "$git_info" | sed -n '3p')
    git_prefix="${git_prefix%/}"
    # Like Starship: show the path from the repository name down (immune to symlinks).
    shown="$(basename "$git_root")${git_prefix:+/${git_prefix}}"
  else
    shown="${dir/#$HOME/~}"
    # Keep the last three components, as Starship's truncation_length does.
    if [ "$(printf '%s\n' "$shown" | awk -F/ '{print NF}')" -gt 3 ]; then
      shown=$(printf '%s\n' "$shown" | awk -F/ '{print $(NF-2)"/"$(NF-1)"/"$NF}')
    fi
  fi
  line1="${bold_cyan}${shown}${reset}"

  if [ -n "$git_root" ]; then
    branch=$(git -C "$dir" --no-optional-locks symbolic-ref --short HEAD 2>/dev/null \
      || git -C "$dir" --no-optional-locks rev-parse --short HEAD 2>/dev/null)
    [ -n "$branch" ] && line1+=" ${bold_purple}${branch_icon} ${branch}${reset}"

    status=$(git -C "$dir" --no-optional-locks status --porcelain=v1 --branch 2>/dev/null)
    flags=""
    if printf '%s\n' "$status" | grep -q '^[MADRC]'; then
      flags+="+"
      git_dirty_tracked=1
    fi
    if printf '%s\n' "$status" | grep -q '^.[MD]'; then
      flags+="!"
      git_dirty_tracked=1
    fi
    printf '%s\n' "$status" | grep -q '^??' && flags+="?"
    head=$(printf '%s\n' "$status" | head -1)
    [[ "$head" == *"ahead "* ]] && flags+="⇡"
    [[ "$head" == *"behind "* ]] && flags+="⇣"
    [ -n "$flags" ] && line1+=" ${bold_red}[${flags}]${reset}"

    # Linked git worktree (e.g. .git/worktrees/<name>)
    if [[ "$git_dir" == */worktrees/* ]]; then
      worktree=$(basename "$git_dir")
      [ -n "$worktree" ] && line1+=" ${green}󰙅 ${worktree}${reset}"
    fi
  fi
fi

# Model and effort (avoid duplicating trailing "(Effort)" already in display_name)
if [ -n "$model" ]; then
  if [ -n "$effort" ]; then
    model_base=$(printf '%s' "$model" | awk -v e="$effort" '{
      s = $0
      if (tolower(s) ~ (" \\(" tolower(e) "\\)$")) {
        sub(/ \([^)]*\)$/, "", s)
      }
      print s
    }')
    append_seg line1 " " "${bold_yellow}󰚩 ${model_base// /-}${reset}${sky}-${effort}${reset}"
  else
    append_seg line1 " " "${bold_yellow}󰚩 ${model// /-}${reset}"
  fi
fi

# Context tokens, colored by the used percentage; turns bold red at COMPACT_WARN_TOKENS (300k)
if [ -n "$ctx_in" ] && [ "${ctx_in%.*}" -gt 0 ] && [ -n "$ctx_size" ] && [ "${ctx_size%.*}" -gt 0 ]; then
  if [ "${ctx_in%.*}" -ge "$COMPACT_WARN_TOKENS" ]; then
    append_seg line1 "  " "${bold_red}󰍛 $(human_tokens "$ctx_in")/$(human_tokens "$ctx_size")${reset}"
  else
    color=$green
    [ -n "$used" ] && color=$(level_color "$used")
    append_seg line1 "  " "${color}󰍛 $(human_tokens "$ctx_in")/$(human_tokens "$ctx_size")${reset}"
  fi
elif [ -n "$used" ] && awk -v u="$used" 'BEGIN { exit !(u > 0) }'; then
  color=$(level_color "$used")
  append_seg line1 "  " "${color}󰍛 $(printf '%.0f' "$used")%${reset}"
fi

# Prompt cache hit ratio from current_usage (shown when cache hits occur)
if [ -n "$cache_read" ] && [ "${cache_read%.*}" -gt 0 ]; then
  total_cur=$(( ${cur_in%.*} + ${cache_read%.*} + ${cur_cache_create%.*} ))
  if [ "$total_cur" -gt 0 ]; then
    cache_pct=$(( (${cache_read%.*} * 100 + total_cur / 2) / total_cur ))
    append_seg line1 "  " "${orange}󰈸 ${cache_pct}%${reset}"
  fi
fi

# Quota usage with time until reset (from Antigravity .quota buckets, excluding third-party models)
if [ -n "$quota_raw" ]; then
  # Strip leading "gemini-" when every bucket shares that prefix
  strip_gemini=1
  IFS=';' read -ra q_entries <<< "$quota_raw"
  for entry in "${q_entries[@]}"; do
    q_key=${entry%%|*}
    case "$q_key" in
      gemini-*) ;;
      *) strip_gemini=0; break ;;
    esac
  done

  usage=""
  for entry in "${q_entries[@]}"; do
    IFS='|' read -r q_key q_type q_val q_reset <<< "$entry"
    label="$q_key"
    [ "$strip_gemini" -eq 1 ] && label="${label#gemini-}"
    label="${label//-wtu/}"
    label="${label//weekly/7d}"
    label="${label//seven_day/7d}"
    label="${label//seven-day/7d}"
    label="${label//five_hour/5h}"
    label="${label//five-hour/5h}"
    label="${label//daily/1d}"

    seg=""
    if [ "$q_type" = "pct" ]; then
      q_pct=$(awk -v v="$q_val" 'BEGIN { if (v < 0) v = 0; if (v > 100) v = 100; printf "%.0f", v }')
      seg="$(level_color "$q_pct")${label} ${q_pct}%${reset}"
    elif [ "$q_type" = "amt" ]; then
      seg="${green}${label} ${q_val}${reset}"
    fi
    if [ -n "$seg" ]; then
      [ -n "$q_reset" ] && [ "${q_reset%.*}" -gt 0 ] && seg+=" ${dim}↻$(format_duration "$q_reset")${reset}"
      usage+="${usage:+${dim} · ${reset}}${seg}"
    fi
  done
  [ -n "$usage" ] && append_seg line2 "  " "󰔟 ${usage}"
fi

# Estimated session cost
if [ -n "$cost" ] && [ "$(printf '%.2f' "$cost")" != "0.00" ]; then
  append_seg line2 "  " "${pink}\$$(printf '%.2f' "$cost")${reset}"
fi

# Working-tree lines added and removed (only runs git diff when tracked files are dirty)
if [ "$git_dirty_tracked" -eq 1 ] && [ -n "$git_root" ]; then
  diff_out=$(git -C "$dir" --no-optional-locks diff HEAD --numstat 2>/dev/null \
    || git -C "$dir" --no-optional-locks diff --numstat 2>/dev/null)
  read -r added removed < <(printf '%s\n' "$diff_out" | awk '
    $1 ~ /^[0-9]+$/ && $2 ~ /^[0-9]+$/ { a += $1; r += $2 }
    END { printf "%d %d\n", a + 0, r + 0 }
  ')
  if [ "${added:-0}" -gt 0 ] || [ "${removed:-0}" -gt 0 ]; then
    append_seg line2 "  " "${green}+${added}${reset} ${red}-${removed}${reset}"
  fi
fi

# Antigravity runtime badges (skipped when inactive/default to keep Starship look clean)
badges=""
if [ -n "$vim_mode" ]; then
  case "$vim_mode" in
    NORMAL)  badges+="${badges:+ }${blue}[N]${reset}" ;;
    INSERT)  badges+="${badges:+ }${green}[I]${reset}" ;;
    VISUAL*) badges+="${badges:+ }${bold_purple}[V]${reset}" ;;
    *)       badges+="${badges:+ }${dim}[${vim_mode}]${reset}" ;;
  esac
fi
if [ -n "$cycle_mode" ]; then
  case "$cycle_mode" in
    plan)         badges+="${badges:+ }${blue}󰙨 plan${reset}" ;;
    auto)         badges+="${badges:+ }${green}󰁨 auto${reset}" ;;
    accept-edits) badges+="${badges:+ }${sky}󰄬 edits${reset}" ;;
    *)            badges+="${badges:+ }${dim}${cycle_mode}${reset}" ;;
  esac
fi
[ "$tool_confirm" = "true" ] && badges+="${badges:+ }${bold_yellow}󰀦 confirm${reset}"
[ "$agent_state" = "error" ] && badges+="${badges:+ }${bold_red}󰅚 error${reset}"
[ "${subagents_running:-0}" -gt 0 ] && badges+="${badges:+ }${sky}󰐻 ${subagents_running}${reset}"
[ -n "$task_count" ] && [ "${task_count%.*}" -gt 0 ] && badges+="${badges:+ }${dim}󰔚 ${task_count}${reset}"
[ -n "$pending_input" ] && [ "${pending_input%.*}" -gt 0 ] && badges+="${badges:+ }${dim}󰍡 ${pending_input}${reset}"
[ -n "$badges" ] && append_seg line2 "  " "$badges"

# Adaptive 1-line vs 2-line output based on terminal_width
if [ -z "$line2" ]; then
  printf '%s' "$line1"
elif [ -z "$line1" ]; then
  printf '%s' "$line2"
elif [ -n "$cols" ] && [ "${cols%.*}" -gt 0 ]; then
  len1=$(visible_len "$line1")
  len2=$(visible_len "$line2")
  if [ $((len1 + 2 + len2 + 4)) -le "${cols%.*}" ]; then
    printf '%s  %s' "$line1" "$line2"
  else
    printf '%s\n%s' "$line1" "$line2"
  fi
else
  printf '%s\n%s' "$line1" "$line2"
fi
