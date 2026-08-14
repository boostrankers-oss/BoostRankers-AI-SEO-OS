from __future__ import annotations

from datetime import UTC
from datetime import datetime
from typing import Iterable

from fastapi import HTTPException
from sqlalchemy import delete
from sqlalchemy import select
from sqlalchemy.orm import Session

from models.permission import Permission
from models.role import Role
from models.role_permission import RolePermission
from models.audit_log import AuditLog

from permissions.registry import PermissionRegistry


class PermissionService:
    """
    Enterprise Permission Service

    Responsibilities

    • Permission synchronization
    • Role permission management
    • Permission validation
    • Permission lookup
    • Role lookup
    • Permission assignment
    • Permission revocation
    • Audit logging
    """

    def __init__(self, db: Session):

        self.db = db

    # -----------------------------------------------------
    # Internal Helpers
    # -----------------------------------------------------

    def _commit(self):

        try:

            self.db.commit()

        except Exception:

            self.db.rollback()

            raise

    def _audit(
        self,
        action: str,
        performed_by: int | None = None,
        metadata: dict | None = None,
    ):

        log = AuditLog(

            action=action,

            user_id=performed_by,

            metadata=metadata or {},

            created_at=datetime.now(UTC),

        )

        self.db.add(log)

    # -----------------------------------------------------
    # Permission Queries
    # -----------------------------------------------------

    def get_permission(
        self,
        permission_name: str,
    ) -> Permission | None:

        return self.db.scalar(

            select(Permission)

            .where(

                Permission.name == permission_name

            )

        )

    def list_permissions(self):

        return self.db.scalars(

            select(Permission)

            .order_by(

                Permission.module,

                Permission.name,

            )

        ).all()

    def permission_exists(
        self,
        permission_name: str,
    ) -> bool:

        return (

            self.get_permission(permission_name)

            is not None

        )

    # -----------------------------------------------------
    # Role Queries
    # -----------------------------------------------------

    def get_role(
        self,
        role_name: str,
    ) -> Role | None:

        return self.db.scalar(

            select(Role)

            .where(

                Role.name == role_name

            )

        )

    def list_roles(self):

        return self.db.scalars(

            select(Role)

            .order_by(Role.name)

        ).all()
        
            # -----------------------------------------------------
    # Synchronization
    # -----------------------------------------------------

    def sync_permissions(self) -> dict:
        """
        Synchronize the database with the
        application's permission registry.

        Returns:
            {
                "created": int,
                "updated": int,
                "removed": int
            }
        """

        registry_permissions = set(
            PermissionRegistry.permissions()
        )

        database_permissions = {

            permission.name: permission

            for permission

            in self.list_permissions()

        }

        created = 0
        updated = 0
        removed = 0

        # --------------------------------------------
        # Create Missing Permissions
        # --------------------------------------------

        for permission_name in sorted(registry_permissions):

            module, action = permission_name.split(":", 1)

            permission = database_permissions.get(
                permission_name
            )

            if permission is None:

                permission = Permission(

                    name=permission_name,

                    module=module,

                    action=action,

                    description=f"{module.title()} {action.title()}",

                    is_active=True,

                )

                self.db.add(permission)

                created += 1

                continue

            changed = False

            if permission.module != module:

                permission.module = module

                changed = True

            if permission.action != action:

                permission.action = action

                changed = True

            if not permission.is_active:

                permission.is_active = True

                changed = True

            if changed:

                updated += 1

        # --------------------------------------------
        # Remove Obsolete Permissions
        # --------------------------------------------

        obsolete = [

            permission

            for permission

            in database_permissions.values()

            if permission.name not in registry_permissions

        ]

        for permission in obsolete:

            self.db.execute(

                delete(RolePermission).where(

                    RolePermission.permission_id

                    == permission.id

                )

            )

            self.db.delete(permission)

            removed += 1

        self._audit(

            action="permission.sync",

            metadata={

                "created": created,

                "updated": updated,

                "removed": removed,

            },

        )

        self._commit()

        return {

            "created": created,

            "updated": updated,

            "removed": removed,

        }

    # -----------------------------------------------------
    # Registry Validation
    # -----------------------------------------------------

    def validate_registry(self):

        registry = PermissionRegistry.permissions()

        duplicates = [

            permission

            for permission

            in registry

            if registry.count(permission) > 1

        ]

        if duplicates:

            raise RuntimeError(

                f"Duplicate permissions detected: {duplicates}"

            )

        return True

    # -----------------------------------------------------
    # Permission Creation
    # -----------------------------------------------------

    def create_permission(

        self,

        name: str,

        description: str | None = None,

    ) -> Permission:

        if self.permission_exists(name):

            raise HTTPException(

                status_code=409,

                detail="Permission already exists.",

            )

        if ":" not in name:

            raise HTTPException(

                status_code=400,

                detail="Permission format must be module:action",

            )

        module, action = name.split(":", 1)

        permission = Permission(

            name=name,

            module=module,

            action=action,

            description=description,

            is_active=True,

        )

        self.db.add(permission)

        self._audit(

            action="permission.create",

            metadata={

                "permission": name,

            },

        )

        self._commit()

        self.db.refresh(permission)

        return permission

    # -----------------------------------------------------
    # Permission Delete
    # -----------------------------------------------------

    def delete_permission(
        self,
        permission_id: int,
    ):

        permission = self.db.get(
            Permission,
            permission_id,
        )

        if permission is None:

            raise HTTPException(

                status_code=404,

                detail="Permission not found.",

            )

        self.db.execute(

            delete(RolePermission).where(

                RolePermission.permission_id

                == permission.id

            )

        )

        self.db.delete(permission)

        self._audit(

            action="permission.delete",

            metadata={

                "permission": permission.name,

            },

        )

        self._commit()

        return True
        
            # -----------------------------------------------------
    # Role Permission Assignment
    # -----------------------------------------------------

    def assign_permission_to_role(
        self,
        role_id: int,
        permission_id: int,
        performed_by: int | None = None,
    ) -> RolePermission:

        role = self.db.get(Role, role_id)

        if role is None:

            raise HTTPException(
                status_code=404,
                detail="Role not found.",
            )

        permission = self.db.get(
            Permission,
            permission_id,
        )

        if permission is None:

            raise HTTPException(
                status_code=404,
                detail="Permission not found.",
            )

        existing = self.db.scalar(

            select(RolePermission).where(

                RolePermission.role_id == role_id,

                RolePermission.permission_id == permission_id,

            )

        )

        if existing:

            return existing

        role_permission = RolePermission(

            role_id=role_id,

            permission_id=permission_id,

            created_at=datetime.now(UTC),

        )

        self.db.add(role_permission)

        self._audit(

            action="permission.assign",

            performed_by=performed_by,

            metadata={

                "role": role.name,

                "permission": permission.name,

            },

        )

        self._commit()

        self.db.refresh(role_permission)

        return role_permission

    # -----------------------------------------------------

    def remove_permission_from_role(
        self,
        role_id: int,
        permission_id: int,
        performed_by: int | None = None,
    ) -> bool:

        mapping = self.db.scalar(

            select(RolePermission).where(

                RolePermission.role_id == role_id,

                RolePermission.permission_id == permission_id,

            )

        )

        if mapping is None:

            return False

        permission = self.db.get(
            Permission,
            permission_id,
        )

        role = self.db.get(
            Role,
            role_id,
        )

        self.db.delete(mapping)

        self._audit(

            action="permission.revoke",

            performed_by=performed_by,

            metadata={

                "role": role.name if role else role_id,

                "permission": permission.name if permission else permission_id,

            },

        )

        self._commit()

        return True

    # -----------------------------------------------------

    def replace_role_permissions(
        self,
        role_id: int,
        permission_ids: Iterable[int],
        performed_by: int | None = None,
    ):

        role = self.db.get(
            Role,
            role_id,
        )

        if role is None:

            raise HTTPException(

                status_code=404,

                detail="Role not found.",

            )

        self.db.execute(

            delete(RolePermission).where(

                RolePermission.role_id == role_id

            )

        )

        permission_ids = set(permission_ids)

        for permission_id in permission_ids:

            permission = self.db.get(

                Permission,

                permission_id,

            )

            if permission is None:

                continue

            self.db.add(

                RolePermission(

                    role_id=role_id,

                    permission_id=permission.id,

                    created_at=datetime.now(UTC),

                )

            )

        self._audit(

            action="permission.replace",

            performed_by=performed_by,

            metadata={

                "role": role.name,

                "permissions": len(permission_ids),

            },

        )

        self._commit()

    # -----------------------------------------------------

    def get_role_permissions(
        self,
        role_id: int,
    ) -> list[Permission]:

        permissions = self.db.scalars(

            select(Permission)

            .join(

                RolePermission,

                Permission.id

                == RolePermission.permission_id,

            )

            .where(

                RolePermission.role_id == role_id

            )

            .order_by(

                Permission.module,

                Permission.action,

            )

        ).all()

        return permissions

    # -----------------------------------------------------

    def role_has_permission(
        self,
        role_id: int,
        permission_name: str,
    ) -> bool:

        permission = self.db.scalar(

            select(Permission).where(

                Permission.name == permission_name

            )

        )

        if permission is None:

            return False

        exists = self.db.scalar(

            select(RolePermission).where(

                RolePermission.role_id == role_id,

                RolePermission.permission_id == permission.id,

            )

        )

        return exists is not None

    # -----------------------------------------------------

    def bulk_assign_permissions(
        self,
        role_id: int,
        permission_ids: Iterable[int],
        performed_by: int | None = None,
    ):

        assigned = []

        skipped = []

        for permission_id in permission_ids:

            mapping = self.db.scalar(

                select(RolePermission).where(

                    RolePermission.role_id == role_id,

                    RolePermission.permission_id == permission_id,

                )

            )

            if mapping:

                skipped.append(permission_id)

                continue

            self.db.add(

                RolePermission(

                    role_id=role_id,

                    permission_id=permission_id,

                    created_at=datetime.now(UTC),

                )

            )

            assigned.append(permission_id)

        self._audit(

            action="permission.bulk_assign",

            performed_by=performed_by,

            metadata={

                "role_id": role_id,

                "assigned": assigned,

                "skipped": skipped,

            },

        )

        self._commit()

        return {

            "assigned": assigned,

            "skipped": skipped,

        }
        
            # -----------------------------------------------------
    # User Effective Permissions
    # -----------------------------------------------------

    def get_effective_permissions(
        self,
        user,
    ) -> set[str]:
        """
        Returns the effective permissions for a user.

        Priority:

        1. Direct User Permissions
        2. Role Permissions
        """

        permissions = set()

        role = getattr(user, "role", None)

        if role is not None:

            role_permissions = self.get_role_permissions(
                role.id
            )

            permissions.update(

                permission.name

                for permission

                in role_permissions

            )

        direct_permissions = getattr(
            user,
            "permissions",
            None,
        )

        if direct_permissions:

            permissions.update(

                permission.name

                if hasattr(permission, "name")

                else str(permission)

                for permission

                in direct_permissions

            )

        return permissions

    # -----------------------------------------------------

    def user_has_permission(
        self,
        user,
        permission: str,
    ) -> bool:

        return (

            permission

            in self.get_effective_permissions(user)

        )

    # -----------------------------------------------------

    def invalidate_permission_cache(
        self,
        role_id: int | None = None,
    ) -> None:
        """
        Placeholder for Redis / Memory cache.

        Future implementation:

        cache.delete(f"role:{role_id}")
        """

        return None

    # -----------------------------------------------------

    def permission_matrix(self):

        matrix = {}

        roles = self.list_roles()

        for role in roles:

            matrix[role.name] = sorted(

                permission.name

                for permission

                in self.get_role_permissions(
                    role.id
                )

            )

        return matrix

    # -----------------------------------------------------

    def export_permissions(self):

        permissions = self.list_permissions()

        grouped = {}

        for permission in permissions:

            grouped.setdefault(

                permission.module,

                [],

            ).append(

                {

                    "id": permission.id,

                    "name": permission.name,

                    "action": permission.action,

                    "description": permission.description,

                }

            )

        return grouped

    # -----------------------------------------------------

    def statistics(self):

        total_permissions = len(

            self.list_permissions()

        )

        total_roles = len(

            self.list_roles()

        )

        assignments = self.db.scalar(

            select(

                RolePermission

            ).count()

        )

        return {

            "permissions": total_permissions,

            "roles": total_roles,

            "assignments": assignments or 0,

        }

    # -----------------------------------------------------

    def seed_default_roles(self):

        """
        Synchronize every default role
        with PermissionRegistry.
        """

        created = 0

        for role_name in PermissionRegistry.all_roles():

            role = self.get_role(role_name)

            if role is None:

                role = Role(

                    name=role_name,

                    description=role_name.replace(
                        "_",
                        " ",
                    ).title(),

                    is_active=True,

                )

                self.db.add(role)

                self.db.flush()

                created += 1

            registry_permissions = (

                PermissionRegistry.role_permissions(
                    role_name
                )
            )

            permission_ids = []

            for permission_name in registry_permissions:

                permission = self.get_permission(
                    permission_name
                )

                if permission:

                    permission_ids.append(
                        permission.id
                    )

            self.replace_role_permissions(

                role.id,

                permission_ids,

            )

        self._audit(

            action="roles.seed",

            metadata={

                "roles_created": created,

            },

        )

        self._commit()

        return created

    # -----------------------------------------------------

    def initialize(self):

        """
        Called once during application startup.
        """

        self.validate_registry()

        self.sync_permissions()

        self.seed_default_roles()

        return {

            "status": "ready",

            "permissions": len(

                self.list_permissions()

            ),

            "roles": len(

                self.list_roles()

            ),

        }