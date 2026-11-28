#   SignFlow: AUTO-MAS 游戏社区核心插件
#   Copyright © 2024-2025 DLmaster361
#   Copyright © 2025-2026 AUTO-MAS Team

#   This file is part of SignFlow.

#   SignFlow is free software: you can redistribute it and/or modify
#   it under the terms of the GNU Affero General Public License as
#   published by the Free Software Foundation, either version 3 of the
#   License, or (at your option) any later version.

#   SignFlow is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty
#   of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#   GNU Affero General Public License for more details.

#   You should have received a copy of the GNU Affero General Public License
#   along with SignFlow. If not, see <https://www.gnu.org/licenses/>.

#   Contact: DLmaster_361@163.com
"""签到门面契约：跳过判据、凭据回写失败、完成日期标记与平台合流。

平台协议实现、凭据字段清单与结果契约都留在宿主，这里用假宿主只钉住插件
自己新增的判断：哪些账号该跑、凭据写回失败怎么呈现、什么时候记完成日期。
真实的网络签到流程成本太高且依赖账号，不在这里覆盖。
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import signflow_sign.sign as sign_module
from auto_mas_core.host.utils import UTC8
from signflow_sign.sign import SignFacade, all_enabled_platforms_signed

TODAY = datetime.now(tz=UTC8).strftime("%Y-%m-%d")


class _FakeProvider:
    """宿主 provider 注册表条目里签到侧真正会用到的那两个字段。"""

    def __init__(self, token_field: str, log_name: str) -> None:
        self.token_field = token_field
        self.log_name = log_name


class _FakeRun:
    """宿主 run_community_provider 的返回值形状。"""

    def __init__(
        self,
        *,
        results: list[dict[str, object]] | None = None,
        platforms: tuple[str, ...] = (),
        credential_updates: dict[str, str] | None = None,
    ) -> None:
        self.results = list(results or [])
        self.platforms = platforms
        self.credential_updates = dict(credential_updates or {})


class _FakeAccount:
    """账号门面投影；字段名与 CommunityAccount 一致。"""

    def __init__(
        self,
        uid: str,
        *,
        name: str = "主号",
        enabled: bool = True,
        tokens: dict[str, str] | None = None,
        last_signed_on: str = "",
    ) -> None:
        self.uid = uid
        self.name = name
        self.enabled = enabled
        self.tokens = dict(tokens or {})
        self.last_signed_on = last_signed_on


class _FakeCommunity:
    """只实现签到用到的四个方法，写回落到自己的账本上而不是真配置。"""

    def __init__(self, accounts: list[_FakeAccount]) -> None:
        self._accounts = list(accounts)
        self.saved: list[tuple[str, str, str]] = []
        self.marked: list[str] = []
        self.save_error: Exception | None = None

    def accounts(self) -> tuple[_FakeAccount, ...]:
        return tuple(self._accounts)

    def account(self, account_uid: str) -> _FakeAccount | None:
        for item in self._accounts:
            if item.uid == account_uid:
                return item
        return None

    async def save_credential(self, account_uid: str, field: str, value: str) -> None:
        if self.save_error is not None:
            raise self.save_error
        self.saved.append((account_uid, field, value))
        # 宿主写回会让下次投影读到新值，这里同步一份，收尾重读才走得通。
        target = self.account(account_uid)
        if target is not None:
            target.tokens[field] = value

    async def mark_signed(self, account_uid: str) -> None:
        self.marked.append(account_uid)


def _install(
    monkeypatch: Any,
    community: _FakeCommunity,
    providers: list[_FakeProvider],
    runs: dict[str, _FakeRun],
) -> list[tuple[str, str]]:
    """把门面依赖的三处宿主能力换成假实现，返回 provider 调用记录。"""

    calls: list[tuple[str, str]] = []

    async def fake_run(
        provider: _FakeProvider,
        token: str,
        *,
        account_name: str,
        account_uid: str,
        on_credential_update: Any = None,
    ) -> _FakeRun:
        calls.append((provider.token_field, token))
        run = runs[provider.token_field]
        if on_credential_update is not None:
            for field, value in run.credential_updates.items():
                try:
                    await on_credential_update(field, value)
                except RuntimeError:
                    # 宿主的真实 provider 会吞掉回调里的写回异常，把它留给
                    # 编排层的收尾兜底；假 provider 保持同一行为，否则测出来
                    # 的是「异常怎么冒泡」而不是「失败怎么被记录」。
                    continue
        return run

    monkeypatch.setattr(sign_module, "_community", lambda: community)
    monkeypatch.setattr(sign_module, "get_community_sign_providers", lambda: providers)
    monkeypatch.setattr(sign_module, "run_community_provider", fake_run)
    return calls


def test_skips_disabled_account(monkeypatch: Any) -> None:
    """停用的账号既不请求上游也不写回，避免给已关掉的账号发请求。"""

    community = _FakeCommunity(
        [_FakeAccount("uid-1", enabled=False, tokens={"SklandToken": "t"})]
    )
    calls = _install(
        monkeypatch,
        community,
        [_FakeProvider("SklandToken", "森空岛")],
        {"SklandToken": _FakeRun(platforms=("森空岛",))},
    )

    results = asyncio.run(SignFacade().run())

    assert results == []
    assert calls == []
    assert community.marked == []


def test_skips_account_signed_today_unless_forced(monkeypatch: Any) -> None:
    """自动签到跳过今日已签账号，手动签到（force）仍然重跑一遍。"""

    account = _FakeAccount("uid-1", tokens={"SklandToken": "t"}, last_signed_on=TODAY)
    community = _FakeCommunity([account])
    calls = _install(
        monkeypatch,
        community,
        [_FakeProvider("SklandToken", "森空岛")],
        {"SklandToken": _FakeRun(platforms=("森空岛",))},
    )

    assert asyncio.run(SignFacade().run()) == []
    assert calls == []

    asyncio.run(SignFacade().run(force=True))
    assert calls == [("SklandToken", "t")]


def test_cloud_genshin_reuses_miyoushe_cookie(monkeypatch: Any) -> None:
    """云原神没有独立凭据时，用本轮米游社 Cookie 换取临时凭据。"""

    cookie = "account_id=1; cookie_token=token"
    community = _FakeCommunity(
        [_FakeAccount("uid-1", tokens={"MiyousheToken": cookie})]
    )
    calls = _install(
        monkeypatch,
        community,
        [
            _FakeProvider("MiyousheToken", "米游社"),
            _FakeProvider("CloudGenshinToken", "云原神"),
        ],
        {
            "MiyousheToken": _FakeRun(platforms=("米游社",)),
            "CloudGenshinToken": _FakeRun(platforms=("米游社",)),
        },
    )

    asyncio.run(SignFacade().run())

    # 云原神拿到的必须是米游社 Cookie 原文，而不是空串。
    assert ("CloudGenshinToken", cookie) in calls


def test_credential_save_failure_becomes_visible_result(monkeypatch: Any) -> None:
    """凭据刷新后写回失败要在结果里留一条，而不是只在日志里消失。"""

    community = _FakeCommunity([_FakeAccount("uid-1", tokens={"SklandToken": "old"})])
    community.save_error = RuntimeError("disk full")
    _install(
        monkeypatch,
        community,
        [_FakeProvider("SklandToken", "森空岛")],
        {
            "SklandToken": _FakeRun(
                platforms=("森空岛",), credential_updates={"SklandToken": "new"}
            )
        },
    )

    results = asyncio.run(SignFacade().run())

    assert community.saved == []
    failure = [
        item
        for item in results
        if str(item.get("reason") or "").startswith("刷新凭据已生成")
    ]
    assert len(failure) == 1
    assert failure[0]["status"] == "失败"
    assert failure[0]["game"] == "森空岛凭据"
    assert failure[0]["platform"] == "森空岛"
    assert failure[0]["account_uid"] == "uid-1"


def test_marks_signed_after_auto_run_even_if_failed(monkeypatch: Any) -> None:
    """自动签到每天只试一次：失败也要记当天，避免后续任务反复重试。"""

    community = _FakeCommunity([_FakeAccount("uid-1", tokens={"SklandToken": "t"})])
    _install(
        monkeypatch,
        community,
        [_FakeProvider("SklandToken", "森空岛")],
        {
            "SklandToken": _FakeRun(
                results=[
                    {
                        "account": "主号/森空岛",
                        "account_uid": "uid-1",
                        "game": "明日方舟",
                        "platform": "森空岛",
                        "status": "失败",
                        "reason": "登录失效",
                    }
                ],
                platforms=("森空岛",),
            )
        },
    )

    asyncio.run(SignFacade().run())

    assert community.marked == ["uid-1"]


def test_forced_run_marks_signed_only_when_all_platforms_done(
    monkeypatch: Any,
) -> None:
    """手动签到只在全部平台完成后才记日期，失败时保留重试入口。"""

    community = _FakeCommunity([_FakeAccount("uid-1", tokens={"SklandToken": "t"})])
    _install(
        monkeypatch,
        community,
        [_FakeProvider("SklandToken", "森空岛")],
        {
            "SklandToken": _FakeRun(
                results=[
                    {
                        "account": "主号/森空岛",
                        "account_uid": "uid-1",
                        "game": "明日方舟",
                        "platform": "森空岛",
                        "status": "失败",
                        "reason": "登录失效",
                    }
                ],
                platforms=("森空岛",),
            )
        },
    )

    asyncio.run(SignFacade().run(force=True))
    assert community.marked == []


def test_no_configured_credential_yields_no_results(monkeypatch: Any) -> None:
    """账号存在但一个凭据都没填时直接跳过，不产生占位结果。"""

    community = _FakeCommunity([_FakeAccount("uid-1")])
    calls = _install(
        monkeypatch,
        community,
        [_FakeProvider("SklandToken", "森空岛")],
        {"SklandToken": _FakeRun(platforms=("森空岛",))},
    )

    assert asyncio.run(SignFacade().run()) == []
    assert calls == []


def test_all_enabled_platforms_signed_requires_every_platform() -> None:
    """完成判据按平台逐个核对，缺一条结果或任一条未完成都算没签完。"""

    results: list[dict[str, object]] = [
        {"account_uid": "uid-1", "platform": "森空岛", "status": "成功"},
        {"account_uid": "uid-1", "platform": "米游社", "status": "失败"},
        # 其它账号的结果不参与本账号判定。
        {"account_uid": "uid-2", "platform": "库街区", "status": "成功"},
    ]

    assert not all_enabled_platforms_signed(
        results, account_uid="uid-1", enabled_platforms=["森空岛", "米游社"]
    )
    assert all_enabled_platforms_signed(
        results, account_uid="uid-2", enabled_platforms=["库街区"]
    )
    # 一个平台都没跑过时不能算完成，否则会误记当天签到。
    assert not all_enabled_platforms_signed(
        results, account_uid="uid-1", enabled_platforms=[]
    )
