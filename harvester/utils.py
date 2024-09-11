"""harvester.utils"""

# ruff: noqa: ANN401

import os
from collections.abc import Callable
from typing import Any, TypeVar

from harvester.exceptions import RequiresContainerContextError

ReturnType = TypeVar("ReturnType")


def require_container(func: Callable[..., ReturnType]) -> Callable[..., ReturnType]:
    """Decorator for functions/methods that must be run inside the Docker container.

    This checks to see if application is running in a container by looking for either a
    /.dockerenv file exists (created automatically by Docker and indicates locally running
    docker container) or the environment variable AWS_EXECUTION_ENV is set (set
    automatically by, and indicates, a running Fargate ECS task).
    """

    def wrapper(*args: Any, **kwargs: Any) -> ReturnType:
        if (
            not os.path.exists("/.dockerenv")
            and os.getenv("AWS_EXECUTION_ENV", None) is None
        ):
            raise RequiresContainerContextError
        return func(*args, **kwargs)

    return wrapper
