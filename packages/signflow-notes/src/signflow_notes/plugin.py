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

"""SignFlow 日常便笺附属插件。插件实例。"""

from __future__ import annotations

from collections.abc import Iterable

from auto_mas_core import ExtensionPlugin

from .notes import NotesFacade


class Plugin(ExtensionPlugin):
    """SignFlow 日常便笺附属插件。

    依赖核心插件服务 `signflow.activity`：便笺数据由 AUTO-MAS 本体采集，
    核心插件负责把宿主 `Community` 的查询能力暴露出来，本插件只做形状收敛。
    不直接依赖 `signflow.community`（账号与凭据），因为便笺用不到凭据。
    """

    requires = ("signflow.activity",)

    provides_services = {"signflow.notes": "query_notes"}

    def __init__(self, config=None, record=None):
        """初始化便笺插件，持有唯一的便笺门面实例。"""

        super().__init__(config=config, record=record)
        self._notes = NotesFacade()

    async def query_notes(
        self, account_ids: Iterable[str] | None = None
    ) -> tuple[dict[str, object], ...]:
        """按账号组查询日常便笺，由核心插件对外代发。

        暴露成协程而不是「返回门面再调用」：宿主 `CallGate` 只包住服务方法
        本身，只有这样插件停用时才会等到在途查询真正结束。门面不持状态，
        宿主已经缓存快照，这里再存一份只会让两边的失效时机打架。
        """

        return await self._notes.snapshots(account_ids)
