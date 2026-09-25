from fastapi import HTTPException
from backend.errors import TemporalReadError, DeviceScopeError
from backend.utils import sanitize_error_message

class MemoryRouter:
    # ... existing code ...

    def read_temporal_memory(self, memory_id: str, timestamp: str):
        try:
            # ... existing read logic ...
            return memory_data
        except TemporalReadError as exc:
            raise HTTPException(
                status_code=400,
                detail=sanitize_error_message(
                    "Invalid temporal memory access parameters.",
                    exc
                )
            )
        except DeviceScopeError as exc:
            raise HTTPException(
                status_code=403,
                detail=sanitize_error_message(
                    "Access denied for requested memory scope.",
                    exc
                )
            )
