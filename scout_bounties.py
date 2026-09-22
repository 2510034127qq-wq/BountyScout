import os
import json
import requests
from typing import List, Dict

# GitHub authentication (optional)
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}

# Keywords to search for in title or body (English + Chinese)
KEYWORDS = [
    "bounty", "paid task", "cash prize", "cash reward", "payment",
    "payout", "compensation", "reward", "paid challenge",
    "paid contribution", "paid PR", "contributor reward",
    # Chinese keywords
    "金额", "待确认", "付费", "奖励", "报酬"
]

def fetch_issues(query: str, per_page: int = 50) -> List[Dict]:
    """
    Fetch issues from GitHub search API using the provided query.
    """
    url = "https://api.github.com/search/issues"
    params = {"q": query, "per_page": per_page}
    resp = requests.get(url, headers=HEADERS, params=params)
    resp.raise_for_status()
    return resp.json().get("items", [])

def is_bounty_issue(issue: Dict) -> bool:
    """
    Determine if an issue qualifies as a bounty by checking title and body
    for any of the predefined keywords.
    """
    title = issue.get("title", "").lower()
    body = issue.get("body", "").lower() or ""
    content = f"{title}\n{body}"
    return any(keyword.lower() in content for keyword in KEYWORDS)

def scan_bounties() -> List[Dict]:
    """
    Scan GitHub for potential bounty issues across all repositories.
    Returns a list of issue dicts that match bounty criteria.
    """
    # Base query: open issues
    query = "is:issue is:open"
    # Append keyword filters for title and body
    keyword_filters = " ".join([f"{kw} in:title,body" for kw in KEYWORDS])
    full_query = f"{query} {keyword_filters}"
    issues = fetch_issues(full_query)
    # Filter issues that actually contain the keyword (case-insensitive)
    bounty_issues = [issue for issue in issues if is_bounty_issue(issue)]
    return bounty_issues
