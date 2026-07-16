"""Stdlib unittest suite for backup.py (transcript-archive v2).

Two layers:
  - Direct unit tests against backup.py's functions (imported in-process) for
    the image policy, per-line byte fidelity, and pure helpers.
  - Subprocess-driven integration tests that run `python3 backup.py` against
    a fake HOME + fake archive dir, to exercise env resolution, argparse,
    exit codes, and the full main() flow honestly (including things that
    only make sense end-to-end, like log rotation and old-layout detection).
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import backup  # noqa: E402

BACKUP_PY = Path(__file__).resolve().parent / "backup.py"


def run_backup(env: dict, args: list | None = None, cwd: Path | None = None) -> subprocess.CompletedProcess:
    full_env = dict(os.environ)
    full_env.update(env)
    cmd = [sys.executable, str(BACKUP_PY)] + (args or [])
    return subprocess.run(cmd, env=full_env, capture_output=True, text=True, cwd=str(cwd) if cwd else None)


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


class TestTombstone(unittest.TestCase):
    def test_format_and_math(self):
        b64 = "QUJDREVGRw=="  # arbitrary base64
        tomb = backup.make_tombstone(b64, "image/png")
        self.assertTrue(tomb.startswith("__IMAGE_TOMBSTONE(media_type=image/png,bytes="))
        self.assertTrue(tomb.endswith("__"))
        expected_len = len(b64) * 3 // 4
        expected_hash = hashlib.sha256(b64.encode("utf-8")).hexdigest()[:12]
        self.assertIn(f"bytes={expected_len}", tomb)
        self.assertIn(f"sha256={expected_hash}", tomb)
        self.assertEqual(len(expected_hash), 12)

    def test_no_regex_in_module(self):
        # The old dangerous 200-char base64 regex must be entirely gone.
        source = BACKUP_PY.read_text()
        self.assertNotIn("A-Za-z0-9+/", source)
        self.assertNotIn("STRIP_MARKER", source)
        self.assertNotIn("B64_RE", source)


class TestMachineIdSanitize(unittest.TestCase):
    def test_lowercases_and_replaces(self):
        self.assertEqual(backup.sanitize_machine_id("My.Laptop_01"), "my-laptop-01")

    def test_already_clean(self):
        self.assertEqual(backup.sanitize_machine_id("laptop-2"), "laptop-2")

    def test_empty_after_sanitize(self):
        self.assertEqual(backup.sanitize_machine_id(""), "")
        self.assertEqual(backup.sanitize_machine_id("..."), "---")


# ---------------------------------------------------------------------------
# Claude image policy
# ---------------------------------------------------------------------------


def claude_tool_screenshot_line(with_array_toolUseResult=False):
    data = "A" * 400
    obj = {
        "message": {
            "role": "user",
            "content": [
                {
                    "tool_use_id": "t1",
                    "type": "tool_result",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": data}},
                        {"type": "text", "text": "screenshot"},
                    ],
                }
            ],
        },
    }
    if with_array_toolUseResult:
        obj["toolUseResult"] = [
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": data}}
        ]
    else:
        obj["toolUseResult"] = {
            "type": "image",
            "file": {"base64": data, "type": "image/png", "originalSize": 12345, "dimensions": {"w": 10, "h": 10}},
        }
    return obj, data


class TestClaudeStripLine(unittest.TestCase):
    def test_human_paste_kept_byte_identical(self):
        obj = {
            "imagePasteIds": [1],
            "origin": {"kind": "human"},
            "promptSource": "typed",
            "message": {
                "role": "user",
                "content": [
                    {"type": "text", "text": "hi"},
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "B" * 300}},
                ],
            },
        }
        before = json.dumps(obj)
        modified = backup.claude_strip_line(obj)
        self.assertFalse(modified)
        self.assertEqual(json.dumps(obj), before)

    def test_tool_result_screenshot_tombstoned(self):
        obj, data = claude_tool_screenshot_line()
        modified = backup.claude_strip_line(obj)
        self.assertTrue(modified)
        inner = obj["message"]["content"][0]["content"][0]
        self.assertTrue(inner["source"]["data"].startswith("__IMAGE_TOMBSTONE("))
        self.assertNotIn(data, inner["source"]["data"])

    def test_tool_use_result_dict_shape_tombstoned(self):
        obj, data = claude_tool_screenshot_line(with_array_toolUseResult=False)
        backup.claude_strip_line(obj)
        self.assertTrue(obj["toolUseResult"]["file"]["base64"].startswith("__IMAGE_TOMBSTONE("))

    def test_tool_use_result_array_shape_tombstoned(self):
        obj, data = claude_tool_screenshot_line(with_array_toolUseResult=True)
        backup.claude_strip_line(obj)
        self.assertTrue(obj["toolUseResult"][0]["source"]["data"].startswith("__IMAGE_TOMBSTONE("))

    def test_agent_forwarded_tombstoned(self):
        obj = {
            "isMeta": True,
            "agentId": "agent-123",
            "message": {
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": "C" * 300}}
                ],
            },
        }
        modified = backup.claude_strip_line(obj)
        self.assertTrue(modified)
        self.assertTrue(
            obj["message"]["content"][0]["source"]["data"].startswith("__IMAGE_TOMBSTONE(")
        )

    def test_document_kept(self):
        obj = {
            "message": {
                "role": "user",
                "content": [
                    {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": "D" * 500}}
                ],
            }
        }
        before = json.dumps(obj)
        modified = backup.claude_strip_line(obj)
        self.assertFalse(modified)
        self.assertEqual(json.dumps(obj), before)

    def test_thinking_signature_untouched(self):
        obj = {
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "thinking", "thinking": "...", "signature": "X" * 500},
                ],
            }
        }
        before = json.dumps(obj)
        modified = backup.claude_strip_line(obj)
        self.assertFalse(modified)
        self.assertEqual(json.dumps(obj), before)

    def test_unknown_bare_image_kept(self):
        # No imagePasteIds/origin, no isMeta+agentId -- uncertain, bias to keep.
        obj = {
            "message": {
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "E" * 300}}
                ],
            }
        }
        modified = backup.claude_strip_line(obj)
        self.assertFalse(modified)

    def test_malformed_shapes_do_not_crash(self):
        weird = {"message": {"content": "not-a-list"}, "toolUseResult": "not-a-dict-or-list"}
        self.assertFalse(backup.claude_strip_line(weird))
        self.assertFalse(backup.claude_strip_line({"message": None}))
        self.assertFalse(backup.claude_strip_line("not even a dict"))


# ---------------------------------------------------------------------------
# Codex image policy
# ---------------------------------------------------------------------------


class TestCodexStripLine(unittest.TestCase):
    def test_user_paste_kept(self):
        obj = {
            "timestamp": "t",
            "type": "event",
            "payload": {
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "<image name=[Image #1]>"},
                    {"type": "input_image", "image_url": "data:image/png;base64," + "F" * 300, "detail": "auto"},
                    {"type": "input_text", "text": "</image>"},
                ],
            },
        }
        before = json.dumps(obj)
        modified = backup.codex_strip_line(obj)
        self.assertFalse(modified)
        self.assertEqual(json.dumps(obj), before)

    def test_custom_tool_call_output_image_tombstoned(self):
        obj = {
            "timestamp": "t",
            "type": "event",
            "payload": {
                "type": "custom_tool_call_output",
                "call_id": "c1",
                "output": [
                    {"type": "input_text", "text": "view"},
                    {"type": "input_image", "image_url": "data:image/jpeg;base64," + "G" * 300, "detail": "auto"},
                ],
            },
        }
        modified = backup.codex_strip_line(obj)
        self.assertTrue(modified)
        url = obj["payload"]["output"][1]["image_url"]
        self.assertTrue(url.startswith("__IMAGE_TOMBSTONE(media_type=image/jpeg,"))

    def test_compacted_line_verbatim(self):
        obj = {"timestamp": "t", "type": "event", "payload": {"type": "compacted", "junk": "x" * 50}}
        before = json.dumps(obj)
        modified = backup.codex_strip_line(obj)
        self.assertFalse(modified)
        self.assertEqual(json.dumps(obj), before)

    def test_replacement_history_verbatim(self):
        obj = {"timestamp": "t", "type": "event", "payload": {"replacement_history": [1, 2, 3]}}
        modified = backup.codex_strip_line(obj)
        self.assertFalse(modified)

    def test_encrypted_content_untouched(self):
        obj = {
            "timestamp": "t",
            "type": "event",
            "payload": {
                "type": "reasoning",
                "encrypted_content": "data:image/png;base64," + "H" * 300,  # looks tempting, must not be touched
            },
        }
        before = json.dumps(obj)
        modified = backup.codex_strip_line(obj)
        self.assertFalse(modified)
        self.assertEqual(json.dumps(obj), before)


# ---------------------------------------------------------------------------
# Line-level byte fidelity
# ---------------------------------------------------------------------------


class TestProcessLines(unittest.TestCase):
    def test_untouched_line_byte_identical(self):
        line_obj = {"b": 1, "a": 2, "message": {"content": [{"type": "text", "text": "hi"}]}}
        raw_line = json.dumps(line_obj).encode("utf-8") + b"\n"
        out = backup.process_lines(raw_line, backup.claude_strip_line)
        self.assertEqual(out, raw_line)

    def test_modified_line_is_valid_json_and_no_trailing_newline_preserved(self):
        obj, _ = claude_tool_screenshot_line()
        raw = json.dumps(obj).encode("utf-8")  # no trailing newline (last line of file)
        out = backup.process_lines(raw, backup.claude_strip_line)
        self.assertFalse(out.endswith(b"\n"))
        json.loads(out.decode("utf-8"))  # must still be valid JSON

    def test_malformed_line_copied_verbatim(self):
        raw = b'{"not": "closed"\n'
        out = backup.process_lines(raw, backup.claude_strip_line)
        self.assertEqual(out, raw)

    def test_lone_surrogate_serialization_falls_back_to_raw_line(self):
        # json.loads() happily accepts an unpaired \ud800 escape (it becomes
        # a Python str containing a literal surrogate code point), but
        # str.encode('utf-8') on that string always raises. Re-serializing a
        # modified (tombstoned) line containing one must never crash the
        # whole run -- it should fall back to the byte-identical original.
        obj = {
            "message": {
                "role": "user",
                "content": [
                    {"type": "text", "text": "bad surrogate: \ud800 end"},
                    {
                        "tool_use_id": "t1",
                        "type": "tool_result",
                        "content": [
                            {
                                "type": "image",
                                "source": {"type": "base64", "media_type": "image/png", "data": "A" * 400},
                            }
                        ],
                    },
                ],
            }
        }
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8", errors="surrogatepass") + b"\n"
        out = backup.process_lines(raw, backup.claude_strip_line)
        self.assertEqual(out, raw)  # unstripped, but byte-identical -- no crash

    def test_recursion_error_on_json_loads_falls_back_to_raw_line(self):
        depth = 200000
        raw = (b'{"x":' * depth + b"1" + b"}" * depth) + b"\n"
        out = backup.process_lines(raw, backup.claude_strip_line)
        self.assertEqual(out, raw)

    def test_multi_line_mixed(self):
        good_untouched = json.dumps({"x": 1}).encode() + b"\n"
        tomb_obj, _ = claude_tool_screenshot_line()
        good_modified = json.dumps(tomb_obj).encode() + b"\n"
        broken = b"not json at all\n"
        blank = b"\n"
        raw = good_untouched + good_modified + broken + blank
        out = backup.process_lines(raw, backup.claude_strip_line)
        lines = out.split(b"\n")
        self.assertEqual(lines[0], good_untouched.rstrip(b"\n"))  # byte-identical
        self.assertEqual(lines[2], broken.rstrip(b"\n"))  # verbatim
        parsed = json.loads(lines[1])
        self.assertTrue(
            json.dumps(parsed)  # re-parses fine
        )


# ---------------------------------------------------------------------------
# process_file: mtime skip / keep-larger / force / dry-run
# ---------------------------------------------------------------------------


class TestProcessFile(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_added_then_skipped_then_updated(self):
        src = self.tmp / "src.jsonl"
        dest = self.tmp / "dest.jsonl"
        src.write_bytes(json.dumps({"a": 1}).encode() + b"\n")

        result = backup.process_file(src, dest, "raw", force=False, dry_run=False)
        self.assertEqual(result, "added")
        self.assertTrue(dest.exists())

        result2 = backup.process_file(src, dest, "raw", force=False, dry_run=False)
        self.assertEqual(result2, "skipped")

        # Touch src forward in time and rewrite -> updated.
        new_mtime = os.path.getmtime(src) + 5
        src.write_bytes(json.dumps({"a": 2}).encode() + b"\n")
        os.utime(src, (new_mtime, new_mtime))
        result3 = backup.process_file(src, dest, "raw", force=False, dry_run=False)
        self.assertEqual(result3, "updated")

    def test_keep_larger_guard(self):
        src = self.tmp / "src.jsonl"
        dest = self.tmp / "dest.jsonl"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"x" * 1000)
        os.utime(dest, (1000, 1000))
        src.write_bytes(b"y" * 10)  # smaller
        os.utime(src, (2000, 2000))  # newer

        result = backup.process_file(src, dest, "raw", force=False, dry_run=False)
        self.assertEqual(result, "kept-larger")
        self.assertEqual(dest.read_bytes(), b"x" * 1000)  # untouched

    def test_force_bypasses_mtime_and_keep_larger(self):
        src = self.tmp / "src.jsonl"
        dest = self.tmp / "dest.jsonl"
        dest.write_bytes(b"x" * 1000)
        os.utime(dest, (5000, 5000))
        src.write_bytes(b"y" * 10)
        os.utime(src, (1000, 1000))  # older AND smaller

        result = backup.process_file(src, dest, "raw", force=True, dry_run=False)
        self.assertEqual(result, "updated")
        self.assertEqual(dest.read_bytes(), b"y" * 10)

    def test_dry_run_writes_nothing(self):
        src = self.tmp / "src.jsonl"
        dest = self.tmp / "dest.jsonl"
        src.write_bytes(b"hello")

        result = backup.process_file(src, dest, "raw", force=False, dry_run=True)
        self.assertEqual(result, "added")
        self.assertFalse(dest.exists())

    def test_strip_kind_processed(self):
        src = self.tmp / "src.jsonl"
        dest = self.tmp / "dest.jsonl"
        obj, _ = claude_tool_screenshot_line()
        src.write_bytes(json.dumps(obj).encode() + b"\n")

        backup.process_file(src, dest, "strip-claude", force=False, dry_run=False)
        out_obj = json.loads(dest.read_bytes().splitlines()[0])
        self.assertTrue(
            out_obj["message"]["content"][0]["content"][0]["source"]["data"].startswith("__IMAGE_TOMBSTONE(")
        )
        self.assertLess(dest.stat().st_size, src.stat().st_size)


# ---------------------------------------------------------------------------
# --compress
# ---------------------------------------------------------------------------


class TestCompress(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_roundtrip_content_equality_vs_uncompressed(self):
        # Same source, one run uncompressed and one compressed: the gzip's
        # decompressed bytes must equal the uncompressed archive's bytes
        # exactly -- compression is a storage wrapper, not a content change.
        obj, _ = claude_tool_screenshot_line()
        src = self.tmp / "src.jsonl"
        src.write_bytes(json.dumps(obj).encode() + b"\n")

        dest_plain = self.tmp / "plain" / "dest.jsonl"
        backup.process_file(src, dest_plain, "strip-claude", force=False, dry_run=False)

        dest_gz_base = self.tmp / "gz" / "dest.jsonl"
        backup.process_file(
            src, dest_gz_base, "strip-claude", force=False, dry_run=False, compress=True
        )
        gz_path = dest_gz_base.with_name(dest_gz_base.name + ".gz")
        self.assertTrue(gz_path.exists())
        self.assertFalse(dest_gz_base.exists())

        with gzip.open(gz_path, "rb") as f:
            decompressed = f.read()
        self.assertEqual(decompressed, dest_plain.read_bytes())

    def test_deterministic_recompression_byte_equality(self):
        data = json.dumps({"a": 1, "b": "x" * 5000}).encode() * 3
        first = backup.gzip_compress_deterministic(data)
        second = backup.gzip_compress_deterministic(data)
        self.assertEqual(first, second)

    def test_mtime_skip_on_gz_dest(self):
        src = self.tmp / "src.jsonl"
        dest = self.tmp / "dest.jsonl"
        src.write_bytes(b"hello world\n")

        result1 = backup.process_file(src, dest, "raw", force=False, dry_run=False, compress=True)
        self.assertEqual(result1, "added")
        gz_path = dest.with_name(dest.name + ".gz")
        self.assertTrue(gz_path.exists())

        result2 = backup.process_file(src, dest, "raw", force=False, dry_run=False, compress=True)
        self.assertEqual(result2, "skipped")

        new_mtime = os.path.getmtime(src) + 5
        src.write_bytes(b"hello world, updated\n")
        os.utime(src, (new_mtime, new_mtime))
        result3 = backup.process_file(src, dest, "raw", force=False, dry_run=False, compress=True)
        self.assertEqual(result3, "updated")

    def test_keep_larger_via_isize_compressed_smaller_uncompressed_larger(self):
        # Existing .gz holds a bigger uncompressed payload than the new
        # source, even though its compressed-on-disk size is small (highly
        # compressible repeated content) -- the guard must compare
        # uncompressed sizes, not on-disk gz sizes.
        src = self.tmp / "src.jsonl"
        dest = self.tmp / "dest.jsonl"
        gz_path = dest.with_name(dest.name + ".gz")
        gz_path.parent.mkdir(parents=True, exist_ok=True)

        big_repetitive = b"x" * 100000  # compresses tiny, but uncompressed size is huge
        gz_path.write_bytes(backup.gzip_compress_deterministic(big_repetitive))
        self.assertLess(gz_path.stat().st_size, len(big_repetitive))  # sanity: compressed shrinks
        os.utime(gz_path, (1000, 1000))

        src.write_bytes(b"y" * 10)  # much smaller uncompressed than existing
        os.utime(src, (2000, 2000))  # newer

        result = backup.process_file(src, dest, "raw", force=False, dry_run=False, compress=True)
        self.assertEqual(result, "kept-larger")
        # untouched
        with gzip.open(gz_path, "rb") as f:
            self.assertEqual(f.read(), big_repetitive)

    def test_keep_larger_via_isize_compressed_larger_uncompressed_smaller(self):
        # Inverse: existing .gz's on-disk (compressed) size is bigger than
        # the new source's raw byte length, but its *uncompressed* payload
        # is smaller -- so the guard must NOT kick in, and the write must
        # proceed.
        src = self.tmp / "src.jsonl"
        dest = self.tmp / "dest.jsonl"
        gz_path = dest.with_name(dest.name + ".gz")
        gz_path.parent.mkdir(parents=True, exist_ok=True)

        # High-entropy small payload compresses poorly (grows on disk).
        small_incompressible = os.urandom(200)
        gz_path.write_bytes(backup.gzip_compress_deterministic(small_incompressible))
        os.utime(gz_path, (1000, 1000))

        new_content = b"z" * 5000  # bigger uncompressed than the existing payload
        src.write_bytes(new_content)
        os.utime(src, (2000, 2000))

        self.assertGreater(gz_path.stat().st_size, len(new_content) - 4900)  # sanity, loose
        result = backup.process_file(src, dest, "raw", force=False, dry_run=False, compress=True)
        self.assertEqual(result, "updated")
        with gzip.open(gz_path, "rb") as f:
            self.assertEqual(f.read(), new_content)

    def test_plain_to_gz_migration_removes_plain_only_after_successful_write(self):
        src = self.tmp / "src.jsonl"
        dest = self.tmp / "dest.jsonl"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"old plain content\n")
        os.utime(dest, (1000, 1000))

        src.write_bytes(b"new content, longer than old\n")
        os.utime(src, (2000, 2000))

        result = backup.process_file(src, dest, "raw", force=False, dry_run=False, compress=True)
        self.assertEqual(result, "updated")
        gz_path = dest.with_name(dest.name + ".gz")
        self.assertTrue(gz_path.exists())
        self.assertFalse(dest.exists())  # plain removed after successful .gz write
        with gzip.open(gz_path, "rb") as f:
            self.assertEqual(f.read(), b"new content, longer than old\n")

    def test_plain_to_gz_migration_mtime_skip_uses_plain_mtime(self):
        src = self.tmp / "src.jsonl"
        dest = self.tmp / "dest.jsonl"
        dest.write_bytes(b"content\n")
        os.utime(dest, (5000, 5000))
        src.write_bytes(b"content\n")
        os.utime(src, (1000, 1000))  # older than the existing plain copy

        result = backup.process_file(src, dest, "raw", force=False, dry_run=False, compress=True)
        self.assertEqual(result, "skipped")
        self.assertTrue(dest.exists())  # nothing written, nothing migrated
        self.assertFalse(dest.with_name(dest.name + ".gz").exists())

    def test_gz_to_plain_reverse_migration(self):
        src = self.tmp / "src.jsonl"
        dest = self.tmp / "dest.jsonl"
        gz_path = dest.with_name(dest.name + ".gz")
        gz_path.parent.mkdir(parents=True, exist_ok=True)
        gz_path.write_bytes(backup.gzip_compress_deterministic(b"old gz content\n"))
        os.utime(gz_path, (1000, 1000))

        src.write_bytes(b"new plain content\n")
        os.utime(src, (2000, 2000))

        result = backup.process_file(src, dest, "raw", force=False, dry_run=False, compress=False)
        self.assertEqual(result, "updated")
        self.assertTrue(dest.exists())
        self.assertEqual(dest.read_bytes(), b"new plain content\n")
        self.assertFalse(gz_path.exists())  # old .gz removed after successful plain write

    def test_force_bypasses_guards_with_compress(self):
        src = self.tmp / "src.jsonl"
        dest = self.tmp / "dest.jsonl"
        gz_path = dest.with_name(dest.name + ".gz")
        gz_path.parent.mkdir(parents=True, exist_ok=True)
        gz_path.write_bytes(backup.gzip_compress_deterministic(b"x" * 1000))
        os.utime(gz_path, (5000, 5000))

        src.write_bytes(b"y" * 10)  # older AND smaller uncompressed
        os.utime(src, (1000, 1000))

        result = backup.process_file(src, dest, "raw", force=True, dry_run=False, compress=True)
        self.assertEqual(result, "updated")
        with gzip.open(gz_path, "rb") as f:
            self.assertEqual(f.read(), b"y" * 10)

    def test_dry_run_writes_nothing_with_compress(self):
        src = self.tmp / "src.jsonl"
        dest = self.tmp / "dest.jsonl"
        src.write_bytes(b"hello\n")

        result = backup.process_file(src, dest, "raw", force=False, dry_run=True, compress=True)
        self.assertEqual(result, "added")
        self.assertFalse(dest.exists())
        self.assertFalse(dest.with_name(dest.name + ".gz").exists())

    def test_gzip_isize_matches_uncompressed_length(self):
        with tempfile.TemporaryDirectory() as td:
            gz_path = Path(td) / "f.jsonl.gz"
            payload = b"abc" * 12345
            gz_path.write_bytes(backup.gzip_compress_deterministic(payload))
            self.assertEqual(backup.gzip_isize(gz_path), len(payload))
            self.assertEqual(backup.existing_uncompressed_size(gz_path), len(payload))

    def test_corrupt_gz_does_not_permanently_wedge_keep_larger_guard(self):
        # A truncated/corrupted .gz (e.g. left by a non-atomic write
        # interrupted mid-way) must NOT be trusted for its trailing 4 bytes
        # -- those can decode to an arbitrary huge "uncompressed size" that
        # would make every future run's real content compare smaller
        # forever, silently and permanently wedging the corrupt copy.
        src = self.tmp / "src.jsonl"
        dest = self.tmp / "dest.jsonl"
        gz_path = dest.with_name(dest.name + ".gz")
        gz_path.parent.mkdir(parents=True, exist_ok=True)

        # 8-byte "gzip" whose header is well-formed enough to have a magic
        # byte pair but whose trailing 4 bytes are not a real ISIZE footer
        # for any actual compressed stream.
        gz_path.write_bytes(b"\x1f\x8b\x08\x00" + b"\xff\xff\xff\xff")
        os.utime(gz_path, (1000, 1000))

        src.write_bytes(b"real content, correctly archived this time\n")
        os.utime(src, (2000, 2000))  # newer, so mtime-skip doesn't trip first

        result = backup.process_file(src, dest, "raw", force=False, dry_run=False, compress=True)
        self.assertNotEqual(result, "kept-larger")
        self.assertEqual(result, "updated")
        with gzip.open(gz_path, "rb") as f:
            self.assertEqual(f.read(), b"real content, correctly archived this time\n")

    def test_corrupt_gz_bad_magic_raises_in_existing_uncompressed_size(self):
        with tempfile.TemporaryDirectory() as td:
            gz_path = Path(td) / "f.jsonl.gz"
            gz_path.write_bytes(b"not a gzip file at all")
            with self.assertRaises(OSError):
                backup.existing_uncompressed_size(gz_path)

    def test_stale_other_format_cleanup_retried_on_later_run(self):
        # Simulates a prior run whose new-format (.gz) write succeeded but
        # whose old-format-cleanup unlink() didn't complete (interrupted, or
        # failed and was logged rather than crashing the run): both the
        # active .gz and the stale plain file exist on disk from the start.
        # A later run -- even with no source change at all -- must still
        # remove the stale leftover rather than leaving it forever, since
        # the mtime-skip check alone (satisfied by the .gz) would otherwise
        # never reach the migration-cleanup code path again.
        src = self.tmp / "src.jsonl"
        dest = self.tmp / "dest.jsonl"
        gz_path = dest.with_name(dest.name + ".gz")
        dest.parent.mkdir(parents=True, exist_ok=True)

        src.write_bytes(b"content\n")
        os.utime(src, (1000, 1000))
        gz_path.write_bytes(backup.gzip_compress_deterministic(b"content\n"))
        os.utime(gz_path, (1000, 1000))
        dest.write_bytes(b"content\n")  # stale leftover from an incomplete migration
        os.utime(dest, (1000, 1000))

        self.assertTrue(dest.exists())
        self.assertTrue(gz_path.exists())

        result = backup.process_file(src, dest, "raw", force=False, dry_run=False, compress=True)
        self.assertEqual(result, "skipped")  # no new content -- but cleanup still runs
        self.assertTrue(gz_path.exists())
        self.assertFalse(dest.exists())  # stale plain file finally removed


# ---------------------------------------------------------------------------
# Log rotation
# ---------------------------------------------------------------------------


class TestLogRotation(unittest.TestCase):
    def test_rotates_when_over_threshold(self):
        with tempfile.TemporaryDirectory() as td:
            log_path = Path(td) / "backup.log"
            log_path.write_bytes(b"x" * (backup.LOG_ROTATE_MAX_BYTES + 1))
            backup.rotate_log_if_large(log_path)
            rotated = Path(str(log_path) + ".1")
            self.assertTrue(rotated.exists())
            self.assertFalse(log_path.exists())

    def test_no_rotate_under_threshold(self):
        with tempfile.TemporaryDirectory() as td:
            log_path = Path(td) / "backup.log"
            log_path.write_bytes(b"small")
            backup.rotate_log_if_large(log_path)
            self.assertTrue(log_path.exists())
            self.assertFalse(Path(str(log_path) + ".1").exists())


# ---------------------------------------------------------------------------
# Integration (subprocess) tests
# ---------------------------------------------------------------------------


class TestIntegration(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.fake_home = self.tmp / "home"
        self.archive = self.tmp / "archive"
        self.fake_home.mkdir()
        self.archive.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def _env(self, machine_id="testmachine"):
        return {
            "HOME": str(self.fake_home),
            "TRANSCRIPT_ARCHIVE_DIR": str(self.archive),
            "TRANSCRIPT_ARCHIVE_MACHINE_ID": machine_id,
        }

    def test_missing_archive_dir_exit_2(self):
        env = dict(os.environ)
        env.pop("TRANSCRIPT_ARCHIVE_DIR", None)
        proc = subprocess.run(
            [sys.executable, str(BACKUP_PY)],
            env={**env, "TRANSCRIPT_ARCHIVE_DIR": ""},
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("TRANSCRIPT_ARCHIVE_DIR", proc.stderr)

    def test_no_sources_exit_1(self):
        proc = run_backup(self._env())
        self.assertEqual(proc.returncode, 1)
        self.assertIn("SUMMARY", proc.stdout.splitlines()[-1])
        self.assertIn("machine=testmachine", proc.stdout)

    def test_clean_run_exit_0_and_second_run_all_skipped(self):
        projects = self.fake_home / ".claude" / "projects" / "proj1"
        projects.mkdir(parents=True)
        (projects / "session1.jsonl").write_text(json.dumps({"a": 1}) + "\n")

        proc1 = run_backup(self._env())
        self.assertEqual(proc1.returncode, 0)
        last_line = proc1.stdout.strip().splitlines()[-1]
        self.assertIn("SUMMARY", last_line)
        self.assertIn("added=1", last_line)

        proc2 = run_backup(self._env())
        self.assertEqual(proc2.returncode, 0)
        last_line2 = proc2.stdout.strip().splitlines()[-1]
        self.assertIn("skipped=1", last_line2)
        self.assertIn("added=0", last_line2)

        dest = self.archive / "testmachine" / "claude" / "projects" / "proj1" / "session1.jsonl"
        self.assertTrue(dest.exists())
        self.assertEqual(json.loads(dest.read_text()), {"a": 1})

    def test_dry_run_writes_nothing_end_to_end(self):
        projects = self.fake_home / ".claude" / "projects"
        projects.mkdir(parents=True)
        (projects / "s.jsonl").write_text(json.dumps({"a": 1}) + "\n")

        proc = run_backup(self._env(), args=["--dry-run"])
        self.assertEqual(proc.returncode, 0)
        dest = self.archive / "testmachine" / "claude" / "projects" / "s.jsonl"
        self.assertFalse(dest.exists())
        # --dry-run must leave zero trace on TRANSCRIPT_ARCHIVE_DIR: no
        # machine-namespaced dir, no backup.log, and the SUMMARY's
        # archive_total shouldn't count a log file the run itself created.
        self.assertFalse((self.archive / "testmachine").exists())
        last_line = proc.stdout.strip().splitlines()[-1]
        self.assertIn("archive_total=0 files", last_line)

    def test_recursion_error_on_json_loads_does_not_abort_run(self):
        projects = self.fake_home / ".claude" / "projects" / "proj1"
        projects.mkdir(parents=True)
        depth = 200000
        evil = ("{\"x\":" * depth) + "1" + ("}" * depth)
        (projects / "evil.jsonl").write_text(evil + "\n")
        (projects / "good.jsonl").write_text(json.dumps({"a": 1}) + "\n")

        proc = run_backup(self._env())
        self.assertEqual(proc.returncode, 0)
        last_line = proc.stdout.strip().splitlines()[-1]
        self.assertIn("SUMMARY", last_line)
        self.assertIn("added=2", last_line)
        self.assertTrue(
            (self.archive / "testmachine" / "claude" / "projects" / "proj1" / "good.jsonl").exists()
        )

    def test_old_layout_warning(self):
        (self.archive / "claude").mkdir()
        projects = self.fake_home / ".claude" / "projects"
        projects.mkdir(parents=True)
        (projects / "s.jsonl").write_text(json.dumps({"a": 1}) + "\n")

        proc = run_backup(self._env())
        self.assertIn("WARN: old", proc.stdout)
        self.assertIn("migrate", proc.stdout.lower())

    def test_machine_id_sanitized_in_layout(self):
        projects = self.fake_home / ".claude" / "projects"
        projects.mkdir(parents=True)
        (projects / "s.jsonl").write_text(json.dumps({"a": 1}) + "\n")

        proc = run_backup(self._env(machine_id="My.Weird Host!"))
        self.assertEqual(proc.returncode, 0)
        self.assertTrue((self.archive / "my-weird-host-").exists())

    def test_tasks_raw_copy(self):
        tasks = self.fake_home / ".claude" / "tasks"
        tasks.mkdir(parents=True)
        (tasks / "task1.md").write_text("just some raw task content\n")

        proc = run_backup(self._env())
        self.assertEqual(proc.returncode, 0)
        dest = self.archive / "testmachine" / "claude" / "tasks" / "task1.md"
        self.assertEqual(dest.read_text(), "just some raw task content\n")

    def test_codex_history_raw_copy_and_sessions_stripped(self):
        codex_home = self.fake_home / ".codex"
        codex_home.mkdir(parents=True)
        (codex_home / "history.jsonl").write_text(json.dumps({"h": 1}) + "\n")
        sessions = codex_home / "sessions"
        sessions.mkdir()
        line = {
            "timestamp": "t",
            "type": "event",
            "payload": {
                "type": "custom_tool_call_output",
                "call_id": "c1",
                "output": [{"type": "input_image", "image_url": "data:image/png;base64," + "Z" * 300}],
            },
        }
        (sessions / "sess1.jsonl").write_text(json.dumps(line) + "\n")

        proc = run_backup(self._env())
        self.assertEqual(proc.returncode, 0)
        hist_dest = self.archive / "testmachine" / "codex" / "history.jsonl"
        self.assertEqual(json.loads(hist_dest.read_text()), {"h": 1})

        sess_dest = self.archive / "testmachine" / "codex" / "sessions" / "sess1.jsonl"
        out_obj = json.loads(sess_dest.read_text())
        self.assertTrue(out_obj["payload"]["output"][0]["image_url"].startswith("__IMAGE_TOMBSTONE("))

    def test_compress_flag_end_to_end(self):
        projects = self.fake_home / ".claude" / "projects"
        projects.mkdir(parents=True)
        (projects / "s.jsonl").write_text(json.dumps({"a": 1}) + "\n")

        proc = run_backup(self._env(), args=["--compress"])
        self.assertEqual(proc.returncode, 0)
        last_line = proc.stdout.strip().splitlines()[-1]
        self.assertIn("added=1", last_line)
        dest_gz = self.archive / "testmachine" / "claude" / "projects" / "s.jsonl.gz"
        self.assertTrue(dest_gz.exists())
        with gzip.open(dest_gz, "rb") as f:
            self.assertEqual(json.loads(f.read()), {"a": 1})

        proc2 = run_backup(self._env(), args=["--compress"])
        self.assertEqual(proc2.returncode, 0)
        last_line2 = proc2.stdout.strip().splitlines()[-1]
        self.assertIn("skipped=1", last_line2)
        self.assertIn("added=0", last_line2)

    def test_error_exit_code_when_source_unreadable(self):
        projects = self.fake_home / ".claude" / "projects"
        projects.mkdir(parents=True)
        bad = projects / "bad.jsonl"
        bad.write_text("{}\n")
        os.chmod(bad, 0o000)
        try:
            proc = run_backup(self._env())
        finally:
            os.chmod(bad, 0o644)
        # Root can typically still read a 000 file, so only assert the
        # exit-code contract when the sandbox actually enforced the perm.
        if proc.returncode == 1:
            self.assertIn("errors=1", proc.stdout)
        else:
            self.assertEqual(proc.returncode, 0)


if __name__ == "__main__":
    unittest.main()
