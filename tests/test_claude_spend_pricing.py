"""Tests for tools/claude-spend's registry-derived, dated pricing (issue #28).

Covers generate_pricing.py (extraction, invariant auto-correction, cache_1h
derivation, missing-representative hard-fail, drift against the committed
pricing_generated.py) and spend.py's pricing lookup (dated override
precedence, era-correct per-model rates, above-200k tiering only where the
registry carries it, family fallback / unpriced accounting).

Run with: python3 -m pytest tests/test_claude_spend_pricing.py -v
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CLAUDE_SPEND_DIR = REPO_ROOT / "tools" / "claude-spend"

sys.path.insert(0, str(CLAUDE_SPEND_DIR))

import generate_pricing  # noqa: E402
import spend  # noqa: E402


# ---------------------------------------------------------------------------
# generate_pricing.py
# ---------------------------------------------------------------------------


def test_extract_converts_token_costs_to_usd_per_mtok() -> None:
    registry = {
        "claude-test-1": {
            "litellm_provider": "anthropic",
            "input_cost_per_token": 3e-06,
            "output_cost_per_token": 1.5e-05,
            "cache_creation_input_token_cost": 3.75e-06,
            "cache_creation_input_token_cost_above_1hr": 6e-06,
            "cache_read_input_token_cost": 3e-07,
        }
    }
    table, corrections = generate_pricing.extract(registry)
    assert corrections == []
    assert table["claude-test-1"] == {
        "in": 3.0,
        "out": 15.0,
        "cache_5m": 3.75,
        "cache_1h": 6.0,
        "cache_read": 0.3,
    }


def test_extract_derives_cache_1h_as_2x_input_when_field_absent() -> None:
    registry = {
        "claude-test-old": {
            "litellm_provider": "anthropic",
            "input_cost_per_token": 1e-06,
            "output_cost_per_token": 5e-06,
        }
    }
    table, corrections = generate_pricing.extract(registry)
    assert corrections == []  # derivation is not a "correction" — no source value to contradict
    assert table["claude-test-old"]["cache_1h"] == 2.0


def test_extract_auto_corrects_corrupt_cache_1h_to_2x_input() -> None:
    """Reproduces the real registry defect: claude-3-opus's cache_1h is a
    flat 6e-06 (copy-pasted from an unrelated model), both violating
    cache_1h >= cache_5m and being wildly off 2x input=30."""
    registry = {
        "claude-3-opus-20240229": {
            "litellm_provider": "anthropic",
            "input_cost_per_token": 1.5e-05,
            "output_cost_per_token": 7.5e-05,
            "cache_creation_input_token_cost": 1.875e-05,
            "cache_creation_input_token_cost_above_1hr": 6e-06,  # corrupt: < cache_5m, and != 2x in
            "cache_read_input_token_cost": 1.5e-06,
        }
    }
    table, corrections = generate_pricing.extract(registry)
    assert table["claude-3-opus-20240229"]["cache_1h"] == 30.0  # corrected to 2x input
    assert len(corrections) == 1
    assert "claude-3-opus-20240229" in corrections[0]


def test_extract_synthetic_corrupt_entry_within_tolerance_not_corrected() -> None:
    """A cache_1h within +/-10% of 2x input, and >= cache_5m, is left alone."""
    registry = {
        "claude-test-close": {
            "litellm_provider": "anthropic",
            "input_cost_per_token": 3e-06,
            "output_cost_per_token": 1.5e-05,
            "cache_creation_input_token_cost": 3.75e-06,
            "cache_creation_input_token_cost_above_1hr": 6.3e-06,  # 2x=6.0, +5% — within tolerance
        }
    }
    table, corrections = generate_pricing.extract(registry)
    assert corrections == []
    assert table["claude-test-close"]["cache_1h"] == 6.3


def test_extract_keeps_above_200k_tier_fields_only_when_present() -> None:
    registry = {
        "claude-tiered": {
            "litellm_provider": "anthropic",
            "input_cost_per_token": 3e-06,
            "output_cost_per_token": 1.5e-05,
            "input_cost_per_token_above_200k_tokens": 6e-06,
            "output_cost_per_token_above_200k_tokens": 2.25e-05,
        },
        "claude-flat": {
            "litellm_provider": "anthropic",
            "input_cost_per_token": 2e-06,
            "output_cost_per_token": 1e-05,
        },
    }
    table, _ = generate_pricing.extract(registry)
    assert table["claude-tiered"]["in_200k"] == 6.0
    assert table["claude-tiered"]["out_200k"] == 22.5
    assert "in_200k" not in table["claude-flat"]
    assert "out_200k" not in table["claude-flat"]


def _write_registry(path: Path, registry: dict) -> None:
    path.write_text(json.dumps(registry))


def _minimal_full_registry() -> dict:
    """A registry with all four FAMILY_REPRESENTATIVE models priced, so the
    hard-fail tests can remove exactly one and isolate the failure."""
    reg = {}
    for fam, model_id in generate_pricing.FAMILY_REPRESENTATIVE.items():
        reg[model_id] = {
            "litellm_provider": "anthropic",
            "input_cost_per_token": 1e-06,
            "output_cost_per_token": 5e-06,
        }
    return reg


def test_generator_hard_fails_when_family_representative_missing(tmp_path: Path) -> None:
    registry = _minimal_full_registry()
    del registry["claude-opus-5"]  # remove the opus family representative
    snapshot = tmp_path / "snapshot.json"
    overrides = tmp_path / "overrides.json"
    out = tmp_path / "pricing_generated.py"
    _write_registry(snapshot, registry)
    overrides.write_text("[]")

    result = subprocess.run(
        [sys.executable, str(CLAUDE_SPEND_DIR / "generate_pricing.py"), str(snapshot), str(overrides), str(out)],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "opus" in result.stderr
    assert not out.exists()


def test_generator_hard_fails_when_representative_has_zero_input_cost(tmp_path: Path) -> None:
    registry = _minimal_full_registry()
    registry["claude-haiku-4-5"]["input_cost_per_token"] = 0.0
    snapshot = tmp_path / "snapshot.json"
    overrides = tmp_path / "overrides.json"
    out = tmp_path / "pricing_generated.py"
    _write_registry(snapshot, registry)
    overrides.write_text("[]")

    result = subprocess.run(
        [sys.executable, str(CLAUDE_SPEND_DIR / "generate_pricing.py"), str(snapshot), str(overrides), str(out)],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "haiku" in result.stderr
    assert not out.exists()


def test_generator_output_matches_committed_pricing_generated_byte_identical(tmp_path: Path) -> None:
    """Drift check: regenerating from the committed snapshot+overrides must
    reproduce the committed pricing_generated.py exactly. If this fails,
    someone hand-edited the generated file or forgot to regenerate it."""
    out = tmp_path / "pricing_generated.py"
    result = subprocess.run(
        [
            sys.executable,
            str(CLAUDE_SPEND_DIR / "generate_pricing.py"),
            str(CLAUDE_SPEND_DIR / "litellm_snapshot.json"),
            str(CLAUDE_SPEND_DIR / "pricing_overrides.json"),
            str(out),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    committed = (CLAUDE_SPEND_DIR / "pricing_generated.py").read_text()
    regenerated = out.read_text()
    assert regenerated == committed


# ---------------------------------------------------------------------------
# spend.py pricing lookup
# ---------------------------------------------------------------------------

USAGE = {
    "input_tokens": 1000,
    "output_tokens": 500,
    "cache_read_input_tokens": 0,
    "cache_creation_input_tokens": 0,
}


def test_opus_4_1_vs_opus_5_are_era_correct_not_flattened() -> None:
    cost_4_1, source_4_1 = spend.compute_cost("claude-opus-4-1-20250805", USAGE, "2025-09-01T00:00:00Z")
    cost_5, source_5 = spend.compute_cost("claude-opus-5", USAGE, "2026-06-01T00:00:00Z")
    assert source_4_1 == "exact"
    assert source_5 == "exact"
    # 4.1: $15/$75 -> (1000*15 + 500*75)/1e6 = 0.0525
    assert cost_4_1 == pytest.approx(0.0525)
    # 5: $5/$25 -> (1000*5 + 500*25)/1e6 = 0.0175
    assert cost_5 == pytest.approx(0.0175)
    assert cost_4_1 > cost_5  # 4.1-era transcripts must not be undercounted at 5-era rates


def test_sonnet_5_dated_override_precedence_pre_and_post_flip() -> None:
    pre_flip_cost, pre_source = spend.compute_cost("claude-sonnet-5", USAGE, "2026-08-15T12:00:00Z")
    post_flip_cost, post_source = spend.compute_cost("claude-sonnet-5", USAGE, "2026-09-15T12:00:00Z")
    assert pre_source == "dated"
    assert post_source == "dated"
    # pre: $2/$10 -> (1000*2 + 500*10)/1e6 = 0.007
    assert pre_flip_cost == pytest.approx(0.007)
    # post: $3/$15 -> (1000*3 + 500*15)/1e6 = 0.0105
    assert post_flip_cost == pytest.approx(0.0105)


def test_sonnet_4_5_long_context_uses_above_200k_tier_rates() -> None:
    # in=3.0/out=15.0 standard; in_200k=6.0/out_200k=22.5 above 200k total context.
    big_usage = {
        "input_tokens": 250_000,
        "output_tokens": 1000,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
    }
    small_usage = {**big_usage, "input_tokens": 100_000}
    big_cost, big_source = spend.compute_cost("claude-sonnet-4-5", big_usage, "2026-06-01T00:00:00Z")
    small_cost, small_source = spend.compute_cost("claude-sonnet-4-5", small_usage, "2026-06-01T00:00:00Z")
    assert big_source == "exact"
    assert small_source == "exact"
    assert big_cost == pytest.approx((250_000 * 6.0 + 1000 * 22.5) / 1_000_000)
    assert small_cost == pytest.approx((100_000 * 3.0 + 1000 * 15.0) / 1_000_000)


def test_fable_long_context_gets_no_surcharge() -> None:
    big_usage = {
        "input_tokens": 250_000,
        "output_tokens": 1000,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
    }
    small_usage = {**big_usage, "input_tokens": 50_000}
    big_cost, _ = spend.compute_cost("claude-fable-5", big_usage, "2026-06-01T00:00:00Z")
    small_cost, _ = spend.compute_cost("claude-fable-5", small_usage, "2026-06-01T00:00:00Z")
    # same per-input-token rate ($10/Mtok) regardless of crossing 200k
    per_token_big = (big_cost - 1000 * 50.0 / 1_000_000) / 250_000
    per_token_small = (small_cost - 1000 * 50.0 / 1_000_000) / 50_000
    assert per_token_big == pytest.approx(10.0 / 1_000_000)
    assert per_token_small == pytest.approx(10.0 / 1_000_000)
    assert per_token_big == per_token_small


@pytest.mark.parametrize("alias", ["sonnet", "opus[1m]"])
def test_alias_strings_hit_family_fallback(alias: str) -> None:
    cost, source = spend.compute_cost(alias, USAGE, "2026-06-01T00:00:00Z")
    assert source == "family"
    assert cost > 0


def test_unknown_model_is_counted_unpriced_not_silently_zero() -> None:
    cost, source = spend.compute_cost("gpt-x", USAGE, "2026-06-01T00:00:00Z")
    assert cost == 0.0  # we genuinely don't know the rate
    assert source == "unpriced"  # ...but the caller is told, not left to assume $0 is correct


def test_session_stats_tracks_unpriced_messages_by_model_string(tmp_path: Path) -> None:
    """The 'not silent' half of the unknown-model contract: SessionStats
    must record which unknown model strings appeared and how often,
    rather than dropping the message with no trace."""
    jsonl_path = tmp_path / "session.jsonl"
    records = [
        {
            "sessionId": "s1",
            "timestamp": "2026-06-01T00:00:00Z",
            "message": {"role": "assistant", "model": "gpt-x", "id": "msg_1", "usage": USAGE},
        },
        {
            "sessionId": "s1",
            "timestamp": "2026-06-01T00:01:00Z",
            "message": {"role": "assistant", "model": "sonnet", "id": "msg_2", "usage": USAGE},
        },
    ]
    jsonl_path.write_text("\n".join(json.dumps(r) for r in records) + "\n")

    stats = spend.SessionStats(jsonl_path)
    stats.process()

    assert stats.unpriced_by_model == {"gpt-x": 1}
    assert stats.fallback_by_model == {"sonnet": 1}
    assert stats.total_cost > 0  # the "sonnet" alias message was priced via fallback
