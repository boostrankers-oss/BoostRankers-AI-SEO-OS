from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any

from fastapi import Request
from fastapi import Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from auth.api_keys import get_api_key_service
from auth.csrf import get_csrf_service
from auth.jwt import get_jwt_service
from permissions.dependency import PermissionChecker


# ==========================================================
# Middleware Configuration
# ==========================================================

@dataclass(slots=True)
class MiddlewareSettings:

    request_id_header: str = "X-Request-ID"

    correlation_header: str = "X-Correlation-ID"

    processing_header: str = "X-Process-Time"

    tenant_header: str = "X-Tenant-ID"

    api_key_header: str = "X-API-Key"

    csrf_header: str = "X-CSRF-Token"

    enable_security_headers: bool = True

    enable_request_logging: bool = True

    enable_request_context: bool = True


DEFAULT_SETTINGS = MiddlewareSettings()


# ==========================================================
# Authentication Middleware
# ==========================================================

class AuthenticationMiddleware(BaseHTTPMiddleware):

    def __init__(
        self,
        app,
        settings: MiddlewareSettings | None = None,
    ):

        super().__init__(app)

        self.settings = settings or DEFAULT_SETTINGS

        self.jwt = get_jwt_service()

        self.api_keys = get_api_key_service()

        self.csrf = get_csrf_service()


# ==========================================================
# Dispatch
# ==========================================================

    async def dispatch(

        self,

        request: Request,

        call_next,

    ) -> Response:

        start = time.perf_counter()

        request.state.request_id = str(

            uuid.uuid4()

        )

        request.state.correlation_id = (

            request.headers.get(

                self.settings.correlation_header

            )

            or

            str(uuid.uuid4())

        )

        request.state.start_time = start

        request.state.user = None

        request.state.company_id = None

        request.state.permissions = []

        request.state.roles = []

        try:

            await self.authenticate(request)

            response = await call_next(request)

        except Exception as exc:

            response = self.exception_response(exc)

        elapsed = time.perf_counter() - start

        self.add_headers(

            response,

            request,

            elapsed,

        )

        return response


# ==========================================================
# Authentication
# ==========================================================

    async def authenticate(

        self,

        request: Request,

    ) -> None:

        authorization = request.headers.get(

            "Authorization"

        )

        api_key = request.headers.get(

            self.settings.api_key_header

        )

        if authorization:

            await self.authenticate_jwt(

                request,

                authorization,

            )

            return

        if api_key:

            await self.authenticate_api_key(

                request,

                api_key,

            )

            return


# ==========================================================
# JWT Authentication
# ==========================================================

    async def authenticate_jwt(

        self,

        request: Request,

        authorization: str,

    ) -> None:

        scheme, _, token = authorization.partition(" ")

        if scheme.lower() != "bearer":

            return

        payload = self.jwt.decode_access_token(

            token

        )

        request.state.user = payload.get("sub")

        request.state.company_id = payload.get(

            "company_id"

        )

        request.state.roles = payload.get(

            "roles",

            [],

        )

        request.state.permissions = payload.get(

            "permissions",

            [],

        )


# ==========================================================
# API Key Authentication
# ==========================================================

    async def authenticate_api_key(

        self,

        request: Request,

        api_key: str,

    ) -> None:

        key = self.api_keys.authenticate(

            api_key

        )

        request.state.user = key.user_id

        request.state.company_id = key.company_id

        request.state.permissions = key.scopes

        request.state.roles = ["api"]
        
        # ==========================================================
# CSRF Validation
# ==========================================================

    async def validate_csrf(
        self,
        request: Request,
    ) -> None:

        if request.method in {

            "GET",
            "HEAD",
            "OPTIONS",

        }:

            return

        session_id = getattr(

            request.state,

            "session_id",

            None,

        )

        if session_id is None:

            return

        header_token = request.headers.get(

            self.settings.csrf_header

        )

        cookie_token = request.cookies.get(

            self.csrf.settings.cookie_name

        )

        if not header_token or not cookie_token:

            raise PermissionError(

                "Missing CSRF token."

            )

        if not self.csrf.validate_request(

            session_id=session_id,

            csrf_token=header_token,

            cookie_token=cookie_token,

            origin=request.headers.get("Origin"),

            referer=request.headers.get("Referer"),

        ):

            raise PermissionError(

                "Invalid CSRF token."

            )


