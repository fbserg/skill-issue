# skill-issue

Reusable agent skills and workflow helpers for Claude and Codex.

Agents: see [INDEX.md](INDEX.md) for a flat map of everything.

## Quickstart

```bash
# 1. Prerequisites
gh auth login   # GitHub CLI, authenticated

# 2. Clone and install
git clone https://github.com/fbserg/skill-issue
cd skill-issue
# Follow docs/install.md, or run the symlink commands in the Install section below.

# 3. Use
# In Claude Code or Codex, invoke:
/epic-plan "add dark mode to the settings page"
# The agent scopes and drafts a GitHub epic with child issues.
# Execute children via:
/resolve-issue <child-number>
```

## Skills

### Codex (`skills/codex/`)

| Skill | Description |
|---|---|
| [`adversarial-review`](skills/codex/adversarial-review/SKILL.md) | Read-only red-team pass over a plan or diff before risky work lands. |
| [`blitz`](skills/codex/blitz/SKILL.md) | Fast execution of ad-hoc lanes in parallel worktrees with adversarial review. |
| [`epic-plan`](skills/codex/epic-plan/SKILL.md) | Scope broad work into a tracker issue and right-sized child issues; materializes on GitHub as soon as the reviewed decomposition is ready — no approval gate. |
| [`issue`](skills/codex/issue/SKILL.md) | Front door for GitHub issue work; scopes ideas or routes issue numbers to resolve-issue. |
| [`resolve-issue`](skills/codex/resolve-issue/SKILL.md) | One issue to review-ready PR in an isolated worktree; never merges. |
| [`ww`](skills/codex/ww/SKILL.md) | Isolated worktree workflow; plan first, PR by default, main untouched. |
| [`zero`](skills/shared/zero/SKILL.md) | Shared destructive cleanup workflow with proof-before-delete classification. |

### Claude (`skills/claude/`)

| Skill | Description |
|---|---|
| [`adversary`](skills/claude/adversary/SKILL.md) | Cross-model red-team: sends a plan or diff to Codex (GPT) for an adversarial pass before committing. |
| [`blitz`](skills/claude/blitz/SKILL.md) | Lightweight executor for ad-hoc lanes: parallel worktrees + adversarial review, no pipeline ceremony. Owns all batches, filed or not. |
| [`deep-research`](skills/claude/deep-research/SKILL.md) | Opus-planned multi-source research with disconfirmation lens, GRADE evidence tiers, and a saturation loop. |
| [`epic-plan`](skills/claude/epic-plan/SKILL.md) | Research-heavy planner: wide parallel research, multi-lens review of the decomposition, child issues that execute via /resolve-issue and /blitz; re-enters from GitHub state. |
| [`resolve-issue`](skills/claude/resolve-issue/SKILL.md) | One worker resolves one issue end to end (test-first, gates verbatim, draft→ready PR); the phased multi-agent pipeline only on user-typed --full. Bounces a true epic to /epic-plan. Never merges. |
| [`patchcue-resolve-issue`](skills/claude/patchcue-resolve-issue/SKILL.md) | PatchCue worker workflow for Claude Code; same marked plan/outcome protocol as the Codex `resolve-issue` skill. |
| [`simplify-sweep`](skills/claude/simplify-sweep/SKILL.md) | Batch-clean a pushed commit range via headless Sonnet /simplify per area; orchestrator reviews and commits. |
| [`usage-review`](skills/claude/usage-review/SKILL.md) | Review your own Claude Code / Codex transcripts (or a shared archive) into a red-teamed report: numbers, automation families, risk incidents, rubric grades, coaching, action plan. Local-only; work dir kept out of git; secret scan before sharing. |

Claude skills remain available for Claude Code. Codex uses the separate
`skills/codex/` tree so tool names and workflow assumptions stay runtime-native.

### Shared (`skills/shared/`) — installed for Claude

| Skill | Description |
|---|---|
| [`authenticity-check`](skills/shared/authenticity-check/SKILL.md) | Score human authenticity and flag AI-sounding spans. Not installed by default. |
| [`humanizer`](skills/shared/humanizer/SKILL.md) | De-slop AI prose. Not installed by default. |
| [`zero`](skills/shared/zero/SKILL.md) | Destructive repo reset: checkpoint, merge all branches/worktrees into main, push. Read before use. |

## Routing an issue

| You have | Use |
|---|---|
| An issue number | `/resolve-issue <N>` (add `--full` for the heavy pipeline) |
| A rough idea (no issue yet) | Ask the agent to file it, then `/resolve-issue <N>` |
| Multiple issues | `/blitz 42 43 44` — parallel lanes, adversarial review |
| Ad-hoc lanes, nothing filed | `/blitz` — parallel worktrees, no issue required |
| A true epic (multi-session, multiple deliverables) | `/epic-plan <topic>` → `/resolve-issue <child-number>` |

Claiming (assign yourself), plan-comment-before-branch, and PR-only delivery are built in — you never merge your own PR.

## Requirements

- Git
- GitHub CLI (`gh`) authenticated: `gh auth login`
- Claude Code with local skill directory support

## Install

See [docs/install.md](docs/install.md) for full instructions.

`skill-issue` is the canonical source for these skills. Edit the files in this
checkout, then run `python3 scripts/check-install.py` to catch any local install
that points at an older copy. Run `python3 scripts/check-links.py` to verify that
all relative markdown links in the repo resolve on disk.

```bash
# Quick install (symlinks — edits to the repo are immediately live)
./scripts/install.sh
```

## Other tools

See [INDEX.md](INDEX.md) for the full tools/scripts table.

### Herdr tools

The [Herdr category](tools/herdr/README.md) holds plugins and an inventory of
existing tools worth extracting. Start with
[project placeholders](tools/herdr/project-anchors/README.md), a self-contained
Linux plugin for inert first tabs and close recovery. Plugins install separately
from skills. A whole-workspace close still stops workers; full machine reboot
recovery remains untested.

## Hooks

Three standalone Claude Code hooks in [`hooks/claude/`](hooks/claude/). They started as copies of the author's live hooks. The live versions have since moved on, so treat these as starting points, not a mirror.

| Hook | What it does |
|---|---|
| [`pretool-bash.sh`](hooks/claude/pretool-bash.sh) | Block destructive Bash commands (recursive delete of system paths, force-push to main, `git reset --hard`, dropping tables), Bash writes that escape an isolated worktree, and bare `git stash` on a dirty tree. |
| [`caffeinate.sh`](hooks/claude/caffeinate.sh) | Keep a Mac awake while the Claude session lives. No-op elsewhere. |
| [`confetti-gate.sh`](hooks/claude/confetti-gate.sh) | Fire Raycast confetti after a successful main push. macOS + Raycast only. |

See [`hooks/claude/README.md`](hooks/claude/README.md) for `settings.json` snippets and what was removed.

## Credits

The `authenticity-check` and `humanizer` skills
are vendored from [aihxp](https://github.com/aihxp)'s Scriveno project
([authenticity-check](https://github.com/aihxp/authenticity-check),
[humanizer](https://github.com/aihxp/humanizer)) and used under the MIT License.
Each vendored skill keeps its original `LICENSE` (copyright preserved as required);
everything else here is MIT under [`LICENSE`](LICENSE).

## Status

Experimental. Read each skill before using it on an important repository.

`zero` is intentionally destructive — it merges everything into the default branch and pushes. Use only at a deliberate cleanup point.

Retired skills and tools are deleted, not archived. Find them in git history.
