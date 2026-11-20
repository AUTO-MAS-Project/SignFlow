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

from .config import SignFlowConfig


class Plugin(ExtensionPlugin):
    """游戏社区核心插件。

    只提供账号与平台协议门面，不直接执行签到；签到由本体内置流程完成。
    """

    config_class = SignFlowConfig

    # 附属插件（便笺 / 抽卡 / Token）以服务名依赖本插件，未启用时无法启用。
    provides_services = {"signflow.community": "community"}

    def community(self) -> dict[str, str]:
        """返回社区门面标识。

        骨架阶段只暴露身份信息，具体能力在后续步骤挂到同一个服务名下，
        避免附属插件反复改动依赖声明。
        """

        return {"plugin": self.plugin_name, "api": "signflow.community"}
