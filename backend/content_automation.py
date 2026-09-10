from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from typing import Any
import base64
import json
import os
import re

from PIL import Image, ImageDraw, ImageFont
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover
    BeautifulSoup = None  # type: ignore[assignment]

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


class WordPressCredentialsRequest(BaseModel):
    wordpress_site: HttpUrl
    wordpress_username: str = Field(min_length=1, max_length=255)
    wordpress_application_password: str = Field(min_length=1, max_length=255)


class InternalLinkInput(BaseModel):
    target_url: HttpUrl
    anchor_text: str = Field(min_length=2, max_length=160)


class WordPressPublishRequest(BaseModel):
    wordpress_site: HttpUrl
    wordpress_username: str = Field(min_length=1, max_length=255)
    wordpress_application_password: str = Field(min_length=1, max_length=255)
    status: str = Field(default="future", pattern="^(draft|publish|future)$")
    scheduled_at: datetime | None = None
    category_ids: list[int] = Field(default_factory=list)
    tag_ids: list[int] = Field(default_factory=list)
    author_id: int | None = None
    internal_links: list[InternalLinkInput] = Field(default_factory=list, max_length=12)


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


def _fallback_client_brand(site: str) -> str:
    """Create a readable client brand from the connected WordPress hostname."""
    host = urlparse(site).netloc.lower().split("@")[-1].split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    labels = host.split(".")
    name = labels[0] if labels else host
    name = re.sub(r"[-_]+", " ", name)
    name = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name)
    return " ".join(name.split()).title() or "Client Website"


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


def _extract_article_text(article_html: str, max_chars: int = 9000) -> str:
    """Extract bounded plain text from the article for visual-context generation."""
    if not article_html:
        return ""
    if BeautifulSoup is not None:
        try:
            soup = BeautifulSoup(article_html, "html.parser")
            for node in soup(["script", "style", "noscript"]):
                node.decompose()
            return " ".join(soup.get_text(" ", strip=True).split())[:max_chars]
        except Exception:
            pass
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", article_html)).strip()[:max_chars]


def _visual_theme(title: str, keyword: str, article_html: str = "") -> str:
    """Infer the service/industry scene from the complete article context."""
    text = f"{title} {keyword} {_extract_article_text(article_html)}".lower()

    theme_rules = (
        ("medical_commercial", (
            "medical cleaning vs commercial cleaning",
            "medical cleaning versus commercial cleaning",
            "medical vs commercial cleaning",
            "medical versus commercial cleaning",
        )),
        ("healthcare", (
            "healthcare", "medical", "hospital", "clinic", "surgery", "patient",
            "health care", "healthcare cleaning", "medical cleaning",
        )),
        ("gym", (
            "gym", "fitness", "workout", "sports centre", "sports center",
            "fitness centre", "fitness center", "exercise",
        )),
        ("school", (
            "school", "student", "classroom", "education", "college", "campus",
            "childcare", "daycare",
        )),
        ("hotel", (
            "hotel", "hospitality", "guest room", "accommodation", "resort",
            "housekeeping", "hotel cleaning",
        )),
        ("industrial", (
            "industrial", "warehouse", "factory", "manufacturing",
            "industrial cleaning", "distribution centre", "distribution center",
        )),
        ("house", (
            "house cleaning", "home cleaning", "residential", "housekeeper",
            "domestic cleaning", "home cleaners", "living room", "bedroom",
            "end of lease", "bond clean", "vacate cleaning", "move out cleaning",
        )),
        ("office", (
            "office", "commercial cleaning", "workplace", "corporate",
            "business cleaning", "workstation", "workspace", "commercial property",
        )),
    )

    for name, terms in theme_rules:
        if any(term in text for term in terms):
            return name

    return "business"


