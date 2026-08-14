from fastapi import Depends

from api.deps.current_user import get_current_user
from models.company import Company
from models.user import User


def get_current_company(
    current_user: User = Depends(
        get_current_user
    ),
) -> Company:

    return current_user.company