# CCTV Device Adapters
# ONVIF 및 제조사별 CCTV 어댑터

from .base import BaseCCTVAdapter

# ONVIF adapter (optional - requires onvif-zeep)
try:
    from .onvif import ONVIFAdapter
    __all__ = [
        "BaseCCTVAdapter",
        "ONVIFAdapter",
    ]
except ImportError:
    __all__ = [
        "BaseCCTVAdapter",
    ]
