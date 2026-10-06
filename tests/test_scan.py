import unittest
from datetime import datetime
from unittest.mock import patch, MagicMock

from models import BountyOpportunity, BountyScanResult
from scan import parse_bounty_body


class TestParseBountyBody(unittest.TestCase):
    def test_parse_single_opportunity(self):
        body = """
#### 1. [Bounty Alert: 10 New Opportunities]
- **Project:** owner/repo
- **Task:** Do some work
- **Reward:** $100
- **Coding Agent fit:** 是
- **Estimated effort:** 数小时到 1 天
- **Related open PRs:** 0
- **Competition:** 未发现明显竞争
- **Original Issue comments:** 0
"""
        result = parse_bounty_body(body)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["reward"], "$100")
        self.assertTrue(result[0]["coding_agent_fit"])
        self.assertEqual(result[0]["related_open_prs"], 0)

    def test_parse_multiple_opportunities(self):
        body = """
#### 1. [First]
- **Reward:** $50
- **Project:** a/b

#### 2. [Second]
- **Reward:** $75
- **Project:** c/d
"""
        result = parse_bounty_body(body)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["reward"], "$50")
        self.assertEqual(result[1]["reward"], "$75")

    def test_parse_no_opportunities(self):
        body = "Just some plain text with no opportunities."
        result = parse_bounty_body(body)
        self.assertEqual(len(result), 0)


class TestBountyScanResult(unittest.TestCase):
    def test_empty_result(self):
        result = BountyScanResult(scan_time=datetime.utcnow())
        self.assertEqual(len(result.opportunities), 0)


if __name__ == "__main__":
    unittest.main()
