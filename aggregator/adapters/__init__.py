from .sportvision import SPORTVISION_SITES, SportVisionAdapter

ADAPTERS = {cfg.source: SportVisionAdapter(cfg) for cfg in SPORTVISION_SITES}
