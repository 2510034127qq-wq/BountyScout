from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class BountyOpportunity:
    title: str
    url: str
    project: str
    source: str
    reward: str
    task: str
    deadline: str
    submission: str
    payment_method: str
    coding_agent_fit: bool
    estimated_effort: str
    related_open_prs: int
    competition: str
    original_issue_comments: int
    last_updated: datetime


@dataclass
class BountyScanResult:
    scan_time: datetime
    opportunities: list[BountyOpportunity] = field(default_factory=list)


@dataclass
class BountyClaim:
    bounty_id: str
    repository: str
    claimant: str
    claimed_at: datetime
    status: str  # "pending", "accepted", "completed"
