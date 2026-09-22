import pytest
from scout_bounties import is_bounty_issue

def test_bounty_detection_in_title():
    issue = {"title": "Implement new feature", "body": "This is a bounty for the task."}
    assert is_bounty_issue(issue) is True

def test_bounty_detection_in_body():
    issue = {"title": "Feature request", "body": "We offer a cash prize for this."}
    assert is_bounty_issue(issue) is True

def test_non_bounty_issue():
    issue = {"title": "Bug fix", "body": "Just a regular issue."}
    assert is_bounty_issue(issue) is False

def test_chinese_keyword_detection():
    issue = {"title": "新功能", "body": "金额待确认，奖励待发放。"}
    assert is_bounty_issue(issue) is True
