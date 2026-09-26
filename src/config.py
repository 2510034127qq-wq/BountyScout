"""
Configuration for BountyScout micro bounty tracker.
"""
import os
from datetime import timedelta

# GitHub API Configuration
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN', '')
GITHUB_API_URL = "https://api.github.com/repos"

# Bounty Filtering
MIN_REWARD_THRESHOLD = 50.0  # Minimum reward in USD to consider
MAX_EFFORT_HOURS = 24.0      # Maximum estimated effort in hours

# Scanning Configuration
SCAN_INTERVAL_HOURS = 6       # Hours between scans for new bounties
BOUNTY_WATCHLIST = [
    "BasedHardware/omi",      # Example: BasedHardware/omi
    "tenstorrent/tt-tools-common",
    "Inkh95/t3n-trusted-approval-agent"
]