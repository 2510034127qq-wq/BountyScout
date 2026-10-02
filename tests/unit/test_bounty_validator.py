"""
Unit tests for BountyValidator
"""

import pytest
from src.services.bounty_validator import BountyValidator


def test_validate_all():
    """Test complete validation pipeline."""
    test_data = [
        {
            'id': '123',
            'title': 'Test Bounty',
            'project': 'test/repo',
            'reward': 50,
            'currency': 'USD',
            'task': 'Test task',
            'status': 'open',
            'last_updated': '2026-09-25T00:00:00Z',
            'validation': {
                'reward_verified': True,
                'no_competition': True
            }
        },
        {
            'id': '456',
            'title': 'Invalid Bounty',
            'project': 'test/repo',
            'reward': 100,  # Invalid reward
            'currency': 'USD',
            'task': 'Test task',
            'status': 'open',
            'last_updated': '2026-09-25T00:00:00Z',
            'validation': {
                'reward_verified': False,
                'no_competition': True
            }
        }
    ]
    
    validator = BountyValidator(test_data)
    validated = validator.validate_all()
    
    assert len(validated) == 2
    assert validated[0]['validation']['reward_verified'] is True
    assert validated[1]['validation']['reward_verified'] is False


def test_filter_valid_bounties():
    """Test filtering of valid bounties."""
    test_data = [
        {
            'id': '123',
            'title': 'Valid Bounty',
            'project': 'test/repo',
            'reward': 50,
            'currency': 'USD',
            'task': 'Test task',
            'status': 'open',
            'last_updated': '2026-09-25T00:00:00Z',
            'validation': {
                'reward_verified': True,
                'no_competition': True,
                'status_valid': True,
                'timestamp_valid': True
            }
        },
        {
            'id': '456',
            'title': 'Invalid Bounty',
            'project': 'test/repo',
            'reward': 50,
            'currency': 'USD',
            'task': 'Test task',
            'status': 'invalid',
            'last_updated': '2026-09-25T00:00:00Z',
            'validation': {
                'reward_verified': True,
                'no_competition': True,
                'status_valid': False
            }
        }
    ]
    
    validator = BountyValidator(test_data)
    valid_bounties = validator.filter_valid_bounties()
    
    assert len(valid_bounties) == 1
    assert valid_bounties[0]['id'] == '123'


def test_timestamp_validation():
    """Test timestamp validation."""
    test_data = [
        {
            'id': '123',
            'title': 'Valid Timestamp',
            'project': 'test/repo',
            'reward': 50,
            'currency': 'USD',
            'task': 'Test task',
            'status': 'open',
            'last_updated': '2026-09-25T00:00:00Z',
            'validation': {}
        },
        {
            'id': '456',
            'title': 'Invalid Timestamp',
            'project': 'test/repo',
            'reward': 50,
            'currency': 'USD',
            'task': 'Test task',
            'status': 'open',
            'last_updated': 'invalid-date',
            'validation': {}
        }
    ]
    
    validator = BountyValidator(test_data)
    validated = validator.validate_all()
    
    assert validated[0]['validation']['timestamp_valid'] is True
    assert validated[1]['validation']['timestamp_valid'] is False