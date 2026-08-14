from __future__ import annotations

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from sqlalchemy.orm import Session

from database.session import get_db

from core.dependencies import get_current_user

from models.user import User

from permissions.constants import Permission

from permissions.dependency import (
    require_permission,
)

from services.permission_service import PermissionService


router = APIRouter(

    prefix="/permissions",

    tags=["Permissions"],

)


def permission_service(
    db: Session = Depends(get_db),
) -> PermissionService:

    return PermissionService(db)


# ==========================================================
# List Permissions
# ==========================================================

@router.get(
    "",
    dependencies=[
        Depends(
            require_permission(
                Permission.PERMISSIONS_VIEW.value
            )
        )
    ],
)
async def list_permissions(

    service: PermissionService = Depends(
        permission_service
    ),

):

    return service.list_permissions()


# ==========================================================
# Export Permissions
# ==========================================================

@router.get(
    "/export",
    dependencies=[
        Depends(
            require_permission(
                Permission.PERMISSIONS_VIEW.value
            )
        )
    ],
)
async def export_permissions(

    service: PermissionService = Depends(
        permission_service
    ),

):

    return service.export_permissions()


# ==========================================================
# Permission Statistics
# ==========================================================

@router.get(
    "/statistics",
    dependencies=[
        Depends(
            require_permission(
                Permission.PERMISSIONS_VIEW.value
            )
        )
    ],
)
async def permission_statistics(

    service: PermissionService = Depends(
        permission_service
    ),

):

    return service.statistics()


# ==========================================================
# Permission Matrix
# ==========================================================

@router.get(
    "/matrix",
    dependencies=[
        Depends(
            require_permission(
                Permission.PERMISSIONS_VIEW.value
            )
        )
    ],
)
async def permission_matrix(

    service: PermissionService = Depends(
        permission_service
    ),

):

    return service.permission_matrix()


# ==========================================================
# Registry
# ==========================================================

@router.get(
    "/registry",
    dependencies=[
        Depends(
            require_permission(
                Permission.SYSTEM_ADMIN.value
            )
        )
    ],
)
async def registry(

    service: PermissionService = Depends(
        permission_service
    ),

):

    return {

        "permissions":

            service.list_permissions(),

        "statistics":

            service.statistics(),

    }
    
    from schemas.permission import (
    PermissionCreate,
    PermissionUpdate,
)


# ==========================================================
# Get Permission
# ==========================================================

@router.get(
    "/{permission_id}",
    dependencies=[
        Depends(
            require_permission(
                Permission.PERMISSIONS_VIEW.value
            )
        )
    ],
)
async def get_permission(

    permission_id: int,

    service: PermissionService = Depends(
        permission_service
    ),

):

    permission = service.db.get(

        backend.models.permission.Permission,

        permission_id,

    )

    if permission is None:

        raise HTTPException(

            status_code=404,

            detail="Permission not found.",

        )

    return permission


# ==========================================================
# Create Permission
# ==========================================================

@router.post(
    "",
    dependencies=[
        Depends(
            require_permission(
                Permission.PERMISSIONS_ASSIGN.value
            )
        )
    ],
)
async def create_permission(

    payload: PermissionCreate,

    current_user: User = Depends(
        get_current_user
    ),

    service: PermissionService = Depends(
        permission_service
    ),

):

    return service.create_permission(

        name=payload.name,

        description=payload.description,

    )


# ==========================================================
# Update Permission
# ==========================================================

@router.put(
    "/{permission_id}",
    dependencies=[
        Depends(
            require_permission(
                Permission.PERMISSIONS_ASSIGN.value
            )
        )
    ],
)
async def update_permission(

    permission_id: int,

    payload: PermissionUpdate,

    current_user: User = Depends(
        get_current_user
    ),

    service: PermissionService = Depends(
        permission_service
    ),

):

    permission = service.db.get(

        backend.models.permission.Permission,

        permission_id,

    )

    if permission is None:

        raise HTTPException(

            status_code=404,

            detail="Permission not found.",

        )

    if payload.description is not None:

        permission.description = payload.description

    if payload.is_active is not None:

        permission.is_active = payload.is_active

    service._audit(

        action="permission.update",

        performed_by=current_user.id,

        metadata={

            "permission": permission.name,

        },

    )

    service._commit()

    service.db.refresh(permission)

    return permission


# ==========================================================
# Delete Permission
# ==========================================================

@router.delete(
    "/{permission_id}",
    dependencies=[
        Depends(
            require_permission(
                Permission.PERMISSIONS_ASSIGN.value
            )
        )
    ],
)
async def delete_permission(

    permission_id: int,

    current_user: User = Depends(
        get_current_user
    ),

    service: PermissionService = Depends(
        permission_service
    ),

):

    service.delete_permission(

        permission_id

    )

    return {

        "success": True,

        "message": "Permission deleted.",

    }
    
    from permissions.registry import PermissionRegistry


# ==========================================================
# Synchronize Permission Registry
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
async def synchronize_permissions(

    current_user: User = Depends(
        get_current_user
    ),

    service: PermissionService = Depends(
        permission_service
    ),

):

    result = service.sync_permissions()

    return {

        "success": True,

        "message": "Permission registry synchronized successfully.",

        "result": result,

    }