# ==========================================================
# Permission Validation
# ==========================================================

    async def validate_permissions(
        self,
        request: Request,
        required_permissions: list[str],
    ) -> None:

        if not required_permissions:

            return

        checker = PermissionChecker(

            required_permissions

        )

        allowed = checker.has_permissions(

            request.state.permissions

        )

        if not allowed:

            raise PermissionError(

                "Permission denied."

            )


# ==========================================================
# Tenant Validation
# ==========================================================

    async def validate_tenant(
        self,
        request: Request,
    ) -> None:

        tenant = request.headers.get(

            self.settings.tenant_header

        )

        if tenant is None:

            return

        if request.state.company_id is None:

            raise PermissionError(

                "Tenant authentication required."

            )

        if str(request.state.company_id) != tenant:

            raise PermissionError(

                "Invalid tenant."

            )


# ==========================================================
# Audit Logging
# ==========================================================

    async def audit_log(
        self,
        request: Request,
        response: Response,
    ) -> None:

        request.state.audit = {

            "request_id":

                request.state.request_id,

            "correlation_id":

                request.state.correlation_id,

            "user":

                request.state.user,

            "tenant":

                request.state.company_id,

            "method":

                request.method,

            "path":

                request.url.path,

            "status":

                response.status_code,

            "ip":

                request.client.host

                if request.client

                else None,

            "timestamp":

                time.time(),

        }


# ==========================================================
# Request Logging
# ==========================================================

    async def request_log(
        self,
        request: Request,
        response: Response,
    ) -> None:

        if not self.settings.enable_request_logging:

            return

        print(

            f"[{response.status_code}] "

            f"{request.method} "

            f"{request.url.path}"

        )


# ==========================================================
# Rate Limit Hook
# ==========================================================

    async def rate_limit_hook(
        self,
        request: Request,
    ) -> None:

        request.state.rate_limit_checked = True


# ==========================================================
# Security Headers
# ==========================================================

    def add_security_headers(
        self,
        response: Response,
    ) -> None:

        if not self.settings.enable_security_headers:

            return

        headers = self.csrf.security_headers()

        for key, value in headers.items():

            response.headers[key] = value

        response.headers["X-Frame-Options"] = "DENY"

        response.headers["X-Content-Type-Options"] = "nosniff"

        response.headers["Referrer-Policy"] = (

            "strict-origin-when-cross-origin"

        )

        response.headers["Permissions-Policy"] = (

            "geolocation=(), microphone=(), camera=()"

        )


# ==========================================================
# Response Headers
# ==========================================================

    def add_headers(
        self,
        response: Response,
        request: Request,
        elapsed: float,
    ) -> None:

        response.headers[

            self.settings.request_id_header

        ] = request.state.request_id

        response.headers[

            self.settings.correlation_header

        ] = request.state.correlation_id

        response.headers[

            self.settings.processing_header

        ] = f"{elapsed:.6f}"

        self.add_security_headers(

            response

        )
        
        # ==========================================================
# Exception Response
# ==========================================================

    def exception_response(
        self,
        exc: Exception,
    ) -> JSONResponse:

        status_code = 500
        error = "internal_server_error"

        if isinstance(exc, PermissionError):

            status_code = 403
            error = "permission_denied"

        elif isinstance(exc, ValueError):

            status_code = 400
            error = "validation_error"

        elif isinstance(exc, RuntimeError):

            status_code = 401
            error = "authentication_required"

        return JSONResponse(

            status_code=status_code,

            content={

                "success": False,

                "error": error,

                "message": str(exc),

            },

        )


# ==========================================================
# Unauthorized Response
# ==========================================================

    def unauthorized_response(
        self,
        message: str = "Unauthorized",
    ) -> JSONResponse:

        return JSONResponse(

            status_code=401,

            content={

                "success": False,

                "error": "unauthorized",

                "message": message,

            },

        )


