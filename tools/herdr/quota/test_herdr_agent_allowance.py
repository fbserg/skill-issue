import copy
import unittest
from datetime import datetime, timezone

from herdr_agent_allowance import render

NOW = datetime(2026, 9, 10, tzinfo=timezone.utc).timestamp()
ENTRY = {
    "provider": "codex",
    "updatedAt": "2026-09-10T00:00:00Z",
    "secondary": {
        "windowMinutes": 10080,
        "usedPercent": 65,
        "resetsAt": "2026-09-13T12:00:00Z",
    },
}


class AllowanceTests(unittest.TestCase):
    def test_ahead_means_over_even_budget(self):
        self.assertIn("7d 35% left · ↑15", render(ENTRY, NOW))

    def test_behind_means_spare_budget(self):
        e = copy.deepcopy(ENTRY)
        e["secondary"]["usedPercent"] = 35
        self.assertIn("7d 65% left · ↓15", render(e, NOW))

    def test_on_pace(self):
        e = copy.deepcopy(ENTRY)
        e["secondary"]["usedPercent"] = 50
        self.assertIn("on pace", render(e, NOW))

    def test_weekly_in_primary_is_not_assumed_five_hours(self):
        e = copy.deepcopy(ENTRY)
        e["primary"] = e.pop("secondary")
        self.assertIn("↑15", render(e, NOW))

    def test_missing_weekly_not_invented_from_session(self):
        e = copy.deepcopy(ENTRY)
        e["secondary"]["windowMinutes"] = 300
        self.assertEqual("Codex weekly quota unavailable", render(e, NOW))

    def test_stale_data_omits_pace_and_reset(self):
        result = render(ENTRY, NOW + 600)
        self.assertIn("stale 10m", result)
        self.assertNotIn("↑", result)
        self.assertNotIn("↻", result)

    def test_claude_throttled_snapshot_labels_age_and_retains_pace(self):
        e = copy.deepcopy(ENTRY)
        e["provider"] = "claude"
        result = render(e, NOW + 600)
        self.assertIn("cached 10m", result)
        self.assertIn("↑", result)
        self.assertNotIn("stale", result)

    def test_claude_overdue_refresh_omits_pace(self):
        e = copy.deepcopy(ENTRY)
        e["provider"] = "claude"
        result = render(e, NOW + 17 * 60)
        self.assertIn("stale 17m", result)
        self.assertNotIn("↑", result)

    def test_expired_window_never_claims_refilled(self):
        result = render(ENTRY, NOW + 4 * 86400)
        self.assertIn("awaiting refresh", result)
        self.assertNotIn("%", result)

    def test_compact_pace_without_reset_date(self):
        self.assertEqual("Codex 7d 35% left · ↑15", render(ENTRY, NOW))

    def test_unknown_reset_does_not_invent_pace(self):
        e = copy.deepcopy(ENTRY)
        del e["secondary"]["resetsAt"]
        self.assertIn("reset unknown", render(e, NOW))

    def test_corrupt_date_fails_loudly(self):
        e = copy.deepcopy(ENTRY)
        e["updatedAt"] = "broken"
        with self.assertRaises(ValueError):
            render(e, NOW)


if __name__ == "__main__":
    unittest.main()
