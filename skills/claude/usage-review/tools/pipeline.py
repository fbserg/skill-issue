#!/usr/bin/env python3
"""One-shot runner for the local (Claude Code + Codex CLI) review pipeline, up to the point where a human or
an orchestrating agent takes over (lanes, draft, red team).

Usage:
  pipeline.py --days 31 [--work DIR] [--user NAME] [--grade] [--model sonnet] [--jobs 5] [--context FILE]

Steps (each tool can also be run alone; see METHODOLOGY.md §2):
  quant.py → cmd_scan.py → summarize.py → sample.py → render.py → risky_digest.py → [grade.py + digest.py] → secret_scan.py

Privacy contract, enforced here:
  * reads ~/.claude/projects and ~/.codex/sessions read-only; writes only into --work
  * --work defaults to ~/.local/share/usage-review/<UTC date>/ and MUST NOT be inside a git repository (work tree, bare repo or .git dir)
    (a report names projects, dollars and whatever people pasted; a stray `git add .` would publish it).
    The work dir gets a `.gitignore` containing `*` regardless.
  * nothing leaves the machine except, with --grade, clipped transcript renders sent to `claude -p`
    (your own Claude account/provider). Lanes and red team (run later, from Claude Code) do the same.
"""
import os, sys, json, argparse, subprocess, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))


def run(tool, *args):
    cmd = [sys.executable, os.path.join(HERE, tool), *map(str, args)]
    print('$', ' '.join(cmd), file=sys.stderr)
    subprocess.run(cmd, check=True)


def inside_git_repo(path):
    """True if the (possibly not yet existing) path is inside a git work tree, a bare repository, or a .git dir."""
    probe = path
    while not os.path.isdir(probe):
        probe = os.path.dirname(probe)
    for flag in ('--is-inside-work-tree', '--is-inside-git-dir', '--is-bare-repository'):
        r = subprocess.run(['git', '-C', probe, 'rev-parse', flag], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip() == 'true':
            return True
    d = probe
    while True:  # belt and braces: any ancestor that is itself a git dir (bare layout: HEAD + objects + refs)
        if os.path.exists(os.path.join(d, '.git')) or all(os.path.exists(os.path.join(d, x)) for x in ('HEAD', 'objects', 'refs')):
            return True
        parent = os.path.dirname(d)
        if parent == d:
            return False
        d = parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--days', type=int, default=31)
    ap.add_argument('--work', default=None, help='work dir (default ~/.local/share/usage-review/<date>); must not be inside a git repo')
    ap.add_argument('--user', default=None, help='label for grade rows (default: login name)')
    ap.add_argument('--grade', action='store_true', help='also sample, render and grade a rubric set (sends clipped renders to `claude -p`); without it no grade sample is made')
    ap.add_argument('--model', default='sonnet')
    ap.add_argument('--jobs', type=int, default=5)
    ap.add_argument('--context', default=None, help='grader context paragraph file (who, projects, conventions)')
    ap.add_argument('--budget', type=int, default=50000)
    ap.add_argument('--per-lane', type=int, default=8)
    ap.add_argument('--grade-n', type=int, default=50)
    a = ap.parse_args()

    work = os.path.realpath(a.work or os.path.expanduser(f"~/.local/share/usage-review/{dt.datetime.now(dt.timezone.utc):%Y-%m-%d}"))
    if inside_git_repo(work):
        sys.exit(f"refusing: work dir {work} is inside a git repository (work tree, bare repo or .git dir). Reports name projects, dollars and pasted secrets; "
                 "pick a --work outside any repo (default: ~/.local/share/usage-review/<date>).")
    os.makedirs(work, exist_ok=True)
    with open(os.path.join(work, '.gitignore'), 'w') as f:
        f.write('*\n')

    run('quant.py', '--days', a.days, '--out', work)
    run('cmd_scan.py', work)
    run('summarize.py', work)
    run('sample.py', work, '--per-lane', a.per_lane, '--grade-n', a.grade_n if a.grade else 0)
    render_args = ['--sessions', os.path.join(work, 'sessions.jsonl'), '--select', os.path.join(work, 'select.json'),
                   '--outdir', os.path.join(work, 'md'), '--budget', a.budget]
    if a.grade:
        render_args += ['--grade-jsonl', os.path.join(work, 'grade_in.jsonl'), '--grade-tags', 'grade']
    if a.user:
        render_args += ['--user', a.user]
    run('render.py', *render_args)
    run('risky_digest.py', work)
    if a.grade:
        grade_args = [os.path.join(work, 'grade_in.jsonl'), '--out', os.path.join(work, 'graded.jsonl'), '--model', a.model, '--jobs', a.jobs]
        if a.context:
            grade_args += ['--context', a.context]
        run('grade.py', *grade_args)
        with open(os.path.join(work, 'digest.md'), 'w') as f:
            subprocess.run([sys.executable, os.path.join(HERE, 'digest.py'), os.path.join(work, 'graded.jsonl')], check=True, stdout=f)
    scan = subprocess.run([sys.executable, os.path.join(HERE, 'secret_scan.py'), work], capture_output=True, text=True)
    high = [l for l in scan.stdout.splitlines() if l.startswith('HIGH')]

    lanes = json.load(open(os.path.join(work, 'lanes.json')))
    tz = dt.datetime.now().astimezone().strftime('%z')
    print(f"""
work dir: {work}   (.gitignore=* written; not inside a git repo)
files: sessions.jsonl quant_summary.txt automation.txt families.json select.json lanes.json md/<tag>/*.md
       risky_cmds.jsonl cmd_stats.json risky_digest.md window.json{' grade_in.jsonl graded.jsonl digest.md' if a.grade else '   (no grade sample; re-run with --grade to add one)'}
secret scan: {len(high)} HIGH findings in rendered/derived files{' — see below; renders quote transcripts verbatim, redact before anything is shared' if high else ''}
{chr(10).join(high[:20])}
next (from Claude Code, see SKILL.md):
  Workflow lanes.js  args = {{"base": "{work}", "who": "<one sentence: whose transcripts, what they do>", "tz": "{tz}", "lanes": <contents of lanes.json ({len(lanes)} lanes)>}}
  then write the draft, extract claims (examples/claims.example.json shape), run redteam.js with {{"base","who","tz","clusters"}}
""", file=sys.stderr)


if __name__ == '__main__':
    main()
