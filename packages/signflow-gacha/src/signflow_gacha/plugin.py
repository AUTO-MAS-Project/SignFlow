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

"""SignFlow 抽卡记录附属插件。插件实例。"""

from __future__ import annotations

from auto_mas_core import ExtensionPlugin


class Plugin(ExtensionPlugin):
    """SignFlow 抽卡记录附属插件。

    只声明对核心插件服务 `signflow.community` 的依赖；具体能力在后续步骤补齐。
    """

    requires = ("signflow.community",)

    provides_services = {"signflow.gacha": "gacha"}

    def gacha(self) -> dict[str, str]:
        """返回本插件的服务标识。

        核心插件通过服务名定位附属插件，骨架阶段只暴露身份信息。
        """

        return {"plugin": self.plugin_name, "api": "signflow.gacha"}
