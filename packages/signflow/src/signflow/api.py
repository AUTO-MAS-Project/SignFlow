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

便笺插件自己不开 HTTP 端点，本模块按服务名取用它的实现。这样前端只需要
认识核心插件一个前缀，附属插件被停用时这里会明确告知原因，而不是留下一个
404 让调用方猜。
"""

from __future__ import annotations

from fastapi import APIRouter, Body
from pydantic import BaseModel, Field

from auto_mas_core import Plugin, PluginError
from auto_mas_core.host.models_schema import OutBase
from auto_mas_core.host.utils import get_logger

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
