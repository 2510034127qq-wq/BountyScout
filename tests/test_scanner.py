import unittest
from src.scanner import parse_bounty_section, assess_coding_agent_fit, estimate_effort, format_report, BountyScanResult


class TestParseBountySection(unittest.TestCase):
    def test_parses_reward(self):
        text = "Reward: $50 PayPal"
        result = parse_bounty_section(text)
        self.assertEqual(result["reward"], "$50 PayPal")

    def test_parses_task(self):
        text = "Task: Implement dark mode"
        result = parse_bounty_section(text)
        self.assertEqual(result["task"], "Implement dark mode")

    def test_defaults_when_missing(self):
        text = "Just a regular issue"
        result = parse_bounty_section(text)
        self.assertEqual(result["reward"], "待确认")
        self.assertEqual(result["deadline"], "待确认")
        self.assertEqual(result["payment_method"], "待确认")
        self.assertEqual(result["task"], "")


class TestAssessCodingAgentFit(unittest.TestCase):
    def test_pending_reward(self):
        self.assertEqual(assess_coding_agent_fit("Build something", "待确认"), "待确认")

    def test_empty_task(self):
        self.assertEqual(assess_coding_agent_fit("", "$50"), "待确认")

    def test_actionable_task(self):
        self.assertEqual(
            assess_coding_agent_fit("Implement a new feature", "$50"),
            "可能适合（需人工确认交付范围）",
        )


class TestEstimateEffort(unittest.TestCase):
    def test_complex_task(self):
        self.assertEqual(estimate_effort("Rewrite the entire backend"), "推测：数天到数周")

    def test_small_task(self):
        self.assertEqual(estimate_effort("Fix typo in README"), "推测：数分钟到数小时")

    def test_ambiguous_task(self):
        self.assertEqual(estimate_effort("Build orders feature"), "推测：数小时到 1 天（需人工确认范围）")

    def test_empty_task(self):
        self.assertEqual(estimate_effort(""), "待确认")


class TestFormatReport(unittest.TestCase):
    def test_formats_single_result(self):
        results = [
            BountyScanResult(
                title="Test Issue",
                project="user/repo",
                source="GitHub Issue",
                reward="$50",
                task="Fix bug",
                deadline="2026-10-14",
                submission="GitHub Issue",
                payment_method="PayPal",
                coding_agent_fit="可能适合（需人工确认交付范围）",
                estimated_effort="推测：数小时到 1 天",
                related_open_prs=0,
                competition="未发现明显竞争",
                original_issue_comments=0,
                last_updated="2026-10-07T14:00:00Z",
            )
        ]
        report = format_report(results, "2026-10-07 16:00 UTC")
        self.assertIn("Test Issue", report)
        self.assertIn("$50", report)
        self.assertIn("PayPal", report)
        self.assertIn("待确认 means manual verification", report)


if __name__ == "__main__":
    unittest.main()
