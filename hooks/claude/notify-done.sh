#!/bin/bash

STDIN_DATA=$(cat)

[ "${CI:-}" = "true" ] && exit 0

# Skip non-interactive (-p/--print)
_ppid=$PPID
for _i in 1 2 3 4 5 6; do
    [ "${_ppid:-1}" -le 1 ] && break
    _args=$(ps -p "$_ppid" -o args= 2>/dev/null) || break
    if printf '%s' "$_args" | grep -qE '\bclaude\b'; then
        printf '%s' "$_args" | grep -qE '(^| )(-p|--print)( |$)' && exit 0
        break
    fi
    _ppid=$(ps -p "$_ppid" -o ppid= 2>/dev/null | tr -d ' ')
done

# Only notify when Claude has a question
TRANSCRIPT=$(printf '%s' "$STDIN_DATA" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d.get('transcript_path',''))" 2>/dev/null)

[ -z "$TRANSCRIPT" ] || [ ! -f "$TRANSCRIPT" ] && exit 0

python3 - "$TRANSCRIPT" <<'EOF' || exit 0
import sys, json

with open(sys.argv[1]) as f:
    lines = [l.strip() for l in f if l.strip()]

last_assistant = None
for line in reversed(lines):
    try:
        msg = json.loads(line)
        if msg.get('type') == 'assistant':
            last_assistant = msg.get('message', msg)
            break
    except Exception:
        continue

if not last_assistant:
    sys.exit(1)

content = last_assistant.get('content', '')
if isinstance(content, list):
    for block in content:
        if isinstance(block, dict) and block.get('type') == 'tool_use' and block.get('name') == 'AskUserQuestion':
            sys.exit(0)
    text = ' '.join(b.get('text', '') for b in content if isinstance(b, dict) and b.get('type') == 'text')
else:
    text = str(content)

sys.exit(0 if text.strip().endswith('?') else 1)
EOF

# Find the controlling terminal from the process tree
_tty=""
_pid=$$
while [ "$_pid" -gt 1 ]; do
    _t=$(ps -p "$_pid" -o tty= 2>/dev/null | tr -d ' ')
    if [ -n "$_t" ] && [ "$_t" != "??" ]; then _tty="/dev/$_t"; break; fi
    _pid=$(ps -p "$_pid" -o ppid= 2>/dev/null | tr -d ' ')
done

[ -z "$_tty" ] && exit 0

printf '\a' > "$_tty"
