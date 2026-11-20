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

"""日常便笺门面：附属插件查询游戏内日常数据的唯一入口。

上游请求统一由本模块经宿主 `Community` 单例发出。宿主已经实现平台协议、
角色发现、并发采集、串行便笺锁与 300s / 30s 两级缓存，插件侧不再复制一套，
也不缓存快照——重复缓存会让两边的失效时机打架。

本模块只做类型收敛：把宿主快照收敛成可直接序列化的只读投影。快照本身不含
凭据与设备值，调用方也不需要账号 token。
"""

from __future__ import annotations

from collections.abc import Iterable

__all__ = ["ActivityFacade"]


class ActivityFacade:
    """日常便笺只读门面。

    实例由核心插件在 `provides_services` 中暴露为 `signflow.activity`，
    附属插件通过 `requires` 依赖该服务名后再取用。
    """

    __slots__ = ()

    async def snapshots(
        self, account_ids: Iterable[str] | None = None
    ) -> tuple[dict[str, object], ...]:
        """按账号组查询日常便笺，返回宿主快照的只读投影。

        `account_ids` 为空表示查询全部已启用账号组。账号组不存在时由宿主抛出
        `ValueError`，这里原样上抛：参数错误必须让调用方看见，不能被降级成
        「查询失败」的假快照。
        """

        from auto_mas_core.host.core import Community

        selected = (
            None
            if account_ids is None
            else [str(item).strip() for item in account_ids if str(item).strip()]
        )
        snapshots = await Community.query_configured_community_activity(selected or None)
        return tuple(snapshot.to_dict() for snapshot in snapshots)
