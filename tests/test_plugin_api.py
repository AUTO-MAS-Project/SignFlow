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
"""核心插件代发端点：附属插件缺失与参数错误都要给出可读结论。"""

from __future__ import annotations

import asyncio

from signflow.api import NotesQueryIn, query_daily_notes


# 宿主 `provides_services` 注册的是插件实例上的方法本身（`CallGate.wrap` 包过的
# 那个），所以 `require(...)` 返回的就是可调用的协程方法，代发端点直接 await 它。
# 替身必须按这个形状写，否则测出来的不是真实调用链。


class _Missing:
    """未安装便笺插件时的服务面：require 抛 PluginError。"""

    def require(self, name: str):
        """模拟宿主未登记 signflow.notes。"""

        from auto_mas_core import PluginError

        raise PluginError(f"服务未注册: {name}")


class _Facade:
    """按插件实例方法的行为返回预置结果或抛出预置异常。"""

    def __init__(self, *, snapshots=None, error=None):
        self._snapshots = snapshots
        self._error = error

    async def snapshots(self, account_ids=None):
        """复现 NotesFacade.snapshots 的成功或失败行为。"""

        if self._error is not None:
            raise self._error
        return self._snapshots or ()


class _Plugin:
    """便笺插件实例替身：query_notes() 是协程方法，直接被代发端点调用。"""

    def __init__(self, facade):
        self._facade = facade

    async def query_notes(self, account_ids=None):
        """对应 provides_services 里登记的 query_notes 方法。"""

        return await self._facade.snapshots(account_ids)


class _Services:
    """只认识 signflow.notes 的服务面。"""

    def __init__(self, *args, **kwargs):
        self._plugin = _Plugin(_Facade(*args, **kwargs))

    def require(self, name: str):
        """返回宿主会给出的可调用对象，而不是门面本身。"""

        assert name == "signflow.notes"
        return self._plugin.query_notes


def _patch_services(monkeypatch, services):
    """替换 SDK Plugin 单例上的服务解析器。"""

    from auto_mas_core import Plugin

    monkeypatch.setattr(Plugin, "services", services, raising=False)


def test_missing_notes_plugin_reports_disabled(monkeypatch):
    """便笺插件未启用时返回 400 与可读原因，而不是 404 或 500。"""

    _patch_services(monkeypatch, _Missing())

    result = asyncio.run(query_daily_notes(NotesQueryIn()))

    assert result.code == 400
    assert result.status == "error"
    assert result.message == "日常便笺插件未启用"
    assert result.data == []


def test_invalid_account_reports_host_message(monkeypatch):
    """账号组不存在时把宿主的中文原因回给调用方。"""

    _patch_services(monkeypatch, _Services(error=ValueError("未找到指定的游戏社区账号组")))

    result = asyncio.run(query_daily_notes(NotesQueryIn(accountIds=["missing"])))

    assert result.code == 400
    assert result.message == "未找到指定的游戏社区账号组"


def test_unexpected_failure_hides_details(monkeypatch):
    """非参数类异常只回通用文案，不把堆栈或上游正文带给前端。"""

    _patch_services(monkeypatch, _Services(error=RuntimeError("上游返回了内部地址 10.0.0.1")))

    result = asyncio.run(query_daily_notes(NotesQueryIn()))

    assert result.code == 500
    assert result.message == "日常便笺查询失败"
    assert "10.0.0.1" not in result.message


def test_success_returns_camel_case_rows(monkeypatch):
    """成功分支原样透传便笺插件的驼峰投影，并回报条数。"""

    _patch_services(
        monkeypatch,
        _Services(snapshots=({"account": "主号", "accountUid": "uid-1"},)),
    )

    result = asyncio.run(query_daily_notes(NotesQueryIn()))

    assert result.code == 200
    assert result.message == "共 1 条日常便笺"
    assert result.data == [{"account": "主号", "accountUid": "uid-1"}]
