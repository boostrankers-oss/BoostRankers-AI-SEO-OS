from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    HttpUrl,
)


# ---------------------------------------------------------
# Base Schema
# ---------------------------------------------------------

class ClientBase(BaseModel):
    """
    Shared client fields.
    """

    business_name: str = Field(
        ...,
        min_length=2,
        max_length=255,
    )

    legal_name: Optional[str] = Field(
        default=None,
        max_length=255,
    )

    website: HttpUrl

    industry: Optional[str] = Field(
        default=None,
        max_length=150,
    )

    business_type: Optional[str] = None

    company_size: Optional[int] = Field(
        default=None,
        ge=1,
    )

    description: Optional[str] = None

    logo_url: Optional[HttpUrl] = None

    # ----------------------------
    # Contact
    # ----------------------------

    contact_name: Optional[str] = None

    designation: Optional[str] = None

    email: Optional[EmailStr] = None

    secondary_email: Optional[EmailStr] = None

    phone: Optional[str] = None

    whatsapp: Optional[str] = None

    # ----------------------------
    # Address
    # ----------------------------

    address_line1: Optional[str] = None

    address_line2: Optional[str] = None

    city: Optional[str] = None

    state: Optional[str] = None

    postal_code: Optional[str] = None

    country: Optional[str] = None

    timezone: str = "UTC"

    currency: str = "USD"

    # ----------------------------
    # SEO
    # ----------------------------

    primary_keyword: Optional[str] = None

    target_location: Optional[str] = None

    target_country: Optional[str] = None

    target_language: str = "en"

    cms: Optional[str] = None

    hosting_provider: Optional[str] = None

    google_business_profile: Optional[HttpUrl] = None
    
    # ---------------------------------------------------------
# Create Client
# ---------------------------------------------------------

class ClientCreate(ClientBase):
    """
    Schema used to create a new client.
    """

    pass


# ---------------------------------------------------------
# Update Client
# ---------------------------------------------------------

class ClientUpdate(BaseModel):
    """
    Partial update schema.
    Every field is optional.
    """

    model_config = ConfigDict(extra="ignore")

    business_name: Optional[str] = Field(None, min_length=2, max_length=255)
    legal_name: Optional[str] = None
    website: Optional[HttpUrl] = None

    industry: Optional[str] = None
    business_type: Optional[str] = None
    company_size: Optional[int] = Field(None, ge=1)

    description: Optional[str] = None
    logo_url: Optional[HttpUrl] = None

    contact_name: Optional[str] = None
    designation: Optional[str] = None

    email: Optional[EmailStr] = None
    secondary_email: Optional[EmailStr] = None

    phone: Optional[str] = None
    whatsapp: Optional[str] = None

    address_line1: Optional[str] = None
    address_line2: Optional[str] = None

    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None

    timezone: Optional[str] = None
    currency: Optional[str] = None

    primary_keyword: Optional[str] = None
    target_location: Optional[str] = None
    target_country: Optional[str] = None
    target_language: Optional[str] = None

    cms: Optional[str] = None
    hosting_provider: Optional[str] = None
    google_business_profile: Optional[HttpUrl] = None

    status: Optional[str] = None
    priority: Optional[str] = None

    subscription_plan: Optional[str] = None
    billing_cycle: Optional[str] = None

    notes: Optional[str] = None
    tags: Optional[str] = None
    source: Optional[str] = None


# ---------------------------------------------------------
# Client Response
# ---------------------------------------------------------

