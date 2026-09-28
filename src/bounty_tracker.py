import json
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import requests
from config import GITHUB_TOKEN, MIN_REWARD_THRESHOLD

@dataclass
class BountyOpportunity:
    project: str
    issue_url: str
    reward: Optional[float] = None
    deadline: Optional[datetime] = None
    task_description: str = ""
    effort_estimate: str = ""
    submission_method: str = ""
    payment_method: str = ""
    agent_fit: bool = False
    competition: bool = False

    def is_valid(self) -> bool:
        return (self.reward is not None and
                self.reward >= MIN_REWARD_THRESHOLD and
                self.agent_fit)

class BountyTracker:
    def __init__(self):
        self.opportunities: List[BountyOpportunity] = []

    def parse_github_issue(self, issue_url: str) -> Optional[BountyOpportunity]:
        try:
            headers = {'Authorization': f'token {GITHUB_TOKEN}'}
            response = requests.get(f"{issue_url}/comments", headers=headers)
            response.raise_for_status()

            comments = response.json()
            if not comments:
                return None

            bounty_data = self._extract_bounty_data(comments)
            if not bounty_data:
                return None

            return BountyOpportunity(**bounty_data)

        except Exception as e:
            print(f"Error parsing issue {issue_url}: {e}")
            return None

    def _extract_bounty_data(self, comments: List[Dict]) -> Optional[Dict]:
        for comment in comments:
            body = comment.get('body', '').lower()
            if 'reward' in body or 'bounty' in body:
                reward = self._extract_reward(body)
                deadline = self._extract_deadline(body)
                agent_fit = 'coding agent fit' in body or 'ai coding agent' in body
                return {
                    'project': self._extract_project(body),
                    'issue_url': comment['url'],
                    'reward': reward,
                    'deadline': deadline,
                    'task_description': self._extract_task_description(body),
                    'effort_estimate': self._extract_effort_estimate(body),
                    'submission_method': self._extract_submission_method(body),
                    'payment_method': self._extract_payment_method(body),
                    'agent_fit': agent_fit,
                    'competition': 'competition' in body or 'open prs' in body
                }
        return None

    def _extract_reward(self, text: str) -> Optional[float]:
        match = re.search(r'(\$|\$|\$\s*[0-9]+\s*[0-9]*)', text)
        if match:
            reward_str = match.group(1).replace('$', '').strip()
            try:
                return float(reward_str)
            except ValueError:
                return None
        return None

    def _extract_deadline(self, text: str) -> Optional[datetime]:
        deadline_match = re.search(r'deadline:\s*([^\
]+)', text, re.IGNORECASE)
        if deadline_match:
            try:
                return datetime.fromisoformat(deadline_match.group(1).strip())
            except ValueError:
                pass
        return None

    def _extract_project(self, text: str) -> str:
        project_match = re.search(r'\[([^\]]+)\]\([^)]+\)', text)
        if project_match:
            return project_match.group(1)
        return "Unknown Project"

    def _extract_task_description(self, text: str) -> str:
        task_match = re.search(r'task:\s*(.*?)(?=\
\
|\$|\
|$)', text, re.DOTALL)
        return task_match.group(1).strip() if task_match else ""

    def _extract_effort_estimate(self, text: str) -> str:
        effort_match = re.search(r'estimated effort:\s*(.*?)(?=\
\
|\$|\
|$)', text, re.DOTALL)
        return effort_match.group(1).strip() if effort_match else ""

    def _extract_submission_method(self, text: str) -> str:
        submission_match = re.search(r'submission:\s*(.*?)(?=\
\
|\$|\
|$)', text, re.DOTALL)
        return submission_match.group(1).strip() if submission_match else "GitHub Issue"

    def _extract_payment_method(self, text: str) -> str:
        payment_match = re.search(r'payment method:\s*(.*?)(?=\
\
|\$|\
|$)', text, re.DOTALL)
        return payment_match.group(1).strip() if payment_match else "Unknown"

    def add_opportunity(self, opportunity: BountyOpportunity):
        if opportunity.is_valid():
            self.opportunities.append(opportunity)

    def get_valid_opportunities(self) -> List[BountyOpportunity]:
        return [op for op in self.opportunities if op.is_valid()]

    def save_to_file(self, filename: str = 'bounties.json'):
        with open(filename, 'w') as f:
            json.dump([op.__dict__ for op in self.opportunities], f, default=str, indent=2)