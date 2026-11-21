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
"""抽卡门面：筛选分页、保底统计，以及读取前的每一道前置检查。"""

from __future__ import annotations

import asyncio

import pytest
from auto_mas_core import Plugin
from signflow_gacha.gacha import GachaFacade
from signflow_gacha.models import GachaRecord
from signflow_gacha.store import GachaStore


def _record(**overrides: object) -> GachaRecord:
    """造一条合法记录；默认值取明日方舟的一条六星。"""

    payload: dict[str, object] = {
        "game": "arknights",
        "playerUid": "1001",
        "id": "1",
        "poolType": "1",
        "poolName": "限定寻访",
        "name": "能天使",
        "rarity": 6,
        "time": "2026-01-01 12:00:00",
    }
    payload.update(overrides)
    return GachaRecord.model_validate(payload)


def _facade(tmp_path, records: list[GachaRecord] | None = None) -> GachaFacade:
    """在临时目录上建一份存档，避免碰到宿主 data 目录。"""

    store = GachaStore(tmp_path / "gacha.json")
    if records:
        store.merge(records)
    return GachaFacade(store)


def test_supported_games_only_lists_registered_protocols(tmp_path) -> None:
    """只有登记过协议的游戏才算支持；其余是结构预留。"""

    assert _facade(tmp_path).supported_games() == ("arknights",)


def test_query_filters_and_paginates(tmp_path) -> None:
    """按 UID 与卡池筛选，再按页切；总数是筛选后的条数。"""

    facade = _facade(
        tmp_path,
        [
            _record(id="1", time="2026-01-03 12:00:00"),
            _record(id="2", time="2026-01-02 12:00:00"),
            _record(id="3", playerUid="1002", time="2026-01-01 12:00:00"),
        ],
    )

    result = facade.query("arknights", player_uid="1001", page=1, page_size=1)

    assert result["total"] == 2
    assert [item["id"] for item in result["data"]] == ["1"]
    assert result["players"] == ["1001", "1002"]


def test_query_reports_draws_since_top_rarity(tmp_path) -> None:
    """保底距离＝最新一次六星之前已抽了多少发。"""

    facade = _facade(
        tmp_path,
        [
            _record(id="1", time="2026-01-03 12:00:00", rarity=3),
            _record(id="2", time="2026-01-02 12:00:00", rarity=6),
            _record(id="3", time="2026-01-01 12:00:00", rarity=4),
        ],
    )

    pool = facade.query("arknights")["pools"][0]

    assert pool["topRarity"] == 6
    assert pool["topCount"] == 1
    assert pool["sinceTop"] == 1


def test_query_skips_gift_rows_in_pool_stats(tmp_path) -> None:
    """礼包类记录不计入保底统计，否则距离会被无关行冲淡。"""

    facade = _facade(
        tmp_path,
        [
            _record(id="1", time="2026-01-03 12:00:00", rarity=3),
            _record(id="2", time="2026-01-02 12:00:00", kind="gift_intel_book"),
        ],
    )

    pool = facade.query("arknights")["pools"][0]

    assert pool["total"] == 1
    # 礼包行剔除后只剩一发三星，池里没有六星，距离就是全池条数。
    assert pool["sinceTop"] == 1


def test_fetch_rejects_unregistered_game(tmp_path) -> None:
    """没登记协议的游戏明确报「暂未支持」，不伪装成读取成功。"""

    with pytest.raises(ValueError, match="暂未支持"):
        asyncio.run(
            _facade(tmp_path).fetch(
                "genshin", account_uid="a", player_uid="1", max_pages=1
            )
        )


def test_fetch_rejects_empty_uid(tmp_path) -> None:
    """UID 为空时先拦下来，不去打官方接口。"""

    with pytest.raises(ValueError, match="请填写游戏 UID"):
        asyncio.run(
            _facade(tmp_path).fetch(
                "arknights", account_uid="a", player_uid="   ", max_pages=1
            )
        )


class _Account:
    """账号门面返回的账号：只带 token 映射。"""

    def __init__(self, tokens: dict[str, str]) -> None:
        self.tokens = tokens


class _Community:
    """核心插件账号门面的替身：只实现抽卡用到的两个方法。"""

    def __init__(self, account: _Account | None) -> None:
        self._account = account

    def account(self, account_uid: str) -> _Account | None:
        """按 UID 取账号；None 表示账号组不存在。"""

        return self._account

    def token_field(self, platform: str) -> str:
        """凭据字段名与宿主注册表一致。"""

        assert platform == "森空岛"
        return "SklandToken"


class _Registry:
    """宿主服务表的替身：require 返回「调用后得到门面」的方法。"""

    def __init__(self, community: _Community) -> None:
        self._community = community

    def require(self, name: str):
        """只认核心插件账号服务，其余服务名视为缺陷。"""

        assert name == "signflow.community"
        return lambda: self._community


def _patch_community(monkeypatch, community: _Community) -> None:
    """把宿主服务表换成替身，避免真的去读账号配置。"""

    monkeypatch.setattr(Plugin, "services", _Registry(community), raising=False)


def test_fetch_reports_missing_account(tmp_path, monkeypatch) -> None:
    """账号组不存在时提示去选一个，而不是抛 KeyError。"""

    _patch_community(monkeypatch, _Community(None))

    with pytest.raises(ValueError, match="已保存的社区账号"):
        asyncio.run(
            _facade(tmp_path).fetch(
                "arknights", account_uid="missing", player_uid="1001", max_pages=1
            )
        )


def test_fetch_reports_account_without_skland_token(tmp_path, monkeypatch) -> None:
    """账号在但没登森空岛时，提示去帐号管理登录。"""

    _patch_community(monkeypatch, _Community(_Account({})))

    with pytest.raises(ValueError, match="尚未登录森空岛"):
        asyncio.run(
            _facade(tmp_path).fetch(
                "arknights", account_uid="a", player_uid="1001", max_pages=1
            )
        )


def test_fetch_rejects_while_another_read_is_running(tmp_path) -> None:
    """同一时刻只允许一个读取；重复触发直接失败而不是排队堆积。"""

    facade = _facade(tmp_path)
    lock_held = facade._lock

    async def run() -> None:
        async with lock_held:
            with pytest.raises(ValueError, match="正在读取"):
                await facade.fetch(
                    "arknights", account_uid="a", player_uid="1001", max_pages=1
                )

    asyncio.run(run())


def test_query_never_touches_the_store_through_upstream(tmp_path) -> None:
    """列表查询只读本地存档：不给它凭据也能出结果，证明不会顺手打上游。

    这是「抽卡不自动刷新」的落地守护：如果哪天有人在 query 里加了拉取，
    没登记账号的实现会立刻失败。
    """

    facade = _facade(tmp_path, [_record(id="1", time="2026-01-01 12:00:00")])

    result = facade.query("arknights")

    assert result["total"] == 1
    assert result["data"][0]["id"] == "1"
