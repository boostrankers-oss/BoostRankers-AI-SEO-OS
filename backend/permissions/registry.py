"""
Enterprise Permission Registry

Responsible for:

• Registering all permissions
• Validating permissions
• Returning permissions by role
• Permission lookup
• Permission synchronization
"""

from __future__ import annotations

from typing import Dict
from typing import List
from typing import Set

from permissions.constants import (
    Permission,
    SUPER_ADMIN_PERMISSIONS,
    AGENCY_OWNER_DEFAULT,
    MANAGER_DEFAULT,
    SEO_SPECIALIST_DEFAULT,
    CONTENT_WRITER_DEFAULT,
    CLIENT_DEFAULT,
)


class PermissionRegistry:

    """
    Central permission registry.

    Every permission used anywhere in the application
    MUST be declared inside constants.py.

    This class guarantees there are no duplicate
    or invalid permissions.
    """

    _permissions: Set[str] = {
        permission.value
        for permission in Permission
    }

    _roles: Dict[str, Set[str]] = {

        "super_admin": SUPER_ADMIN_PERMISSIONS,

        "agency_owner": AGENCY_OWNER_DEFAULT,

        "manager": MANAGER_DEFAULT,

        "seo_specialist": SEO_SPECIALIST_DEFAULT,

        "content_writer": CONTENT_WRITER_DEFAULT,

        "client": CLIENT_DEFAULT,

    }

    # -------------------------------------------------

    @classmethod
    def permissions(cls) -> List[str]:

        return sorted(cls._permissions)

    # -------------------------------------------------

    @classmethod
    def exists(
        cls,
        permission: str,
    ) -> bool:

        return permission in cls._permissions

    # -------------------------------------------------

    @classmethod
    def validate(
        cls,
        permissions: list[str],
    ):

        invalid = [

            permission

            for permission in permissions

            if permission not in cls._permissions

        ]

        if invalid:

            raise ValueError(

                f"Unknown permissions: {invalid}"

            )

    # -------------------------------------------------

    @classmethod
    def role_permissions(
        cls,
        role: str,
    ) -> Set[str]:

        return cls._roles.get(

            role.lower(),

            set(),

        )

    # -------------------------------------------------

    @classmethod
    def role_exists(
        cls,
        role: str,
    ) -> bool:

        return role.lower() in cls._roles

    # -------------------------------------------------

    @classmethod
    def all_roles(cls) -> List[str]:

        return sorted(

            cls._roles.keys()

        )

    # -------------------------------------------------

    @classmethod
    def add_permission(
        cls,
        permission: str,
    ):

        cls._permissions.add(permission)

    # -------------------------------------------------

    @classmethod
    def add_role(

        cls,

        role: str,

        permissions: Set[str],

    ):

        cls.validate(

            list(permissions)

        )

        cls._roles[

            role.lower()

        ] = permissions

    # -------------------------------------------------

    @classmethod
    def has_permission(

        cls,

        role: str,

        permission: str,

    ) -> bool:

        return (

            permission

            in cls.role_permissions(role)

        )

    # -------------------------------------------------

    @classmethod
    def modules(cls) -> Dict[str, List[str]]:

        modules: Dict[str, List[str]] = {}

        for permission in cls.permissions():

            module = permission.split(":")[0]

            modules.setdefault(

                module,

                [],

            ).append(permission)

        return modules

    # -------------------------------------------------

    @classmethod
    def export(cls) -> dict:

        return {

            "roles": {

                role: sorted(list(perms))

                for role, perms

                in cls._roles.items()

            },

            "permissions": cls.permissions(),

        }

    # -------------------------------------------------

    @classmethod
    def statistics(cls):

        return {

            "total_permissions":

                len(cls._permissions),

            "total_roles":

                len(cls._roles),

            "modules":

                len(cls.modules()),

        }