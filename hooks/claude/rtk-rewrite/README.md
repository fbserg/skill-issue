# rtk-rewrite

Transparently rewrites verbose Bash commands through [`rtk`](https://github.com/lukeed/rtk) (Rust Token Killer) so their output lands in the model's context already compressed.

## What it does

- On every `Bash` call, runs `rtk rewrite` on the command
- `rtk` decides what's worth compressing — `find`, `ps`, `npm`, `cargo`, `wc`, test runners, and friends get rewritten; everything else (`cat`/`grep`/`ls`/`git`/`curl`) passes through untouched
- Output-heavy rewrites are also **auto-allowed**, so a command the user already approved in raw form doesn't trip a fresh permission prompt after rewriting
- `find` with compound predicates (`-not`, `-exec`, `-o`, `-a`, `-prune`) is skipped — rtk doesn't handle those
- If `rtk` isn't installed, the hook is a silent no-op

## Why

Tool output is the silent context killer. A `npm install` log or a wide `find` can dump thousands of tokens of noise. rtk strips that to the signal before it ever reaches the model — no behavior change for you, just a leaner context window. Check savings with `rtk gain`.

## Prerequisites

```bash
brew install rtk   # also needs jq, which you almost certainly already have
```

The hook fails open: install it first, add rtk later, nothing breaks in between.

## Install

```jsonc
// .claude/settings.json or ~/.claude/settings.json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "/path/to/hooks/claude/rtk-rewrite/rtk-rewrite.sh"
          }
        ]
      }
    ]
  }
}
```

Replace `/path/to/` with the absolute path to this repo clone, or symlink the script. If you already have a `Bash` matcher (e.g. `git-no-bypass`), add this as another entry in the same `hooks` array — they chain.
