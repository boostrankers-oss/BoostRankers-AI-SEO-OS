from __future__ import annotations
from jose import JWTError

from datetime import UTC, datetime, timedelta
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from models.company import Company
from models.refresh_token import RefreshToken
from models.role import Role
from models.user import User

from core.security import (
    generate_password_reset_token,
    generate_email_verification_token,
    hash_password,
)

from models.audit_log import AuditLog

from schemas.auth import (
    LoginRequest,
    RegisterRequest,
)

from core.security import (
    hash_password,
    verify_password,
    validate_password_strength,
    generate_session_id,
)

from core.jwt import (
    create_access_token,
    create_refresh_token,
)

# Default role assigned to new users
DEFAULT_ROLE = "client"


class AuthService:
    """
    Authentication service.

    Responsible for:

    - User registration
    - Login
    - Logout
    - Refresh Tokens
    - Password Reset
    - Email Verification
    """

    def __init__(self, db: Session):
        self.db = db

    # ==========================================================
    # Private Helpers
    # ==========================================================

    def _find_user_by_email(self, email: str) -> Optional[User]:
        return self.db.scalar(
            select(User).where(User.email == email.lower())
        )

    def _find_company_by_name(
        self,
        company_name: str,
    ) -> Optional[Company]:

        return self.db.scalar(
            select(Company).where(
                Company.name == company_name
            )
        )

    def _find_role(
        self,
        role_name: str = DEFAULT_ROLE,
    ) -> Optional[Role]:

        return self.db.scalar(
            select(Role).where(
                Role.name == role_name
            )
        )

    def _create_company(
        self,
        company_name: str,
    ) -> Company:

        slug = (
            company_name.lower()
            .replace(" ", "-")
            .replace("_", "-")
        )

        company = Company(
            name=company_name,
            slug=slug,
            subscription_plan="free",
            subscription_status="trial",
            is_active=True,
        )

        self.db.add(company)
        self.db.flush()

        return company

    def _issue_tokens(
        self,
        user: User,
    ) -> dict:

        session_id = generate_session_id()

        access_token = create_access_token(
            user_id=user.id,
            email=user.email,
            company_id=user.company_id,
            role=user.role,
            permissions=[],
        )

        refresh_token = create_refresh_token(
            user_id=user.id,
            session_id=session_id,
        )

        refresh = RefreshToken(
            user_id=user.id,
            token=refresh_token,
            token_family=session_id,
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )

        self.db.add(refresh)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": 900,
        }

    def _update_last_login(
        self,
        user: User,
    ) -> None:

        user.last_login = datetime.now(UTC)
        user.failed_login_attempts = 0

    def _failed_login(
        self,
        user: User,
    ) -> None:

        user.failed_login_attempts += 1

        if user.failed_login_attempts >= 5:

            user.locked_until = (
                datetime.now(UTC)
                + timedelta(minutes=30)
            )

    def _check_locked(
        self,
        user: User,
    ) -> None:

        if (
            user.locked_until
            and user.locked_until > datetime.now(UTC)
        ):

            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=(
                    "Account temporarily locked."
                ),
            )

    def _validate_password(
        self,
        password: str,
    ) -> None:

        result = validate_password_strength(
            password
        )

        if not result.valid:

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.message,
            )

    def _commit(self):

        self.db.commit()

    def _rollback(self):

        self.db.rollback()
        
            # ==========================================================
    # Register
    # ==========================================================

    def register(
        self,
        data: RegisterRequest,
    ) -> dict:
        """
        Register a new user.

        Flow

        1. Validate password
        2. Check email uniqueness
        3. Create company (optional)
        4. Assign default role
        5. Hash password
        6. Create user
        7. Generate JWT tokens
        8. Commit transaction
        """

        try:

            # --------------------------------------------
            # Password Validation
            # --------------------------------------------

            self._validate_password(data.password)

            # --------------------------------------------
            # Email Already Exists
            # --------------------------------------------

            existing_user = self._find_user_by_email(
                data.email
            )

            if existing_user:

                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Email already registered.",
                )

            # --------------------------------------------
            # Company
            # --------------------------------------------

            company = None

            if data.company_name:

                company = self._find_company_by_name(
                    data.company_name
                )

                if company is None:

                    company = self._create_company(
                        data.company_name
                    )

            # --------------------------------------------
            # Role
            # --------------------------------------------

            role = self._find_role(DEFAULT_ROLE)

            # The roles table exists, but the default "client" seed is
            # missing in the current database.  User.role is retained as
            # the backward-compatible RBAC value and role_id is nullable,
            # so a new client can be registered safely without requiring
            # a manual database seed just to complete signup.
            role_name = role.name if role else DEFAULT_ROLE
            role_id = role.id if role else None

            # --------------------------------------------
            # Create User
            # --------------------------------------------

            user = User(

                first_name=data.first_name,

                last_name=data.last_name,

                email=data.email.lower(),

                hashed_password=hash_password(
                    data.password
                ),

                role=role_name,

                role_id=role_id,

                company_id=(
                    company.id
                    if company
                    else None
                ),

                is_active=True,

                is_verified=False,
            )

            self.db.add(user)

            self.db.flush()

            # --------------------------------------------
            # JWT
            # --------------------------------------------

            tokens = self._issue_tokens(
                user
            )

            self._commit()

            return {

                "success": True,

                "message":
                    "Registration successful.",

                "user": {

                    "id": user.id,

                    "first_name":
                        user.first_name,

                    "last_name":
                        user.last_name,

                    "email":
                        user.email,

                    "role":
                        user.role,

                    "company_id":
                        user.company_id,

                    "is_verified":
                        user.is_verified,
                },

                "tokens": tokens,
            }

        except HTTPException:

            self._rollback()

            raise

        except Exception as exc:

            self._rollback()

            raise HTTPException(

                status_code=500,

                detail=str(exc),
            )
            
            # ==========================================================
    # Login
    # ==========================================================

    def login(
        self,
        data: LoginRequest,
    ) -> dict:
        """
        Authenticate a user and issue JWT tokens.
        """

        try:
            # -------------------------------------------------
            # Find User
            # -------------------------------------------------

            user = self._find_user_by_email(
                data.email
            )

            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password.",
                )

            # -------------------------------------------------
            # Active Account
            # -------------------------------------------------

            if not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Account is disabled.",
                )

            # -------------------------------------------------
            # Locked Account
            # -------------------------------------------------

            self._check_locked(user)

            # -------------------------------------------------
            # Verify Password
            # -------------------------------------------------

            if not verify_password(
                data.password,
                user.hashed_password,
            ):
                self._failed_login(user)

                self._commit()

                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password.",
                )

            # -------------------------------------------------
            # Successful Login
            # -------------------------------------------------

            self._update_last_login(user)

            user.locked_until = None

            # -------------------------------------------------
            # Issue JWT Tokens
            # -------------------------------------------------

            tokens = self._issue_tokens(user)

            self._commit()

            return {
                "success": True,
                "message": "Login successful.",
                "user": {
                    "id": user.id,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "email": user.email,
                    "role": user.role,
                    "company_id": user.company_id,
                    "is_verified": user.is_verified,
                    "last_login": user.last_login,
                },
                "tokens": tokens,
            }

        except HTTPException:
            self._rollback()
            raise

        except Exception as exc:
            self._rollback()

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(exc),
            )
        
        # ==========================================================
        # Refresh Access Token
        # ==========================================================

