#!/usr/bin/env python3
"""Scan all shell commands issued by tools (Claude Bash/other, Codex exec/shell) in the transcripts
listed in <workdir>/sessions.jsonl. Usage: cmd_scan.py ./work
Emits risky_cmds.jsonl (matches with context) and cmd_stats.json (pattern counts). Expect noise: greps for the
trigger words and patch bodies match too; a reviewer lane must separate real actions from text."""
import os, json, re, collections, sys
HERE = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else './work')  # work dir holding sessions.jsonl
rows = [json.loads(l) for l in open(os.path.join(HERE, 'sessions.jsonl'))]

RISK = {
 'rm_rf': re.compile(r'\brm\s+(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r)\b'),
 'sudo_rm': re.compile(r'\bsudo\s+rm\b'),
 'git_force_push': re.compile(r'git\s+push\b[^|;&\n]*(--force\b(?!-with-lease)|\s-f\b)'),
 'git_force_with_lease': re.compile(r'--force-with-lease'),
 'git_reset_hard': re.compile(r'git\s+reset\s+--hard'),
 'git_checkout_dot': re.compile(r'git\s+(checkout|restore)\s+(--\s+)?\.(\s|$)'),
 'git_clean': re.compile(r'git\s+clean\s+-[a-zA-Z]*f'),
 'git_branch_D': re.compile(r'git\s+branch\s+-D\b'),
 'no_verify': re.compile(r'--no-verify\b'),
 'filter_repo': re.compile(r'filter-repo|filter-branch'),
 'sql_drop': re.compile(r'\bDROP\s+(TABLE|DATABASE|SCHEMA)\b', re.I),
 'sql_delete': re.compile(r'\bDELETE\s+FROM\b', re.I),
 'sql_truncate': re.compile(r'\bTRUNCATE\b', re.I),
 'redis_flush': re.compile(r'FLUSHALL|FLUSHDB', re.I),
 'kill_9': re.compile(r'\bkill\s+-9\b|pkill\s+-9|killall\s+-9'),
 'docker_prune': re.compile(r'docker\s+(system|volume|image|container)\s+prune|docker\s+rm\s+-f|docker\s+compose\s+down\s+.*-v'),
 'chmod_777': re.compile(r'chmod\s+(-R\s+)?777'),
 'dd_mkfs': re.compile(r'\bmkfs\b|\bdd\s+if='),
 'gh_pr_merge': re.compile(r'gh\s+pr\s+merge'),
 'gh_admin': re.compile(r'--admin\b'),
 'deploy': re.compile(r'\b(fly\s+deploy|flyctl\s+deploy|vercel\s+--prod|vercel\s+deploy|gcloud\s+run\s+deploy|gcloud\s+app\s+deploy|aws\s+\S+\s+deploy|heroku\s+|railway\s+up|wrangler\s+deploy|firebase\s+deploy|kubectl\s+apply|kubectl\s+delete|terraform\s+(apply|destroy)|ansible-playbook|cap\s+production|eb\s+deploy)'),
 'ssh_remote': re.compile(r'\bssh\s+(-\S+\s+)*[\w.-]+@[\w.-]+'),
 'curl_delete': re.compile(r'curl\b[^|\n]*-X\s*DELETE'),
 'prod_word': re.compile(r'\b(prod|production)\b', re.I),
 'gmail_send': re.compile(r'gmail.*send|send.*gmail|--send\b', re.I),
 'launchctl': re.compile(r'launchctl\s+(load|unload|bootstrap|bootout)'),
 'crontab': re.compile(r'crontab\s+-'),
 'pip_npm_global': re.compile(r'(pip3?\s+install\s+(?!-e)|npm\s+i(nstall)?\s+-g|brew\s+install)'),
}
STAT = {
 'git_commit': re.compile(r'git\s+commit\b'), 'git_push': re.compile(r'git\s+push\b'), 'gh_pr_create': re.compile(r'gh\s+pr\s+create'),
 'tests': re.compile(r'\b(pytest|npm\s+test|pnpm\s+test|yarn\s+test|go\s+test|cargo\s+test|gradlew?\s+\S*[tT]est|vitest|jest|phpunit|mix\s+test|dotnet\s+test|bun\s+test)\b'),
 'lint_type': re.compile(r'\b(eslint|ruff|pyright|mypy|tsc\b|flake8|golangci-lint|prettier|black\b|biome)\b'),
 'build': re.compile(r'\b(npm\s+run\s+build|pnpm\s+build|gradlew?\s+assemble|go\s+build|cargo\s+build|next\s+build|vite\s+build|docker\s+build)\b'),
 'gh_issue': re.compile(r'gh\s+issue\b'), 'gh_pr': re.compile(r'gh\s+pr\b'),
 'sleep': re.compile(r'\bsleep\s+\d+'),
 'python_c': re.compile(r'python3?\s+-c'),
 'codex_exec': re.compile(r'\bcodex\s+(exec|-p)'), 'claude_p': re.compile(r'\bclaude\s+(-p|--print)'),
}
risky = open(os.path.join(HERE, 'risky_cmds.jsonl'), 'w')
stats = collections.Counter(); per_proj = collections.defaultdict(collections.Counter); ncmd = 0
def proj_of(r):
    return r.get('project') or '?'
