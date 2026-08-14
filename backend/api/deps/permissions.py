from fastapi import Depends
from fastapi import HTTPException
from fastapi import status

from api.deps.current_user import get_current_user
from models.user import User


def require_role(*roles):

    def dependency(
        current_user: User = Depends(get_current_user),
    ):

        if current_user.role not in roles:

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied.",
            )

        return current_user

    return dependency


def require_admin():

    return require_role(
        "admin",
        "super_admin",
    )


def require_staff():

    return require_role(
        "staff",
        "admin",
        "super_admin",
    )


def require_client():

    return require_role(
        "client",
        "staff",
        "admin",
        "super_admin",
    )