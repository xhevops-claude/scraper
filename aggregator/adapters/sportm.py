"""Adapter for the Sport M e-commerce platform.

Sport M runs its own ASP.NET storefront and operates intersport.mk on the
same codebase, so one adapter covers both (verified 2026-10-27, see
docs/research/sport-m-platform.md).

- No sitemap and no JSON-LD. Discovery walks the paginated HTML catalog
  (/ProductCatalog?Page=N, 18 tiles per page, empty page = end).
- Listing tiles carry id, title, brand logo, image and an add-to-cart call
  with regular price, sale price and a discount flag. We remember those per
  id so the product page only has to add category and sizes.
- Product id is the brand's article code (adidas "JQ5211", Nike
  "414714-569", On "3WG10035259"), which doubles as the SKU.
- Product URL: /ProductCatalog/ProductDetails?ProductID=<id>
- Brand filter: ?Brend=<code>; the codes are shared by both shops.
"""

import re
from dataclasses import dataclass, field
from typing import AsyncIterator
from urllib.parse import parse_qs, quote, urlparse

from ..fetch import PoliteClient
from ..models import Product

PRODUCT_PATH = "/ProductCatalog/ProductDetails"
PAGE_SIZE = 18

# Listing tiles sit in div.product_partial blocks. Two layouts exist:
# intersport.mk has a title anchor, brand logo and an add-to-cart call per
# tile; sport-m.com.mk only has the image link (name in an unquoted alt)
# and a price box.
TILE_SPLIT_RE = re.compile(r'<div class="[^"]*\bproduct_partial\b[^"]*">')
TILE_ID_RE = re.compile(r'ProductDetails\?ProductID=([^&"\']+)')
TILE_TITLE_RE = re.compile(r'<a id="Description [^"]+"[^>]*>\s*(.*?)\s*</a>', re.S)
TILE_ALT_RE = re.compile(r'<img[^>]*\salt=(?:"([^"]*)"|([^>]*?))\s+class="img-list"')
TILE_IMG_RE = re.compile(r'<img[^>]*\ssrc=["\']?(/ProductImages/[^"\'\s>]+)')
TILE_PRICE_RE = re.compile(r'([\d.]+,\d{2})\s*ден')
TILE_OLD_RE = re.compile(r'class="[^"]*pricePositionDecoration[^"]*"[^>]*>\s*([\d.]+,\d{2})')
TILE_SALE_RE = re.compile(r'class="[^"]*colorRed[^"]*"[^>]*>\s*([\d.]+,\d{2})')
# OnAddToShoppingCartFromProdList(id, image, normalPrice, priceWithDiscount,
#                                 discountFlag, priceNumeric)
CART_RE = re.compile(
    r"OnAddToShoppingCartFromProdList\('([^']*)','([^']*)','([^']*)',"
    r"'([^']*)','([^']*)','([^']*)'\)")
BRAND_IMG_RE = re.compile(r'<img class="ow-brand-image" alt="([^"]*)"')
TITLE_RE = re.compile(
    r"<h2 class=\"details_description\" id='([^']+) description'>\s*(.*?)\s*</h2>",
    re.S)
OLD_PRICE_RE = re.compile(r'id="old_price_pd"[^>]*>\s*([^<]*?)\s*<')
BREADCRUMB_RE = re.compile(r'class="breadcrumb-link">\s*([^<]*?)\s*<')
SIZE_RE = re.compile(r'<li[^>]*class="size-option[^"]*"[^>]*>(.*?)</li>', re.S)
# Product page gallery (DevExpress image zoom navigator): names may
# contain spaces, so read them from the JS item list rather than the DOM.
GALLERY_RE = re.compile(r"'s':'(/ProductImages/[^']+)'")
MAIN_IMAGE_RE = re.compile(r'id="ImageDetails"[^>]*src="([^"]+)"')
TAG_RE = re.compile(r"<[^>]+>")

