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

"""SignFlow 核心插件实例。"""

from __future__ import annotations

from auto_mas_core import ExtensionPlugin
from fastapi import APIRouter

from .accounts import CommunityFacade
from .api import router as community_router
from .config import SignFlowConfig


class Plugin(ExtensionPlugin):
    """游戏社区核心插件。

    只提供账号、凭据与平台协议门面，不直接执行签到：签到编排在
    `signflow-sign` 附属插件，本插件只把账号与代理投影交给它。
    便笺采集在 `signflow-notes` 附属插件，本插件不再转发宿主便笺实现。
    """

    config_class = SignFlowConfig

    # 附属插件不自己开 HTTP 端点：宿主只认插件自有前缀，前端也只需要记住
    # 一个 /api/plugin/signflow。便笺等查询能力由本插件代发，插件被停用时
    # 仍能返回一条用户看得懂的失败原因。
    api_router = APIRouter()
    api_router.include_router(community_router)

    # 附属插件（便笺 / 签到 / 抽卡 / Token）以服务名依赖本插件，未启用时无法启用。
    # 一个能力一个服务名：附属插件只声明自己真正要用的那一个，接口面越小越不容易被误用。
    provides_services = {
        "signflow.community": "community",
    }

    def __init__(self, config=None, record=None):
        """初始化核心插件，预先持有唯一的账号门面实例。"""

        super().__init__(config=config, record=record)
        self._facade = CommunityFacade()

    def community(self) -> CommunityFacade:
        """返回社区账号与凭据门面，供附属插件取用。

        门面是无状态只读投影，每次调用返回同一实例，避免附属插件各自
        复制一份账号字段清单。
        """

        return self._facade
