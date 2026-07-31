"""Stdlib unittest suite for search.py (transcript FTS index).

All tests run against a temp HOME, temp archive dir, and temp DB via env
vars, importing search.py in-process. No network, no real archive.
"""

from __future__ import annotations

import gzip
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

import search


def transcript_line(role: str, text: str, ts: str = "2026-07-01T12:00:00.000Z") -> str:
    return json.dumps(
        {
            "type": role,
            "timestamp": ts,
            "message": {"role": role, "content": [{"type": "text", "text": text}]},
        }
    )


def tool_lines(ts: str = "2026-07-01T12:01:00.000Z") -> list[str]:
    return [
        json.dumps(
            {
                "type": "assistant",
                "timestamp": ts,
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Bash",
                            "input": {"command": "rm -rf /tmp/zebra_dir"},
                        }
                    ]
                },
            }
        ),
        json.dumps(
            {
                "type": "user",
                "timestamp": ts,
                "message": {
                    "content": [
                        {
                            "type": "tool_result",
                            "content": [{"type": "text", "text": "zebra_dir removed ok"}],
                        }
                    ]
                },
            }
        ),
    ]


class SearchTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.home = root / "home"
        self.archive = root / "archive"
        self.live = self.home / ".claude/projects/-Users-x-proj"
        self.live.mkdir(parents=True)
        machine_projects = self.archive / "laptop/claude/projects/-Users-x-old"
        machine_projects.mkdir(parents=True)
        self.archive_session = machine_projects / "aaaa1111.jsonl.gz"
        with gzip.open(self.archive_session, "wt") as fh:
            fh.write(
                transcript_line("assistant", "the archived pangolin invoice discussion")
                + "\n"
            )
        self.live_session = self.live / "bbbb2222.jsonl"
        lines = [transcript_line("user", "please fix the flamingo bug")] + tool_lines()
        self.live_session.write_text("\n".join(lines) + "\n")
        self.env = mock.patch.dict(
            os.environ,
            {
                "HOME": str(self.home),
                "TRANSCRIPT_ARCHIVE_DIR": str(self.archive),
                "TRANSCRIPT_SEARCH_DB": str(root / "test.db"),
            },
        )
        self.env.start()
        # Path.home() reads HOME at call time on POSIX; patch to be explicit.
        self.home_patch = mock.patch.object(Path, "home", return_value=self.home)
        self.home_patch.start()

    def tearDown(self):
        self.home_patch.stop()
        self.env.stop()
        self.tmp.cleanup()

    def index(self) -> str:
        out = io.StringIO()
        with redirect_stdout(out):
            search.cmd_index()
        return out.getvalue()

    def query(self, *argv: str) -> str:
        out = io.StringIO()
        with redirect_stdout(out):
            search.cmd_search(search.parse_args(["search", *argv]))
        return out.getvalue()

    def test_index_ingests_live_and_gz_archive(self):
        summary = self.index()
        self.assertIn("indexed 2 new/changed files", summary)
        self.assertIn("pangolin", self.query("pangolin"))
        self.assertIn("flamingo", self.query("flamingo"))

    def test_tool_blocks_are_rows_with_their_own_roles(self):
        self.index()
        self.assertIn("tool_use", self.query("zebra_dir", "--role", "tool_use"))
        self.assertIn("tool_result", self.query("removed", "--role", "tool_result"))
        self.assertIn("no matches", self.query("zebra_dir", "--role", "assistant"))

    def test_project_and_machine_attribution(self):
        self.index()
        hit = self.query("pangolin")
        self.assertIn("-Users-x-old", hit)
        self.assertIn(str(self.archive_session), hit)

    def test_incremental_skip_and_reingest_on_change(self):
        self.index()
        self.assertIn("(2 unchanged)", self.index())
        with open(self.live_session, "a") as fh:
            fh.write(transcript_line("user", "now discuss the axolotl migration") + "\n")
        os.utime(self.live_session, (1e9, 1e9))  # force distinct mtime
        self.assertIn("indexed 1 new/changed files", self.index())
        self.assertIn("axolotl", self.query("axolotl"))
        # old content survives re-ingest exactly once (snippet marks the hit)
        self.assertEqual(self.query("flamingo").count(">>>flamingo<<<"), 1)

    def test_phrase_and_date_filters(self):
        self.index()
        self.assertIn("pangolin", self.query('"archived pangolin invoice"'))
        self.assertIn("no matches", self.query("pangolin", "--since", "2026-07-02"))
        self.assertIn("pangolin", self.query("pangolin", "--until", "2026-07-02"))

    def test_files_mode_prints_unique_paths(self):
        self.index()
        out = self.query("flamingo", "--files").strip().splitlines()
        self.assertEqual(out, [str(self.live_session)])

    def test_live_only_when_archive_env_unset(self):
        del os.environ["TRANSCRIPT_ARCHIVE_DIR"]
        sources = search.resolve_sources()
        self.assertEqual(list(sources), ["live"])

    def test_truncated_gz_skipped_and_retried_next_run(self):
        bad = self.archive / "laptop/claude/projects/-Users-x-old/cccc3333.jsonl.gz"
        with gzip.open(bad, "wt") as fh:
            fh.write(transcript_line("user", "unreachable ocelot content") + "\n")
        raw = bad.read_bytes()
        bad.write_bytes(raw[: len(raw) - 8])  # strip gzip trailer -> EOFError
        err = io.StringIO()
        with mock.patch("sys.stderr", err):
            summary = self.index()
        self.assertIn("read-failed (will retry)", summary)
        self.assertIn("cccc3333", err.getvalue())
        # healthy files still indexed; broken one absent and not marked done
        self.assertIn("flamingo", self.query("flamingo"))
        self.assertIn("no matches", self.query("ocelot"))
        bad.write_bytes(raw)  # repair -> next run picks it up
        with mock.patch("sys.stderr", io.StringIO()):
            self.assertIn("indexed 1 new/changed files", self.index())
        self.assertIn("ocelot", self.query("ocelot"))

    def test_malformed_lines_are_skipped_not_fatal(self):
        with open(self.live_session, "a") as fh:
            fh.write("not json at all\n{\"half\": \n")
        self.index()
        self.assertIn("flamingo", self.query("flamingo"))


if __name__ == "__main__":
    unittest.main()
