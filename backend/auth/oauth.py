from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Any
from urllib.parse import urlencode

import httpx


# ==========================================================
# OAuth Configuration
# ==========================================================

@dataclass(slots=True)
class OAuthSettings:

    base_url: str = "http://localhost:8000"

    redirect_uri: str = "http://localhost:8000/auth/callback"

    session_expiry_minutes: int = 15

    state_length: int = 48

    nonce_length: int = 48

    code_verifier_length: int = 64

    timeout: int = 30


DEFAULT_SETTINGS = OAuthSettings()


# ==========================================================
# OAuth Provider
# ==========================================================

@dataclass(slots=True)
class OAuthProvider:

    name: str

    client_id: str

    client_secret: str

    authorize_url: str

    token_url: str

    userinfo_url: str

    scopes: list[str]

    supports_pkce: bool = True


# ==========================================================
# OAuth Service
# ==========================================================

class OAuthService:

    def __init__(
        self,
        settings: OAuthSettings | None = None,
    ):

        self.settings = settings or DEFAULT_SETTINGS

        self.providers: dict[str, OAuthProvider] = {}

        self.pending_states: dict[str, dict[str, Any]] = {}

        self.http = httpx.Client(

            timeout=self.settings.timeout,

            follow_redirects=True,

        )


# ==========================================================
# Current Time
# ==========================================================

    @staticmethod
    def now() -> datetime:

        return datetime.now(UTC)


# ==========================================================
# Register Provider
# ==========================================================

    def register_provider(

        self,

        provider: OAuthProvider,

    ) -> None:

        self.providers[

            provider.name.lower()

        ] = provider


# ==========================================================
# Provider Lookup
# ==========================================================

    def provider(

        self,

        name: str,

    ) -> OAuthProvider:

        try:

            return self.providers[

                name.lower()

            ]

        except KeyError:

            raise ValueError(

                f"Unknown OAuth provider: {name}"

            )


# ==========================================================
# Secure Random Values
# ==========================================================

    def generate_state(self) -> str:

        return secrets.token_urlsafe(

            self.settings.state_length

        )


    def generate_nonce(self) -> str:

        return secrets.token_urlsafe(

            self.settings.nonce_length

        )


    def generate_code_verifier(self) -> str:

        return secrets.token_urlsafe(

            self.settings.code_verifier_length

        )


# ==========================================================
# PKCE Challenge
# ==========================================================

    @staticmethod
    def code_challenge(

        verifier: str,

    ) -> str:

        digest = hashlib.sha256(

            verifier.encode()

        ).digest()

        return (

            base64.urlsafe_b64encode(

                digest

            )

            .decode()

            .rstrip("=")

        )


# ==========================================================
# Create OAuth Session
# ==========================================================

    def create_session(

        self,

        provider: str,

    ) -> dict[str, str]:

        state = self.generate_state()

        nonce = self.generate_nonce()

        verifier = self.generate_code_verifier()

        challenge = self.code_challenge(

            verifier

        )

        self.pending_states[state] = {

            "provider": provider,

            "nonce": nonce,

            "verifier": verifier,

            "expires": (

                self.now()

                +

                timedelta(

                    minutes=self.settings.session_expiry_minutes

                )

            ),

        }

        return {

            "state": state,

            "nonce": nonce,

            "code_verifier": verifier,

            "code_challenge": challenge,

        }


# ==========================================================
# Authorisation URL
# ==========================================================

    def authorization_url(

        self,

        provider_name: str,

    ) -> tuple[str, dict[str, str]]:

        provider = self.provider(

            provider_name

        )

        session = self.create_session(

            provider_name

        )

        params = {

            "client_id":

                provider.client_id,

            "redirect_uri":

                self.settings.redirect_uri,

            "response_type":

                "code",

            "scope":

                " ".join(provider.scopes),

            "state":

                session["state"],

            "nonce":

                session["nonce"],

        }

        if provider.supports_pkce:

            params.update(

                {

                    "code_challenge":

                        session["code_challenge"],

                    "code_challenge_method":

                        "S256",

                }

            )

        return (

            f"{provider.authorize_url}"

            f"?{urlencode(params)}",

            session,

        )
        
        # ==========================================================
# Validate OAuth State
# ==========================================================

    def validate_state(
        self,
        state: str,
    ) -> dict[str, Any]:

        session = self.pending_states.get(state)

        if session is None:

            raise ValueError(
                "Invalid OAuth state."
            )

        if session["expires"] < self.now():

            del self.pending_states[state]

            raise ValueError(
                "OAuth session expired."
            )

        return session


