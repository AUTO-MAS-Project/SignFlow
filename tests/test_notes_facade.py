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
"""日常便笺门面的契约：键名与前端 ActivitySnapshot 一致，参数错误原样上抛。

采集实现（collector / provider / parser / transport）自带单测以外的覆盖成本很高，
这里只钉住对外可观察的三件事：快照键名、实参透传、参数错误不被降级。
"""

from __future__ import annotations

import asyncio

import pytest
from signflow_notes.contracts import CommunityActivitySnapshot
from signflow_notes.notes import NotesFacade

# 采集快照的真实形状：见 signflow_notes/contracts.py 的
#
#   CommunityActivitySnapshot.to_dict()
#
# 便笺门面只做驼峰收敛，不增删键。
SNAPSHOT = CommunityActivitySnapshot(
    account="主号",
    account_uid="0f21f760-8d5b-4f4e-8f6a-2c3d4e5f6a7b",
    game="明日方舟",
    platform="森空岛",
    status="success",
    completed=3,
    target=3,
    tasks=({"name": "日常活跃度", "completed": 3, "target": 3, "status": "已完成"},),
    resources=({"name": "理智", "current": 120, "target": 135, "status": "恢复中"},),
    reason="",
    updated_at="2026-11-20T21:00:00+08:00",
    role_name="博士",
    role_uid="1234567",
    server="官服",
    source="/api/v1/game/player/info",
)


class _FakeCollector:
    """最小采集面：让便笺门面能在无宿主进程时跑通调用链。"""

    def __init__(self, snapshots, *, error=None):
        self.calls: list[object] = []
        self._snapshots = snapshots
        self._error = error

    async def query(self, account_ids=None):
        """记录实参并返回预置快照，模拟真实采集器。"""

        self.calls.append(account_ids)
        if self._error is not None:
            raise self._error
        return self._snapshots


def test_snapshots_use_camel_case_contract():
    """便笺输出键名与前端 ActivitySnapshot 一致，其余键保持快照原样。"""

    collector = _FakeCollector([SNAPSHOT])
    notes = asyncio.run(NotesFacade(collector).snapshots())

    assert len(notes) == 1
    assert notes[0]["accountUid"] == SNAPSHOT.account_uid
    assert notes[0]["updatedAt"] == SNAPSHOT.updated_at
    assert notes[0]["roleName"] == SNAPSHOT.role_name
    assert notes[0]["roleUid"] == SNAPSHOT.role_uid
    # 未列在别名表里的键必须原样保留，避免便笺层悄悄改了快照契约。
    assert notes[0]["account"] == SNAPSHOT.account
    assert notes[0]["game"] == SNAPSHOT.game
    assert notes[0]["platform"] == SNAPSHOT.platform
    assert notes[0]["status"] == SNAPSHOT.status
    # to_dict() 会把 tasks / resources 逐项摊成普通 dict 列表，便于直接序列化
    assert notes[0]["tasks"] == [dict(item) for item in SNAPSHOT.tasks]
    assert notes[0]["resources"] == [dict(item) for item in SNAPSHOT.resources]
    # 不再出现蛇形键，避免下游同时维护两套键名。
    assert "account_uid" not in notes[0]
    assert "updated_at" not in notes[0]
    assert collector.calls == [None]


def test_snapshots_forward_account_ids():
    """传入账号组时原样交给采集器，不在便笺层做去重或过滤之外的处理。"""

    collector = _FakeCollector([])

    notes = asyncio.run(NotesFacade(collector).snapshots(["a", "b"]))

    assert notes == ()
    assert collector.calls == [["a", "b"]]


def test_snapshots_propagate_value_error():
    """账号组不存在属于参数错误，必须上抛而不是降级成空结果。"""

    collector = _FakeCollector([], error=ValueError("未找到指定的游戏社区账号组"))

    with pytest.raises(ValueError, match="未找到指定的游戏社区账号组"):
        asyncio.run(NotesFacade(collector).snapshots(["missing"]))
