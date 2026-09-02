"""Contract checks for PatchCue worker protocol v1 in resolve-issue."""
from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RESOLVE_ISSUE_SKILL = REPO_ROOT / "skills" / "codex" / "resolve-issue" / "SKILL.md"


def test_resolve_issue_skill_contains_protocol_markers_and_plan_keys() -> None:
    skill_text = RESOLVE_ISSUE_SKILL.read_text(encoding="utf-8")

    required_protocol_fragments = (
        "<!-- patchcue:plan v=1 issue=N -->",
        "PROTOCOL: v1",
        "CLASS_OR_INSTANCE: CLASS|INSTANCE — <evidence>",
        "GATE: required|none",
        "QUESTION: <text>",
        "ACCEPTANCE:",
        "EVIDENCE:",
        "<!-- patchcue:outcome v=1 issue=N -->",
        "OUTCOME: pr|data-fix|question|superseded",
    )

    for fragment in required_protocol_fragments:
        assert fragment in skill_text, f"resolve-issue is missing protocol fragment: {fragment}"


def test_resolve_issue_skill_contains_each_protocol_rule_sentence() -> None:
    skill_text = RESOLVE_ISSUE_SKILL.read_text(encoding="utf-8")

    required_rule_sentences = (
        "If a narrow slice shows ≥90% one value, re-query the whole dimension.",
        "If ≥90% of the whole dimension has that value, classify the issue as CLASS.",
        "Treat any change to who sees what data, money, or roles as a QUESTION when the repo's decision ledger contains no ruling.",
        "If any QUESTION exists, post the plan and a question outcome, then stop without opening a branch.",
        "Set `GATE: required` for CLASS and `GATE: none` for INSTANCE.",
        "Repos may widen the required trigger set through configuration, but CLASS is the default trigger.",
        "If `GATE: required`, stop after the plan without an outcome or branch.",
        "Continue only when PatchCue resumes the run after a validated go decision.",
        "Treat \"operator data fix, no deploy\" as a legal outcome.",
        "For `OUTCOME: data-fix`, add `DATA_FIX_STATEMENT: <exact statement>` and `ROLLBACK: <exact rollback plan>`, then stop without a branch, PR, or deploy.",
        "Re-poll issue comments immediately before acting on the gate.",
        "Re-poll issue comments immediately before every push.",
        "Never pass the gate against a stale plan.",
        "Never push against a stale plan.",
        "If the run is PatchCue-invoked, leave its PR as a draft and never call `gh pr ready`.",
        "For `OUTCOME: superseded`, close any PR owned by this run.",
    )

    normalized_skill_text = " ".join(skill_text.split())
    for sentence in required_rule_sentences:
        assert sentence in normalized_skill_text, f"resolve-issue is missing rule: {sentence}"

    foreign_comment_rule = (
        "If a scope-relevant comment comes from a login other than the worker or "
        "controller, park the run as superseded or amend and repost the plan."
    )
    assert normalized_skill_text.count(foreign_comment_rule) == 2
