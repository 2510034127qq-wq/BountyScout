#!/usr/bin/env python3
"""
BountyScout - GitHub micro bounty scanner.

Scans GitHub issues for bounty opportunities and generates reports.
"""

import json
import sys
import argparse
from datetime import datetime
from pathlib import Path
from typing import Optional

from models import BountyClaim, BountyOpportunity, BountyScanResult


REPO_OWNER = "2510034127qq-wq"
REPO_NAME = "BountyScout"
BASE_URL = "https://api.github.com/repos"


def fetch_issue(repo: str, issue_number: int) -> dict:
    """Fetch a GitHub issue by number."""
    import urllib.request
    url = f"{BASE_URL}/{repo}/issues/{issue_number}"
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("User-Agent", "BountyScout/1.0")
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode())


def fetch_issue_comments(repo: str, issue_number: int) -> list[dict]:
    """Fetch comments for a GitHub issue."""
    import urllib.request
    url = f"{BASE_URL}/{repo}/issues/{issue_number}/comments"
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("User-Agent", "BountyScout/1.0")
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode())


def parse_bounty_body(body: str) -> list[dict]:
    """Parse bounty opportunities from issue body markdown."""
    opportunities = []
    current = {}
    lines = body.splitlines()

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("####"):
            if current.get("title"):
                opportunities.append(current)
            current = {"source": "markdown"}
            current["title"] = stripped.lstrip("#").strip()
        elif stripped.startswith("- **Task:**"):
            current["task"] = stripped.replace("- **Task:**", "").strip()
        elif stripped.startswith("- **Reward:**"):
            current["reward"] = stripped.replace("- **Reward:**", "").strip()
        elif stripped.startswith("- **Project:**"):
            current["project"] = stripped.replace("- **Project:**", "").strip()
        elif stripped.startswith("- **Coding Agent fit:**"):
            fit = stripped.replace("- **Coding Agent fit:**", "").strip()
            current["coding_agent_fit"] = "sim" in fit.lower() or "yes" in fit.lower() or fit == "是"
        elif stripped.startswith("- **Estimated effort:**"):
            current["estimated_effort"] = stripped.replace("- **Estimated effort:**", "").strip()
        elif stripped.startswith("- **Related open PRs:**"):
            prs = stripped.replace("- **Related open PRs:**", "").strip()
            current["related_open_prs"] = int(prs) if prs.isdigit() else 0
        elif stripped.startswith("- **Competition:**"):
            current["competition"] = stripped.replace("- **Competition:**", "").strip()
        elif stripped.startswith("- **Original Issue comments:**"):
            comments = stripped.replace("- **Original Issue comments:**", "").strip()
            current["original_issue_comments"] = int(comments) if comments.isdigit() else 0

    if current.get("title"):
        opportunities.append(current)

    return opportunities


def fetch_github_issue(repo: str, issue_number: int) -> dict:
    """Fetch a GitHub issue using the API."""
    import urllib.request
    url = f"https://api.github.com/repos/{repo}/issues/{issue_number}"
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("User-Agent", "BountyScout/1.0")
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode())


def run_scan(source_repo: str, source_issue: int, output_dir: str = "output") -> BountyScanResult:
    """Run a full bounty scan and return results."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    print(f"Fetching issue #{source_issue} from {source_repo}...")
    issue = fetch_github_issue(source_repo, source_issue)
    body = issue.get("body", "")
    scan_time = datetime.utcnow()

    opportunities_data = parse_bounty_body(body)
    opportunities = []

    for op in opportunities_data:
        bounty = BountyOpportunity(
            title=op.get("title", "Unknown"),
            url="",
            project=op.get("project", "Unknown"),
            source="GitHub Issue",
            reward=op.get("reward", "TBD"),
            task=op.get("task", ""),
            deadline=op.get("deadline", "TBD"),
            submission=op.get("submission", "TBD"),
            payment_method=op.get("payment_method", "TBD"),
            coding_agent_fit=op.get("coding_agent_fit", False),
            estimated_effort=op.get("estimated_effort", "TBD"),
            related_open_prs=op.get("related_open_prs", 0),
            competition=op.get("competition", "None detected"),
            original_issue_comments=op.get("original_issue_comments", 0),
            last_updated=scan_time,
        )
        opportunities.append(bounty)

    result = BountyScanResult(scan_time=scan_time, opportunities=opportunities)

    # Save report
    report_path = Path(output_dir) / f"scan_{scan_time.strftime('%Y%m%d_%H%M%S')}.json"
    report_data = {
        "scan_time": scan_time.isoformat(),
        "opportunities": [
            {
                "title": o.title,
                "url": o.url,
                "project": o.project,
                "source": o.source,
                "reward": o.reward,
                "task": o.task,
                "deadline": o.deadline,
                "coding_agent_fit": o.coding_agent_fit,
                "estimated_effort": o.estimated_effort,
                "related_open_prs": o.related_open_prs,
                "competition": o.competition,
            }
            for o in opportunities
        ],
    }
    with open(report_path, "w") as f:
        json.dump(report_data, f, indent=2)

    print(f"Scan complete. Found {len(opportunities)} opportunities.")
    print(f"Report saved to {report_path}")
    return result


def main():
    parser = argparse.ArgumentParser(description="BountyScout - Scan GitHub for micro bounties")
    parser.add_argument("--repo", required=True, help="Source repo in owner/name format")
    parser.add_argument("--issue", type=int, required=True, help="Issue number to scan")
    parser.add_argument("--output", default="output", help="Output directory for reports")
    args = parser.parse_args()

    result = run_scan(args.repo, args.issue, args.output)

    print(f"\nFound {len(result.opportunities)} opportunities:")
    for i, op in enumerate(result.opportunities, 1):
        fit_tag = "AGENT_OK" if op.coding_agent_fit else "AGENT_TODO"
        print(f"  {i}. [{fit_tag}] {op.title} - {op.reward}")


if __name__ == "__main__":
    main()
