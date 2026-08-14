from __future__ import annotations
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    event,
    
)

"""
Boost Rankers AI SEO OS
Production Audit Model

This model represents one complete SEO audit execution.

Author:
Boost Rankers Engineering Team

Architecture:
    FastAPI
    SQLAlchemy 2.x
    SQLite / PostgreSQL
    UUID Primary Keys

Features

✓ Technical SEO
✓ Content Analysis
✓ EEAT
✓ Local SEO
✓ AI Search Optimization
✓ Google Search Console
✓ Google Analytics
✓ Schema Analysis
✓ Core Web Vitals
✓ Security
✓ Performance
✓ Claude AI Analysis
✓ Report Generation
"""

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from models.base import BaseModel


# ============================================================
# ENUMS
# ============================================================


class AuditStatus(str, enum.Enum):
    """Audit lifecycle."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AuditType(str, enum.Enum):
    """Audit type."""

    FULL = "full"
    TECHNICAL = "technical"
    CONTENT = "content"
    LOCAL = "local"
    BACKLINK = "backlink"
    COMPETITOR = "competitor"
    AI = "ai"


class DeviceType(str, enum.Enum):
    """Device used during audit."""

    DESKTOP = "desktop"
    MOBILE = "mobile"
    TABLET = "tablet"


class CrawlStrategy(str, enum.Enum):
    """Crawler mode."""

    STANDARD = "standard"
    ADVANCED = "advanced"
    ENTERPRISE = "enterprise"


class ReportStatus(str, enum.Enum):
    """Report generation status."""

    NOT_GENERATED = "not_generated"
    GENERATING = "generating"
    GENERATED = "generated"
    FAILED = "failed"


class AuditPriority(str, enum.Enum):
    """Audit execution priority."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


# ============================================================
# MODEL
# ============================================================


