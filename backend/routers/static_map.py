from fastapi import HTTPException
from backend.errors import CoordinateParseError, ProviderError
from backend.utils import sanitize_error_message

class StaticMapRouter:
    # ... existing code ...

    def parse_coordinates(self, coordinates: str):
        try:
            parsed = self._validate_coordinates(coordinates)
            return self._query_provider(parsed)
        except CoordinateParseError as exc:
            raise HTTPException(
                status_code=400,
                detail=sanitize_error_message(
                    "Invalid coordinate format.",
                    exc
                )
            )
        except ProviderError as exc:
            raise HTTPException(
                status_code=503,
                detail=sanitize_error_message(
                    "Map provider unavailable.",
                    exc
                )
            )

    def _validate_coordinates(self, coordinates: str):
        # ... existing validation logic ...
        return validated_coords
