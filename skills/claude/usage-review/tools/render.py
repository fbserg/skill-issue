#!/usr/bin/env python3
"""Render selected raw transcripts (Claude jsonl / Codex rollout jsonl) to compact markdown
for lane reading + LLM grading. Usage:
  render.py --sessions sessions.jsonl --select select.json --outdir md/ --budget 50000 \
            --grade-jsonl grade_in.jsonl [--grade-tags grade] [--user NAME]
select.json: list of {"path":..., "tag": "...", "budget": <optional per-item char budget>}
(tag = lane/sample dir under --outdir). Only items whose tag is in --grade-tags (default: all)
are written to --grade-jsonl. Output stays local; the header of every render names the raw source file."""
import os, sys, json, argparse, getpass

def clip(s, n):
    s = s or ''
    return s if len(s) <= n else s[:n] + f' …[+{len(s)-n} chars]'

def arg_summary(name, inp):
    if not isinstance(inp, dict): return ''
    if name in ('Bash',): return clip(inp.get('command', ''), 160).replace('\n', ' ⏎ ')
    if name in ('Read', 'Write', 'Edit', 'MultiEdit', 'NotebookEdit'): return inp.get('file_path', '')
    if name in ('Grep', 'Glob'): return clip(str(inp.get('pattern', '')), 80) + ' ' + str(inp.get('path', '') or '')
    if name == 'Agent': return f"[{inp.get('subagent_type','')}] " + clip(inp.get('description', ''), 100)
    if name == 'Skill': return str(inp.get('skill', '')) + ' ' + clip(str(inp.get('args', '')), 60)
    if name == 'Workflow': return clip(str(inp.get('name') or inp.get('scriptPath') or 'inline script'), 80)
    if name == 'AskUserQuestion':
        qs = inp.get('questions') or []
        return clip(' | '.join(q.get('question', '') for q in qs if isinstance(q, dict)), 160)
    if name in ('WebFetch', 'WebSearch'): return clip(inp.get('url') or inp.get('query') or '', 100)
    if name in ('SendMessage',): return clip(f"to={inp.get('to')} {inp.get('message','') if isinstance(inp.get('message'),str) else ''}", 120)
    return clip(json.dumps(inp, ensure_ascii=False), 120)

def text_blocks(content):
    if isinstance(content, str): return content
    out = []
    for b in content or []:
        if isinstance(b, dict) and b.get('type') == 'text': out.append(b.get('text', ''))
    return '\n'.join(out)

def render_claude(path):
    lines = []; n_user = n_asst = n_tool = 0; title = None; first_ts = None; last_ts = None; model = None
    with open(path, errors='replace') as f:
        for line in f:
            try: o = json.loads(line)
            except Exception: continue
            t = o.get('type'); ts = o.get('timestamp')
            if ts:
                first_ts = first_ts or ts; last_ts = ts
            if t == 'summary' and not title: title = o.get('summary')
            msg = o.get('message') or {}
            side = ' (sub-agent)' if o.get('isSidechain') else ''
            if t == 'user':
                c = msg.get('content')
                if isinstance(c, list) and c and isinstance(c[0], dict) and c[0].get('type') == 'tool_result':
                    # summarise tool results by size + first line
                    for b in c:
                        if isinstance(b, dict) and b.get('type') == 'tool_result':
                            body = b.get('content')
                            txt = body if isinstance(body, str) else text_blocks(body)
                            first = (txt or '').strip().splitlines()[0][:120] if (txt or '').strip() else ''
                            err = ' ERROR' if b.get('is_error') else ''
                            lines.append(f"  ← result{err} ({len(txt or '')} chars) {first}")
                    continue
                txt = text_blocks(c)
                if not txt.strip(): continue
                s = txt.strip()
                if s.startswith('<system-reminder>') or s.startswith('<local-command-stdout>'): continue
                if s.startswith('<command-name>'):
                    lines.append(f"**User (slash):** {clip(s, 200)}"); n_user += 1; continue
                if s.startswith('<task-notification>') or s.startswith('<bash-stdout') or s.startswith('<bash-input>'):
                    lines.append(f"  [{clip(s, 160)}]"); continue
                n_user += 1
                lines.append(f"**User{side}** [{(ts or '')[11:16]}]: {clip(s, 3000)}")
            elif t == 'assistant':
                model = msg.get('model') or model
                n_asst += 1
                for b in msg.get('content') or []:
                    if not isinstance(b, dict): continue
                    if b.get('type') == 'text' and b.get('text', '').strip():
                        lines.append(f"**Assistant{side}:** {clip(b['text'].strip(), 2500)}")
                    elif b.get('type') == 'tool_use':
                        n_tool += 1
                        lines.append(f"→ used tool {b.get('name')}: {arg_summary(b.get('name'), b.get('input'))}")
                    elif b.get('type') == 'thinking':
                        pass
    return dict(lines=lines, n_user=n_user, n_assistant=n_asst, n_tool_calls=n_tool, title=title,
                first_ts=first_ts, last_ts=last_ts, model=model, source='claude')

