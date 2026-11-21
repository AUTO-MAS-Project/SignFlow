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
"""Token 门面：凭据状态盘点与刷新写回，逐条覆盖每一种回话。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import pytest
from auto_mas_core import Plugin
from signflow_token import credentials
from signflow_token.credentials import TokenFacade

_PLATFORMS = (
    ("SklandToken", "森空岛"),
    ("MiyousheToken", "米游社"),
    ("CloudGenshinToken", "云原神"),
    ("KuroToken", "库街区"),
    ("TaygedoToken", "塔吉多"),
)


@dataclass
class _Account:
    """账号门面的账号投影：uid、名字、启用状态与凭据映射。"""

    uid: str
    name: str = "主号"
    enabled: bool = True
    tokens: dict[str, str] = field(default_factory=dict)


class _Community:
    """核心插件账号门面的替身：只实现 Token 用到的五个方法。"""

    def __init__(self, accounts: list[_Account], platforms=_PLATFORMS) -> None:
        self._accounts = accounts
        self._platforms = platforms
        self.persisted: list[tuple[str, str, str]] = []

    def platforms(self):
        """凭据字段名与平台显示名的对照。"""

        return tuple(self._platforms)

    def token_fields(self):
        """宿主注册表里的凭据字段顺序。"""

        return tuple(field for field, _ in self._platforms)

    def accounts(self):
        """全部账号组。"""

        return tuple(self._accounts)

    def account(self, account_uid: str) -> _Account | None:
        """按 UID 取账号；None 表示账号组不存在。"""

        return next((item for item in self._accounts if item.uid == account_uid), None)

    def proxy(self) -> str:
        """宿主代理设置；测试里留空，不真的走网络。"""

        return ""


class _Registry:
    """宿主服务表的替身：require 返回「调用后得到门面」的方法。"""

    def __init__(self, community: _Community) -> None:
        self._community = community

    def require(self, name: str):
        """只认核心插件账号服务，其余服务名视为缺陷。"""

        assert name == "signflow.community"
        return lambda: self._community


def _patch(monkeypatch, community: _Community) -> None:
    """把宿主服务表换成替身，避免真的去读账号配置。"""

    monkeypatch.setattr(Plugin, "services", _Registry(community), raising=False)


def test_status_lists_every_registered_field(monkeypatch) -> None:
    """每个账号都按宿主注册表列全部凭据字段，空字段明确标成未配置。"""

    _patch(monkeypatch, _Community([_Account("a")]))

    row = TokenFacade().status()[0]

    assert [item["field"] for item in row["items"]] == [
        field for field, _ in _PLATFORMS
    ]
    assert all(item["configured"] is False for item in row["items"])
    assert all(item["message"] == "尚未配置" for item in row["items"])


def test_status_filters_by_account_ids(monkeypatch) -> None:
    """传入账号列表时只返回这些账号；空列表退化为全量。"""

    community = _Community([_Account("a"), _Account("b")])
    _patch(monkeypatch, community)

    facade = TokenFacade()

    assert [row["uid"] for row in facade.status(["b"])] == ["b"]
    assert len(facade.status([])) == 2


def test_status_reports_invalid_credential(monkeypatch) -> None:
    """格式不合法的凭据标成无效，并把宿主的原因原样带出来。"""

    account = _Account("a", tokens={"SklandToken": '{"cred":"only-cred"}'})
    _patch(monkeypatch, _Community([account]))

    item = TokenFacade().status()[0]["items"][0]

    assert item["field"] == "SklandToken"
    assert item["configured"] is True
    assert item["checked"] is True
    assert item["valid"] is False
    assert "必须同时包含" in str(item["message"])


def test_status_marks_unregistered_platform_as_unchecked(monkeypatch) -> None:
    """宿主新增平台但本插件还没接通校验时，如实说没校验，不伪装成通过。"""

    community = _Community(
        [_Account("a", tokens={"NewToken": "x"})],
        platforms=(("NewToken", "新平台"),),
    )
    _patch(monkeypatch, community)

    item = TokenFacade().status()[0]["items"][0]

    assert item["configured"] is True
    assert item["checked"] is False
    assert item["valid"] is False
    assert item["message"] == "该平台暂不支持本地校验"


def test_refresh_rejects_missing_account(monkeypatch) -> None:
    """账号组不存在时提示去选一个，而不是抛 KeyError。"""

    _patch(monkeypatch, _Community([]))

    with pytest.raises(ValueError, match="已保存的社区账号"):
        asyncio.run(TokenFacade().refresh("missing"))


def test_refresh_rejects_account_without_credentials(monkeypatch) -> None:
    """账号在但一个凭据都没配时，直接说没得刷新。"""

    _patch(monkeypatch, _Community([_Account("a")]))

    with pytest.raises(ValueError, match="还没有可刷新的凭据"):
        asyncio.run(TokenFacade().refresh("a"))


def test_refresh_writes_back_updated_credential(monkeypatch) -> None:
    """刷新出新值时写回账号组，并如实报告已更新。"""

    account = _Account("a", tokens={"SklandToken": "old"})
    community = _Community([account])
    _patch(monkeypatch, community)

    async def fake_refresh(platform: str, raw: str, proxy: str | None) -> str:
        assert platform == "森空岛"
        assert proxy == ""
        return "new"

    persisted: list[tuple[str, str, str]] = []

    async def fake_persist(account_uid: str, field: str, raw: str) -> None:
        persisted.append((account_uid, field, raw))

    monkeypatch.setattr(credentials, "_refresh_one", fake_refresh)
    monkeypatch.setattr(credentials, "_persist", fake_persist)

    result = asyncio.run(TokenFacade().refresh("a"))

    assert result["uid"] == "a"
    assert persisted == [("a", "SklandToken", "new")]
    assert result["items"] == [
        {
            "field": "SklandToken",
            "platform": "森空岛",
            "refreshed": True,
            "message": "凭据已更新",
        }
    ]


def test_refresh_keeps_going_after_one_platform_fails(monkeypatch) -> None:
    """单个平台失败不影响其它平台，失败项单独带上原因。"""

    account = _Account("a", tokens={"SklandToken": "old", "TaygedoToken": "旧"})
    _patch(monkeypatch, _Community([account]))

    async def fake_refresh(platform: str, raw: str, proxy: str | None) -> str:
        if platform == "森空岛":
            raise ValueError("森空岛凭据刷新失败: 上游拒绝请求")
        return "新"

    persisted: list[tuple[str, str, str]] = []

    async def fake_persist(account_uid: str, field: str, raw: str) -> None:
        persisted.append((account_uid, field, raw))

    monkeypatch.setattr(credentials, "_refresh_one", fake_refresh)
    monkeypatch.setattr(credentials, "_persist", fake_persist)

    items = asyncio.run(TokenFacade().refresh("a"))["items"]

    assert [item["refreshed"] for item in items] == [False, True]
    assert "上游拒绝请求" in str(items[0]["message"])
    assert persisted == [("a", "TaygedoToken", "新")]


def test_refresh_skips_persist_when_value_unchanged(monkeypatch) -> None:
    """上游回同一个值时不必写盘，如实说凭据仍然有效。"""

    account = _Account("a", tokens={"SklandToken": "same"})
    _patch(monkeypatch, _Community([account]))

    async def fake_refresh(platform: str, raw: str, proxy: str | None) -> str:
        return "same"

    async def fake_persist(account_uid: str, field: str, raw: str) -> None:
        raise AssertionError("值没变时不应写回")

    monkeypatch.setattr(credentials, "_refresh_one", fake_refresh)
    monkeypatch.setattr(credentials, "_persist", fake_persist)

    item = asyncio.run(TokenFacade().refresh("a"))["items"][0]

    assert item["refreshed"] is True
    assert item["message"] == "凭据仍然有效"


def test_refresh_reports_persist_failure(monkeypatch) -> None:
    """写回失败不能说成成功：上游可能已消费旧凭据。"""

    account = _Account("a", tokens={"SklandToken": "old"})
    _patch(monkeypatch, _Community([account]))

    async def fake_refresh(platform: str, raw: str, proxy: str | None) -> str:
        return "new"

    async def fake_persist(account_uid: str, field: str, raw: str) -> None:
        raise OSError("磁盘只读")

    monkeypatch.setattr(credentials, "_refresh_one", fake_refresh)
    monkeypatch.setattr(credentials, "_persist", fake_persist)

    item = asyncio.run(TokenFacade().refresh("a"))["items"][0]

    assert item["refreshed"] is False
    assert item["message"] == "刷新成功但写回失败，请重试"


def test_refresh_only_touches_requested_fields(monkeypatch) -> None:
    """指定字段时只刷新这些字段，没配的字段跳过而不是报错。"""

    account = _Account("a", tokens={"SklandToken": "old", "TaygedoToken": "旧"})
    _patch(monkeypatch, _Community([account]))

    seen: list[str] = []

    async def fake_refresh(platform: str, raw: str, proxy: str | None) -> str:
        seen.append(platform)
        return f"{raw}-new"

    async def fake_persist(account_uid: str, field: str, raw: str) -> None:
        return None

    monkeypatch.setattr(credentials, "_refresh_one", fake_refresh)
    monkeypatch.setattr(credentials, "_persist", fake_persist)

    asyncio.run(TokenFacade().refresh("a", ["SklandToken", "KuroToken"]))

    assert seen == ["森空岛"]
