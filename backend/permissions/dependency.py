"""
Permission Dependency

FastAPI dependency used to protect endpoints.

Example:

@router.post(
    "/clients",
    dependencies=[
        Depends(
            require_permission(
                Permission.CLIENTS_CREATE
            )
        )
    ]
)
"""

from __future__ import annotations

from typing import Iterable

from fastapi import Depends
from fastapi import HTTPException
from fastapi import status

from core.dependencies import get_current_user
from models.user import User
from permissions.registry import PermissionRegistry


class PermissionDenied(HTTPException):

    def __init__(
        self,
        permission: str,
    ):

        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission '{permission}' required.",
        )


def _extract_permissions(
    user: User,
) -> set[str]:

    permissions = getattr(
        user,
        "permissions",
        None,
    )

    if permissions:

        return {

            str(permission)

            for permission

            in permissions

        }

    role = getattr(
        user,
        "role",
        None,
    )

    if role is None:

        return set()

    role_name = getattr(
        role,
        "name",
        role,
    )

    return PermissionRegistry.role_permissions(
        str(role_name)
    )


def require_permission(
    permission: str,
):

    if not PermissionRegistry.exists(
        permission
    ):

        raise RuntimeError(
            f"Unknown permission '{permission}'. "
            "Register it inside permissions/constants.py"
        )

    async def dependency(

        current_user: User = Depends(
            get_current_user
        ),

    ) -> User:

        permissions = _extract_permissions(
            current_user
        )

        if permission not in permissions:

            raise PermissionDenied(
                permission
            )

        return current_user

    return dependency


def require_any_permission(
    *permissions: str,
):

    for permission in permissions:

        if not PermissionRegistry.exists(
            permission
        ):

            raise RuntimeError(
                f"Unknown permission '{permission}'."
            )

    async def dependency(

        current_user: User = Depends(
            get_current_user
        ),

    ) -> User:

        user_permissions = _extract_permissions(
            current_user
        )

        if any(

            permission in user_permissions

            for permission

            in permissions

        ):

            return current_user

        raise HTTPException(

            status_code=status.HTTP_403_FORBIDDEN,

            detail="Insufficient permissions.",

        )

    return dependency


def require_all_permissions(
    *permissions: str,
):

    for permission in permissions:

        if not PermissionRegistry.exists(
            permission
        ):

            raise RuntimeError(
                f"Unknown permission '{permission}'."
            )

    async def dependency(

        current_user: User = Depends(
            get_current_user
        ),

    ) -> User:

        user_permissions = _extract_permissions(
            current_user
        )

        missing = [

            permission

            for permission

            in permissions

            if permission not in user_permissions

        ]

        if missing:

            raise HTTPException(

                status_code=status.HTTP_403_FORBIDDEN,

                detail={

                    "message": "Missing permissions.",

                    "missing": missing,

                },

            )

        return current_user

    return dependency


def has_permission(
    user: User,
    permission: str,
) -> bool:

    return (

        permission

        in _extract_permissions(user)

    )


def has_any_permission(
    user: User,
    permissions: Iterable[str],
) -> bool:

    user_permissions = _extract_permissions(
        user
    )

    return any(

        permission in user_permissions

        for permission

        in permissions

    )


def has_all_permissions(
    user: User,
    permissions: Iterable[str],
) -> bool:

    user_permissions = _extract_permissions(
        user
    )

    return all(

        permission in user_permissions

        for permission

        in permissions

    )