from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class TokenResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int


class TokenPayload(BaseModel):
    sub: str
    email: str
    company_id: str | None = None
    role: str
    permissions: list[str] = []


class RefreshTokenPayload(BaseModel):
    sub: str
    sid: str


class LoginResponse(BaseModel):
    user: dict
    tokens: TokenResponse