import pytest
from fastapi import HTTPException
from backend.routers.action_items import ActionItemRouter
from backend.errors import TaskRelationshipConflict

def test_task_relationship_error_sanitization():
    router = ActionItemRouter()

    with pytest.raises(HTTPException) as exc_info:
        router.update_task_relationship("test_id", {"invalid": "relation"})

    assert "Task relationship conflict detected." in exc_info.value.detail
    assert "internal_task_state" not in exc_info.value.detail