class Audit(BaseModel):
    """
    Stores one complete SEO Audit.

    Every execution of the crawler creates one Audit.

    Related Modules

    • Dashboard
    • Reports
    • Claude AI
    • Google Search Console
    • Google Analytics
    • PageSpeed
    • Technical SEO
    • Content
    • Local SEO
    • Schema
    """

    __tablename__ = "audits"

    # ============================================================
    # OWNERSHIP
    # ============================================================

    company_id: Mapped[str | None] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    client_id: Mapped[str | None] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    # NOTE:
    # Add back_populates only after confirming the existing
    # Company, Client and User models use matching names.

    company: Mapped["Company"] = relationship(lazy="select")
    client: Mapped["Client"] = relationship(lazy="select")
    user: Mapped["User"] = relationship(lazy="select")

    # ============================================================
    # WEBSITE INFORMATION
    # ============================================================

    website: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        index=True,
        doc="Website URL",
    )

    domain: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    homepage: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    primary_keyword: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    secondary_keywords: Mapped[list[str] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    location: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    country: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )

    language: Mapped[str] = mapped_column(
        String(20),
        default="en",
        nullable=False,
    )

    industry: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    business_type: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )

    website_category: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )

    website_platform: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
        doc="WordPress, Shopify, Wix etc.",
    )

    cms: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )

    # ============================================================
    # AUDIT CONFIGURATION
    # ============================================================

    audit_name: Mapped[str | None] = mapped_column(
        String(255),
    )

    audit_type: Mapped[AuditType] = mapped_column(
        Enum(AuditType),
        default=AuditType.FULL,
        nullable=False,
    )

    priority: Mapped[AuditPriority] = mapped_column(
        Enum(AuditPriority),
        default=AuditPriority.NORMAL,
    )

    status: Mapped[AuditStatus] = mapped_column(
        Enum(AuditStatus),
        default=AuditStatus.PENDING,
        nullable=False,
        index=True,
    )

    device: Mapped[DeviceType] = mapped_column(
        Enum(DeviceType),
        default=DeviceType.DESKTOP,
    )

    crawl_strategy: Mapped[CrawlStrategy] = mapped_column(
        Enum(CrawlStrategy),
        default=CrawlStrategy.STANDARD,
    )

    crawl_depth: Mapped[int] = mapped_column(
        Integer,
        default=5,
    )

    max_pages: Mapped[int] = mapped_column(
        Integer,
        default=500,
    )

    crawl_delay: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    request_timeout: Mapped[int] = mapped_column(
        Integer,
        default=30,
    )

    max_threads: Mapped[int] = mapped_column(
        Integer,
        default=5,
    )

    include_subdomains: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    obey_robots_txt: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    render_javascript: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    follow_nofollow: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    scan_images: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    scan_css: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    scan_js: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    enable_pagespeed: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    enable_claude_ai: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    enable_gsc: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    enable_ga4: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    competitor_urls: Mapped[list[str] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    # ============================================================
    # EXECUTION
    # ============================================================

    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    duration_seconds: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    progress_percentage: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    current_stage: Mapped[str | None] = mapped_column(
        String(255),
    )

    current_task: Mapped[str | None] = mapped_column(
        String(255),
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
    )

    warning_message: Mapped[str | None] = mapped_column(
        Text,
    )
    
        # ============================================================
    # CRAWL STATISTICS
    # ============================================================

    pages_discovered: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    pages_crawled: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    pages_successful: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    pages_failed: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    pages_skipped: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    pages_with_errors: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    pages_with_warnings: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    pages_with_redirects: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    pages_blocked: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    pages_timeout: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    crawl_duration_ms: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    average_response_time: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    fastest_response_time: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    slowest_response_time: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    average_page_size_kb: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    total_download_size_mb: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    total_requests: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    successful_requests: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    failed_requests: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    # ============================================================
    # URL STATISTICS
    # ============================================================

    unique_urls: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    duplicate_urls: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    parameterized_urls: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    uppercase_urls: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    long_urls: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    clean_urls: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    seo_friendly_urls: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    dynamic_urls: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    static_urls: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    # ============================================================
    # HTTP STATUS METRICS
    # ============================================================

    status_200: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    status_301: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    status_302: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    status_304: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    status_400: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    status_401: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    status_403: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    status_404: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    status_410: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    status_429: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    status_500: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    status_502: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    status_503: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    status_other: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    # ============================================================
    # INDEXABILITY
    # ============================================================

    indexable_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    non_indexable_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    indexed_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    noindex_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    nofollow_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    canonicalized_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    duplicate_canonical_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    self_referencing_canonicals: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    missing_canonical_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    canonical_errors: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    robots_blocked_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    x_robots_tag_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    # ============================================================
    # REDIRECT METRICS
    # ============================================================

    redirects_found: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    permanent_redirects: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    temporary_redirects: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    redirect_chains: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    redirect_loops: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    broken_redirects: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    # ============================================================
    # SITEMAP
    # ============================================================

    sitemap_found: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    sitemap_valid: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    sitemap_url: Mapped[str | None] = mapped_column(
        String(500),
    )

    sitemap_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    sitemap_errors: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    orphan_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    # ============================================================
    # ROBOTS.TXT
    # ============================================================

    robots_txt_found: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    robots_txt_valid: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    robots_disallow_rules: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    robots_allow_rules: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    robots_crawl_delay: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    # ============================================================
    # LINK METRICS
    # ============================================================

    internal_links: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    external_links: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    broken_internal_links: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    broken_external_links: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    orphan_internal_links: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    nofollow_internal_links: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    nofollow_external_links: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    average_internal_links: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    average_external_links: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    # ============================================================
    # OVERALL SEO SCORES
    # ============================================================

    overall_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    technical_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    crawl_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    indexability_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    architecture_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    url_structure_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    link_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )
    
        # ============================================================
    # TECHNICAL SEO
    # ============================================================

    broken_links: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    broken_images: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    duplicate_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    soft_404_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    server_error_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    client_error_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    pages_without_html_lang: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    pages_with_inline_css: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    pages_with_inline_js: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    pages_with_large_dom: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    html_validation_errors: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    html_validation_warnings: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    # ============================================================
    # TITLE TAG ANALYSIS
    # ============================================================

    total_titles: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    missing_titles: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    duplicate_titles: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    multiple_titles: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    short_titles: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    long_titles: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    keyword_missing_in_title: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    title_pixel_overflow: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    average_title_length: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    title_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    # ============================================================
    # META DESCRIPTION ANALYSIS
    # ============================================================

    total_meta_descriptions: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    missing_meta_descriptions: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    duplicate_meta_descriptions: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    short_meta_descriptions: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    long_meta_descriptions: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    keyword_missing_in_description: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    average_meta_description_length: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    meta_description_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    # ============================================================
    # HEADING STRUCTURE
    # ============================================================

    pages_with_h1: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    missing_h1: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    multiple_h1: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    empty_h1: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    duplicate_h1: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    pages_without_h2: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    average_h2_count: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    average_h3_count: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    improper_heading_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    heading_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    # ============================================================
    # CANONICAL ANALYSIS
    # ============================================================

    canonical_present: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    canonical_missing: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    canonical_invalid: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    canonical_to_redirect: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    canonical_to_404: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    canonical_cross_domain: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    canonical_conflicts: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    canonical_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    # ============================================================
    # ROBOTS META TAGS
    # ============================================================

    meta_noindex_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    meta_nofollow_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    meta_noarchive_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    meta_nosnippet_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    conflicting_robot_directives: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    robots_meta_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )
    
        # ============================================================
    # DUPLICATE CONTENT ANALYSIS
    # ============================================================

    duplicate_content_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    near_duplicate_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    exact_duplicate_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    duplicate_title_and_description: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    duplicate_h1_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    duplicate_canonical_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    duplicate_slug_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    duplicate_image_alt_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    duplicate_content_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    # ============================================================
    # CONTENT QUALITY
    # ============================================================

    thin_content_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    empty_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    low_word_count_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    high_word_count_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    average_word_count: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    average_readability_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    keyword_stuffed_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    missing_primary_keyword: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    content_quality_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    # ============================================================
    # PAGINATION
    # ============================================================

    paginated_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    pagination_errors: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    rel_next_found: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    rel_prev_found: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    broken_pagination: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    pagination_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    # ============================================================
    # BREADCRUMBS
    # ============================================================

    breadcrumb_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    missing_breadcrumbs: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    breadcrumb_schema_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    broken_breadcrumbs: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    breadcrumb_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    # ============================================================
    # OPEN GRAPH
    # ============================================================

    og_title_present: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    og_description_present: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    og_image_present: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    og_url_present: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    og_type_present: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    missing_open_graph: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    open_graph_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    # ============================================================
    # TWITTER CARDS
    # ============================================================

    twitter_card_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    twitter_title_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    twitter_description_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    twitter_image_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    missing_twitter_cards: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    twitter_card_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    # ============================================================
    # FAVICON ANALYSIS
    # ============================================================

    favicon_found: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    favicon_missing: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    apple_touch_icon_found: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    manifest_found: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    favicon_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    # ============================================================
    # MOBILE FRIENDLINESS
    # ============================================================

    mobile_friendly_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    mobile_unfriendly_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    responsive_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    viewport_meta_present: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    clickable_elements_too_close: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    text_too_small: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    horizontal_scroll_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    mobile_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    # ============================================================
    # ACCESSIBILITY
    # ============================================================

    images_missing_alt: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    empty_alt_attributes: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    missing_form_labels: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    missing_aria_labels: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    low_contrast_elements: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    missing_lang_attribute: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    accessibility_errors: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    accessibility_warnings: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    accessibility_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )
    
        # ============================================================
    # CONTENT SEO
    # ============================================================

    total_words: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    unique_words: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    average_words_per_page: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    shortest_page_words: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    longest_page_words: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    average_sentence_length: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    average_paragraph_length: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    reading_ease_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    reading_grade_level: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    content_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    # ============================================================
    # KEYWORD ANALYSIS
    # ============================================================

    primary_keyword_found: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    primary_keyword_density: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    secondary_keyword_density: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    keyword_in_title: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    keyword_in_h1: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    keyword_in_url: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    keyword_in_meta_description: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    keyword_in_first_paragraph: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    keyword_in_image_alt: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    keyword_stuffing_detected: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    keyword_variations_found: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    keyword_prominence_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    keyword_distribution_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    keyword_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    # ============================================================
    # NLP & ENTITY ANALYSIS
    # ============================================================

    entities_detected: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    unique_entities: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    people_entities: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    organisation_entities: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    location_entities: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    product_entities: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    event_entities: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    semantic_relevance_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    entity_coverage_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    nlp_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    # ============================================================
    # AI CONTENT ANALYSIS
    # ============================================================

    ai_generated_content_detected: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    ai_content_percentage: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    human_content_percentage: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    ai_content_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    originality_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    plagiarism_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    # ============================================================
    # TOPICAL AUTHORITY
    # ============================================================

    topic_clusters: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    pillar_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    supporting_articles: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    topic_depth_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    topical_authority_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    semantic_keyword_coverage: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    # ============================================================
    # CONTENT FRESHNESS
    # ============================================================

    recently_updated_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    outdated_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    pages_without_last_modified: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    average_content_age_days: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    freshness_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    # ============================================================
    # INTERNAL CONTENT STRUCTURE
    # ============================================================

    cornerstone_content_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    topic_cluster_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    uncategorised_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    content_orphans: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    internal_topic_cluster_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    # ============================================================
    # EEAT (Experience • Expertise • Authoritativeness • Trust)
    # ============================================================

    author_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    pages_with_author_bio: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    pages_with_author_schema: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    about_page_found: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    contact_page_found: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    privacy_policy_found: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    terms_page_found: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    editorial_policy_found: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    reviewer_information_found: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    references_found: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    citations_found: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    external_sources_found: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    trust_signals_found: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    experience_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    expertise_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    authoritativeness_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    trustworthiness_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    eeat_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )
    
        # ============================================================
    # LOCAL SEO
    # ============================================================

    local_seo_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    service_area: Mapped[str | None] = mapped_column(
        String(255),
    )

    business_name: Mapped[str | None] = mapped_column(
        String(255),
    )

    business_phone: Mapped[str | None] = mapped_column(
        String(100),
    )

    business_email: Mapped[str | None] = mapped_column(
        String(255),
    )

    business_address: Mapped[str | None] = mapped_column(
        String(500),
    )

    city: Mapped[str | None] = mapped_column(
        String(150),
    )

    state: Mapped[str | None] = mapped_column(
        String(150),
    )

    postcode: Mapped[str | None] = mapped_column(
        String(50),
    )

    latitude: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    longitude: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    # ============================================================
    # GOOGLE BUSINESS PROFILE
    # ============================================================

    gbp_detected: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    gbp_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    gbp_category_present: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    gbp_description_present: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    gbp_services_present: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    gbp_products_present: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    gbp_photos_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    gbp_posts_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    gbp_questions_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    gbp_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    # ============================================================
    # NAP CONSISTENCY
    # ============================================================

    nap_consistent: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    name_consistent: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    address_consistent: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    phone_consistent: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    nap_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    # ============================================================
    # REVIEWS & REPUTATION
    # ============================================================

    review_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    average_rating: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    five_star_reviews: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    four_star_reviews: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    three_star_reviews: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    two_star_reviews: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    one_star_reviews: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    replied_reviews: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    unanswered_reviews: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    reputation_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    # ============================================================
    # LOCAL CITATIONS
    # ============================================================

    total_citations: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    consistent_citations: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    inconsistent_citations: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    missing_citations: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    duplicate_citations: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    citation_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    # ============================================================
    # SCHEMA.ORG
    # ============================================================

    schema_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    schema_found: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    valid_schema: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    invalid_schema: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    schema_errors: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    schema_warnings: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    organization_schema: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    local_business_schema: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    article_schema: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    faq_schema: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    breadcrumb_schema: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    review_schema: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    product_schema: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    service_schema: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    website_schema: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    person_schema: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    rich_results_eligible: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    rich_results_errors: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    rich_results_warnings: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    # ============================================================
    # AI SEARCH OPTIMISATION
    # ============================================================

    ai_search_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    llms_txt_found: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    llms_txt_valid: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    ai_summary_available: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    entity_optimisation_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    answer_engine_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    conversational_content_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    faq_coverage_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    semantic_search_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    knowledge_graph_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    ai_citation_probability: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    chatgpt_readiness_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    gemini_readiness_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    claude_readiness_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    perplexity_readiness_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    copilot_readiness_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    ai_visibility_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )
    
        # ============================================================
    # CORE WEB VITALS
    # ============================================================

    core_web_vitals_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    lcp: Mapped[float] = mapped_column(
        Float,
        default=0,
        doc="Largest Contentful Paint (seconds)",
    )

    cls: Mapped[float] = mapped_column(
        Float,
        default=0,
        doc="Cumulative Layout Shift",
    )

    inp: Mapped[float] = mapped_column(
        Float,
        default=0,
        doc="Interaction to Next Paint",
    )

    fcp: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    ttfb: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    speed_index: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    total_blocking_time: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    pages_passing_cwv: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    pages_failing_cwv: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    # ============================================================
    # LIGHTHOUSE SCORES
    # ============================================================

    lighthouse_performance: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    lighthouse_accessibility: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    lighthouse_best_practices: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    lighthouse_seo: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    lighthouse_pwa: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    # ============================================================
    # PERFORMANCE ANALYSIS
    # ============================================================

    performance_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    average_load_time: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    html_size_kb: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    css_size_kb: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    javascript_size_kb: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    image_size_kb: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    font_size_kb: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    transfer_size_kb: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    dom_content_loaded: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    fully_loaded_time: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    # ============================================================
    # IMAGE SEO
    # ============================================================

    total_images: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    images_with_alt: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    images_missing_alt: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    images_over_100kb: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    images_over_500kb: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    webp_images: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    avif_images: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    lazy_loaded_images: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    broken_images_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    image_seo_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    # ============================================================
    # CSS OPTIMISATION
    # ============================================================

    total_css_files: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    unused_css_percentage: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    minified_css: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    render_blocking_css: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    css_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    # ============================================================
    # JAVASCRIPT OPTIMISATION
    # ============================================================

    total_js_files: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    unused_js_percentage: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    minified_js: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    deferred_js_files: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    async_js_files: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    render_blocking_js: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    javascript_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    # ============================================================
    # RESOURCE OPTIMISATION
    # ============================================================

    gzip_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    brotli_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    http2_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    http3_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    browser_caching_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    cdn_detected: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    preload_used: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    preconnect_used: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    dns_prefetch_used: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    resource_optimization_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    # ============================================================
    # SECURITY
    # ============================================================

    security_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    https_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    mixed_content_found: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    hsts_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    csp_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    x_frame_options: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    x_content_type_options: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    referrer_policy: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    permissions_policy: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    secure_cookies: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    malware_detected: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    phishing_detected: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    ssl_grade: Mapped[str | None] = mapped_column(
        String(10),
    )

    security_headers_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )
    
        # ============================================================
    # BACKLINK ANALYSIS
    # ============================================================

    backlink_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    total_backlinks: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    referring_domains: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    referring_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    dofollow_backlinks: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    nofollow_backlinks: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    sponsored_backlinks: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    ugc_backlinks: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    image_backlinks: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    homepage_backlinks: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    deep_page_backlinks: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    lost_backlinks: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    new_backlinks: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    toxic_backlinks: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    broken_backlinks: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    average_domain_authority: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    average_page_authority: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    # ============================================================
    # ANCHOR TEXT ANALYSIS
    # ============================================================

    branded_anchor_links: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    exact_match_anchor_links: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    partial_match_anchor_links: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    generic_anchor_links: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    naked_url_anchor_links: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    image_anchor_links: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    anchor_diversity_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    over_optimised_anchor_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    # ============================================================
    # INTERNAL LINK ARCHITECTURE
    # ============================================================

    internal_link_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    average_internal_links_per_page: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    orphan_pages_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    deeply_nested_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    pages_with_low_internal_links: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    pages_with_high_internal_links: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    crawl_depth_average: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    maximum_crawl_depth: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    click_depth_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    # ============================================================
    # XML SITEMAP DETAILS
    # ============================================================

    sitemap_index_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    xml_sitemap_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    sitemap_urls_submitted: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    sitemap_urls_indexed: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    sitemap_last_updated: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    sitemap_compression_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    sitemap_image_entries: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    sitemap_video_entries: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    sitemap_news_entries: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    sitemap_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    # ============================================================
    # GOOGLE SEARCH CONSOLE
    # ============================================================

    gsc_connected: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    gsc_total_clicks: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    gsc_total_impressions: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    gsc_average_ctr: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    gsc_average_position: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    gsc_indexed_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    gsc_excluded_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    gsc_valid_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    gsc_errors: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    gsc_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    # ============================================================
    # GOOGLE ANALYTICS 4
    # ============================================================

    ga4_connected: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    ga4_users: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    ga4_new_users: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    ga4_sessions: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    ga4_engaged_sessions: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    ga4_bounce_rate: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    ga4_engagement_rate: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    ga4_average_session_duration: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    ga4_conversions: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    ga4_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    # ============================================================
    # BING WEBMASTER TOOLS
    # ============================================================

    bing_connected: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    bing_clicks: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    bing_impressions: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    bing_average_position: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    bing_indexed_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    bing_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    # ============================================================
    # HISTORICAL SEO TRENDS
    # ============================================================

    previous_overall_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    score_change: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    previous_keyword_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    previous_backlink_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    previous_indexed_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    trend_direction: Mapped[str | None] = mapped_column(
        String(20),
    )

    trend_summary: Mapped[str | None] = mapped_column(
        Text,
    )

    growth_percentage: Mapped[float] = mapped_column(
        Float,
        default=0,
    )
    
        # ============================================================
    # COMPETITOR ANALYSIS
    # ============================================================

    competitor_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    competitors_analysed: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    competitor_average_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    ranking_gap: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    keyword_gap: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    backlink_gap: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    content_gap: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    authority_gap: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    competitor_visibility_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    competitor_opportunity_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    # ============================================================
    # KEYWORD RANK TRACKING
    # ============================================================

    tracked_keywords: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    keywords_top3: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    keywords_top10: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    keywords_top20: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    keywords_top50: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    keywords_top100: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    average_keyword_position: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    keyword_visibility_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    keyword_growth_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    # ============================================================
    # SERP FEATURES
    # ============================================================

    featured_snippets: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    ai_overviews: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    people_also_ask: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    local_pack: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    image_pack: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    video_results: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    shopping_results: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    knowledge_panel: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    faq_results: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    serp_feature_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    # ============================================================
    # SOCIAL SIGNALS
    # ============================================================

    social_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    facebook_present: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    instagram_present: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    linkedin_present: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    x_present: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    youtube_present: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    pinterest_present: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    tiktok_present: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    social_profiles_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    social_schema_present: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    # ============================================================
    # CONVERSION OPTIMISATION
    # ============================================================

    cro_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    contact_form_found: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    phone_number_visible: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    email_visible: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    call_to_action_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    trust_badges_found: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    testimonials_found: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    live_chat_found: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    booking_system_found: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    ecommerce_detected: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    checkout_https: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    conversion_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    # ============================================================
    # AUDIT REPORT SUMMARY
    # ============================================================

    critical_issues: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    high_priority_issues: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    medium_priority_issues: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    low_priority_issues: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    passed_checks: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    failed_checks: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    warning_checks: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    informational_checks: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    audit_summary: Mapped[str | None] = mapped_column(
        Text,
    )

    ai_recommendations: Mapped[str | None] = mapped_column(
        Text,
    )

    executive_summary: Mapped[str | None] = mapped_column(
        Text,
    )
    
        # ============================================================
    # AI ENGINE
    # ============================================================

    ai_engine_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    ai_provider: Mapped[str | None] = mapped_column(
        String(100),
    )

    ai_model: Mapped[str | None] = mapped_column(
        String(150),
    )

    ai_analysis_version: Mapped[str | None] = mapped_column(
        String(50),
    )

    ai_prompt_version: Mapped[str | None] = mapped_column(
        String(50),
    )

    ai_confidence_score: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    ai_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    ai_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    ai_processing_seconds: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    ai_analysis_status: Mapped[str | None] = mapped_column(
        String(50),
    )

    # ============================================================
    # TOKEN USAGE
    # ============================================================

    prompt_tokens: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    completion_tokens: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    total_tokens: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    cached_tokens: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    estimated_cost: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    # ============================================================
    # AI AGENTS
    # ============================================================

    total_agents: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    completed_agents: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    failed_agents: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    skipped_agents: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    running_agents: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    agent_success_rate: Mapped[float] = mapped_column(
        Float,
        default=0,
    )

    # ============================================================
    # BACKGROUND JOB
    # ============================================================

    job_id: Mapped[str | None] = mapped_column(
        String(120),
        index=True,
    )

    queue_name: Mapped[str | None] = mapped_column(
        String(80),
    )

    worker_name: Mapped[str | None] = mapped_column(
        String(100),
    )

    retry_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    max_retries: Mapped[int] = mapped_column(
        Integer,
        default=3,
    )

    job_priority: Mapped[int] = mapped_column(
        Integer,
        default=5,
    )

    job_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    job_finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    # ============================================================
    # CACHE
    # ============================================================

    cache_key: Mapped[str | None] = mapped_column(
        String(255),
    )

    cache_hit: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    cache_ttl_seconds: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    cache_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    # ============================================================
    # EXPORTS
    # ============================================================

    pdf_generated: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    excel_generated: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    csv_generated: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    json_generated: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    last_export_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    export_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    # ============================================================
    # NOTIFICATIONS
    # ============================================================

    email_sent: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    slack_sent: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    webhook_sent: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    notification_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    last_notification_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    # ============================================================
    # SYSTEM METADATA
    # ============================================================

    audit_version: Mapped[str | None] = mapped_column(
        String(30),
    )

    engine_version: Mapped[str | None] = mapped_column(
        String(30),
    )

    crawler_version: Mapped[str | None] = mapped_column(
        String(30),
    )

    api_version: Mapped[str | None] = mapped_column(
        String(30),
    )

    environment: Mapped[str | None] = mapped_column(
        String(30),
    )

    server_hostname: Mapped[str | None] = mapped_column(
        String(255),
    )

    execution_node: Mapped[str | None] = mapped_column(
        String(100),
    )

    metadata_json: Mapped[dict | None] = mapped_column(
        JSON,
    )

    audit_log: Mapped[dict | None] = mapped_column(
        JSON,
    )

    ai_raw_response: Mapped[dict | None] = mapped_column(
        JSON,
    )

    crawler_statistics: Mapped[dict | None] = mapped_column(
        JSON,
    )
    
        # ============================================================
    # COMPUTED PROPERTIES
    # ============================================================

    @property
    def is_finished(self) -> bool:
        return self.status in (
            AuditStatus.COMPLETED,
            AuditStatus.FAILED,
            AuditStatus.CANCELLED,
        )

    @property
    def is_running(self) -> bool:
        return self.status == AuditStatus.RUNNING

    @property
    def is_pending(self) -> bool:
        return self.status in (
            AuditStatus.PENDING,
            AuditStatus.QUEUED,
        )

    @property
    def completion_percentage(self) -> float:
        return round(float(self.progress or 0), 2)

    @property
    def duration_seconds(self) -> float:
        if self.started_at and self.completed_at:
            return (
                self.completed_at - self.started_at
            ).total_seconds()
        return float(self.duration or 0)

    # ============================================================
    # STATUS HELPERS
    # ============================================================

    def mark_queued(self) -> None:
        self.status = AuditStatus.QUEUED
        self.progress = 0

    def mark_running(self) -> None:
        self.status = AuditStatus.RUNNING
        self.started_at = datetime.utcnow()
        self.progress = 1

    def update_progress(self, progress: float) -> None:
        self.progress = max(0, min(progress, 100))

    def mark_completed(self) -> None:
        self.status = AuditStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.progress = 100

    def mark_failed(self, message: str | None = None) -> None:
        self.status = AuditStatus.FAILED
        self.completed_at = datetime.utcnow()

        if message:
            self.error_message = message

    def mark_cancelled(self) -> None:
        self.status = AuditStatus.CANCELLED
        self.completed_at = datetime.utcnow()

    # ============================================================
    # SCORE CALCULATION
    # ============================================================

    def calculate_overall_score(self) -> float:

        scores = [
            self.technical_score,
            self.content_score,
            self.eeat_score,
            self.local_seo_score,
            self.schema_score,
            self.performance_score,
            self.core_web_vitals_score,
            self.security_score,
            self.backlink_score,
            self.ai_search_score,
        ]

        values = [
            float(score)
            for score in scores
            if score is not None
        ]

        if not values:
            return 0.0

        self.overall_score = round(
            sum(values) / len(values),
            2,
        )

        return self.overall_score

    # ============================================================
    # EXECUTIVE SUMMARY
    # ============================================================

    def generate_summary(self) -> str:

        return (
            f"Audit Score: {self.overall_score}/100 | "
            f"Critical Issues: {self.critical_issues} | "
            f"High: {self.high_priority_issues} | "
            f"Warnings: {self.warning_checks}"
        )

    # ============================================================
    # SERIALIZATION
    # ============================================================

    def to_dict(self) -> dict:

        result = {}

        for column in self.__table__.columns:

            value = getattr(self, column.name)

            if isinstance(value, datetime):
                value = value.isoformat()

            elif isinstance(value, Enum):
                value = value.value

            result[column.name] = value

        return result

    # ============================================================
    # API RESPONSE
    # ============================================================

    def to_api_response(self) -> dict:

        return {
            "id": self.id,
            "status": self.status.value,
            "website": self.website,
            "overall_score": self.overall_score,
            "progress": self.progress,
            "completed": self.is_finished,
            "summary": self.generate_summary(),
        }

    # ============================================================
    # RESET
    # ============================================================

    def reset_results(self) -> None:

        self.progress = 0
        self.overall_score = 0
        self.error_message = None
        self.warning_message = None

    # ============================================================
    # VALIDATION
    # ============================================================

    def validate(self) -> list[str]:

        errors: list[str] = []

        if not self.website:
            errors.append("Website URL is required.")

        if self.progress < 0 or self.progress > 100:
            errors.append("Progress must be between 0 and 100.")

        return errors

    # ============================================================
    # STRING REPRESENTATIONS
    # ============================================================

    def __repr__(self) -> str:

        return (
            f"<Audit(id={self.id}, "
            f"website='{self.website}', "
            f"status='{self.status.value}', "
            f"score={self.overall_score})>"
        )

    def __str__(self) -> str:
        return self.__repr__()
        
            # ============================================================
    # ORM UTILITIES
    # ============================================================

    @classmethod
    def active_query(cls):
        return select(cls).where(
            cls.status.in_(
                [
                    AuditStatus.PENDING,
                    AuditStatus.QUEUED,
                    AuditStatus.RUNNING,
                ]
            )
        )

    @classmethod
    def completed_query(cls):
        return select(cls).where(
            cls.status == AuditStatus.COMPLETED
        )

    @classmethod
    def failed_query(cls):
        return select(cls).where(
            cls.status == AuditStatus.FAILED
        )

    @classmethod
    def recent_query(cls, limit: int = 20):
        return (
            select(cls)
            .order_by(cls.created_at.desc())
            .limit(limit)
        )

    # ============================================================
    # BUSINESS HELPERS
    # ============================================================

    @property
    def success_rate(self) -> float:
        total = self.passed_checks + self.failed_checks

        if total == 0:
            return 0.0

        return round(
            (self.passed_checks / total) * 100,
            2,
        )

    @property
    def issue_count(self) -> int:
        return (
            self.critical_issues
            + self.high_priority_issues
            + self.medium_priority_issues
            + self.low_priority_issues
        )

    @property
    def has_errors(self) -> bool:
        return self.issue_count > 0

    @property
    def is_successful(self) -> bool:
        return (
            self.status == AuditStatus.COMPLETED
            and self.error_message is None
        )

    # ============================================================
    # MODEL HELPERS
    # ============================================================

    def clone(self):

        copy = Audit()

        for column in self.__table__.columns:

            if column.name in (
                "id",
                "created_at",
                "updated_at",
            ):
                continue

            setattr(
                copy,
                column.name,
                getattr(self, column.name),
            )

        copy.status = AuditStatus.PENDING
        copy.progress = 0

        return copy

    def touch(self):
        self.updated_at = datetime.utcnow()

    # ============================================================
    # SQLALCHEMY EVENTS
    # ============================================================

    @staticmethod
    def before_insert(mapper, connection, target):

        target.created_at = datetime.utcnow()
        target.updated_at = datetime.utcnow()

        if target.progress is None:
            target.progress = 0

        if target.status is None:
            target.status = AuditStatus.PENDING

    @staticmethod
    def before_update(mapper, connection, target):

        target.updated_at = datetime.utcnow()
        
        __table_args__ = (

        Index("ix_audit_status", "status"),

        Index("ix_audit_company", "company_id"),

        Index("ix_audit_client", "client_id"),

        Index("ix_audit_user", "user_id"),

        Index("ix_audit_created", "created_at"),

        Index("ix_audit_completed", "completed_at"),

        Index("ix_audit_score", "overall_score"),

        Index("ix_audit_domain", "domain"),

        Index("ix_audit_keyword", "keywords"),

        Index(
            "ix_audit_company_status",
            "company_id",
            "status",
        ),

        Index(
            "ix_audit_client_status",
            "client_id",
            "status",
        ),

        Index(
            "ix_audit_company_created",
            "company_id",
            "created_at",
        ),

        CheckConstraint(
            "progress >= 0 AND progress <= 100",
            name="ck_audit_progress",
        ),

        CheckConstraint(
            "overall_score >= 0 AND overall_score <= 100",
            name="ck_audit_score",
        ),

    )
    
        event.listen(
        Audit,
        "before_insert",
        Audit.before_insert,
    )

        event.listen(
        Audit,
        "before_update",
        Audit.before_update,
    )
    
    reports = relationship(
    "Report",
    back_populates="audit",
    cascade="all, delete-orphan",
    )
   
    