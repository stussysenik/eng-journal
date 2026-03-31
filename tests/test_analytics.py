from __future__ import annotations

import unittest

from journal.analytics import summarize_prompt_events


class AnalyticsTests(unittest.TestCase):
    def test_prompt_summary_tracks_directive_signals(self) -> None:
        summary = summarize_prompt_events(
            [
                {"prompt_text": "Interview me till you're 95% sure of what I want and think step by step.", "prompt_length": 78},
                {"prompt_text": "Please validate whole diff and double check, then launch two agents in parallel.", "prompt_length": 79},
                {"prompt_text": "Implement the plan.", "prompt_length": 19},
            ]
        )
        signals = {item["name"]: item["count"] for item in summary["directive_signals"]}
        self.assertEqual(signals["interview_before_action"], 1)
        self.assertEqual(signals["step_by_step"], 1)
        self.assertEqual(signals["verification_first"], 1)
        self.assertEqual(signals["parallel_agents"], 1)
        self.assertEqual(signals["implement_direct"], 1)


if __name__ == "__main__":
    unittest.main()