def refresh(
    self,
    refresh_token: str,
) -> dict:
    """
    Refresh JWT tokens using refresh token rotation.

    Flow

    1. Verify JWT
    2. Check DB record
    3. Check revoked
    4. Check expired
    5. Load user
    6. Create new Access Token
    7. Rotate Refresh Token
    8. Revoke previous Refresh Token
    """

    try:

        # ---------------------------------------------
        # Verify JWT
        # ---------------------------------------------

        payload = verify_token(
            refresh_token,
            token_type="refresh",
        )

        user_id = payload["sub"]

        session_id = payload["sid"]

        # ---------------------------------------------
        # Database Lookup
        # ---------------------------------------------

        db_token = self.db.scalar(
            select(RefreshToken).where(
                RefreshToken.token == refresh_token
            )
        )

        if db_token is None:

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token not found.",
            )

        # ---------------------------------------------
        # Revoked
        # ---------------------------------------------

        if db_token.is_revoked:

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token revoked.",
            )

        # ---------------------------------------------
        # Expired
        # ---------------------------------------------

        if db_token.is_expired:

            db_token.revoke("expired")

            self._commit()

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token expired.",
            )

        # ---------------------------------------------
        # User
        # ---------------------------------------------

        user = self.db.get(
            User,
            user_id,
        )

        if user is None:

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )

        if not user.is_active:

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account disabled.",
            )

        # ---------------------------------------------
        # Rotate Token
        # ---------------------------------------------

        db_token.revoke(
            reason="rotation"
        )

        new_access = create_access_token(
            user_id=user.id,
            email=user.email,
            company_id=user.company_id,
            role=user.role,
            permissions=[],
        )

        new_refresh = create_refresh_token(
            user_id=user.id,
            session_id=session_id,
        )

        self.db.add(
            RefreshToken(
                user_id=user.id,
                token=new_refresh,
                token_family=db_token.token_family,
                device_name=db_token.device_name,
                device_type=db_token.device_type,
                browser=db_token.browser,
                operating_system=db_token.operating_system,
                ip_address=db_token.ip_address,
                user_agent=db_token.user_agent,
                location=db_token.location,
                expires_at=datetime.now(UTC)
                + timedelta(days=30),
            )
        )

        db_token.replaced_by_token = new_refresh

        db_token.last_used_at = datetime.now(UTC)

        self._commit()

        return {

            "success": True,

            "message": "Token refreshed.",

            "tokens": {

                "access_token": new_access,

                "refresh_token": new_refresh,

                "expires_in": 900,
            },
        }

    except JWTError:

        self._rollback()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token.",
        )

    except HTTPException:

        self._rollback()

        raise

    except Exception as exc:

        self._rollback()

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )
        
        # ==========================================================
# Logout Current Device
# ==========================================================