def _industry_visual_direction(theme: str) -> str:
    """Return a service-specific photography direction, not a reusable illustration."""
    directions = {
        "healthcare": (
            "A professional commercial cleaner actively sanitising a modern clinic or "
            "healthcare facility, wearing realistic PPE/gloves, using professional cleaning "
            "equipment, with treatment rooms, hygienic surfaces and clinical details visible."
        ),
        "medical_commercial": (
            "A sophisticated split-scene comparison: one side shows a professional cleaner "
            "sanitising a clinical/medical environment with appropriate PPE and disinfecting "
            "equipment; the other shows a professional cleaner maintaining a modern office. "
            "The two environments should look clearly different and authentic."
        ),
        "gym": (
            "A professional gym cleaner actively disinfecting fitness equipment such as a "
            "treadmill, weights or exercise machines in a premium modern fitness facility. "
            "Show realistic cleaning tools and an authentic working environment."
        ),
        "school": (
            "A professional school cleaner actively cleaning a bright classroom or school "
            "common area, with desks, educational surroundings, hygiene equipment and a "
            "realistic professional cleaning workflow."
        ),
        "hotel": (
            "A professional hospitality cleaner or housekeeper actively preparing a premium "
            "hotel guest room or hospitality area, with realistic linens, surfaces, cleaning "
            "cart and professional equipment."
        ),
        "industrial": (
            "A professional industrial cleaner actively operating commercial cleaning "
            "equipment inside a realistic warehouse, factory or industrial facility, with "
            "appropriate PPE, machinery and large-scale surfaces."
        ),
        "house": (
            "A professional residential cleaner actively performing the specific cleaning "
            "service in a realistic high-quality home interior. Show authentic household "
            "surfaces, cleaning tools and a human cleaner at work."
        ),
        "office": (
            "A professional commercial cleaner actively cleaning a modern corporate office, "
            "wiping desks or workstations with professional spray and microfiber equipment. "
            "Show realistic office furniture, computers, glass partitions and workplace detail."
        ),
        "business": (
            "A professional commercial cleaner actively delivering the service in a realistic "
            "business facility, with visible professional cleaning equipment and a human worker "
            "engaged in the task."
        ),
    }
    return directions.get(theme, directions["business"])


def _image_generation_config() -> tuple[str, str, str] | None:
    """Read optional image-generation configuration without changing existing app settings."""
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None

    model = os.getenv("CONTENT_IMAGE_MODEL", "gpt-image-2").strip() or "gpt-image-2"
    quality = os.getenv("CONTENT_IMAGE_QUALITY", "high").strip().lower()
    if quality not in {"low", "medium", "high", "auto"}:
        quality = "high"
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    return api_key, model, quality, base_url


def _build_ai_image_prompt(
    title: str,
    keyword: str,
    article_html: str,
    client_brand: str,
    theme: str,
) -> str:
    """Create a professional editorial-photo prompt from the actual article topic."""
    article_text = _extract_article_text(article_html, 7000)
    direction = _industry_visual_direction(theme)

    return f"""
Create a premium editorial hero photograph for a professional business blog.

ARTICLE TITLE:
{title}

PRIMARY KEYWORD:
{keyword}

CLIENT BUSINESS:
{client_brand}

INDUSTRY / SERVICE:
{theme.replace("_", " ")}

SERVICE-SPECIFIC SCENE:
{direction}

ARTICLE CONTEXT:
{article_text[:7000]}

CREATIVE DIRECTION:
- Photorealistic commercial photography, not an illustration, cartoon, icon set, vector art,
  flat graphic, 3D render, clipart or generic stock-photo collage.
- Show a real human professional actively performing the relevant cleaning service.
- The person must be naturally integrated into the environment and visibly doing the work,
  not simply standing and smiling at the camera.
- Use realistic professional cleaning tools, PPE where appropriate, natural human anatomy,
  believable hands, realistic skin, fabric and equipment.
- Make the environment clearly match the service described by the article.
- Premium corporate editorial photography suitable for a high-end Australian business website.
- Natural daylight plus realistic interior lighting, shallow depth of field where appropriate,
  subtle cinematic composition, authentic textures, clean premium finish.
- Compose the main human/service action toward the RIGHT 55% of the frame.
- Keep the LEFT 42% visually clean, bright and uncluttered so exact article-title typography
  can be added later by the application.
- Do NOT put any words, letters, logos, watermarks, fake signage, business names or article
  titles inside the generated photograph.
- Do NOT create a generic reusable scene. The environment, tools and activity must reflect
  the specific industry/service and article context.
- Landscape hero composition, approximately 16:9.
- No borders, no infographic panels, no UI elements, no template frame.
""".strip()


