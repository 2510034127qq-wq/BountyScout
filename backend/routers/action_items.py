from fastapi import HTTPException
from backend.errors import TaskRelationshipConflict
from backend.utils import sanitize_error_message

class ActionItemRouter:
    # ... existing code ...

    def update_task_relationship(self, task_id: str, new_relationship: dict):
        try:
            # ... existing update logic ...
            return updated_task
        except TaskRelationshipConflict as exc:
            raise HTTPException(
                status_code=409,
                detail=sanitize_error_message(
                    "Task relationship conflict detected.",
                    exc
                )
            )
