import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import scout_bounties as scout


NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)


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
            "Please report security bugs. We do not offer a bug bounty program or cash rewards.",
            "Please report security bugs. I can't offer any cash prize, but I can send swag.",
            "A platform for discovering paid contribution opportunities and browsing bounty issues.",
            "Nominations are closed and the winners announced. Winners receive a cash prize of $1000.",
            "SPAM: Congratulations, you have been awarded a £2000 cash prize. Call us now.",
            "A partially paid contribution changes the accounting state. Fix this API test.",
        ]
        for index, text in enumerate(cases):
            with self.subTest(index=index):
                self.assertIsNone(
                    scout.analyze_candidate(
                        "Project documentation",
                        "example/repo",
                        f"https://github.com/example/repo/blob/main/{index}.md",
                        "Repository Markdown",
                        text,
                        now=NOW,
                    )
                )

    def test_keeps_actionable_bounty_when_amount_is_unknown(self):
        candidate = scout.analyze_candidate(
            "Parser bug bounty",
            "example/parser",
            "https://github.com/example/parser/blob/main/BOUNTY.md",
            "Repository Markdown",
            "Find and fix the parser bug, then submit a Pull Request to claim the bounty.",
            now=NOW,
        )
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate["reward"], "金额待确认")

    def test_generic_readme_needs_concrete_cash_evidence(self):
        candidate = scout.analyze_candidate(
            "example/resources — README.md",
            "example/resources",
            "https://github.com/example/resources/blob/main/README.md",
            "Repository Markdown",
            "Browse bug bounty resources and submit fixes to the listed projects.",
            now=NOW,
        )
        self.assertIsNone(candidate)

    def test_large_competition_prize_is_not_a_micro_bounty(self):
        candidate = scout.analyze_candidate(
            "example/contest — CHALLENGE.md",
            "example/contest",
            "https://github.com/example/contest/blob/main/CHALLENGE.md",
            "Repository Markdown",
            "Cash prize: $100,000. Build a full product and submit it to the competition.",
            now=NOW,
        )
        self.assertIsNone(candidate)

    def test_reward_amount_ignores_unrelated_usage_prices(self):
        candidate = scout.analyze_candidate(
            "[AGENT-TASK] Implement pricing",
            "example/pricing",
            "https://github.com/example/pricing/issues/1",
            "GitHub Issue",
            "Calls cost $0.01 each.\n\n## Reward\n$15 USD paid in USDC after merge.\n\nImplement one pricing function.",
            now=NOW,
        )
        self.assertEqual(candidate["reward"], "$15 USD")

    def test_rejects_jobs_large_events_and_expired_deadlines(self):
        cases = [
            "Paid challenge with a $500 salary range. We are hiring for a full-time role.",
            "Hackathon prize pool: $10,000. Build a product during this multi-day competition.",
            "Small bug bounty: $50. Submit a PR. Deadline: 2025-12-31.",
        ]
        for index, text in enumerate(cases):
            with self.subTest(index=index):
                self.assertIsNone(
                    scout.analyze_candidate(
                        "Paid engineering opportunity",
                        "example/repo",
                        f"https://github.com/example/repo/{index}",
                        "Repository Markdown",
                        text,
                        now=NOW,
                    )
                )


