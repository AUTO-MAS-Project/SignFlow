"""SignFlow 游戏社区核心插件入口。"""

from auto_mas_core import PLUGIN_API_VERSION

from .plugin import Plugin as PLUGIN

__all__ = ["PLUGIN", "PLUGIN_API_VERSION"]
