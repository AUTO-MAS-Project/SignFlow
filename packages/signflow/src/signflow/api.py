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
"""核心插件对外接口：附属插件的查询能力统一由本插件代发。

便笺与抽卡插件自己不开 HTTP 端点，本模块按服务名取用它们的实现。这样前端
只需要认识核心插件一个前缀，附属插件被停用时这里会明确告知原因，而不是留下
一个 404 让调用方猜。
"""

from __future__ import annotations

from auto_mas_core import Plugin, PluginError
from auto_mas_core.host.models_schema import OutBase
from auto_mas_core.host.utils import get_logger
from fastapi import APIRouter, Body
from pydantic import BaseModel, Field

__all__ = ["router"]

router = APIRouter(prefix="/api/plugin/signflow", tags=["游戏社区"])

logger = get_logger("SignFlow 社区 API")


class NotesQueryIn(BaseModel):
    """便笺查询入参。"""

    accountIds: list[str] | None = Field(
        default=None, description="账号组 UID 列表，留空表示全部已启用账号组"
    )


class NotesQueryOut(OutBase):
    """便笺查询结果。

    `data` 的每一项由便笺插件给出，字段是宿主快照的驼峰投影；
    `tasks` 与 `resources` 由宿主解析器按游戏自由扩展，因此这里
    不逐字段建模，避免插件跟着上游改写第三份字段清单。
    """

    data: list[dict[str, object]] = Field(default_factory=list)


@router.post("/notes/query", summary="查询日常便笺", response_model=NotesQueryOut)
async def query_daily_notes(
    payload: NotesQueryIn = Body(...),
) -> NotesQueryOut:
    """按账号组查询游戏内日常便笺。"""

    try:
        notes = Plugin.services.require("signflow.notes")
    except PluginError:
        return NotesQueryOut(
            code=400,
            status="error",
            message="日常便笺插件未启用",
        )

    try:
        # 服务本身就是协程方法，由宿主 CallGate 包住；这里直接 await 才能让
        # 便笺插件停用时等到在途查询结束，而不是拿到一个已经失效的门面。
        data = await notes(payload.accountIds)
    except ValueError as error:
        # 账号组不存在等参数问题由宿主抛出，原样回给调用方便于定位。
        return NotesQueryOut(code=400, status="error", message=str(error))
    except Exception:
        logger.opt(exception=True).warning("日常便笺查询失败")
        return NotesQueryOut(code=500, status="error", message="日常便笺查询失败")

    return NotesQueryOut(message=f"共 {len(data)} 条日常便笺", data=list(data))


class GachaQueryIn(BaseModel):
    """抽卡记录查询入参。"""

    game: str = Field(default="arknights", description="游戏标识，如 arknights")
    playerUid: str = Field(default="", description="游戏 UID，留空表示该游戏全部角色")
    pool: str = Field(default="", description="卡池类型，留空表示全部卡池")
    page: int = Field(default=1, ge=1, description="页码，从 1 开始")
    pageSize: int = Field(default=50, ge=1, le=200, description="每页条数")


class GachaQueryOut(OutBase):
    """抽卡记录查询结果。

    `data` 的每一项是一条抽卡记录，字段名沿用记录模型（与 BMASC 导出格式
    一致，便于以后导入导出）；保底统计在 `pools` 里，前端据此画卡池切换与
    「距上次六星」。
    """

    data: list[dict[str, object]] = Field(default_factory=list)
    total: int = 0
    players: list[str] = Field(default_factory=list)
    pools: list[dict[str, object]] = Field(default_factory=list)


class GachaFetchIn(BaseModel):
    """抽卡记录读取入参。

    不含任何授权材料：凭据一律由抽卡插件经账号门面从账号组取，接口只收
    账号组 UID，避免把 Token 塞进请求体后被日志或代理记录带走。
    """

    game: str = Field(default="arknights", description="游戏标识，如 arknights")
    accountUid: str = Field(default="", description="账号组 UID，读取其森空岛凭据")
    playerUid: str = Field(min_length=1, max_length=120, description="游戏 UID")
    maxPages: int = Field(default=100, ge=1, le=500, description="单个卡池最多翻页数")


