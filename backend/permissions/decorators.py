"""
Permission Decorators

These decorators protect service methods, background jobs,
scheduled tasks, CLI commands, and any non-FastAPI execution.

Example:

@require_permission(Permission.CLIENTS_CREATE.value)
def create_client(...):
    ...

Example:

@require_any_permission(
    Permission.USERS_VIEW.value,
    Permission.USERS_UPDATE.value,
)
"""

from __future__ import annotations

from functools import wraps
from typing import Any
from typing import Callable

from permissions.dependency import (
    has_permission,
    has_any_permission,
    has_all_permissions,
)


class PermissionError(Exception):
    """
    Raised when a permission check fails.
    """

    pass


def require_permission(permission: str):

    def decorator(func: Callable):

        @wraps(func)
        def wrapper(*args, **kwargs):

            user = kwargs.get("current_user")

            if user is None:

                if args:

                    candidate = args[0]

                    if hasattr(candidate, "current_user"):

                        user = candidate.current_user

            if user is None:

                raise PermissionError(
                    "Current user not supplied."
                )

            if not has_permission(
                user,
                permission,
            ):

                raise PermissionError(
                    f"Permission '{permission}' required."
                )

            return func(*args, **kwargs)

        return wrapper

    return decorator


def require_any_permission(
    *permissions: str,
):

    def decorator(func: Callable):

        @wraps(func)
        def wrapper(*args, **kwargs):

            user = kwargs.get("current_user")

            if user is None:

                if args:

                    candidate = args[0]

                    if hasattr(candidate, "current_user"):

                        user = candidate.current_user

            if user is None:

                raise PermissionError(
                    "Current user not supplied."
                )

            if not has_any_permission(
                user,
                permissions,
            ):

                raise PermissionError(
                    "Required permission missing."
                )

            return func(*args, **kwargs)

        return wrapper

    return decorator


def require_all_permissions(
    *permissions: str,
):

    def decorator(func: Callable):

        @wraps(func)
        def wrapper(*args, **kwargs):

            user = kwargs.get("current_user")

            if user is None:

                if args:

                    candidate = args[0]

                    if hasattr(candidate, "current_user"):

                        user = candidate.current_user

            if user is None:

                raise PermissionError(
                    "Current user not supplied."
                )

            if not has_all_permissions(
                user,
                permissions,
            ):

                raise PermissionError(
                    "One or more permissions are missing."
                )

            return func(*args, **kwargs)

        return wrapper

    return decorator


def super_admin_only(func: Callable):

    @wraps(func)
    def wrapper(*args, **kwargs):

        user = kwargs.get("current_user")

        if user is None:

            if args:

                candidate = args[0]

                if hasattr(candidate, "current_user"):

                    user = candidate.current_user

        if user is None:

            raise PermissionError(
                "Current user missing."
            )

        role = getattr(
            user,
            "role",
            None,
        )

        role_name = getattr(
            role,
            "name",
            role,
        )

        if str(role_name).lower() != "super_admin":

            raise PermissionError(
                "Super Administrator privileges required."
            )

        return func(*args, **kwargs)

    return wrapper


def agency_owner_only(func: Callable):

    @wraps(func)
    def wrapper(*args, **kwargs):

        user = kwargs.get("current_user")

        if user is None:

            if args:

                candidate = args[0]

                if hasattr(candidate, "current_user"):

                    user = candidate.current_user

        if user is None:

            raise PermissionError(
                "Current user missing."
            )

        role = getattr(
            user,
            "role",
            None,
        )

        role_name = getattr(
            role,
            "name",
            role,
        )

        allowed = {
            "agency_owner",
            "super_admin",
        }

        if str(role_name).lower() not in allowed:

            raise PermissionError(
                "Agency Owner privileges required."
            )

        return func(*args, **kwargs)

    return wrapper