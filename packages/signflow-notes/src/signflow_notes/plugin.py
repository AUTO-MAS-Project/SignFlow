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

    只依赖核心插件服务 `signflow.community`：账号投影、凭据字段名与代理地址
    都由它提供。采集实现（平台协议、角色发现、并发请求、缓存与串行锁）在本包
    内，宿主便笺实现迁出后不再向宿主转发。

    与核心插件的 `signflow.activity` 服务无依赖关系：那条服务是宿主版便笺的
    转发口，本插件自带实现后不再需要它，也不再与核心插件形成回环依赖。
    """

    requires = ("signflow.community",)

    provides_services = {"signflow.notes": "query_notes"}

    def __init__(self, config=None, record=None):
        """初始化便笺插件，持有唯一的便笺门面实例。"""

        super().__init__(config=config, record=record)
        self._notes = NotesFacade()

    async def on_enable(self) -> None:
        """订阅宿主配置变动信号，账号或代理一改动就清空便笺缓存。

        插件没有宿主那样的配置钩子，只能自己订阅。订阅失败不阻断启用：缓存
        只是退化成按 TTL 过期，比让整个插件起不来更合适。
        """

        self._notes.collector.attach()

    async def on_disable(self) -> None:
        """解除配置订阅并丢弃缓存，避免停用后仍持有旧快照。"""

        self._notes.collector.detach()

    async def query_notes(
        self, account_ids: Iterable[str] | None = None
    ) -> tuple[dict[str, object], ...]:
        """按账号组查询日常便笺，由核心插件对外代发。

        暴露成协程而不是「返回门面再调用」：宿主 `CallGate` 只包住服务方法
        本身，只有这样插件停用时才会等到在途查询真正结束。
        """

        return await self._notes.snapshots(account_ids)
