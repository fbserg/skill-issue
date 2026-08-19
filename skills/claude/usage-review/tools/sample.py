#!/usr/bin/env python3
"""Stratified sample selection over work/sessions.jsonl (+ families.json from summarize.py).
Usage: sample.py ./work [--per-lane 8] [--grade-n 50] [--projects 6]

Writes into the work dir:
  select.json  [{path, tag, budget?}] — input to render.py; tag = lane directory name
  lanes.json   [{key, dir, extra}]    — lane list for workflows/lanes.js, with the corpus numbers each lane needs

Rules (METHODOLOGY.md §2.4): stratify, do not cherry-pick. Per project: largest / median / most recent thirds.
Automation families and 0-user-turn sessions are excluded from human lanes; two of each family go to
lane-automation. Theme lanes get targeted pulls (top cost, API errors, interrupts, short/long openers,
biggest sub-agent fan-out + one child each, Codex TUI vs headless).
"""
import os, sys, json, argparse, collections


def thirds(rows, n):
    """largest, median-ish, most recent — n items total, deduped, order preserved."""
    if not rows or n <= 0:
        return []
    by_cost = sorted(rows, key=lambda r: -r['cost_full'])
    by_time = sorted(rows, key=lambda r: r['first_ts'] or '', reverse=True)
    mid = sorted(rows, key=lambda r: r['cost_full'])
    k = max(1, n // 3)
    med = mid[len(mid) // 2 - k // 2: len(mid) // 2 - k // 2 + k] if len(mid) > k else mid
    picked, seen = [], set()
    for r in by_cost[:k] + med + by_time[:n - 2 * k]:
        if r['path'] not in seen:
            seen.add(r['path']); picked.append(r)
    return picked[:n]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('work')
    ap.add_argument('--per-lane', type=int, default=8)
    ap.add_argument('--grade-n', type=int, default=50)
    ap.add_argument('--projects', type=int, default=6, help='number of per-project lanes; the rest are grouped')
    a = ap.parse_args()
    rows = [json.loads(l) for l in open(os.path.join(a.work, 'sessions.jsonl'))]
    fams = json.load(open(os.path.join(a.work, 'families.json'))) if os.path.exists(os.path.join(a.work, 'families.json')) else {}
    fam_paths = {p for v in fams.values() for p in v}
    top = [r for r in rows if not r['nested']]
    nested = [r for r in rows if r['nested']]
    human = [r for r in top if r['path'] not in fam_paths and r['user_turns'] >= 1]
    money = lambda x: f"${x:,.0f}"
    sel, lanes = [], []
    seen_tags = collections.defaultdict(set)

    def add(r, tag, budget=None):
        if r['path'] in seen_tags[tag]:
            return
        seen_tags[tag].add(r['path'])
        item = {'path': r['path'], 'tag': tag}
        if budget:
            item['budget'] = budget
        sel.append(item)

    # per-project lanes
    by_proj = collections.defaultdict(list)
    for r in human:
        by_proj[r.get('project') or '?'].append(r)
    ranked = sorted(by_proj.items(), key=lambda kv: -sum(r['cost_full'] for r in kv[1]))
    for proj, rs in ranked[:a.projects]:
        key = 'proj-' + proj.strip('-').replace('/', '-')[-40:]
        for r in thirds(rs, a.per_lane):
            add(r, key)
        lanes.append({'key': key, 'dir': key, 'extra': f"Project lane: {proj}. In the window: {len(rs):,} human sessions, cost_full {money(sum(r['cost_full'] for r in rs))}, "
                      f"{sum(r['assistant_turns'] for r in rs):,} assistant turns, {sum(1 for r in rs if r['source']=='codex')} of them Codex. Assess what was worked on, how the human directs the AI, what worked, what did not, risk, and ranked concrete suggestions."})
    rest = [r for _proj, rs in ranked[a.projects:] for r in rs]
    if rest:
        for r in thirds(rest, a.per_lane):
            add(r, 'proj-other')
        lanes.append({'key': 'proj-other', 'dir': 'proj-other', 'extra': f"Project lane: the remaining {len(ranked)-a.projects} smaller projects grouped ({len(rest):,} human sessions, cost_full {money(sum(r['cost_full'] for r in rest))}). Same questions as a project lane; note per-project differences."})

    # theme lanes
    top_cost = sorted(human, key=lambda r: -r['cost_full'])
    for r in top_cost[:a.per_lane]:
        add(r, 'lane-waste')
    for r in sorted(human, key=lambda r: -r['api_errors'])[:3]:
        add(r, 'lane-waste')
    for r in [r for r in top if r['user_turns'] == 0][:2]:
        add(r, 'lane-waste', 12000)
    lanes.append({'key': 'lane-waste', 'dir': 'lane-waste', 'extra': f"Theme lane: WASTE AND FAILURE MODES. Files: the {a.per_lane} most expensive human sessions (top one {money(top_cost[0]['cost_full']) if top_cost else '$0'}), the sessions with most API errors, two 0-user-turn sessions. "
                  f"Human sessions in window: {len(human):,}, cost_full {money(sum(r['cost_full'] for r in human))}. Determine what each expensive session bought and where the cost came from (never-restarted context, retries, loops, over-parallelism); estimate what share is real waste; give the 5 highest-value fixes."})

    for r in top_cost[:a.per_lane // 2]:
        add(r, 'lane-verification')
    for r in sorted(human, key=lambda r: -sum(n for t, n in (r.get('tools') or {}).items() if t in ('Bash', 'exec_command', 'shell', 'local_shell_call')))[:a.per_lane // 2]:
        add(r, 'lane-verification')
    lanes.append({'key': 'lane-verification', 'dir': 'lane-verification', 'extra': "Theme lane: VERIFICATION AND RISK. Besides your directory, read <base>/risky_digest.md fully: a regex scan of every shell command in the window, grouped by pattern; MOST hits are noise (greps for the words, patch bodies, docs). Separate real destructive / production-touching / credential-exposing actions from noise and list the real ones with evidence. In the sampled sessions, are 'done'/'verified' claims backed by observed tests, exit codes, browser/DB/API checks? Count sessions that accept an unverified claim."})

    short_long = [r for r in human if r['short_openers'] and r['assistant_turns'] >= 8]
    for r in sorted(short_long, key=lambda r: -r['assistant_turns'])[:a.per_lane // 2]:
        add(r, 'lane-prompting')
    for r in sorted(human, key=lambda r: -r['first_prompt_len'])[:2]:
        add(r, 'lane-prompting')
    for r in sorted(human, key=lambda r: -r['interrupts'])[:a.per_lane // 2]:
        add(r, 'lane-prompting')
    lanes.append({'key': 'lane-prompting', 'dir': 'lane-prompting', 'extra': f"Theme lane: PROMPTING, FRONT-LOADING AND STEERING. Files: sessions opened with <60-char prompts that ran 8+ turns ({len(short_long):,} exist), the longest openers, the most-interrupted sessions (window totals: {sum(r['interrupts'] for r in human):,} interrupts, {sum(r['plan_mode'] for r in human):,} plan-mode mentions, {sum(r['effort_words'] for r in human):,} typed effort words). "
                  "Assess what arrives late that belonged in turn 1, how corrections are phrased, whether interrupts are productive, whether the assistant asks the right questions, and what an opening template for this person/team should contain."})

    parents = sorted(human, key=lambda r: -((r.get('tools') or {}).get('Agent', 0) + (r.get('tools') or {}).get('Workflow', 0) + (r.get('tools') or {}).get('spawn_agent', 0)))
    n_children = 0
    for r in parents[:a.per_lane // 2]:
        if not any(t in (r.get('tools') or {}) for t in ('Agent', 'Workflow', 'spawn_agent')):
            break
        add(r, 'lane-orchestration')
        parent_dir = r['path'][:-6]  # <session>.jsonl -> <session>/
        kids = [n for n in nested if n['path'].startswith(parent_dir + '/')]
        if kids:
            add(max(kids, key=lambda k: k['cost_full']), 'lane-orchestration-sub'); n_children += 1
    if 'lane-orchestration' in seen_tags:
        lanes.append({'key': 'lane-orchestration', 'dir': 'lane-orchestration', 'extra': f"Theme lane: ORCHESTRATION AND DELEGATION. Files: the parent sessions with the biggest sub-agent fan-out; also read <base>/md/lane-orchestration-sub/*.md ({n_children} representative sub-agent transcripts, one per parent). Window: {len(nested):,} sub-agent transcripts, cost_full {money(sum(r['cost_full'] for r in nested))}. "
                      "Assess quality of delegation prompts, whether the parent verifies sub-agent claims or takes them on faith, structured-output use, poll loops, duplicated lanes, and whether fan-out size matched the task."})

    codex = [r for r in human if r['source'] == 'codex']
    if codex:
        tui = [r for r in codex if not (r.get('originator') or '').startswith('codex_exec')]
        headless = [r for r in codex if (r.get('originator') or '').startswith('codex_exec')]
        for r in thirds(tui, a.per_lane * 2 // 3):
            add(r, 'lane-codex')
        for r in thirds(headless, a.per_lane // 3):
            add(r, 'lane-codex')
        eff = collections.Counter(r.get('reasoning_effort') or '?' for r in [x for x in top if x['source'] == 'codex'])
        lanes.append({'key': 'lane-codex', 'dir': 'lane-codex', 'extra': f"Theme lane: CODEX USAGE. Files: interactive Codex TUI sessions and headless codex_exec dispatches. Window: {len(codex):,} human Codex sessions, effort mix {dict(eff.most_common())}, {len(headless):,} headless. "
                      "Assess what Codex is used for versus Claude, how it is instructed, multi-agent use (spawn_agent/send_message payloads are opaque — say so), effort fit, failure modes."})

    if fams:
        for paths in fams.values():
            fam_rows = sorted((r for r in top if r['path'] in set(paths)), key=lambda r: -r['cost_full'])
            for r in fam_rows[:1] + fam_rows[len(fam_rows) // 2: len(fam_rows) // 2 + 1]:
                add(r, 'lane-automation', 12000)
        lanes.append({'key': 'lane-automation', 'dir': 'lane-automation', 'extra': f"Theme lane: AUTOMATION INVENTORY. Files: 2 short renders per automation family ({len(fams)} families, see <base>/automation.txt for counts and cost per family). "
                      "Assess model fit per family, prompt quality, output verification, sensitivity of data handled, failure modes, cost per run; recommend routing changes and which automations deserve tests."})

    # rubric-grade sample: human sessions only, per project proportional to its session count (min 1), cost-ranked order, capped at --grade-n
    left = a.grade_n
    for _proj, rs in ranked:
        if left <= 0:
            break
        per = min(left, max(1, round(a.grade_n * len(rs) / max(1, len(human)))))
        picked = thirds(rs, per)
        for r in picked:
            add(r, 'grade')
        left -= len(picked)
    json.dump(sel, open(os.path.join(a.work, 'select.json'), 'w'), indent=0)
    json.dump(lanes, open(os.path.join(a.work, 'lanes.json'), 'w'), indent=1)
    print(f"selected {len(sel)} renders across {len(seen_tags)} tags; {len(lanes)} lanes; grade sample {len(seen_tags['grade'])}", file=sys.stderr)


if __name__ == '__main__':
    main()
