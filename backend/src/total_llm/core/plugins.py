"""Plugin registry for extensible analysis types."""

from typing import Any, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class PluginRegistry:
    """Registry for analysis and processing plugins."""

    _instance = None

    def __init__(self):
        self._plugins: Dict[str, Any] = {}

    @classmethod
    def instance(cls) -> "PluginRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, name: str, plugin: Any, category: str = "analysis") -> None:
        key = f"{category}:{name}"
        self._plugins[key] = plugin
        logger.info(f"Plugin registered: {key}")

    def get(self, name: str, category: str = "analysis") -> Optional[Any]:
        return self._plugins.get(f"{category}:{name}")

    def list_plugins(self, category: Optional[str] = None) -> Dict[str, Any]:
        if category:
            return {k: v for k, v in self._plugins.items() if k.startswith(f"{category}:")}
        return dict(self._plugins)

    def unregister(self, name: str, category: str = "analysis") -> bool:
        key = f"{category}:{name}"
        if key in self._plugins:
            del self._plugins[key]
            return True
        return False


def get_plugin_registry() -> PluginRegistry:
    return PluginRegistry.instance()
