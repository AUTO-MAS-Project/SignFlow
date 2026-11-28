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
"""日常便笺门面：把本插件采集到的日常快照收敛成插件能力。

采集实现就在本包内（`collector` + `provider` + `parser` + `transport`），
不再向核心插件或宿主转发：便笺是独立附属插件，自带上游协议、角色发现、
并发采集、串行锁与 300s / 30s 两级缓存。只从核心插件取账号与凭据门面
`signflow.community`——凭据只在那里解密读取，便笺侧只拿按字段名取值的投影。

本模块只负责两件事：

1. 把采集结果收敛成独立的 `signflow.notes` 能力，让便笺可以和签到分别安装、
   分别停用；
2. 固定对外输出形状：快照是 snake_case，前端 ActivitySnapshot 契约是驼峰，
   这里只转换一次，下游不必再记两套键名。
"""

from __future__ import annotations

from collections.abc import Iterable

from .collector import ActivityCollector

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
    """把采集快照投影成前端契约，未列出的键原样保留。"""

    return {_FIELD_ALIASES.get(key, key): value for key, value in snapshot.items()}


class NotesFacade:
    """日常便笺只读门面。

    实例由本插件在 `provides_services` 中暴露为 `signflow.notes`，
    核心插件对外代发时通过服务名取用。采集器由构造参数注入，测试可以换掉
    它而不必拉起宿主进程。
    """

    __slots__ = ("_collector",)

    def __init__(self, collector: ActivityCollector | None = None) -> None:
        """绑定唯一采集器；默认自建，生命周期由插件启停驱动。"""

        self._collector = collector if collector is not None else ActivityCollector()

    @property
    def collector(self) -> ActivityCollector:
        """返回采集器，供插件在启用与停用时挂接配置信号。"""

        return self._collector

    async def snapshots(
        self, account_ids: Iterable[str] | None = None
    ) -> tuple[dict[str, object], ...]:
        """按账号组查询日常便笺，返回与前端一致的驼峰投影。

        `account_ids` 为空表示查询全部已启用账号组。账号组不存在时采集器会抛出
        `ValueError`，这里原样上抛：参数错误必须让调用方看见，不能被降级成
        「查询失败」的假快照。
        """

        snapshots = await self._collector.query(account_ids)
        return tuple(_to_note(snapshot.to_dict()) for snapshot in snapshots)
