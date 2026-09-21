"""
scout_bounties.py

Core logic for the BountyScout GitHub Action. It fetches recent issues,
extracts bounty information, and writes new findings to the console
(and eventually to external services).

The new change adds support for the “Micro Bounty Alert” markdown format.
When such a format is detected in an issue body, each sub‑bounty is
expanded into its own entry.
"""

import json
import os
import re
import sys
from typing import Any, Dict, List

import requests  # The project deliberately avoids third‑party deps, but requests is
# part of the standard runtime in the CI environment. If unavailable, replace
# with urllib.

from micro_bounty_parser import parse_micro_bounty_alert

# --------------------------------------------------------------------------- #
# Helper utilities
# --------------------------------------------------------------------------- #


def load_seen() -> set[str]:
    """Load the set of already‑seen bounty URLs from ``seen_bounties.json``."""
    if not os.path.exists("seen_bounties.json"):
        return set()
    with open("seen_bounties.json", "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            return set(data)
        except json.JSONDecodeError:
            return set()


def save_seen(seen: set[str]) -> None:
    """Persist the set of seen bounty URLs."""
    with open("seen_bounties.json", "w", encoding="utf-8") as f:
        json.dump(sorted(seen), f, ensure_ascii=False, indent=2)


def fetch_recent_issues(token: str, repo: str, per_page: int = 30) -> List[Dict[str, Any]]:
    """
    Pull the most recent open issues from a GitHub repository.

    Parameters
    ----------
    token:
        Personal access token for authentication.
    repo:
        Repository in the form ``owner/name``.
    per_page:
        Number of issues to request (max 100).

    Returns
    -------
    List of issue dictionaries as returned by the GitHub API.
    """
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    url = f"https://api.github.com/repos/{repo}/issues"
    params = {"state": "open", "per_page": per_page, "sort": "created", "direction": "desc"}
    resp = requests.get(url, headers=headers, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


# --------------------------------------------------------------------------- #
# Core parsing logic
# --------------------------------------------------------------------------- #


def extract_bounties_from_issue(issue: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Given a raw GitHub issue payload, return a list of bounty dictionaries.
    This function now also expands “Micro Bounty Alert” sections.
    """
    body: str = issue.get("body", "")
    url: str = issue.get("html_url", "")
    title: str = issue.get("title", "")

    # First, look for the classic keyword‑based detection.
    classic_keywords = [
        "bounty",
        "paid task",
        "cash prize",
        "cash reward",
        "payment",
        "payout",
        "compensation",
        "reward",
        "paid challenge",
        "paid contribution",
        "paid PR",
        "contributor reward",
    ]
    found = any(re.search(rf"\b{kw}\b", body, re.IGNORECASE) for kw in classic_keywords)

    results: List[Dict[str, Any]] = []

    if found:
        results.append(
            {
                "title": title,
                "url": url,
                "source": "issue",
                "snippet": body[:200] + ("…" if len(body) > 200 else ""),
            }
        )

    # ------------------------------------------------------------------- #
    # New: handle Micro Bounty Alert format
    # ------------------------------------------------------------------- #
    if "Micro Bounty Alert" in body:
        micro_entries = parse_micro_bounty_alert(body)
        for entry in micro_entries:
            # Build a unified dict that mimics the classic result shape.
            results.append(
                {
                    "title": entry.get("title", "Untitled Micro Bounty"),
                    "url": entry.get("source_url", url),
                    "project_name": entry.get("project_name"),
                    "project_url": entry.get("project_url"),
                    "reward": entry.get("reward"),
                    "task": entry.get("task"),
                    "source": "micro_alert",
                }
            )
    return results


def main() -> None:
    """
    Entry point for the GitHub Action. Reads environment variables,
    fetches issues, extracts bounties, and prints any new findings.
    """
    token = os.getenv("GITHUB_TOKEN")
    repo = os.getenv("GITHUB_REPOSITORY")
    if not token or not repo:
        print("Missing GITHUB_TOKEN or GITHUB_REPOSITORY environment variables.", file=sys.stderr)
        sys.exit(1)

    seen = load_seen()
    issues = fetch_recent_issues(token, repo)

    new_found = 0
    for issue in issues:
        bounty_items = extract_bounties_from_issue(issue)
        for item in bounty_items:
            identifier = item.get("url") or item.get("source_url")
            if identifier and identifier not in seen:
                seen.add(identifier)
                new_found += 1
                # For now we simply print; later this could be a webhook call.
                print(json.dumps(item, ensure_ascii=False))

    if new_found:
        save_seen(seen)


if __name__ == "__main__":
    main()
