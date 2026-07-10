#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
import fcntl
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


STATE_ROOT = Path(os.environ.get("TMPDIR", "/tmp")) / "claude-quality-hooks"
SKIP_PARTS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    "vendor",
    "__pycache__",
}
PRETTIER_EXTS = {
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".json",
    ".css",
    ".scss",
    ".html",
    ".md",
    ".mdx",
    ".yaml",
    ".yml",
}
ESLINT_EXTS = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
BIOME_EXTS = ESLINT_EXTS | {".json", ".jsonc", ".css"}


@dataclass
class ToolResult:
    name: str
    command: list[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    def summary(self) -> str:
        out = (self.stderr or self.stdout).strip()
        if len(out) > 1200:
            out = out[:1200] + "\n..."
        return f"{self.name} failed: {' '.join(self.command)}\n{out}".strip()


def read_payload() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def disabled() -> bool:
    return os.environ.get("AGENT_QUALITY_HOOK") == "0"


def session_key(payload: dict[str, Any]) -> str:
    sid = payload.get("session_id") or "unknown-session"
    aid = payload.get("agent_id") or payload.get("agentId") or "main"
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", f"{sid}-{aid}")


def state_file(payload: dict[str, Any], suffix: str) -> Path:
    STATE_ROOT.mkdir(parents=True, exist_ok=True)
    return STATE_ROOT / f"{session_key(payload)}.{suffix}.json"


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def root_token(root: Path) -> str:
    return hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:16]


def cwd_from_payload(payload: dict[str, Any]) -> Path:
    raw = payload.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    return Path(raw).expanduser().resolve()


def git_root(cwd: Path) -> Path | None:
    try:
        proc = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    return Path(proc.stdout.strip()).resolve()


def git_changed(root: Path) -> set[str]:
    proc = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain=v1", "-z"],
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )
    if proc.returncode != 0:
        return set()
    changed: set[str] = set()
    entries = [e for e in proc.stdout.split("\0") if e]
    i = 0
    while i < len(entries):
        entry = entries[i]
        path = entry[3:] if len(entry) > 3 else entry
        if entry.startswith(("R", "C")) and i + 1 < len(entries):
            i += 1
        if path:
            changed.add(path)
        i += 1
    return changed


def rel_to_abs(root: Path, rel: str) -> Path:
    return (root / rel).resolve()


def abs_to_rel(root: Path, path: Path) -> str | None:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return None


def is_skipped(rel: str) -> bool:
    p = Path(rel)
    if p.name.endswith((".lock", ".min.js", ".map")):
        return True
    return any(part in SKIP_PARTS for part in p.parts)


def repo_opt_out(root: Path) -> bool:
    cfg = root / ".agent-quality-hooks.toml"
    if not cfg.exists():
        return False
    try:
        data = tomllib.loads(cfg.read_text(encoding="utf-8"))
    except Exception:
        return False
    return data.get("enabled") is False


def repo_config(root: Path) -> dict[str, Any]:
    cfg = root / ".agent-quality-hooks.toml"
    if not cfg.exists():
        return {}
    try:
        return tomllib.loads(cfg.read_text(encoding="utf-8"))
    except Exception:
        return {}


def node_tools_allowed(root: Path) -> bool:
    if os.environ.get("AGENT_QUALITY_ALLOW_NODE") == "1":
        return True
    data = repo_config(root)
    tools = data.get("tools") if isinstance(data.get("tools"), dict) else {}
    return data.get("allow_node_tools") is True or tools.get("node") is True


def package_json(root: Path) -> dict[str, Any]:
    path = root / "package.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def pkg_has(root: Path, name: str) -> bool:
    pkg = package_json(root)
    deps = {}
    for key in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        value = pkg.get(key)
        if isinstance(value, dict):
            deps.update(value)
    scripts = pkg.get("scripts") if isinstance(pkg.get("scripts"), dict) else {}
    return name in deps or any(name in str(v) for v in scripts.values())


def local_bin(root: Path, name: str) -> bool:
    return (root / "node_modules" / ".bin" / name).exists()


