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
"""核心插件代发的凭据端点：缺插件、参数错误、部分失败都要给出可读结论。"""

from __future__ import annotations

import asyncio

from signflow.api import (
    TokenRefreshIn,
    TokenStatusIn,
    query_token_status,
    refresh_token_credential,
)


class _Missing:
    """未安装 Token 插件时的服务面：require 一律抛 PluginError。"""

    def require(self, name: str):
        """模拟宿主未登记 Token 服务。"""

        from auto_mas_core import PluginError

        raise PluginError(f"服务未注册: {name}")


class _Services:
    """按服务名返回插件实例上的方法本身（与宿主注册形状一致）。"""

    def __init__(self, plugin: object) -> None:
        self._plugin = plugin

    def require(self, name: str):
        """把服务名映射到插件方法，名字写错即报错。"""

        mapping = {
            "signflow.token": "credential_status",
            "signflow.token.refresh": "refresh_credential",
        }
        return getattr(self._plugin, mapping[name])


class _Plugin:
    """Token 插件实例的替身：可预置返回值或异常。"""

    def __init__(
        self,
        *,
        status_result=None,
        refresh_result=None,
        error=None,
    ) -> None:
        self._status_result = status_result
        self._refresh_result = refresh_result
        self._error = error

    async def credential_status(self, account_ids=None):
        """返回预置的状态盘点结果。"""

        if self._error is not None:
            raise self._error
        return self._status_result or ()

    async def refresh_credential(self, account_uid, fields=None):
        """返回预置的刷新结果。"""

        if self._error is not None:
            raise self._error
        return self._refresh_result or {}


def _patch(monkeypatch, services) -> None:
    """换掉宿主服务表，避免真的去加载插件。"""

    from auto_mas_core import Plugin

    monkeypatch.setattr(Plugin, "services", services, raising=False)


def test_status_reports_missing_plugin(monkeypatch) -> None:
    """Token 插件没装时提示未启用，而不是 500。"""

    _patch(monkeypatch, _Missing())

    result = asyncio.run(query_token_status(TokenStatusIn()))

    assert result.code == 400
    assert result.message == "Token 获取插件未启用"
    assert result.data == []


def test_status_returns_rows_without_plaintext(monkeypatch) -> None:
    """状态行原样透传，且结果里不该出现凭据原文。"""

    row = {
        "uid": "a",
        "name": "主号",
        "enabled": True,
        "items": [
            {
                "field": "SklandToken",
                "platform": "森空岛",
                "configured": True,
                "checked": True,
                "valid": True,
                "message": "凭据格式有效",
            }
        ],
    }
    _patch(monkeypatch, _Services(_Plugin(status_result=(row,))))

    result = asyncio.run(query_token_status(TokenStatusIn()))

    assert result.code == 200
    assert result.message == "共 1 个账号组"
    assert result.data == [row]


def test_status_passes_value_error_through(monkeypatch) -> None:
    """插件给出的可读原因原样回给调用方。"""

    _patch(monkeypatch, _Services(_Plugin(error=ValueError("账号组不存在"))))

    result = asyncio.run(query_token_status(TokenStatusIn()))

    assert result.code == 400
    assert result.message == "账号组不存在"


def test_status_hides_internal_error(monkeypatch) -> None:
    """未知异常只回一句通用结论，不泄露内部细节。"""

    _patch(monkeypatch, _Services(_Plugin(error=RuntimeError("boom"))))

    result = asyncio.run(query_token_status(TokenStatusIn()))

    assert result.code == 500
    assert result.message == "凭据状态盘点失败"


def test_refresh_marks_partial_when_one_platform_failed(monkeypatch) -> None:
    """有平台刷新失败时状态是 partial，逐项原因原样带出。"""

    payload = {
        "uid": "a",
        "items": [
            {
                "field": "SklandToken",
                "platform": "森空岛",
                "refreshed": False,
                "message": "森空岛凭据刷新失败: 上游拒绝请求",
            },
            {
                "field": "TaygedoToken",
                "platform": "塔吉多",
                "refreshed": True,
                "message": "凭据已更新",
            },
        ],
    }
    _patch(monkeypatch, _Services(_Plugin(refresh_result=payload)))

    result = asyncio.run(refresh_token_credential(TokenRefreshIn(accountUid="a")))

    assert result.code == 200
    assert result.status == "partial"
    assert result.uid == "a"
    assert result.message == "共刷新 2 项，失败 1 项"
    assert result.items == payload["items"]


def test_refresh_reports_success_without_failures(monkeypatch) -> None:
    """全部刷新成功时状态是 success。"""

    payload = {
        "uid": "a",
        "items": [
            {
                "field": "SklandToken",
                "platform": "森空岛",
                "refreshed": True,
                "message": "凭据已更新",
            }
        ],
    }
    _patch(monkeypatch, _Services(_Plugin(refresh_result=payload)))

    result = asyncio.run(refresh_token_credential(TokenRefreshIn(accountUid="a")))

    assert result.status == "success"
    assert result.message == "共刷新 1 项，失败 0 项"


def test_refresh_passes_value_error_through(monkeypatch) -> None:
    """账号不存在等可直接展示的原因原样上抛。"""

    _patch(
        monkeypatch,
        _Services(_Plugin(error=ValueError("该账号还没有可刷新的凭据"))),
    )

    result = asyncio.run(refresh_token_credential(TokenRefreshIn(accountUid="a")))

    assert result.code == 400
    assert result.message == "该账号还没有可刷新的凭据"


def test_refresh_reports_missing_plugin(monkeypatch) -> None:
    """刷新时 Token 插件不在也回未启用，而不是 500。"""

    _patch(monkeypatch, _Missing())

    result = asyncio.run(refresh_token_credential(TokenRefreshIn(accountUid="a")))

    assert result.code == 400
    assert result.message == "Token 获取插件未启用"