# Brand codes are identical on sport-m.com.mk and intersport.mk
# (checked against /Home/Brands on both).
BRAND_CODES = {
    "adidas": "01",
    "nike": "02",
    "puma": "04",
    "reebok": "07",
    "4f": "69",
    "skechers": "70",
    "asics": "72",
    "salomon": "73",
    "new balance": "81",
    "energetics": "100",
    "mckinley": "104",
    "on": "122",
    "crocs": "00050",
    "jack wolfskin": "00071",
    "salewa": "00074",
}

CODE_BRANDS = {code: name.title() if name != "on" else "On"
               for name, code in BRAND_CODES.items()}
CODE_BRANDS["00050"] = "Crocs"
CODE_BRANDS["104"] = "McKinley"

# Multi-word brands the product title may start with; everything else is
# taken to be the first word of the title.
MULTI_WORD_BRANDS = ("New Balance", "Jack Wolfskin", "The North Face",
                     "Under Armour", "Dare 2b", "D.Franklin")


@dataclass(frozen=True)
class SiteConfig:
    source: str      # e.g. "sportm_mk"
    base_url: str    # e.g. "https://sport-m.com.mk"
    currency: str = "MKD"


SPORTM_SITES = [
    SiteConfig("sportm_mk", "https://sport-m.com.mk"),
    SiteConfig("intersport_mk", "https://intersport.mk"),
]


@dataclass
class TileInfo:
    """What a listing tile tells us before the product page is fetched."""
    name: str
    brand: str | None = None
    price: float | None = None
    old_price: float | None = None
    image: str | None = None


