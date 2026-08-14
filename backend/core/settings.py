from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# ==========================================================
# Environment
# ==========================================================

class Environment(StrEnum):

    DEVELOPMENT = "development"

    TESTING = "testing"

    STAGING = "staging"

    PRODUCTION = "production"


# ==========================================================
# Log Level
# ==========================================================

class LogLevel(StrEnum):

    DEBUG = "DEBUG"

    INFO = "INFO"

    WARNING = "WARNING"

    ERROR = "ERROR"

    CRITICAL = "CRITICAL"


# ==========================================================
# Database
# ==========================================================

class DatabaseSettings(BaseSettings):

    url: str = Field(
        ......,
        alias="DATABASE_URL",
    )

    echo: bool = Field(
        default=False,
        alias="DATABASE_ECHO",
    )

    pool_size: int = Field(
        default=20,
        ge=1,
        le=100,
        alias="DATABASE_POOL_SIZE",
    )

    max_overflow: int = Field(
        default=30,
        ge=0,
        alias="DATABASE_MAX_OVERFLOW",
    )

    pool_timeout: int = Field(
        default=30,
        ge=5,
        alias="DATABASE_POOL_TIMEOUT",
    )

    pool_recycle: int = Field(
        default=1800,
        alias="DATABASE_POOL_RECYCLE",
    )

    model_config = SettingsConfigDict(
        env_prefix="",
        extra="ignore",
    )


# ==========================================================
# Redis
# ==========================================================

class RedisSettings(BaseSettings):

    url: str = Field(
        default="redis://localhost:6379/0",
        alias="REDIS_URL",
    )

    password: SecretStr | None = Field(
        default=None,
        alias="REDIS_PASSWORD",
    )

    ttl: int = Field(
        default=3600,
        alias="REDIS_DEFAULT_TTL",
    )

    max_connections: int = Field(
        default=100,
        alias="REDIS_MAX_CONNECTIONS",
    )

    model_config = SettingsConfigDict(
        env_prefix="",
        extra="ignore",
    )


# ==========================================================
# Security
# ==========================================================

class SecuritySettings(BaseSettings):

    secret_key: SecretStr = Field(
        alias="SECRET_KEY",
    )

    jwt_algorithm: str = Field(
        default="HS256",
        alias="JWT_ALGORITHM",
    )

    access_token_minutes: int = Field(
        default=30,
        alias="ACCESS_TOKEN_EXPIRE_MINUTES",
    )

    refresh_token_days: int = Field(
        default=30,
        alias="REFRESH_TOKEN_EXPIRE_DAYS",
    )

    encryption_key: SecretStr | None = Field(
        default=None,
        alias="ENCRYPTION_KEY",
    )

    csrf_enabled: bool = Field(
        default=True,
        alias="CSRF_ENABLED",
    )

    model_config = SettingsConfigDict(
        env_prefix="",
        extra="ignore",
    )


# ==========================================================
# Email
# ==========================================================

class EmailSettings(BaseSettings):

    smtp_host: str = Field(
        default="localhost",
        alias="SMTP_HOST",
    )

    smtp_port: int = Field(
        default=587,
        alias="SMTP_PORT",
    )

    username: str = Field(
        default="",
        alias="SMTP_USERNAME",
    )

    password: SecretStr | None = Field(
        default=None,
        alias="SMTP_PASSWORD",
    )

    use_tls: bool = Field(
        default=True,
        alias="SMTP_TLS",
    )

    sender: str = Field(
        default="noreply@boostrankers.com",
        alias="SMTP_SENDER",
    )

    model_config = SettingsConfigDict(
        env_prefix="",
        extra="ignore",
    )


# ==========================================================
# Storage
# ==========================================================

