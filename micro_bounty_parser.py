"""
micro_bounty_parser.py

Utility to parse the special “Micro Bounty Alert” markdown format that
BountyScout may encounter. The format looks like:

#### 1. [Title of bounty]
- **Project:** [Owner/Repo](https://github.com/Owner/Repo)
- **Source:** GitHub Issue (https://github.com/Owner/Repo/issues/123)
- **Reward:** $50
- **Task:** Some description …

Multiple such sections can appear in a single issue body. This module
extracts each section into a dictionary with the most useful fields.
"""

import re
from typing import List, Dict


def _parse_key_value(line: str) -> tuple[str, str] | None:
    """
    Parse a markdown list line of the form ``- **Key:** Value``.
    Returns a (key, value) tuple or ``None`` if the line does not match.
    """
    match = re.match(r"- \*\*(.+?):\*\* (.+)", line)
    if not match:
        return None
    key, value = match.group(1).strip(), match.group(2).strip()
    return key, value


def parse_micro_bounty_alert(text: str) -> List[Dict[str, object]]:
    """
    Parse a markdown body that contains one or more “Micro Bounty Alert”
    sections.

    Parameters
    ----------
    text:
        The raw markdown text (e.g. the body of a GitHub issue).

    Returns
    -------
    A list of dictionaries, each representing a bounty. Only the most
    common fields are extracted; unknown fields are ignored.
    """
    entries: List[Dict[str, object]] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # Section header – starts with four # characters
        if line.startswith("#### "):
            # Title may be prefixed with a number and a dot, we keep the whole title.
            title = line[5:].strip()
            entry: Dict[str, object] = {"title": title}
            i += 1
            # Consume following list items until the next header or EOF
            while i < len(lines) and not lines[i].strip().startswith("#### "):
                kv = _parse_key_value(lines[i].strip())
                if kv:
                    key, value = kv
                    # Normalise known keys
                    if key == "Project":
                        # Expected format: [Owner/Repo](url)
                        proj_match = re.match(r"\[(.+?)\]\((.+?)\)", value)
                        if proj_match:
                            entry["project_name"] = proj_match.group(1)
                            entry["project_url"] = proj_match.group(2)
                    elif key == "Source":
                        # Expected format: GitHub Issue (url)
                        src_match = re.search(r"\((https?://[^)]+)\)", value)
                        if src_match:
                            entry["source_url"] = src_match.group(1)
                    elif key == "Reward":
                        # Strip any non‑digit characters and store as int
                        amount_match = re.search(r"\d+", value.replace(",", ""))
                        if amount_match:
                            entry["reward"] = int(amount_match.group(0))
                    elif key == "Task":
                        entry["task"] = value
                    else:
                        # Store any other key verbatim for possible future use
                        entry[key.lower().replace(" ", "_")] = value
                i += 1
            entries.append(entry)
        else:
            i += 1
    return entries
