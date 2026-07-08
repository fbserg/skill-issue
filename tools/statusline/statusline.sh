#!/usr/bin/env bash
set -f

input=$(cat)
[ -z "$input" ] && { printf "Claude"; exit 0; }

mkdir -p /tmp/claude
printf '%s' "$input" > /tmp/claude/statusline-last.json
ratecache=/tmp/claude/statusline-ratelimits.json

blue='\033[38;2;0;153;255m'
orange='\033[38;2;255;176;85m'
green='\033[38;2;0;160;0m'
cyan='\033[38;2;46;149;153m'
red='\033[38;2;255;85;85m'
yellow='\033[38;2;230;200;0m'
dim='\033[2m'
reset='\033[0m'


format_tokens() {
    local n=$1
    if (( n >= 1000000 )); then
        awk "BEGIN{printf \"%.1fm\", $n/1000000}"
    elif (( n >= 1000 )); then
        awk "BEGIN{printf \"%.0fk\", $n/1000}"
    else
        printf "%d" "$n"
    fi
}

build_bar() {
    local pct=$1 width=$2
    (( pct < 0 )) && pct=0
    (( pct > 100 )) && pct=100
    local -a partials=("" "▏" "▎" "▍" "▌" "▋" "▊" "▉")
    local total_eighths=$(( pct * width * 8 / 100 ))
    local full=$(( total_eighths / 8 ))
    local frac=$(( total_eighths % 8 ))
    local has_partial=$(( frac > 0 ? 1 : 0 ))
    local empty=$(( width - full - has_partial ))
    local color
    if (( pct >= 90 )); then color=$red
    elif (( pct >= 70 )); then color=$yellow
    elif (( pct >= 50 )); then color=$orange
    else color=$green
    fi
    local bar="$color" i
    for (( i=0; i<full; i++ )); do bar+="█"; done
    (( frac > 0 )) && bar+="${partials[$frac]}"
    for (( i=0; i<empty; i++ )); do bar+=" "; done
    bar+="$reset"
    printf "%s" "$bar"
}

to_epoch() {
    local ts="$1"
    # already a unix timestamp (integer)
    [[ "$ts" =~ ^[0-9]+$ ]] && { echo "$ts"; return; }
    local epoch
    epoch=$(date -d "$ts" +%s 2>/dev/null) && { echo "$epoch"; return; }
    local stripped="${ts%%.*}"
    stripped="${stripped%%Z}"; stripped="${stripped%%+*}"
    if [[ "$ts" == *Z* ]] || [[ "$ts" == *+00:00* ]]; then
        epoch=$(env TZ=UTC date -j -f "%Y-%m-%dT%H:%M:%S" "$stripped" +%s 2>/dev/null)
    else
        epoch=$(date -j -f "%Y-%m-%dT%H:%M:%S" "$stripped" +%s 2>/dev/null)
    fi
    [ -n "$epoch" ] && echo "$epoch"
}

time_until() {
    local diff=$(( $1 - $(date +%s) ))
    (( diff <= 0 )) && echo "now" && return
    local mins=$(( diff / 60 ))
    if (( mins >= 60 )); then
        local hrs=$(( mins / 60 )) rem=$(( mins % 60 ))
        (( rem > 0 )) && echo "${hrs}h${rem}m" || echo "${hrs}h"
    else
        echo "${mins}m"
    fi
}

sep=" ${dim}|${reset} "
out=""