class StorageSettings(BaseSettings):

    backend: str = Field(
        default="local",
        alias="STORAGE_BACKEND",
    )

    upload_directory: Path = Field(
        default=Path("uploads"),
        alias="UPLOAD_DIRECTORY",
    )

    max_upload_size: int = Field(
        default=100 * 1024 * 1024,
        alias="MAX_UPLOAD_SIZE",
    )

    allowed_extensions: list[str] = Field(
        default_factory=lambda: [
            ".jpg",
            ".jpeg",
            ".png",
            ".webp",
            ".gif",
            ".svg",
            ".pdf",
            ".csv",
            ".xlsx",
            ".docx",
            ".pptx",
            ".zip",
        ]
    )

    model_config = SettingsConfigDict(
        env_prefix="",
        extra="ignore",
    )
    
    # ==========================================================
# AI Providers
# ==========================================================

class AnthropicSettings(BaseSettings):

    api_key: SecretStr | None = Field(
        default=None,
        alias="ANTHROPIC_API_KEY",
    )

    model: str = Field(
        default="claude-sonnet-4",
        alias="ANTHROPIC_MODEL",
    )

    max_tokens: int = Field(
        default=8192,
        ge=256,
        le=200000,
        alias="ANTHROPIC_MAX_TOKENS",
    )

    temperature: float = Field(
        default=0.2,
        ge=0.0,
        le=2.0,
        alias="ANTHROPIC_TEMPERATURE",
    )

    timeout: int = Field(
        default=300,
        alias="ANTHROPIC_TIMEOUT",
    )

    model_config = SettingsConfigDict(
        env_prefix="",
        extra="ignore",
    )


class OpenAISettings(BaseSettings):

    api_key: SecretStr | None = Field(
        default=None,
        alias="OPENAI_API_KEY",
    )

    model: str = Field(
        default="gpt-5",
        alias="OPENAI_MODEL",
    )

    timeout: int = Field(
        default=300,
        alias="OPENAI_TIMEOUT",
    )

    model_config = SettingsConfigDict(
        env_prefix="",
        extra="ignore",
    )


class GeminiSettings(BaseSettings):

    api_key: SecretStr | None = Field(
        default=None,
        alias="GEMINI_API_KEY",
    )

    model: str = Field(
        default="gemini-2.5-pro",
        alias="GEMINI_MODEL",
    )

    timeout: int = Field(
        default=300,
        alias="GEMINI_TIMEOUT",
    )

    model_config = SettingsConfigDict(
        env_prefix="",
        extra="ignore",
    )


class DeepSeekSettings(BaseSettings):

    api_key: SecretStr | None = Field(
        default=None,
        alias="DEEPSEEK_API_KEY",
    )

    model: str = Field(
        default="deepseek-chat",
        alias="DEEPSEEK_MODEL",
    )

    timeout: int = Field(
        default=300,
        alias="DEEPSEEK_TIMEOUT",
    )

    model_config = SettingsConfigDict(
        env_prefix="",
        extra="ignore",
    )


# ==========================================================
# Queue
# ==========================================================

class QueueSettings(BaseSettings):

    backend: str = Field(
        default="redis",
        alias="QUEUE_BACKEND",
    )

    workers: int = Field(
        default=4,
        ge=1,
        alias="QUEUE_WORKERS",
    )

    retry_attempts: int = Field(
        default=5,
        ge=0,
        alias="QUEUE_RETRIES",
    )

    retry_delay: int = Field(
        default=60,
        alias="QUEUE_RETRY_DELAY",
    )

    dead_letter_enabled: bool = Field(
        default=True,
        alias="QUEUE_DEAD_LETTER",
    )

    model_config = SettingsConfigDict(
        env_prefix="",
        extra="ignore",
    )


# ==========================================================
# Scheduler
# ==========================================================

class SchedulerSettings(BaseSettings):

    enabled: bool = Field(
        default=True,
        alias="SCHEDULER_ENABLED",
    )

    timezone: str = Field(
        default="UTC",
        alias="SCHEDULER_TIMEZONE",
    )

    max_jobs: int = Field(
        default=500,
        alias="SCHEDULER_MAX_JOBS",
    )

    cleanup_interval: int = Field(
        default=3600,
        alias="SCHEDULER_CLEANUP_INTERVAL",
    )

    model_config = SettingsConfigDict(
        env_prefix="",
        extra="ignore",
    )


