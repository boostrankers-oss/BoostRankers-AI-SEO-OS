from __future__ import annotations

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from sqlalchemy.orm import Session

from database.session import get_db
from core.dependencies import get_current_user

from models.user import User

from permissions.constants import Permission
from permissions.dependency import require_permission

from services.role_service import RoleService


router = APIRouter(

    prefix="/roles",

    tags=["Roles"],

)


def role_service(

    db: Session = Depends(get_db),

) -> RoleService:

    return RoleService(db)


# ==========================================================
# List Roles
# ==========================================================

@router.get(
    "",
    dependencies=[
        Depends(
            require_permission(
                Permission.ROLES_VIEW.value
            )
        )
    ],
)
async def list_roles(

    service: RoleService = Depends(
        role_service
    ),

):

    return service.list_roles()


# ==========================================================
# Role Statistics
# ==========================================================

@router.get(
    "/statistics",
    dependencies=[
        Depends(
            require_permission(
                Permission.ROLES_VIEW.value
            )
        )
    ],
)
async def role_statistics(

    service: RoleService = Depends(
        role_service
    ),

):

    return service.statistics()


# ==========================================================
# Export Roles
# ==========================================================

@router.get(
    "/export",
    dependencies=[
        Depends(
            require_permission(
                Permission.ROLES_VIEW.value
            )
        )
    ],
)
async def export_roles(

    service: RoleService = Depends(
        role_service
    ),

):

    return service.export_roles()


# ==========================================================
# Health
# ==========================================================

@router.get(
    "/health",
)
async def role_health(

    service: RoleService = Depends(
        role_service
    ),

):

    return service.health()


# ==========================================================
# Initialization
# ==========================================================

@router.post(
    "/initialize",
    dependencies=[
        Depends(
            require_permission(
                Permission.SYSTEM_ADMIN.value
            )
        )
    ],
)
async def initialize_roles(

    current_user: User = Depends(
        get_current_user
    ),

    service: RoleService = Depends(
        role_service
    ),

):

    result = service.initialize()

    return {

        "success": True,

        "message": "Role system initialized.",

        "data": result,

    }


# ==========================================================
# Synchronize Default Roles
# ==========================================================

@router.post(
    "/sync",
    dependencies=[
        Depends(
            require_permission(
                Permission.SYSTEM_ADMIN.value
            )
        )
    ],
)
async def synchronize_roles(

    current_user: User = Depends(
        get_current_user
    ),

    service: RoleService = Depends(
        role_service
    ),

):

    result = service.synchronize_defaults()

    return {

        "success": True,

        "result": result,

    }
    
    from schemas.role import (
    RoleCreate,
    RoleUpdate,
)

from models.role import Role


# ==========================================================
# Get Role
# ==========================================================

@router.get(
    "/{role_id}",
    dependencies=[
        Depends(
            require_permission(
                Permission.ROLES_VIEW.value
            )
        )
    ],
)
async def get_role(
    role_id: int,
    service: RoleService = Depends(role_service),
):

    role = service.get_role(role_id)

    if role is None:

        raise HTTPException(
            status_code=404,
            detail="Role not found.",
        )

    return role


# ==========================================================
# Create Role
# ==========================================================

@router.post(
    "",
    dependencies=[
        Depends(
            require_permission(
                Permission.ROLES_CREATE.value
            )
        )
    ],
)
async def create_role(
    payload: RoleCreate,
    current_user: User = Depends(get_current_user),
    service: RoleService = Depends(role_service),
):

    role = service.create_role(

        name=payload.name,

        description=payload.description,

        company_id=payload.company_id,

        permissions=payload.permissions,

        created_by=current_user.id,

    )

    return {

        "success": True,

        "message": "Role created successfully.",

        "data": role,

    }


# ==========================================================
# Update Role
# ==========================================================

@router.put(
    "/{role_id}",
    dependencies=[
        Depends(
            require_permission(
                Permission.ROLES_EDIT.value
            )
        )
    ],
)
async def update_role(
    role_id: int,
    payload: RoleUpdate,
    current_user: User = Depends(get_current_user),
    service: RoleService = Depends(role_service),
):

    role = service.update_role(

        role_id=role_id,

        data=payload,

        updated_by=current_user.id,

    )

    return {

        "success": True,

        "message": "Role updated successfully.",

        "data": role,

    }


