from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from typing import Any
import re

from PIL import Image, ImageDraw, ImageFont
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column

from api.deps.current_user import get_current_user
from database.database import engine
from database.session import get_db
from models.base import BaseModel as DBBaseModel
from models.user import User

router = APIRouter(prefix="/api/content-automation", tags=["Content Automation"])


class ContentArticle(DBBaseModel):
    __tablename__ = "content_articles"

    company_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    plan_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    day_number: Mapped[int] = mapped_column(nullable=False, default=1)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    keyword: Mapped[str] = mapped_column(String(500), nullable=False)
    article_html: Mapped[str] = mapped_column(Text, nullable=False)
    meta_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    meta_description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    slug: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="written", index=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    wordpress_site: Mapped[str | None] = mapped_column(String(500), nullable=True)
    wordpress_post_id: Mapped[int | None] = mapped_column(nullable=True)
    wordpress_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ArticleCreate(BaseModel):
    plan_id: str | None = None
    day_number: int = Field(ge=1, le=90)
    title: str = Field(min_length=3, max_length=500)
    keyword: str = Field(min_length=1, max_length=500)
    article_html: str = Field(min_length=100)
    meta_title: str | None = Field(default=None, max_length=500)
    meta_description: str | None = Field(default=None, max_length=1000)
    slug: str | None = Field(default=None, max_length=500)


class WordPressPublishRequest(BaseModel):
    wordpress_site: HttpUrl
    wordpress_username: str = Field(min_length=1, max_length=255)
    wordpress_application_password: str = Field(min_length=1, max_length=255)
    status: str = Field(default="future", pattern="^(draft|publish|future)$")
    scheduled_at: datetime | None = None
    category_ids: list[int] = Field(default_factory=list)
    tag_ids: list[int] = Field(default_factory=list)
    author_id: int | None = None


def _scope(user: User):
    if getattr(user, "company_id", None):
        return ContentArticle.company_id == str(user.company_id)
    return ContentArticle.created_by == str(user.id)


def _site(value: str) -> str:
    parsed = urlparse(value.rstrip("/"))
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=400, detail="Enter a valid WordPress site URL.")
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/') }".rstrip("/")


def _slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value[:80] or "boost-rankers-featured-image"


def _font(size: int, bold: bool = False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _build_featured_image(title: str, keyword: str) -> bytes:
    """Create a deterministic, non-empty 1600x900 branded PNG without an image API."""
    width, height = 1600, 900
    image = Image.new("RGB", (width, height), (12, 20, 38))
    pixels = image.load()
    seed = sum(ord(ch) for ch in f"{title}|{keyword}") % 360
    for y in range(height):
        for x in range(width):
            t = (x + y) / (width + height)
            pixels[x, y] = (
                int(10 + 18 * t),
                int(20 + 24 * t),
                int(38 + 38 * t),
            )

    draw = ImageDraw.Draw(image, "RGBA")
    # Branded geometric accents.
    draw.rounded_rectangle((90, 80, 1510, 820), radius=42, outline=(251, 210, 11, 180), width=4)
    draw.ellipse((1120, -140, 1740, 480), fill=(251, 210, 11, 42))
    draw.ellipse((-180, 600, 500, 1280), fill=(16, 185, 129, 30))
    draw.rounded_rectangle((120, 130, 1480, 770), radius=32, fill=(0, 0, 0, 35))

    title_font = _font(68, bold=True)
    keyword_font = _font(30, bold=False)
    brand_font = _font(26, bold=True)

    def wrap(text: str, font, max_chars: int = 34):
        words = text.split()
        lines, current = [], ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if len(candidate) > max_chars and current:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)
        return lines[:5]

    lines = wrap(title, title_font)
    y = 260
    for line in lines:
        draw.text((150, y), line, font=title_font, fill=(255, 255, 255, 255))
        y += 82

    draw.text((150, 680), f"Primary keyword: {keyword[:110]}", font=keyword_font, fill=(210, 220, 235, 255))
    draw.text((150, 735), "BOOST RANKERS · AI SEO OS", font=brand_font, fill=(251, 210, 11, 255))

    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