# ==========================================================
# Rate Limiting
# ==========================================================

class RateLimitSettings(BaseSettings):

    enabled: bool = Field(
        default=True,
        alias="RATE_LIMIT_ENABLED",
    )

    requests_per_minute: int = Field(
        default=120,
        alias="RATE_LIMIT_REQUESTS",
    )

    burst_limit: int = Field(
        default=250,
        alias="RATE_LIMIT_BURST",
    )

    model_config = SettingsConfigDict(
        env_prefix="",
        extra="ignore",
    )


# ==========================================================
# SEO Engine
# ==========================================================

class SEOSettings(BaseSettings):

    crawl_timeout: int = Field(
        default=120,
        alias="SEO_CRAWL_TIMEOUT",
    )

    max_pages: int = Field(
        default=1000,
        alias="SEO_MAX_PAGES",
    )

    max_depth: int = Field(
        default=5,
        alias="SEO_MAX_DEPTH",
    )

    concurrent_requests: int = Field(
        default=10,
        alias="SEO_CONCURRENT_REQUESTS",
    )

    user_agent: str = Field(
        default="BoostRankersAISEOOSBot/1.0",
        alias="SEO_USER_AGENT",
    )

    obey_robots_txt: bool = Field(
        default=True,
        alias="SEO_OBEY_ROBOTS",
    )

    render_javascript: bool = Field(
        default=False,
        alias="SEO_RENDER_JS",
    )

    model_config = SettingsConfigDict(
        env_prefix="",
        extra="ignore",
    )


# ==========================================================
# Feature Flags
# ==========================================================

class FeatureSettings(BaseSettings):

    ai_enabled: bool = Field(
        default=True,
        alias="FEATURE_AI",
    )

    audit_enabled: bool = Field(
        default=True,
        alias="FEATURE_AUDIT",
    )

    local_seo_enabled: bool = Field(
        default=True,
        alias="FEATURE_LOCAL_SEO",
    )

    backlinks_enabled: bool = Field(
        default=True,
        alias="FEATURE_BACKLINKS",
    )

    reports_enabled: bool = Field(
        default=True,
        alias="FEATURE_REPORTS",
    )

    white_label_enabled: bool = Field(
        default=True,
        alias="FEATURE_WHITE_LABEL",
    )

    api_enabled: bool = Field(
        default=True,
        alias="FEATURE_API",
    )

    model_config = SettingsConfigDict(
        env_prefix="",
        extra="ignore",
    )


# ==========================================================
# Audit Engine
# ==========================================================

class AuditSettings(BaseSettings):

    parallel_agents: int = Field(
        default=10,
        alias="AUDIT_PARALLEL_AGENTS",
    )

    max_runtime: int = Field(
        default=1800,
        alias="AUDIT_MAX_RUNTIME",
    )

    save_raw_html: bool = Field(
        default=False,
        alias="AUDIT_SAVE_HTML",
    )

    save_screenshots: bool = Field(
        default=True,
        alias="AUDIT_SAVE_SCREENSHOTS",
    )

    keep_history_days: int = Field(
        default=365,
        alias="AUDIT_HISTORY_DAYS",
    )

    model_config = SettingsConfigDict(
        env_prefix="",
        extra="ignore",
    )
    
    # ==========================================================
# Logging
# ==========================================================

class LoggingSettings(BaseSettings):

    level: LogLevel = Field(
        default=LogLevel.INFO,
        alias="LOG_LEVEL",
    )

    json_logs: bool = Field(
        default=True,
        alias="LOG_JSON",
    )

    log_directory: Path = Field(
        default=Path("logs"),
        alias="LOG_DIRECTORY",
    )

    file_name: str = Field(
        default="boost-rankers.log",
        alias="LOG_FILE",
    )

    rotation: str = Field(
        default="50 MB",
        alias="LOG_ROTATION",
    )

    retention: str = Field(
        default="30 days",
        alias="LOG_RETENTION",
    )

    compression: str = Field(
        default="zip",
        alias="LOG_COMPRESSION",
    )

    access_log: bool = Field(
        default=True,
        alias="ACCESS_LOG",
    )

    audit_log: bool = Field(
        default=True,
        alias="AUDIT_LOG",
    )

    model_config = SettingsConfigDict(
        env_prefix="",
        extra="ignore",
    )