@dataclass
class SportMAdapter:
    config: SiteConfig
    _tiles: dict[str, TileInfo] = field(default_factory=dict)

    # -- discovery ---------------------------------------------------------

    async def discover(self, client: PoliteClient) -> AsyncIterator[str]:
        """Yield every product URL by walking the whole catalog."""
        async for url, _title in self._walk(client, ""):
            yield url

    async def discover_listing(
            self, client: PoliteClient,
            listing_query: str) -> AsyncIterator[tuple[str, str]]:
        """Yield (product_url, title) from a filtered catalog listing.

        `listing_query` is the site's own query string, e.g. "Brend=01" or
        "Segment=03&Grupa=01&Brend=02".
        """
        query = listing_query.strip("?& ")
        # Sport M tiles carry no brand logo; when the listing is filtered by
        # brand we know it anyway.
        code = parse_qs(query).get("Brend", [None])[0]
        brand = CODE_BRANDS.get(code) if code else None
        async for item in self._walk(client, query, brand):
            yield item

    def brand_listing(self, brand: str) -> str | None:
        code = BRAND_CODES.get(brand.strip().casefold())
        return f"Brend={code}" if code else None

    async def _walk(self, client: PoliteClient, query: str,
                    brand: str | None = None) -> AsyncIterator[tuple[str, str]]:
        seen: set[str] = set()
        page = 1
        while True:
            sep = "&" if query else ""
            url = f"{self.config.base_url}/ProductCatalog?{query}{sep}Page={page}"
            resp = await client.get(url)
            new = 0
            for product_id, tile in self.parse_listing(resp.text).items():
                if product_id in seen:
                    continue
                seen.add(product_id)
                new += 1
                if brand and not tile.brand:
                    tile.brand = brand
                self._tiles[product_id] = tile
                yield self.product_url(product_id), tile.name
            # The "next" arrow is rendered even on the last page, so the
            # only reliable end signal is a page with nothing new on it.
            if new == 0:
                return
            page += 1

    def product_url(self, product_id: str) -> str:
        return f"{self.config.base_url}{PRODUCT_PATH}?ProductID={product_id}"

    def parse_listing(self, html: str) -> dict[str, TileInfo]:
        tiles: dict[str, TileInfo] = {}
        for block in TILE_SPLIT_RE.split(html)[1:]:
            id_match = TILE_ID_RE.search(block)
            if not id_match:
                continue
            product_id = id_match.group(1)
            title = TILE_TITLE_RE.search(block)
            if title:
                name = _clean(title.group(1))
            else:
                alt = TILE_ALT_RE.search(block)
                name = _clean(alt.group(1) or alt.group(2) or "") if alt else ""
            if not name:
                continue
            tile = TileInfo(name=name)
            brand = BRAND_IMG_RE.search(block)
            if brand:
                tile.brand = brand.group(1).strip() or None
            img = TILE_IMG_RE.search(block)
            if img:
                tile.image = _abs(self.config.base_url, img.group(1))
            cart = CART_RE.search(block)
            if cart:
                _id, _image, normal, discounted, flag, _num = cart.groups()
                if flag == "1":
                    tile.price = _to_float(discounted)
                    tile.old_price = _to_float(normal)
                else:
                    tile.price = _to_float(normal)
            else:
                sale = TILE_SALE_RE.search(block)
                old = TILE_OLD_RE.search(block)
                if sale:
                    tile.price = _to_float(sale.group(1))
                    tile.old_price = _to_float(old.group(1)) if old else None
                else:
                    price = TILE_PRICE_RE.search(block)
                    tile.price = _to_float(price.group(1)) if price else None
            tiles[product_id] = tile
        return tiles

    # -- product pages -----------------------------------------------------

    async def fetch_product(self, client: PoliteClient, url: str) -> Product | None:
        resp = await client.get(url)
        return self.parse_product(resp.text, url)

    def parse_product(self, html: str, url: str) -> Product | None:
        title_match = TITLE_RE.search(html)
        if not title_match:
            return None
        product_id = title_match.group(1).strip()
        url_id = parse_qs(urlparse(url).query).get("ProductID", [None])[0]
        if url_id and url_id != product_id:
            # The server answered with a different product (redirect to a
            # default item) - treat as missing.
            return None
        name = _clean(title_match.group(2))
        tile = self._tiles.get(product_id)

        price_match = re.search(
            r"id=['\"]%s Price['\"][^>]*>\s*([^<]*)" % re.escape(product_id), html)
        price = _to_float(price_match.group(1)) if price_match else None
        old_match = OLD_PRICE_RE.search(html)
        old_price = _to_float(old_match.group(1)) if old_match else None
        if price is None and tile:
            price, old_price = tile.price, tile.old_price

        crumbs = [c for c in BREADCRUMB_RE.findall(html) if c]
        category = "/".join(crumbs) or None

        sizes = [_clean(s) for s in SIZE_RE.findall(html)]
        sizes = [s for s in sizes if s]
        # Sold-out sizes are omitted rather than marked, so any listed size
        # means purchasable; no size block at all is unknown, not sold out.
        availability = "InStock" if sizes else None

        brand = (tile.brand if tile else None) or _brand_from_name(name)

        images: list[str] = []
        main = MAIN_IMAGE_RE.search(html)
        refs = ([main.group(1)] if main else []) + GALLERY_RE.findall(html)
        for ref in refs:
            img = _abs(self.config.base_url, quote(ref, safe="/:_.-"))
            if img not in images:
                images.append(img)
        if not images and tile and tile.image:
            images = [tile.image]

        return Product(
            source=self.config.source,
            source_id=product_id,
            url=self.product_url(product_id),
            name=name,
            sku=product_id,
            brand=brand,
            category=category,
            price=price,
            old_price=old_price,
            currency=self.config.currency,
            availability=availability,
            images=images,
        )


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", TAG_RE.sub(" ", text)).strip()


def _abs(base: str, path: str) -> str:
    return path if path.startswith("http") else base + path


def _brand_from_name(name: str) -> str | None:
    for brand in MULTI_WORD_BRANDS:
        if name.casefold().startswith(brand.casefold() + " "):
            return brand
    first = name.split(" ", 1)[0]
    return first or None


def _to_float(value) -> float | None:
    """Parse "12.399,00 ден." / " 799,00 ден." / "6099" -> float."""
    if value is None:
        return None
    text = re.sub(r"[^\d.,]", "", str(value))
    if not text:
        return None
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", text):
        text = text.replace(".", "")
    try:
        return float(text)
    except ValueError:
        return None