def has_any(root: Path, names: tuple[str, ...]) -> bool:
    return any((root / name).exists() for name in names)


def pyproject(root: Path) -> dict[str, Any]:
    path = root / "pyproject.toml"
    if not path.exists():
        return {}
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def py_declares(root: Path, tool: str) -> bool:
    data = pyproject(root)
    if tool in data.get("tool", {}):
        return True
    text = (root / "pyproject.toml").read_text(encoding="utf-8") if (root / "pyproject.toml").exists() else ""
    return re.search(rf'["\']{re.escape(tool)}[<>=~!,"\']', text) is not None


def command_exists(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def run(root: Path, cmd: list[str]) -> ToolResult:
    try:
        proc = subprocess.run(cmd, cwd=root, text=True, capture_output=True, timeout=30, check=False)
        return ToolResult(cmd[0], cmd, proc.returncode, proc.stdout, proc.stderr)
    except Exception as exc:
        return ToolResult(cmd[0], cmd, 1, "", str(exc))


def npx(root: Path, args: list[str]) -> ToolResult:
    return run(root, ["npx", "--no-install", *args])


def format_touched(root: Path, rels: set[str]) -> tuple[list[str], list[ToolResult]]:
    STATE_ROOT.mkdir(parents=True, exist_ok=True)
    lock_path = STATE_ROOT / f"format-{root_token(root)}.lock"
    with lock_path.open("w", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return _format_touched_locked(root, rels)


def _format_touched_locked(root: Path, rels: set[str]) -> tuple[list[str], list[ToolResult]]:
    if repo_opt_out(root):
        return [], []
    rels = {r for r in rels if r and not is_skipped(r) and (root / r).exists() and (root / r).is_file()}
    if not rels:
        return [], []

    formatted: list[str] = []
    failures: list[ToolResult] = []

    by_ext: dict[str, list[str]] = {}
    for rel in sorted(rels):
        by_ext.setdefault(Path(rel).suffix, []).append(rel)

    allow_node = node_tools_allowed(root)
    if allow_node and has_any(root, ("biome.json", "biome.jsonc")) and pkg_has(root, "@biomejs/biome") and local_bin(root, "biome"):
        files = [r for r in rels if Path(r).suffix in BIOME_EXTS]
        if files:
            # --no-errors-on-unmatched: repos may scope biome to a subtree via
            # files.include; touched files outside that scope must not fail the batch.
            res = npx(root, ["biome", "check", "--write", "--no-errors-on-unmatched", *files])
            (formatted if res.ok else failures).extend(files if res.ok else [])
            if not res.ok:
                failures.append(res)
        return sorted(set(formatted)), failures

    prettier_configured = has_any(
        root,
        (
            ".prettierrc",
            ".prettierrc.json",
            ".prettierrc.yml",
            ".prettierrc.yaml",
            ".prettierrc.js",
            "prettier.config.js",
            "prettier.config.cjs",
            "prettier.config.mjs",
        ),
    ) or pkg_has(root, "prettier")
    if allow_node and prettier_configured and local_bin(root, "prettier"):
        files = [r for r in rels if Path(r).suffix in PRETTIER_EXTS]
        if files:
            res = npx(root, ["prettier", "--write", *files])
            if res.ok:
                formatted.extend(files)
            else:
                failures.append(res)

    eslint_configured = has_any(
        root,
        (
            "eslint.config.js",
            "eslint.config.mjs",
            "eslint.config.cjs",
            ".eslintrc",
            ".eslintrc.json",
            ".eslintrc.js",
            ".eslintrc.cjs",
        ),
    ) and pkg_has(root, "eslint") and local_bin(root, "eslint")
    if allow_node and eslint_configured:
        files = [r for r in rels if Path(r).suffix in ESLINT_EXTS]
        if files:
            res = npx(root, ["eslint", "--fix", *files])
            if res.ok:
                formatted.extend(files)
            else:
                failures.append(res)

    py_files = by_ext.get(".py", [])
    if py_files and (py_declares(root, "ruff") or has_any(root, ("ruff.toml", ".ruff.toml"))):
        if command_exists("ruff"):
            # --unfixable F401,F841,ERA001: never apply deletion-type fixes mid-flight —
            # agents add an import/variable in one edit and use it in the next, and
            # commented-out code may be a step in an in-progress edit sequence;
            # commit-time ruff still strips them.
            _ruff_ok = True
            for args in (["ruff", "check", "--fix", "--unfixable", "F401,F841,ERA001", *py_files], ["ruff", "format", *py_files]):
                res = run(root, args)
                if not res.ok:
                    failures.append(res)
                    _ruff_ok = False
            if _ruff_ok:
                formatted.extend(py_files)
        else:
            failures.append(ToolResult("ruff", ["ruff"], 127, "", "ruff is configured but not installed"))
    elif py_files and py_declares(root, "black"):
        if command_exists("black"):
            res = run(root, ["black", *py_files])
            if res.ok:
                formatted.extend(py_files)
            else:
                failures.append(res)

    sh_files = [r for r in rels if Path(r).suffix == ".sh"]
    if sh_files and command_exists("shellcheck"):
        res = run(root, ["shellcheck", *sh_files])
        if not res.ok:
            failures.append(res)

    go_files = [r for r in rels if Path(r).suffix == ".go"]
    if go_files and (root / "go.mod").exists() and command_exists("gofmt"):
        res = run(root, ["gofmt", "-w", *go_files])
        if res.ok:
            formatted.extend(go_files)
        else:
            failures.append(res)

    return sorted(set(formatted)), failures


def direct_tool_files(payload: dict[str, Any], root: Path) -> set[str]:
    tool_input = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {}
    tool_response = payload.get("tool_response") if isinstance(payload.get("tool_response"), dict) else {}
    files: set[str] = set()
    candidates: list[str] = []
    for src in (tool_input, tool_response):
        for key in ("file_path", "filePath", "path"):
            raw = src.get(key)
            if isinstance(raw, str) and raw:
                candidates.append(raw)
        for key in ("file_paths", "filePaths", "paths"):
            raw = src.get(key)
            if isinstance(raw, list):
                candidates.extend(x for x in raw if isinstance(x, str))
    for raw in candidates:
            path = Path(raw).expanduser()
            if not path.is_absolute():
                path = cwd_from_payload(payload) / path
            rel = abs_to_rel(root, path)
            if rel:
                files.add(rel)
    return files


WRITE_CMD_RE = re.compile(
    r"""
    (^|[;&|]\s*)(apply_patch|tee|dd|install|mv|cp|touch|truncate|mkdir|ln|rsync|patch)\b
    |(^|[;&|]\s*)git\s+apply\b
    |(^|[;&|]\s*)(sed|perl|ruby|python3?|node)\b.*\s-i(\b|['"])
    |(^|[;&|]\s*)(python3?|node)\b.*(open\(|writeFile|writeFileSync)
    |(^|[;&|]\s*)cat\b.*>\s*
    |(^|[;&|]\s*)printf\b.*>\s*
    |(^|[;&|]\s*)echo\b.*>\s*
    |>\s*[^&]
    |>>\s*[^&]
    """,
    re.IGNORECASE | re.VERBOSE | re.DOTALL,
)


def bash_might_write(payload: dict[str, Any]) -> bool:
    tool_input = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {}
    command = str(tool_input.get("command") or "")
    return bool(WRITE_CMD_RE.search(command))


def file_hash(path: Path) -> str | None:
    try:
        if not path.exists() or not path.is_file():
            return None
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def hash_changed(root: Path, rels: set[str]) -> dict[str, str | None]:
    return {rel: file_hash(root / rel) for rel in sorted(rels) if rel and not is_skipped(rel)}


def record_pre(payload: dict[str, Any]) -> None:
    root = git_root(cwd_from_payload(payload))
    if not root:
        return
    tool_use_id = payload.get("tool_use_id") or "unknown"
    changed = git_changed(root)
    path = state_file(payload, "pre")
    lock_path = path.with_suffix(path.suffix + ".lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("w", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        data = load_json(path, {})
        data[tool_use_id] = {"root": str(root), "changed": sorted(changed), "hashes": hash_changed(root, changed)}
        save_json(path, data)


def touched_from_pre(payload: dict[str, Any], root: Path) -> set[str]:
    tool_use_id = payload.get("tool_use_id") or "unknown"
    data = load_json(state_file(payload, "pre"), {})
    before = set(data.get(tool_use_id, {}).get("changed", []))
    before_hashes = data.get(tool_use_id, {}).get("hashes", {})
    after = git_changed(root)
    touched = after - before
    for rel in after & before:
        if file_hash(root / rel) != before_hashes.get(rel):
            touched.add(rel)
    return touched


def record_feedback(payload: dict[str, Any], formatted: list[str], failures: list[ToolResult], touched: set[str] | None = None) -> None:
    if not formatted and not failures and not touched:
        return
    path = state_file(payload, "feedback")
    lock_path = path.with_suffix(path.suffix + ".lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("w", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        data = load_json(path, {"formatted": [], "failures": [], "failure_items": []})
        touched_set = set(touched or formatted)
        data.setdefault("formatted", []).extend(formatted)
        root = git_root(cwd_from_payload(payload))
        root_s = str(root) if root else ""
        items = data.setdefault("failure_items", [])
        if touched_set:
            items[:] = [
                item for item in items
                if not (item.get("root", "") == root_s and set(item.get("paths", [])) & touched_set)
            ]
        items.extend(
            {
                "root": root_s,
                "paths": sorted(touched_set),
                "summary": f.summary(),
                "hashes": hash_changed(root, touched_set) if root else {},
            }
            for f in failures
        )
        data["failures"] = [item["summary"] for item in items]
        data["formatted"] = sorted(set(data["formatted"]))
        data["failures"] = data["failures"][-20:]
        data["failure_items"] = items[-20:]
        save_json(path, data)


def stage_touched(payload: dict[str, Any], root: Path, touched: set[str]) -> None:
    """Append touched relpaths to the per-session staging list (drained by PostToolBatch).

    PostToolUse stages, PostToolBatch executes once per batch — cheaper than running
    formatters per-edit and avoids flooding context with N system reminders.
    """
    if not touched:
        return
    path = state_file(payload, "feedback")
    lock_path = path.with_suffix(path.suffix + ".lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    root_s = str(root)
    with lock_path.open("w", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        data = load_json(path, {})
        staged = data.setdefault("staged", {})
        bucket = set(staged.get(root_s, []))
        bucket.update(touched)
        staged[root_s] = sorted(bucket)
        save_json(path, data)


def drain_staged(payload: dict[str, Any], root: Path) -> set[str]:
    """Pop and return all touched relpaths staged for `root`. Clears the bucket."""
    path = state_file(payload, "feedback")
    lock_path = path.with_suffix(path.suffix + ".lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    root_s = str(root)
    with lock_path.open("w", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        data = load_json(path, {})
        staged = data.get("staged") or {}
        touched = set(staged.pop(root_s, []))
        if "staged" in data:
            data["staged"] = staged
        save_json(path, data)
    return touched


def run_post_tool_stage() -> int:
    """PostToolUse body: stage touched paths only. PostToolBatch runs the formatters once."""
    payload = read_payload()
    if disabled():
        return 0
    root = git_root(cwd_from_payload(payload))
    if not root:
        return 0
    touched = direct_tool_files(payload, root)
    if (payload.get("tool_name") or "") == "Bash":
        pre_touched = touched_from_pre(payload, root)
        if not bash_might_write(payload) and not pre_touched:
            return 0
        touched |= pre_touched
    stage_touched(payload, root, touched)
    return 0


def claude_context(message: str) -> None:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": message}}))


def claude_batch_context(message: str) -> None:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolBatch", "additionalContext": message}}))


def claude_stop_context(message: str) -> None:
    print(json.dumps({"systemMessage": message}))


def claude_stop_block(message: str) -> None:
    print(json.dumps({"decision": "block", "reason": message}))
