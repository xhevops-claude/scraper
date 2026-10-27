"""Adapter for the Sport Vision e-commerce platform.

The same platform (NBSHOP) runs Sport Vision storefronts in 13 countries
(sportvision.mk, .rs, .ba, ...) plus the sister brands Sport Reality and
Buzz Sneakers, so one adapter covers the family; each storefront is a
SiteConfig entry.

Findings for sportvision.mk (verified 2026-08-28, see
docs/research/sportvision-mk.md):
- robots.txt allows product/category crawling and points at a sitemap index.
- files/sitemap/<REGION>_<lang>/product.xml enumerates every product URL
  (~13k for MK).
- Product pages are server-rendered and embed a schema.org Product JSON-LD
  block: name, sku, productID, brand, images, offers (price, currency,
  availability). Previous price sits in HTML as `prev-old-price`.
- Product URL format: /<lang>/<category>/<numeric-id>-<slug>
"""

import json
import re
from dataclasses import dataclass
from typing import AsyncIterator
from xml.etree import ElementTree

import httpx

from ..fetch import PoliteClient
from ..models import Product

SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
LDJSON_RE = re.compile(
    r'<script type="application/ld\+json">(.*?)</script>', re.S)
# Main product's previous price; the div carries "hide" in its class list
# when the product is not discounted. Related-product tiles use a different
# class (prev-old-price), so anchor on product-oldprice specifically.
OLD_PRICE_RE = re.compile(
    r'class="[^"]*\bproduct-oldprice\b([^"]*)"[^>]*>\s*'
    r'<span class="product-oldprice-value value">([\d.,]+)</span>', re.S)
PRODUCT_PATH_RE = re.compile(r"/([a-z0-9-]+)/(\d+)-[^/]+/?$")
# Product tile on listing pages: anchor with the detail URL and the product
# title. Tiles repeat per color variant, so de-dup on the numeric id.
TILE_RE = re.compile(
    r'<a href="(https?://[^"]+/mk/[a-z0-9-]+/(\d{5,})-[^"]*)"\s+title="([^"]*)"')


@dataclass(frozen=True)
class SiteConfig:
    source: str          # e.g. "sportvision_mk"
    base_url: str        # e.g. "https://www.sportvision.mk"
    sitemap_region: str  # e.g. "MAK_mk" -> files/sitemap/MAK_mk/product.xml
    currency: str


SPORTVISION_SITES = [
    SiteConfig("sportvision_mk", "https://www.sportvision.mk", "MAK_mk", "MKD"),
    # Sister brands on the same NBSHOP platform, same sitemap layout and
    # product markup (verified 2026-10-27, see docs/research/):
    SiteConfig("sportreality_mk", "https://www.sportreality.mk", "MAK_mk", "MKD"),
    SiteConfig("buzzsneakers_mk", "https://www.buzzsneakers.mk", "MAK_mk", "MKD"),
    # Other countries' storefronts, ready to enable once reachable:
    # SiteConfig("sportvision_rs", "https://www.sportvision.rs", "SRB_rs", "RSD"),
    # SiteConfig("sportvision_ba", "https://www.sportvision.ba", "BIH_ba", "BAM"),
]


class SportVisionAdapter:
    def __init__(self, config: SiteConfig):
        self.config = config

    async def discover(self, client: PoliteClient) -> AsyncIterator[str]:
        """Yield every product URL from the site's product sitemap."""
        url = (f"{self.config.base_url}/files/sitemap/"
               f"{self.config.sitemap_region}/product.xml")
        resp = await client.get(url)
        root = ElementTree.fromstring(resp.content)
        for loc in root.iterfind(".//sm:url/sm:loc", SITEMAP_NS):
            if loc.text:
                yield loc.text.strip()

    async def discover_listing(
            self, client: PoliteClient,
            listing_path: str) -> AsyncIterator[tuple[str, str]]:
        """Yield (product_url, title) from a filtered listing.

        `listing_path` is the path after /mk/, using the site's own filter
        segments, e.g. "patiki/zenski/new-balance" for women's New Balance
        sneakers. Walks /page-2, /page-3, ... until pages run out.
        """
        seen: set[str] = set()
        page = 1
        while True:
            suffix = "" if page == 1 else f"/page-{page}"
            url = f"{self.config.base_url}/mk/{listing_path.strip('/')}{suffix}"
            try:
                resp = await client.get(url)
            except httpx.HTTPStatusError as exc:
                if exc.response is not None and exc.response.status_code == 404:
                    return
                raise
            new = 0
            for match in TILE_RE.finditer(resp.text):
                product_id = match.group(2)
                if product_id in seen:
                    continue
                seen.add(product_id)
                new += 1
                yield match.group(1), match.group(3).strip()
            if new == 0 or f"page-{page + 1}" not in resp.text:
                return
            page += 1

    def brand_listing(self, brand: str) -> str | None:
        """Brand filter listing, e.g. "proizvodi/new-balance"."""
        slug = re.sub(r"[^a-z0-9]+", "-", brand.strip().casefold()).strip("-")
        return f"proizvodi/{slug}" if slug else None

    async def fetch_product(self, client: PoliteClient, url: str) -> Product | None:
        resp = await client.get(url)
        return self.parse_product(resp.text, url)

    def parse_product(self, html: str, url: str) -> Product | None:
        ld = self._product_ldjson(html)
        if ld is None:
            return None

        offers = ld.get("offers") or {}
        path_match = PRODUCT_PATH_RE.search(url.split("?")[0])
        category = path_match.group(1) if path_match else None
        source_id = str(ld.get("productID") or
                        (path_match.group(2) if path_match else ""))
        if not source_id:
            return None

        old_price = None
        old_price_match = OLD_PRICE_RE.search(html)
        if old_price_match and "hide" not in old_price_match.group(1):
            old_price = _to_float(old_price_match.group(2))
        availability = (offers.get("availability") or "").rsplit("/", 1)[-1] or None
        brand = ld.get("brand")
        if isinstance(brand, dict):
            brand = brand.get("name")

        return Product(
            source=self.config.source,
            source_id=source_id,
            url=url,
            name=(ld.get("name") or "").strip(),
            sku=ld.get("sku"),
            brand=brand,
            category=category,
            price=_to_float(offers.get("price")),
            old_price=old_price,
            currency=offers.get("priceCurrency") or self.config.currency,
            availability=availability,
            images=_image_list(ld.get("image")),
        )

    @staticmethod
    def _product_ldjson(html: str) -> dict | None:
        # Pages carry several ld+json blocks (breadcrumbs, a commented-out
        # template with invalid JSON, and the real Product) - take the first
        # block that parses and has @type == Product.
        for match in LDJSON_RE.finditer(html):
            try:
                # strict=False: descriptions sometimes carry raw newlines
                # inside the JSON string, which the default parser rejects.
                data = json.loads(match.group(1), strict=False)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict) and data.get("@type") == "Product":
                return data
        return None


def _image_list(value) -> list[str]:
    # JSON-LD "image" is usually a list but occasionally a single string.
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [i for i in value if isinstance(i, str)]
    return []


def _to_float(value) -> float | None:
    if value is None:
        return None
    try:
        # Site formats prices both as "4990.00" (JSON-LD) and "5.790" (HTML,
        # dot as thousands separator with no decimals).
        text = str(value).strip()
        if re.fullmatch(r"\d{1,3}(\.\d{3})+", text):
            text = text.replace(".", "")
        return float(text.replace(",", ""))
    except ValueError:
        return None