# ==========================================================
# Monitoring
# ==========================================================

class MonitoringSettings(BaseSettings):

    enabled: bool = Field(
        default=True,
        alias="MONITORING_ENABLED",
    )

    prometheus: bool = Field(
        default=True,
        alias="PROMETHEUS_ENABLED",
    )

    opentelemetry: bool = Field(
        default=False,
        alias="OTEL_ENABLED",
    )

    metrics_interval: int = Field(
        default=30,
        alias="METRICS_INTERVAL",
    )

    tracing: bool = Field(
        default=True,
        alias="TRACING_ENABLED",
    )

    profiling: bool = Field(
        default=False,
        alias="PROFILING_ENABLED",
    )

    model_config = SettingsConfigDict(
        env_prefix="",
        extra="ignore",
    )


# ==========================================================
# API
# ==========================================================

class APISettings(BaseSettings):

    title: str = Field(
        default="Boost Rankers AI SEO OS API",
        alias="API_TITLE",
    )

    version: str = Field(
        default="1.0.0",
        alias="API_VERSION",
    )

    prefix: str = Field(
        default="/api",
        alias="API_PREFIX",
    )

    docs_url: str = Field(
        default="/docs",
        alias="API_DOCS_URL",
    )

    redoc_url: str = Field(
        default="/redoc",
        alias="API_REDOC_URL",
    )

    openapi_url: str = Field(
        default="/openapi.json",
        alias="OPENAPI_URL",
    )

    request_timeout: int = Field(
        default=300,
        alias="API_TIMEOUT",
    )

    model_config = SettingsConfigDict(
        env_prefix="",
        extra="ignore",
    )


# ==========================================================
# CORS
# ==========================================================

class CORSSettings(BaseSettings):

    enabled: bool = Field(
        default=True,
        alias="CORS_ENABLED",
    )

    allow_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://localhost:5173",
        ]
    )

    allow_methods: list[str] = Field(
        default_factory=lambda: ["*"]
    )

    allow_headers: list[str] = Field(
        default_factory=lambda: ["*"]
    )

    allow_credentials: bool = Field(
        default=True,
        alias="CORS_CREDENTIALS",
    )

    expose_headers: list[str] = Field(
        default_factory=list,
    )

    model_config = SettingsConfigDict(
        env_prefix="",
        extra="ignore",
    )


# ==========================================================
# WebSocket
# ==========================================================

class WebSocketSettings(BaseSettings):

    enabled: bool = Field(
        default=True,
        alias="WEBSOCKET_ENABLED",
    )

    heartbeat: int = Field(
        default=30,
        alias="WEBSOCKET_HEARTBEAT",
    )

    max_connections: int = Field(
        default=10000,
        alias="WEBSOCKET_MAX_CONNECTIONS",
    )

    ping_interval: int = Field(
        default=20,
        alias="WEBSOCKET_PING_INTERVAL",
    )

    ping_timeout: int = Field(
        default=30,
        alias="WEBSOCKET_PING_TIMEOUT",
    )

    model_config = SettingsConfigDict(
        env_prefix="",
        extra="ignore",
    )


# ==========================================================
# Server Sent Events
# ==========================================================

class SSESettings(BaseSettings):

    enabled: bool = Field(
        default=True,
        alias="SSE_ENABLED",
    )

    heartbeat: int = Field(
        default=15,
        alias="SSE_HEARTBEAT",
    )

    reconnect_delay: int = Field(
        default=3000,
        alias="SSE_RECONNECT_DELAY",
    )

    max_clients: int = Field(
        default=5000,
        alias="SSE_MAX_CLIENTS",
    )

    model_config = SettingsConfigDict(
        env_prefix="",
        extra="ignore",
    )


