import json
import os
from unittest import mock

import pytest

# Import the function we want to test
from scout_bounties import extract_bounties_from_issue, load_seen, save_seen


@pytest.fixture
def dummy_issue():
    return {
        "title": "Micro Bounty Alert: 3 New Opportunities",
        "html_url": "https://github.com/example/repo/issues/999",
        "body": """
### Active Micro Bounty Scan Results

#### 1. [Sample bounty one](https://github.com/example/repo/issues/1)
- **Project:** [example/repo](https://github.com/example/repo)
- **Source:** GitHub Issue (https://github.com/example/repo/issues/1)
- **Reward:** $100
- **Task:** Do something useful.
""",
    }


def test_extract_bounties_from_issue_micro_alert(dummy_issue):
    results = extract_bounties_from_issue(dummy_issue)
    # Two results: one classic detection (keyword “bounty”) and one micro‑alert entry
    assert len(results) == 2

    # Classic detection entry
    classic = next(r for r in results if r.get("source") == "issue")
    assert classic["title"] == dummy_issue["title"]
    assert classic["url"] == dummy_issue["html_url"]

    # Micro‑alert entry
    micro = next(r for r in results if r.get("source") == "micro_alert")
    assert micro["title"] == "1. [Sample bounty one](https://github.com/example/repo/issues/1)"
    assert micro["reward"] == 100
    assert micro["project_name"] == "example/repo"
    assert micro["project_url"] == "https://github.com/example/repo"
    assert micro["url"] == "https://github.com/example/repo/issues/1"


def test_seen_file_roundtrip(tmp_path):
    # Use a temporary file path for isolation
    seen_path = tmp_path / "seen_bounties.json"
    original_path = "seen_bounties.json"

    # Patch the path used inside the module
    with mock.patch.object(os.path, "exists", lambda p: p == str(seen_path)):
        with mock.patch("builtins.open", mock.mock_open()) as m:
            # Save a set
            save_seen({"https://example.com/1", "https://example.com/2"})
            # Ensure the file was written with sorted list
            handle = m()
            written = "".join(call.args[0] for call in handle.write.mock_calls)
            data = json.loads(written)
            assert data == [
                "https://example.com/1",
                "https://example.com/2",
            ]

            # Now load it back
            handle.read.return_value = json.dumps(data)
            loaded = load_seen()
            assert loaded == {"https://example.com/1", "https://example.com/2"}
