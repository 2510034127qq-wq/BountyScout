```python
import io
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import scout_bounties as scout


NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)


def api_error(code, message, headers=None):
    body = io.BytesIO(json.dumps({"message": message}).encode("utf-8"))
    return scout.urllib.error.HTTPError("https://api.github.com/test", code, message, headers or {}, body)


def api_response(payload):
    response = mock.MagicMock()
    response.__enter__.return_value.read.return_value = json.dumps(payload).encode("utf-8")
    return response


class CandidateAnalysisTests(unittest.TestCase):
    def test_extracts_micro_challenge_fields(self):
        text = """
        # Open Source Challenge

        Cash prize: $100 for each accepted report.
        This task should take under an hour: try the CLI, find a bug, and report a GitHub Issue.
        Submit the Issue URL through our Google Form at https://forms.gle/example.
        Deadline: 2026-12-31.
        Winners are paid via PayPal or USDC.
        """

        candidate = scout.analyze_candidate(
            "Open Source Challenge",
            "example/project",
            "https://github.com/example/project/blob/main/CHALLENGE.md",
            "Repository Markdown",
            text,
            now=NOW,
        )

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate["reward"], "$100")
        self.assertEqual(candidate["deadline"], "Deadline: 2026-12-31.")
        self.assertEqual(candidate["submission"], "Google Form、GitHub Issue")
        self.assertEqual(candidate["payment_method"], "PayPal、USDC")
        self.assertIn("find a bug", candidate["task"])
        self.assertTrue(candidate["agent_fit"].startswith("是"))
        self.assertIn("under an hour", candidate["effort"])

    def test_payment_is_unknown_when_not_explicitly_stated(self):
        candidate = scout.analyze_candidate(
            "Fix parser bounty",
            "example/parser",
            "https://github.com/example/parser/issues/7",
            "GitHub Issue",
            "Bounty: USD 75. Fix the parser and submit a pull request.",
            now=NOW,
        )

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate["reward"], "USD 75")
        self.assertEqual(candidate["payment_method"], "待确认")
        self.assertEqual(candidate["submission"], "Pull Request")

    def test_rejects_non_cash_reward_model_discussion(self):
        candidate = scout.analyze_candidate(
            "Reward model documentation",
            "example/ml",
            "https://github.com/example/ml/blob/main/README.md",
            "Repository Markdown",
            "The reward function controls reinforcement learning. Document the reward model API.",
            now=NOW,
        )
        self.assertIsNone(candidate)

    def test_extracts_indian_rupee_amount(self):
        candidate = scout.analyze_candidate(
            "Short engineering challenge",
            "example/challenge",
            "https://github.com/example/challenge/blob/main/BOUNTY.md",
            "Repository Markdown",
            "Cash prize: ₹10,000. Find one bug and submit a GitHub Issue. Deadline: 2026-12-31.",
            now=NOW,
        )
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate["reward"], "₹10,000")

    def test_rejects_costs_and_nonexistent_bounty_programs(self):
        cases = [
            "Engineering challenge: reduce AWS WAF cost from $5.00 by applying a custom rule.",
            "Payment processing bug: the account balance shows $500. Fix the balance display.",
            "Product price is $99. Implement the missing checkout label.",
            "Tutorial: set the demo account balance to $100 and add an assertion.",
            "Please report security bugs. We do not offer a bug bounty program or cash rewards.",
            "Please report security bugs. I can't offer any cash prize.",
        ]
        for text in cases:
            with self.subTest(text=text):
                candidate = scout.analyze_candidate(
                    "Test case",
                    "example/repo",
                    "https://github.com/example/repo/issues/1",
                    "GitHub Issue",
                    text,
                    now=NOW,
                )
                self.assertIsNone(candidate)
```
import io
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import scout_bounties as scout


NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)


def api_error(code, message, headers=None):
    body = io.BytesIO(json.dumps({"message": message}).encode("utf-8"))
    return scout.urllib.error.HTTPError("https://api.github.com/test", code, message, headers or {}, body)


def api_response(payload):
    response = mock.MagicMock()
    response.__enter__.return_value.read.return_value = json.dumps(payload).encode("utf-8")
    return response


class CandidateAnalysisTests(unittest.TestCase):
    def test_extracts_micro_challenge_fields(self):
        text = """
        # Open Source Challenge

        Cash prize: $100 for each accepted report.
        This task should take under an hour: try the CLI, find a bug, and report a GitHub Issue.
        Submit the Issue URL through our Google Form at https://forms.gle/example.
        Deadline: 2026-12-31.
        Winners are paid via PayPal or USDC.
        """

        candidate = scout.analyze_candidate(
            "Open Source Challenge",
            "example/project",
            "https://github.com/example/project/blob/main/CHALLENGE.md",
            "Repository Markdown",
            text,
            now=NOW,
        )

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate["reward"], "$100")
        self.assertEqual(candidate["deadline"], "Deadline: 2026-12-31.")
        self.assertEqual(candidate["submission"], "Google Form、GitHub Issue")
        self.assertEqual(candidate["payment_method"], "PayPal、USDC")
        self.assertIn("find a bug", candidate["task"])
        self.assertTrue(candidate["agent_fit"].startswith("是"))
        self.assertIn("under an hour", candidate["effort"])

    def test_payment_is_unknown_when_not_explicitly_stated(self):
        candidate = scout.analyze_candidate(
            "Fix parser bounty",
            "example/parser",
            "https://github.com/example/parser/issues/7",
            "GitHub Issue",
            "Bounty: USD 75. Fix the parser and submit a pull request.",
            now=NOW,
        )

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate["reward"], "USD 75")
        self.assertEqual(candidate["payment_method"], "待确认")
        self.assertEqual(candidate["submission"], "Pull Request")

    def test_rejects_non_cash_reward_model_discussion(self):
        candidate = scout.analyze_candidate(
            "Reward model documentation",
            "example/ml",
            "https://github.com/example/ml/blob/main/README.md",
            "Repository Markdown",
            "The reward function controls reinforcement learning. Document the reward model API.",
            now=NOW,
        )
        self.assertIsNone(candidate)

    def test_extracts_indian_rupee_amount(self):
        candidate = scout.analyze_candidate(
            "Short engineering challenge",
            "example/challenge",
            "https://github.com/example/challenge/blob/main/BOUNTY.md",
            "Repository Markdown",
            "Cash prize: ₹10,000. Find one bug and submit a GitHub Issue. Deadline: 2026-12-31.",
            now=NOW,
        )
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate["reward"], "₹10,000")

    def test_rejects_costs_and_nonexistent_bounty_programs(self):
        cases = [
            "Engineering challenge: reduce AWS WAF cost from $5.00 by applying a custom rule.",
            "Payment processing bug: the account balance shows $500. Fix the balance display.",
            "Product price is $99. Implement the missing checkout label.",
            "Tutorial: set the demo account balance to $100 and add an assertion.",
            "Please report security bugs. We do not offer a bug bounty program or cash rewards.",
            "Please report security bugs. I can't offer any cash prize.",
        ]
        for text in cases:
            with self.subTest(text=text):
                candidate = scout.analyze_candidate(
                    "Test case",
                    "example/repo",
                    "https://github.com/example/repo/issues/1",
                    "GitHub Issue",
                    text,
                    now=NOW,
                )
                self.assertIsNone(candidate)
