import json
import textwrap

from micro_bounty_parser import parse_micro_bounty_alert


SAMPLE_TEXT = textwrap.dedent(
    """
    ### Active Micro Bounty Scan Results

    **Scan Time:** 2026-09-21 00:08 UTC

    #### 1. [Making a legacy private app public orphans its reviews, API keys and installs](https://github.com/BasedHardware/omi/issues/15284)
    - **Project:** [BasedHardware/omi](https://github.com/BasedHardware/omi)
    - **Source:** GitHub Issue (https://github.com/BasedHardware/omi/issues/15284)
    - **Reward:** $50
    - **Task:** Stop re-minting the id and just flip the flag, as the else branch already does. That removes every orphaning at once and leaves all references valid, but it keeps -private in the id of a now-public app.
    - **Deadline:** 待确认
    - **Submission:** 待确认

    #### 2. [A failed chat turn still spends the user's question, and retrying spends another](https://github.com/BasedHardware/omi/issues/15287)
    - **Project:** [BasedHardware/omi](https://github.com/BasedHardware/omi)
    - **Source:** GitHub Issue (https://github.com/BasedHardware/omi/issues/15287)
    - **Reward:** $50
    - **Task:** Either half can be closed on its own. A release on the terminal-failure branch fixes the first without touching the wire contract. The second needs the client to supply the message id or an idempotency key so a retry reuses it, which is an API change and your call.
    - **Deadline:** 待确认

    #### 3. [Live listen billing charges the silent gap every time audio resumes](https://github.com/BasedHardware/omi/issues/15263)
    - **Project:** [BasedHardware/omi](https://github.com/BasedHardware/omi)
    - **Source:** GitHub Issue (https://github.com/BasedHardware/omi/issues/15263)
    - **Reward:** $50
    - **Task:** billabletranscriptionseconds (backend/utils/analytics.py:7) clamps the end
    """
).strip()


def test_parse_micro_bounty_alert():
    entries = parse_micro_bounty_alert(SAMPLE_TEXT)
    # Expect three entries
    assert len(entries) == 3

    # Spot‑check the first entry
    first = entries[0]
    assert first["title"].startswith("1.")
    assert first["project_name"] == "BasedHardware/omi"
    assert first["project_url"] == "https://github.com/BasedHardware/omi"
    assert first["source_url"] == "https://github.com/BasedHardware/omi/issues/15284"
    assert first["reward"] == 50
    assert "Stop re-minting the id" in first["task"]

    # Spot‑check the second entry
    second = entries[1]
    assert second["title"].startswith("2.")
    assert second["reward"] == 50
    assert "Either half can be closed" in second["task"]

    # Spot‑check the third entry
    third = entries[2]
    assert third["title"].startswith("3.")
    assert third["reward"] == 50
    assert "billabletranscriptionseconds" in third["task"]
