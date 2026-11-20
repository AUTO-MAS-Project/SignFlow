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
"""日常便笺门面的契约：键名与前端 ActivitySnapshot 一致，参数错误原样上抛。"""

from __future__ import annotations

import asyncio

import pytest

from signflow_notes.notes import NotesFacade


# 宿主快照的真实形状：见 app/tools/common/community/contracts.py 的
#
#   CommunityActivitySnapshot.to_dict()
#
# 插件只做驼峰收敛，不增删键。
HOST_SNAPSHOT = {
    "account": "主号",
    "account_uid": "0f21f760-8d5b-4f4e-8f6a-2c3d4e5f6a7b",
    "game": "明日方舟",
    "platform": "森空岛",
    "status": "success",
    "completed": 3,
    "target": 3,
    "tasks": ({"name": "日常活跃度", "completed": 3, "target": 3, "status": "已完成"},),
    "resources": ({"name": "理智", "current": 120, "target": 135, "status": "恢复中"},),
    "reason": "",
    "updated_at": "2026-11-20T21:00:00+08:00",
    "role_name": "博士",
    "role_uid": "1234567",
    "server": "官服",
    "source": "/api/v1/game/player/info",
}


class _FakeRegistry:
    """最小服务面：让便笺门面能在无宿主进程时跑通调用链。"""

    def __init__(self, snapshots, *, error=None):
        self.calls: list[object] = []
        self._snapshots = snapshots
        self._error = error

    def require(self, name: str):
        """只认 signflow.activity，其他服务名按未注册处理。"""

        assert name == "signflow.activity"

        async def query(account_ids=None):
            """记录实参并返回预置快照，模拟核心插件服务。"""

            self.calls.append(account_ids)
            if self._error is not None:
                raise self._error
            return self._snapshots

        return query


def _patch_services(monkeypatch, registry):
    """把假服务注册表挂到 SDK 的 Plugin 单例上。"""

    from auto_mas_core import Plugin

    monkeypatch.setattr(Plugin, "services", registry, raising=False)


def test_snapshots_use_camel_case_contract(monkeypatch):
    """便笺输出键名与前端 ActivitySnapshot 一致，其余键保持宿主原样。"""

    registry = _FakeRegistry([HOST_SNAPSHOT])
    _patch_services(monkeypatch, registry)

    notes = asyncio.run(NotesFacade().snapshots())

    assert len(notes) == 1
    assert notes[0]["accountUid"] == HOST_SNAPSHOT["account_uid"]
    assert notes[0]["updatedAt"] == HOST_SNAPSHOT["updated_at"]
    assert notes[0]["roleName"] == HOST_SNAPSHOT["role_name"]
    assert notes[0]["roleUid"] == HOST_SNAPSHOT["role_uid"]
    # 未列在别名表里的键必须原样保留，避免插件悄悄改了宿主契约。
    assert notes[0]["account"] == HOST_SNAPSHOT["account"]
    assert notes[0]["game"] == HOST_SNAPSHOT["game"]
    assert notes[0]["platform"] == HOST_SNAPSHOT["platform"]
    assert notes[0]["status"] == HOST_SNAPSHOT["status"]
    assert notes[0]["tasks"] == HOST_SNAPSHOT["tasks"]
    assert notes[0]["resources"] == HOST_SNAPSHOT["resources"]
    # 不再出现蛇形键，避免下游同时维护两套键名。
    assert "account_uid" not in notes[0]
    assert "updated_at" not in notes[0]
    assert registry.calls == [None]


def test_snapshots_forward_account_ids(monkeypatch):
    """传入账号组时原样交给核心插件，不在便笺层做去重或过滤之外的处理。"""

    registry = _FakeRegistry([])
    _patch_services(monkeypatch, registry)

    notes = asyncio.run(NotesFacade().snapshots(["a", "b"]))

    assert notes == ()
    assert registry.calls == [["a", "b"]]


def test_snapshots_propagate_value_error(monkeypatch):
    """账号组不存在属于参数错误，必须上抛而不是降级成空结果。"""

    registry = _FakeRegistry([], error=ValueError("未找到指定的游戏社区账号组"))
    _patch_services(monkeypatch, registry)

    with pytest.raises(ValueError, match="未找到指定的游戏社区账号组"):
        asyncio.run(NotesFacade().snapshots(["missing"]))
