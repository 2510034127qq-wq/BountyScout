import re
from dataclasses import dataclass
from typing import Optional
import urllib.request
import json
from datetime import datetime, timezone


@dataclass
class BountyScanResult:
    title: str
    project: str
    source: str
    reward: str
    task: str
    deadline: str
    submission: str
    payment_method: str
    coding_agent_fit: str
    estimated_effort: str
    related_open_prs: int
    competition: str
    original_issue_comments: int
    last_updated: str


def fetch_github_issue(repo: str, issue_number: int) -> dict:
    url = f"https://api.github.com/repos/{repo}/issues/{issue_number}"
    req = urllib.request.Request(url, headers={"User-Agent": "BountyScout/1.0"})
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_issue_comments(repo: str, issue_number: int) -> list:
    url = f"https://api.github.com/repos/{repo}/issues/{issue_number}/comments"
    req = urllib.request.Request(url, headers={"User-Agent": "BountyScout/1.0"})
    with urllib.request.urlopen(req) as response:
        raw = json.loads(response.read().decode("utf-8"))
        return raw if isinstance(raw, list) else []


def parse_bounty_section(text: str) -> Optional[dict]:
    """Extract bounty-related metadata from issue body or comments."""
    reward_match = re.search(r"(?:Reward|Recompensa|\breward\b)[:\s]+([^\n]+)", text, re.IGNORECASE)
    deadline_match = re.search(r"(?:Deadline|Prazo|deadline)[:\s]+([^\n]+)", text, re.IGNORECASE)
    payment_match = re.search(r"(?:Payment method|Método de pagamento|payment)[:\s]+([^\n]+)", text, re.IGNORECASE)
    task_match = re.search(r"(?:Task|Tarefa|task)[:\s]+([^\n]+)", text, re.IGNORECASE)

    return {
        "reward": reward_match.group(1).strip() if reward_match else "待确认",
        "deadline": deadline_match.group(1).strip() if deadline_match else "待确认",
        "payment_method": payment_match.group(1).strip() if payment_match else "待确认",
        "task": task_match.group(1).strip() if task_match else "",
    }


def assess_coding_agent_fit(task: str, reward: str) -> str:
    if reward == "待确认" or not task.strip():
        return "待确认"
    keywords = ["build", "implement", "fix", "add", "create", "write"]
    if any(kw in task.lower() for kw in keywords):
        return "可能适合（需人工确认交付范围）"
    return "待确认"


def estimate_effort(task: str) -> str:
    if not task.strip():
        return "待确认"
    low = ["small", "quick", "minor", "trivial"]
    high = ["large", "complex", "rewrite", "refactor", "full"]
    task_lower = task.lower()
    if any(w in task_lower for w in high):
        return "推测：数天到数周"
    if any(w in task_lower for w in low):
        return "推测：数分钟到数小时"
    return "推测：数小时到 1 天（需人工确认范围）"


def scan_repository(repo: str, max_issues: int = 30) -> list[BountyScanResult]:
    now_utc = datetime.now(timezone.utc)
    scan_time_str = now_utc.strftime("%Y-%m-%d %H:%M UTC")

    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/issues?state=all&per_page={max_issues}",
        headers={"User-Agent": "BountyScout/1.0"},
    )
    with urllib.request.urlopen(req) as response:
        issues = json.loads(response.read().decode("utf-8"))

    results = []
    for issue in issues:
        issue_text = issue.get("body") or ""
        comments = fetch_issue_comments(repo, issue["number"])
        for comment in comments:
            issue_text += "\n" + (comment.get("body") or "")

        bounty_meta = parse_bounty_section(issue_text)
        coding_fit = assess_coding_agent_fit(bounty_meta["task"], bounty_meta["reward"])
        effort = estimate_effort(bounty_meta["task"])

        pr_req = urllib.request.Request(
            f"https://api.github.com/repos/{repo}/pulls?state=open&head={repo.split('/')[0]}:&per_page=100",
            headers={"User-Agent": "BountyScout/1.0"},
        )
        try:
            with urllib.request.urlopen(pr_req) as pr_resp:
                related_prs = len(json.loads(pr_resp.read().decode("utf-8")))
        except Exception:
            related_prs = 0

        result = BountyScanResult(
            title=issue["title"],
            project=repo,
            source="GitHub Issue",
            reward=bounty_meta["reward"],
            task=bounty_meta["task"],
            deadline=bounty_meta["deadline"],
            submission="待确认",
            payment_method=bounty_meta["payment_method"],
            coding_agent_fit=coding_fit,
            estimated_effort=effort,
            related_open_prs=related_prs,
            competition="未发现明显竞争",
            original_issue_comments=len(comments),
            last_updated=issue["updated_at"],
        )
        results.append(result)

    return results


def format_report(results: list[BountyScanResult], scan_time: str) -> str:
    lines = [f"### Active Micro Bounty Scan Results\n", f"**Scan Time:** {scan_time}\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"\n#### {i}. **{r.title}**\n")
        lines.append(f"- **Project:** [{r.project}](https://github.com/{r.project})\n")
        lines.append(f"- **Source:** {r.source}\n")
        lines.append(f"- **Reward:** {r.reward}\n")
        lines.append(f"- **Task:** {r.task}\n")
        lines.append(f"- **Deadline:** {r.deadline}\n")
        lines.append(f"- **Submission:** {r.submission}\n")
        lines.append(f"- **Payment method:** {r.payment_method}\n")
        lines.append(f"- **Coding Agent fit:** {r.coding_agent_fit}\n")
        lines.append(f"- **Estimated effort:** {r.estimated_effort}\n")
        lines.append(f"- **Related open PRs:** {r.related_open_prs}\n")
        lines.append(f"- **Competition:** {r.competition}\n")
        lines.append(f"- **Original Issue comments:** {r.original_issue_comments}\n")
        lines.append(f"- **Last updated:** {r.last_updated}\n")
    lines.append(
        "\n> Payment methods are reported only when explicitly mentioned by the source; "
        "待确认 means manual verification is required.\n"
    )
    return "".join(lines)
