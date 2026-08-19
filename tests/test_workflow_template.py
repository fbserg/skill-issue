"""docs/workflow-template.md ships a copy-paste Workflow script inside a
```js fenced block. It must stay syntactically valid JS — this extracts the
block and runs `node --check` on it, the same gate a human editing the doc
by hand is expected to run (see the doc's own "keep it syntactically valid"
note). Skips if `node` isn't on PATH rather than failing the whole suite on
an unrelated environment gap.

Run with: python3 -m pytest tests/test_workflow_template.py -v
"""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = REPO_ROOT / "docs" / "workflow-template.md"
JS_BLOCK_RE = re.compile(r"```js\n(.*?)\n```", re.DOTALL)


def _extract_js_block() -> str:
    text = TEMPLATE_PATH.read_text(encoding="utf-8")
    match = JS_BLOCK_RE.search(text)
    assert match, f"{TEMPLATE_PATH}: no ```js fenced block found"
    return match.group(1)


@pytest.mark.skipif(shutil.which("node") is None, reason="node not on PATH")
def test_template_script_is_syntactically_valid_js() -> None:
    script = _extract_js_block()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=True) as tmp:
        tmp.write(script)
        tmp.flush()
        result = subprocess.run(
            ["node", "--check", tmp.name],
            capture_output=True, text=True, check=False,
        )
    assert result.returncode == 0, f"node --check failed:\n{result.stderr}"


def test_template_has_exactly_one_js_block() -> None:
    text = TEMPLATE_PATH.read_text(encoding="utf-8")
    assert text.count("```js\n") == 1


def test_template_doc_is_under_150_lines() -> None:
    lines = TEMPLATE_PATH.read_text(encoding="utf-8").splitlines()
    assert len(lines) <= 150, f"{TEMPLATE_PATH}: {len(lines)} lines, target ~150"