# --- repo@branch ---
cwd=$(printf '%s' "$input" | jq -r '.workspace.current_dir // .cwd // empty')
if [ -n "$cwd" ]; then
    repo="${cwd##*/}"
    git_branch=$(GIT_OPTIONAL_LOCKS=0 git -C "$cwd" rev-parse --abbrev-ref HEAD 2>/dev/null)
    dirty=$(GIT_OPTIONAL_LOCKS=0 git -C "$cwd" status --porcelain 2>/dev/null | head -1)
    if [ -n "$git_branch" ] && [ "$git_branch" != "HEAD" ]; then
        branch_sfx="" branch_color=$green
        [ -n "$dirty" ] && branch_sfx="*" && branch_color=$yellow
        out+="${cyan}${repo}${reset}${dim}@${reset}${branch_color}${git_branch}${branch_sfx}${reset}"
    elif [ "$git_branch" = "HEAD" ]; then
        sha=$(GIT_OPTIONAL_LOCKS=0 git -C "$cwd" rev-parse --short HEAD 2>/dev/null)
        out+="${cyan}${repo}${reset}${dim}@${sha}${reset}"
    else
        out+="${cyan}${repo}${reset}"
    fi
    if [ -n "$dirty" ]; then
        diff_stat=$(GIT_OPTIONAL_LOCKS=0 git -C "$cwd" diff HEAD --numstat 2>/dev/null \
            | awk '{a+=$1; d+=$2} END {if(a||d) printf "%d %d",a,d}')
        if [ -n "$diff_stat" ]; then
            ins=${diff_stat%% *} del=${diff_stat##* }
            (( ins > 0 )) && out+=" ${green}+${ins}${reset}"
            (( del > 0 )) && out+=" ${red}-${del}${reset}"
        fi
    fi
fi

# --- model + effort ---
model_name=$(printf '%s' "$input" | jq -r '.model.display_name // empty')
effort_level=$(printf '%s' "$input" | jq -r '.effort.level // empty')
# shorten: "Opus 4.8 (1M context)" -> "opus1m", "Sonnet 4.6" -> "sonnet", "Fable 5" -> "fable"
if [ -n "$model_name" ]; then
    short=$(printf '%s' "$model_name" | awk '{print tolower($1)}')
    case "$model_name" in *1[Mm]*) short="${short}1m" ;; esac
    model_name="$short"
fi
if [ -n "$model_name" ]; then
    out+="${sep}${blue}${model_name}${reset}"
    if [ -n "$effort_level" ] && [ "$effort_level" != "null" ]; then
        case "$effort_level" in
            max)    eff_color=$red ;;
            xhigh)  eff_color=$red ;;
            high)   eff_color=$orange ;;
            medium) eff_color=$yellow ;;
            low)    eff_color=$green ;;
            *)      eff_color=$cyan ;;
        esac
        out+="${dim}·${reset}${eff_color}${effort_level}${reset}"
    fi
fi

# --- context bar ---
size=$(printf '%s' "$input" | jq -r '.context_window.context_window_size // 0')
itok=$(printf '%s' "$input" | jq -r '.context_window.current_usage.input_tokens // 0')
ccr=$(printf '%s' "$input" | jq -r '.context_window.current_usage.cache_creation_input_tokens // 0')
crd=$(printf '%s' "$input" | jq -r '.context_window.current_usage.cache_read_input_tokens // 0')
used=$(( itok + ccr + crd ))

# Fill the bar toward the point where auto-compaction ACTUALLY fires, not the
# raw window. Claude Code's real trigger (verified against the cli binary) is:
#   window  = env set ? min(rawWindow, clamp(env,100k,1M)) : rawWindow
#   trigger = min( floor(window * pct/100), window - 13000 )
# The window-13000 term is a hard output reserve CC always subtracts; at pct=100
# it's what makes the true trigger 287k, not the configured 300k. We anchor on
# the raw window from stdin (already correct for 1M on/off) so the bar stays
# honest even when CLAUDE_CODE_AUTO_COMPACT_WINDOW is unset. NOTE: do NOT use
# stdin's context_window.used_percentage — CC computes that against the raw
# window, so it reads ~29% at the moment compaction fires. Useless here.
CTX_OUTPUT_RESERVE=13000          # CC's fixed reserve below the window (SB7)
window=$size
compact_env=${CLAUDE_CODE_AUTO_COMPACT_WINDOW:-0}
if (( compact_env > 0 )); then
    (( compact_env < 100000 )) && compact_env=100000
    (( compact_env > 1000000 )) && compact_env=1000000
    (( window == 0 || compact_env < window )) && window=$compact_env
fi
if (( window > 0 )); then
    pct_override=${CLAUDE_AUTOCOMPACT_PCT_OVERRIDE:-100}
    trigger=$(( window * pct_override / 100 ))
    reserve_cap=$(( window - CTX_OUTPUT_RESERVE ))
    (( trigger > reserve_cap )) && trigger=$reserve_cap
    (( trigger < 1 )) && trigger=1
    ctx_pct=$(( used * 100 / trigger ))
    out+="${sep}$(build_bar "$ctx_pct" 8) ${orange}$(format_tokens "$used")/$(format_tokens "$trigger")${reset}"