class ClientResponse(ClientBase):
    """
    Returned after creating, updating or retrieving a client.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID

    company_id: UUID

    # ----------------------------
    # Integration Status
    # ----------------------------

    google_search_console_connected: bool
    google_analytics_connected: bool
    google_tag_manager_connected: bool
    bing_webmaster_connected: bool

    # ----------------------------
    # SEO Scores
    # ----------------------------

    overall_score: float
    technical_score: float
    content_score: float
    eeat_score: float
    local_seo_score: float
    backlinks_score: float
    keyword_score: float
    schema_score: float
    core_web_vitals_score: float
    ai_search_score: float

    # ----------------------------
    # SEO Statistics
    # ----------------------------

    total_keywords: int
    ranked_keywords: int
    total_backlinks: int
    referring_domains: int

    total_audits: int
    critical_issues: int
    warnings: int
    passed_checks: int

    # ----------------------------
    # Status
    # ----------------------------

    status: str
    priority: str

    subscription_plan: str
    billing_cycle: str

    is_active: bool
    is_archived: bool

    # ----------------------------
    # Audit Dates
    # ----------------------------

    first_audit_at: Optional[datetime]
    last_audit_at: Optional[datetime]
    next_audit_at: Optional[datetime]

    # ----------------------------
    # Metadata
    # ----------------------------

    notes: Optional[str]
    tags: Optional[str]
    source: Optional[str]

    created_at: datetime
    updated_at: datetime
    
    # ---------------------------------------------------------
# Client Summary
# ---------------------------------------------------------

class ClientSummary(BaseModel):
    """
    Lightweight client object used in tables and dropdowns.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_name: str
    website: HttpUrl
    industry: Optional[str]

    overall_score: float

    total_keywords: int
    total_backlinks: int
    total_audits: int

    status: str
    priority: str

    is_active: bool

    last_audit_at: Optional[datetime]


# ---------------------------------------------------------
# Client Dashboard
# ---------------------------------------------------------

class ClientDashboard(BaseModel):
    """
    Client overview used by dashboard.
    """

    model_config = ConfigDict(from_attributes=True)

    client: ClientResponse

    active_keywords: int

    completed_audits: int

    pending_audits: int

    failed_audits: int

    critical_issues: int

    warnings: int

    opportunities: int

    overall_score: float

    technical_score: float

    content_score: float

    eeat_score: float

    local_seo_score: float

    schema_score: float

    ai_search_score: float

    last_audit_at: Optional[datetime]


# ---------------------------------------------------------
# Client List Response
# ---------------------------------------------------------

class ClientListResponse(BaseModel):
    """
    Paginated client list.
    """

    total: int

    page: int

    page_size: int

    total_pages: int

    items: list[ClientSummary]


# ---------------------------------------------------------
# Client Statistics
# ---------------------------------------------------------

class ClientStatistics(BaseModel):
    """
    Agency-wide client statistics.
    """

    total_clients: int

    active_clients: int

    inactive_clients: int

    archived_clients: int

    average_score: float

    total_keywords: int

    total_backlinks: int

    total_audits: int

    completed_audits: int

    failed_audits: int


# ---------------------------------------------------------
# Client Search
# ---------------------------------------------------------

class ClientSearchRequest(BaseModel):

    search: Optional[str] = None

    industry: Optional[str] = None

    status: Optional[str] = None

    country: Optional[str] = None

    city: Optional[str] = None

    priority: Optional[str] = None

    page: int = Field(default=1, ge=1)

    page_size: int = Field(
        default=20,
        ge=1,
        le=100,
    )


# ---------------------------------------------------------
# Delete Response
# ---------------------------------------------------------

class DeleteClientResponse(BaseModel):

    success: bool

    message: str


# ---------------------------------------------------------
# Generic Success Response
# ---------------------------------------------------------

class ClientActionResponse(BaseModel):

    success: bool

    message: str

    client_id: UUID | None = None


# ---------------------------------------------------------
# Dashboard KPI Card
# ---------------------------------------------------------

class ClientKPICard(BaseModel):

    title: str

    value: float | int | str

    change: float = 0

    trend: str = "neutral"


# ---------------------------------------------------------
# Dashboard Response
# ---------------------------------------------------------

class ClientDashboardResponse(BaseModel):

    client: ClientResponse

    statistics: ClientStatistics

    kpis: list[ClientKPICard]

    recent_activity: list[dict] = []

    upcoming_tasks: list[dict] = []

    ai_recommendations: list[dict] = []


# ---------------------------------------------------------
# Export Response
# ---------------------------------------------------------

class ClientExportResponse(BaseModel):

    file_name: str

    download_url: str

    generated_at: datetime