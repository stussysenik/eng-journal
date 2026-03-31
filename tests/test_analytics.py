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

    def test_prompt_summary_splits_control_and_substantive_prompts(self) -> None:
        summary = summarize_prompt_events(
            [
                {"prompt_text": "/usage", "prompt_length": 6},
                {"prompt_text": "yes", "prompt_length": 3},
                {"prompt_text": "Please verify the whole diff and then implement the fix.", "prompt_length": 57},
                {"prompt_text": "Please verify the whole diff and then implement the fix.", "prompt_length": 57},
            ]
        )
        self.assertEqual(summary["control_prompt_count"], 2)
        self.assertEqual(summary["substantive_prompt_count"], 2)
        self.assertEqual(summary["duplicate_prompt_instances"], 1)
        self.assertEqual(summary["substantive_duplicate_instances"], 1)


if __name__ == "__main__":
    unittest.main()
