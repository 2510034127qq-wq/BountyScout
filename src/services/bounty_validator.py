"""
BasedHardware/omi Bounty Validator
Automated validation for micro bounty opportunities
"""

import json
from datetime import datetime
from typing import Dict, List, Optional


class BountyValidator:
    """Validates bounty opportunities against schema requirements."""

    def __init__(self, bounty_data: List[Dict]):
        self.bounty_data = bounty_data

    def validate_all(self) -> List[Dict]:
        """Run complete validation pipeline on all bounties."""
        validated = []
        for bounty in self.bounty_data:
            validated_bounty = self._validate_single(bounty)
            if validated_bounty:
                validated.append(validated_bounty)
        return validated

    def _validate_single(self, bounty: Dict) -> Optional[Dict]:
        """Validate individual bounty opportunity."""
        required_fields = {
            'id', 'title', 'project', 'reward', 'currency',
            'task', 'status', 'last_updated', 'validation'
        }

        if not required_fields.issubset(bounty.keys()):
            return None

        # Validate reward
        if not isinstance(bounty['reward'], int) or bounty['reward'] != 50:
            bounty['validation']['reward_verified'] = False
        else:
            bounty['validation']['reward_verified'] = True

        # Validate status
        if bounty['status'] not in ['open', 'closed', 'completed']:
            bounty['validation']['status_valid'] = False
        else:
            bounty['validation']['status_valid'] = True

        # Validate timestamp
        try:
            datetime.fromisoformat(bounty['last_updated'])
            bounty['validation']['timestamp_valid'] = True
        except (ValueError, TypeError):
            bounty['validation']['timestamp_valid'] = False

        # Validate competition check
        if 'no_competition' in bounty['validation']:
            bounty['validation']['competition_checked'] = True
        else:
            bounty['validation']['competition_checked'] = False

        return bounty

    def filter_valid_bounties(self) -> List[Dict]:
        """Return only bounties that pass all validation checks."""
        validated = self.validate_all()
        return [b for b in validated 
               if all(b['validation'].values())]


if __name__ == "__main__":
    with open('src/bounties/omi_bounties.json') as f:
        bounties = json.load(f)

    validator = BountyValidator(bounties)
    valid_bounties = validator.filter_valid_bounties()
    
    print(f"Validated {len(valid_bounties)}/{len(bounties)} bounties")
    print(f"Valid bounties: {len(valid_bounties)}")