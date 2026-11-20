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
"""抽卡记录的数据形状；授权链接、Token 与账号凭据都不属于记录本身。

字段与 Better-MAS-Tools 的记录模型保持一致，这样以后要导入它导出的 BMASC
JSON 时不需要再做第二遍字段映射。稀有度统一按 1 基计：明日方舟上游返回 0 基
星级，由协议层加一后再入库，避免下游每个消费方各加一次。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["GachaGame", "GachaRecord"]

# 首批只接入森空岛明日方舟；其余取值是结构预留，注册表里没有对应协议时
# 查询会返回空列表、读取会明确报「暂未支持」，不会伪装成读取成功。
GachaGame = Literal["genshin", "starrail", "zzz", "wuthering", "arknights", "endfield"]


class GachaRecord(BaseModel):
    """一条抽卡记录。

    `extra="forbid"` 是有意为之：导入外部文件时多出来的字段必须显式报错，
    否则一份字段名写错的存档会被静默接受，等到前端展示才发现数据不全。
    """

    model_config = ConfigDict(extra="forbid")

    game: GachaGame
    playerUid: str = Field(min_length=1, max_length=120)
    id: str = Field(min_length=1, max_length=200)
    poolType: str = Field(min_length=1, max_length=120)
    poolName: str = Field(default="", max_length=180)
    name: str = Field(min_length=1, max_length=180)
    itemId: str = Field(default="", max_length=100)
    itemType: str = Field(default="", max_length=80)
    rarity: int = Field(ge=1, le=6)
    time: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}$")
    timezone: int = Field(default=8, ge=-12, le=14)
    lang: str = Field(default="zh-cn", max_length=20)
    isFree: bool = False
    kind: str = Field(default="", max_length=60)
