#!/usr/bin/env python3
"""Generate a frozen per-model pricing table from a vendored LiteLLM snapshot
plus hand-maintained dated overrides.

Reads litellm_snapshot.json (first-party anthropic claude entries only,
see vendor_pricing.py) and pricing_overrides.json (dated regimes that a
point-in-time registry snapshot can't represent, e.g. a price flip),
converts to USD per million tokens, and writes pricing_generated.py:

- PRICING_BY_MODEL: exact model-ID rates, including above-200k tier fields
  (in_200k, out_200k, cache_5m_200k, cache_1h_200k, cache_read_200k) only
  for entries where the registry carries them.
- PRICING_BY_FAMILY: newest-per-family fallback for model IDs/aliases not
  in the registry (e.g. "sonnet", "opus[1m]").
- PRICING_DATED: dated regime overrides from pricing_overrides.json, sorted
  by model then effective_from, checked before PRICING_BY_MODEL at lookup
  time.

Invariant: cache_1h >= cache_5m and cache_1h within +/-10% of 2x input.
The registry ships corrupt cache_1h values for some claude-3-era rows
(copy-pasted from an unrelated model); violations are auto-corrected to
exactly 2x input rather than skipped — skipping would fall back to
family-fallback pricing, which is worse (claude-3-opus at opus-5 rates
would undercount 15/75 real vs 5/25 fallback). Corrections are listed in
the generated file's header comment. Missing cache_1h is derived as
2x input (Anthropic's documented rule) without being called a correction.

Hard-fails (non-zero exit) if a FAMILY_REPRESENTATIVE model ID is absent
from the registry, or has missing/zero input or output cost.

Usage: generate_pricing.py <snapshot.json> <overrides.json> <out.py>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

MTOK = 1_000_000
FIELDS = {
    "in": "input_cost_per_token",
    "out": "output_cost_per_token",
    "cache_5m": "cache_creation_input_token_cost",
    "cache_1h": "cache_creation_input_token_cost_above_1hr",
    "cache_read": "cache_read_input_token_cost",
}
FIELDS_200K = {
    "in_200k": "input_cost_per_token_above_200k_tokens",
    "out_200k": "output_cost_per_token_above_200k_tokens",
    "cache_5m_200k": "cache_creation_input_token_cost_above_200k_tokens",
    "cache_1h_200k": "cache_creation_input_token_cost_above_1hr_above_200k_tokens",
    "cache_read_200k": "cache_read_input_token_cost_above_200k_tokens",
}
# newest-generation representative per family, used as fallback for unknown/alias IDs
FAMILY_REPRESENTATIVE = {
    "fable": "claude-fable-5",
    "opus": "claude-opus-5",
    "sonnet": "claude-sonnet-5",
    "haiku": "claude-haiku-4-5",
}
CACHE_1H_TOLERANCE = 0.10  # +/-10% of 2x input before it's flagged as corrupt


def extract(registry: dict) -> tuple[dict[str, dict[str, float]], list[str]]:
    """Return (table, corrections). corrections is a list of human-readable notes."""
    table: dict[str, dict[str, float]] = {}
    corrections: list[str] = []
    for model_id, entry in registry.items():
        if not isinstance(entry, dict):
            continue
        rates: dict[str, float] = {}
        for short, field in FIELDS.items():
            raw = entry.get(field)
            if raw is not None:
                rates[short] = round(raw * MTOK, 6)
        for short, field in FIELDS_200K.items():
            raw = entry.get(field)
            if raw is not None:
                rates[short] = round(raw * MTOK, 6)

        if "in" not in rates or "out" not in rates:
            continue

        two_x_input = 2 * rates["in"]
        if "cache_1h" not in rates:
            # older entries lack the 1h-cache tier; derive as 2x input (Anthropic's rule)
            rates["cache_1h"] = round(two_x_input, 6)
        else:
            cache_5m = rates.get("cache_5m", 0.0)
            off_by = abs(rates["cache_1h"] - two_x_input) / two_x_input if two_x_input else 0.0
            corrupt = rates["cache_1h"] < cache_5m or off_by > CACHE_1H_TOLERANCE
            if corrupt:
                corrections.append(
                    f"{model_id}: cache_1h {rates['cache_1h']} -> {round(two_x_input, 6)} "
                    f"(registry value violated cache_1h>=cache_5m or +/-{int(CACHE_1H_TOLERANCE * 100)}% "
                    f"of 2x input={two_x_input})"
                )
                rates["cache_1h"] = round(two_x_input, 6)

        table[model_id] = rates
    return table, corrections


def load_overrides(path: Path) -> list[dict]:
    overrides = json.loads(path.read_text())
    for o in overrides:
        missing = {"model", "effective_from", "effective_until", "rates"} - o.keys()
        if missing:
            sys.exit(f"pricing_overrides.json entry missing keys {missing}: {o}")
    overrides.sort(key=lambda o: (o["model"], o["effective_from"] or ""))
    return overrides


def main() -> None:
    if len(sys.argv) != 4:
        sys.exit(f"usage: {sys.argv[0]} <snapshot.json> <overrides.json> <out.py>")
    snapshot_path, overrides_path, dst = sys.argv[1], sys.argv[2], sys.argv[3]

    registry = json.loads(Path(snapshot_path).read_text())
    vendored_at = (registry.get("_meta") or {}).get("vendored_at")
    if not vendored_at:
        sys.exit(
            f"{snapshot_path} has no _meta.vendored_at stamp — re-vendor it with "
            "vendor_pricing.py so snapshot age is trackable"
        )
    table, corrections = extract(registry)

    missing_reps = [fam for fam, mid in FAMILY_REPRESENTATIVE.items() if mid not in table]
    if missing_reps:
        sys.exit(f"registry missing family representatives: {missing_reps}")
    zero_reps = [
        fam
        for fam, mid in FAMILY_REPRESENTATIVE.items()
        if not table[mid].get("in") or not table[mid].get("out")
    ]
    if zero_reps:
        sys.exit(f"family representatives with missing/zero in or out cost: {zero_reps}")

    fallback = {fam: table[mid] for fam, mid in FAMILY_REPRESENTATIVE.items()}
    dated = load_overrides(Path(overrides_path))

    with open(dst, "w") as fh:
        fh.write('"""Frozen pricing table — GENERATED by generate_pricing.py, do not hand-edit.\n\n')
        fh.write("Source: litellm_snapshot.json (vendored LiteLLM registry, first-party\n")
        fh.write("anthropic claude entries) + pricing_overrides.json (dated regimes).\n")
        fh.write("USD per million tokens.\n")
        if corrections:
            fh.write("\nInvariant corrections applied (registry cache_1h was corrupt, corrected\n")
            fh.write("to 2x input per Anthropic's documented rule):\n")
            for note in corrections:
                fh.write(f"- {note}\n")
        fh.write('"""\n\n')
        fh.write(f'SNAPSHOT_VENDORED_AT = "{vendored_at}"\n\n')
        fh.write("PRICING_BY_MODEL = ")
        fh.write(json.dumps(table, indent=4, sort_keys=True).replace("null", "None"))
        fh.write("\n\nPRICING_BY_FAMILY = ")
        fh.write(json.dumps(fallback, indent=4, sort_keys=True))
        fh.write("\n\nPRICING_DATED = ")
        fh.write(json.dumps(dated, indent=4, sort_keys=True).replace("null", "None"))
        fh.write("\n")
    print(
        f"wrote {len(table)} model entries, {len(fallback)} family fallbacks, "
        f"{len(dated)} dated overrides, {len(corrections)} invariant corrections to {dst}"
    )


if __name__ == "__main__":
    main()
