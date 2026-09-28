import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

@dataclass
class BountyOpportunity:
    project: str
    source: str
    reward: float
    currency: str
    task: str
    deadline: Optional[datetime] = None
    submission: str = "Pull Request"
    payment_method: List[str] = None
    effort_estimate: Optional[str] = None
    competition: bool = False

class BountyTracker:
    def __init__(self):
        self.patterns = {
            'reward': r'\$(\d+)\s*(?:USD|USDC)?|金额待确认',
            'deadline': r'待确认|(\d{4}-\d{2}-\d{2})',
            'payment': r'(PayPal|USDC|USDT|Stablecoin)'
        }

    def parse_issue(self, issue_text: str) -> Optional[BountyOpportunity]:
        reward_match = re.search(self.patterns['reward'], issue_text)
        reward = float(reward_match.group(1)) if reward_match else None

        deadline_match = re.search(self.patterns['deadline'], issue_text)
        deadline = datetime.strptime(deadline_match.group(1), '%Y-%m-%d') if deadline_match and deadline_match.group(1) != '待确认' else None

        payment_methods = re.findall(self.patterns['payment'], issue_text)

        return BountyOpportunity(
            project="BasedHardware/omi" if "BasedHardware" in issue_text else "SPLURT-Station/S.P.L.U.R.T-tg",
            source="GitHub Issue",
            reward=reward,
            currency="USD" if reward else "待确认",
            task=re.search(r'\[\w+\]\s*(.*)', issue_text).group(1).strip(),
            deadline=deadline,
            payment_method=payment_methods if payment_methods else ["待确认"]
        )

class BountyScanner:
    def __init__(self, tracker: BountyTracker):
        self.tracker = tracker

    def scan(self, issues: List[str]) -> List[BountyOpportunity]:
        return [self.tracker.parse_issue(issue) for issue in issues if self._is_bounty(issue)]

    def _is_bounty(self, text: str) -> bool:
        return "bounty" in text.lower() or "reward" in text.lower() or "\$" in text