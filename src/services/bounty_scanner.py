import json
from datetime import datetime
from typing import Dict, List, Optional

from src.bounties.base import Bounty


class BountyScanner:
    """Scans and validates new bounty opportunities."""

    def __init__(self, bounty_dir: str = "src/bounties"):
        self.bounty_dir = bounty_dir

    def scan_new_bounties(self) -> List[Dict]:
        """Detect and validate new bounty opportunities."""
        bounty_files = []
        for filename in self._list_bounty_files():
            bounty_data = self._load_bounty_data(filename)
            if self._validate_bounty(bounty_data):
                bounty_files.append(bounty_data)
        return bounty_files

    def _list_bounty_files(self) -> List[str]:
        """List all bounty JSON files in the bounty directory."""
        import os
        return [f for f in os.listdir(self.bounty_dir) if f.endswith('.json')]

    def _load_bounty_data(self, filename: str) -> Dict:
        """Load bounty data from JSON file."""
        with open(f"{self.bounty_dir}/{filename}", 'r') as f:
            return json.load(f)

    def _validate_bounty(self, bounty_data: Dict) -> bool:
        """Validate bounty data structure and requirements."""
        required_fields = [
            "id", "project", "source", "title", "description", 
            "reward", "submission_method", "coding_agent_fit"
        ]
        
        for field in required_fields:
            if field not in bounty_data:
                return False

        if not isinstance(bounty_data["reward"], dict) or "amount" not in bounty_data["reward"]:
            return False

        return True

    def get_high_priority_bounties(self, threshold: int = 1000) -> List[Dict]:
        """Filter bounties with rewards above a specified threshold."""
        all_bounties = self.scan_new_bounties()
        return [
            bounty for bounty in all_bounties
            if isinstance(bounty["reward"]["amount"], (int, float)) and 
            bounty["reward"]["amount"] >= threshold
        ]