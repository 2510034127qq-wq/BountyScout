import pytest
from fastapi import HTTPException
from backend.routers.candidates import WorkstreamCandidateResolver
from backend.errors import CandidateStoreError

def test_candidate_error_sanitization():
    resolver = WorkstreamCandidateResolver()

    with pytest.raises(HTTPException) as exc_info:
        resolver._resolve_candidate("invalid_id")

    assert "Failed to retrieve candidate data." in exc_info.value.detail
    assert "internal database schema" not in exc_info.value.detail.lower()
