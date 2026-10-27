from .sportm import SPORTM_SITES, SportMAdapter
from .sportvision import SPORTVISION_SITES, SportVisionAdapter

ADAPTERS = {cfg.source: SportVisionAdapter(cfg) for cfg in SPORTVISION_SITES}
ADAPTERS.update({cfg.source: SportMAdapter(cfg) for cfg in SPORTM_SITES})