def render_codex(path):
    lines = []; n_user = n_asst = n_tool = 0; first_ts = None; last_ts = None; model = None; cwd = None
    with open(path, errors='replace') as f:
        for line in f:
            try: o = json.loads(line)
            except Exception: continue
            t = o.get('type'); p = o.get('payload') or {}; ts = o.get('timestamp')
            if ts:
                first_ts = first_ts or ts; last_ts = ts
            if t == 'session_meta': cwd = p.get('cwd')
            elif t == 'turn_context': model = p.get('model') or model
            elif t == 'response_item':
                pt = p.get('type')
                if pt == 'message':
                    txt = '\n'.join(b.get('text', '') for b in p.get('content') or [] if isinstance(b, dict) and b.get('type') in ('input_text', 'output_text', 'text'))
                    s = txt.strip()
                    if not s: continue
                    if p.get('role') == 'user':
                        if s.startswith('# AGENTS.md') or s.startswith('<environment_context>') or s.startswith('<INSTRUCTIONS>'): continue
                        n_user += 1; lines.append(f"**User** [{(ts or '')[11:16]}]: {clip(s, 3000)}")
                    elif p.get('role') == 'assistant':
                        n_asst += 1; lines.append(f"**Assistant:** {clip(s, 2500)}")
                elif pt in ('function_call', 'custom_tool_call', 'local_shell_call'):
                    n_tool += 1
                    args = p.get('arguments') or p.get('input') or ''
                    try:
                        a = json.loads(args) if isinstance(args, str) else args
                        if isinstance(a, dict) and 'cmd' in a: args = a['cmd'] if isinstance(a['cmd'], str) else ' '.join(map(str, a['cmd']))
                    except Exception: pass
                    lines.append(f"→ used tool {p.get('name') or pt}: {clip(str(args), 160).replace(chr(10),' ⏎ ')}")
                elif pt in ('function_call_output', 'custom_tool_call_output'):
                    out = p.get('output') or ''
                    if isinstance(out, dict): out = json.dumps(out)
                    first = str(out).strip().splitlines()[0][:120] if str(out).strip() else ''
                    lines.append(f"  ← result ({len(str(out))} chars) {first}")
    return dict(lines=lines, n_user=n_user, n_assistant=n_asst, n_tool_calls=n_tool, title=None,
                first_ts=first_ts, last_ts=last_ts, model=model, source='codex', cwd=cwd)

def budget_text(text, budget):
    if len(text) <= budget: return text, False
    head = int(budget * 0.6); tail = budget - head
    return text[:head] + f"\n\n[… {len(text)-budget} chars elided …]\n\n" + text[-tail:], True

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sessions', required=True)
    ap.add_argument('--select', required=True)
    ap.add_argument('--outdir', required=True)
    ap.add_argument('--budget', type=int, default=60000)
    ap.add_argument('--grade-jsonl', default=None)
    ap.add_argument('--grade-tags', default=None, help='comma-separated tags to include in --grade-jsonl (default: all)')
    ap.add_argument('--user', default=getpass.getuser(), help='label stored in grade rows (a name, handle or "self")')
    a = ap.parse_args()
    grade_tags = set(a.grade_tags.split(',')) if a.grade_tags else None
    meta = {}
    for line in open(a.sessions):
        r = json.loads(line); meta[r['path']] = r
    sel = json.load(open(a.select))
    os.makedirs(a.outdir, exist_ok=True)
    gout = open(a.grade_jsonl, 'w') if a.grade_jsonl else None
    for item in sel:
        path = item['path']; m = meta.get(path, {})
        r = render_codex(path) if path.endswith('.jsonl') and '/.codex/' in path else render_claude(path)
        proj = m.get('project') or r.get('cwd') or ''
        title = r.get('title') or m.get('summary_title') or (m.get('first_prompt') or '')[:80].replace('\n', ' ')
        date = (r.get('first_ts') or m.get('first_ts') or '')[:10]
        hdr = (f"### {date} {(r.get('first_ts') or '')[11:16]}–{(r.get('last_ts') or '')[11:16]} · {r['source']} · {title}\n"
               f"project: {proj} · model: {r.get('model') or ','.join((m.get('models') or {}).keys())} · user turns {r['n_user']} · assistant turns {r['n_assistant']} · tool calls {r['n_tool_calls']} · new tokens {m.get('new_tokens')} · est ${m.get('cost_full',0):.2f} (full) / ${m.get('cost_new',0):.2f} (new)\n"
               f"source file: {path}\n\n")
        body = '\n'.join(r['lines'])
        text, clipped = budget_text(body, int(item.get('budget') or a.budget))
        tagdir = os.path.join(a.outdir, item.get('tag', 'misc')); os.makedirs(tagdir, exist_ok=True)
        base = f"{date}_{r['source']}_{os.path.basename(path)[8:36] if "rollout" in path else os.path.basename(path)[:16]}.md"
        with open(os.path.join(tagdir, base), 'w') as f: f.write(hdr + text + '\n')
        if gout and (grade_tags is None or item.get('tag') in grade_tags):
            gout.write(json.dumps(dict(user=a.user, date=date, path=path, line=0, project=proj, source=r['source'],
                                       session_id=m.get('session_id') or os.path.basename(path)[:-6], title=title,
                                       n_user=r['n_user'], n_assistant=r['n_assistant'], n_tool_calls=r['n_tool_calls'],
                                       chars=len(body), clipped=clipped, format='raw', text=text, tag=item.get('tag')), ensure_ascii=False) + '\n')
    if gout: gout.close()

if __name__ == '__main__':
    main()
