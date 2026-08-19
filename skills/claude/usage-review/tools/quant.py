#!/usr/bin/env python3
"""Quant pass over local Claude Code + Codex transcripts (read-only on ~/.claude and ~/.codex).
Usage: quant.py --days 31 --out ./work   (writes work/sessions.jsonl, one row per transcript file)
Row fields: source, path, nested, project (short display name), project_dir (raw), session_id, first_ts/last_ts, models, tok{model:[in,cache_w,cache_r,out]},
user_turns, assistant_turns, tools, first_prompt (first 300 chars), interrupts, api_errors, cost_new, cost_full,
new_tokens, cache_read, out_tokens, originator/reasoning_effort (codex)."""
import os, sys, json, glob, time, collections, datetime as dt

import argparse
_ap = argparse.ArgumentParser(); _ap.add_argument('--days', type=int, default=31); _ap.add_argument('--out', default='./work')
_args = _ap.parse_args()
HOME = os.path.expanduser('~')
OUT = os.path.abspath(_args.out); os.makedirs(OUT, exist_ok=True)
CUT_TS = time.time() - _args.days * 86400
CUT_ISO = dt.datetime.fromtimestamp(CUT_TS, dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')

# list prices per M tokens: (input, output, cache_write, cache_read)
PRICE = {
    'opus': (15, 75, 18.75, 1.5), 'fable': (15, 75, 18.75, 1.5), 'mythos': (15, 75, 18.75, 1.5),
    'sonnet': (3, 15, 3.75, 0.3), 'haiku': (1, 5, 1.25, 0.1),
    'gpt-5': (1.25, 10, 1.25, 0.125),  # codex family, rough
}
def price_for(model):
    m = (model or '').lower()
    for k, v in PRICE.items():
        if k in m: return v
    return (15, 75, 18.75, 1.5)

def text_of(content):
    if isinstance(content, str): return content
    out = []
    for b in content or []:
        if isinstance(b, dict) and b.get('type') == 'text': out.append(b.get('text', ''))
    return '\n'.join(out)

def is_real_user_text(t):
    if not t: return False
    s = t.strip()
    if s.startswith('<local-command') or s.startswith('<command-name>') or s.startswith('<system-reminder>'): return False
    if s.startswith('<task-notification>') or s.startswith('[Request interrupted'): return False
    if s.startswith('<bash-input>') or s.startswith('<bash-stdout') or s.startswith('<user-memory-input>'): return False
    return True

def project_name(cwd, fallback):
    """Short display name: basename of cwd; a worktree checkout (<name>-worktrees/<x>) maps to <name>."""
    if not cwd:
        return fallback
    parent, base = os.path.split(cwd.rstrip('/'))
    pb = os.path.basename(parent)
    return pb[:-len('-worktrees')] if pb.endswith('-worktrees') else base

def parse_claude(path, nested=False):
    project_dir = path.split('/.claude/projects/')[1].split('/')[0] if '/.claude/projects/' in path else os.path.basename(os.path.dirname(path))
    r = dict(source='claude', path=path, nested=nested, project=project_dir, project_dir=project_dir,
             session_id=os.path.basename(path)[:-6], first_ts=None, last_ts=None, models=collections.Counter(),
             tok=collections.defaultdict(lambda: [0, 0, 0, 0]),  # model -> in, cache_w, cache_r, out
             user_turns=0, assistant_turns=0, tools=collections.Counter(), sidechain_lines=0, api_errors=0,
             interrupts=0, first_prompt='', first_prompt_len=0, user_prompt_chars=0, short_openers=0,
             plan_mode=0, effort_words=0, git_branch=None, cwd=None, cost_new=0.0, cost_full=0.0,
             lines=0, summary_title=None, bytes=os.path.getsize(path))
    seen_first_user = False
    with open(path, 'r', errors='replace') as f:
        for line in f:
            r['lines'] += 1
            try: o = json.loads(line)
            except Exception: continue
            t = o.get('type')
            ts = o.get('timestamp')
            if ts:
                if r['first_ts'] is None or ts < r['first_ts']: r['first_ts'] = ts
                if r['last_ts'] is None or ts > r['last_ts']: r['last_ts'] = ts
            if o.get('cwd') and not r['cwd']: r['cwd'] = o['cwd']
            if o.get('gitBranch') and not r['git_branch']: r['git_branch'] = o['gitBranch']
            if t == 'summary' and not r['summary_title']: r['summary_title'] = o.get('summary')
            if o.get('isSidechain'): r['sidechain_lines'] += 1
            msg = o.get('message') or {}
            if t == 'user':
                c = msg.get('content')
                if isinstance(c, list) and c and isinstance(c[0], dict) and c[0].get('type') == 'tool_result':
                    continue
                txt = text_of(c)
                if is_real_user_text(txt):
                    r['user_turns'] += 1
                    r['user_prompt_chars'] += len(txt)
                    if not seen_first_user:
                        seen_first_user = True
                        r['first_prompt'] = txt[:300]
                        r['first_prompt_len'] = len(txt)
                        if len(txt) < 60: r['short_openers'] = 1
                    low = txt.lower()
                    if 'plan mode' in low or 'enterplanmode' in low or low.startswith('/plan'): r['plan_mode'] += 1
                    if 'ultrathink' in low or 'think harder' in low or 'think hard' in low: r['effort_words'] += 1
                if '[Request interrupted' in (txt or ''): r['interrupts'] += 1
            elif t == 'assistant':
                r['assistant_turns'] += 1
                model = msg.get('model') or 'unknown'
                r['models'][model] += 1
                u = msg.get('usage') or {}
                tk = r['tok'][model]
                tk[0] += u.get('input_tokens', 0) or 0
                tk[1] += u.get('cache_creation_input_tokens', 0) or 0
                tk[2] += u.get('cache_read_input_tokens', 0) or 0
                tk[3] += u.get('output_tokens', 0) or 0
                for b in msg.get('content') or []:
                    if isinstance(b, dict) and b.get('type') == 'tool_use':
                        r['tools'][b.get('name', '?')] += 1
                if o.get('isApiErrorMessage'): r['api_errors'] += 1
    r['project'] = project_name(r['cwd'], project_dir)
    for model, tk in r['tok'].items():
        p = price_for(model)
        r['cost_new'] += (tk[0] * p[0] + tk[1] * p[2] + tk[3] * p[1]) / 1e6
        r['cost_full'] += (tk[0] * p[0] + tk[1] * p[2] + tk[2] * p[3] + tk[3] * p[1]) / 1e6
    r['models'] = dict(r['models']); r['tools'] = dict(r['tools']); r['tok'] = dict(r['tok'])
    r['new_tokens'] = sum(v[0] + v[1] + v[3] for v in r['tok'].values())
    r['cache_read'] = sum(v[2] for v in r['tok'].values())
    r['out_tokens'] = sum(v[3] for v in r['tok'].values())
    return r

def parse_codex(path):
    r = dict(source='codex', path=path, nested=False, project=None, project_dir=None, session_id=None, first_ts=None, last_ts=None,
             models=collections.Counter(), tok={}, user_turns=0, assistant_turns=0, tools=collections.Counter(),
             sidechain_lines=0, api_errors=0, interrupts=0, first_prompt='', first_prompt_len=0, user_prompt_chars=0,
             short_openers=0, plan_mode=0, effort_words=0, git_branch=None, cwd=None, cost_new=0.0, cost_full=0.0,
             lines=0, summary_title=None, bytes=os.path.getsize(path), originator=None, reasoning_effort=None)
    last_total = None; model = None; seen_first = False
    with open(path, 'r', errors='replace') as f:
        for line in f:
            r['lines'] += 1
            try: o = json.loads(line)
            except Exception: continue
            ts = o.get('timestamp')
            if ts:
                if r['first_ts'] is None or ts < r['first_ts']: r['first_ts'] = ts
                if r['last_ts'] is None or ts > r['last_ts']: r['last_ts'] = ts
            t = o.get('type'); p = o.get('payload') or {}
            if t == 'session_meta':
                r['session_id'] = p.get('id'); r['cwd'] = p.get('cwd'); r['originator'] = p.get('originator')
                r['project_dir'] = p.get('cwd'); r['project'] = project_name(p.get('cwd'), '?')
            elif t == 'turn_context':
                model = p.get('model') or model
                r['reasoning_effort'] = p.get('effort') or r['reasoning_effort']
                if model: r['models'][model] += 1
            elif t == 'response_item':
                pt = p.get('type')
                if pt == 'message':
                    role = p.get('role')
                    if role == 'user':
                        txt = '\n'.join(b.get('text', '') for b in p.get('content') or [] if isinstance(b, dict))
                        s = txt.strip()
                        if s.startswith('# AGENTS.md') or s.startswith('<environment_context>') or s.startswith('<INSTRUCTIONS>') or not s: continue
                        r['user_turns'] += 1; r['user_prompt_chars'] += len(s)
                        if not seen_first:
                            seen_first = True; r['first_prompt'] = s[:300]; r['first_prompt_len'] = len(s)
                            if len(s) < 60: r['short_openers'] = 1
                        low = s.lower()
                        if 'ultrathink' in low or 'think harder' in low: r['effort_words'] += 1
                    elif role == 'assistant':
                        r['assistant_turns'] += 1
                elif pt in ('function_call', 'custom_tool_call', 'local_shell_call'):
                    r['tools'][p.get('name') or pt] += 1
            elif t == 'event_msg' and p.get('type') == 'token_count':
                info = p.get('info') or {}
                if info.get('total_token_usage'): last_total = info['total_token_usage']
            elif t == 'event_msg' and p.get('type') == 'turn_aborted':
                r['interrupts'] += 1
            elif t == 'event_msg' and p.get('type') == 'error':
                r['api_errors'] += 1
    m = model or 'gpt-5?'
    if last_total:
        inp = last_total.get('input_tokens', 0); cached = last_total.get('cached_input_tokens', 0)
        cw = last_total.get('cache_write_input_tokens', 0); out = last_total.get('output_tokens', 0)
        r['tok'] = {m: [max(inp - cached, 0), cw, cached, out]}
        pr = price_for('gpt-5')
        r['cost_new'] = ((inp - cached) * pr[0] + cw * pr[2] + out * pr[1]) / 1e6
        r['cost_full'] = r['cost_new'] + cached * pr[3] / 1e6
    r['models'] = dict(r['models']); r['tools'] = dict(r['tools'])
    r['new_tokens'] = sum(v[0] + v[1] + v[3] for v in r['tok'].values())
    r['cache_read'] = sum(v[2] for v in r['tok'].values())
    r['out_tokens'] = sum(v[3] for v in r['tok'].values())
    return r

def main():
    files = []
    for p in glob.glob(HOME + '/.claude/projects/*/*.jsonl'):
        if os.stat(p).st_mtime >= CUT_TS: files.append(('claude', p, False))
    for p in glob.glob(HOME + '/.claude/projects/*/*/**/*.jsonl', recursive=True):
        if os.stat(p).st_mtime >= CUT_TS: files.append(('claude', p, True))
    for p in glob.glob(HOME + '/.codex/sessions/**/*.jsonl', recursive=True):
        if os.stat(p).st_mtime >= CUT_TS: files.append(('codex', p, False))
    print('files', len(files), file=sys.stderr)
    out = open(os.path.join(OUT, 'sessions.jsonl'), 'w')
    t0 = time.time()
    for i, (src, p, nested) in enumerate(files):
        try:
            r = parse_claude(p, nested) if src == 'claude' else parse_codex(p)
        except Exception as e:
            print('ERR', p, e, file=sys.stderr); continue
        # keep only sessions with activity inside the window
        if r['last_ts'] and r['last_ts'][:19] < CUT_ISO: continue
        out.write(json.dumps(r) + '\n')
        if i % 500 == 0: print(i, round(time.time() - t0), 's', file=sys.stderr)
    out.close()
    print('done', round(time.time() - t0), 's', file=sys.stderr)

if __name__ == '__main__':
    main()
