#!/usr/bin/env bash
# SessionStart: keep the Mac awake for as long as the claude CLI that spawned this hook lives.
# `-w` ties caffeinate to that pid, so it self-releases; no pidfile, no stop hook. No-op off macOS.
command -v caffeinate >/dev/null || exit 0
pid=$PPID
for _ in 1 2 3 4 5 6; do
  [[ "${pid:-1}" -le 1 ]] && exit 0
  ps -p "$pid" -o args= 2>/dev/null | grep -qE '\bclaude\b' && break
  pid=$(ps -p "$pid" -o ppid= 2>/dev/null | tr -d ' ')
done
caffeinate -i -w "$pid" </dev/null >/dev/null 2>&1 &