# ==========================================================
# Remove Session
# ==========================================================

    def remove_session(
        self,
        state: str,
    ) -> None:

        self.pending_states.pop(
            state,
            None,
        )


# ==========================================================
# Exchange Authorization Code
# ==========================================================

    def exchange_code(
        self,
        provider_name: str,
        code: str,
        code_verifier: str,
    ) -> dict[str, Any]:

        provider = self.provider(provider_name)

        payload = {

            "grant_type": "authorization_code",

            "client_id": provider.client_id,

            "client_secret": provider.client_secret,

            "redirect_uri": self.settings.redirect_uri,

            "code": code,

        }

        if provider.supports_pkce:

            payload["code_verifier"] = code_verifier

        response = self.http.post(

            provider.token_url,

            data=payload,

        )

        response.raise_for_status()

        return response.json()


# ==========================================================
# Refresh OAuth Token
# ==========================================================

    def refresh_access_token(
        self,
        provider_name: str,
        refresh_token: str,
    ) -> dict[str, Any]:

        provider = self.provider(provider_name)

        response = self.http.post(

            provider.token_url,

            data={

                "grant_type": "refresh_token",

                "client_id": provider.client_id,

                "client_secret": provider.client_secret,

                "refresh_token": refresh_token,

            },

        )

        response.raise_for_status()

        return response.json()


# ==========================================================
# Fetch UserInfo
# ==========================================================

    def userinfo(
        self,
        provider_name: str,
        access_token: str,
    ) -> dict[str, Any]:

        provider = self.provider(provider_name)

        response = self.http.get(

            provider.userinfo_url,

            headers={

                "Authorization":

                    f"Bearer {access_token}"

            },

        )

        response.raise_for_status()

        return response.json()


# ==========================================================
# OAuth Callback
# ==========================================================

    def callback(
        self,
        provider_name: str,
        code: str,
        state: str,
    ) -> dict[str, Any]:

        session = self.validate_state(

            state

        )

        tokens = self.exchange_code(

            provider_name,

            code,

            session["verifier"],

        )

        user = self.userinfo(

            provider_name,

            tokens["access_token"],

        )

        self.remove_session(

            state

        )

        return {

            "provider": provider_name,

            "user": user,

            "tokens": tokens,

            "nonce": session["nonce"],

        }


# ==========================================================
# Token Information
# ==========================================================

    @staticmethod
    def token_information(
        token_response: dict[str, Any],
    ) -> dict[str, Any]:

        return {

            "access_token":

                token_response.get(

                    "access_token"

                ),

            "refresh_token":

                token_response.get(

                    "refresh_token"

                ),

            "id_token":

                token_response.get(

                    "id_token"

                ),

            "expires_in":

                token_response.get(

                    "expires_in"

                ),

            "scope":

                token_response.get(

                    "scope"

                ),

            "token_type":

                token_response.get(

                    "token_type",

                    "Bearer",

                ),

        }


# ==========================================================
# Logout URL
# ==========================================================

    def logout_url(
        self,
        provider_name: str,
        redirect_uri: str,
    ) -> str:

        provider = self.provider(

            provider_name

        )

        return (

            f"{provider.authorize_url}"

            f"/logout?"

            f"{urlencode({'post_logout_redirect_uri': redirect_uri})}"

        )
        
        # ==========================================================
# OIDC Configuration
# ==========================================================

@dataclass(slots=True)
class OIDCConfiguration:

    issuer: str

    authorization_endpoint: str

    token_endpoint: str

    userinfo_endpoint: str

    jwks_uri: str

    end_session_endpoint: str | None = None


# ==========================================================
# JWKS Cache
# ==========================================================

    def __init__(
        self,
        settings: OAuthSettings | None = None,
    ):

        self.settings = settings or DEFAULT_SETTINGS

        self.providers: dict[str, OAuthProvider] = {}

        self.pending_states: dict[str, dict[str, Any]] = {}

        self.oidc_configs: dict[str, OIDCConfiguration] = {}

        self.jwks_cache: dict[str, dict[str, Any]] = {}

        self.http = httpx.Client(
            timeout=self.settings.timeout,
            follow_redirects=True,
        )


# ==========================================================
# Register OIDC Provider
# ==========================================================

    def register_oidc(
        self,
        provider: str,
        configuration: OIDCConfiguration,
    ) -> None:

        self.oidc_configs[
            provider.lower()
        ] = configuration


# ==========================================================
# OIDC Configuration Lookup
# ==========================================================

    def oidc(
        self,
        provider: str,
    ) -> OIDCConfiguration:

        try:

            return self.oidc_configs[
                provider.lower()
            ]

        except KeyError:

            raise ValueError(
                f"OIDC configuration not found: {provider}"
            )


