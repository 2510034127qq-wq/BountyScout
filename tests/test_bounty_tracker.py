"""
Unit tests for bounty_tracker.py
"""
import pytest
from bounty_tracker import BountyTracker, BountyOpportunity
from datetime import datetime

def test_parse_valid_bounty():
    tracker = BountyTracker()
    mock_issue_url = "https://github.com/test/test/issues/1"
    mock_comment = {
        'body': 'Project: [TestOrg/TestRepo](https://github.com/TestOrg/TestRepo)\
\
'
                'Reward: $50\
'
                'Deadline: 2026-10-25T23:59:59Z\
'
                'Task: Fix the bug in module X\
'
                'Estimated effort: 2 hours\
'
                'Submission: GitHub PR\
'
                'Payment method: PayPal\
'
                'Coding Agent fit: yes',
        'url': mock_issue_url
    }

    # Mock requests.get to return our test comment
    with patch('requests.get') as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = [mock_comment]

        opportunity = tracker.parse_github_issue(mock_issue_url)
        assert opportunity is not None
        assert opportunity.project == "TestOrg/TestRepo"
        assert opportunity.reward == 50.0
        assert opportunity.deadline == datetime(2026, 10, 25, 23, 59, 59)
        assert opportunity.agent_fit == True

def test_reward_extraction():
    tracker = BountyTracker()
    assert tracker._extract_reward("Reward: $50") == 50.0
    assert tracker._extract_reward("$100") == 100.0
    assert tracker._extract_reward("Reward: $0") == 0.0
    assert tracker._extract_reward("No reward") is None

def test_deadline_extraction():
    tracker = BountyTracker()
    assert tracker._extract_deadline("Deadline: 2026-10-25T23:59:59Z") is not None
    assert tracker._extract_deadline("No deadline") is None

def test_agent_fit_detection():
    tracker = BountyTracker()
    assert tracker._extract_agent_fit("Coding Agent fit: yes") == True
    assert tracker._extract_agent_fit("AI coding agent allowed") == True
    assert tracker._extract_agent_fit("No agent fit") == False