async def _generate_ai_featured_image(
    client: httpx.AsyncClient,
    title: str,
    keyword: str,
    article_html: str,
    client_brand: str,
) -> bytes | None:
    """Generate a photorealistic article image when OPENAI_API_KEY is configured.

    Failure is intentionally non-fatal: the existing local generator remains the safe
    fallback so WordPress publishing and all other application features continue to work.
    """
    config = _image_generation_config()
    if config is None:
        return None

    api_key, model, quality, base_url = config
    theme = _visual_theme(title, keyword, article_html)
    prompt = _build_ai_image_prompt(title, keyword, article_html, client_brand, theme)

    payload = {
        "model": model,
        "prompt": prompt,
        "size": "1536x1024",
        "quality": quality,
        "background": "opaque",
        "output_format": "png",
        "n": 1,
    }

    try:
        response = await client.post(
            f"{base_url}/images/generations",
            json=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(120.0, connect=20.0),
        )
        if response.status_code >= 400:
            return None

        data = response.json()
        item = (data.get("data") or [{}])[0]
        encoded = item.get("b64_json")
        if not encoded:
            return None

        image_bytes = base64.b64decode(encoded)
        if not image_bytes:
            return None

        # Validate that the API returned a real decodable image before continuing.
        with Image.open(BytesIO(image_bytes)) as generated:
            generated.load()

        return image_bytes
    except Exception:
        # Image generation is an enhancement. Never turn a temporary provider failure
        # into a WordPress publishing failure.
        return None


