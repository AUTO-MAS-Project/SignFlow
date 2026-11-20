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
"""SignFlow 抽卡记录附属插件。插件实例。

首批只接通森空岛明日方舟：协议、记录模型与本地存档都在本包里，编排只认
`_PROTOCOLS` 登记过的游戏。其余游戏保持结构预留，查询返回空列表、读取
明确报「暂未支持」，不会伪装成读取成功。

凭据一律经核心插件的 `signflow.community` 门面取用，本插件不读宿主配置，
也不保存任何一份凭据。
"""

from __future__ import annotations

from auto_mas_core import ExtensionPlugin

from .gacha import GachaFacade


class Plugin(ExtensionPlugin):
    """抽卡记录附属插件。

    依赖核心插件服务 `signflow.community`：账号与凭据只从门面读，不复制
    第二份字段清单；HTTP 客户端也用宿主社区客户端，代理与 DNS 回退保持一致。
    """

    requires = ("signflow.community",)

    # 一个能力一个服务名：核心插件代发端点时按需取用，接口面越小越不容易被误用。
    provides_services = {
        "signflow.gacha": "query_records",
        "signflow.gacha.fetch": "fetch_records",
        "signflow.gacha.games": "supported_games",
    }

    def __init__(self, config=None, record=None):
        """初始化抽卡插件，持有唯一的抽卡门面实例。"""

        super().__init__(config=config, record=record)
        self._gacha = GachaFacade()

    async def supported_games(self) -> tuple[str, ...]:
        """返回已接通协议的游戏；前端按此决定显示哪些页签。

        同样以协程形式暴露：与另外两个服务保持同一种调用形态，调用方不必
        为「哪个是同步、哪个是异步」分叉处理。
        """

        return self._gacha.supported_games()

    async def query_records(
        self,
        game: str,
        *,
        player_uid: str = "",
        pool: str = "",
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, object]:
        """查询某个游戏已入库的抽卡记录，由核心插件对外代发。"""

        # 读存档是同步 IO，体量在几十万行以内，直接在本协程里做完即可，
        # 交给线程池反而多一层调度。
        return self._gacha.query(
            game,
            player_uid=player_uid,
            pool=pool,
            page=page,
            page_size=page_size,
        )

    async def fetch_records(
        self,
        game: str,
        *,
        account_uid: str,
        player_uid: str,
        max_pages: int = 100,
    ) -> dict[str, object]:
        """读取一个角色的抽卡记录并入库存档。

        暴露成协程而不是「返回门面再调用」：宿主 `CallGate` 只包住服务方法
        本身，只有这样插件停用时才会等到在途读取真正结束。
        """

        added, fetched, warnings = await self._gacha.fetch(
            game,
            account_uid=account_uid,
            player_uid=player_uid,
            max_pages=max_pages,
        )
        return {"added": added, "fetched": fetched, "warnings": list(warnings)}
