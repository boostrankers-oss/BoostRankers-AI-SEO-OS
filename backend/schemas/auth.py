from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


# ==========================================================
# Login
# ==========================================================

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    remember_me: bool = False


# ==========================================================
# Register
# ==========================================================

class RegisterRequest(BaseModel):
    first_name: str = Field(..., min_length=2, max_length=100)
    last_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr

    password: str = Field(
        ...,
        min_length=12,
        max_length=72,
    )

    confirm_password: str
    company_name: str | None = None

    @field_validator("password")
    @classmethod
    def validate_password_bytes(cls, value: str) -> str:
        """bcrypt supports a maximum of 72 UTF-8 bytes."""
        if len(value.encode("utf-8")) > 72:
            raise ValueError(
                "Password must be 72 bytes or fewer. "
                "Please choose a shorter password."
            )

        return value

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, value: str, info):
        password = info.data.get("password")

        if password and value != password:
            raise ValueError("Passwords do not match.")

        return value

# ==========================================================
# Forgot Password
# ==========================================================

class ForgotPasswordRequest(BaseModel):
    email: EmailStr


# ==========================================================
# Reset Password
# ==========================================================

class ResetPasswordRequest(BaseModel):
    token: str
    password: str = Field(..., min_length=12)
    confirm_password: str

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, value: str, info):
        password = info.data.get("password")
        if password and value != password:
            raise ValueError("Passwords do not match.")
        return value


# ==========================================================
# Change Password
# ==========================================================

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=12)
    confirm_password: str

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, value: str, info):
        password = info.data.get("new_password")
        if password and value != password:
            raise ValueError("Passwords do not match.")
        return value


# ==========================================================
# Verify Email
# ==========================================================

class VerifyEmailRequest(BaseModel):
    token: str


# ==========================================================
# Refresh Token
# ==========================================================

class RefreshTokenRequest(BaseModel):
    refresh_token: str


# ==========================================================
# Logout
# ==========================================================

class LogoutRequest(BaseModel):
    refresh_token: str


# ==========================================================
# User Profile
# ==========================================================

class UserProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    company_id: str | None
    first_name: str
    last_name: str
    email: EmailStr
    role: str
    phone: str | None
    avatar_url: str | None
    is_active: bool
    is_verified: bool


# ==========================================================
# Generic Response
# ==========================================================

class MessageResponse(BaseModel):
    success: bool = True
    message: str