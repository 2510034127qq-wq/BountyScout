from __future__ import annotations

import anyio
from anyio import failafter, tothread
from typing import Any, Callable, Optional

class MCPDeployer:
    def __init__(self, timeout: Optional[float] = None):
        self.timeout = timeout

    def _call(self, fn: Callable[..., Any], *args, **kwargs) -> Any:
        """Execute a function with enforced timeout for blocking targets.

        Args:
            fn: The function to execute.
            *args: Positional arguments for `fn`.
            **kwargs: Keyword arguments for `fn`.

        Returns:
            The result of `fn`.

        Raises:
            TimeoutError: If the function exceeds the timeout.
        """
        if self.timeout is None:
            return fn(*args, **kwargs)

        def wrapped() -> Any:
            return fn(*args, **kwargs)

        # Enforce timeout without shielding worker waits
        return anyio.run(failafter(self.timeout, wrapped))