# ==========================================================
# Delete Role
# ==========================================================

@router.delete(
    "/{role_id}",
    dependencies=[
        Depends(
            require_permission(
                Permission.ROLES_DELETE.value
            )
        )
    ],
)
async def delete_role(
    role_id: int,
    current_user: User = Depends(get_current_user),
    service: RoleService = Depends(role_service),
):

    service.delete_role(

        role_id=role_id,

        deleted_by=current_user.id,

    )

    return {

        "success": True,

        "message": "Role deleted successfully.",

    }


# ==========================================================
# Restore Role
# ==========================================================

@router.post(
    "/{role_id}/restore",
    dependencies=[
        Depends(
            require_permission(
                Permission.ROLES_EDIT.value
            )
        )
    ],
)
async def restore_role(
    role_id: int,
    current_user: User = Depends(get_current_user),
    service: RoleService = Depends(role_service),
):

    role = service.restore_role(

        role_id=role_id,

        restored_by=current_user.id,

    )

    return {

        "success": True,

        "message": "Role restored successfully.",

        "data": role,

    }
    
    from schemas.role import (
    BulkRoleAssignment,
    CloneRoleRequest,
)


# ==========================================================
# Clone Role
# ==========================================================

@router.post(
    "/{role_id}/clone",
    dependencies=[
        Depends(
            require_permission(
                Permission.ROLES_CREATE.value
            )
        )
    ],
)
async def clone_role(
    role_id: int,
    payload: CloneRoleRequest,
    current_user: User = Depends(get_current_user),
    service: RoleService = Depends(role_service),
):

    role = service.clone_role(

        role_id=role_id,

        new_name=payload.name,

        description=payload.description,

        created_by=current_user.id,

    )

    return {

        "success": True,

        "message": "Role cloned successfully.",

        "data": role,

    }


# ==========================================================
# Assign Role To User
# ==========================================================

@router.post(
    "/assign",
    dependencies=[
        Depends(
            require_permission(
                Permission.ROLES_ASSIGN.value
            )
        )
    ],
)
async def assign_role(
    user_id: int,
    role_id: int,
    current_user: User = Depends(get_current_user),
    service: RoleService = Depends(role_service),
):

    result = service.assign_role_to_user(

        user_id=user_id,

        role_id=role_id,

        assigned_by=current_user.id,

    )

    return {

        "success": True,

        "data": result,

    }


# ==========================================================
# Remove Role From User
# ==========================================================

@router.delete(
    "/assign",
    dependencies=[
        Depends(
            require_permission(
                Permission.ROLES_ASSIGN.value
            )
        )
    ],
)
async def remove_role(
    user_id: int,
    role_id: int,
    current_user: User = Depends(get_current_user),
    service: RoleService = Depends(role_service),
):

    service.remove_role_from_user(

        user_id=user_id,

        role_id=role_id,

        removed_by=current_user.id,

    )

    return {

        "success": True,

        "message": "Role removed successfully.",

    }


# ==========================================================
# Bulk Assign Roles
# ==========================================================

@router.post(
    "/bulk-assign",
    dependencies=[
        Depends(
            require_permission(
                Permission.ROLES_ASSIGN.value
            )
        )
    ],
)
async def bulk_assign_roles(
    payload: BulkRoleAssignment,
    current_user: User = Depends(get_current_user),
    service: RoleService = Depends(role_service),
):

    result = service.bulk_assign_role(

        users=payload.user_ids,

        role_id=payload.role_id,

        assigned_by=current_user.id,

    )

    return {

        "success": True,

        "assigned": result,

    }


# ==========================================================
# Replace User Roles
# ==========================================================

