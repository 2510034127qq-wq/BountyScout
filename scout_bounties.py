"""
BountyScout – a lightweight GitHub bounty scanner.

This module contains the core logic used by the scanner and the test suite.
The original implementation was intentionally minimal; the test suite expects
a few helper functions to be available for inspecting bounty keywords and
managing the `seen_bounties.json` file.  The functions below are fully
type‑annotated, use the standard library only, and are written with
production‑grade error handling in mind.

The public API of this module is intentionally small:

* :data:`KEYWORDS` – the list of bounty‑related terms that the scanner looks
  for in issue bodies.
* :func:`contains_bounty_keyword` – a case‑insensitive check for any of the
  keywords in a string.
* :func:`load_seen_bounties` – read the JSON file that tracks already‑seen
  bounty URLs and return a :class:`set` of strings.
* :func:`save_seen_bounties` – persist a set of URLs back to the JSON file.

The test suite imports these symbols directly, so they must be defined at
module level.  The implementation below is deliberately straightforward
and does not rely on any third‑party packages, keeping the project
dependency‑free.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable, Set

# --------------------------------------------------------------------------- #
# Public constants
# --------------------------------------------------------------------------- #

#: The bounty‑related keywords that the scanner looks for.  They are kept in
#: a list rather than a set so that the order is stable for deterministic
#: output in tests.
KEYWORDS: list[str] = [
    "bounty",
    "paid task",
    "cash prize",
    "cash reward",
    "payment",
    "payout",
    "compensation",
    "reward",
    "paid challenge",
    "paid contribution",
    "paid PR",
    "contributor reward",
]

# --------------------------------------------------------------------------- #
# Helper functions
# --------------------------------------------------------------------------- #

#: Compile a single regular expression that matches any of the keywords as a
#: whole word, case‑insensitively.  The pattern is built once at import
#: time for efficiency.
_KEYWORDS_RE = re.compile(
    r"\b(?:%s)\b" % "|".join(re.escape(k) for k in KEYWORDS),
    flags=re.IGNORECASE,
)


def contains_bounty_keyword(text: str) -> bool:
    """
    Return ``True`` if *text* contains any of the bounty keywords.

    The check is performed in a case‑insensitive manner and matches whole
    words only.  This function is intentionally lightweight and suitable
    for use in a tight loop when scanning many issue bodies.

    Parameters
    ----------
    text:
        The string to search.

    Returns
    -------
    bool
        ``True`` if any keyword is present, otherwise ``False``.
    """
    return bool(_KEYWORDS_RE.search(text))


# --------------------------------------------------------------------------- #
# Seen‑bounties persistence helpers
# --------------------------------------------------------------------------- #

#: Path to the JSON file that stores the URLs of bounties that have already
#: been processed.  The file is located in the same directory as this module.
_SEEN_BOUNTIES_PATH = Path(__file__).parent / "seen_bounties.json"


def load_seen_bounties() -> Set[str]:
    """
    Load the set of already‑seen bounty URLs from :data:`_SEEN_BOUNTIES_PATH`.

    The file is expected to contain a JSON array of strings.  If the file
    does not exist, an empty set is returned.  Any JSON decoding error is
    propagated to the caller – the test suite expects this behaviour.

    Returns
    -------
    set[str]
        The set of URLs that have already been processed.
    """
    if not _SEEN_BOUNTIES_PATH.is_file():
        return set()

    with _SEEN_BOUNTIES_PATH.open("r", encoding="utf-8") as fp:
        data = json.load(fp)

    if not isinstance(data, list):
        raise ValueError("seen_bounties.json must contain a JSON array")

    return set(str(item) for item in data)


def save_seen_bounties(bounties: Iterable[str]) -> None:
    """
    Persist *bounties* to :data:`_SEEN_BOUNTIES_PATH`.

    The input is converted to a sorted list of unique strings before
    writing.  The file is written with UTF‑8 encoding and a trailing newline
    for readability.

    Parameters
    ----------
    bounties:
        An iterable of URLs to persist.
    """
    unique = sorted(set(str(b) for b in bounties))
    with _SEEN_BOUNTIES_PATH.open("w", encoding="utf-8") as fp:
        json.dump(unique, fp, ensure_ascii=False, indent=2)
        fp.write("\n")