# ==========================================================
# Initialize RBAC
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
async def initialize_permissions(

    current_user: User = Depends(
        get_current_user
    ),

    service: PermissionService = Depends(
        permission_service
    ),

):

    result = service.initialize()

    return {

        "success": True,

        "message": "Permission system initialized.",

        "data": result,

    }


# ==========================================================
# Seed Default Roles
# ==========================================================

@router.post(
    "/seed",
    dependencies=[
        Depends(
            require_permission(
                Permission.SYSTEM_ADMIN.value
            )
        )
    ],
)
async def seed_default_roles(

    current_user: User = Depends(
        get_current_user
    ),

    service: PermissionService = Depends(
        permission_service
    ),

):

    created = service.seed_default_roles()

    return {

        "success": True,

        "roles_created": created,

    }


# ==========================================================
# Permission Modules
# ==========================================================

@router.get(
    "/modules",
    dependencies=[
        Depends(
            require_permission(
                Permission.PERMISSIONS_VIEW.value
            )
        )
    ],
)
async def permission_modules():

    return PermissionRegistry.modules()


# ==========================================================
# Available Roles
# ==========================================================

@router.get(
    "/roles",
    dependencies=[
        Depends(
            require_permission(
                Permission.PERMISSIONS_VIEW.value
            )
        )
    ],
)
async def available_roles():

    return {

        "roles": PermissionRegistry.all_roles(),

    }


# ==========================================================
# Health
# ==========================================================

@router.get(
    "/health",
)
async def permission_health(

    service: PermissionService = Depends(
        permission_service
    ),

):

    return {

        "service": "Permission API",

        "status": "healthy",

        "permissions": len(

            service.list_permissions()

        ),

        "roles": len(

            service.list_roles()

        ),

    }


# ==========================================================
# Registry Validation
# ==========================================================

@router.post(
    "/validate",
    dependencies=[
        Depends(
            require_permission(
                Permission.SYSTEM_ADMIN.value
            )
        )
    ],
)
async def validate_registry(

    service: PermissionService = Depends(
        permission_service
    ),

):

    service.validate_registry()

    return {

        "success": True,

        "message": "Permission registry validation successful.",

    }
    
    from fastapi import Query

# ==========================================================
# Search Permissions
# ==========================================================

@router.get(
    "/search",
    dependencies=[
        Depends(
            require_permission(
                Permission.PERMISSIONS_VIEW.value
            )
        )
    ],
)
async def search_permissions(
    module: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
    service: PermissionService = Depends(permission_service),
):

    permissions = service.list_permissions()

    if module:

        permissions = [

            permission

            for permission in permissions

            if permission.module.lower() == module.lower()

        ]

    if keyword:

        keyword = keyword.lower()

        permissions = [

            permission

            for permission in permissions

            if (
                keyword in permission.name.lower()
                or
                (permission.description or "").lower().find(keyword) >= 0
            )

        ]

    total = len(permissions)

    permissions = permissions[skip: skip + limit]

    return {

        "total": total,

        "skip": skip,

        "limit": limit,

        "items": permissions,

    }


# ==========================================================
# Bulk Assign Permissions
# ==========================================================

@router.post(
    "/roles/{role_id}/assign",
    dependencies=[
        Depends(
            require_permission(
                Permission.PERMISSIONS_ASSIGN.value
            )
        )
    ],
)
async def bulk_assign_permissions(
    role_id: int,
    permission_ids: list[int],
    current_user: User = Depends(get_current_user),
    service: PermissionService = Depends(permission_service),
):

    result = service.bulk_assign_permissions(

        role_id=role_id,

        permission_ids=permission_ids,

        performed_by=current_user.id,

    )

    return {

        "success": True,

        "result": result,

    }


# ==========================================================
# Replace Role Permissions
# ==========================================================

@router.put(
    "/roles/{role_id}",
    dependencies=[
        Depends(
            require_permission(
                Permission.PERMISSIONS_ASSIGN.value
            )
        )
    ],
)
async def replace_role_permissions(
    role_id: int,
    permission_ids: list[int],
    current_user: User = Depends(get_current_user),
    service: PermissionService = Depends(permission_service),
):

    service.replace_role_permissions(

        role_id=role_id,

        permission_ids=permission_ids,

        performed_by=current_user.id,

    )

    return {

        "success": True,

        "message": "Role permissions updated.",

    }


# ==========================================================
# Get Role Permissions
# ==========================================================

@router.get(
    "/roles/{role_id}",
    dependencies=[
        Depends(
            require_permission(
                Permission.PERMISSIONS_VIEW.value
            )
        )
    ],
)
async def get_role_permissions(
    role_id: int,
    service: PermissionService = Depends(permission_service),
):

    permissions = service.get_role_permissions(
        role_id
    )

    return {

        "count": len(permissions),

        "items": permissions,

    }


# ==========================================================
# API Information
# ==========================================================

@router.get("/info")
async def permission_api_info():

    return {

        "name": "Permission API",

        "version": "1.0.0",

        "authentication": "JWT",

        "authorization": "RBAC",

        "service": "PermissionService",

    }