fi

# --- rate limits (account-global; cache only papers over a missing reading) ---
# Rate-limit numbers are ACCOUNT-GLOBAL: every concurrent session's CC fetches
# the same 5h/7d figures, so a window's own live stdin reading is authoritative
# whenever it's present. The shared cache exists solely to fill in a bucket that
# this render's stdin happens to be missing — never to override a live reading.
#
# Per bucket: prefer the live local reading; fall back to cache only when local
# is absent. This recovers in BOTH directions — climbing and (as old requests
# age out of a rolling window) falling — and can never freeze the bar at a stale
# value. An earlier version keyed freshness on the larger resets_at, but
# resets_at is not a recency signal: one reading carrying a later reset would
# latch the bar (often at a WRONG value) until that future reset passed.
# Atomic mv, no lock; concurrent writers still converge.
local_rl=$(printf '%s' "$input" | jq -c '.rate_limits // {}' 2>/dev/null)
[ -z "$local_rl" ] && local_rl='{}'
cache_rl=$(jq -c '.' "$ratecache" 2>/dev/null)
[ -z "$cache_rl" ] && cache_rl='{}'

merged=$(jq -n \
    --argjson cache "$cache_rl" \
    --argjson local "$local_rl" \
    --argjson now "$(date +%s)" '
    # live local wins when present; cache only fills a missing bucket
    def fresher(cached; live):
      if (live == null or live == {}) then cached else live end;
    {
      five_hour: fresher($cache.five_hour; $local.five_hour),
      seven_day: fresher($cache.seven_day; $local.seven_day),
      updated_at: $now
    }')

# Persist unless there is genuinely nothing to record (no local, no cache).
if [ "$local_rl" != "{}" ] || [ "$cache_rl" != "{}" ]; then
    printf '%s' "$merged" > "$ratecache.$$" && mv -f "$ratecache.$$" "$ratecache"
fi

five_pct=$(printf '%s' "$merged" | jq -r '.five_hour.used_percentage // empty' 2>/dev/null)
if [ -n "$five_pct" ] && [ "$five_pct" != "null" ]; then
    five_int=$(printf "%.0f" "$five_pct" 2>/dev/null || echo 0)
    out+="${sep}${yellow}5h${reset} $(build_bar "$five_int" 6) ${cyan}${five_int}%${reset}"
    five_reset=$(printf '%s' "$merged" | jq -r '.five_hour.resets_at // empty' 2>/dev/null)
    if [ -n "$five_reset" ] && [ "$five_reset" != "null" ]; then
        epoch=$(to_epoch "$five_reset")
        [ -n "$epoch" ] && out+=" ${dim}in $(time_until "$epoch")${reset}"
    fi
fi

seven_pct=$(printf '%s' "$merged" | jq -r '.seven_day.used_percentage // empty' 2>/dev/null)
if [ -n "$seven_pct" ] && [ "$seven_pct" != "null" ]; then
    seven_int=$(printf "%.0f" "$seven_pct" 2>/dev/null || echo 0)
    seven_reset=$(printf '%s' "$merged" | jq -r '.seven_day.resets_at // empty' 2>/dev/null)
    out+="${sep}${blue}7d${reset} $(build_bar "$seven_int" 6) ${cyan}${seven_int}%${reset}"
    if [ -n "$seven_reset" ] && [ "$seven_reset" != "null" ]; then
        reset_epoch=$(to_epoch "$seven_reset")
        if [ -n "$reset_epoch" ]; then
            week_start=$(( reset_epoch - 7 * 86400 ))
            elapsed=$(( $(date +%s) - week_start ))
            week_pct=$(( elapsed * 100 / (7 * 86400) ))
            (( week_pct > 100 )) && week_pct=100
            delta=$(( seven_int - week_pct ))
            if (( delta >= 0 )); then
                pace_str="+${delta}%"
                (( delta >= 10 )) && pace_color=$red || pace_color=$cyan
            else
                pace_str="${delta}%"
                (( delta <= -10 )) && pace_color=$green || pace_color=$cyan
            fi
            out+=" ${pace_color}${pace_str}${reset}"
        fi
    fi
fi

printf "%b" "$out"
