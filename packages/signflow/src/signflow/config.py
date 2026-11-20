#   SignFlow: AUTO-MAS 游戏社区核心插件
#   Copyright © 2024-2025 DLmaster361
#   Copyright © 2025-2026 AUTO-MAS Team

#   This file is part of SignFlow.

#   SignFlow is free software: you can redistribute it and/or modify
#   it under the terms of the GNU Affero General Public License as
#   published by the Free Software Foundation, either version 3 of
#   the License, or (at your option) any later version.

#   SignFlow is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty
#   of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#   GNU Affero General Public License for more details.

#   You should have received a copy of the GNU Affero General Public License
#   along with SignFlow. If not, see <https://www.gnu.org/licenses/>.

#   Contact: DLmaster_361@163.com

"""SignFlow 核心插件自有配置。"""

from __future__ import annotations

from typing import Annotated

from auto_mas_core import ConfigGroup, PluginConfig, UiVisibility, ui
from pydantic import Field


class CacheFields(ConfigGroup):
    """社区数据缓存策略。"""

    ActivityTtlSeconds: int = Field(
        default=180,
        ge=30,
        le=3600,
        description="日常便笺缓存有效期（秒）",
    )


class SignFlowConfig(PluginConfig):
    """SignFlow 核心插件的持久化配置。"""

    Cache: Annotated[CacheFields, ui(visibility=UiVisibility.HIDE)] = Field(
        default_factory=CacheFields,
        description="社区数据缓存策略",
    )