def _compose_professional_featured_image(
    generated_bytes: bytes,
    title: str,
    keyword: str,
    client_brand: str,
) -> bytes:
    """Crop the generated photograph and add exact, readable title/brand typography."""
    with Image.open(BytesIO(generated_bytes)) as source:
        image = source.convert("RGB")
        target_w, target_h = 1600, 900
        target_ratio = target_w / target_h
        source_ratio = image.width / image.height

        if source_ratio > target_ratio:
            crop_w = int(image.height * target_ratio)
            left = max(0, (image.width - crop_w) // 2)
            image = image.crop((left, 0, left + crop_w, image.height))
        elif source_ratio < target_ratio:
            crop_h = int(image.width / target_ratio)
            top = max(0, (image.height - crop_h) // 2)
            image = image.crop((0, top, image.width, top + crop_h))

        image = image.resize((target_w, target_h), Image.Resampling.LANCZOS)

    draw = ImageDraw.Draw(image, "RGBA")
    title_font = _font(61, bold=True)
    brand_font = _font(31, bold=True)
    keyword_font = _font(23, bold=False)
    label_font = _font(20, bold=True)

    # Premium dark-to-transparent editorial panel on the left.
    panel = Image.new("RGBA", image.size, (0, 0, 0, 0))
    panel_draw = ImageDraw.Draw(panel, "RGBA")
    for x in range(0, 780, 12):
        alpha = int(205 * max(0.0, 1.0 - x / 820))
        panel_draw.rectangle((x, 0, x + 12, 900), fill=(5, 18, 35, alpha))
    image = Image.alpha_composite(image.convert("RGBA"), panel)
    draw = ImageDraw.Draw(image, "RGBA")

    # Thin brand accent and subtle bottom protection.
    draw.rounded_rectangle((55, 55, 805, 845), radius=28, outline=(255, 255, 255, 80), width=2)
    draw.rectangle((0, 810, 1600, 900), fill=(4, 18, 35, 180))

    # Exact article title: generated text is never trusted to an image model.
    def wrap(text: str, max_chars: int = 28) -> list[str]:
        words = " ".join(text.split()).split()
        lines: list[str] = []
        current = ""
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

    draw.rounded_rectangle((82, 105, 590, 153), radius=20, fill=(14, 107, 151, 230))
    draw.text(
        (105, 114),
        "PROFESSIONAL SERVICE GUIDE",
        font=label_font,
        fill=(255, 255, 255, 255),
    )

    y = 205
    for line in wrap(title):
        draw.text(
            (82, y),
            line,
            font=title_font,
            fill=(255, 255, 255, 255),
            stroke_width=1,
            stroke_fill=(5, 18, 35, 210),
        )
        y += 72

    # Client business name is always exact and visible.
    brand = " ".join(client_brand.split())[:100] or "Client Website"
    draw.text((82, 665), brand, font=brand_font, fill=(255, 214, 50, 255))
    draw.text(
        (82, 714),
        f"Primary keyword: {keyword[:78]}",
        font=keyword_font,
        fill=(235, 243, 249, 235),
    )
    draw.rectangle((82, 770, 330, 776), fill=(255, 214, 50, 255))

    output = BytesIO()
    image.convert("RGB").save(output, format="JPEG", quality=94, optimize=True)
    return output.getvalue()


def _build_featured_image(
    title: str,
    keyword: str,
    article_html: str = "",
    client_brand: str = "",
    ai_image_bytes: bytes | None = None,
) -> bytes:
    """Build a professional featured image while preserving a deterministic fallback."""
    client_brand = " ".join(str(client_brand or "").split())[:120] or "Client Website"

    if ai_image_bytes:
        try:
            return _compose_professional_featured_image(
                ai_image_bytes, title, keyword, client_brand
            )
        except Exception:
            pass

    # Existing local generation remains the fallback for deployments without an
    # OpenAI image key or when the provider is temporarily unavailable.
    return _build_local_fallback_image(title, keyword, article_html, client_brand)


def _draw_cleaner(draw: ImageDraw.ImageDraw, x: int, y: int, scale: float = 1.0) -> None:
    """Draw a compact deterministic fallback cleaner illustration."""
    r = int(25 * scale)
    draw.ellipse((x - r, y - r, x + r, y + r), fill=(242, 194, 155, 255))
    draw.arc(
        (x - r, y - r, x + r, y + r),
        190,
        350,
        fill=(15, 23, 42, 255),
        width=max(2, int(5 * scale)),
    )
    body_w = int(75 * scale)
    body_h = int(120 * scale)
    draw.rounded_rectangle(
        (x - body_w, y + r, x + body_w, y + r + body_h),
        radius=int(18 * scale),
        fill=(30, 144, 132, 255),
    )
    arm_w = max(5, int(14 * scale))
    draw.line(
        (x - body_w + 5 * scale, y + 55 * scale, x - body_w - 55 * scale, y + 115 * scale),
        fill=(242, 194, 155, 255),
        width=arm_w,
    )
    draw.line(
        (x + body_w - 5 * scale, y + 55 * scale, x + body_w + 45 * scale, y + 95 * scale),
        fill=(242, 194, 155, 255),
        width=arm_w,
    )


def _draw_medical_scene(draw: ImageDraw.ImageDraw) -> None:
    draw.rounded_rectangle((900, 190, 1460, 620), radius=28, fill=(230, 242, 250, 255))
    for x in (950, 1070, 1190, 1310):
        for y in (260, 360, 460):
            draw.rounded_rectangle(
                (x, y, x + 70, y + 70), radius=8, fill=(175, 215, 235, 255)
            )
    draw.rectangle((1125, 275, 1235, 390), fill=(30, 144, 132, 255))
    draw.rectangle((1085, 307, 1275, 358), fill=(30, 144, 132, 255))
    _draw_cleaner(draw, 1040, 540, 0.75)


def _draw_split_cleaning_scene(draw: ImageDraw.ImageDraw) -> None:
    draw.rounded_rectangle((860, 180, 1110, 590), radius=22, fill=(228, 241, 248, 255))
    draw.rectangle((955, 250, 1015, 370), fill=(30, 144, 132, 255))
    draw.rectangle((925, 280, 1045, 340), fill=(30, 144, 132, 255))
    draw.rounded_rectangle((1140, 180, 1460, 590), radius=22, fill=(238, 235, 224, 255))
    for x in (1180, 1300):
        draw.rectangle((x, 235, x + 95, 325), fill=(175, 215, 235, 255))
    draw.rectangle((1180, 410, 1395, 435), fill=(101, 76, 55, 255))
    draw.line((1210, 435, 1195, 525), fill=(75, 60, 48, 255), width=9)
    draw.line((1365, 435, 1380, 525), fill=(75, 60, 48, 255), width=9)
    draw.line((1125, 160, 1125, 620), fill=(251, 210, 11, 220), width=6)
    _draw_cleaner(draw, 1060, 560, 0.55)


def _draw_gym_scene(draw: ImageDraw.ImageDraw) -> None:
    draw.line((870, 520, 1060, 520), fill=(60, 70, 82, 255), width=16)
    draw.line((1060, 520, 1110, 390), fill=(60, 70, 82, 255), width=16)
    draw.line((1110, 390, 1210, 390), fill=(60, 70, 82, 255), width=14)
    draw.rectangle((1220, 305, 1430, 325), fill=(75, 60, 48, 255))
    for x in range(1240, 1420, 45):
        draw.line((x, 325, x, 515), fill=(75, 60, 48, 255), width=7)
        draw.rounded_rectangle((x - 18, 420, x + 18, 445), radius=6, fill=(30, 144, 132, 255))
    _draw_cleaner(draw, 1030, 500, 0.55)


def _draw_school_scene(draw: ImageDraw.ImageDraw) -> None:
    draw.rounded_rectangle((890, 185, 1450, 600), radius=28, fill=(245, 238, 222, 255))
    draw.polygon([(850, 190), (1170, 70), (1490, 190)], fill=(30, 144, 132, 255))
    for x in (940, 1100, 1260):
        draw.rectangle((x, 280, x + 95, 370), fill=(175, 215, 235, 255))
    draw.rectangle((1080, 420, 1240, 600), fill=(180, 145, 100, 255))
    _draw_cleaner(draw, 1050, 555, 0.6)


def _draw_office_scene(draw: ImageDraw.ImageDraw) -> None:
    draw.rectangle((875, 190, 1460, 590), fill=(235, 240, 244, 255))
    for x in (920, 1080, 1240):
        draw.rectangle((x, 240, x + 100, 335), fill=(165, 205, 225, 255))
    draw.rectangle((900, 440, 1400, 470), fill=(101, 76, 55, 255))
    for x in (930, 1080, 1230, 1380):
        draw.line((x, 470, x - 10, 575), fill=(70, 60, 50, 255), width=8)
    _draw_cleaner(draw, 1040, 545, 0.52)


def _draw_house_scene(draw: ImageDraw.ImageDraw) -> None:
    draw.polygon([(870, 300), (1160, 95), (1450, 300)], fill=(30, 144, 132, 255))
    draw.rounded_rectangle((900, 290, 1420, 600), radius=18, fill=(245, 239, 224, 255))
    draw.rectangle((1100, 430, 1215, 600), fill=(130, 94, 65, 255))
    for x in (950, 1260):
        draw.rectangle((x, 350, x + 110, 430), fill=(175, 215, 235, 255))
    _draw_cleaner(draw, 1010, 555, 0.55)


def _draw_hotel_scene(draw: ImageDraw.ImageDraw) -> None:
    draw.rounded_rectangle((900, 155, 1430, 605), radius=25, fill=(240, 234, 220, 255))
    draw.rectangle((1120, 330, 1210, 605), fill=(130, 94, 65, 255))
    for x in (950, 1060, 1260, 1370):
        for y in (220, 340, 460):
            draw.rectangle((x, y, x + 70, y + 65), fill=(175, 215, 235, 255))
    draw.rounded_rectangle((920, 490, 1080, 565), radius=12, fill=(255, 255, 255, 255))
    _draw_cleaner(draw, 1280, 545, 0.5)


def _draw_industrial_scene(draw: ImageDraw.ImageDraw) -> None:
    draw.rectangle((880, 260, 1450, 600), fill=(70, 82, 96, 255))
    for x in (930, 1080, 1230, 1380):
        draw.rectangle((x, 350, x + 70, 440), fill=(175, 215, 235, 255))
    draw.ellipse((1230, 465, 1380, 615), fill=(251, 210, 11, 255))
    _draw_cleaner(draw, 1040, 545, 0.5)


def _draw_business_scene(draw: ImageDraw.ImageDraw) -> None:
    draw.rounded_rectangle((900, 170, 1450, 600), radius=28, fill=(235, 240, 244, 255))
    for x, h in ((930, 270), (1050, 210), (1170, 320), (1290, 240)):
        draw.rectangle((x, 600 - h, x + 90, 600), fill=(75, 95, 115, 255))
    _draw_cleaner(draw, 1030, 545, 0.5)


def _build_local_fallback_image(
    title: str,
    keyword: str,
    article_html: str = "",
    client_brand: str = "",
) -> bytes:
    """Deterministic fallback used only when AI image generation is unavailable."""
    width, height = 1600, 900
    theme = _visual_theme(title, keyword, article_html)
    client_brand = " ".join(str(client_brand or "").split())[:120] or "Client Website"

    theme_backgrounds = {
        "healthcare": (12, 30, 43),
        "medical_commercial": (17, 29, 42),
        "gym": (20, 31, 43),
        "school": (25, 35, 45),
        "office": (22, 30, 42),
        "house": (29, 34, 43),
        "hotel": (32, 31, 40),
        "industrial": (25, 31, 38),
        "business": (18, 28, 42),
    }
    scene_drawers = {
        "healthcare": _draw_medical_scene,
        "medical_commercial": _draw_split_cleaning_scene,
        "gym": _draw_gym_scene,
        "school": _draw_school_scene,
        "office": _draw_office_scene,
        "house": _draw_house_scene,
        "hotel": _draw_hotel_scene,
        "industrial": _draw_industrial_scene,
        "business": _draw_business_scene,
    }

    image = Image.new("RGB", (width, height), theme_backgrounds.get(theme, (18, 28, 42)))
    draw = ImageDraw.Draw(image, "RGBA")
    scene_drawers.get(theme, _draw_business_scene)(draw)

    draw.rounded_rectangle((70, 65, 1530, 835), radius=42, outline=(251, 210, 11, 175), width=4)
    draw.rounded_rectangle((90, 95, 805, 805), radius=34, fill=(5, 12, 25, 185))

    title_font = _font(62, bold=True)
    keyword_font = _font(27, bold=False)
    brand_font = _font(25, bold=True)

    def wrap(text: str, max_chars: int = 31):
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

    y = 210
    for line in wrap(title):
        draw.text((135, y), line, font=title_font, fill=(255, 255, 255, 255))
        y += 76

    draw.text(
        (135, 625),
        f"Primary keyword: {keyword[:90]}",
        font=keyword_font,
        fill=(218, 228, 240, 255),
    )
    draw.text((135, 690), client_brand, font=brand_font, fill=(251, 210, 11, 255))

    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


async def _upload_featured_image(
    client: httpx.AsyncClient,
    site: str,
    auth: tuple[str, str],
    title: str,
    keyword: str,
    article_html: str = "",
    client_brand: str = "",
) -> dict[str, Any]:
    ai_image_bytes = await _generate_ai_featured_image(
        client, title, keyword, article_html, client_brand
    )
    image_bytes = _build_featured_image(
        title, keyword, article_html, client_brand, ai_image_bytes
    )
    filename = f"{_slugify(title)}.jpg" if ai_image_bytes else f"{_slugify(title)}.png"
    response = await client.post(
        f"{site}/wp-json/wp/v2/media",
        content=image_bytes,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "image/jpeg" if ai_image_bytes else "image/png",
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


async def _wordpress_content_candidates(
    client: httpx.AsyncClient, site: str, auth: tuple[str, str], current_post_id: int | None = None
) -> list[dict[str, Any]]:
    """Fetch published WordPress pages and posts that are eligible internal-link targets."""
    candidates: list[dict[str, Any]] = []
    for content_type in ("pages", "posts"):
        try:
            response = await client.get(
                f"{site}/wp-json/wp/v2/{content_type}",
                params={
                    "status": "publish",
                    "per_page": 100,
                    "page": 1,
                    "orderby": "modified",
                    "order": "desc",
                    "_fields": "id,link,title,slug,type,modified",
                },
                auth=auth,
            )
        except Exception:
            continue
        if response.status_code >= 400:
            continue
        try:
            rows = response.json()
        except Exception:
            continue
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            item_id = row.get("id")
            if current_post_id is not None and str(item_id) == str(current_post_id):
                continue
            link = str(row.get("link") or "").strip()
            title = str((row.get("title") or {}).get("rendered") or row.get("title") or "").strip()
            if not link or not title:
                continue
            candidates.append({
                "id": item_id,
                "type": "page" if content_type == "pages" else "post",
                "title": title,
                "url": link,
                "slug": str(row.get("slug") or ""),
            })

    # De-duplicate by canonical URL while preserving the freshest API ordering.
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for item in candidates:
        key = item["url"].rstrip("/").lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique[:180]


@router.post("/articles/{article_id}/internal-link-candidates")
async def internal_link_candidates(
    article_id: str,
    data: WordPressCredentialsRequest,
    db=Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    article = db.scalar(select(ContentArticle).where(ContentArticle.id == article_id, _scope(current_user)))
    if not article:
        raise HTTPException(status_code=404, detail="Content article not found.")

    site = _site(str(data.wordpress_site))
    auth = (data.wordpress_username.strip(), data.wordpress_application_password.strip())
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0), follow_redirects=True) as client:
            me = await client.get(f"{site}/wp-json/wp/v2/users/me", params={"context": "edit"}, auth=auth)
            if me.status_code >= 400:
                raise HTTPException(status_code=401, detail="WordPress authentication failed. Use a WordPress Application Password.")
            candidates = await _wordpress_content_candidates(client, site, auth, article.wordpress_post_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not load WordPress pages and posts: {exc}") from exc

    return {"success": True, "count": len(candidates), "candidates": candidates}


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

    # Internal-link targets are selected by Claude in the frontend from the
    # authenticated WordPress candidate list. The backend validates every URL
    # against the connected site before inserting links.
    final_content = article.article_html
    applied_internal_links: list[dict[str, str]] = []
    if data.internal_links:
        parsed_site = urlparse(site)
        allowed_host = parsed_site.netloc.lower()
        allowed_scheme = parsed_site.scheme.lower()
        valid_links: list[dict[str, str]] = []
        for item in data.internal_links:
            target = str(item.target_url).strip()
            parsed_target = urlparse(target)
            if parsed_target.scheme.lower() != allowed_scheme or parsed_target.netloc.lower() != allowed_host:
                continue
            if target.rstrip("/") == site.rstrip("/"):
                continue
            anchor = " ".join(item.anchor_text.split())[:160]
            if len(anchor) >= 2:
                valid_links.append({"url": target, "anchor": anchor})

        if valid_links:
            if BeautifulSoup is None:
                raise HTTPException(status_code=500, detail="Internal-link publishing requires beautifulsoup4. Install the backend dependency and restart the server.")
            soup = BeautifulSoup(final_content, "html.parser")
            existing_urls = {str(a.get("href") or "").rstrip("/").lower() for a in soup.find_all("a", href=True)}

            for link in valid_links[:8]:
                target_key = link["url"].rstrip("/").lower()
                if target_key in existing_urls:
                    continue
                pattern = re.compile(re.escape(link["anchor"]), re.IGNORECASE)
                inserted = False
                for node in list(soup.find_all(string=True)):
                    parent = node.parent
                    if parent is None or parent.name in {"a", "code", "pre", "script", "style", "h1", "h2", "h3", "h4", "h5", "h6"}:
                        continue
                    if parent.find_parent(["a", "code", "pre", "script", "style", "h1", "h2", "h3", "h4", "h5", "h6"]):
                        continue
                    match = pattern.search(str(node))
                    if not match:
                        continue
                    before = str(node)[:match.start()]
                    matched = match.group(0)
                    after = str(node)[match.end():]
                    anchor_tag = soup.new_tag("a", href=link["url"])
                    anchor_tag.string = matched
                    from bs4 import NavigableString
                    fragment = [NavigableString(before), anchor_tag, NavigableString(after)]
                    node.replace_with(*fragment)
                    existing_urls.add(target_key)
                    applied_internal_links.append({"target_url": link["url"], "anchor_text": matched})
                    inserted = True
                    break
                if len(applied_internal_links) >= 8:
                    break

            final_content = str(soup)

    payload: dict[str, Any] = {
        "title": article.title,
        "content": final_content,
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

            # Use the client's actual WordPress site name for image branding.
            # If WordPress does not expose a name, safely fall back to the domain.
            client_brand = _fallback_client_brand(site)
            try:
                site_info = await client.get(f"{site}/wp-json", auth=auth)
                if site_info.status_code < 400:
                    site_data = site_info.json()
                    wp_name = str(site_data.get("name") or "").strip()
                    if wp_name:
                        client_brand = wp_name[:120]
            except Exception:
                pass

            featured = await _upload_featured_image(
                client,
                site,
                auth,
                article.title,
                article.keyword,
                article.article_html,
                client_brand,
            )
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

    article.article_html = final_content
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
            "internal_links_applied": applied_internal_links,
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