# ==========================================================
# Upload Policies
# ==========================================================

class UploadSettings(BaseSettings):

    virus_scan: bool = Field(
        default=False,
        alias="UPLOAD_VIRUS_SCAN",
    )

    image_optimization: bool = Field(
        default=True,
        alias="UPLOAD_IMAGE_OPTIMIZATION",
    )

    overwrite_existing: bool = Field(
        default=False,
        alias="UPLOAD_OVERWRITE",
    )

    chunk_size: int = Field(
        default=8 * 1024 * 1024,
        alias="UPLOAD_CHUNK_SIZE",
    )

    max_parallel_uploads: int = Field(
        default=5,
        alias="UPLOAD_PARALLEL",
    )

    model_config = SettingsConfigDict(
        env_prefix="",
        extra="ignore",
    )


# ==========================================================
# Backup
# ==========================================================

class BackupSettings(BaseSettings):

    enabled: bool = Field(
        default=True,
        alias="BACKUP_ENABLED",
    )

    directory: Path = Field(
        default=Path("backups"),
        alias="BACKUP_DIRECTORY",
    )

    schedule: str = Field(
        default="0 2 * * *",
        alias="BACKUP_SCHEDULE",
    )

    retention_days: int = Field(
        default=30,
        alias="BACKUP_RETENTION_DAYS",
    )

    compress: bool = Field(
        default=True,
        alias="BACKUP_COMPRESS",
    )

    encrypt: bool = Field(
        default=True,
        alias="BACKUP_ENCRYPT",
    )

    model_config = SettingsConfigDict(
        env_prefix="",
        extra="ignore",
    )


# ==========================================================
# Licensing
# ==========================================================

class LicensingSettings(BaseSettings):

    edition: str = Field(
        default="agency",
        alias="LICENSE_EDITION",
    )

    license_key: SecretStr | None = Field(
        default=None,
        alias="LICENSE_KEY",
    )

    max_companies: int = Field(
        default=100,
        alias="LICENSE_MAX_COMPANIES",
    )

    max_users: int = Field(
        default=1000,
        alias="LICENSE_MAX_USERS",
    )

    white_label: bool = Field(
        default=True,
        alias="LICENSE_WHITE_LABEL",
    )

    api_access: bool = Field(
        default=True,
        alias="LICENSE_API_ACCESS",
    )

    model_config = SettingsConfigDict(
        env_prefix="",
        extra="ignore",
    )
    
    # ==========================================================
# Billing
# ==========================================================

class BillingSettings(BaseSettings):

    provider: str = Field(
        default="stripe",
        alias="BILLING_PROVIDER",
    )

    currency: str = Field(
        default="USD",
        alias="BILLING_CURRENCY",
    )

    trial_days: int = Field(
        default=14,
        ge=0,
        alias="BILLING_TRIAL_DAYS",
    )

    invoice_prefix: str = Field(
        default="BR",
        alias="INVOICE_PREFIX",
    )

    webhook_secret: SecretStr | None = Field(
        default=None,
        alias="BILLING_WEBHOOK_SECRET",
    )

    stripe_secret_key: SecretStr | None = Field(
        default=None,
        alias="STRIPE_SECRET_KEY",
    )

    stripe_publishable_key: SecretStr | None = Field(
        default=None,
        alias="STRIPE_PUBLISHABLE_KEY",
    )

    model_config = SettingsConfigDict(
        env_prefix="",
        extra="ignore",
    )


# ==========================================================
# Multi Tenant
# ==========================================================

class TenantSettings(BaseSettings):

    enabled: bool = Field(
        default=True,
        alias="TENANT_ENABLED",
    )

    isolation: str = Field(
        default="logical",
        alias="TENANT_ISOLATION",
    )

    default_company: str = Field(
        default="boost-rankers",
        alias="DEFAULT_COMPANY",
    )

    max_companies: int = Field(
        default=1000,
        ge=1,
        alias="MAX_COMPANIES",
    )

    allow_custom_domains: bool = Field(
        default=True,
        alias="ALLOW_CUSTOM_DOMAINS",
    )

    white_label: bool = Field(
        default=True,
        alias="WHITE_LABEL",
    )

    model_config = SettingsConfigDict(
        env_prefix="",
        extra="ignore",
    )


