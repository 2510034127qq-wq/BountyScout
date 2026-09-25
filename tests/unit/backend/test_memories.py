import pytest
from fastapi import HTTPException
from backend.routers.memories import MemoryRouter
from backend.errors import TemporalReadError

def test_memory_error_sanitization():
    router = MemoryRouter()

    with pytest.raises(HTTPException) as exc_info:
        router.read_temporal_memory("test_id", "invalid_timestamp")

    assert "Invalid temporal memory access parameters." in exc_info.value.detail
    assert "collection_123" not in exc_info.value.detail
