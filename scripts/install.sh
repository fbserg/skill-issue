#!/usr/bin/env bash
# install.sh — symlink skill-issue skills and tools into the right runtime dirs.
# Idempotent: safe to re-run after pulling new skills.
# Does NOT install hooks — those require settings.json edits.
# See hooks/claude/README.md for hook wiring instructions.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Installing from: $REPO_ROOT"
echo ""

mkdir -p \
  "${HOME}/.claude/skills" \
  "${HOME}/.local/bin"

# ── Claude-only skills ────────────────────────────────────────────────────────
echo "Claude skills:"
for skill_dir in "${REPO_ROOT}/skills/claude"/*/; do
  name="$(basename "$skill_dir")"
  target="${HOME}/.claude/skills/${name}"
  ln -sfn "$skill_dir" "$target"
  echo "  ~/.claude/skills/${name} -> $skill_dir"
done

echo ""

# ── Shared skills (dirs containing SKILL.md only — skip loose .md files) ─────
echo "Shared skills (Claude):"
for skill_dir in "${REPO_ROOT}/skills/shared"/*/; do
  # Skip if not a directory (handles glob no-match)
  [[ -d "$skill_dir" ]] || continue
  # Only install dirs that contain a SKILL.md
  [[ -f "${skill_dir}SKILL.md" ]] || continue
  name="$(basename "$skill_dir")"
  ln -sfn "$skill_dir" "${HOME}/.claude/skills/${name}"
  echo "  ~/.claude/skills/${name} -> $skill_dir"
done

echo ""

# ── gmail-tools ───────────────────────────────────────────────────────────────
gmail_tools_src="${REPO_ROOT}/tools/gmail-tools/bin/gmail-tools"
gmail_tools_dst="${HOME}/.local/bin/gmail-tools"
ln -sfn "$gmail_tools_src" "$gmail_tools_dst"
echo "gmail-tools:"
echo "  ~/.local/bin/gmail-tools -> $gmail_tools_src"

echo ""
echo "Done. Confirm ~/.local/bin is on PATH, then verify:"
echo "  gmail-tools --help   # needs uv installed"
echo ""
echo "To install hooks, see: ${REPO_ROOT}/hooks/claude/README.md"
