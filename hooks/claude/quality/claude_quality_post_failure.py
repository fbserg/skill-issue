#!/usr/bin/env python3
# Same as PostToolUse: stage touched paths so a partial-write-then-fail still gets
# picked up by PostToolBatch.
from claude_quality_lib import run_post_tool_stage

if __name__ == "__main__":
    raise SystemExit(run_post_tool_stage())
