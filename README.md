# BountyScout

A GitHub-based bounty hunting and tracking tool that scans for micro bounties across repositories.

## Features

- Scan GitHub issues for bounty opportunities
- Categorize by reward, competition, and effort
- Track coding agent fit and related PRs
- Export structured reports

## Usage

Run a scan:

```bash
python scan.py --repo <owner/repo>
```

## Structure

- `scan.py` - Main scanning logic
- `models.py` - Data models for bounties
- `output/` - Generated reports
