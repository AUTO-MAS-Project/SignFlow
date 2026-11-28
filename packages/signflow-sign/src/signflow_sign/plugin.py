# Copyright (C) 2024-2025 DLmaster361
# Copyright (C) 2025-2026 AUTO-MAS Team

# This file is part of AUTO-MAS.

# AUTO-MAS is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# AUTO-MAS is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License
# along with AUTO-MAS. If not, see <https://www.gnu.org/licenses/>.

# Contact: DLmaster_361@163.com

"""SignFlow 签到附属插件。插件实例。"""

from __future__ import annotations

from auto_mas_core import ExtensionPlugin

from .sign import SignFacade


class Plugin(ExtensionPlugin):
    """游戏社区每日签到插件。

    只提供"把已配置的平台跑完"这一件事：触发时机、结果落盘与通知都留在宿主。
    宿主按下述服务名取用，本插件自己不开 HTTP 端点。
    """

    requires = ("signflow.community",)
    provides_services = {"signflow.sign": "run_sign_in"}

    def __init__(self, config=None, record=None) -> None:
        super().__init__(config=config, record=record)
        self._sign = SignFacade()

    async def run_sign_in(self, force: bool = False) -> list[dict[str, object]]:
        """执行所有已配置平台的签到，返回宿主的签到结果条目列表。

        暴露成协程而不是"返回门面再调用"，因为宿主 CallGate 只包住服务方法本身，
        只有这样停用插件时才会等在途签到真正结束。
        """

        return await self._sign.run(force=force)
