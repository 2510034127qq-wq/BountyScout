from typing import List
from .tracker import BountyOpportunity, BountyTracker

class GitHubBountyScanner:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.tracker = BountyTracker()

    def fetch_recent_bounties(self, days: int = 7) -> List[BountyOpportunity]:
        # Mock implementation - replace with actual GitHub API calls
        mock_issues = [
            "[[Bounty proposal] feat(python-cli): action items -> Asana (CSV) export recipe ($25 proposed)]",  # Issue 1
            "[[Bounty proposal] feat(python-cli): conversations -> Podcast RSS 2.0 export recipe ($25 proposed)]",  # Issue 2
            "[[BOUNTY] Suggestion #1244]",  # Issue 3
            "[bounty-watch 2026-09-28: 0 new, 0 resumed, 1 watchlist changes]"  # Issue 4
        ]
        return self.tracker.scan(mock_issues)

    def validate_reward(self, bounty: BountyOpportunity) -> bool:
        return bounty.reward is not None and bounty.reward > 0