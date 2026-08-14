from __future__ import annotations

from datetime import UTC
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from models.audit_log import AuditLog
from models.company import Company
from models.permission import Permission
from models.role import Role
from models.role_permission import RolePermission
from models.user import User


class RoleService:
    """
    Enterprise Role Service

    Responsibilities

    • Role CRUD
    • Company Roles
    • Default Roles
    • Role Assignment
    • Role Cloning
    • Permission Mapping
    • Validation
    • Audit Logging
    """

    def __init__(
        self,
        db: Session,
    ):

        self.db = db

    # --------------------------------------------------
    # Internal Helpers
    # --------------------------------------------------

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

        self.db.add(

            AuditLog(

                action=action,

                user_id=performed_by,

                metadata=metadata or {},

                created_at=datetime.now(UTC),

            )

        )

    # --------------------------------------------------
    # Queries
    # --------------------------------------------------

    def get_role(
        self,
        role_id: int,
    ) -> Role | None:

        return self.db.get(
            Role,
            role_id,
        )

    def get_role_by_name(
        self,
        role_name: str,
    ) -> Role | None:

        return self.db.scalar(

            select(Role)

            .where(

                Role.name == role_name

            )

        )

    def role_exists(
        self,
        role_name: str,
    ) -> bool:

        return (

            self.get_role_by_name(
                role_name
            )

            is not None

        )

    def list_roles(self):

        return self.db.scalars(

            select(Role)

            .order_by(

                Role.name

            )

        ).all()

    def company_roles(
        self,
        company_id: int,
    ):

        return self.db.scalars(

            select(Role)

            .where(

                Role.company_id == company_id

            )

            .order_by(

                Role.name

            )

        ).all()

    # --------------------------------------------------
    # Validation
    # --------------------------------------------------

    def validate_role_name(
        self,
        role_name: str,
    ):

        role_name = role_name.strip()

        if len(role_name) < 3:

            raise HTTPException(

                status_code=400,

                detail="Role name too short.",

            )

        if len(role_name) > 100:

            raise HTTPException(

                status_code=400,

                detail="Role name too long.",

            )

        return role_name
        
            # --------------------------------------------------
    # Create Role
    # --------------------------------------------------

    def create_role(
        self,
        *,
        name: str,
        description: str | None = None,
        company_id: int | None = None,
        is_system: bool = False,
        performed_by: int | None = None,
    ) -> Role:

        name = self.validate_role_name(name)

        existing = self.db.scalar(

            select(Role).where(

                Role.name == name,

                Role.company_id == company_id,

            )

        )

        if existing:

            raise HTTPException(

                status_code=409,

                detail="Role already exists.",

            )

        if company_id is not None:

            company = self.db.get(

                Company,

                company_id,

            )

            if company is None:

                raise HTTPException(

                    status_code=404,

                    detail="Company not found.",

                )

        role = Role(

            name=name,

            description=description,

            company_id=company_id,

            is_system=is_system,

            is_active=True,

            created_at=datetime.now(UTC),

        )

        self.db.add(role)

        self._audit(

            action="role.create",

            performed_by=performed_by,

            metadata={

                "role": name,

                "company_id": company_id,

            },

        )

        self._commit()

        self.db.refresh(role)

        return role

    # --------------------------------------------------
    # Update Role
    # --------------------------------------------------

    def update_role(
        self,
        role_id: int,
        *,
        name: str | None = None,
        description: str | None = None,
        is_active: bool | None = None,
        performed_by: int | None = None,
    ) -> Role:

        role = self.get_role(role_id)

        if role is None:

            raise HTTPException(

                status_code=404,

                detail="Role not found.",

            )

        if getattr(role, "is_system", False):

            raise HTTPException(

                status_code=403,

                detail="System roles cannot be modified.",

            )

        if name:

            name = self.validate_role_name(name)

            duplicate = self.db.scalar(

                select(Role).where(

                    Role.name == name,

                    Role.company_id == role.company_id,

                    Role.id != role.id,

                )

            )

            if duplicate:

                raise HTTPException(

                    status_code=409,

                    detail="Role name already exists.",

                )

            role.name = name

        if description is not None:

            role.description = description

        if is_active is not None:

            role.is_active = is_active

        if hasattr(role, "updated_at"):

            role.updated_at = datetime.now(UTC)

        self._audit(

            action="role.update",

            performed_by=performed_by,

            metadata={

                "role_id": role.id,

            },

        )

        self._commit()

        self.db.refresh(role)

        return role

    # --------------------------------------------------
    # Delete Role
    # --------------------------------------------------

    def delete_role(
        self,
        role_id: int,
        *,
        force: bool = False,
        performed_by: int | None = None,
    ) -> bool:

        role = self.get_role(role_id)

        if role is None:

            raise HTTPException(

                status_code=404,

                detail="Role not found.",

            )

        if getattr(role, "is_system", False):

            raise HTTPException(

                status_code=403,

                detail="System roles cannot be deleted.",

            )

        users = self.db.scalars(

            select(User).where(

                User.role_id == role.id

            )

        ).all()

        if users:

            raise HTTPException(

                status_code=409,

                detail="Users are still assigned to this role.",

            )

        self.db.query(RolePermission).filter(

            RolePermission.role_id == role.id

        ).delete(

            synchronize_session=False,

        )

        if force:

            self.db.delete(role)

        else:

            role.is_active = False

            if hasattr(role, "deleted_at"):

                role.deleted_at = datetime.now(UTC)

        self._audit(

            action="role.delete",

            performed_by=performed_by,

            metadata={

                "role_id": role.id,

                "force": force,

            },

        )

        self._commit()

        return True
        
            # --------------------------------------------------
    # Clone Role
    # --------------------------------------------------

    def clone_role(
        self,
        source_role_id: int,
        *,
        new_name: str,
        company_id: int | None = None,
        performed_by: int | None = None,
    ) -> Role:

        source = self.get_role(source_role_id)

        if source is None:

            raise HTTPException(

                status_code=404,

                detail="Source role not found.",

            )

        new_name = self.validate_role_name(new_name)

        if self.role_exists(new_name):

            raise HTTPException(

                status_code=409,

                detail="Role already exists.",

            )

        cloned = Role(

            name=new_name,

            description=source.description,

            company_id=company_id,

            is_system=False,

            is_active=True,

            created_at=datetime.now(UTC),

        )

        self.db.add(cloned)

        self.db.flush()

        permissions = self.db.scalars(

            select(RolePermission).where(

                RolePermission.role_id == source.id

            )

        ).all()

        for permission in permissions:

            self.db.add(

                RolePermission(

                    role_id=cloned.id,

                    permission_id=permission.permission_id,

                    created_at=datetime.now(UTC),

                )

            )

        self._audit(

            action="role.clone",

            performed_by=performed_by,

            metadata={

                "source_role": source.name,

                "new_role": cloned.name,

            },

        )

        self._commit()

        self.db.refresh(cloned)

        return cloned

    # --------------------------------------------------
    # Assign Role To User
    # --------------------------------------------------

    def assign_role_to_user(
        self,
        *,
        user_id: int,
        role_id: int,
        performed_by: int | None = None,
    ) -> User:

        user = self.db.get(
            User,
            user_id,
        )

        if user is None:

            raise HTTPException(

                status_code=404,

                detail="User not found.",

            )

        role = self.get_role(role_id)

        if role is None:

            raise HTTPException(

                status_code=404,

                detail="Role not found.",

            )

        if (

            role.company_id is not None

            and

            user.company_id != role.company_id

        ):

            raise HTTPException(

                status_code=403,

                detail="Cross-company role assignment is not allowed.",

            )

        user.role_id = role.id

        if hasattr(user, "updated_at"):

            user.updated_at = datetime.now(UTC)

        self._audit(

            action="role.assign",

            performed_by=performed_by,

            metadata={

                "user_id": user.id,

                "role": role.name,

            },

        )

        self._commit()

        self.db.refresh(user)

        return user

    # --------------------------------------------------
    # Remove Role From User
    # --------------------------------------------------

    def remove_role_from_user(
        self,
        *,
        user_id: int,
        performed_by: int | None = None,
    ) -> User:

        user = self.db.get(

            User,

            user_id,

        )

        if user is None:

            raise HTTPException(

                status_code=404,

                detail="User not found.",

            )

        user.role_id = None

        if hasattr(user, "updated_at"):

            user.updated_at = datetime.now(UTC)

        self._audit(

            action="role.remove",

            performed_by=performed_by,

            metadata={

                "user_id": user.id,

            },

        )

        self._commit()

        self.db.refresh(user)

        return user

    # --------------------------------------------------
    # Copy Permissions
    # --------------------------------------------------

    def copy_role_permissions(
        self,
        *,
        source_role_id: int,
        target_role_id: int,
        performed_by: int | None = None,
    ):

        source = self.get_role(source_role_id)

        target = self.get_role(target_role_id)

        if source is None or target is None:

            raise HTTPException(

                status_code=404,

                detail="Role not found.",

            )

        self.db.query(

            RolePermission

        ).filter(

            RolePermission.role_id == target.id

        ).delete(

            synchronize_session=False,

        )

        permissions = self.db.scalars(

            select(RolePermission).where(

                RolePermission.role_id == source.id

            )

        ).all()

        for permission in permissions:

            self.db.add(

                RolePermission(

                    role_id=target.id,

                    permission_id=permission.permission_id,

                    created_at=datetime.now(UTC),

                )

            )

        self._audit(

            action="role.copy_permissions",

            performed_by=performed_by,

            metadata={

                "source": source.name,

                "target": target.name,

            },

        )

        self._commit()

    # --------------------------------------------------
    # Set Default Role
    # --------------------------------------------------

    def set_default_role(
        self,
        company_id: int,
        role_id: int,
    ) -> Role:

        role = self.get_role(role_id)

        if role is None:

            raise HTTPException(

                status_code=404,

                detail="Role not found.",

            )

        self.db.query(Role).filter(

            Role.company_id == company_id

        ).update(

            {

                "is_default": False

            }

        )

        role.is_default = True

        self._commit()

        self.db.refresh(role)

        return role

    # --------------------------------------------------
    # Bulk Assign Role
    # --------------------------------------------------

    def bulk_assign_role(
        self,
        *,
        role_id: int,
        user_ids: list[int],
        performed_by: int | None = None,
    ) -> dict:

        updated = 0

        skipped = 0

        role = self.get_role(role_id)

        if role is None:

            raise HTTPException(

                status_code=404,

                detail="Role not found.",

            )

        for user_id in user_ids:

            user = self.db.get(

                User,

                user_id,

            )

            if user is None:

                skipped += 1

                continue

            if (

                role.company_id is not None

                and

                role.company_id != user.company_id

            ):

                skipped += 1

                continue

            user.role_id = role.id

            updated += 1

        self._audit(

            action="role.bulk_assign",

            performed_by=performed_by,

            metadata={

                "role": role.name,

                "updated": updated,

                "skipped": skipped,

            },

        )

        self._commit()

        return {

            "updated": updated,

            "skipped": skipped,

        }
        
            # --------------------------------------------------
    # Role Hierarchy
    # --------------------------------------------------

    def role_level(
        self,
        role: Role,
    ) -> int:
        """
        Returns the hierarchy level of a role.

        Higher number = higher privilege.
        """

        hierarchy = {

            "client": 10,

            "content_writer": 20,

            "seo_specialist": 30,

            "manager": 40,

            "agency_owner": 50,

            "super_admin": 100,

        }

        return hierarchy.get(

            role.name.lower(),

            0,

        )

    # --------------------------------------------------

    def can_manage_role(
        self,
        actor_role: Role,
        target_role: Role,
    ) -> bool:

        return (

            self.role_level(actor_role)

            >

            self.role_level(target_role)

        )

    # --------------------------------------------------

    def can_assign_role(
        self,
        actor_role: Role,
        target_role: Role,
    ) -> bool:

        return self.can_manage_role(

            actor_role,

            target_role,

        )

    # --------------------------------------------------
    # Effective Permissions
    # --------------------------------------------------

    def effective_permissions(
        self,
        role_id: int,
    ) -> list[str]:

        permissions = self.db.scalars(

            select(Permission)

            .join(

                RolePermission,

                Permission.id
                ==
                RolePermission.permission_id,

            )

            .where(

                RolePermission.role_id
                ==
                role_id

            )

            .order_by(

                Permission.module,

                Permission.action,

            )

        ).all()

        return [

            permission.name

            for permission

            in permissions

        ]

    # --------------------------------------------------
    # Company Templates
    # --------------------------------------------------

    def create_company_templates(
        self,
        company_id: int,
    ):

        templates = [

            (
                "Manager",
                "Company Manager",
            ),

            (
                "SEO Specialist",
                "SEO Executive",
            ),

            (
                "Content Writer",
                "Content Team",
            ),

            (
                "Client",
                "Client Portal",
            ),

        ]

        created = []

        for name, description in templates:

            exists = self.db.scalar(

                select(Role).where(

                    Role.company_id == company_id,

                    Role.name == name,

                )

            )

            if exists:

                continue

            role = Role(

                name=name,

                description=description,

                company_id=company_id,

                is_system=False,

                is_active=True,

                created_at=datetime.now(UTC),

            )

            self.db.add(role)

            self.db.flush()

            created.append(role)

        self._commit()

        return created

    # --------------------------------------------------
    # Role Summary
    # --------------------------------------------------

    def role_summary(
        self,
        role_id: int,
    ) -> dict:

        role = self.get_role(role_id)

        if role is None:

            raise HTTPException(

                status_code=404,

                detail="Role not found.",

            )

        users = self.db.query(User).filter(

            User.role_id == role.id

        ).count()

        permissions = self.db.query(

            RolePermission

        ).filter(

            RolePermission.role_id == role.id

        ).count()

        return {

            "id": role.id,

            "name": role.name,

            "description": role.description,

            "users": users,

            "permissions": permissions,

            "company_id": role.company_id,

            "system": role.is_system,

            "active": role.is_active,

        }

    # --------------------------------------------------
    # Role Statistics
    # --------------------------------------------------

    def statistics(self):

        total_roles = self.db.query(

            Role

        ).count()

        system_roles = self.db.query(

            Role

        ).filter(

            Role.is_system.is_(True)

        ).count()

        custom_roles = self.db.query(

            Role

        ).filter(

            Role.is_system.is_(False)

        ).count()

        active_roles = self.db.query(

            Role

        ).filter(

            Role.is_active.is_(True)

        ).count()

        return {

            "total_roles": total_roles,

            "system_roles": system_roles,

            "custom_roles": custom_roles,

            "active_roles": active_roles,

        }

    # --------------------------------------------------
    # Synchronization
    # --------------------------------------------------

    def synchronize_defaults(self):

        """
        Ensures built-in roles exist.

        Called during application startup.
        """

        defaults = [

            "super_admin",

            "agency_owner",

            "manager",

            "seo_specialist",

            "content_writer",

            "client",

        ]

        created = 0

        for role_name in defaults:

            exists = self.get_role_by_name(

                role_name

            )

            if exists:

                continue

            role = Role(

                name=role_name,

                description=role_name.replace(
                    "_",
                    " ",
                ).title(),

                is_system=True,

                is_active=True,

                created_at=datetime.now(UTC),

            )

            self.db.add(role)

            created += 1

        self._commit()

        return created
        
            # --------------------------------------------------
    # Export Roles
    # --------------------------------------------------

    def export_roles(self) -> list[dict]:
        """
        Export all roles with their permissions.
        Used by:
        - Admin UI
        - Backup
        - API
        """

        data = []

        roles = self.list_roles()

        for role in roles:

            data.append(

                {

                    "id": role.id,

                    "name": role.name,

                    "description": role.description,

                    "company_id": role.company_id,

                    "system": role.is_system,

                    "active": role.is_active,

                    "permissions": self.effective_permissions(
                        role.id
                    ),

                }

            )

        return data

    # --------------------------------------------------
    # Import Roles
    # --------------------------------------------------

    def import_roles(
        self,
        roles: list[dict],
        overwrite: bool = False,
    ):

        imported = 0

        skipped = 0

        for item in roles:

            existing = self.get_role_by_name(
                item["name"]
            )

            if existing:

                if overwrite:

                    existing.description = item.get(
                        "description"
                    )

                    existing.is_active = item.get(
                        "active",
                        True,
                    )

                    imported += 1

                else:

                    skipped += 1

                continue

            role = Role(

                name=item["name"],

                description=item.get(
                    "description"
                ),

                company_id=item.get(
                    "company_id"
                ),

                is_system=item.get(
                    "system",
                    False,
                ),

                is_active=item.get(
                    "active",
                    True,
                ),

                created_at=datetime.now(UTC),

            )

            self.db.add(role)

            imported += 1

        self._commit()

        return {

            "imported": imported,

            "skipped": skipped,

        }

    # --------------------------------------------------
    # Cache
    # --------------------------------------------------

    def invalidate_cache(
        self,
        role_id: int | None = None,
    ):

        """
        Placeholder for Redis cache.

        Future implementation:

        cache.delete(
            f"role:{role_id}"
        )
        """

        return None

    # --------------------------------------------------
    # Validation
    # --------------------------------------------------

    def validate_role(
        self,
        role: Role,
    ):

        if not role.name:

            raise HTTPException(

                status_code=400,

                detail="Role name missing.",

            )

        if not role.is_active:

            raise HTTPException(

                status_code=403,

                detail="Role is inactive.",

            )

        return True

    # --------------------------------------------------
    # Startup Initialization
    # --------------------------------------------------

    def initialize(self):

        """
        Executed during FastAPI startup.

        Ensures the RBAC subsystem
        is fully synchronized.
        """

        self.synchronize_defaults()

        self.invalidate_cache()

        return {

            "status": "ready",

            "roles": len(

                self.list_roles()

            ),

        }

    # --------------------------------------------------
    # Health Check
    # --------------------------------------------------

    def health(self):

        return {

            "service": "RoleService",

            "status": "healthy",

            "roles": len(

                self.list_roles()

            ),

            "timestamp": datetime.now(
                UTC
            ).isoformat(),

        }