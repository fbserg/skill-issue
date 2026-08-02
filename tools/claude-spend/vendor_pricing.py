#!/usr/bin/env python3
"""Vendor a snapshot of LiteLLM's pricing registry, stripped to first-party
Anthropic Claude entries.

Manual invocation only — no hook, no runtime network fetch. Re-run this
(then generate_pricing.py) when Anthropic ships new models or a price
change; commit the refreshed litellm_snapshot.json and pricing_generated.py
together.

Usage:
    python3 vendor_pricing.py [source] [--out PATH]

    source   URL or local file path to model_prices_and_context_window.json.
             Defaults to LiteLLM's raw GitHub URL.
    --out    Output path [default: litellm_snapshot.json next to this script]
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_SOURCE = (
    "https://raw.githubusercontent.com/BerriAI/litellm/main/"
    "model_prices_and_context_window.json"
)


def load_registry(source: str) -> dict:
    if source.startswith("http://") or source.startswith("https://"):
        with urllib.request.urlopen(source) as resp:  # noqa: S310 - manual invocation only
            return json.load(resp)
    return json.loads(Path(source).read_text())


def strip_to_anthropic_claude(registry: dict) -> dict:
    """Keep only first-party `anthropic` entries whose key starts with `claude`.

    Bedrock/Vertex re-listings carry region premiums and aren't what
    claude-spend needs; non-claude anthropic entries don't exist but the
    prefix check is cheap insurance against registry key drift.
    """
    return {
        model_id: entry
        for model_id, entry in registry.items()
        if isinstance(entry, dict)
        and entry.get("litellm_provider") == "anthropic"
        and model_id.startswith("claude")
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source", nargs="?", default=DEFAULT_SOURCE, help="URL or local file path to the LiteLLM registry")
    ap.add_argument(
        "--out",
        default=str(Path(__file__).resolve().parent / "litellm_snapshot.json"),
        help="Output path for the stripped snapshot",
    )
    args = ap.parse_args()

    registry = load_registry(args.source)
    snapshot = strip_to_anthropic_claude(registry)
    if not snapshot:
        sys.exit(f"no anthropic/claude entries found in {args.source} — refusing to write an empty snapshot")

    snapshot["_meta"] = {
        "vendored_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "source": args.source,
    }
    out_path = Path(args.out)
    out_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n")
    print(f"wrote {len(snapshot) - 1} anthropic claude entries from {args.source} to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