@router.put(
    "/users/{user_id}",
    dependencies=[
        Depends(
            require_permission(
                Permission.ROLES_ASSIGN.value
            )
        )
    ],
)
async def replace_user_roles(
    user_id: int,
    role_ids: list[int],
    current_user: User = Depends(get_current_user),
    service: RoleService = Depends(role_service),
):

    result = service.replace_user_roles(

        user_id=user_id,

        role_ids=role_ids,

        updated_by=current_user.id,

    )

    return {

        "success": True,

        "data": result,

    }


# ==========================================================
# Effective Permissions
# ==========================================================

@router.get(
    "/{role_id}/permissions",
    dependencies=[
        Depends(
            require_permission(
                Permission.ROLES_VIEW.value
            )
        )
    ],
)
async def role_permissions(
    role_id: int,
    service: RoleService = Depends(role_service),
):

    permissions = service.effective_permissions(
        role_id
    )

    return {

        "role_id": role_id,

        "count": len(permissions),

        "permissions": permissions,

    }
    
    from fastapi import Query

from schemas.role import (
    RoleImportRequest,
)


# ==========================================================
# Company Roles
# ==========================================================

@router.get(
    "/company/{company_id}",
    dependencies=[
        Depends(
            require_permission(
                Permission.ROLES_VIEW.value
            )
        )
    ],
)
async def company_roles(
    company_id: int,
    service: RoleService = Depends(role_service),
):

    roles = service.company_roles(company_id)

    return {

        "company_id": company_id,

        "count": len(roles),

        "roles": roles,

    }


# ==========================================================
# Company Templates
# ==========================================================

@router.post(
    "/company/{company_id}/templates",
    dependencies=[
        Depends(
            require_permission(
                Permission.ROLES_CREATE.value
            )
        )
    ],
)
async def create_company_templates(
    company_id: int,
    current_user: User = Depends(get_current_user),
    service: RoleService = Depends(role_service),
):

    result = service.create_company_templates(
        company_id=company_id,
        created_by=current_user.id,
    )

    return {

        "success": True,

        "result": result,

    }


# ==========================================================
# Default Role
# ==========================================================

@router.post(
    "/{role_id}/default",
    dependencies=[
        Depends(
            require_permission(
                Permission.ROLES_EDIT.value
            )
        )
    ],
)
async def set_default_role(
    role_id: int,
    company_id: int,
    current_user: User = Depends(get_current_user),
    service: RoleService = Depends(role_service),
):

    service.set_default_role(

        role_id=role_id,

        company_id=company_id,

        updated_by=current_user.id,

    )

    return {

        "success": True,

        "message": "Default role updated.",

    }


# ==========================================================
# Role Hierarchy
# ==========================================================

@router.get(
    "/hierarchy",
    dependencies=[
        Depends(
            require_permission(
                Permission.ROLES_VIEW.value
            )
        )
    ],
)
async def role_hierarchy(
    service: RoleService = Depends(role_service),
):

    return {

        "hierarchy": service.role_summary(),

    }


# ==========================================================
# Import Roles
# ==========================================================

@router.post(
    "/import",
    dependencies=[
        Depends(
            require_permission(
                Permission.ROLES_CREATE.value
            )
        )
    ],
)
async def import_roles(
    payload: RoleImportRequest,
    service: RoleService = Depends(role_service),
):

    result = service.import_roles(

        roles=payload.roles,

        overwrite=payload.overwrite,

    )

    return {

        "success": True,

        "result": result,

    }


# ==========================================================
# Search Roles
# ==========================================================

@router.get(
    "/search",
    dependencies=[
        Depends(
            require_permission(
                Permission.ROLES_VIEW.value
            )
        )
    ],
)
async def search_roles(
    keyword: str | None = Query(default=None),
    company_id: int | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
    service: RoleService = Depends(role_service),
):

    roles = service.list_roles()

    if company_id is not None:

        roles = [

            role

            for role in roles

            if role.company_id == company_id

        ]

    if keyword:

        keyword = keyword.lower()

        roles = [

            role

            for role in roles

            if (

                keyword in role.name.lower()

                or

                keyword in (role.description or "").lower()

            )

        ]

    total = len(roles)

    roles = roles[skip:skip + limit]

    return {

        "total": total,

        "skip": skip,

        "limit": limit,

        "items": roles,

    }


