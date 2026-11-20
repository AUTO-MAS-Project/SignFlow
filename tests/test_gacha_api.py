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
"""核心插件代发的抽卡端点：缺插件、参数错误、部分成功都要给出可读结论。"""

from __future__ import annotations

import asyncio

from signflow.api import (
    GachaFetchIn,
    GachaQueryIn,
    fetch_gacha_records,
    get_gacha_games,
    query_gacha_records,
)


class _Missing:
    """未安装抽卡插件时的服务面：require 一律抛 PluginError。"""

    def require(self, name: str):
        """模拟宿主未登记抽卡服务。"""

        from auto_mas_core import PluginError

        raise PluginError(f"服务未注册: {name}")


class _Services:
    """按服务名返回插件实例上的方法本身（与宿主注册形状一致）。"""

    def __init__(self, plugin: object) -> None:
        self._plugin = plugin

    def require(self, name: str):
        """把服务名映射到插件方法，名字写错即报错。"""

        mapping = {
            "signflow.gacha": "query_records",
            "signflow.gacha.fetch": "fetch_records",
            "signflow.gacha.games": "supported_games",
        }
        return getattr(self._plugin, mapping[name])


class _Plugin:
    """抽卡插件实例的替身：可预置返回值或异常。"""

    def __init__(
        self,
        *,
        games=None,
        query_result=None,
        fetch_result=None,
        error=None,
    ) -> None:
        self._games = games or ()
        self._query_result = query_result
        self._fetch_result = fetch_result
        self._error = error

    async def supported_games(self):
        """返回预置的游戏列表。"""

        if self._error is not None:
            raise self._error
        return self._games

    async def query_records(self, game, **kwargs):
        """返回预置的查询结果。"""

        if self._error is not None:
            raise self._error
        return self._query_result or {}

    async def fetch_records(self, game, **kwargs):
        """返回预置的读取结果。"""

        if self._error is not None:
            raise self._error
        return self._fetch_result or {}


def _patch(monkeypatch, services) -> None:
    """换掉宿主服务表，避免真的去加载插件。"""

    from auto_mas_core import Plugin

    monkeypatch.setattr(Plugin, "services", services, raising=False)


def test_games_reports_missing_plugin(monkeypatch) -> None:
    """抽卡插件没装时提示未启用，而不是 500。"""

    _patch(monkeypatch, _Missing())

    result = asyncio.run(get_gacha_games())

    assert result.code == 400
    assert result.message == "抽卡记录插件未启用"


def test_games_lists_registered_games(monkeypatch) -> None:
    """装了插件就返回已支持的游戏，前端据此点亮页签。"""

    _patch(monkeypatch, _Services(_Plugin(games=("arknights",))))

    result = asyncio.run(get_gacha_games())

    assert result.code == 200
    assert result.games == ["arknights"]


def test_query_returns_page_and_pools(monkeypatch) -> None:
    """查询结果原样透传给前端，total 与 pools 都不做二次加工。"""

    payload = {
        "data": [{"id": "1", "name": "能天使"}],
        "total": 1,
        "players": ["1001"],
        "pools": [{"poolType": "1", "sinceTop": 1}],
    }
    _patch(monkeypatch, _Services(_Plugin(query_result=payload)))

    result = asyncio.run(query_gacha_records(GachaQueryIn()))

    assert result.code == 200
    assert result.total == 1
    assert result.data == [{"id": "1", "name": "能天使"}]
    assert result.players == ["1001"]
    assert result.pools == [{"poolType": "1", "sinceTop": 1}]


def test_query_passes_value_error_through(monkeypatch) -> None:
    """存档损坏这类本地问题由插件给结论，端点原样回给调用方。"""

    _patch(
        monkeypatch,
        _Services(_Plugin(error=ValueError("抽卡记录存档已损坏，无法安全读取"))),
    )

    result = asyncio.run(query_gacha_records(GachaQueryIn()))

    assert result.code == 400
    assert "存档已损坏" in result.message


def test_query_hides_internal_error(monkeypatch) -> None:
    """未知异常只回一句通用结论，不泄露内部细节。"""

    _patch(monkeypatch, _Services(_Plugin(error=RuntimeError("boom"))))

    result = asyncio.run(query_gacha_records(GachaQueryIn()))

    assert result.code == 500
    assert result.message == "抽卡记录查询失败"


def test_fetch_marks_partial_when_warnings(monkeypatch) -> None:
    """有卡池没读完时状态是 partial，告警原样带出。"""

    _patch(
        monkeypatch,
        _Services(
            _Plugin(
                fetch_result={
                    "added": 3,
                    "fetched": 5,
                    "warnings": ["卡池 1 读取未完成"],
                }
            )
        ),
    )

    result = asyncio.run(
        fetch_gacha_records(GachaFetchIn(accountUid="a", playerUid="1001"))
    )

    assert result.code == 200
    assert result.status == "partial"
    assert (result.added, result.fetched) == (3, 5)
    assert result.warnings == ["卡池 1 读取未完成"]


def test_fetch_reports_success_without_warnings(monkeypatch) -> None:
    """全部读完时状态是 success。"""

    _patch(
        monkeypatch,
        _Services(_Plugin(fetch_result={"added": 2, "fetched": 2, "warnings": []})),
    )

    result = asyncio.run(
        fetch_gacha_records(GachaFetchIn(accountUid="a", playerUid="1001"))
    )

    assert result.status == "success"
    assert result.message == "读取 2 条，新增 2 条"


def test_fetch_passes_value_error_through(monkeypatch) -> None:
    """凭据缺失等可直接展示的原因原样上抛。"""

    _patch(
        monkeypatch,
        _Services(
            _Plugin(error=ValueError("该账号尚未登录森空岛，请先在帐号管理中完成登录"))
        ),
    )

    result = asyncio.run(
        fetch_gacha_records(GachaFetchIn(accountUid="a", playerUid="1001"))
    )

    assert result.code == 400
    assert "尚未登录森空岛" in result.message


def test_fetch_reports_missing_plugin(monkeypatch) -> None:
    """读取时抽卡插件不在也回未启用，而不是 500。"""

    _patch(monkeypatch, _Missing())

    result = asyncio.run(
        fetch_gacha_records(GachaFetchIn(accountUid="a", playerUid="1001"))
    )

    assert result.code == 400
    assert result.message == "抽卡记录插件未启用"
