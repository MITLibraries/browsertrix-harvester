"""browsertrix_harvester.utils"""
# ruff: noqa: ANN401

import os
from collections.abc import Callable
from typing import Any, TypeVar

from browsertrix_harvester.exceptions import RequiresContainerContextError

ReturnType = TypeVar("ReturnType")


def require_container(func: Callable[..., ReturnType]) -> Callable[..., ReturnType]:
    """Decorator for functions/methods that must be run inside the Docker container."""

    def wrapper(*args: Any, **kwargs: Any) -> ReturnType:
        # TODO: re-enable after determining what files and/or env vars indicate docker
        #   container or fargate ECS task
        # if not (
        #     os.path.exists("/.dockerenv") or os.getenv("DOCKER_HOST", None) is not None
        # ):
        #     raise RequiresContainerContextError
        return func(*args, **kwargs)

    return wrapper
