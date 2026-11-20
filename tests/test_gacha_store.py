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
"""抽卡记录存档：去重、倒序、上限与非破坏性读取。"""

from __future__ import annotations

import json

import pytest
import signflow_gacha.store as store_module
from signflow_gacha.models import GachaRecord
from signflow_gacha.store import GachaStore, record_key


def _record(**overrides: object) -> GachaRecord:
    """造一条合法记录；默认值取明日方舟的一条六星。"""

    payload: dict[str, object] = {
        "game": "arknights",
        "playerUid": "1001",
        "id": "1",
        "poolType": "1",
        "name": "能天使",
        "rarity": 6,
        "time": "2026-01-01 12:00:00",
    }
    payload.update(overrides)
    return GachaRecord.model_validate(payload)


def test_merge_counts_only_new_records(tmp_path) -> None:
    """同一记录读取两次只留一条，第二次新增数为零。"""

    store = GachaStore(tmp_path / "gacha.json")
    assert store.merge([_record()]) == 1
    assert store.merge([_record()]) == 0
    assert len(store.load()) == 1


def test_merge_sorts_by_time_desc(tmp_path) -> None:
    """存档按时间倒序落盘，前端第一页看到的就是最近一抽。"""

    store = GachaStore(tmp_path / "gacha.json")
    store.merge([_record(id="1", time="2026-01-01 12:00:00")])
    store.merge([_record(id="2", time="2026-01-02 12:00:00")])

    assert [item.id for item in store.load()] == ["2", "1"]


def test_record_key_covers_game_uid_pool_and_id() -> None:
    """判据是四项组合：换任一维度都不该被当成同一条。"""

    base = _record()
    assert record_key(base) == ("arknights", "1001", "1", "1")
    assert record_key(_record(poolType="2")) != record_key(base)
    assert record_key(_record(playerUid="1002")) != record_key(base)


def test_merge_rejects_oversized_archive(tmp_path, monkeypatch) -> None:
    """超过上限时拒绝写入，避免用户还不知情就被丢掉一部分记录。"""

    monkeypatch.setattr(store_module, "MAX_RECORDS", 1)
    store = GachaStore(tmp_path / "gacha.json")

    with pytest.raises(ValueError, match="导出备份"):
        store.merge([_record(id="1"), _record(id="2")])


def test_load_returns_empty_when_archive_missing(tmp_path) -> None:
    """没有存档就是没有记录，不建空文件也不报错。"""

    assert GachaStore(tmp_path / "gacha.json").load() == []


def test_load_rejects_corrupted_entry(tmp_path) -> None:
    """坏条目上抛而不是返回空列表；空列表会让下一次合并覆盖整份存档。"""

    path = tmp_path / "gacha.json"
    path.write_text(
        json.dumps({"version": 1, "records": [{"game": "arknights"}]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="存档已损坏"):
        GachaStore(path).load()


def test_load_rejects_unknown_field(tmp_path) -> None:
    """多出来的字段按模型约定报错，不静默接受半份数据。"""

    path = tmp_path / "gacha.json"
    payload = {**_record().model_dump(), "extra": "x"}
    path.write_text(json.dumps({"version": 1, "records": [payload]}), encoding="utf-8")

    with pytest.raises(ValueError, match="存档已损坏"):
        GachaStore(path).load()


def test_load_rejects_broken_json(tmp_path) -> None:
    """JSON 语法坏档也落到同一句文案，不把宿主的配置口吻抛给用户。"""

    path = tmp_path / "gacha.json"
    path.write_text("{ not json", encoding="utf-8")

    with pytest.raises(ValueError, match="存档已损坏"):
        GachaStore(path).load()
