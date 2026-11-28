#   SignFlow: AUTO-MAS 游戏社区核心插件
#   Copyright © 2024-2025 DLmaster361
#   Copyright © 2025-2026 AUTO-MAS Team

#   This file is part of SignFlow.

#   SignFlow is free software: you can redistribute it and/or modify
#   it under the terms of the GNU Affero General Public License as
#   published by the Free Software Foundation, either version 3 of
#   the License, or (at your option) any later version.

#   SignFlow is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#   GNU Affero General Public License for more details.

#   You should have received a copy of the GNU Affero General Public License
#   along with SignFlow. If not, see <https://www.gnu.org/licenses/>.

#   Contact: DLmaster_361@163.com


"""日常便笺的领域契约。

这份契约原在 AUTO-MAS 本体 `app/tools/common/community/contracts.py`，随便笺采集
一起搬入本插件。签到相关的契约（成功判据、凭据状态）留在本体，本插件不再引用：
便笺只读游戏内日常数据，不参与签到判定，两边互不牵连。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

ActivityState = Literal[
    "success",
    "empty",
    "limited",
    "unavailable",
    "failed",
]


@dataclass(frozen=True)
class CommunityActivitySnapshot:
    """日常活跃度领域结果，供后续只读查询模块复用。"""

    account: str
    account_uid: str
    game: str
    platform: str
    status: ActivityState
    completed: int | None = None
    target: int | None = None
    tasks: tuple[Mapping[str, object], ...] = ()
    resources: tuple[Mapping[str, object], ...] = ()
    reason: str = ""
    updated_at: str = ""
    role_name: str = ""
    role_uid: str = ""
    server: str = ""
    source: str = ""

    def to_dict(self) -> dict[str, object]:
        """转换为与 API 无关的普通字典。"""

        return {
            "account": self.account,
            "account_uid": self.account_uid,
            "game": self.game,
            "platform": self.platform,
            "status": self.status,
            "completed": self.completed,
            "target": self.target,
            "tasks": [dict(task) for task in self.tasks],
            "resources": [dict(resource) for resource in self.resources],
            "reason": self.reason,
            "updated_at": self.updated_at,
            "role_name": self.role_name,
            "role_uid": self.role_uid,
            "server": self.server,
            "source": self.source,
        }