async def _upload_featured_image(client: httpx.AsyncClient, site: str, auth: tuple[str, str], title: str, keyword: str) -> dict[str, Any]:
    image_bytes = _build_featured_image(title, keyword)
    filename = f"{_slugify(title)}.png"
    response = await client.post(
        f"{site}/wp-json/wp/v2/media",
        content=image_bytes,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "image/png",
        },
        auth=auth,
    )
    if response.status_code >= 400:
        try:
            detail = response.json().get("message", response.text)
        except Exception:
            detail = response.text
        raise HTTPException(status_code=502, detail=f"WordPress rejected the featured image upload (HTTP {response.status_code}): {detail}")
    media = response.json()
    media_id = media.get("id")
    if not media_id:
        raise HTTPException(status_code=502, detail="WordPress accepted the image but returned no media ID.")

    # Set accessible alt text using the article title.
    alt_response = await client.post(
        f"{site}/wp-json/wp/v2/media/{int(media_id)}",
        json={"alt_text": title[:500]},
        auth=auth,
    )
    if alt_response.status_code >= 400:
        # The featured image itself is valid; do not fail publication only because
        # a secondary alt-text update was rejected.
        pass

    return {
        "id": int(media_id),
        "url": str(media.get("source_url") or media.get("guid", {}).get("rendered") or ""),
    }


async def _apply_seo_metadata(client: httpx.AsyncClient, site: str, auth: tuple[str, str], post_id: int, meta_title: str, meta_description: str, focus_keyphrase: str) -> dict[str, Any]:
    status_response = await client.get(f"{site}/wp-json/boost-rankers/v1/seo-meta/status", auth=auth)
    if status_response.status_code == 404:
        raise HTTPException(
            status_code=424,
            detail="WordPress SEO Bridge is not installed. Install the Boost Rankers SEO Bridge plugin on the WordPress site before publishing so SEO title, meta description, and focus keyphrase are saved automatically.",
        )
    if status_response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Could not verify the WordPress SEO Bridge (HTTP {status_response.status_code}).")

    response = await client.post(
        f"{site}/wp-json/boost-rankers/v1/seo-meta/{post_id}",
        json={
            "seo_title": meta_title[:500],
            "meta_description": meta_description[:1000],
            "focus_keyphrase": focus_keyphrase[:500],
        },
        auth=auth,
    )
    if response.status_code >= 400:
        try:
            detail = response.json().get("message", response.text)
        except Exception:
            detail = response.text
        raise HTTPException(status_code=502, detail=f"WordPress SEO metadata could not be saved (HTTP {response.status_code}): {detail}")
    result = response.json()
    return {"applied": bool(result.get("success", True)), "response": result}


@router.on_event("startup")
def _ensure_table() -> None:
    ContentArticle.__table__.create(bind=engine, checkfirst=True)


@router.get("/articles")
def list_articles(db=Depends(get_db), current_user: User = Depends(get_current_user)):
    rows = db.scalars(
        select(ContentArticle)
        .where(_scope(current_user))
        .order_by(ContentArticle.day_number.asc(), ContentArticle.created_at.desc())
    ).all()
    return {"success": True, "articles": [_serialize(x) for x in rows]}


@router.post("/articles")
def create_article(data: ArticleCreate, db=Depends(get_db), current_user: User = Depends(get_current_user)):
    article = ContentArticle(
        company_id=str(current_user.company_id) if getattr(current_user, "company_id", None) else None,
        created_by=str(current_user.id),
        updated_by=str(current_user.id),
        **data.model_dump(),
    )
    db.add(article)
    db.commit()
    db.refresh(article)
    return {"success": True, "article": _serialize(article)}