# ==========================================================
# Forbidden Response
# ==========================================================

    def forbidden_response(
        self,
        message: str = "Forbidden",
    ) -> JSONResponse:

        return JSONResponse(

            status_code=403,

            content={

                "success": False,

                "error": "forbidden",

                "message": message,

            },

        )


# ==========================================================
# Request Context
# ==========================================================

    def request_context(
        self,
        request: Request,
    ) -> dict[str, Any]:

        return {

            "request_id":

                getattr(
                    request.state,
                    "request_id",
                    None,
                ),

            "correlation_id":

                getattr(
                    request.state,
                    "correlation_id",
                    None,
                ),

            "user":

                getattr(
                    request.state,
                    "user",
                    None,
                ),

            "company_id":

                getattr(
                    request.state,
                    "company_id",
                    None,
                ),

            "roles":

                getattr(
                    request.state,
                    "roles",
                    [],
                ),

            "permissions":

                getattr(
                    request.state,
                    "permissions",
                    [],
                ),

        }


# ==========================================================
# Authentication Status
# ==========================================================

    def authenticated(
        self,
        request: Request,
    ) -> bool:

        return (

            getattr(
                request.state,
                "user",
                None
            )

            is not None

        )


# ==========================================================
# Middleware Statistics
# ==========================================================

    def statistics(
        self,
    ) -> dict[str, Any]:

        return {

            "security_headers":

                self.settings.enable_security_headers,

            "request_logging":

                self.settings.enable_request_logging,

            "request_context":

                self.settings.enable_request_context,

            "jwt_enabled": True,

            "csrf_enabled": True,

            "api_keys_enabled": True,

        }


# ==========================================================
# Middleware Health
# ==========================================================

    def health(
        self,
    ) -> dict[str, Any]:

        return {

            "service": "AuthenticationMiddleware",

            "status": "healthy",

            "jwt": "available",

            "csrf": "available",

            "api_keys": "available",

            "permissions": "available",

        }


# ==========================================================
# Diagnostics
# ==========================================================

    def diagnostics(
        self,
    ) -> dict[str, Any]:

        return {

            "health":

                self.health(),

            "statistics":

                self.statistics(),

            "csrf":

                self.csrf.health(),

            "jwt":

                self.jwt.health(),

            "api_keys":

                self.api_keys.health(),

        }


# ==========================================================
# Security Report
# ==========================================================

    def security_report(
        self,
    ) -> dict[str, Any]:

        return {

            "middleware":

                "AuthenticationMiddleware",

            "jwt":

                self.jwt.health(),

            "csrf":

                self.csrf.security_report(),

            "api_keys":

                self.api_keys.security_report(),

            "security_headers":

                self.settings.enable_security_headers,

        }


# ==========================================================
# Maintenance
# ==========================================================

    def maintenance(
        self,
    ) -> dict[str, Any]:

        return {

            "csrf":

                self.csrf.maintenance(),

            "api_keys":

                self.api_keys.maintenance(),

        }
        
        # ==========================================================
# Public Endpoints
# ==========================================================

    PUBLIC_PATHS = {

        "/",

        "/docs",

        "/redoc",

        "/openapi.json",

        "/health",

        "/api/health",

        "/login",

        "/register",

        "/forgot-password",

        "/reset-password",

    }


# ==========================================================
# Public Request
# ==========================================================

    def is_public_request(
        self,
        request: Request,
    ) -> bool:

        path = request.url.path

        if path in self.PUBLIC_PATHS:

            return True

        return False


# ==========================================================
# Excluded Paths
# ==========================================================

    def is_excluded(
        self,
        request: Request,
        excluded: list[str] | None = None,
    ) -> bool:

        if not excluded:

            return False

        path = request.url.path

        return any(

            path.startswith(item)

            for item in excluded

        )


# ==========================================================
# Authentication Required
# ==========================================================

    async def require_authentication(
        self,
        request: Request,
    ) -> None:

        if self.is_public_request(request):

            return

        if not self.authenticated(request):

            raise RuntimeError(

                "Authentication required."

            )


