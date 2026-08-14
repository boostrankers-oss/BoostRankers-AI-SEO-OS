from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from fastapi import status
from starlette.responses import JSONResponse
from utils.security import decode_token   # or from core.jwt import decode_token

class TenantIsolationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip auth for health check or login routes
        if request.url.path in ["/api/health", "/api/v1/auth/login", "/api/v1/auth/signup"]:
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            payload = decode_token(token)
            if payload:
                request.state.user_id = payload.get("sub")
                request.state.company_id = payload.get("company_id")   # ✅ extract company_id

        return await call_next(request)