class GachaFetchOut(OutBase):
    """抽卡记录读取结果；有告警时 status 为 partial。"""

    added: int = 0
    fetched: int = 0
    warnings: list[str] = Field(default_factory=list)


class GachaGamesOut(OutBase):
    """已接通协议的游戏；前端据此决定哪些页签可用。"""

    games: list[str] = Field(default_factory=list)


def _gacha_service(name: str):
    """按服务名取抽卡插件的能力，缺失时同时给出可直接展示的原因。

    抽卡插件未安装或未启用属于正常状态（用户没装），不是错误，所以返回
    (None, 原因) 而不是抛异常，由调用方决定怎么回话。
    """

    try:
        return Plugin.services.require(name), ""
    except PluginError:
        return None, "抽卡记录插件未启用"


@router.get(
    "/gacha/games", summary="查询已支持的抽卡游戏", response_model=GachaGamesOut
)
async def get_gacha_games() -> GachaGamesOut:
    """返回抽卡插件已接通协议的游戏列表。"""

    games_service, reason = _gacha_service("signflow.gacha.games")
    if games_service is None:
        return GachaGamesOut(code=400, status="error", message=reason)

    try:
        games = await games_service()
    except Exception:
        logger.opt(exception=True).warning("抽卡游戏列表读取失败")
        return GachaGamesOut(code=500, status="error", message="抽卡游戏列表读取失败")

    return GachaGamesOut(message=f"共 {len(games)} 个游戏已支持", games=list(games))


@router.post("/gacha/query", summary="查询抽卡记录", response_model=GachaQueryOut)
async def query_gacha_records(payload: GachaQueryIn = Body(...)) -> GachaQueryOut:
    """查询已入库的抽卡记录，按游戏、角色与卡池筛选后分页。"""

    service, reason = _gacha_service("signflow.gacha")
    if service is None:
        return GachaQueryOut(code=400, status="error", message=reason)

    try:
        result = await service(
            payload.game,
            player_uid=payload.playerUid,
            pool=payload.pool,
            page=payload.page,
            page_size=payload.pageSize,
        )
    except ValueError as error:
        # 存档损坏等本地问题由抽卡插件抛出，原样回给调用方便于定位。
        return GachaQueryOut(code=400, status="error", message=str(error))
    except Exception:
        logger.opt(exception=True).warning("抽卡记录查询失败")
        return GachaQueryOut(code=500, status="error", message="抽卡记录查询失败")

    return GachaQueryOut(
        message=f"共 {result.get('total', 0)} 条抽卡记录",
        data=list(result.get("data") or []),
        total=int(result.get("total") or 0),
        players=list(result.get("players") or []),
        pools=list(result.get("pools") or []),
    )


@router.post("/gacha/fetch", summary="读取抽卡记录", response_model=GachaFetchOut)
async def fetch_gacha_records(payload: GachaFetchIn = Body(...)) -> GachaFetchOut:
    """读取一个角色的抽卡记录并入库存档。"""

    fetch_service, reason = _gacha_service("signflow.gacha.fetch")
    if fetch_service is None:
        return GachaFetchOut(code=400, status="error", message=reason)

    try:
        result = await fetch_service(
            payload.game,
            account_uid=payload.accountUid,
            player_uid=payload.playerUid,
            max_pages=payload.maxPages,
        )
    except ValueError as error:
        # 凭据缺失、正在读取、暂未支持等都可直接展示给用户。
        return GachaFetchOut(code=400, status="error", message=str(error))
    except Exception:
        logger.opt(exception=True).warning("抽卡记录读取失败")
        return GachaFetchOut(code=500, status="error", message="抽卡记录读取失败")

    warnings = list(result.get("warnings") or [])
    added = int(result.get("added") or 0)
    fetched = int(result.get("fetched") or 0)
    return GachaFetchOut(
        code=200,
        status="partial" if warnings else "success",
        message=f"读取 {fetched} 条，新增 {added} 条",
        added=added,
        fetched=fetched,
        warnings=warnings,
    )