# ==========================================================
# Validate Role
# ==========================================================

@router.post(
    "/{role_id}/validate",
    dependencies=[
        Depends(
            require_permission(
                Permission.ROLES_VIEW.value
            )
        )
    ],
)
async def validate_role(
    role_id: int,
    service: RoleService = Depends(role_service),
):

    role = service.get_role(role_id)

    if role is None:

        raise HTTPException(

            status_code=404,

            detail="Role not found.",

        )

    service.validate_role(role)

    return {

        "success": True,

        "message": "Role validation successful.",

    }


# ==========================================================
# API Diagnostics
# ==========================================================

@router.get("/info")
async def role_api_information():

    return {

        "service": "Role API",

        "version": "1.0.0",

        "authentication": "JWT",

        "authorization": "Enterprise RBAC",

    }
    
    from fastapi import Body

from schemas.role import (
    BulkRoleDeleteRequest,
    BulkRoleRestoreRequest,
)


# ==========================================================
# Bulk Delete Roles
# ==========================================================

@router.delete(
    "/bulk",
    dependencies=[
        Depends(
            require_permission(
                Permission.ROLES_DELETE.value
            )
        )
    ],
)
async def bulk_delete_roles(
    payload: BulkRoleDeleteRequest,
    current_user: User = Depends(get_current_user),
    service: RoleService = Depends(role_service),
):

    result = service.bulk_delete_roles(

        role_ids=payload.role_ids,

        deleted_by=current_user.id,

    )

    return {

        "success": True,

        "deleted": result,

    }


# ==========================================================
# Bulk Restore Roles
# ==========================================================

@router.post(
    "/bulk/restore",
    dependencies=[
        Depends(
            require_permission(
                Permission.ROLES_EDIT.value
            )
        )
    ],
)
async def bulk_restore_roles(
    payload: BulkRoleRestoreRequest,
    current_user: User = Depends(get_current_user),
    service: RoleService = Depends(role_service),
):

    result = service.bulk_restore_roles(

        role_ids=payload.role_ids,

        restored_by=current_user.id,

    )

    return {

        "success": True,

        "restored": result,

    }


# ==========================================================
# Refresh Role Cache
# ==========================================================

@router.post(
    "/cache/refresh",
    dependencies=[
        Depends(
            require_permission(
                Permission.SYSTEM_ADMIN.value
            )
        )
    ],
)
async def refresh_role_cache(
    service: RoleService = Depends(role_service),
):

    service.invalidate_cache()

    return {

        "success": True,

        "message": "Role cache refreshed.",

    }


# ==========================================================
# Readiness Check
# ==========================================================

@router.get("/ready")
async def readiness(
    service: RoleService = Depends(role_service),
):

    status = service.initialize()

    return {

        "ready": True,

        "status": status,

    }


# ==========================================================
# Role Summary
# ==========================================================

@router.get(
    "/summary",
    dependencies=[
        Depends(
            require_permission(
                Permission.ROLES_VIEW.value
            )
        )
    ],
)
async def role_summary(
    service: RoleService = Depends(role_service),
):

    return service.role_summary()


# ==========================================================
# Startup Synchronization
# ==========================================================

@router.post(
    "/startup-sync",
    dependencies=[
        Depends(
            require_permission(
                Permission.SYSTEM_ADMIN.value
            )
        )
    ],
)
async def startup_sync(
    service: RoleService = Depends(role_service),
):

    result = service.initialize()

    return {

        "success": True,

        "message": "Startup synchronization completed.",

        "result": result,

    }


# ==========================================================
# API Metadata
# ==========================================================

@router.get("/metadata")
async def metadata():

    return {

        "module": "roles",

        "version": "1.0.0",

        "authentication": "JWT",

        "authorization": "Enterprise RBAC",

        "supports": [

            "CRUD",

            "Role Assignment",

            "Role Hierarchy",

            "Company Isolation",

            "Import",

            "Export",

            "Bulk Operations",

            "Audit Logging",

            "Cache Refresh",

            "Health Checks",

        ],

    }