class TriageAndStateTests(unittest.TestCase):
    def test_issue_safeguards(self):
        base = {
            "comments": 2,
            "labels": [],
            "repository_url": "https://api.github.com/repos/owner/repo",
        }
        self.assertTrue(scout.is_clean_issue(base))
        self.assertFalse(scout.is_clean_issue({**base, "assignees": [{"login": "taken"}]}))
        self.assertFalse(scout.is_clean_issue({**base, "comments": 26}))
        self.assertFalse(scout.is_clean_issue({**base, "pull_request": {}}))
        self.assertFalse(scout.is_clean_issue({**base, "labels": [{"name": "bounty-alert"}]}))
        self.assertFalse(scout.is_clean_issue({**base, "labels": [{"name": "bounty-large"}]}))
        self.assertFalse(scout.is_clean_issue({**base, "labels": [{"name": "radar"}]}))
        self.assertFalse(scout.is_clean_issue(base, "owner/repo"))

    def test_issue_requires_an_actual_reward_offer(self):
        genuine = {
            "title": "[BOUNTY] Fix the parser edge case",
            "body": "Implement the fix and submit a PR.",
            "labels": [],
        }
        discussed_only = {
            "title": "Add bounty adapter integration",
            "body": "Implement a state machine that can create hypothetical USDC bounties.",
            "labels": [],
        }
        paused = {
            "title": "[PAUSED · EXTERNAL_UNFUNDED] $100 bounty",
            "body": "This issue is not funded.",
            "labels": [{"name": "bounty"}],
        }
        submitted_claim = {
            "title": "Update project profile",
            "body": "I am submitting an edit. The project has paid $65,000 in bounties.",
            "labels": [],
        }
        self.assertTrue(scout.has_issue_reward_offer(genuine))
        self.assertFalse(scout.has_issue_reward_offer(discussed_only))
        self.assertFalse(scout.has_issue_reward_offer(paused))
        self.assertFalse(scout.has_issue_reward_offer(submitted_claim))

    def test_extracts_xlm_and_grantfox_payment(self):
        candidate = scout.analyze_candidate(
            "[BOUNTY] Small parser fix",
            "example/parser",
            "https://github.com/example/parser/issues/1",
            "GitHub Issue",
            "Bounty: 100 XLM. Fix one parser edge case. Reward: 100 XLM via GrantFox after merge.",
            now=NOW,
        )
        self.assertEqual(candidate["reward"], "100 XLM")
        self.assertEqual(candidate["payment_method"], "XLM、GrantFox")

    def test_expired_day_first_deadline_is_rejected(self):
        candidate = scout.analyze_candidate(
            "Engineering Challenge",
            "example/challenge",
            "https://github.com/example/challenge/blob/main/CHALLENGE.md",
            "Repository Markdown",
            "Cash prize: ₹10,000. Submit a GitHub Issue. Submission deadline: 31 August 2026.",
            now=NOW,
        )
        self.assertIsNone(candidate)

    def test_candidate_markdown_path(self):
        self.assertTrue(scout.candidate_markdown_path(".github/CONTRIBUTING.md"))
        self.assertTrue(scout.candidate_markdown_path("events/mini-challenge.mdx"))
        self.assertFalse(scout.candidate_markdown_path("src/challenge.py"))

    def test_state_save_preserves_existing_order_and_appends(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            state = Path(temp_dir) / "seen.json"
            state.write_text(json.dumps(["https://b", "https://a"]), encoding="utf-8")
            scout.save_seen_bounties({"https://a", "https://b", "https://c"}, str(state))
            self.assertEqual(json.loads(state.read_text(encoding="utf-8")), ["https://b", "https://a", "https://c"])

    def test_deduplication_keeps_higher_score(self):
        low = {"url": "https://same", "score": 2, "updated_at": None}
        high = {"url": "https://same", "score": 8, "updated_at": None}
        other = {"url": "https://other", "score": 5, "updated_at": None}
        ranked = scout.deduplicate_and_rank([low, other, high])
        self.assertEqual(ranked, [high, other])

    def test_duplicate_mirrors_and_original_url(self):
        body = "原 URL | https://github.com/original/project/issues/66"
        self.assertEqual(scout.extract_original_issue_url(body), "https://github.com/original/project/issues/66")

        first = {
            "url": "https://github.com/mirror/repo/issues/1",
            "project": "mirror/repo",
            "title": "[Reward] Tiny task #2",
            "score": 6,
            "updated_at": "2026-09-01T00:00:00Z",
        }
        duplicate = {
            **first,
            "url": "https://github.com/mirror/repo/issues/2",
            "title": "[Reward] Tiny task #2",
            "score": 7,
        }
        self.assertEqual(scout.deduplicate_and_rank([first, duplicate]), [duplicate])


class FormattingTests(unittest.TestCase):
    def test_notification_contains_required_fields_and_obeys_limit(self):
        candidate = {
            "title": "Tiny parser fix",
            "project": "example/parser",
            "url": "https://github.com/example/parser/issues/1",
            "source": "GitHub Issue",
            "reward": "$50",
            "task": "Fix one parser edge case",
            "deadline": "待确认",
            "submission": "Pull Request",
            "payment_method": "待确认",
            "agent_fit": "是",
            "effort": "推测：数小时",
        }
        message = scout.format_plain_notification([candidate] * 10, "2026-09-01 00:00 UTC", limit=700)
        self.assertLessEqual(len(message), 700)
        self.assertIn("Payment: 待确认", message)
        self.assertIn("Coding Agent: 是", message)
        self.assertIn("…and", message)


if __name__ == "__main__":
    unittest.main()