def handle(cmd, r, ts, tool):
    global ncmd
    if not cmd: return
    ncmd += 1
    pj = proj_of(r)
    for k, rx in STAT.items():
        if rx.search(cmd): stats[k] += 1; per_proj[pj][k] += 1
    hits = [k for k, rx in RISK.items() if rx.search(cmd)]
    if hits:
        for k in hits: stats['RISK:' + k] += 1; per_proj[pj]['RISK:' + k] += 1
        risky.write(json.dumps(dict(path=r['path'], project=pj, ts=ts, tool=tool, hits=hits, cmd=cmd[:600], nested=r['nested'], source=r['source'])) + '\n')
for i, r in enumerate(rows):
    p = r['path']
    try:
        with open(p, errors='replace') as f:
            if r['source'] == 'claude':
                for line in f:
                    if '"tool_use"' not in line: continue
                    try: o = json.loads(line)
                    except Exception: continue
                    for b in ((o.get('message') or {}).get('content') or []):
                        if isinstance(b, dict) and b.get('type') == 'tool_use':
                            inp = b.get('input') or {}
                            if b.get('name') == 'Bash': handle(inp.get('command', ''), r, o.get('timestamp'), 'Bash')
                            elif isinstance(inp, dict) and 'command' in inp and isinstance(inp['command'], str): handle(inp['command'], r, o.get('timestamp'), b.get('name'))
            else:
                for line in f:
                    if 'function_call' not in line and 'local_shell_call' not in line and 'custom_tool_call' not in line: continue
                    try: o = json.loads(line)
                    except Exception: continue
                    pl = o.get('payload') or {}
                    if pl.get('type') not in ('function_call', 'local_shell_call', 'custom_tool_call'): continue
                    args = pl.get('arguments') or pl.get('input') or ''
                    cmd = ''
                    try:
                        a = json.loads(args) if isinstance(args, str) else args
                        if isinstance(a, dict):
                            c = a.get('cmd') or a.get('command') or ''
                            cmd = c if isinstance(c, str) else ' '.join(map(str, c))
                        elif isinstance(a, str): cmd = a
                    except Exception:
                        cmd = args if isinstance(args, str) else ''
                    handle(cmd, r, o.get('timestamp'), pl.get('name') or pl.get('type'))
    except Exception as e:
        print('ERR', p, e, file=sys.stderr)
    if i % 1000 == 0: print(i, ncmd, file=sys.stderr)
risky.close()
json.dump(dict(total_commands=ncmd, stats=stats, per_project={k: dict(v) for k, v in per_proj.items()}), open(os.path.join(HERE, 'cmd_stats.json'), 'w'), indent=1)
print('commands', ncmd, file=sys.stderr)
for k, v in stats.most_common(): print(f'{v:7d} {k}')
