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
"""抽卡记录的本地存档。

一处存档一个 JSON 文件，落在宿主的 data 目录下，跟着用户的备份走，不混进
config：记录是纯数据，丢一份不如换一份，配置坏了却会让整个插件起不来。

写入走宿主的 `write_file()`（同目录 .tmp + fsync + 原子替换），所以断电或
进程被杀时留下的是旧存档而不是半个 JSON。合并时按 `record_key` 覆盖去重，
同一抽卡记录重复读取多少次都只留一条。
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from pydantic import ValidationError

from .models import GachaRecord

__all__ = ["MAX_RECORDS", "GachaStore", "record_key"]

# 单账号抽卡记录上限。比这个数更大的存档先导出再分文件，插件不替用户
# 决定要丢掉哪些记录。
MAX_RECORDS = 200_000

STORE_VERSION = 1


def record_key(item: GachaRecord) -> tuple[str, str, str, str]:
    """记录的唯一性判据：同游戏、同 UID、同卡池、同记录编号。"""

    return item.game, item.playerUid, item.poolType, item.id


def _sort_key(item: GachaRecord) -> tuple[str, int, str]:
    """按时间倒序；同一秒内短 id 在前，保证排序稳定可比。"""

    return item.time, len(item.id), item.id


class GachaStore:
    """抽卡记录存档；只做读、写、合并，不判断权限也不发请求。"""

    __slots__ = ("_path",)

    def __init__(self, path: Path | None = None) -> None:
        """允许显式指定存档路径，测试与将来的多存档共用一份实现。"""

        self._path = path

    @property
    def path(self) -> Path:
        """存档路径；未显式指定时取宿主 data 目录下的插件命名空间。

        宿主目前没有「插件专属数据目录」的约定，这里按 `data/signflow/`
        建一个命名空间，既不会和本体文件重名，用户备份时也能整目录带走。
        """

        if self._path is not None:
            return self._path

        from auto_mas_core.host.core import Config

        return Config.data_path / "signflow" / "gacha.json"

    def load(self) -> list[GachaRecord]:
        """读取全部记录；存档不存在时返回空列表。

        存档存在但解析失败时上抛 `ValueError`，不用空列表顶替：调用方一旦
        把空列表当成「确实没有记录」，下一次合并就会把整份存档覆盖掉。
        """

        from auto_mas_core.host.utils import io as _io

        try:
            payload = _io.read_dict_file(self.path)
        except _io.ConfigCorruptedError as error:
            # 宿主的坏档异常文案是通用配置口吻，这里换成抽卡记录自己的说法，
            # 免得用户以为是自己改坏了设置。
            raise ValueError(
                f"抽卡记录存档已损坏，无法安全读取：{self.path}"
            ) from error
        raw = payload.get("records")
        if not isinstance(raw, list):
            return []

        records: list[GachaRecord] = []
        for item in raw:
            try:
                records.append(GachaRecord.model_validate(item))
            except ValidationError as error:
                # 只报存档路径，不回显条目内容：损坏的存档里可能混着上一次
                # 手工编辑留下的任意文本。
                raise ValueError(
                    f"抽卡记录存档已损坏，无法安全读取：{self.path}"
                ) from error
        return records

    def write(self, records: Iterable[GachaRecord]) -> None:
        """整份覆盖写入，调用方负责先合并好。"""

        from auto_mas_core.host.utils import io as _io

        _io.write_file(
            self.path,
            {
                "version": STORE_VERSION,
                "records": [item.model_dump() for item in records],
            },
        )

    def merge(self, incoming: Iterable[GachaRecord]) -> int:
        """把新记录并入存档，返回新增条数。

        读、合、写在一处同步完成：宿主跑在单一事件循环里，同步函数不会被
        其它协程打断，所以不需要额外的锁也不会丢更新。
        """

        existing = {record_key(item): item for item in self.load()}
        before = len(existing)
        for item in incoming:
            existing[record_key(item)] = item
        if len(existing) > MAX_RECORDS:
            raise ValueError("记录超过 20 万条，请先导出备份后分开管理")

        self.write(sorted(existing.values(), key=_sort_key, reverse=True))
        return len(existing) - before