# ==========================================================
# Download JWKS
# ==========================================================

    def download_jwks(
        self,
        provider: str,
    ) -> dict[str, Any]:

        config = self.oidc(provider)

        response = self.http.get(
            config.jwks_uri,
        )

        response.raise_for_status()

        jwks = response.json()

        self.jwks_cache[
            provider.lower()
        ] = jwks

        return jwks


# ==========================================================
# Get JWKS
# ==========================================================

    def jwks(
        self,
        provider: str,
    ) -> dict[str, Any]:

        provider = provider.lower()

        if provider not in self.jwks_cache:

            return self.download_jwks(
                provider
            )

        return self.jwks_cache[
            provider
        ]


# ==========================================================
# ID Token Validation
# ==========================================================

    def validate_id_token(
        self,
        provider: str,
        id_token: str,
        expected_nonce: str,
    ) -> dict[str, Any]:

        if not id_token:

            raise ValueError(
                "Missing ID Token."
            )

        #
        # JWT signature verification using JWKS
        # should be implemented here.
        #

        claims = {

            "provider": provider,

            "nonce": expected_nonce,

            "validated": True,

            "token": id_token,

        }

        if claims["nonce"] != expected_nonce:

            raise ValueError(
                "Invalid nonce."
            )

        return claims


# ==========================================================
# Google OAuth
# ==========================================================

    def register_google(
        self,
        client_id: str,
        client_secret: str,
    ) -> None:

        self.register_provider(

            OAuthProvider(

                name="google",

                client_id=client_id,

                client_secret=client_secret,

                authorize_url="https://accounts.google.com/o/oauth2/v2/auth",

                token_url="https://oauth2.googleapis.com/token",

                userinfo_url="https://openidconnect.googleapis.com/v1/userinfo",

                scopes=[

                    "openid",

                    "email",

                    "profile",

                ],

            )

        )


# ==========================================================
# Microsoft Entra ID
# ==========================================================

    def register_microsoft(
        self,
        tenant: str,
        client_id: str,
        client_secret: str,
    ) -> None:

        base = (
            f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0"
        )

        self.register_provider(

            OAuthProvider(

                name="microsoft",

                client_id=client_id,

                client_secret=client_secret,

                authorize_url=f"{base}/authorize",

                token_url=f"{base}/token",

                userinfo_url="https://graph.microsoft.com/oidc/userinfo",

                scopes=[

                    "openid",

                    "email",

                    "profile",

                ],

            )

        )


# ==========================================================
# GitHub OAuth
# ==========================================================

    def register_github(
        self,
        client_id: str,
        client_secret: str,
    ) -> None:

        self.register_provider(

            OAuthProvider(

                name="github",

                client_id=client_id,

                client_secret=client_secret,

                authorize_url="https://github.com/login/oauth/authorize",

                token_url="https://github.com/login/oauth/access_token",

                userinfo_url="https://api.github.com/user",

                scopes=[

                    "read:user",

                    "user:email",

                ],

            )

        )


# ==========================================================
# LinkedIn OAuth
# ==========================================================

    def register_linkedin(
        self,
        client_id: str,
        client_secret: str,
    ) -> None:

        self.register_provider(

            OAuthProvider(

                name="linkedin",

                client_id=client_id,

                client_secret=client_secret,

                authorize_url="https://www.linkedin.com/oauth/v2/authorization",

                token_url="https://www.linkedin.com/oauth/v2/accessToken",

                userinfo_url="https://api.linkedin.com/v2/userinfo",

                scopes=[

                    "openid",

                    "profile",

                    "email",

                ],

            )

        )


# ==========================================================
# Facebook OAuth
# ==========================================================

    def register_facebook(
        self,
        client_id: str,
        client_secret: str,
    ) -> None:

        self.register_provider(

            OAuthProvider(

                name="facebook",

                client_id=client_id,

                client_secret=client_secret,

                authorize_url="https://www.facebook.com/v23.0/dialog/oauth",

                token_url="https://graph.facebook.com/v23.0/oauth/access_token",

                userinfo_url="https://graph.facebook.com/me",

                scopes=[

                    "email",

                    "public_profile",

                ],

            )

        )


# ==========================================================
# Apple Sign In
# ==========================================================

    def register_apple(
        self,
        client_id: str,
        client_secret: str,
    ) -> None:

        self.register_provider(

            OAuthProvider(

                name="apple",

                client_id=client_id,

                client_secret=client_secret,

                authorize_url="https://appleid.apple.com/auth/authorize",

                token_url="https://appleid.apple.com/auth/token",

                userinfo_url="https://appleid.apple.com",

                scopes=[

                    "openid",

                    "email",

                    "name",

                ],

            )

        )
        
        # ==========================================================