# ==========================================================
# Analytics
# ==========================================================

class AnalyticsSettings(BaseSettings):

    enabled: bool = Field(
        default=True,
        alias="ANALYTICS_ENABLED",
    )

    retention_days: int = Field(
        default=730,
        alias="ANALYTICS_RETENTION_DAYS",
    )

    anonymize_ip: bool = Field(
        default=True,
        alias="ANALYTICS_ANONYMIZE_IP",
    )

    model_config = SettingsConfigDict(
        env_prefix="",
        extra="ignore",
    )


# ==========================================================
# Google Search Console
# ==========================================================

class SearchConsoleSettings(BaseSettings):

    enabled: bool = Field(
        default=True,
        alias="GSC_ENABLED",
    )

    client_id: str = Field(
        default="",
        alias="GSC_CLIENT_ID",
    )

    client_secret: SecretStr | None = Field(
        default=None,
        alias="GSC_CLIENT_SECRET",
    )

    refresh_interval: int = Field(
        default=3600,
        alias="GSC_REFRESH_INTERVAL",
    )

    model_config = SettingsConfigDict(
        env_prefix="",
        extra="ignore",
    )


# ==========================================================
# Google Analytics
# ==========================================================

class GoogleAnalyticsSettings(BaseSettings):

    enabled: bool = Field(
        default=True,
        alias="GA_ENABLED",
    )

    property_id: str = Field(
        default="",
        alias="GA_PROPERTY_ID",
    )

    credentials_file: str = Field(
        default="",
        alias="GA_CREDENTIALS_FILE",
    )

    sync_interval: int = Field(
        default=3600,
        alias="GA_SYNC_INTERVAL",
    )

    model_config = SettingsConfigDict(
        env_prefix="",
        extra="ignore",
    )


# ==========================================================
# Workers
# ==========================================================

class WorkerSettings(BaseSettings):

    workers: int = Field(
        default=4,
        alias="WORKERS",
    )

    threads: int = Field(
        default=4,
        alias="THREADS",
    )

    graceful_timeout: int = Field(
        default=60,
        alias="GRACEFUL_TIMEOUT",
    )

    keep_alive: int = Field(
        default=30,
        alias="KEEP_ALIVE",
    )

    model_config = SettingsConfigDict(
        env_prefix="",
        extra="ignore",
    )


# ==========================================================
# AI Usage
# ==========================================================

class AIUsageSettings(BaseSettings):

    max_requests_per_day: int = Field(
        default=10000,
        alias="AI_MAX_REQUESTS_PER_DAY",
    )

    max_tokens_per_day: int = Field(
        default=10_000_000,
        alias="AI_MAX_TOKENS_PER_DAY",
    )

    enable_usage_tracking: bool = Field(
        default=True,
        alias="AI_TRACK_USAGE",
    )

    enable_cost_tracking: bool = Field(
        default=True,
        alias="AI_TRACK_COST",
    )

    model_config = SettingsConfigDict(
        env_prefix="",
        extra="ignore",
    )


# ==========================================================
# Security Hardening
# ==========================================================

class SecurityHardeningSettings(BaseSettings):

    secure_headers: bool = Field(
        default=True,
        alias="SECURE_HEADERS",
    )

    hsts: bool = Field(
        default=True,
        alias="ENABLE_HSTS",
    )

    content_security_policy: bool = Field(
        default=True,
        alias="ENABLE_CSP",
    )

    x_frame_options: str = Field(
        default="DENY",
        alias="X_FRAME_OPTIONS",
    )

    x_content_type_options: bool = Field(
        default=True,
        alias="X_CONTENT_TYPE_OPTIONS",
    )

    referrer_policy: str = Field(
        default="strict-origin-when-cross-origin",
        alias="REFERRER_POLICY",
    )

    permissions_policy: bool = Field(
        default=True,
        alias="PERMISSIONS_POLICY",
    )

    model_config = SettingsConfigDict(
        env_prefix="",
        extra="ignore",
    )


