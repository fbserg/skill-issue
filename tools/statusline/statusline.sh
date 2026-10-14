#!/usr/bin/env bash
set -f

input=$(cat)
[ -z "$input" ] && { printf "Claude"; exit 0; }

mkdir -p /tmp/claude
printf '%s' "$input" > /tmp/claude/statusline-last.json

# Rate-limit readings are stashed per ACCOUNT, in a durable location, because
# they are worth more than this bar. `.rate_limits` on stdin is the server's own
# 5h/7d utilization (Claude Code builds it straight from the
# anthropic-ratelimit-unified-* response headers), so every render hands us a
# free, authoritative reading for whichever account is driving this session --
# the same number burn_sweep.py otherwise spends an API call to fetch.
#
# One file per account uuid, not one shared file keyed by account: two sessions
# on different accounts would otherwise read-modify-write the same object and a
# lost update would silently blank an account's row on the dashboard. Separate
# files cannot clobber each other. /tmp is wrong for the same reason -- it is
# cleared on reboot, and the sweep may be the next thing to read this.
ratecache_dir="$HOME/.config/burn/statusline-ratelimits"
account_config="${CLAUDE_CONFIG_DIR:+$CLAUDE_CONFIG_DIR/}"
account_config="${account_config:-$HOME/}.claude.json"
account_uuid=$(jq -r '.oauthAccount.accountUuid // "unknown"' "$account_config" 2>/dev/null)
[ -z "$account_uuid" ] && account_uuid=unknown
mkdir -p "$ratecache_dir"
ratecache="$ratecache_dir/$account_uuid.json"

blue='\033[38;2;0;153;255m'
orange='\033[38;2;255;176;85m'
green='\033[38;2;0;160;0m'
cyan='\033[38;2;46;149;153m'
red='\033[38;2;255;85;85m'
yellow='\033[38;2;230;200;0m'
magenta='\033[38;2;255;100;255m'
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

# healthy = dim; color only appears as a threshold alarm
pct_color() {
    if (( $1 >= 90 )); then printf '%s' "$red"
    elif (( $1 >= 70 )); then printf '%s' "$yellow"
    elif (( $1 >= 50 )); then printf '%s' "$orange"
    else printf '%s' "$green"
    fi
}

