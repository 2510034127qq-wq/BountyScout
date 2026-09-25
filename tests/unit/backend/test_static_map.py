import pytest
from fastapi import HTTPException
from backend.routers.static_map import StaticMapRouter

def test_coordinate_error_sanitization():
    router = StaticMapRouter()

    with pytest.raises(HTTPException) as exc_info:
        router.parse_coordinates("invalid,coords")

    assert "Invalid coordinate format." in exc_info.value.detail
    assert "provider_internal_error" not in exc_info.value.detail
