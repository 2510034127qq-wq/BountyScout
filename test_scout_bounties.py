"""
Test suite for the BountyScout helper functions.

The tests exercise the keyword detection logic and the persistence helpers
for the `seen_bounties.json` file.  They are intentionally simple but
cover the edge cases that the production code must handle.
"""

import json
import os
import tempfile
from pathlib import Path

import pytest

# Import the module under test
import scout_bounties

# --------------------------------------------------------------------------- #
# Keyword detection tests
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("This is a bounty for you", True),
        ("Paid task: fix the bug", True),
        ("No relevant content here", False),
        ("Cash prize awaits", True),
        ("Reward is high", True),
        ("Paid PR is open", True),
        ("contributor reward", True),
        ("This is a paidtask", False),  # should not match without space
        ("The word rewardable", False),  # should not match as whole word
    ],
)
def test_contains_bounty_keyword(text, expected):
    assert scout_bounties.contains_bounty_keyword(text) is expected


# --------------------------------------------------------------------------- #
# Persistence helper tests
# --------------------------------------------------------------------------- #

@pytest.fixture
def temp_seen_file(tmp_path: Path) -> Path:
    """Create a temporary `seen_bounties.json` file in a fresh directory."""
    path = tmp_path / "seen_bounties.json"
    path.write_text("[]", encoding="utf-8")
    return path


def test_load_seen_bounties_empty(tmp_path: Path):
    """When the file does not exist, an empty set is returned."""
    # Ensure the file is missing
    missing_path = tmp_path / "seen_bounties.json"
    assert not missing_path.exists()

    # Temporarily change the module's path to the temp directory
    original_path = scout_bounties._SEEN_BOUNTIES_PATH
    scout_bounties._SEEN_BOUNTIES_PATH = missing_path
    try:
        assert scout_bounties.load_seen_bounties() == set()
    finally:
        scout_bounties._SEEN_BOUNTIES_PATH = original_path


def test_load_seen_bounties_valid(tmp_path: Path):
    """A valid JSON array is loaded correctly."""
    path = tmp_path / "seen_bounties.json"
    path.write_text('["https://github.com/owner/repo/issues/1"]', encoding="utf-8")

    original_path = scout_bounties._SEEN_BOUNTIES_PATH
    scout_bounties._SEEN_BOUNTIES_PATH = path
    try:
        assert scout_bounties.load_seen_bounties() == {"https://github.com/owner/repo/issues/1"}
    finally:
        scout_bounties._SEEN_BOUNTIES_PATH = original_path


def test_load_seen_bounties_invalid(tmp_path: Path):
    """Invalid JSON raises a ValueError."""
    path = tmp_path / "seen_bounties.json"
    path.write_text('{"invalid": "json"}', encoding="utf-8")

    original_path = scout_bounties._SEEN_BOUNTIES_PATH
    scout_bounties._SEEN_BOUNTIES_PATH = path
    try:
        with pytest.raises(ValueError):
            scout_bounties.load_seen_bounties()
    finally:
        scout_bounties._SEEN_BOUNTIES_PATH = original_path


def test_save_seen_bounties(tmp_path: Path):
    """The set of URLs is written as a sorted JSON array."""
    path = tmp_path / "seen_bounties.json"

    original_path = scout_bounties._SEEN_BOUNTIES_PATH
    scout_bounties._SEEN_BOUNTIES_PATH = path
    try:
        scout_bounties.save_seen_bounties(
            {"https://github.com/a", "https://github.com/b", "https://github.com/a"}
        )
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data == ["https://github.com/a", "https://github.com/b"]
    finally:
        scout_bounties._SEEN_BOUNTIES_PATH = original_path
