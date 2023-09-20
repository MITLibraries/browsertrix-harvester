"""browsertrix_harvester.utils"""
# ruff: noqa: ANN401

import os
from collections.abc import Callable
from typing import Any, TypeVar

from browsertrix_harvester.exceptions import RequiresContainerContextError

IN_CONTAINER: bool = os.path.exists("/.dockerenv")

ReturnType = TypeVar("ReturnType")


def require_container(func: Callable[..., ReturnType]) -> Callable[..., ReturnType]:
    """Decorator for functions/methods that must be run inside the Docker container."""

    def wrapper(*args: Any, **kwargs: Any) -> ReturnType:
        if not IN_CONTAINER:
            raise RequiresContainerContextError
        return func(*args, **kwargs)

    return wrapper
