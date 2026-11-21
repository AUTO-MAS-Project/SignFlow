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
"""抽卡记录编排：读取、落库、查询。

本模块是抽卡插件对外的全部能力面，核心插件按服务名取用后转给前端。三条
边界写在这里而不是散在各处：

1. 平台协议按游戏登记在 `_PROTOCOLS` 里，读取时只查表，不写 if 链；
   某个游戏的协议还没做，就是没登记，读它会得到一句明确的「暂未支持」。
2. 凭据只从核心插件的账号门面取，本模块不碰宿主配置、不复制凭据字段清单。
3. 读取全程持锁并限流：抽卡记录接口对同一账号频繁请求会触发风控，同一时刻
   只允许一个读取任务，重复点击直接失败而不是排队堆积。
4. 读取只由用户手动触发：本模块不排定时任务、不在插件启用时预热、不在签到
   之后自动补拉。抽卡记录接口是风控敏感面，什么时候打由用户点按钮决定，
   自动化留空比事后解释「为什么号被限流」省事。
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Callable, Coroutine
from typing import Any

from . import arknights
from .models import GachaRecord
from .store import GachaStore

__all__ = ["GachaFacade"]

# 单页默认条数与上限：前端表格一页几十行就够，上限防止一次把整份存档塞进响应。
_DEFAULT_PAGE_SIZE = 50
_MAX_PAGE_SIZE = 200

# 游戏 → 读取协议。新增游戏只加一行，编排层不改。
_PROTOCOLS: dict[
    str, Callable[..., Coroutine[Any, Any, tuple[list[GachaRecord], list[str]]]]
] = {
    "arknights": arknights.fetch_arknights,
}


class GachaFacade:
    """抽卡记录的读取与查询入口；不持配置，不判断授权开关。"""

    __slots__ = ("_store", "_lock")

    def __init__(self, store: GachaStore | None = None) -> None:
        """允许注入存档实现，测试与将来的多存档共用一份编排。"""

        self._store = store if store is not None else GachaStore()
        self._lock = asyncio.Lock()

    def supported_games(self) -> tuple[str, ...]:
        """返回已登记协议的游戏；其余游戏只有结构预留，读取会明确报错。"""

        return tuple(_PROTOCOLS)

    def query(
        self,
        game: str,
        *,
        player_uid: str = "",
        pool: str = "",
        page: int = 1,
        page_size: int = _DEFAULT_PAGE_SIZE,
    ) -> dict[str, object]:
        """按游戏、UID、卡池筛选并分页，同时给出卡池保底统计。

        返回值形状与前端表格一一对应：`data` 是当页记录，`total` 是筛选后
        总数，`players` 用于切换角色，`pools` 用于切换卡池与展示保底距离。
        """

        size = max(1, min(page_size, _MAX_PAGE_SIZE))
        current = max(1, page)
        game_records = [item for item in self._store.load() if item.game == game]
        selected = [
            item
            for item in game_records
            if not player_uid or item.playerUid == player_uid
        ]

        # 保底距离只按同一角色、同一类池计算；多角色混在一起算出来的数字没有意义。
        grouped: dict[tuple[str, str], list[GachaRecord]] = defaultdict(list)
        for item in selected:
            if item.kind != "gift_intel_book":
                grouped[(item.playerUid, item.poolType)].append(item)

        top_rarity = 6 if game == "arknights" else 5
        pools = [
            {
                "poolType": key,
                "poolName": f"{uid} · {items[0].poolName or key}",
                "total": len(items),
                "topRarity": top_rarity,
                "topCount": sum(item.rarity == top_rarity for item in items),
                "sinceTop": next(
                    (
                        index
                        for index, item in enumerate(items)
                        if item.rarity == top_rarity
                    ),
                    len(items),
                ),
            }
            for (uid, key), items in grouped.items()
        ]

        filtered = [item for item in selected if not pool or item.poolType == pool]
        start = (current - 1) * size
        return {
            "data": [item.model_dump() for item in filtered[start : start + size]],
            "total": len(filtered),
            "players": sorted({item.playerUid for item in game_records}),
            "pools": pools,
        }

    async def fetch(
        self,
        game: str,
        *,
        account_uid: str,
        player_uid: str,
        max_pages: int = 100,
    ) -> tuple[int, int, list[str]]:
        """读取一个角色的抽卡记录并入库存档，返回 (新增, 读取, 告警)。

        授权材料只活在本次调用里：从账号门面取到的凭据交给协议函数后即丢弃，
        既不入库也不进返回值。整个读取持锁，重复触发直接失败。

        只由用户手动触发的读取入口调用：本方法不自己排期、不自己重试，读多
        读少由调用方决定，读失败就如实抛给调用方。
        """

        protocol = _PROTOCOLS.get(game)
        if protocol is None:
            raise ValueError("抽卡记录暂未支持该游戏")
        if not player_uid.strip():
            raise ValueError("请填写游戏 UID")
        if self._lock.locked():
            raise ValueError("抽卡记录正在读取，请稍后重试")

        async with self._lock:
            credential = self._credential(account_uid)
            records, warnings = await self._read(
                protocol, credential, player_uid.strip(), max_pages
            )

        added = self._store.merge(records) if records else 0
        if not records and warnings:
            raise ValueError("没有取得有效抽卡记录，请检查授权时效后重试")
        return added, len(records), warnings

    def _credential(self, account_uid: str) -> str:
        """从核心插件账号门面取森空岛凭据；缺失时给出可执行的提示。"""

        from auto_mas_core import Plugin

        community = Plugin.services.require("signflow.community")()
        account = community.account(account_uid)
        if account is None:
            raise ValueError("请选择一个已保存的社区账号")

        token = account.tokens.get(community.token_field("森空岛"), "")
        if not token:
            raise ValueError("该账号尚未登录森空岛，请先在帐号管理中完成登录")
        return token

    async def _read(
        self,
        protocol: Callable[
            ..., Coroutine[Any, Any, tuple[list[GachaRecord], list[str]]]
        ],
        credential: str,
        player_uid: str,
        max_pages: int,
    ) -> tuple[list[GachaRecord], list[str]]:
        """在宿主社区客户端上跑一次协议；客户端负责代理与 DNS 回退。"""

        from auto_mas_core import Plugin

        from app.tools.common.community.http import create_community_client

        proxy = Plugin.services.require("signflow.community")().proxy()
        # 客户端由宿主提供，代理、DNS 回退与 trust_env 都在里面配好了；
        # 这里只借用它，不另造 http 连接层。
        async with create_community_client(proxy) as client:
            return await protocol(client, credential, player_uid, max_pages=max_pages)
