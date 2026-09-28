import json
from datetime import datetime, timedelta
from typing import List
from bounty_tracker import BountyTracker
from config import GITHUB_API_URL, SCAN_INTERVAL_HOURS

class BountyScanner:
    def __init__(self):
        self.tracker = BountyTracker()
        self.last_scan_time = None

    def scan_for_new_bounties(self) -> List[str]:
        if self.last_scan_time and (datetime.now() - self.last_scan_time) < timedelta(hours=SCAN_INTERVAL_HOURS):
            return []

        print(f"Scanning for new bounties at {datetime.now()}")
        new_bounties = []

        # Example bounty URLs (replace with dynamic fetching from config)
        bounty_urls = [
            "https://github.com/BasedHardware/omi/issues/18911",
            "https://github.com/tenstorrent/tt-tools-common/issues/76",
            "https://github.com/Inkh95/t3n-trusted-approval-agent/issues/26"
        ]

        for url in bounty_urls:
            opportunity = self.tracker.parse_github_issue(url)
            if opportunity and opportunity.is_valid():
                self.tracker.add_opportunity(opportunity)
                new_bounties.append(url)

        self.last_scan_time = datetime.now()
        self.tracker.save_to_file()
        return new_bounties

    def load_existing_bounties(self):
        try:
            with open('bounties.json', 'r') as f:
                data = json.load(f)
                for item in data:
                    opportunity = BountyOpportunity(**item)
                    self.tracker.add_opportunity(opportunity)
        except FileNotFoundError:
            pass