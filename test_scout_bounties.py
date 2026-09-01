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

    def test_keeps_high_reward_when_task_scope_is_small(self):
        candidate = scout.analyze_candidate(
            "example/contest — CHALLENGE.md",
            "example/contest",
            "https://github.com/example/contest/blob/main/CHALLENGE.md",
            "Repository Markdown",
            "Cash reward: $100,000. Fix one parser edge case and submit a pull request.",
            now=NOW,
        )
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate["reward"], "$100,000")

    def test_large_scope_is_rejected_independently_of_reward(self):
        candidate = scout.analyze_candidate(
            "example/contest — CHALLENGE.md",
            "example/contest",
            "https://github.com/example/contest/blob/main/CHALLENGE.md",
            "Repository Markdown",
            "Cash prize: $100. This is a multi-month architecture redesign; submit the completed product.",
            now=NOW,
        )
        self.assertIsNone(candidate)

    def test_reward_amount_ignores_unrelated_usage_prices(self):
        candidate = scout.analyze_candidate(
            "[AGENT-TASK] Implement pricing",
            "example/pricing",
            "https://github.com/example/pricing/issues/1",
            "GitHub Issue",
            "Calls cost $0.01 each.\n\n## Reward\n$15 USD paid via PayPal or USDC after merge.\n\nImplement one pricing function.",
            now=NOW,
        )
        self.assertEqual(candidate["reward"], "$15 USD")

    def test_non_cash_only_rewards_are_filtered(self):
        rewards = (
            "Reward: a $50 gift card after the PR is merged.",
            "Reward: 500 points after the PR is merged.",
            "Reward: a completion certificate after the PR is merged.",
            "Reward: a physical prize after the PR is merged.",
            "Reward: a gift card after the PR is merged. The product price is $100.",
        )
        for index, reward in enumerate(rewards):
            with self.subTest(reward=reward):
                text = f"{reward}\nFix one parser edge case and submit a pull request."
                self.assertTrue(scout.non_cash_reward_types(text))
                self.assertIsNone(
                    scout.analyze_candidate(
                        "[BOUNTY] Small parser fix",
                        "example/parser",
                        f"https://github.com/example/parser/issues/{index}",
                        "GitHub Issue",
                        text,
                        now=NOW,
                    )
                )

    def test_explicit_cash_alternative_keeps_mixed_reward(self):
        text = "Reward: a $50 gift card or $50 paid via PayPal after merge. Fix the parser and submit a pull request."
        candidate = scout.analyze_candidate(
            "[BOUNTY] Small parser fix",
            "example/parser",
            "https://github.com/example/parser/issues/90",
            "GitHub Issue",
            text,
            now=NOW,
        )
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate["reward"], "$50")
        self.assertEqual(candidate["payment_method"], "PayPal")

    def test_explicit_cash_amount_keeps_mixed_non_cash_extras(self):
        rewards = (
            "Reward: $100 + a gift card after merge.",
            "Reward: $50 cash + swag after merge.",
        )
        for index, reward in enumerate(rewards):
            with self.subTest(reward=reward):
                candidate = scout.analyze_candidate(
                    "[BOUNTY] Small parser fix",
                    "example/parser",
                    f"https://github.com/example/parser/issues/{100 + index}",
                    "GitHub Issue",
                    f"{reward} Fix the parser and submit a pull request.",
                    now=NOW,
                )
                self.assertIsNotNone(candidate)

    def test_repository_markdown_filename_is_not_a_hard_filter(self):
        for filename in ("GOVERNANCE.md", "PROGRAM.md", "REWARDS.md"):
            with self.subTest(filename=filename):
                candidate = scout.analyze_candidate(
                    f"example/project — {filename}",
                    "example/project",
                    f"https://github.com/example/project/blob/main/{filename}",
                    "Repository Markdown",
                    "Compensation: USD 125. Contributors are paid after merge via PayPal. "
                    "Implement one policy check and submit a pull request.",
                    now=NOW,
                )
                self.assertIsNotNone(candidate)

    def test_completion_payment_phrases_link_contribution_to_reward(self):
        offers = (
            "Payout: $100. Contributors receive the payout after merge.",
            "Compensation: USD 80, paid upon acceptance.",
            "You are paid after merge: $75.",
            "Payment after accepted PR: $90.",
        )
        for index, offer in enumerate(offers):
            with self.subTest(offer=offer):
                text = f"{offer} Fix one parser edge case and submit a pull request."
                item = {"title": "Small parser task", "body": text, "labels": []}
                self.assertTrue(scout.has_issue_reward_offer(item))
                self.assertIsNotNone(
                    scout.analyze_candidate(
                        "Small parser task",
                        "example/parser",
                        f"https://github.com/example/parser/issues/{110 + index}",
                        "GitHub Issue",
                        text,
                        now=NOW,
                    )
                )

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
    def test_issue_search_queries_cover_common_payment_terms(self):
        expected = {
            'is:issue is:open "paid task" in:title,body sort:updated-desc',
            'is:issue is:open "cash reward" in:title,body sort:updated-desc',
            "is:issue is:open payment in:title,body sort:updated-desc",
            "is:issue is:open payout in:title,body sort:updated-desc",
            "is:issue is:open compensation in:title,body sort:updated-desc",
            "is:issue is:open reward in:title,body sort:updated-desc",
        }
        self.assertTrue(expected.issubset(set(scout.ISSUE_SEARCH_QUERIES)))

    def test_issue_safeguards(self):
        base = {
            "comments": 2,
            "labels": [],
            "repository_url": "https://api.github.com/repos/owner/repo",
        }
        self.assertTrue(scout.is_clean_issue(base))
        self.assertFalse(scout.is_clean_issue({**base, "state": "closed"}))
        self.assertTrue(scout.is_clean_issue({**base, "assignees": [{"login": "taken"}]}))
        self.assertTrue(scout.is_clean_issue({**base, "comments": 26}))
        self.assertTrue(scout.is_clean_issue({**base, "labels": [{"name": "claimed"}]}))
        self.assertTrue(scout.is_clean_issue({**base, "labels": [{"name": "in progress"}]}))
        self.assertFalse(scout.is_clean_issue({**base, "pull_request": {}}))
        self.assertFalse(scout.is_clean_issue({**base, "labels": [{"name": "bounty-alert"}]}))
        self.assertFalse(scout.is_clean_issue({**base, "labels": [{"name": "bounty-large"}]}))
        self.assertFalse(scout.is_clean_issue({**base, "labels": [{"name": "radar"}]}))
        self.assertFalse(scout.is_clean_issue(base, "owner/repo"))
        exclusive = {
            **base,
            "assignees": [{"login": "taken"}],
            "body": "Only the assigned contributor is eligible; others may not submit.",
        }
        self.assertFalse(scout.is_clean_issue(exclusive))
        self.assertEqual(scout.issue_safeguard_reason(exclusive), "assigned / claimed")
        no_new_claims = {
            **base,
            "body": "A submission is already under review. New contributors should not start parallel work.",
        }
        self.assertFalse(scout.is_clean_issue(no_new_claims))
        self.assertFalse(scout.is_clean_issue({**base, "labels": [{"name": "completed"}]}))
        self.assertFalse(scout.is_clean_issue({**base, "body": "This task has been completed."}))

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

    def test_real_game_economy_issues_are_not_bounty_offers(self):
        issues = (
            {
                "title": "fix!(lua.endpoints): cash_out fires before round-eval rows commit — rewards under-collected, sometimes $0",
                "body": (
                    "Calling cash_out as soon as the game reaches ROUND_EVAL collects less money than the game owes — "
                    "usually short exactly one blind reward ($3/$4/$5), and $0 in the worst case.\n"
                    "The dollar rows (blind reward, interest, per-joker payouts) are still being committed.\n"
                    "Suggested Fix: wait until the round-eval UI has finished creating its rows."
                ),
                "labels": [],
                "url": "https://github.com/coder/balatrobot/issues/231",
                "project": "coder/balatrobot",
            },
            {
                "title": "bug: leaderboard runs affected by two balatrobot defects — economy short-collected",
                "body": (
                    "The cash_out race collects one blind reward short ($3/$4/$5), or $0 when the payout is only the "
                    "reward row. Several dataset runs die in the shop on purchases they could have afforded.\n"
                    "Suggested Fixes: pick up the balatrobot fixes when they land."
                ),
                "labels": [],
                "url": "https://github.com/coder/balatrollm/issues/85",
                "project": "coder/balatrollm",
            },
            {
                "title": "Onboarding",
                "body": (
                    "Minecraft tutorial challenge: Sell $1,500 worth of crops. Player reaches a balance of $1,500.\n"
                    "Once all five challenges have been completed, reward player with 1 Frontier Key and $10,000."
                ),
                "labels": [],
                "url": "https://github.com/surf-sound/lifestealz/issues/10",
                "project": "surf-sound/lifestealz",
            },
        )
        for item in issues:
            with self.subTest(url=item["url"]):
                self.assertFalse(scout.has_issue_reward_offer(item))
                text = "\n".join((item["title"], item["body"]))
                self.assertIsNone(
                    scout.analyze_candidate(
                        item["title"],
                        item["project"],
                        item["url"],
                        "GitHub Issue",
                        text,
                        now=NOW,
                    )
                )

    def test_real_jd_card_reward_extracts_amount_but_is_filtered(self):
        item = {
            "title": "[Reward] HarnessClaw 体验测评（任一场景） #2",
            "body": """
            ### Task description
            提交方式：开一个 PR，把测评内容写成 markdown，合并后发放奖励。
            为了保证奖励真正发给用过 HarnessClaw 的人，PR 需要满足审核标准。

            奖励形式：京东卡（人民币 100 元等值），在 PR 合并后与作者联系发放。

            ### Reward currency
            CNY RMB

            ### Reward amount
            100

            ### Reward payer
            FenjuFu
            """,
            "labels": [{"name": "good first issue"}, {"name": "reward"}],
            "url": "https://github.com/harnessclaw/harnessclaw/issues/66",
        }
        text = "\n".join((item["title"], item["body"]))
        self.assertTrue(scout.has_issue_reward_offer(item))
        self.assertEqual(scout.extract_reward_amounts(text), ["100 RMB"])
        self.assertEqual(scout.non_cash_reward_types(text), ["京东卡"])
        self.assertIsNone(
            scout.analyze_candidate(
                item["title"],
                "harnessclaw/harnessclaw",
                item["url"],
                "GitHub Issue",
                text,
                now=NOW,
                reward_offer_confirmed=True,
            )
        )

    def test_issue_5_hall_of_fame_total_is_historical_not_current_reward(self):
        text = """
        # Hall of Fame — September 2026
        ## Top Contributors
        Leaderboard and total earned by past winners.
        ## Monthly Stats
        Total Bounty Distributed: $4770
        """
        candidate = scout.analyze_candidate(
            "🏆 Hall of Fame — September 2026",
            "zhangjiayang6835-cyber/ai-research",
            "https://github.com/zhangjiayang6835-cyber/ai-research/issues/1533",
            "GitHub Issue",
            text,
            now=NOW,
            reward_offer_confirmed=True,
        )
        self.assertIsNone(candidate)

        virtual_footer_reasons = []
        virtual_footer = scout.analyze_candidate(
            "Monthly contributor stats",
            "zhangjiayang6835-cyber/ai-research",
            "https://github.com/zhangjiayang6835-cyber/ai-research/issues/1533",
            "GitHub Issue",
            """
            Total Bounty Distributed: $4770
            虚拟代币仅供学习排名使用，不可兑换为现金或加密货币。
            """,
            now=NOW,
            reward_offer_confirmed=True,
            rejection_reasons=virtual_footer_reasons,
        )
        self.assertIsNone(virtual_footer)
        self.assertEqual(virtual_footer_reasons, ["no reward link"])

        english_virtual_reasons = []
        english_virtual = scout.analyze_candidate(
            "Contributor payout summary",
            "example/stats",
            "https://github.com/example/stats/issues/1",
            "GitHub Issue",
            "Virtual tokens for ranking only; cannot be redeemed for cash or cryptocurrency.",
            now=NOW,
            reward_offer_confirmed=True,
            rejection_reasons=english_virtual_reasons,
        )
        self.assertIsNone(english_virtual)
        self.assertEqual(english_virtual_reasons, ["no reward link"])

        current = scout.analyze_candidate(
            "[BOUNTY] Fix leaderboard sorting",
            "example/game",
            "https://github.com/example/game/issues/4",
            "GitHub Issue",
            "Current reward: $40. Fix the leaderboard sorting bug and submit a pull request.",
            now=NOW,
        )
        self.assertIsNotNone(current)

    def test_issue_5_large_grant_and_other_explicit_heavy_scopes_are_filtered(self):
        scopes = (
            "Conduct a full security audit; the engagement typically runs 3–6 weeks.",
            "Complete this multi-milestone implementation and final report.",
            "This is a large empirical reproduction across 48 portfolio setups.",
            "Take ownership of this long-running project.",
        )
        for index, scope in enumerate(scopes):
            with self.subTest(scope=scope):
                text = f"Requested bounty program budget: $90,000. {scope} Submit the deliverables."
                self.assertIsNone(
                    scout.analyze_candidate(
                        "Grant Application - Security Audit of Zaino",
                        "ZcashCommunityGrants/zcashcommunitygrants",
                        f"https://github.com/ZcashCommunityGrants/zcashcommunitygrants/issues/{407 + index}",
                        "GitHub Issue",
                        text,
                        now=NOW,
                        reward_offer_confirmed=True,
                    )
                )

    def test_issue_5_stripe_credit_pack_is_product_billing_not_payout(self):
        text = """
        Goal: implement a token/credit wallet for customer billing.
        Store stripe_payment_id on customer purchases and decrement credits for every billable tool call.
        Stripe credit packs: Starter $20, Growth $99. Add a recurring subscription tier.
        Submit the implementation after the checkout test passes.
        """
        self.assertFalse(scout.has_issue_reward_offer({"title": "BidDeed billing system", "body": text}))
        self.assertEqual(scout.extract_payment_methods(text), [])
        self.assertIsNone(
            scout.analyze_candidate(
                "BidDeed.AI: Token/credit-based billing system",
                "breverdbidder/cli-anything-biddeed",
                "https://github.com/breverdbidder/cli-anything-biddeed/issues/19677",
                "GitHub Issue",
                text,
                now=NOW,
                reward_offer_confirmed=True,
            )
        )

        real_bounty = "Bounty: $50. Fix one Stripe checkout bug; contributors are paid via Stripe after merge."
        candidate = scout.analyze_candidate(
            "[BOUNTY] Fix checkout callback",
            "example/checkout",
            "https://github.com/example/checkout/issues/1",
            "GitHub Issue",
            real_bounty,
            now=NOW,
        )
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate["payment_method"], "Stripe")

    def test_issue_6_product_payment_flows_are_not_contributor_payouts(self):
        cases = (
            (
                "Link popup PaymentSheet silently cancels",
                "Fix the PaymentSheet callback after a customer PaymentIntent destination charge. Submit a PR.",
            ),
            (
                "Platform-fee charge used live mode",
                "A test claim charged a real card $180.54 plus a $175 platform fee. Implement the fix.",
            ),
            (
                "Batch proof endpoint charges once",
                "The paid API endpoint charges $0.008 even though pricing is per proof. "
                "Fix x-payment-info and add regression tests.",
            ),
            (
                "Payment spec replay bug",
                "A paid resource can be replayed after a card charge. Correct the payment intent spec in a PR.",
            ),
        )
        for index, (title, text) in enumerate(cases):
            with self.subTest(title=title):
                item = {"title": title, "body": text, "labels": []}
                self.assertFalse(scout.has_issue_reward_offer(item))
                self.assertIsNone(
                    scout.analyze_candidate(
                        title,
                        "example/product",
                        f"https://github.com/example/product/issues/{30 + index}",
                        "GitHub Issue",
                        text,
                        now=NOW,
                        reward_offer_confirmed=True,
                    )
                )

        actual_bounty = (
            "Bounty: $80. Fix the PaymentSheet callback. "
            "Contributors are paid via Stripe after the pull request is merged."
        )
        candidate = scout.analyze_candidate(
            "[BOUNTY] Fix PaymentSheet callback",
            "example/product",
            "https://github.com/example/product/issues/40",
            "GitHub Issue",
            actual_bounty,
            now=NOW,
        )
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate["reward"], "$80")
        self.assertEqual(candidate["payment_method"], "Stripe")

    def test_issue_6_financial_facts_are_not_reward_amounts(self):
        cases = (
            (
                "UK source packages: funded early-years facts",
                "Package publisher facts: Government top-up paid £632,200,000 and market size £14 billion. "
                "Add the source package and run validation.",
            ),
            (
                "Proper DROP modeling for all plans",
                "Implement actuarial assumptions for pension benefit values of $18.98 and $64. "
                "Submit a pull request with the model checks.",
            ),
            (
                "Correct customer balance",
                "The customer balance shows $500 after payment. Fix the accounting state and add tests.",
            ),
        )
        for index, (title, text) in enumerate(cases):
            with self.subTest(title=title):
                self.assertFalse(scout.has_issue_reward_offer({"title": title, "body": text, "labels": []}))
                self.assertIsNone(
                    scout.analyze_candidate(
                        title,
                        "example/finance",
                        f"https://github.com/example/finance/issues/{50 + index}",
                        "GitHub Issue",
                        text,
                        now=NOW,
                        reward_offer_confirmed=True,
                    )
                )

    def test_paid_bounty_is_kept_but_unrelated_business_limit_is_not_reward(self):
        text = """
        Recruitly offers 75% off to agencies with less than $500,000 in annual revenue.
        Add one missing YAML record and run the repository verifier.
        This is a focused, data-only contribution under paid Frantic bounty 120.
        """
        item = {"title": "Missing record: Recruitly Startup Program", "body": text, "labels": []}
        self.assertTrue(scout.has_issue_reward_offer(item))
        candidate = scout.analyze_candidate(
            item["title"],
            "sourcey/startup-credits",
            "https://github.com/sourcey/startup-credits/issues/917",
            "GitHub Issue",
            text,
            now=NOW,
        )
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate["reward"], "金额待确认")

    def test_domain_payment_words_near_code_work_do_not_prove_a_bounty(self):
        cases = (
            "Enable product charges and payouts, then audit the $5/$10/$20 monthly prices.",
            "A VAT payment contributes the amount to paid totals. Fix the accounting code and submit a PR.",
            "Never approve payments or start paid services. Run tests before opening a pull request.",
            "The licence covers commercial advantage or monetary compensation. Post a pull request with feedback.",
            "Evaluate an external creator platform's payout semantics and reuse its reward normalizer.",
            "The demo paid tool settles a simulated payment before input validation. Fix the test.",
            "Add historical personnel compensation records and employer-paid benefit fields.",
            "Build virtual races where users earn prizes; cash fulfillment may be added later.",
        )
        for index, text in enumerate(cases):
            with self.subTest(index=index):
                item = {"title": "Ordinary engineering issue", "body": text, "labels": []}
                self.assertFalse(scout.has_issue_reward_offer(item))
                self.assertIsNone(
                    scout.analyze_candidate(
                        item["title"],
                        "example/product",
                        f"https://github.com/example/product/issues/{70 + index}",
                        "GitHub Issue",
                        text,
                        now=NOW,
                    )
                )

        genuine = "Paid task: fix one parser edge case and submit a PR to claim the $60 bounty."
        self.assertTrue(scout.has_issue_reward_offer({"title": "Parser fix", "body": genuine, "labels": []}))

    def test_archived_competition_directory_is_discovery_not_current_task(self):
        text = """
        # Programming Competitions
        | Competition | Organizer | Prize | Link |
        | Code Jam | Google | USD 100,000 | [archive](https://example.com/codejam/archive) |
        | Hash Code | Google | Cash prize | [archive](https://example.com/hashcode/archive) |
        | Kick Start | Google | Prize | [archive](https://example.com/kickstart/archive) |
        """
        self.assertTrue(scout.is_discovery_source_document(text))
        self.assertIsNone(
            scout.analyze_candidate(
                "example/repo — docs/companies/competitions.md",
                "example/repo",
                "https://github.com/example/repo/blob/main/docs/companies/competitions.md",
                "Repository Markdown",
                text,
                now=NOW,
            )
        )

    def test_generic_backing_templates_need_current_funding_evidence(self):
        templates = (
            "Everyone can add rewards. Fix the parser and submit a PR.",
            "Want to back this issue? Post a bounty on it! Fix the parser and submit a PR.",
            "Sponsor this issue or fund this issue. Fix the parser and submit a PR.",
        )
        for text in templates:
            with self.subTest(text=text):
                item = {"title": "Parser bug", "body": text, "labels": []}
                self.assertFalse(scout.has_issue_reward_offer(item))
                self.assertIsNone(
                    scout.analyze_candidate(
                        item["title"],
                        "example/parser",
                        "https://github.com/example/parser/issues/2",
                        "GitHub Issue",
                        text,
                        now=NOW,
                        reward_offer_confirmed=True,
                    )
                )

        funded = (
            "Want to back this issue? Post a bounty on it. Current reward: $75. "
            "Fix the parser and submit a pull request."
        )
        self.assertTrue(scout.has_issue_reward_offer({"title": "Parser bug", "body": funded, "labels": []}))
        self.assertIsNotNone(
            scout.analyze_candidate(
                "Parser bug",
                "example/parser",
                "https://github.com/example/parser/issues/3",
                "GitHub Issue",
                funded,
                now=NOW,
            )
        )

    def test_explicit_no_reward_or_non_task_language_is_filtered(self):
        negatives = (
            "Production payouts are not live yet. When paid work launches, contributors may earn rewards.",
            "This is a zero-bounty task with zero monetary reward. Submit a PR if interested.",
            "This is not a build ticket; it only describes a possible future bounty.",
            "This task is unfunded and has no reward yet. Implementing it is optional.",
            "The bounty bot says this issue does not have any reward yet.",
        )
        for index, text in enumerate(negatives):
            with self.subTest(text=text):
                self.assertFalse(scout.has_issue_reward_offer({"title": "Task", "body": text, "labels": []}))
                self.assertIsNone(
                    scout.analyze_candidate(
                        "Task",
                        "example/project",
                        f"https://github.com/example/project/issues/{10 + index}",
                        "GitHub Issue",
                        text,
                        now=NOW,
                        reward_offer_confirmed=True,
                    )
                )

    def test_nofx_reward_ranges_are_discovery_source_not_task_reward(self):
        text = """
        # NOFX Community
        ## Bounty Program
        ### Active Bounties
        | Category | Reward Range | Examples |
        | Small Features | $50-200 | Bug fixes, UI improvements, documentation |
        | Medium Features | $200-500 | WebSocket support, new AI models |
        ### How to Claim Bounties
        1. Find issue tagged `[BOUNTY]`
        2. Submit PR with demo
        3. Get paid after merge
        ### Current Bounty Tasks
        | [Hyperliquid Integration](bounty-hyperliquid.md) | TBD | Open |
        """
        url = "https://github.com/BigBanana-7788/nofx/blob/main/docs/community/README.md"
        self.assertTrue(scout.is_discovery_source_document(text))
        self.assertIsNone(
            scout.analyze_candidate(
                "BigBanana-7788/nofx — docs/community/README.md",
                "BigBanana-7788/nofx",
                url,
                "Repository Markdown",
                text,
                now=NOW,
            )
        )
        self.assertEqual(
            scout.extract_discovery_task_urls(text, url),
            ["https://github.com/BigBanana-7788/nofx/blob/main/docs/community/bounty-hyperliquid.md"],
        )

    def test_rejects_crypto_only_payments(self):
        assets = ("USDC", "USDT", "BTC", "sats", "Lightning", "ETH", "SOL", "XLM", "DAI", "RTC")
        for asset in assets:
            with self.subTest(asset=asset):
                candidate = scout.analyze_candidate(
                    "[BOUNTY] Small parser fix",
                    "example/parser",
                    "https://github.com/example/parser/issues/1",
                    "GitHub Issue",
                    f"Bounty: $50. Fix one parser edge case. Payout is only in {asset} after merge.",
                    now=NOW,
                )
                self.assertIsNone(candidate)

    def test_rejects_unknown_token_payout_to_on_chain_wallet(self):
        candidate = scout.analyze_candidate(
            "[BOUNTY] Small parser fix",
            "example/parser",
            "https://github.com/example/parser/issues/1",
            "GitHub Issue",
            "Bounty: $50. Fix one parser edge case. Payout is sent only to your on-chain wallet address.",
            now=NOW,
        )
        self.assertIsNone(candidate)

    def test_rtc_technical_term_does_not_imply_crypto_payment(self):
        candidate = scout.analyze_candidate(
            "[BOUNTY] Fix the RTC connection",
            "example/realtime",
            "https://github.com/example/realtime/issues/1",
            "GitHub Issue",
            "Bounty: $50. Fix the RTC connection bug and submit a pull request. Payment method is pending.",
            now=NOW,
        )
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate["payment_method"], "待确认")

    def test_keeps_mixed_fiat_and_crypto_payment(self):
        candidate = scout.analyze_candidate(
            "[BOUNTY] Small parser fix",
            "example/parser",
            "https://github.com/example/parser/issues/1",
            "GitHub Issue",
            "Bounty: $50. Fix one parser edge case. Payout via PayPal or USDC after merge.",
            now=NOW,
        )
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate["payment_method"], "PayPal、USDC")

    def test_keeps_fiat_option_alongside_on_chain_wallet(self):
        candidate = scout.analyze_candidate(
            "[BOUNTY] Small parser fix",
            "example/parser",
            "https://github.com/example/parser/issues/1",
            "GitHub Issue",
            "Bounty: $50. Fix one parser edge case. Payout via PayPal or an on-chain wallet after merge.",
            now=NOW,
        )
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate["payment_method"], "PayPal、链上钱包")

    def test_negated_fiat_option_does_not_bypass_crypto_filter(self):
        candidate = scout.analyze_candidate(
            "[BOUNTY] Small parser fix",
            "example/parser",
            "https://github.com/example/parser/issues/1",
            "GitHub Issue",
            "Bounty: $50. Fix one parser edge case. Payout is USDC only; PayPal is not available.",
            now=NOW,
        )
        self.assertIsNone(candidate)

    def test_verified_grantfox_rule_filters_crypto_only_payment(self):
        rule = scout.verified_platform_payment_rule(
            text="GrantFox reward consideration applies after review.",
            labels=["GrantFox OSS", "Maybe Rewarded"],
        )
        self.assertEqual(rule["name"], "GrantFox")
        candidate = scout.analyze_candidate(
            "[BOUNTY] Small parser fix",
            "example/parser",
            "https://github.com/example/parser/issues/1",
            "GitHub Issue",
            "Bounty: $50. Fix one parser edge case. GrantFox reward consideration applies after review.",
            now=NOW,
            platform_payment_rule=rule,
        )
        self.assertIsNone(candidate)

    def test_unverified_platform_without_payout_channel_stays_unknown(self):
        text = "Bounty: $50. Fix one parser edge case. ExampleFox reward consideration applies after review."
        rule = scout.verified_platform_payment_rule(text=text, labels=["ExampleFox OSS"])
        self.assertIsNone(rule)
        candidate = scout.analyze_candidate(
            "[BOUNTY] Small parser fix",
            "example/parser",
            "https://github.com/example/parser/issues/1",
            "GitHub Issue",
            text,
            now=NOW,
            platform_payment_rule=rule,
        )
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate["payment_method"], "待确认")

    def test_explicit_fiat_option_overrides_platform_crypto_only_rule(self):
        rule = scout.verified_platform_payment_rule(labels=["GrantFox OSS"])
        candidate = scout.analyze_candidate(
            "[BOUNTY] Small parser fix",
            "example/parser",
            "https://github.com/example/parser/issues/1",
            "GitHub Issue",
            "Bounty: $50. Fix one parser edge case. Payout via PayPal or USDC.",
            now=NOW,
            platform_payment_rule=rule,
        )
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate["payment_method"], "PayPal、USDC")
        self.assertEqual(candidate["payment_rule_source"], rule["evidence_url"])

    def test_verified_platform_can_be_identified_from_official_host(self):
        rule = scout.verified_platform_payment_rule(url="https://contribute.grantfox.xyz/issues/123")
        self.assertEqual(rule["name"], "GrantFox")

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
        self.assertTrue(scout.candidate_markdown_path("docs/GOVERNANCE.md"))
        self.assertTrue(scout.candidate_markdown_path("PROGRAM.md"))
        self.assertTrue(scout.candidate_markdown_path("REWARDS.md"))
        self.assertFalse(scout.candidate_markdown_path("src/challenge.py"))

    def test_state_save_preserves_existing_order_and_appends(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            state = Path(temp_dir) / "seen.json"
            state.write_text(json.dumps(["https://b", "https://a"]), encoding="utf-8")
            scout.save_seen_bounties({"https://a", "https://b", "https://c"}, str(state))
            self.assertEqual(json.loads(state.read_text(encoding="utf-8")), ["https://b", "https://a", "https://c"])

    def test_issue_search_depth_is_expanded(self):
        self.assertEqual(scout.ISSUE_RESULTS_PER_QUERY, 50)

    def test_rate_limit_prefers_retry_after_header(self):
        responses = [
            api_error(
                429,
                "secondary rate limit",
                {
                    "Retry-After": "107",
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": "9999999999",
                },
            ),
            api_response({"items": []}),
        ]
        with mock.patch.object(scout.urllib.request, "urlopen", side_effect=responses) as urlopen, mock.patch.object(
            scout.time, "sleep"
        ) as sleep:
            result = scout.github_api_get("/search/code?q=reward")

        self.assertEqual(result, {"items": []})
        self.assertEqual(urlopen.call_count, 2)
        sleep.assert_called_once_with(107)

    def test_github_api_encodes_spaces_in_code_search_result_url(self):
        raw_url = (
            "https://api.github.com/repositories/263787924/contents/"
            "_cet/Higher Diploma in Social Service.md?ref=665209831ac70cada6d52510414e444ce163e5e5"
        )
        with mock.patch.object(
            scout.urllib.request,
            "urlopen",
            return_value=api_response({"content": ""}),
        ) as urlopen:
            result = scout.github_api_get(raw_url, "token")

        self.assertEqual(result, {"content": ""})
        request = urlopen.call_args.args[0]
        self.assertIn("Higher%20Diploma%20in%20Social%20Service.md", request.full_url)
        self.assertNotIn(" ", request.full_url)

    def test_rate_limit_uses_reset_epoch_when_remaining_is_zero(self):
        responses = [
            api_error(
                403,
                "API rate limit exceeded",
                {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1062"},
            ),
            api_response({"ok": True}),
        ]
        with mock.patch.object(scout.urllib.request, "urlopen", side_effect=responses), mock.patch.object(
            scout.time, "time", return_value=1000
        ), mock.patch.object(scout.time, "sleep") as sleep:
            result = scout.github_api_get("/rate-limited")

        self.assertEqual(result, {"ok": True})
        sleep.assert_called_once_with(62)

    def test_secondary_rate_limit_uses_three_exponential_retries(self):
        responses = [
            api_error(429, "You have exceeded a secondary rate limit") for _ in range(3)
        ] + [api_response({"ok": True})]
        with mock.patch.object(scout.urllib.request, "urlopen", side_effect=responses) as urlopen, mock.patch.object(
            scout.time, "sleep"
        ) as sleep:
            result = scout.github_api_get("/secondary-limit")

        self.assertEqual(result, {"ok": True})
        self.assertEqual(urlopen.call_count, 4)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [60, 120, 240])

    def test_non_rate_limit_403_is_not_retried(self):
        with mock.patch.object(
            scout.urllib.request,
            "urlopen",
            side_effect=api_error(403, "Resource not accessible by integration"),
        ) as urlopen, mock.patch.object(scout.time, "sleep") as sleep:
            result = scout.github_api_get("/forbidden")

        self.assertIsNone(result)
        self.assertEqual(urlopen.call_count, 1)
        sleep.assert_not_called()

    def test_related_prs_count_open_and_ignore_closed_unmerged(self):
        item = {
            "number": 476,
            "html_url": "https://github.com/connect-boiz/soroban-security-scanner/issues/476",
            "repository_url": "https://api.github.com/repos/connect-boiz/soroban-security-scanner",
            "timeline_url": "https://api.github.com/repos/connect-boiz/soroban-security-scanner/issues/476/timeline",
        }
        events = [
            {
                "event": "cross-referenced",
                "source": {
                    "issue": {
                        "number": 505,
                        "state": "closed",
                        "html_url": "https://github.com/connect-boiz/soroban-security-scanner/pull/505",
                        "body": "Addresses #476",
                        "pull_request": {"merged_at": None},
                    }
                },
            },
            {
                "event": "cross-referenced",
                "source": {
                    "issue": {
                        "number": 533,
                        "state": "open",
                        "html_url": "https://github.com/connect-boiz/soroban-security-scanner/pull/533",
                        "body": "Closes #476",
                        "pull_request": {"merged_at": None},
                    }
                },
            },
        ]
        with mock.patch.object(scout, "github_api_get", return_value=events):
            info = scout.fetch_related_pr_info(item, "token")

        self.assertEqual(info["open_pr_count"], 1)
        self.assertEqual(info["merged_pr_count"], 0)
        self.assertFalse(info["completed_by_merged_pr"])

    def test_merged_pr_only_completes_issue_with_explicit_closing_reference(self):
        item = {
            "number": 42,
            "html_url": "https://github.com/example/parser/issues/42",
            "repository_url": "https://api.github.com/repos/example/parser",
        }
        merged = {
            "event": "cross-referenced",
            "source": {
                "issue": {
                    "state": "closed",
                    "html_url": "https://github.com/example/parser/pull/9",
                    "body": "## Fixes #42\n\nImplements the requested parser correction.",
                    "pull_request": {"merged_at": "2026-09-01T01:00:00Z"},
                }
            },
        }
        with mock.patch.object(scout, "github_api_get", return_value=[merged]):
            info = scout.fetch_related_pr_info(item, "token")
        self.assertEqual(info["merged_pr_count"], 1)
        self.assertTrue(info["completed_by_merged_pr"])

        merged["source"]["issue"]["body"] = "Related work for #42; does not complete the task."
        with mock.patch.object(scout, "github_api_get", return_value=[merged]):
            info = scout.fetch_related_pr_info(item, "token")
        self.assertFalse(info["completed_by_merged_pr"])

    def test_open_prs_lower_rank_more_under_first_wins_rule(self):
        pr_info = {"open_pr_count": 2, "merged_pr_count": 0, "completed_by_merged_pr": False}
        normal = scout.apply_pr_competition({"score": 10}, pr_info, "Open submissions are reviewed.")
        first_wins = scout.apply_pr_competition(
            {"score": 10}, pr_info, "The first valid submission wins the bounty."
        )

        self.assertEqual(normal["open_pr_count"], 2)
        self.assertEqual(normal["score"], 8)
        self.assertEqual(first_wins["score"], 4)
        self.assertTrue(first_wins["first_wins"])

    def test_assignee_claim_and_busy_comments_are_competition_signals(self):
        item = {
            "assignees": [{"login": "working"}],
            "labels": [{"name": "claimed"}],
            "comments": 60,
        }
        candidate = scout.apply_pr_competition(
            {"score": 10},
            {"open_pr_count": 0, "merged_pr_count": 0},
            "Submissions are reviewed independently.",
            item=item,
        )

        self.assertEqual(candidate["assignee_count"], 1)
        self.assertEqual(candidate["participation_labels"], ["claimed"])
        self.assertEqual(candidate["score"], 6)
        self.assertIn("1 个 assignee", candidate["competition"])
        self.assertIn("claimed", candidate["competition"])
        self.assertIn("60 条评论", candidate["competition"])

    def test_soroban_476_is_competitive_but_filtered_by_grantfox_payment(self):
        item = {
            "number": 476,
            "html_url": "https://github.com/connect-boiz/soroban-security-scanner/issues/476",
            "repository_url": "https://api.github.com/repos/connect-boiz/soroban-security-scanner",
            "title": "Critical: bounty pool has no real token custody",
            "body": "Reward: $1,000. Implement real token custody and submit a pull request.",
            "labels": [{"name": "GrantFox OSS"}, {"name": "Maybe Rewarded"}],
        }
        open_pr = {
            "event": "cross-referenced",
            "source": {
                "issue": {
                    "number": 533,
                    "state": "open",
                    "html_url": "https://github.com/connect-boiz/soroban-security-scanner/pull/533",
                    "body": "Closes #476",
                    "pull_request": {"merged_at": None},
                }
            },
        }
        with mock.patch.object(scout, "github_api_get", return_value=[open_pr]):
            pr_info = scout.fetch_related_pr_info(item, "token")
        self.assertEqual(pr_info["open_pr_count"], 1)
        self.assertFalse(pr_info["completed_by_merged_pr"])

        text = "\n".join((item["title"], item["body"]))
        rule = scout.verified_platform_payment_rule(
            text=text,
            labels=[label["name"] for label in item["labels"]],
            url=item["html_url"],
        )
        candidate = scout.analyze_candidate(
            item["title"],
            "connect-boiz/soroban-security-scanner",
            item["html_url"],
            "GitHub Issue",
            text,
            now=NOW,
            platform_payment_rule=rule,
        )
        self.assertIsNone(candidate)

    def test_code_search_queries_are_spaced(self):
        queries = [("first", "first query"), ("second", "second query")]
        with mock.patch.object(scout, "DOCUMENT_SEARCH_QUERIES", queries), mock.patch.object(
            scout, "search_endpoint", return_value={"items": []}
        ) as search, mock.patch.object(scout.time, "sleep") as sleep:
            documents, worked = scout.fetch_code_search_documents("token")

        self.assertEqual(documents, [])
        self.assertTrue(worked)
        sleep.assert_called_once_with(scout.CODE_SEARCH_INTERVAL_SECONDS)
        self.assertEqual(search.call_count, 2)

    def test_document_scan_applies_verified_platform_payment_rule(self):
        document = {
            "title": "GrantFox bounty",
            "project": "grantfox.xyz",
            "url": "https://contribute.grantfox.xyz/issues/123",
            "text": "Cash reward: $50. Fix one parser edge case and submit a pull request.",
        }
        with mock.patch.object(scout, "fetch_readme_fallback_documents", return_value=[document]):
            self.assertEqual(scout.scan_documents(), [])

    def test_document_scan_follows_discovery_page_to_concrete_task(self):
        discovery = {
            "title": "example/project — COMMUNITY.md",
            "project": "example/project",
            "url": "https://github.com/example/project/blob/main/COMMUNITY.md",
            "text": """
            Bounty Program. Reward Range: $50-200 for bug fixes.
            How to claim bounties: find an issue tagged [BOUNTY].
            Current bounty tasks: [BOUNTY Parser fix](bounty-parser.md).
            """,
        }
        target = {
            "source": "Repository Markdown",
            "title": "example/project — bounty-parser.md",
            "project": "example/project",
            "url": "https://github.com/example/project/blob/main/bounty-parser.md",
            "text": "Bounty: $75. Fix one parser edge case and submit a pull request.",
        }
        with mock.patch.object(
            scout, "fetch_readme_fallback_documents", return_value=[discovery]
        ), mock.patch.object(scout, "fetch_discovery_target", return_value=target) as fetch_target:
            candidates = scout.scan_documents()

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["url"], target["url"])
        self.assertEqual(candidates[0]["reward"], "$75")
        self.assertEqual(candidates[0]["discovered_via"], discovery["url"])
        fetch_target.assert_called_once_with(
            "https://github.com/example/project/blob/main/bounty-parser.md", None
        )

    def test_scan_statistics_are_logged(self):
        with mock.patch.object(scout, "search_endpoint", return_value={"items": []}), mock.patch.object(
            scout, "log"
        ) as logger:
            self.assertEqual(scout.scan_issues("token"), [])

        summary = logger.call_args_list[-1].args[0]
        self.assertIn("Issue scan summary", summary)
        self.assertIn("raw=0", summary)
        self.assertIn("matched=0", summary)

    def test_diagnostic_samples_are_bounded_and_include_rejection_reason(self):
        samples = {}
        for index in range(scout.FILTER_SAMPLE_LIMIT + 3):
            scout.add_diagnostic_sample(samples, "no reward link", f"https://example.test/{index}")
        self.assertEqual(len(samples["no reward link"]), scout.FILTER_SAMPLE_LIMIT)

        reasons = []
        candidate = scout.analyze_candidate(
            "[BOUNTY] Tiny parser fix",
            "example/parser",
            "https://github.com/example/parser/issues/404",
            "GitHub Issue",
            "Reward: a gift card after merge. Fix the parser and submit a pull request.",
            now=NOW,
            rejection_reasons=reasons,
        )
        self.assertIsNone(candidate)
        self.assertEqual(reasons, ["non-cash"])

        with mock.patch.object(scout, "log") as logger:
            scout.log_diagnostic_samples("Issue", samples)
        logged = logger.call_args.args[0]
        self.assertIn("Issue triage sample [no reward link]", logged)
        self.assertIn("https://example.test/0", logged)

    def test_scan_keeps_issue_with_open_pr_and_records_competition(self):
        issue = {
            "number": 42,
            "html_url": "https://github.com/example/parser/issues/42",
            "repository_url": "https://api.github.com/repos/example/parser",
            "title": "[BOUNTY] Fix one parser edge case",
            "body": "Bounty: $50. Fix the parser and submit a Pull Request. Payout via PayPal.",
            "labels": [{"name": "bounty"}, {"name": "claimed"}],
            "assignees": [{"login": "working"}],
            "comments": 60,
            "state": "open",
        }
        open_pr = {
            "event": "cross-referenced",
            "source": {
                "issue": {
                    "state": "open",
                    "html_url": "https://github.com/example/parser/pull/7",
                    "body": "Closes #42",
                    "pull_request": {"merged_at": None},
                }
            },
        }
        with mock.patch.object(scout, "search_endpoint", return_value={"items": [issue]}), mock.patch.object(
            scout, "github_api_get", return_value=[open_pr]
        ), mock.patch.object(scout, "log") as logger:
            candidates = scout.scan_issues("token")

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["open_pr_count"], 1)
        self.assertEqual(candidates[0]["assignee_count"], 1)
        self.assertEqual(candidates[0]["participation_labels"], ["claimed"])
        self.assertEqual(candidates[0]["comments"], 60)
        self.assertIn("有竞争", candidates[0]["competition"])
        messages = "\n".join(call.args[0] for call in logger.call_args_list)
        self.assertIn("assigned / claimed (competition)", messages)
        self.assertIn("too many comments (competition)", messages)
        self.assertIn(issue["html_url"], messages)

    def test_scan_filters_issue_completed_by_merged_pr(self):
        issue = {
            "number": 42,
            "html_url": "https://github.com/example/parser/issues/42",
            "repository_url": "https://api.github.com/repos/example/parser",
            "title": "[BOUNTY] Fix one parser edge case",
            "body": "Bounty: $50. Fix the parser and submit a Pull Request. Payout via PayPal.",
            "labels": [{"name": "bounty"}],
            "assignees": [],
            "comments": 1,
            "state": "open",
        }
        merged_pr = {
            "event": "cross-referenced",
            "source": {
                "issue": {
                    "state": "closed",
                    "html_url": "https://github.com/example/parser/pull/7",
                    "body": "Closes #42",
                    "pull_request": {"merged_at": "2026-09-01T01:00:00Z"},
                }
            },
        }
        with mock.patch.object(scout, "search_endpoint", return_value={"items": [issue]}), mock.patch.object(
            scout, "github_api_get", return_value=[merged_pr]
        ):
            self.assertEqual(scout.scan_issues("token"), [])

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

    def test_radar_is_resolved_to_original_issue_metadata(self):
        radar = {
            "html_url": "https://github.com/radar/alerts/issues/9",
            "repository_url": "https://api.github.com/repos/radar/alerts",
            "title": "[radar] New bounty",
            "body": "Original Issue URL: https://github.com/source/project/issues/42",
            "labels": [{"name": "radar"}],
            "comments": 99,
        }
        original = {
            "html_url": "https://github.com/source/project/issues/42",
            "repository_url": "https://api.github.com/repos/source/project",
            "title": "[BOUNTY] Fix one parser edge case",
            "body": "Bounty: $75. Fix the parser and submit a Pull Request. Payout via PayPal.",
            "labels": [{"name": "bounty"}],
            "assignees": [],
            "comments": 3,
            "state": "open",
            "updated_at": "2026-09-01T01:00:00Z",
        }

        with mock.patch.object(scout, "search_endpoint", return_value={"items": [radar]}), mock.patch.object(
            scout, "github_api_get", return_value=original
        ):
            candidates = scout.scan_issues("token")

        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertEqual(candidate["project"], "source/project")
        self.assertEqual(candidate["url"], original["html_url"])
        self.assertEqual(candidate["comments"], 3)
        self.assertEqual(candidate["reward"], "$75")
        self.assertEqual(candidate["payment_method"], "PayPal")
        self.assertEqual(candidate["discovered_via"], radar["html_url"])

    def test_unresolved_radar_is_not_reported(self):
        radar = {
            "html_url": "https://github.com/radar/alerts/issues/10",
            "title": "[radar] Bounty alert without source link",
            "body": "A generated notification with no original task URL.",
            "labels": [{"name": "radar"}],
        }
        self.assertIsNone(scout.resolve_radar_source(radar, "token"))

    def test_crypto_only_original_behind_radar_is_filtered(self):
        radar = {
            "html_url": "https://github.com/radar/alerts/issues/12",
            "title": "[radar] Crypto bounty",
            "body": "Original Issue URL: https://github.com/source/project/issues/55",
            "labels": [{"name": "radar"}],
        }
        original = {
            "html_url": "https://github.com/source/project/issues/55",
            "repository_url": "https://api.github.com/repos/source/project",
            "title": "[BOUNTY] Fix parser",
            "body": "Bounty: $100. Fix the parser. Payout is USDC only.",
            "labels": [{"name": "bounty"}],
            "assignees": [],
            "comments": 1,
            "state": "open",
        }
        with mock.patch.object(scout, "search_endpoint", return_value={"items": [radar]}), mock.patch.object(
            scout, "github_api_get", return_value=original
        ):
            self.assertEqual(scout.scan_issues("token"), [])

    def test_radar_can_resolve_an_external_bounty_page(self):
        radar = {
            "html_url": "https://github.com/radar/alerts/issues/11",
            "title": "[radar] External challenge",
            "body": "Original Task URL: https://challenge.example/tasks/parser",
            "labels": [{"name": "radar"}],
        }
        page = """
        <html><head><title>Parser Micro Challenge</title></head><body>
        <h1>Cash prize: $80</h1>
        <p>Fix one parser edge case and submit a Pull Request.</p>
        <p>Deadline: 2026-12-31. Winners are paid via Wise.</p>
        </body></html>
        """
        with mock.patch.object(scout, "fetch_text_url", return_value=page):
            resolved = scout.resolve_radar_source(radar, "token")

        self.assertEqual(resolved["kind"], "external")
        self.assertEqual(resolved["url"], "https://challenge.example/tasks/parser")
        self.assertIn("Cash prize: $80", resolved["text"])

        with mock.patch.object(scout, "search_endpoint", return_value={"items": [radar]}), mock.patch.object(
            scout, "fetch_text_url", return_value=page
        ):
            candidates = scout.scan_issues("token")
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["source"], "External bounty page")
        self.assertEqual(candidates[0]["payment_method"], "Wise")
        self.assertEqual(candidates[0]["project"], "challenge.example")


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
            "comments": 3,
            "discovered_via": "https://github.com/radar/alerts/issues/1",
            "open_pr_count": 1,
            "competition": "有竞争：1 个相关 open PR",
        }
        message = scout.format_plain_notification([candidate] * 10, "2026-09-01 00:00 UTC", limit=700)
        self.assertLessEqual(len(message), 700)
        self.assertIn("Payment: 待确认", message)
        self.assertIn("Coding Agent: 是", message)
        self.assertIn("Original comments: 3", message)
        self.assertIn("Related open PRs: 1", message)
        self.assertIn("Discovered via:", message)
        self.assertIn("…and", message)

        issue_body = scout.format_github_issue_body([candidate], "2026-09-01 00:00 UTC")
        self.assertIn("Tiny parser fix", issue_body)
        self.assertIn("**Related open PRs:** 1", issue_body)
        self.assertNotIn("Issue scan summary", issue_body)
        self.assertNotIn("analysis_filtered=", issue_body)