def logout(
    self,
    refresh_token: str,
) -> dict:
    """
    Logout the current device by revoking the supplied
    refresh token.
    """

    try:

        db_token = self.db.scalar(
            select(RefreshToken).where(
                RefreshToken.token == refresh_token
            )
        )

        if db_token is None:
            return {
                "success": True,
                "message": "Already logged out.",
            }

        if not db_token.is_revoked:
            db_token.revoke("user_logout")

        self._commit()

        return {
            "success": True,
            "message": "Logout successful.",
        }

    except HTTPException:
        self._rollback()
        raise

    except Exception as exc:
        self._rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )
        
        # ==========================================================
# Logout All Sessions
# ==========================================================

def logout_all_sessions(
    self,
    user_id: str,
) -> dict:
    """
    Revoke every refresh token belonging to a user.
    """

    try:

        tokens = self.db.scalars(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id,
                RefreshToken.is_revoked.is_(False),
            )
        ).all()

        count = 0

        for token in tokens:
            token.revoke("logout_all_devices")
            count += 1

        self._commit()

        return {
            "success": True,
            "message": "All sessions revoked.",
            "revoked_sessions": count,
        }

    except HTTPException:
        self._rollback()
        raise

    except Exception as exc:
        self._rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )
        
        # ==========================================================
# Forgot Password
# ==========================================================

def forgot_password(
    self,
    email: str,
) -> dict:
    """
    Generate a password reset token.

    Note:
    The same success message is always returned to prevent
    email enumeration attacks.
    """

    try:

        user = self._find_user_by_email(email)

        if user:

            reset_token = generate_password_reset_token()

            # TODO:
            # Persist a hashed reset token with an expiry
            # (e.g. 15–30 minutes) in a dedicated table or
            # user fields before sending the email.

            self.db.add(
                AuditLog(
                    user_id=user.id,
                    company_id=user.company_id,
                    module="authentication",
                    action="forgot_password",
                    success=True,
                    message="Password reset requested.",
                )
            )

            # TODO:
            # Send reset email asynchronously.
            # enqueue_email_job(user.email, reset_token)

            self._commit()

        return {
            "success": True,
            "message": (
                "If an account exists for that email, "
                "password reset instructions have been sent."
            ),
        }

    except Exception as exc:

        self._rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


# ==========================================================
# Reset Password
# ==========================================================

def reset_password(
    self,
    token: str,
    new_password: str,
) -> dict:
    """
    Reset a user's password.

    NOTE:
    Token lookup/validation must be implemented using a
    dedicated password reset table or hashed token store.
    """

    try:

        self._validate_password(new_password)

        # TODO:
        # Lookup hashed token
        # Verify expiry
        # Retrieve user

        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=(
                "Password reset token validation "
                "is not implemented yet."
            ),
        )

    except HTTPException:
        self._rollback()
        raise

    except Exception as exc:

        self._rollback()

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# ==========================================================
# Change Password
# ==========================================================

def change_password(
    self,
    user: User,
    current_password: str,
    new_password: str,
) -> dict:

    try:

        if not verify_password(
            current_password,
            user.hashed_password,
        ):

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Current password is incorrect.",
            )

        self._validate_password(new_password)

        user.hashed_password = hash_password(
            new_password
        )

        user.password_changed_at = datetime.now(UTC)

        self.db.add(
            AuditLog(
                user_id=user.id,
                company_id=user.company_id,
                module="authentication",
                action="change_password",
                success=True,
                message="Password changed successfully.",
            )
        )

        self._commit()

        return {
            "success": True,
            "message": "Password updated successfully.",
        }

    except HTTPException:

        self._rollback()
        raise

    except Exception as exc:

        self._rollback()

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# ==========================================================
# Verify Email
# ==========================================================

def verify_email(
    self,
    token: str,
) -> dict:
    """
    Verify a user's email.

    NOTE:
    This requires a persisted email verification token.
    """

    try:

        # TODO:
        # Lookup verification token
        # Verify expiry
        # Load user

        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=(
                "Email verification token "
                "validation is not implemented yet."
            ),
        )

    except HTTPException:
        self._rollback()
        raise

    except Exception as exc:

        self._rollback()

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )
        
        # ==========================================================
# Cleanup Expired Sessions
# ==========================================================

def cleanup_expired_sessions(self) -> int:

    expired = self.db.scalars(
        select(RefreshToken)
    ).all()

    removed = 0

    for token in expired:

        if token.is_expired:
            self.db.delete(token)
            removed += 1

    self._commit()

    return removed
    
    # ==========================================================
# Compatibility wrappers for existing routers
# ==========================================================

def register_user(db, user: RegisterRequest):
    """
    Compatibility wrapper for routers/auth.py.

    The signup endpoint now receives RegisterRequest directly, so
    first_name/last_name are never lost by an incompatible legacy
    UserCreate schema.
    """
    service = AuthService(db)
    return service.register(user)


def authenticate_user(db, email: str, password: str):
    """
    Compatibility wrapper for routers/auth.py
    """
    service = AuthService(db)

    request = LoginRequest(
        email=email,
        password=password,
    )

    return service.login(request)
