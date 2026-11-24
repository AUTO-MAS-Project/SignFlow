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

"""Token 获取插件自有配置。

只放「怎么登录」这一层：人机验证交给谁做。凭据本身仍写在宿主的账号组里，
本插件不为任何平台副本化凭据字段。
"""

from __future__ import annotations

from typing import Annotated, Literal

from auto_mas_core import ConfigGroup, PluginConfig, encrypted
from pydantic import Field


class CaptchaFields(ConfigGroup):
    """人机验证策略。"""

    Mode: Literal["manual", "yunma"] = Field(
        default="manual",
        description="人机验证方式（manual 为人工完成，yunma 为本机调用云码识别）",
    )

    YunmaToken: Annotated[str, encrypted()] = Field(
        default="", description="云码 API 密钥，仅在本机保存"
    )


class TokenConfig(PluginConfig):
    """SignFlow Token 获取插件的持久化配置。"""

    Captcha: CaptchaFields = Field(
        default_factory=CaptchaFields, description="人机验证策略"
    )