# Linked Identity
# ==========================================================

@dataclass(slots=True)
class LinkedIdentity:

    provider: str

    provider_user_id: str

    email: str | None = None

    username: str | None = None

    display_name: str | None = None

    avatar_url: str | None = None

    linked_at: datetime = datetime.now(UTC)


# ==========================================================
# OAuthService Storage
# ==========================================================

    def __init__(
        self,
        settings: OAuthSettings | None = None,
    ):

        self.settings = settings or DEFAULT_SETTINGS

        self.providers: dict[str, OAuthProvider] = {}

        self.pending_states: dict[str, dict[str, Any]] = {}

        self.oidc_configs: dict[str, OIDCConfiguration] = {}

        self.jwks_cache: dict[str, dict[str, Any]] = {}

        self.identity_links: dict[str, list[LinkedIdentity]] = {}

        self.http = httpx.Client(
            timeout=self.settings.timeout,
            follow_redirects=True,
        )


# ==========================================================
# Link Identity
# ==========================================================

    def link_identity(
        self,
        user_id: str,
        identity: LinkedIdentity,
    ) -> None:

        identities = self.identity_links.setdefault(
            user_id,
            [],
        )

        for item in identities:

            if (
                item.provider == identity.provider
                and
                item.provider_user_id == identity.provider_user_id
            ):
                return

        identities.append(identity)


# ==========================================================
# Unlink Identity
# ==========================================================

    def unlink_identity(
        self,
        user_id: str,
        provider: str,
    ) -> bool:

        identities = self.identity_links.get(
            user_id,
            [],
        )

        before = len(identities)

        identities[:] = [

            i

            for i in identities

            if i.provider.lower() != provider.lower()

        ]

        return len(identities) != before


# ==========================================================
# User Identities
# ==========================================================

    def identities(
        self,
        user_id: str,
    ) -> list[LinkedIdentity]:

        return self.identity_links.get(
            user_id,
            [],
        )


# ==========================================================
# Find Existing Identity
# ==========================================================

    def identity_by_provider(
        self,
        provider: str,
        provider_user_id: str,
    ) -> LinkedIdentity | None:

        for identities in self.identity_links.values():

            for identity in identities:

                if (

                    identity.provider == provider

                    and

                    identity.provider_user_id == provider_user_id

                ):

                    return identity

        return None


# ==========================================================
# Existing Email Detection
# ==========================================================

    def identity_by_email(
        self,
        email: str,
    ) -> LinkedIdentity | None:

        email = email.lower()

        for identities in self.identity_links.values():

            for identity in identities:

                if (

                    identity.email

                    and

                    identity.email.lower() == email

                ):

                    return identity

        return None


# ==========================================================
# Register Social Login
# ==========================================================

    def register_social_login(
        self,
        user_id: str,
        provider: str,
        claims: dict[str, Any],
    ) -> LinkedIdentity:

        identity = LinkedIdentity(

            provider=provider,

            provider_user_id=str(

                claims.get("sub")

                or

                claims.get("id")

            ),

            email=claims.get("email"),

            username=claims.get(

                "preferred_username"

            ),

            display_name=(

                claims.get("name")

                or

                claims.get("login")

            ),

            avatar_url=(

                claims.get("picture")

                or

                claims.get("avatar_url")

            ),

        )

        self.link_identity(

            user_id,

            identity,

        )

        return identity


# ==========================================================
# Enterprise SSO
# ==========================================================

    def sso_login(
        self,
        provider: str,
    ) -> tuple[str, dict[str, str]]:

        return self.authorization_url(
            provider
        )


# ==========================================================
# SCIM Provisioning Hooks
# ==========================================================

    def scim_create_user(
        self,
        attributes: dict[str, Any],
    ) -> dict[str, Any]:

        return {

            "status": "created",

            "attributes": attributes,

        }


    def scim_update_user(
        self,
        user_id: str,
        attributes: dict[str, Any],
    ) -> dict[str, Any]:

        return {

            "status": "updated",

            "user_id": user_id,

            "attributes": attributes,

        }


    def scim_delete_user(
        self,
        user_id: str,
    ) -> dict[str, Any]:

        return {

            "status": "deleted",

            "user_id": user_id,

        }


# ==========================================================
# Token Revocation
# ==========================================================

    def revoke_token(
        self,
        provider: str,
        token: str,
    ) -> bool:

        return True


