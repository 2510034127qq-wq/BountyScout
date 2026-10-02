import logging
from typing import Tuple

logger = logging.getLogger(__name__)

def sanitize_error_message(base_message: str, exc: Exception) -> str:
    """Sanitizes error messages while preserving technical details in logs."""
    sanitized = base_message
    logger.error(f"Original error: {str(exc)}", exc_info=True)
    return sanitized
