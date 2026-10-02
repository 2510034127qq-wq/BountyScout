"""
Bounty Utility Functions
Common operations for bounty management
"""

from typing import Dict, List
from datetime import datetime, timedelta


def calculate_deadline(last_updated: str, days: int = 7) -> Optional[str]:
    """Calculate deadline from last updated timestamp."""
    try:
        dt = datetime.fromisoformat(last_updated)
        deadline = dt + timedelta(days=days)
        return deadline.isoformat()
    except (ValueError, TypeError):
        return None


def estimate_effort_range(effort_estimate: str) -> Dict[str, float]:
    """Convert effort estimate string to numeric range."""
    ranges = {
        'few minutes': (0.1, 0.5),
        'few hours': (0.5, 4),
        '1 day': (4, 8),
        '1-2 hours': (1, 2),
        '2-4 hours': (2, 4),
        '3-6 hours': (3, 6),
        '4-8 hours': (4, 8)
    }
    
    for key, value in ranges.items():
        if key in effort_estimate.lower():
            return {
                'min_hours': value[0],
                'max_hours': value[1],
                'description': key
            }
    
    return {
        'min_hours': 0,
        'max_hours': 8,
        'description': 'unknown'
    }


def normalize_bounty_data(bounty: Dict) -> Dict:
    """Normalize bounty data structure."""
    normalized = bounty.copy()
    
    # Standardize project reference
    if 'project' in normalized and '/' in normalized['project']:
        normalized['project_reference'] = normalized['project'].split('/')
    
    # Calculate deadline if not set
    if 'deadline' not in normalized or not normalized['deadline']:
        normalized['deadline'] = calculate_deadline(normalized['last_updated'])
    
    # Parse effort estimate
    if 'effort_estimate' in normalized:
        normalized['effort'] = estimate_effort_range(normalized['effort_estimate'])
    
    # Standardize validation flags
    if 'validation' not in normalized:
        normalized['validation'] = {}
    
    return normalized


def filter_by_status(bounties: List[Dict], status: str = 'open') -> List[Dict]:
    """Filter bounties by status."""
    return [b for b in bounties if b.get('status', '').lower() == status.lower()]


def sort_by_priority(bounties: List[Dict]) -> List[Dict]:
    """Sort bounties by priority (newest first, then by effort)."""
    return sorted(
        bounties,
        key=lambda x: (
            -datetime.fromisoformat(x['last_updated']).timestamp() if 'last_updated' in x else 0,
            x.get('effort', {}).get('min_hours', 0)
        )
    )