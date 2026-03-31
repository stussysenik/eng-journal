from __future__ import annotations

import unittest

from journal.pricing import calculate_claude_cost, estimate_codex_cost


class PricingTests(unittest.TestCase):
    def test_claude_opus_45_uses_updated_rate_card(self) -> None:
        cost = calculate_claude_cost(
            "claude-opus-4-5-20251101",
            input_tokens=1_000_000,
            output_tokens=1_000_000,
            cache_read_tokens=1_000_000,
            cache_write_tokens=1_000_000,
        )
        self.assertAlmostEqual(cost["actual"], 36.75, places=4)
        self.assertAlmostEqual(cost["without_cache"], 41.25, places=4)
        self.assertAlmostEqual(cost["cache_savings"], 4.5, places=4)

    def test_codex_estimate_returns_monotonic_range(self) -> None:
        estimate = estimate_codex_cost(2_000_000, "gpt-5.4")
        self.assertLessEqual(estimate["low"], estimate["mid"])
        self.assertLessEqual(estimate["mid"], estimate["high"])


if __name__ == "__main__":
    unittest.main()

