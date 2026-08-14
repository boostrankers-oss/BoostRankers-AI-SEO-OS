"""
Enterprise Permission Registry
Boost Rankers AI SEO OS

Every permission in the application is declared here.

Format:
module:action
"""

from __future__ import annotations

from enum import StrEnum


class Permission(StrEnum):
    # ==========================================
    # Dashboard
    # ==========================================

    DASHBOARD_VIEW = "dashboard:view"

    # ==========================================
    # Users
    # ==========================================

    USERS_VIEW = "users:view"
    USERS_CREATE = "users:create"
    USERS_UPDATE = "users:update"
    USERS_DELETE = "users:delete"
    USERS_RESTORE = "users:restore"
    USERS_ASSIGN_ROLE = "users:assign_role"
    USERS_ASSIGN_COMPANY = "users:assign_company"
    USERS_RESET_PASSWORD = "users:reset_password"

    # ==========================================
    # Roles
    # ==========================================

    ROLES_VIEW = "roles:view"
    ROLES_CREATE = "roles:create"
    ROLES_UPDATE = "roles:update"
    ROLES_DELETE = "roles:delete"

    # ==========================================
    # Permissions
    # ==========================================

    PERMISSIONS_VIEW = "permissions:view"
    PERMISSIONS_ASSIGN = "permissions:assign"

    # ==========================================
    # Companies
    # ==========================================

    COMPANIES_VIEW = "companies:view"
    COMPANIES_CREATE = "companies:create"
    COMPANIES_UPDATE = "companies:update"
    COMPANIES_DELETE = "companies:delete"

    # ==========================================
    # Clients
    # ==========================================

    CLIENTS_VIEW = "clients:view"
    CLIENTS_CREATE = "clients:create"
    CLIENTS_UPDATE = "clients:update"
    CLIENTS_DELETE = "clients:delete"
    CLIENTS_IMPORT = "clients:import"
    CLIENTS_EXPORT = "clients:export"

    # ==========================================
    # Audits
    # ==========================================

    AUDITS_VIEW = "audits:view"
    AUDITS_CREATE = "audits:create"
    AUDITS_RUN = "audits:run"
    AUDITS_DELETE = "audits:delete"
    AUDITS_COMPARE = "audits:compare"

    # ==========================================
    # Reports
    # ==========================================

    REPORTS_VIEW = "reports:view"
    REPORTS_GENERATE = "reports:generate"
    REPORTS_DOWNLOAD = "reports:download"
    REPORTS_DELETE = "reports:delete"

    # ==========================================
    # AI
    # ==========================================

    AI_CHAT = "ai:chat"
    AI_CONTENT = "ai:content"
    AI_SCHEMA = "ai:schema"
    AI_KEYWORDS = "ai:keywords"
    AI_META = "ai:meta"
    AI_INTERNAL_LINKS = "ai:internal_links"

    # ==========================================
    # Technical SEO
    # ==========================================

    TECHNICAL_AUDIT = "technical:audit"
    TECHNICAL_SCHEMA = "technical:schema"
    TECHNICAL_SITEMAP = "technical:sitemap"
    TECHNICAL_ROBOTS = "technical:robots"

    # ==========================================
    # Local SEO
    # ==========================================

    LOCAL_VIEW = "local:view"
    LOCAL_CITATIONS = "local:citations"
    LOCAL_GBP = "local:gbp"

    # ==========================================
    # Backlinks
    # ==========================================

    BACKLINKS_VIEW = "backlinks:view"
    BACKLINKS_ANALYZE = "backlinks:analyze"
    BACKLINKS_EXPORT = "backlinks:export"

    # ==========================================
    # Keywords
    # ==========================================

    KEYWORDS_VIEW = "keywords:view"
    KEYWORDS_RESEARCH = "keywords:research"
    KEYWORDS_CLUSTER = "keywords:cluster"

    # ==========================================
    # Rankings
    # ==========================================

    RANKINGS_VIEW = "rankings:view"
    RANKINGS_TRACK = "rankings:track"

    # ==========================================
    # Search Console
    # ==========================================

    SEARCH_CONSOLE_VIEW = "search_console:view"
    SEARCH_CONSOLE_SYNC = "search_console:sync"

    # ==========================================
    # Google Analytics
    # ==========================================

    ANALYTICS_VIEW = "analytics:view"
    ANALYTICS_SYNC = "analytics:sync"

    # ==========================================
    # Billing
    # ==========================================

    BILLING_VIEW = "billing:view"
    BILLING_UPDATE = "billing:update"

    # ==========================================
    # API Keys
    # ==========================================

    API_KEYS_VIEW = "api_keys:view"
    API_KEYS_CREATE = "api_keys:create"
    API_KEYS_DELETE = "api_keys:delete"

    # ==========================================
    # Settings
    # ==========================================

    SETTINGS_VIEW = "settings:view"
    SETTINGS_UPDATE = "settings:update"

    # ==========================================
    # Notifications
    # ==========================================

    NOTIFICATIONS_VIEW = "notifications:view"
    NOTIFICATIONS_SEND = "notifications:send"

    # ==========================================
    # Audit Logs
    # ==========================================

    AUDIT_LOGS_VIEW = "audit_logs:view"

    # ==========================================
    # System
    # ==========================================

    SYSTEM_ADMIN = "system:admin"


SUPER_ADMIN_PERMISSIONS = {
    permission.value
    for permission in Permission
}


AGENCY_OWNER_DEFAULT = {
    permission.value
    for permission in Permission
    if permission != Permission.SYSTEM_ADMIN
}


MANAGER_DEFAULT = {
    Permission.DASHBOARD_VIEW.value,
    Permission.CLIENTS_VIEW.value,
    Permission.CLIENTS_CREATE.value,
    Permission.CLIENTS_UPDATE.value,
    Permission.AUDITS_VIEW.value,
    Permission.AUDITS_CREATE.value,
    Permission.AUDITS_RUN.value,
    Permission.REPORTS_VIEW.value,
    Permission.REPORTS_GENERATE.value,
    Permission.USERS_VIEW.value,
    Permission.USERS_CREATE.value,
    Permission.USERS_UPDATE.value,
}


SEO_SPECIALIST_DEFAULT = {
    Permission.DASHBOARD_VIEW.value,
    Permission.CLIENTS_VIEW.value,
    Permission.AUDITS_VIEW.value,
    Permission.AUDITS_RUN.value,
    Permission.REPORTS_VIEW.value,
    Permission.REPORTS_GENERATE.value,
    Permission.AI_CHAT.value,
    Permission.AI_CONTENT.value,
    Permission.AI_SCHEMA.value,
    Permission.AI_KEYWORDS.value,
    Permission.TECHNICAL_AUDIT.value,
    Permission.BACKLINKS_ANALYZE.value,
    Permission.KEYWORDS_RESEARCH.value,
}


CONTENT_WRITER_DEFAULT = {
    Permission.DASHBOARD_VIEW.value,
    Permission.AI_CONTENT.value,
    Permission.AI_META.value,
    Permission.AI_INTERNAL_LINKS.value,
}


CLIENT_DEFAULT = {
    Permission.DASHBOARD_VIEW.value,
    Permission.CLIENTS_VIEW.value,
    Permission.AUDITS_VIEW.value,
    Permission.REPORTS_VIEW.value,
}