class ExternalFetchSecurityTests(unittest.TestCase):
    def test_safe_public_http_url_rejects_common_ssrf_bypass_hosts(self):
        blocked = (
            "http://127.0.0.1/",
            "http://0177.0.0.1/",
            "http://2130706433/",
            "http://0x7f000001/",
            "http://127.1/",
            "http://[::1]/",
            "http://169.254.169.254/",
            "http://10.0.0.1/",
            "http://metadata.google.internal/",
            "https://localhost/",
        )
        for url in blocked:
            self.assertFalse(scout.safe_public_http_url(url), url)

        self.assertTrue(scout.safe_public_http_url("https://example.com/bounty"))

    def test_fetch_external_page_source_rejects_blocked_url(self):
        self.assertIsNone(scout.fetch_external_page_source("http://127.0.0.1/"))

    def test_restricted_fetch_rejects_redirect_to_private_target(self):
        handler = scout.SafeRedirectHandler()
        request = scout.urllib.request.Request("http://example.com/start")
        redirected = handler.redirect_request(
            request,
            None,
            302,
            "Found",
            {"Location": "http://169.254.169.254/latest/meta-data/"},
            "http://169.254.169.254/latest/meta-data/",
        )
        self.assertIsNone(redirected)

        allowed = handler.redirect_request(
            request,
            None,
            302,
            "Found",
            {"Location": "https://example.com/task"},
            "https://example.com/task",
        )
        self.assertIsNotNone(allowed)
        self.assertEqual(allowed.full_url, "https://example.com/task")

    def test_fetch_external_page_source_blocks_redirect_to_private_target(self):
        """Integration: public URL → restricted fetch → blocked private redirect → None."""

        real_build_opener = scout.urllib.request.build_opener

        class FakePublicRedirectHandler(scout.urllib.request.BaseHandler):
            handler_order = scout.urllib.request.HTTPHandler.handler_order - 1

            def http_open(self, req):
                raise scout.urllib.error.HTTPError(
                    req.full_url,
                    302,
                    "Found",
                    {"Location": "http://169.254.169.254/latest/meta-data/"},
                    io.BytesIO(b""),
                )

        def fake_build_opener(*handlers):
            if any(isinstance(handler, scout.SafeRedirectHandler) for handler in handlers):
                return real_build_opener(FakePublicRedirectHandler(), *handlers)
            return real_build_opener(*handlers)

        with mock.patch("scout_bounties.urllib.request.build_opener", side_effect=fake_build_opener):
            result = scout.fetch_external_page_source("http://example.com/bounty-task")

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