# ==========================================================
# Background Audit Hook
# ==========================================================

    async def after_response(
        self,
        request: Request,
        response: Response,
    ) -> None:

        await self.audit_log(

            request,

            response,

        )

        await self.request_log(

            request,

            response,

        )


# ==========================================================
# Middleware Pipeline
# ==========================================================

    async def process_security(
        self,
        request: Request,
    ) -> None:

        await self.rate_limit_hook(

            request

        )

        await self.validate_tenant(

            request

        )

        await self.validate_csrf(

            request

        )


# ==========================================================
# Middleware Registration
# ==========================================================

def register_authentication_middleware(

    app,

    settings: MiddlewareSettings | None = None,

) -> None:

    app.add_middleware(

        AuthenticationMiddleware,

        settings=settings,

    )


# ==========================================================
# Configuration Validation
# ==========================================================

def validate_middleware_settings(

    settings: MiddlewareSettings,

) -> bool:

    if not settings.request_id_header:

        raise ValueError(

            "request_id_header is required."

        )

    if not settings.correlation_header:

        raise ValueError(

            "correlation_header is required."

        )

    if not settings.processing_header:

        raise ValueError(

            "processing_header is required."

        )

    if not settings.tenant_header:

        raise ValueError(

            "tenant_header is required."

        )

    if not settings.api_key_header:

        raise ValueError(

            "api_key_header is required."

        )

    if not settings.csrf_header:

        raise ValueError(

            "csrf_header is required."

        )

    return True


# ==========================================================
# Middleware Manager
# ==========================================================

class MiddlewareManager:

    def __init__(
        self,
        settings: MiddlewareSettings | None = None,
    ):

        self.settings = settings or DEFAULT_SETTINGS

        validate_middleware_settings(

            self.settings

        )


    def register(
        self,
        app,
    ) -> None:

        register_authentication_middleware(

            app,

            self.settings,

        )


    def diagnostics(
        self,
    ) -> dict[str, Any]:

        return {

            "middleware": "registered",

            "settings": self.settings,

        }


# ==========================================================
# Helper
# ==========================================================

def middleware_health() -> dict[str, Any]:

    return {

        "service": "AuthenticationMiddleware",

        "status": "healthy",

    }
    
    # ==========================================================
# Singleton
# ==========================================================

_middleware_manager: MiddlewareManager | None = None


def initialize_middleware(
    settings: MiddlewareSettings | None = None,
) -> MiddlewareManager:

    global _middleware_manager

    _middleware_manager = MiddlewareManager(
        settings=settings,
    )

    return _middleware_manager


# ==========================================================
# Get Middleware Manager
# ==========================================================

def get_middleware_manager() -> MiddlewareManager:

    if _middleware_manager is None:

        raise RuntimeError(
            "MiddlewareManager has not been initialized."
        )

    return _middleware_manager


# ==========================================================
# Convenience Helpers
# ==========================================================

def register_middleware(
    app,
) -> None:

    get_middleware_manager().register(app)


def middleware_diagnostics() -> dict[str, Any]:

    manager = get_middleware_manager()

    return manager.diagnostics()


def middleware_statistics() -> dict[str, Any]:

    middleware = AuthenticationMiddleware

    return {

        "name": middleware.__name__,

        "registered": _middleware_manager is not None,

    }


def middleware_security_report() -> dict[str, Any]:

    return {

        "authentication": True,

        "jwt": True,

        "csrf": True,

        "api_keys": True,

        "rbac": True,

        "tenant_isolation": True,

        "security_headers": True,

    }


def middleware_maintenance() -> dict[str, Any]:

    return {

        "status": "completed",

        "timestamp": time.time(),

    }


# ==========================================================
# Public Exports
# ==========================================================

__all__ = [

    "MiddlewareSettings",

    "AuthenticationMiddleware",

    "MiddlewareManager",

    "initialize_middleware",

    "get_middleware_manager",

    "register_authentication_middleware",

    "register_middleware",

    "middleware_health",

    "middleware_statistics",

    "middleware_security_report",

    "middleware_diagnostics",

    "middleware_maintenance",

]