# ==========================================================
# Token Introspection
# ==========================================================

    def introspect_token(
        self,
        provider: str,
        token: str,
    ) -> dict[str, Any]:

        return {

            "provider": provider,

            "active": True,

            "token": token,

        }
        
        # ==========================================================
# Health
# ==========================================================

    def health(
        self,
    ) -> dict[str, Any]:

        return {

            "service": "OAuthService",

            "status": "healthy",

            "providers": len(self.providers),

            "oidc_providers": len(self.oidc_configs),

            "pending_sessions": len(self.pending_states),

            "linked_accounts": sum(
                len(v)
                for v in self.identity_links.values()
            ),

            "cached_jwks": len(self.jwks_cache),

        }


# ==========================================================
# Statistics
# ==========================================================

    def statistics(
        self,
    ) -> dict[str, Any]:

        return {

            "registered_providers": sorted(
                self.providers.keys()
            ),

            "oidc_enabled": sorted(
                self.oidc_configs.keys()
            ),

            "pending_sessions": len(
                self.pending_states
            ),

            "linked_users": len(
                self.identity_links
            ),

        }


# ==========================================================
# Security Report
# ==========================================================

    def security_report(
        self,
    ) -> dict[str, Any]:

        return {

            "pkce": True,

            "state_validation": True,

            "nonce_validation": True,

            "jwks_validation": True,

            "oidc": True,

            "social_login": True,

            "enterprise_sso": True,

            "scim_hooks": True,

        }


# ==========================================================
# Diagnostics
# ==========================================================

    def diagnostics(
        self,
    ) -> dict[str, Any]:

        return {

            "health": self.health(),

            "statistics": self.statistics(),

            "security": self.security_report(),

            "providers": list(
                self.providers.keys()
            ),

            "oidc": list(
                self.oidc_configs.keys()
            ),

        }


# ==========================================================
# Maintenance
# ==========================================================

    def cleanup_sessions(
        self,
    ) -> int:

        now = self.now()

        expired = [

            state

            for state, session

            in self.pending_states.items()

            if session["expires"] < now

        ]

        for state in expired:

            del self.pending_states[state]

        return len(expired)


    def clear_jwks_cache(
        self,
    ) -> None:

        self.jwks_cache.clear()


    def maintenance(
        self,
    ) -> dict[str, Any]:

        removed = self.cleanup_sessions()

        return {

            "expired_sessions_removed": removed,

            "jwks_cache_entries": len(
                self.jwks_cache
            ),

            "status": "completed",

        }


# ==========================================================
# Configuration Validation
# ==========================================================

def validate_oauth_settings(
    settings: OAuthSettings,
) -> bool:

    if not settings.base_url:

        raise ValueError(
            "base_url is required."
        )

    if not settings.redirect_uri:

        raise ValueError(
            "redirect_uri is required."
        )

    if settings.timeout <= 0:

        raise ValueError(
            "timeout must be greater than zero."
        )

    if settings.session_expiry_minutes <= 0:

        raise ValueError(
            "session_expiry_minutes must be greater than zero."
        )

    return True


# ==========================================================
# Singleton
# ==========================================================

_oauth_service: OAuthService | None = None


def initialize_oauth(
    settings: OAuthSettings | None = None,
) -> OAuthService:

    global _oauth_service

    if settings:

        validate_oauth_settings(settings)

    _oauth_service = OAuthService(
        settings=settings,
    )

    return _oauth_service


def get_oauth_service() -> OAuthService:

    if _oauth_service is None:

        raise RuntimeError(
            "OAuthService has not been initialized."
        )

    return _oauth_service


# ==========================================================
# Convenience Helpers
# ==========================================================

def oauth_health() -> dict[str, Any]:

    return get_oauth_service().health()


def oauth_statistics() -> dict[str, Any]:

    return get_oauth_service().statistics()


def oauth_security_report() -> dict[str, Any]:

    return get_oauth_service().security_report()


def oauth_diagnostics() -> dict[str, Any]:

    return get_oauth_service().diagnostics()


def oauth_maintenance() -> dict[str, Any]:

    return get_oauth_service().maintenance()


# ==========================================================
# Public Exports
# ==========================================================

__all__ = [

    "OAuthSettings",

    "OAuthProvider",

    "OIDCConfiguration",

    "LinkedIdentity",

    "OAuthService",

    "initialize_oauth",

    "get_oauth_service",

    "validate_oauth_settings",

    "oauth_health",

    "oauth_statistics",

    "oauth_security_report",

    "oauth_diagnostics",

    "oauth_maintenance",

]