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
"""日常便笺门面：把宿主采集到的游戏内日常数据收敛成插件能力。

数据本身由 AUTO-MAS 本体采集。核心插件已经把这份数据暴露成 `signflow.activity`
服务，本模块不再直接访问上游接口、不读账号凭据、也不缓存快照——宿主已经实现
平台协议、角色发现、并发采集、串行便笺锁与 300s / 30s 两级缓存。

本模块只负责两件事：

1. 把便笺查询从核心插件的数据门面收敛成独立的 `signflow.notes` 能力，
   让便笺可以和签到分别安装、分别停用；
2. 固定对外输出形状：宿主快照是 snake_case，前端 ActivitySnapshot 契约是驼峰，
   这里只转换一次，下游不必再记两套键名。
"""

from __future__ import annotations

from collections.abc import Iterable

__all__ = ["NotesFacade"]


# 只列出与前端命名不同的键；其余键（account / game / platform / status /
# completed / target / tasks / resources / reason / server / source）两边一致。
_FIELD_ALIASES = {
    "account_uid": "accountUid",
    "updated_at": "updatedAt",
    "role_name": "roleName",
    "role_uid": "roleUid",
}


def _to_note(snapshot: dict[str, object]) -> dict[str, object]:
    """把宿主快照投影成前端契约，未列出的键原样保留。"""

    return {_FIELD_ALIASES.get(key, key): value for key, value in snapshot.items()}


class NotesFacade:
    """日常便笺只读门面。

    实例由本插件在 `provides_services` 中暴露为 `signflow.notes`，
    核心插件对外代发时通过服务名取用。
    """

    __slots__ = ()

    async def snapshots(
        self, account_ids: Iterable[str] | None = None
    ) -> tuple[dict[str, object], ...]:
        """按账号组查询日常便笺，返回与前端一致的驼峰投影。

        `account_ids` 为空表示查询全部已启用账号组。账号组不存在时宿主会抛出
        `ValueError`，这里原样上抛：参数错误必须让调用方看见，不能被降级成
        「查询失败」的假快照。
        """

        from auto_mas_core import Plugin

        # 服务本身就是协程方法，由宿主 CallGate 包住：插件停用时这边会等到
        # 在途查询结束，不会拿到一个已经失效的门面对象。
        activity = Plugin.services.require("signflow.activity")
        snapshots = await activity(account_ids)
        return tuple(_to_note(snapshot) for snapshot in snapshots)
