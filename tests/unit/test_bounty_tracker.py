import pytest
from datetime import datetime
from src.bounty.tracker import BountyTracker, BountyOpportunity

@pytest.fixture
def tracker():
    return BountyTracker()

def test_parse_bounty_issue(tracker):
    issue_text = "[[Bounty proposal] feat(python-cli): action items -> Asana (CSV) export recipe ($25 proposed)]"
    bounty = tracker.parse_issue(issue_text)
    assert bounty.project == "BasedHardware/omi"
    assert bounty.reward == 25.0
    assert bounty.currency == "USD"
    assert bounty.task == "feat(python-cli): action items -> Asana (CSV) export recipe ($25 proposed)"

def test_parse_issue_without_reward(tracker):
    issue_text = "[[BOUNTY] Suggestion #1244]"
    bounty = tracker.parse_issue(issue_text)
    assert bounty.reward is None
    assert bounty.currency == "待确认"

def test_parse_deadline(tracker):
    issue_text = "Deadline: 2026-10-01"
    bounty = tracker.parse_issue(issue_text)
    assert bounty.deadline == datetime.strptime("2026-10-01", "%Y-%m-%d")