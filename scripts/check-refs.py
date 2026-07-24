#!/usr/bin/env python3
"""Reference-drift guard: verify every tool name, agent type, model id, and
slash command mentioned in a SKILL.md (or agents/*.md, or the top-level docs)
actually resolves to something that exists in this repo.

Catches the class of defect an audit finds one grep at a time: a skill
referencing a tool that doesn't exist (or that's been deprecated out from
under it, like TaskOutput), an agent type nothing defines, or a slash
command with no backing skill.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Directories whose .md files we scan for references. CHANGELOG is history,
# not a live contract, and deprecated/ is explicitly archived — both excluded.
SCAN_DIRS = ["skills", "agents", "docs", "hooks/claude"]
SCAN_ROOT_FILES = ["README.md", "INDEX.md"]

# Claude Code / Codex CLI tool names this repo's skills and agents are known
# to invoke. Update when a skill starts using a new one.
KNOWN_TOOLS = {
    "Agent", "Artifact", "AskUserQuestion", "Bash", "CronCreate", "CronDelete",
    "CronList", "Edit", "ExitPlanMode", "Glob", "Grep", "LSP", "Monitor",
    "NotebookEdit", "Read", "ReportFindings", "SendMessage", "SendUserFile",
    "Skill", "TaskStop", "TodoWrite", "ToolSearch", "WebFetch", "WebSearch",
    "Workflow", "Write",
}

# Tools that once existed and were removed/deprecated — referencing them is
# always a bug, not just an unresolved name, so they're rejected explicitly
# rather than merely "not in KNOWN_TOOLS" (which would also catch genuine
# typos with a less specific message).
BANNED_TOOLS = {
    "TaskOutput": "deprecated — unavailable to subagents; use `claude agents "
                   "--json` + Read on the pulse/output file instead (see "
                   "docs/lane-watchdog.md)",
    "TaskCreate": "not part of this repo's tool surface",
    "TaskGet": "not part of this repo's tool surface",
    "TaskList": "not part of this repo's tool surface",
    "TaskUpdate": "not part of this repo's tool surface",
}

# Agent types resolvable without a local agents/*.md — Claude Code builtins.
BUILTIN_AGENT_TYPES = {"general-purpose", "Explore", "Plan", "claude", "statusline-setup"}

KNOWN_MODEL_IDS = {"sonnet", "opus", "haiku"}

ALLOWED_SLASH_FALSE_POSITIVES = {
    # Regex catches these from prose ("the plan's /verify step",
    # "/tmp/epic-plan/<slug>/") even though they aren't invokable commands.
    "verify", "slug",
}

# Claude Code ships these as built-in slash commands, not skills — no
# SKILL.md will ever back them.
BUILTIN_SLASH_COMMANDS = {"config", "simplify", "help", "clear"}

# Real, invokable commands that live outside this repo (personal
# ~/.claude/commands/*.md files, not skill-issue skills) and so can't be
# checked against a local SKILL.md. Documented here instead of silently
# allowlisted so the exception is visible.
EXTERNAL_COMMANDS = {"codex-go"}  # ~/.claude/commands/codex-go.md, unversioned


def scan_files() -> list[Path]:
    files: list[Path] = []
    for d in SCAN_DIRS:
        files.extend((REPO_ROOT / d).rglob("*.md"))
    for f in SCAN_ROOT_FILES:
        p = REPO_ROOT / f
        if p.exists():
            files.append(p)
    return sorted(set(files))


def skill_frontmatter_names() -> set[str]:
    names = set()
    for skill_md in (REPO_ROOT / "skills").rglob("SKILL.md"):
        text = skill_md.read_text(encoding="utf-8")
        m = re.search(r"^name:\s*(\S+)", text, re.MULTILINE)
        if m:
            names.add(m.group(1).strip().strip('"'))
    return names


def agent_frontmatter_names() -> set[str]:
    names = set()
    for agent_md in (REPO_ROOT / "agents").glob("*.md"):
        text = agent_md.read_text(encoding="utf-8")
        m = re.search(r"^name:\s*(\S+)", text, re.MULTILINE)
        if m:
            names.add(m.group(1).strip().strip('"'))
    return names


def check_slash_commands(files: list[Path], defined_commands: set[str]) -> list[str]:
    errors = []
    pattern = re.compile(r"`/([a-zA-Z][a-zA-Z0-9_-]*)(?: [^`/]*)?`")
    for f in files:
        text = f.read_text(encoding="utf-8")
        for m in pattern.finditer(text):
            cmd = m.group(1)
            if cmd in ALLOWED_SLASH_FALSE_POSITIVES:
                continue
            if cmd in BUILTIN_SLASH_COMMANDS or cmd in EXTERNAL_COMMANDS:
                continue
            if cmd not in defined_commands:
                errors.append(
                    f"{f.relative_to(REPO_ROOT)}: `/{cmd}` has no backing "
                    f"skill (no SKILL.md with name: {cmd})"
                )
    return errors


def check_agent_types(files: list[Path], defined_agents: set[str]) -> list[str]:
    errors = []
    pattern = re.compile(r'agentType:\s*"?([a-zA-Z][a-zA-Z0-9_-]*)"?')
    for f in files:
        text = f.read_text(encoding="utf-8")
        for m in pattern.finditer(text):
            agent_type = m.group(1)
            if agent_type in defined_agents or agent_type in BUILTIN_AGENT_TYPES:
                continue
            errors.append(
                f"{f.relative_to(REPO_ROOT)}: agentType \"{agent_type}\" is "
                f"not defined in agents/ and is not a known builtin"
            )
    return errors


NEGATION_MARKERS = ("never", "not ", "don't", "do not", "deprecated", "avoid", "banned")


def check_tools(files: list[Path]) -> list[str]:
    errors = []
    for f in files:
        text = f.read_text(encoding="utf-8")
        for banned, reason in BANNED_TOOLS.items():
            for line in text.splitlines():
                if not re.search(rf"\b{re.escape(banned)}\b", line):
                    continue
                if any(marker in line.lower() for marker in NEGATION_MARKERS):
                    continue  # documented prohibition, not a live call
                errors.append(f"{f.relative_to(REPO_ROOT)}: references banned tool `{banned}` ({reason})")
        m = re.search(r"^tools:\s*(.+)$", text, re.MULTILINE)
        if m:
            for tool in [t.strip() for t in m.group(1).split(",")]:
                if tool and tool not in KNOWN_TOOLS:
                    errors.append(
                        f"{f.relative_to(REPO_ROOT)}: tools: frontmatter lists "
                        f"unknown tool `{tool}`"
                    )
    return errors


def check_model_ids(files: list[Path]) -> list[str]:
    errors = []
    for f in files:
        if f.parent.name != "agents" and f.parent != (REPO_ROOT / "agents"):
            continue
        text = f.read_text(encoding="utf-8")
        m = re.search(r"^model:\s*(\S+)", text, re.MULTILINE)
        if m and m.group(1) not in KNOWN_MODEL_IDS:
            errors.append(f"{f.relative_to(REPO_ROOT)}: model: \"{m.group(1)}\" is not a known model id")
    return errors


def main() -> int:
    files = scan_files()
    defined_commands = skill_frontmatter_names()
    defined_agents = agent_frontmatter_names()

    errors: list[str] = []
    errors += check_slash_commands(files, defined_commands)
    errors += check_agent_types(files, defined_agents)
    errors += check_tools(files)
    errors += check_model_ids(files)

    if errors:
        for e in sorted(set(errors)):
            print(f"FAIL: {e}", file=sys.stderr)
        print(f"\n{len(set(errors))} reference-drift issue(s) found.", file=sys.stderr)
        return 1

    print(
        f"OK reference-drift check: {len(files)} file(s) scanned, "
        f"{len(defined_commands)} command(s) and {len(defined_agents)} agent "
        f"type(s) known."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