# ==========================================================
# Application Settings
# ==========================================================

class ApplicationSettings(BaseSettings):

    environment: Environment = Field(
        default=Environment.DEVELOPMENT,
        alias="ENVIRONMENT",
    )

    application_name: str = Field(
        default="Boost Rankers AI SEO OS",
        alias="APP_NAME",
    )

    company_name: str = Field(
        default="Boost Rankers",
        alias="COMPANY_NAME",
    )

    version: str = Field(
        default="1.0.0",
        alias="APP_VERSION",
    )

    debug: bool = Field(
        default=False,
        alias="DEBUG",
    )

    database: DatabaseSettings = Field(
        default_factory=DatabaseSettings,
    )

    redis: RedisSettings = Field(
        default_factory=RedisSettings,
    )

    security: SecuritySettings = Field(
        default_factory=SecuritySettings,
    )

    email: EmailSettings = Field(
        default_factory=EmailSettings,
    )

    storage: StorageSettings = Field(
        default_factory=StorageSettings,
    )

    anthropic: AnthropicSettings = Field(
        default_factory=AnthropicSettings,
    )

    openai: OpenAISettings = Field(
        default_factory=OpenAISettings,
    )

    gemini: GeminiSettings = Field(
        default_factory=GeminiSettings,
    )

    deepseek: DeepSeekSettings = Field(
        default_factory=DeepSeekSettings,
    )

    queue: QueueSettings = Field(
        default_factory=QueueSettings,
    )

    scheduler: SchedulerSettings = Field(
        default_factory=SchedulerSettings,
    )

    rate_limit: RateLimitSettings = Field(
        default_factory=RateLimitSettings,
    )

    seo: SEOSettings = Field(
        default_factory=SEOSettings,
    )

    features: FeatureSettings = Field(
        default_factory=FeatureSettings,
    )

    audit: AuditSettings = Field(
        default_factory=AuditSettings,
    )

    logging: LoggingSettings = Field(
        default_factory=LoggingSettings,
    )

    monitoring: MonitoringSettings = Field(
        default_factory=MonitoringSettings,
    )

    api: APISettings = Field(
        default_factory=APISettings,
    )

    cors: CORSSettings = Field(
        default_factory=CORSSettings,
    )

    websocket: WebSocketSettings = Field(
        default_factory=WebSocketSettings,
    )

    sse: SSESettings = Field(
        default_factory=SSESettings,
    )

    uploads: UploadSettings = Field(
        default_factory=UploadSettings,
    )

    backup: BackupSettings = Field(
        default_factory=BackupSettings,
    )

    licensing: LicensingSettings = Field(
        default_factory=LicensingSettings,
    )

    billing: BillingSettings = Field(
        default_factory=BillingSettings,
    )

    tenants: TenantSettings = Field(
        default_factory=TenantSettings,
    )

    analytics: AnalyticsSettings = Field(
        default_factory=AnalyticsSettings,
    )

    search_console: SearchConsoleSettings = Field(
        default_factory=SearchConsoleSettings,
    )

    google_analytics: GoogleAnalyticsSettings = Field(
        default_factory=GoogleAnalyticsSettings,
    )

    workers: WorkerSettings = Field(
        default_factory=WorkerSettings,
    )

    ai_usage: AIUsageSettings = Field(
        default_factory=AIUsageSettings,
    )

    hardening: SecurityHardeningSettings = Field(
        default_factory=SecurityHardeningSettings,
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("application_name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Application name cannot be empty.")
        return value

    @field_validator("company_name")
    @classmethod
    def validate_company(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Company name cannot be empty.")
        return value
        
        # ==========================================================
# Settings Singleton
# ==========================================================

_settings: ApplicationSettings | None = None


@lru_cache(maxsize=1)
def get_settings() -> ApplicationSettings:
    return ApplicationSettings()


def load_settings() -> ApplicationSettings:
    global _settings

    if _settings is None:
        _settings = get_settings()

    return _settings


def reload_settings() -> ApplicationSettings:
    global _settings

    get_settings.cache_clear()

    _settings = get_settings()

    return _settings


# ==========================================================
# Environment Helpers
# ==========================================================

def is_development() -> bool:
    return (
        load_settings().environment
        == Environment.DEVELOPMENT
    )


def is_testing() -> bool:
    return (
        load_settings().environment
        == Environment.TESTING
    )


def is_staging() -> bool:
    return (
        load_settings().environment
        == Environment.STAGING
    )


def is_production() -> bool:
    return (
        load_settings().environment
        == Environment.PRODUCTION
    )


# ==========================================================
# Export
# ==========================================================

def export_settings() -> dict[str, Any]:
    return load_settings().model_dump(
        mode="json",
        exclude_none=False,
    )


# ==========================================================
# Diagnostics
# ==========================================================

def settings_diagnostics() -> dict[str, Any]:

    settings = load_settings()

    return {

        "application": settings.application_name,

        "company": settings.company_name,

        "version": settings.version,

        "environment": settings.environment.value,

        "debug": settings.debug,

        "database": settings.database.url,

        "redis": settings.redis.url,

        "queue_backend": settings.queue.backend,

        "storage_backend": settings.storage.backend,

        "ai": {

            "anthropic": bool(
                settings.anthropic.api_key
            ),

            "openai": bool(
                settings.openai.api_key
            ),

            "gemini": bool(
                settings.gemini.api_key
            ),

            "deepseek": bool(
                settings.deepseek.api_key
            ),

        },

    }


# ==========================================================
# Health
# ==========================================================

def settings_health() -> dict[str, Any]:

    try:

        load_settings()

        return {

            "status": "healthy",

            "environment": load_settings().environment.value,

        }

    except Exception as exc:

        return {

            "status": "unhealthy",

            "error": str(exc),

        }


# ==========================================================
# Runtime Override
# ==========================================================

def override_setting(
    section: str,
    field: str,
    value: Any,
) -> None:

    settings = load_settings()

    target = getattr(settings, section)

    setattr(target, field, value)


# ==========================================================
# Reset
# ==========================================================

def reset_settings() -> None:

    global _settings

    get_settings.cache_clear()

    _settings = None


# ==========================================================
# FastAPI Dependency
# ==========================================================

def settings_dependency() -> ApplicationSettings:

    return load_settings()


# ==========================================================
# Startup
# ==========================================================

async def startup_settings() -> None:

    load_settings()


# ==========================================================
# Shutdown
# ==========================================================

async def shutdown_settings() -> None:

    reset_settings()


# ==========================================================
# Public API
# ==========================================================

__all__ = [

    "Environment",

    "LogLevel",

    "ApplicationSettings",

    "DatabaseSettings",

    "RedisSettings",

    "SecuritySettings",

    "EmailSettings",

    "StorageSettings",

    "AnthropicSettings",

    "OpenAISettings",

    "GeminiSettings",

    "DeepSeekSettings",

    "QueueSettings",

    "SchedulerSettings",

    "RateLimitSettings",

    "SEOSettings",

    "FeatureSettings",

    "AuditSettings",

    "LoggingSettings",

    "MonitoringSettings",

    "APISettings",

    "CORSSettings",

    "WebSocketSettings",

    "SSESettings",

    "UploadSettings",

    "BackupSettings",

    "LicensingSettings",

    "BillingSettings",

    "TenantSettings",

    "AnalyticsSettings",

    "SearchConsoleSettings",

    "GoogleAnalyticsSettings",

    "WorkerSettings",

    "AIUsageSettings",

    "SecurityHardeningSettings",

    "get_settings",

    "load_settings",

    "reload_settings",

    "reset_settings",

    "settings_dependency",

    "startup_settings",

    "shutdown_settings",

    "settings_health",

    "settings_diagnostics",

    "export_settings",

    "override_setting",

    "is_development",

    "is_testing",

    "is_staging",

    "is_production",

]