# agent-hud-style labeled bar: bg-colored fill, label overlaid flush-right;
# black text on the fill, light gray on the empty track
build_labeled_bar() {
    local pct=$1 width=$2 label=$3
    (( pct < 0 )) && pct=0
    (( pct > 100 )) && pct=100
    local -a partials=("" "▏" "▎" "▍" "▌" "▋" "▊" "▉")
    local total_eighths=$(( pct * width * 8 / 100 ))
    local full=$(( total_eighths / 8 ))
    local frac=$(( total_eighths % 8 ))
    local fill_fg
    fill_fg=$(pct_color "$pct")
    local fill_bg=${fill_fg/38;2/48;2}
    local track_bg='\033[48;2;58;58;58m'
    local on_fill='\033[38;2;20;20;20m'
    local on_track='\033[38;2;170;170;170m'
    local start=$(( width - ${#label} ))
    local bar="" i c
    for (( i=0; i<width; i++ )); do
        c=""
        (( i >= start )) && c=${label:$(( i - start )):1}
        if (( i < full )); then
            bar+="${fill_bg}${on_fill}${c:- }"
        elif (( i == full )) && (( frac > 0 )) && [ -z "$c" ]; then
            bar+="${track_bg}${fill_fg}${partials[$frac]}"
        else
            bar+="${track_bg}${on_track}${c:- }"
        fi
    done
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
    # coarse on purpose: floor to whole hours, understating a deadline is harmless
    (( mins >= 60 )) && echo "$(( mins / 60 ))h" || echo "${mins}m"
}

sep="  "
out=""

# --- repo@branch ---
cwd=$(printf '%s' "$input" | jq -r '.workspace.current_dir // .cwd // empty')
if [ -n "$cwd" ]; then
    repo="${cwd##*/}"
    git_branch=$(GIT_OPTIONAL_LOCKS=0 git -C "$cwd" rev-parse --abbrev-ref HEAD 2>/dev/null)
    dirty=$(GIT_OPTIONAL_LOCKS=0 git -C "$cwd" status --porcelain 2>/dev/null | head -1)
    if [ -n "$git_branch" ] && [ "$git_branch" != "HEAD" ]; then
        (( ${#git_branch} > 18 )) && git_branch="${git_branch:0:9}…${git_branch: -8}"
        branch_sfx="" branch_color=$green
        [ -n "$dirty" ] && branch_sfx="*" && branch_color=$yellow
        out+="${cyan}${repo}${reset} ${branch_color}${git_branch}${branch_sfx}${reset}"
    elif [ "$git_branch" = "HEAD" ]; then
        sha=$(GIT_OPTIONAL_LOCKS=0 git -C "$cwd" rev-parse --short HEAD 2>/dev/null)
        out+="${cyan}${repo}${reset}${dim} @${sha}${reset}"
    else
        out+="${cyan}${repo}${reset}"
    fi
    # diff stat: +ins-del, no space between, rendered before drift arrows
    if [ -n "$dirty" ]; then
        diff_stat=$(GIT_OPTIONAL_LOCKS=0 git -C "$cwd" diff HEAD --numstat 2>/dev/null \
            | awk '{a+=$1; d+=$2} END {if(a||d) printf "%d %d",a,d}')
        if [ -n "$diff_stat" ]; then
            ins=${diff_stat%% *} del=${diff_stat##* }
            frag=""
            (( ins > 0 )) && frag+="${green}+${ins}${reset}"
            (( del > 0 )) && frag+="${red}-${del}${reset}"
            [ -n "$frag" ] && out+=" $frag"
        fi
    fi
    # drift vs trunk (agent-hud's ⇡⇣ arrows): ahead = unpushed/unmerged, behind = trunk moved on
    if [ -n "$git_branch" ] && [ "$git_branch" != "HEAD" ]; then
        trunk=$(GIT_OPTIONAL_LOCKS=0 git -C "$cwd" rev-parse --abbrev-ref origin/HEAD 2>/dev/null)
        if [ -z "$trunk" ]; then
            for c in origin/main origin/master main master; do
                GIT_OPTIONAL_LOCKS=0 git -C "$cwd" rev-parse --verify -q "$c" >/dev/null 2>&1 && { trunk=$c; break; }
            done
        fi
        if [ -n "$trunk" ]; then
            counts=$(GIT_OPTIONAL_LOCKS=0 git -C "$cwd" rev-list --left-right --count "$trunk...HEAD" 2>/dev/null)
            if [ -n "$counts" ]; then
                behind=${counts%%[[:space:]]*} ahead=${counts##*[[:space:]]}
                (( ahead > 0 )) && out+=" ${green}⇡${ahead}${reset}"
                (( behind > 0 )) && out+=" ${red}⇣${behind}${reset}"
            fi
        fi
    fi
fi

# --- model + effort ---
model_name=$(printf '%s' "$input" | jq -r '.model.display_name // empty')
effort_level=$(printf '%s' "$input" | jq -r '.effort.level // empty')
# shorten: "Opus 4.8" -> "opu", "Fable 5" -> "fab", "Sonnet 4.6" -> "son"
# (1M suffix dropped: auto-compact window is capped at 500k here anyway)
if [ -n "$model_name" ]; then
    model_name=$(printf '%s' "$model_name" | awk '{print tolower(substr($1,1,3))}')
fi
if [ -n "$model_name" ]; then
    if [ -n "$effort_level" ] && [ "$effort_level" != "null" ]; then
        # one plain letter keeps the segment one cell wide
        case "$effort_level" in
            xhigh)  effort_label="X" eff_color=$magenta ;;
            max)    effort_label="x" eff_color=$red ;;
            high)   effort_label="h" eff_color=$orange ;;
            medium) effort_label="m" eff_color=$yellow ;;
            low)    effort_label="l" eff_color=$green ;;
            *)      effort_label=$effort_level eff_color=$cyan ;;
        esac
        out+="${sep}${blue}${model_name}${reset}${dim}·${reset}${eff_color}${effort_label}${reset}"
    else
        out+="${sep}${blue}${model_name}${reset}"
    fi
fi

# --- context bar ---
size=$(printf '%s' "$input" | jq -r '.context_window.context_window_size // 0')
itok=$(printf '%s' "$input" | jq -r '.context_window.current_usage.input_tokens // 0')
ccr=$(printf '%s' "$input" | jq -r '.context_window.current_usage.cache_creation_input_tokens // 0')
crd=$(printf '%s' "$input" | jq -r '.context_window.current_usage.cache_read_input_tokens // 0')
used=$(( itok + ccr + crd ))

# Fill the bar toward the point where auto-compaction ACTUALLY fires, not the
# raw window. Re-derived from the 2.1.220 binary (functions aY / CSe / Sfo):
#   window    = env set ? min(rawWindow, clamp(env,100k,1M)) : rawWindow
#   effective = window - min(maxOutputTokens, 20000)      <- CSe()
#   trigger   = min( floor(effective * pct/100), effective - 13000 )   <- Sfo()
# TWO reserves stack, not one: a max-output reserve capped at 20k, then a fixed
# 13k on top. At pct=100 a configured 500k window really compacts at 467k, not
# 487k (the old comment here missed the 20k term). maxOutputTokens defaults to
# 32k on every current model, so the cap binds and 20k is right unless
# CLAUDE_CODE_MAX_OUTPUT_TOKENS is pushed below it.
# Not modelled: CC also arms a *precomputed* compact earlier, at
# effective*(1-0.2) = 384k, gated by the tengu_amber_rokovoko statsig — that
# summarizes in the background, so 467k stays the line the bar should track.
# We anchor on the raw window from stdin (already correct for 1M on/off) so the
# bar stays honest even when CLAUDE_CODE_AUTO_COMPACT_WINDOW is unset. NOTE: do
# NOT use stdin's context_window.used_percentage — CC computes that against the
# raw window, so it reads ~29% at the moment compaction fires. Useless here.
CTX_OUTPUT_RESERVE=13000          # fixed reserve below the effective window
CTX_MAX_OUTPUT_RESERVE=20000      # min(maxOutputTokens, 20k), subtracted first
window=$size
compact_env=${CLAUDE_CODE_AUTO_COMPACT_WINDOW:-0}
if (( compact_env > 0 )); then
    (( compact_env < 100000 )) && compact_env=100000
    (( compact_env > 1000000 )) && compact_env=1000000
    (( window == 0 || compact_env < window )) && window=$compact_env
fi
if (( window > 0 )); then
    pct_override=${CLAUDE_AUTOCOMPACT_PCT_OVERRIDE:-100}
    effective=$(( window - CTX_MAX_OUTPUT_RESERVE ))
    trigger=$(( effective * pct_override / 100 ))
    reserve_cap=$(( effective - CTX_OUTPUT_RESERVE ))
    (( trigger > reserve_cap )) && trigger=$reserve_cap
    (( trigger < 1 )) && trigger=1
    ctx_pct=$(( used * 100 / trigger ))
    out+="${sep}$(build_labeled_bar "$ctx_pct" 8 "${ctx_pct}%")"
fi

# --- prompt-cache leaf ---
# Countdown = minutes until the prompt cache goes cold, from Claude Code's own
# prompt_cache.expires_at; wilts once past it. Leaf colour = miss share of the
# last request's input.
cache_expires_at=$(printf '%s' "$input" | jq -r 'if .prompt_cache.caching_observed then .prompt_cache.expires_at // empty else empty end')
if (( used > 0 )) && [ -n "$cache_expires_at" ]; then
    expires_in=$(( cache_expires_at - $(date +%s) ))
    if (( expires_in <= 0 )); then
        out+=" 🥀"
    else
        miss_pct=$(( 100 - crd * 100 / used ))
        if (( miss_pct >= 50 )); then leaf="🔥"
        elif (( miss_pct >= 20 )); then leaf="🍂"
        else leaf="🌿"; fi
        out+=" ${leaf}${dim}$(( (expires_in + 59) / 60 ))m${reset}"
    fi
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
    --arg account "$account_uuid" \
    --argjson now "$(date +%s)" '
    # live local wins when present; cache only fills a missing bucket
    def fresher(cached; live):
      if (live == null or live == {}) then cached else live end;
    {
      account_uuid: $account,
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
    out+="${sep}${yellow}5h${reset}$(build_labeled_bar "$five_int" 8 "${five_int}%")"
    five_reset=$(printf '%s' "$merged" | jq -r '.five_hour.resets_at // empty' 2>/dev/null)
    if [ -n "$five_reset" ] && [ "$five_reset" != "null" ]; then
        epoch=$(to_epoch "$five_reset")
        [ -n "$epoch" ] && out+=" ${dim}↻$(time_until "$epoch")${reset}"
    fi
fi

seven_pct=$(printf '%s' "$merged" | jq -r '.seven_day.used_percentage // empty' 2>/dev/null)
if [ -n "$seven_pct" ] && [ "$seven_pct" != "null" ]; then
    seven_int=$(printf "%.0f" "$seven_pct" 2>/dev/null || echo 0)
    seven_reset=$(printf '%s' "$merged" | jq -r '.seven_day.resets_at // empty' 2>/dev/null)
    out+="${sep}${blue}7d${reset}$(build_labeled_bar "$seven_int" 8 "${seven_int}%")"
    if [ -n "$seven_reset" ] && [ "$seven_reset" != "null" ]; then
        reset_epoch=$(to_epoch "$seven_reset")
        if [ -n "$reset_epoch" ]; then
            week_start=$(( reset_epoch - 7 * 86400 ))
            elapsed=$(( $(date +%s) - week_start ))
            week_pct=$(( elapsed * 100 / (7 * 86400) ))
            (( week_pct > 100 )) && week_pct=100
            delta=$(( seven_int - week_pct ))
            if (( delta >= 10 )); then
                pace_str="↑${delta}" pace_color=$red
            elif (( delta >= 0 )); then
                pace_str="↑${delta}" pace_color=$yellow
            else
                pace_str="↓$(( -delta ))" pace_color=$green
            fi
            out+=" ${pace_color}${pace_str}${reset}"
        fi
    fi
fi

printf "%b" "$out"
