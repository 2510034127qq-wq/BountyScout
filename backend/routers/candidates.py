from fastapi import HTTPException
from backend.errors import CandidateStoreError, TaskLinkValidationError
from backend.utils import sanitize_error_message

class WorkstreamCandidateResolver:
    # ... existing code ...

    def _resolve_candidate(self, candidate_id: str):
        try:
            # ... existing resolution logic ...
            return candidate_data
        except CandidateStoreError as exc:
            raise HTTPException(
                status_code=500,
                detail=sanitize_error_message(
                    "Failed to retrieve candidate data.",
                    exc
                )
            )
        except TaskLinkValidationError as exc:
            raise HTTPException(
                status_code=400,
                detail=sanitize_error_message(
                    "Invalid candidate task relationship.",
                    exc
                )
            )
