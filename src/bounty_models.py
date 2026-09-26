from dataclasses import dataclass
from datetime import datetime
from typing import Optional

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
                self.agent_fit and
                self.deadline is not None and
                self.deadline > datetime.now())