@router.get("/articles/{article_id}")
def get_article(article_id: str, db=Depends(get_db), current_user: User = Depends(get_current_user)):
    article = db.scalar(select(ContentArticle).where(ContentArticle.id == article_id, _scope(current_user)))
    if not article:
        raise HTTPException(status_code=404, detail="Content article not found.")
    return {"success": True, "article": _serialize(article)}


@router.post("/articles/{article_id}/publish/wordpress")
async def publish_article_wordpress(
    article_id: str,
    data: WordPressPublishRequest,
    db=Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    article = db.scalar(select(ContentArticle).where(ContentArticle.id == article_id, _scope(current_user)))
    if not article:
        raise HTTPException(status_code=404, detail="Content article not found.")

    site = _site(str(data.wordpress_site))
    auth = (data.wordpress_username.strip(), data.wordpress_application_password.strip())
    if data.status == "future" and data.scheduled_at is None:
        raise HTTPException(status_code=400, detail="scheduled_at is required for a scheduled WordPress post.")

    payload: dict[str, Any] = {
        "title": article.title,
        "content": article.article_html,
        "status": data.status,
    }
    if article.slug:
        payload["slug"] = article.slug
    if article.meta_description:
        payload["excerpt"] = article.meta_description
    if data.category_ids:
        payload["categories"] = data.category_ids
    if data.tag_ids:
        payload["tags"] = data.tag_ids
    if data.author_id:
        payload["author"] = data.author_id
    if data.scheduled_at is not None:
        scheduled = data.scheduled_at
        if scheduled.tzinfo is None:
            scheduled = scheduled.replace(tzinfo=timezone.utc)
        payload["date"] = scheduled.isoformat()
        payload["date_gmt"] = scheduled.astimezone(timezone.utc).isoformat()

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(45.0, connect=15.0), follow_redirects=True) as client:
            me = await client.get(f"{site}/wp-json/wp/v2/users/me", params={"context": "edit"}, auth=auth)
            if me.status_code >= 400:
                raise HTTPException(status_code=401, detail=f"WordPress authentication failed (HTTP {me.status_code}). Use a WordPress Application Password.")

            # Fail before creating a post if the required SEO bridge is absent.
            bridge = await client.get(f"{site}/wp-json/boost-rankers/v1/seo-meta/status", auth=auth)
            if bridge.status_code == 404:
                raise HTTPException(status_code=424, detail="Install and activate the Boost Rankers SEO Bridge plugin on WordPress. It is required to save SEO title, meta description, and focus keyphrase automatically.")
            if bridge.status_code >= 400:
                raise HTTPException(status_code=502, detail=f"WordPress SEO Bridge check failed (HTTP {bridge.status_code}).")
            try:
                bridge_data = bridge.json()
            except Exception:
                bridge_data = {}
            if not bridge_data.get("yoast_active"):
                raise HTTPException(status_code=424, detail="Yoast SEO is not active on the connected WordPress site. Activate Yoast SEO so Boost Rankers can save the SEO title, meta description, and focus keyphrase.")

            featured = await _upload_featured_image(client, site, auth, article.title, article.keyword)
            payload["featured_media"] = featured["id"]

            response = await client.post(f"{site}/wp-json/wp/v2/posts", json=payload, auth=auth)
            if response.status_code >= 400:
                try:
                    detail = response.json().get("message", response.text)
                except Exception:
                    detail = response.text
                raise HTTPException(status_code=502, detail=f"WordPress rejected the post (HTTP {response.status_code}): {detail}")
            result = response.json()

            seo = await _apply_seo_metadata(
                client,
                site,
                auth,
                int(result["id"]),
                article.meta_title or article.title,
                article.meta_description or article.title,
                article.keyword,
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not connect to WordPress: {exc}") from exc

    article.status = "published" if data.status == "publish" else "scheduled" if data.status == "future" else "draft"
    article.wordpress_site = site
    article.wordpress_post_id = result.get("id")
    article.wordpress_url = result.get("link")
    article.scheduled_at = data.scheduled_at
    article.last_error = None
    if data.status == "publish":
        article.published_at = datetime.now(timezone.utc)
    article.updated_by = str(current_user.id)
    db.commit()
    db.refresh(article)

    return {
        "success": True,
        "message": "WordPress content scheduled successfully." if data.status == "future" else "WordPress content published successfully." if data.status == "publish" else "WordPress draft created successfully.",
        "article": _serialize(article),
        "wordpress": {
            "featured_media_id": featured["id"],
            "featured_image_url": featured["url"],
            "seo_metadata_applied": seo["applied"],
        },
    }


@router.post("/articles/{article_id}/sync-wordpress")
async def sync_wordpress_status(
    article_id: str,
    db=Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Refresh a scheduled article's status from the public WordPress REST API.

    WordPress owns the actual future-post publication through its scheduler.
    This endpoint only observes the real WordPress status and updates our local
    record; it never fabricates a published state.
    """
    article = db.scalar(select(ContentArticle).where(ContentArticle.id == article_id, _scope(current_user)))
    if not article:
        raise HTTPException(status_code=404, detail="Content article not found.")

    if not article.wordpress_site or not article.wordpress_post_id:
        return {"success": True, "changed": False, "article": _serialize(article)}

    if article.status not in {"scheduled", "published"}:
        return {"success": True, "changed": False, "article": _serialize(article)}

    site = _site(article.wordpress_site)
    endpoint = f"{site}/wp-json/wp/v2/posts/{int(article.wordpress_post_id)}"

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=8.0), follow_redirects=True) as client:
            response = await client.get(endpoint)

            if response.status_code == 200:
                remote = response.json()
                remote_status = str(remote.get("status") or "").lower()
                if remote_status == "publish" and article.status != "published":
                    article.status = "published"
                    article.published_at = datetime.now(timezone.utc)
                    article.last_error = None
                    if remote.get("link"):
                        article.wordpress_url = str(remote["link"])
                    article.updated_by = str(current_user.id)
                    db.commit()
                    db.refresh(article)
                    return {"success": True, "changed": True, "article": _serialize(article)}

                # WordPress still reports future: keep the scheduled state.
                if remote_status == "future":
                    article.status = "scheduled"
                    article.last_error = None
                    if remote.get("link"):
                        article.wordpress_url = str(remote["link"])
                    article.updated_by = str(current_user.id)
                    db.commit()
                    db.refresh(article)
                    return {"success": True, "changed": False, "article": _serialize(article)}

                return {"success": True, "changed": False, "remote_status": remote_status, "article": _serialize(article)}

            # A future post is normally not publicly retrievable. Do not mark it
            # failed just because WordPress hides it until publication.
            if response.status_code in {401, 403, 404}:
                return {"success": True, "changed": False, "remote_status": "not_publicly_available", "article": _serialize(article)}

            return {"success": True, "changed": False, "remote_status": f"http_{response.status_code}", "article": _serialize(article)}
    except Exception as exc:
        # Status polling is best-effort. Never turn a temporary network issue
        # into a false publication/failure state.
        return {"success": True, "changed": False, "remote_status": "check_failed", "article": _serialize(article), "check_error": str(exc)}


def _serialize(article: ContentArticle) -> dict[str, Any]:
    return {
        "id": str(article.id),
        "plan_id": article.plan_id,
        "day_number": article.day_number,
        "title": article.title,
        "keyword": article.keyword,
        "article_html": article.article_html,
        "meta_title": article.meta_title,
        "meta_description": article.meta_description,
        "slug": article.slug,
        "status": article.status,
        "scheduled_at": article.scheduled_at.isoformat() if article.scheduled_at else None,
        "wordpress_site": article.wordpress_site,
        "wordpress_post_id": article.wordpress_post_id,
        "wordpress_url": article.wordpress_url,
        "last_error": article.last_error,
        "published_at": article.published_at.isoformat() if article.published_at else None,
    }
