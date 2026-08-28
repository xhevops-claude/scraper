from dataclasses import dataclass, field


@dataclass
class Product:
    """Normalized product record shared by all site adapters."""

    source: str            # adapter/site key, e.g. "sportvision_mk"
    source_id: str         # stable id on the source site, e.g. "8731122"
    url: str
    name: str
    sku: str | None = None
    brand: str | None = None
    category: str | None = None   # site category slug, e.g. "patiki"
    price: float | None = None
    old_price: float | None = None
    currency: str | None = None
    availability: str | None = None  # "InStock" / "OutOfStock"
    images: list[str] = field(default_factory=list)
