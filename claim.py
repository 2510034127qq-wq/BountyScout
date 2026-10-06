#!/usr/bin/env python3
"""
Bounty claim module for BountyScout.

Handles claiming bounties and tracking submission status.
"""

import json
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Optional

from models import BountyClaim


CLAIMS_FILE = "claims.json"


def load_claims() -> list[BountyClaim]:
    """Load existing claims from file."""
    path = Path(CLAIMS_FILE)
    if not path.exists():
        return []
    with open(path) as f:
        data = json.load(f)
    claims = []
    for item in data:
        claims.append(BountyClaim(
            bounty_id=item["bounty_id"],
            repository=item["repository"],
            claimant=item["claimant"],
            claimed_at=datetime.fromisoformat(item["claimed_at"]),
            status=item["status"],
        ))
    return claims


def save_claims(claims: list[BountyClaim]):
    """Save claims to file."""
    data = [
        {
            "bounty_id": c.bounty_id,
            "repository": c.repository,
            "claimant": c.claimant,
            "claimed_at": c.claimed_at.isoformat(),
            "status": c.status,
        }
        for c in claims
    ]
    with open(CLAIMS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def claim_bounty(repository: str, issue_number: int, claimant: str) -> BountyClaim:
    """Submit a bounty claim for an issue."""
    claims = load_claims()

    bounty_id = f"{repository}#{issue_number}"
    # Check for duplicate claim
    for c in claims:
        if c.bounty_id == bounty_id:
            raise ValueError(f"Already claimed: {bounty_id}")

    claim = BountyClaim(
        bounty_id=bounty_id,
        repository=repository,
        claimant=claimant,
        claimed_at=datetime.utcnow(),
        status="pending",
    )
    claims.append(claim)
    save_claims(claims)
    print(f"Claim submitted: {bounty_id} by {claimant}")
    return claim


def get_pending_claims() -> list[BountyClaim]:
    """Return all pending claims."""
    return [c for c in load_claims() if c.status == "pending"]


def mark_completed(bounty_id: str):
    """Mark a claim as completed."""
    claims = load_claims()
    for c in claims:
        if c.bounty_id == bounty_id:
            c.status = "completed"
            break
    save_claims(claims)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Bounty claim management")
    parser.add_argument("command", choices=["claim", "list", "complete"])
    parser.add_argument("--repo", help="Repository (owner/name)")
    parser.add_argument("--issue", type=int, help="Issue number")
    parser.add_argument("--claimant", default="agent", help="Claimant identifier")
    args = parser.parse_args()

    if args.command == "claim":
        if not args.repo or not args.issue:
            parser.error("--repo and --issue required for claim")
        claim_bounty(args.repo, args.issue, args.claimant)
    elif args.command == "list":
        pending = get_pending_claims()
        print(f"Pending claims: {len(pending)}")
        for c in pending:
            print(f"  - {c.bounty_id} ({c.claimant})")
    elif args.command == "complete":
        if not args.repo or not args.issue:
            parser.error("--repo and --issue required for complete")
        mark_completed(f"{args.repo}#{args.issue}")
        print(f"Completed: {args.repo}#{args.issue}")


if __name__ == "__main__":
    main()
