# proof-gate

A `Stop` hook that blocks Claude from declaring "done" while the repo has uncommitted code or unpushed commits.

## The story

A 3-week transcript sweep on one project found ~29 sessions where Claude signed off as "done/fixed/shipped" while the repo still had dirty tracked files or commits that hadn't been pushed. The user had to manually ask "did you push? is it deployed?" every time. This hook converts that silent skip into one explicit checkpoint — it fires at most once per session, and Claude satisfies it by either actually pushing or explicitly saying "this is local-only."

## What it does

1. On `Stop`, reads the last assistant text turn from `transcript_path`.
2. Checks whether the message contains a completion claim (`done`, `fixed`, `shipped`, `✅`, etc.).
3. Checks whether the message contains an explicit local-only/WIP disclaimer (passes silently if so).
4. Inspects git state: dirty tracked **code** files OR commits ahead of the upstream branch.
5. If the message claims completion AND the repo has undeployed code AND no disclaimer: **block once** and demand proof.

"Proof" means: run the deploy command and confirm it succeeded, or say "this is local-only / WIP." That turns skipping the deploy into a deliberate, auditable choice rather than an accidental omission.

## Install

```jsonc
// .claude/settings.json or ~/.claude/settings.json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/path/to/hooks/claude/proof-gate/proof-gate.sh"
          }
        ]
      }
    ]
  }
}
```

Replace `/path/to/` with the absolute path to this repo clone.

## Environment variables

All optional — the hook works out of the box without any configuration.

| Variable | Default | Effect |
|---|---|---|
| `PROOF_GATE_CODE_REGEX` | `\.(py\|mjs\|js\|ts\|tsx\|jsx\|sh\|sql\|toml\|css\|html)$` | `grep -E` pattern; a changed file must match to count as "code" |
| `PROOF_GATE_EXCLUDE_REGEX` | `(^/)(docs\|tests?\|spec)/\|\.(md\|txt\|csv\|json\|lock)$` | `grep -E` pattern; matched paths are excluded even if they pass the code regex |
| `PROOF_GATE_DEPLOY_CMD` | `git push` | Your project's deploy command, shown verbatim in the remediation message (e.g. `just push-main`) |

Example with project-specific deploy command:

```jsonc
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "PROOF_GATE_DEPLOY_CMD='just push-main' /path/to/hooks/claude/proof-gate/proof-gate.sh"
          }
        ]
      }
    ]
  }
}
```

## Caveats

- **Heuristic keyword matching.** Completion claims and disclaimers are detected by regex against the lowercased last assistant text turn. Unusual phrasing can miss. The risk is a false negative (hook doesn't fire when it should) rather than a false positive — the worst outcome is the original silent skip, not a spurious block.
- **Fires at most once per session.** A marker file in `${TMPDIR:-/tmp}/claude-proof-gate/<session_id>` prevents looping. If Claude answers the gate correctly in a continuation turn, the hook stays silent for the rest of the session.
- **No-upstream branches.** If the current branch has no upstream configured, `git rev-list @{upstream}..HEAD` fails gracefully and `ahead` is treated as 0. The hook still catches dirty tracked files; it just won't flag unpushed commits on detached or upstream-less branches.
- **Fail-open.** Any error — missing `jq`, not a git repo, unreadable transcript — causes the hook to exit 0 silently. It never blocks a session due to a configuration problem.
- **Respects `stop_hook_active`.** The hook exits immediately when `stop_hook_active` is `true`, preventing the re-entry loop that would occur if Claude tried to satisfy the gate in its blocked continuation turn.
