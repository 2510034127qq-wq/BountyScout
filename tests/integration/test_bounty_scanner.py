from src.bounty.scanner import GitHubBountyScanner
from src.bounty.tracker import BountyOpportunity

def test_scan_recent_bounties():
    scanner = GitHubBountyScanner(api_key="test_key")
    bounties = scanner.fetch_recent_bounties(days=1)
    assert len(bounties) == 4
    assert all(isinstance(b, BountyOpportunity) for b in bounties)

def test_reward_validation():
    scanner = GitHubBountyScanner(api_key="test_key")
    bounties = scanner.fetch_recent_bounties(days=1)
    valid_bounties = [b for b in bounties if scanner.validate_reward(b)]
    assert len(valid_bounties) == 2  # Only issues 1 and 2 have explicit rewards