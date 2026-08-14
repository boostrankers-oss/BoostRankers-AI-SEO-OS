"""
Boost Rankers AI SEO OS
Production Company Schemas

Pydantic v2
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    HttpUrl,
)


# ============================================================
# BASE SCHEMA
# ============================================================

class CompanyBase(BaseModel):
    """Base company schema."""

    model_config = ConfigDict(
        from_attributes=True,
        extra="ignore",
    )

    # --------------------------------------------------------
    # Identity
    # --------------------------------------------------------

    name: str = Field(
        min_length=2,
        max_length=200,
    )

    legal_name: Optional[str] = Field(
        default=None,
        max_length=255,
    )

    description: Optional[str] = None

    website: Optional[HttpUrl] = None

    domain: Optional[str] = None

    industry: Optional[str] = None

    company_size: str = "SMALL"

    founded_year: Optional[int] = None

    registration_number: Optional[str] = None

    tax_number: Optional[str] = None

    # --------------------------------------------------------
    # Contact
    # --------------------------------------------------------

    email: Optional[EmailStr] = None

    support_email: Optional[EmailStr] = None

    sales_email: Optional[EmailStr] = None

    billing_email: Optional[EmailStr] = None

    phone: Optional[str] = None

    alternate_phone: Optional[str] = None

    whatsapp: Optional[str] = None

    # --------------------------------------------------------
    # Address
    # --------------------------------------------------------

    address_line1: Optional[str] = None

    address_line2: Optional[str] = None

    city: Optional[str] = None

    state: Optional[str] = None

    postal_code: Optional[str] = None

    country: Optional[str] = None

    latitude: Optional[float] = None

    longitude: Optional[float] = None

    # --------------------------------------------------------
    # Localization
    # --------------------------------------------------------

    timezone: str = "UTC"

    currency: str = "USD"

    language: str = "en"

    date_format: str = "DD/MM/YYYY"

    time_format: str = "24h"

    # --------------------------------------------------------
    # Branding
    # --------------------------------------------------------

    logo_url: Optional[HttpUrl] = None

    favicon_url: Optional[HttpUrl] = None

    cover_image: Optional[HttpUrl] = None

    primary_color: Optional[str] = None

    secondary_color: Optional[str] = None

    accent_color: Optional[str] = None

    font_family: Optional[str] = None

    custom_domain: Optional[str] = None

    dark_mode_enabled: bool = False

    white_label_enabled: bool = False
    
        # --------------------------------------------------------
    # Subscription
    # --------------------------------------------------------

    subscription_plan: str = "FREE"

    subscription_status: str = "TRIAL"

    billing_cycle: str = "MONTHLY"

    monthly_price: Decimal = Decimal("0.00")

    credit_balance: int = 0

    trial_starts_at: Optional[datetime] = None

    trial_ends_at: Optional[datetime] = None

    subscription_starts_at: Optional[datetime] = None

    subscription_expires_at: Optional[datetime] = None

    next_billing_date: Optional[datetime] = None

    # --------------------------------------------------------
    # Account Limits
    # --------------------------------------------------------

    max_users: int = 5

    max_clients: int = 100

    max_projects: int = 100

    max_monthly_audits: int = 500

    max_storage_gb: int = 20

    api_calls_per_month: int = 100000

    # --------------------------------------------------------
    # Current Usage
    # --------------------------------------------------------

    used_storage_gb: float = 0

    used_api_calls: int = 0

    active_users: int = 0

    active_clients: int = 0

    active_projects: int = 0

    # --------------------------------------------------------
    # Google Integrations
    # --------------------------------------------------------

    google_search_console_connected: bool = False

    google_analytics_connected: bool = False

    google_business_profile_connected: bool = False

    google_tag_manager_connected: bool = False

    bing_webmaster_connected: bool = False

    # --------------------------------------------------------
    # API Integrations
    # --------------------------------------------------------

    openai_api_enabled: bool = False

    anthropic_api_enabled: bool = False

    pagespeed_api_enabled: bool = False

    google_maps_api_enabled: bool = False

    smtp_enabled: bool = False

    webhook_enabled: bool = False

    slack_enabled: bool = False

    zapier_enabled: bool = False

    # --------------------------------------------------------
    # SEO Defaults
    # --------------------------------------------------------

    default_country: Optional[str] = None

    default_language: Optional[str] = None

    default_search_engine: Optional[str] = None

    default_device: Optional[str] = None

    default_audit_schedule: Optional[str] = None

    enable_ai_recommendations: bool = True

    enable_auto_audits: bool = False

    enable_email_reports: bool = True

    enable_white_label_reports: bool = False

    # --------------------------------------------------------
    # Statistics
    # --------------------------------------------------------

    total_users: int = 0

    total_clients: int = 0

    total_projects: int = 0

    total_audits: int = 0

    total_reports: int = 0

    average_seo_score: float = 0

    total_keywords: int = 0

    total_backlinks: int = 0

    monthly_api_requests: int = 0

    # --------------------------------------------------------
    # Status
    # --------------------------------------------------------

    status: str = "ACTIVE"

    is_active: bool = True

    is_verified: bool = False

    is_archived: bool = False